import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from google.cloud import storage
from google.oauth2 import service_account
import logging
from datetime import datetime, timedelta

# Add the parent directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.models import File
from config.settings import settings

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_db_session():
    """Create a database session"""
    database_url = f"postgresql://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"
    engine = create_engine(database_url)
    Session = sessionmaker(bind=engine)
    return Session()

def cleanup_deleted_files(days_threshold=30):
    """
    Permanently delete files that have been soft-deleted for more than the specified number of days
    """
    try:
        # Initialize GCS client with specific service account
        gcs_credentials = service_account.Credentials.from_service_account_file(
            settings.GCS_SERVICE_ACCOUNT_KEY
        )
        storage_client = storage.Client(
            project=settings.VERTEX_AI_PROJECT,
            credentials=gcs_credentials
        )
        bucket = storage_client.bucket(settings.GCS_BUCKET_NAME)
        
        # Get database session
        db = get_db_session()
        
        # Calculate the threshold date
        threshold_date = datetime.utcnow() - timedelta(days=days_threshold)
        
        # Get all soft-deleted files older than the threshold
        deleted_files = db.query(File).filter(
            File.is_deleted == True,
            File.created_at < threshold_date
        ).all()
        
        logger.info(f"Found {len(deleted_files)} files to permanently delete")
        
        for file in deleted_files:
            try:
                # Delete from GCS
                blob = bucket.blob(file.storage_path)
                if blob.exists():
                    blob.delete()
                    logger.info(f"Deleted file from GCS: {file.storage_path}")
                else:
                    logger.warning(f"File not found in GCS: {file.storage_path}")
                
                # Delete from database
                db.delete(file)
                logger.info(f"Deleted file record from database: {file.id}")
                
            except Exception as e:
                logger.error(f"Error deleting file {file.id}: {str(e)}")
                continue
        
        # Commit all database changes
        db.commit()
        logger.info("Cleanup completed successfully")
        
    except Exception as e:
        logger.error(f"Error during cleanup: {str(e)}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    # Default to 30 days if no argument is provided
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    cleanup_deleted_files(days) 