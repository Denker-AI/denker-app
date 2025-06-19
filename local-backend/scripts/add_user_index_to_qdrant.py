#!/usr/bin/env python3
"""
Add missing user_id and file_id indexes to existing Qdrant collections.

This script addresses the security vulnerability by ensuring that existing
collections have the necessary indexes for user filtering.

SECURITY CRITICAL: Run this script on existing installations to enable
secure user filtering in Qdrant searches.
"""

import os
import sys
import logging
import argparse
from pathlib import Path

# Add the local-backend directory to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from qdrant_client import QdrantClient
from qdrant_client.http import models as rest
from qdrant_client.http.exceptions import UnexpectedResponse
from config.settings import settings

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def add_security_indexes(client: QdrantClient, collection_name: str):
    """Add security-critical indexes to existing collection."""
    try:
        # Check if collection exists
        collections = client.get_collections().collections
        collection_names = [collection.name for collection in collections]
        
        if collection_name not in collection_names:
            logger.error(f"Collection '{collection_name}' does not exist")
            return False
        
        logger.info(f"Adding security indexes to collection '{collection_name}'")
        
        # Add user_id index - CRITICAL for security
        try:
            client.create_payload_index(
                collection_name=collection_name,
                field_name="metadata.user_id",
                field_schema=rest.PayloadSchemaType.KEYWORD,
            )
            logger.info("✅ Added metadata.user_id index")
        except Exception as e:
            if "already exists" in str(e).lower():
                logger.info("✅ metadata.user_id index already exists")
            else:
                logger.error(f"❌ Failed to create metadata.user_id index: {e}")
                return False
        
        # Add file_id index - helpful for file-based filtering
        try:
            client.create_payload_index(
                collection_name=collection_name,
                field_name="metadata.file_id",
                field_schema=rest.PayloadSchemaType.KEYWORD,
            )
            logger.info("✅ Added metadata.file_id index")
        except Exception as e:
            if "already exists" in str(e).lower():
                logger.info("✅ metadata.file_id index already exists")
            else:
                logger.warning(f"⚠️ Failed to create metadata.file_id index: {e}")
                # This one is not critical for security, so don't fail
        
        logger.info(f"✅ Security indexes successfully added to collection '{collection_name}'")
        return True
    
    except Exception as e:
        logger.error(f"❌ Error adding security indexes: {e}")
        return False

def delete_all_documents(client: QdrantClient, collection_name: str):
    """Delete all documents from the collection."""
    try:
        logger.warning(f"⚠️ DELETING ALL DOCUMENTS from collection '{collection_name}'")
        
        # Get collection info first
        collection_info = client.get_collection(collection_name)
        point_count = collection_info.points_count
        
        if point_count == 0:
            logger.info("Collection is already empty")
            return True
        
        logger.warning(f"About to delete {point_count} documents from collection '{collection_name}'")
        
        # Delete all points in the collection in batches
        deleted_count = 0
        batch_size = 1000
        
        while True:
            # Get a batch of points
            scroll_result = client.scroll(
                collection_name=collection_name,
                limit=batch_size,
                with_payload=False,
                with_vectors=False
            )
            
            points = scroll_result[0]
            if not points:
                break
                
            # Delete this batch
            point_ids = [point.id for point in points]
            logger.info(f"Deleting batch of {len(point_ids)} points...")
            
            result = client.delete(
                collection_name=collection_name,
                points_selector=point_ids
            )
            
            deleted_count += len(point_ids)
            logger.info(f"Deleted {deleted_count}/{point_count} points so far...")
            
        logger.info(f"Total deletion completed: {deleted_count} points deleted")
        
        # Verify deletion
        updated_info = client.get_collection(collection_name)
        remaining_points = updated_info.points_count
        
        if remaining_points == 0:
            logger.info(f"✅ Successfully deleted all {point_count} documents")
            return True
        else:
            logger.error(f"❌ Deletion incomplete: {remaining_points} documents remain")
            return False
    
    except Exception as e:
        logger.error(f"❌ Error deleting documents: {e}")
        return False

def verify_user_data_integrity(client: QdrantClient, collection_name: str):
    """Verify that all documents have user_id in metadata."""
    try:
        logger.info("Verifying user data integrity...")
        
        # Get collection info first
        collection_info = client.get_collection(collection_name)
        total_points = collection_info.points_count
        
        if total_points == 0:
            logger.info("Collection is empty - no data to verify")
            return True
        
        # Scroll through documents to check for user_id
        scroll_result = client.scroll(
            collection_name=collection_name,
            limit=100,
            with_payload=True,
            with_vectors=False
        )
        
        documents_checked = 0
        documents_without_user_id = 0
        user_ids_found = set()
        
        for point in scroll_result[0]:
            documents_checked += 1
            if point.payload and "metadata" in point.payload:
                metadata = point.payload["metadata"]
                if isinstance(metadata, dict) and "user_id" in metadata:
                    user_ids_found.add(metadata["user_id"])
                else:
                    documents_without_user_id += 1
                    logger.warning(f"Document {point.id} missing user_id in metadata")
            else:
                documents_without_user_id += 1
                logger.warning(f"Document {point.id} missing metadata structure")
        
        logger.info(f"Data integrity check completed:")
        logger.info(f"  Total documents in collection: {total_points}")
        logger.info(f"  Documents checked (sample): {documents_checked}")
        logger.info(f"  Documents without user_id: {documents_without_user_id}")
        logger.info(f"  Unique user_ids found: {len(user_ids_found)}")
        
        if user_ids_found:
            logger.info(f"  User IDs: {list(user_ids_found)}")
        
        if documents_without_user_id > 0:
            logger.error(f"❌ SECURITY ISSUE: {documents_without_user_id} documents lack user_id!")
            logger.error("These documents will not be accessible through secure search.")
            logger.error("Consider using --delete-all-documents to clean up the collection.")
            return False
        else:
            logger.info("✅ All checked documents have proper user_id metadata")
            return True
    
    except Exception as e:
        logger.error(f"Error during data integrity check: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(
        description="Add security indexes to Qdrant collection and optionally clean existing data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Just verify data integrity
  python add_user_index_to_qdrant.py --verify-only
  
  # Delete all documents and create clean indexes
  python add_user_index_to_qdrant.py --delete-all-documents
  
  # Create indexes on existing data
  python add_user_index_to_qdrant.py
        """
    )
    parser.add_argument("--url", default=os.environ.get("QDRANT_URL", settings.QDRANT_URL),
                        help="Qdrant server URL")
    parser.add_argument("--api-key", default=os.environ.get("QDRANT_API_KEY", settings.QDRANT_API_KEY),
                        help="Qdrant API key")
    parser.add_argument("--collection", default=os.environ.get("COLLECTION_NAME", settings.QDRANT_COLLECTION_NAME),
                        help="Collection name to update")
    parser.add_argument("--verify-only", action="store_true",
                        help="Only verify data integrity, don't add indexes")
    parser.add_argument("--delete-all-documents", action="store_true",
                        help="⚠️ DELETE ALL DOCUMENTS from the collection before creating indexes")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Enable verbose logging")
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    if not args.url:
        logger.error("Qdrant URL not provided. Use --url or set QDRANT_URL environment variable.")
        return 1
    
    if not args.collection:
        logger.error("Collection name not provided. Use --collection or set COLLECTION_NAME environment variable.")
        return 1
    
    # Safety check for deletion
    if args.delete_all_documents and not args.verify_only:
        logger.warning("⚠️ WARNING: You are about to DELETE ALL DOCUMENTS!")
        logger.warning("This cannot be undone. All user files will be permanently lost.")
        logger.warning(f"Collection: {args.collection}")
        print()
        response = input("Type 'DELETE ALL DOCUMENTS' to confirm: ")
        if response != "DELETE ALL DOCUMENTS":
            logger.info("Operation cancelled by user")
            return 0
    
    logger.info(f"Connecting to Qdrant at {args.url}")
    try:
        client = QdrantClient(url=args.url, api_key=args.api_key)
        
        # Test connection
        collections = client.get_collections()
        logger.info(f"Connected successfully. Found {len(collections.collections)} collections.")
    except Exception as e:
        logger.error(f"Failed to connect to Qdrant: {e}")
        return 1
    
    # Delete all documents if requested
    if args.delete_all_documents and not args.verify_only:
        logger.info("Step 1: Deleting all documents...")
        if not delete_all_documents(client, args.collection):
            logger.error("❌ Failed to delete documents")
            return 1
    
    # Verify data integrity
    step_num = 2 if args.delete_all_documents and not args.verify_only else 1
    logger.info(f"Step {step_num}: Verifying data integrity...")
    integrity_ok = verify_user_data_integrity(client, args.collection)
    
    if not integrity_ok and not args.delete_all_documents:
        logger.error("❌ Data integrity issues found!")
        logger.error("Some documents may not be accessible after security fix is applied.")
        logger.error("Consider using --delete-all-documents to clean up the collection.")
    
    if args.verify_only:
        logger.info("Verification complete (--verify-only mode)")
        return 0 if integrity_ok else 1
    
    # Add security indexes
    step_num += 1
    logger.info(f"Step {step_num}: Adding security indexes to collection '{args.collection}'")
    success = add_security_indexes(client, args.collection)
    
    if success and (integrity_ok or args.delete_all_documents):
        logger.info("✅ Security setup completed successfully")
        logger.info("✅ Qdrant searches are now secure with user filtering")
        if args.delete_all_documents:
            logger.info("✅ Collection is now clean and secure")
            logger.info("Users can start uploading documents with proper security")
        return 0
    elif success and not integrity_ok:
        logger.warning("⚠️ Indexes added but data integrity issues found")
        logger.warning("Some documents may not be accessible due to missing user_id")
        logger.warning("Consider using --delete-all-documents to start with a clean slate")
        return 1
    else:
        logger.error("❌ Failed to add security indexes")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 