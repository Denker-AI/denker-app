from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File as FastAPIFile, Form, Response, BackgroundTasks, Request
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any, List, Optional
from uuid import uuid4
import os
import shutil
from google.cloud import storage
from google.oauth2 import service_account
from datetime import datetime, timedelta
from fastapi.responses import FileResponse, StreamingResponse
import logging
import tempfile
import json
from hashlib import sha256
from inspect import isawaitable
import io
from sqlalchemy import select, cast, Text
from sqlalchemy.dialects.postgresql import JSONB
import asyncio

from db.database import get_db
from db.repositories import FileRepository, UserRepository, MessageRepository
from db.models import User, File as DBFile, FileAttachment as DBFileAttachment
from core.auth import get_current_user_dependency
from config.settings import settings
from services.security import current_user_dependency
from services.qdrant_service import qdrant_service
from mcp_local.core.websocket_manager import get_websocket_manager

# Set up logger
logger = logging.getLogger(__name__)

router = APIRouter()

# Get the appropriate user dependency based on DEBUG mode
current_user_dependency = get_current_user_dependency()

# Initialize Google Cloud Storage client with specific service account for storage
gcs_credentials = service_account.Credentials.from_service_account_file(
    settings.GCS_SERVICE_ACCOUNT_KEY
)
storage_client = storage.Client(
    project=settings.VERTEX_AI_PROJECT,
    credentials=gcs_credentials
)
bucket = storage_client.bucket(settings.GCS_BUCKET_NAME)

@router.get("/list")
async def list_files(
    current_user: User = Depends(current_user_dependency),
    db: AsyncSession = Depends(get_db)
):
    """
    List all files for the current user
    """
    # Ensure current_user is awaited if it's a coroutine
    user = await current_user if isawaitable(current_user) else current_user
    
    file_repo = FileRepository(db)
    files = await file_repo.get_by_user(user.id)
    
    return [
        {
            "id": file.id,
            "filename": file.filename,
            "file_type": file.file_type,
            "file_size": file.file_size,
            "created_at": file.created_at,
            "is_processed": file.is_processed,
            "is_deleted": file.is_deleted,
            "metadata": file.meta_data
        }
        for file in files if not file.is_deleted
    ]

@router.post("/upload")
async def upload_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = FastAPIFile(...),
    original_path: Optional[str] = Form(None),
    query_id: Optional[str] = Form(None),
    message_id: Optional[str] = Form(None),
    current_user: User = Depends(current_user_dependency),
    db: AsyncSession = Depends(get_db)
):
    """
    Upload a file (Electron: store original path, deduplicate by hash)
    """
    logger.info(f"[UploadEndpoint] Entered upload_file. Filename: {file.filename}, Original Path: {original_path}, QueryID: {query_id}, MessageID: {message_id}")
    try:
        # Ensure current_user is awaited if it's a coroutine
        user = await current_user if isawaitable(current_user) else current_user
        logger.info(f"[UploadEndpoint] User resolved: {user.id if user else 'User object is None'}")
        
        file_id = str(uuid4())
        filename = file.filename
        content = await file.read()
        logger.info(f"[UploadEndpoint] File content read. Length: {len(content) if content else 'Content is None'}")

        # Use the original path as storage_path if provided
        storage_path = original_path or filename

        # Compute file hash (SHA256)
        def compute_file_hash(path):
            hasher = sha256()
            with open(path, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    hasher.update(chunk)
            return hasher.hexdigest()

        # If original_path is provided, use it for hashing; otherwise, save to temp and hash
        if original_path and os.path.exists(original_path):
            file_hash = compute_file_hash(original_path)
        else:
            # Save to temp for hashing
            temp_dir = os.path.join("/tmp", "denker_uploads", str(user.id))
            os.makedirs(temp_dir, exist_ok=True)
            local_file_path = os.path.join(temp_dir, f"{file_id}")
            with open(local_file_path, "wb") as f:
                f.write(content)
            file_hash = compute_file_hash(local_file_path)
            storage_path = local_file_path
        logger.info(f"[UploadEndpoint] File hash computed: {file_hash}")

        # Direct query for duplicate check, similar to file_exists endpoint
        stmt = (
            select(DBFile)
            .where(DBFile.user_id == user.id)
            .where(cast(DBFile.meta_data["file_hash"], Text) == file_hash)
            .where(DBFile.is_deleted == False) # Also ensure we don't match soft-deleted files
        )
        logger.info(f"[UploadEndpoint] Performing direct duplicate check for user_id: {user.id}, file_hash: {file_hash}")
        result = await db.execute(stmt)
        existing = result.scalars().first()
        
        if existing:
            logger.info(f"[UploadEndpoint] Direct duplicate check FOUND existing file. File ID: {existing.id}, User ID: {existing.user_id}, Hash in metadata: {existing.meta_data.get('file_hash') if existing.meta_data else 'N/A'}")
            return {
                "id": existing.id,
                "filename": existing.filename,
                "file_type": existing.file_type,
                "file_size": existing.file_size,
                "created_at": existing.created_at,
                "duplicate": True
            }

        # Create file record in DB, using the original path as storage_path and storing the hash
        file_repo = FileRepository(db)
        file_obj = await file_repo.create({
            "id": file_id,
            "user_id": user.id,
            "filename": filename,
            "file_type": file.content_type,
            "file_size": len(content),
            "storage_path": storage_path,  # Store the real path
            "metadata": {
                "indexed_in_qdrant": False,
                "processing_status": "pending",
                "file_hash": file_hash
            }
        })

        logger.info(f"[UploadEndpoint] Successfully created DB record for file_id: {file_obj.id}. QueryID: {query_id}, MessageID: {message_id}")

        # Schedule processing from the original path
        background_tasks.add_task(
            process_file_with_mcp_qdrant,
            file_id=file_id,
            file_content=content,
            file_type=file.content_type,
            filename=filename,
            user_id=user.id,
            db_session=db,
            websocket_manager=get_websocket_manager(),
            query_id=query_id,
            message_id=message_id,
            local_file_path=storage_path
        )

        return {
            "id": file_obj.id,
            "filename": file_obj.filename,
            "file_type": file_obj.file_type,
            "file_size": file_obj.file_size,
            "created_at": file_obj.created_at,
            "duplicate": False
        }

    except Exception as e:
        logger.error(f"Error uploading file: {str(e)}", exc_info=True) # Added exc_info=True
        raise HTTPException(
            status_code=500,
            detail="Failed to upload file"
        )

# --- File processing endpoints using MCP/coordinator are now handled by the local backend (Electron app) ---
# async def process_file_with_mcp_qdrant(
#     file_id: str,
#     file_content: bytes,
#     file_type: str,
#     filename: str,
#     user_id: str,
#     db_session: Session,
#     websocket_manager: Optional[Any] = None,
#     query_id: Optional[str] = None,
#     message_id: Optional[str] = None,
#     local_file_path: Optional[str] = None
# ):
#     ... (comment out full function)

def process_file_with_mcp_qdrant(*args, **kwargs):
    raise NotImplementedError("File processing is now handled by the local backend (Electron app).")

@router.get("/exists")
async def file_exists(hash: str, user_id: str, db: AsyncSession = Depends(get_db)):
    logger.info(f"[FileExistsEndpoint] Received request. Hash: {hash}, User ID: {user_id}")
    
    json_to_check = {"file_hash": hash}

    stmt = (
        select(DBFile)
        .where(DBFile.user_id == user_id)
        # Explicitly cast meta_data to JSONB before using the @> operator
        .where(cast(DBFile.meta_data, JSONB).op("@>")(json_to_check)) 
        .where(DBFile.is_deleted == False)
    )
    logger.info(f"[FileExistsEndpoint] Executing query: {str(stmt).replace(chr(10), ' ')} WITH params: user_id={user_id}, json_to_check={json_to_check}")
    try:
        result = await db.execute(stmt)
        file = result.scalars().first()

        if file:
            logger.info(f"[FileExistsEndpoint] File FOUND (using @> on JSONB). File ID: {file.id}, User ID: {file.user_id}, MetaData: {file.meta_data}")
            return {"exists": True, "file_id": file.id, "metadata": file.meta_data}
        logger.info(f"[FileExistsEndpoint] File NOT found (using @> on JSONB) for Hash: {hash}, User ID: {user_id}")
        return {"exists": False}
    except Exception as e:
        logger.error(f"[FileExistsEndpoint] Error during query execution: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error querying file existence: {str(e)}")

@router.get("/{file_id}")
async def get_file(
    file_id: str,
    current_user: User = Depends(current_user_dependency),
    db: AsyncSession = Depends(get_db)
):
    """
    Get file metadata
    """
    # Ensure current_user is awaited if it's a coroutine
    user = await current_user if isawaitable(current_user) else current_user
    
    file_repo = FileRepository(db)
    file = await file_repo.get(file_id)
    
    if not file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found"
        )
    
    if file.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this file"
        )
    
    return {
        "id": file.id,
        "filename": file.filename,
        "file_type": file.file_type,
        "file_size": file.file_size,
        "created_at": file.created_at,
        "is_processed": file.is_processed,
        "is_deleted": file.is_deleted,
        "metadata": file.meta_data
    }

@router.get("/{file_id}/download")
async def download_file(
    file_id: str,
    current_user: User = Depends(current_user_dependency),
    db: AsyncSession = Depends(get_db)
):
    """Download a file by ID"""
    try:
        # Ensure current_user is awaited if it's a coroutine
        user = await current_user if isawaitable(current_user) else current_user
        
        # Get file from database
        file = await db.get(DBFile, file_id)
        
        if not file:
            raise HTTPException(
                status_code=404,
                detail="File not found"
            )
            
        # Check ownership
        if file.user_id != user.id:
            raise HTTPException(
                status_code=403,
                detail="Not authorized to access this file"
            )
            
        # For files stored in GCS
        if file.storage_path.startswith("gs://"):
            # Parse GCS path
            gcs_path = file.storage_path.replace("gs://", "")
            bucket_name = gcs_path.split("/")[0]
            blob_path = "/".join(gcs_path.split("/")[1:])
            
            # Get from GCS
            bucket = storage_client.bucket(bucket_name)
            blob = bucket.blob(blob_path)
            
            # Get file content
            content = blob.download_as_bytes()
            
            # Create file-like object
            file_obj = io.BytesIO(content)
            
            return StreamingResponse(
                file_obj,
                media_type=file.file_type,
                headers={
                    "Content-Disposition": f'attachment; filename="{file.filename}"'
                }
            )
        
        # For local files
        if os.path.exists(file.storage_path):
            return FileResponse(
                file.storage_path,
                filename=file.filename,
                media_type=file.file_type
            )
            
        # File not found in storage
        raise HTTPException(
            status_code=404,
            detail="File not found in storage"
        )
        
    except Exception as e:
        logger.error(f"Error downloading file: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to download file: {str(e)}"
        )

@router.get("/{file_id}/direct-download")
async def direct_download_file(
    file_id: str,
    current_user: User = Depends(current_user_dependency),
    db: AsyncSession = Depends(get_db)
):
    """Direct download/access to a file's raw data by ID for API use"""
    try:
        # Ensure current_user is awaited if it's a coroutine
        user = await current_user if isawaitable(current_user) else current_user
        
        # Get file from database
        file_repo = FileRepository(db)
        file = await file_repo.get(file_id)
        
        if not file:
            raise HTTPException(
                status_code=404,
                detail="File not found"
            )
            
        # Check ownership
        if file.user_id != user.id:
            raise HTTPException(
                status_code=403,
                detail="Not authorized to access this file"
            )
            
        # For files stored in GCS
        if file.storage_path.startswith("gs://"):
            # Parse GCS path
            gcs_path = file.storage_path.replace("gs://", "")
            bucket_name = gcs_path.split("/")[0]
            blob_path = "/".join(gcs_path.split("/")[1:])
            
            # Get from GCS
            bucket = storage_client.bucket(bucket_name)
            blob = bucket.blob(blob_path)
            
            # Get file content
            content = blob.download_as_bytes()
            
            # Create file-like object
            file_obj = io.BytesIO(content)
            
            # Return raw file content for API use
            return StreamingResponse(
                file_obj,
                media_type=file.file_type
            )
        
        # For local files
        if os.path.exists(file.storage_path):
            return FileResponse(
                file.storage_path,
                media_type=file.file_type
            )
            
        # File not found in storage
        raise HTTPException(
            status_code=404,
            detail="File not found in storage"
        )
        
    except Exception as e:
        logger.error(f"Error accessing file directly: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to access file: {str(e)}"
        )

@router.delete("/{file_id}")
async def delete_file(
    file_id: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(current_user_dependency),
    db: AsyncSession = Depends(get_db)
):
    """
    Delete a file (soft delete in DB and hard delete from Qdrant)
    """
    # Ensure current_user is awaited if it's a coroutine
    user = await current_user if isawaitable(current_user) else current_user
    
    file_repo = FileRepository(db)
    file = await file_repo.get(file_id)
    
    if not file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found"
        )
    
    if file.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this file"
        )
    
    # Soft delete - just mark as deleted
    await file_repo.update(file_id, {"is_deleted": True})
    
    # Add a background task to delete from Qdrant
    background_tasks.add_task(qdrant_service.delete_documents_by_file_id, file_id)
    
    return {"message": "File deletion initiated successfully"}

@router.get("/", response_model=List[Dict[str, Any]])
async def get_files(
    current_user: User = Depends(current_user_dependency),
    db: AsyncSession = Depends(get_db)
):
    """
    Get all files for the current user (duplicate of /list for API consistency)
    """
    # Ensure current_user is awaited if it's a coroutine
    user = await current_user if isawaitable(current_user) else current_user
    
    file_repo = FileRepository(db)
    files = await file_repo.get_by_user(user.id)
    
    return [
        {
            "id": file.id,
            "filename": file.filename,
            "file_type": file.file_type,
            "file_size": file.file_size,
            "created_at": file.created_at,
            "is_processed": file.is_processed,
            "is_deleted": file.is_deleted,
            "metadata": file.meta_data
        }
        for file in files if not file.is_deleted
    ]

@router.post("/search")
async def search_files(
    query: str = Form(...),
    current_user: User = Depends(current_user_dependency),
    db: AsyncSession = Depends(get_db)
):
    """
    Search files by filename
    """
    # Ensure current_user is awaited if it's a coroutine
    user = await current_user if isawaitable(current_user) else current_user
    
    # Get all files
    file_repo = FileRepository(db)
    files = await file_repo.get_by_user(user.id)
    
    # Filter files by query
    query = query.lower()
    filtered_files = [
        {
            "id": file.id,
            "filename": file.filename,
            "file_type": file.file_type,
            "file_size": file.file_size,
            "created_at": file.created_at,
            "is_processed": file.is_processed,
            "is_deleted": file.is_deleted,
            "metadata": file.meta_data
        }
        for file in files
        if query in file.filename.lower() and not file.is_deleted
    ]
    
    return filtered_files

@router.post("/metadata")
async def upload_metadata(request: Request, db: AsyncSession = Depends(get_db)):
    data = await request.json()
    metadata = data.get("metadata")
    embeddings = data.get("embeddings")  # Optionally handle embeddings
    if not metadata:
        raise HTTPException(status_code=400, detail="Missing metadata in request payload")

    # Validate required fields within the metadata object, including file_id
    required_fields = ["user_id", "filename", "file_id"]
    for field in required_fields:
        if field not in metadata or not metadata[field]:
            raise HTTPException(status_code=400, detail=f"Missing or empty required field '{field}' in metadata")

    file_id_from_request = metadata["file_id"]

    # Create a new File record with metadata only
    file_repo = FileRepository(db)
    try:
        create_payload = {
            "id": file_id_from_request,  # Use the file_id from the request
            "user_id": metadata["user_id"],
            "filename": metadata["filename"],
            "file_type": metadata.get("file_type"),
            "file_size": metadata.get("file_size"),
            "storage_path": metadata.get("storage_path", ""), # Include storage_path if available in metadata
            "meta_data": metadata,  # This stores the whole 'metadata' dict from the request
            "is_processed": metadata.get("is_processed", False) # Use is_processed from metadata if provided, else False
        }
        file_obj = await file_repo.create(create_payload)
    except Exception as e:
        logger.error(f"Error creating file record in /metadata endpoint: {e}", exc_info=True)
        # from sqlalchemy.exc import IntegrityError
        # if isinstance(e, IntegrityError):
        #     raise HTTPException(status_code=409, detail=f"File with ID {file_id_from_request} may already exist or another integrity constraint violated.")
        raise HTTPException(status_code=500, detail=f"Database error while creating file metadata: {e}")
        
    # Optionally, store embeddings in Qdrant or elsewhere here
    return {"file_id": file_obj.id, "metadata": file_obj.meta_data}

@router.post("/{file_id}/update")
async def update_file_metadata(file_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    """
    Update the metadata of a specific file.
    This endpoint is designed to be called by trusted backend processes (like the local-backend).
    It merges new metadata with existing metadata.
    """
    try:
        data = await request.json()
        new_metadata = data.get("meta_data")

        if not new_metadata:
            raise HTTPException(status_code=400, detail="meta_data not provided in request body")

        file_repo = FileRepository(db)
        # Fetch the existing file
        file_to_update = await file_repo.get(file_id)

        if not file_to_update:
            raise HTTPException(status_code=404, detail="File not found")

        # Merge new metadata into existing metadata
        if file_to_update.meta_data:
            # Using a direct update approach to ensure JSONB is handled correctly
            updated_metadata = file_to_update.meta_data.copy()
            updated_metadata.update(new_metadata)
        else:
            updated_metadata = new_metadata
        
        # Explicitly update the meta_data field
        file_to_update.meta_data = updated_metadata
        
        # Add the object to the session to mark it as dirty
        db.add(file_to_update)
        
        # Commit the changes to the database
        await db.commit()
        await db.refresh(file_to_update)

        logger.info(f"Successfully updated metadata for file_id: {file_id}. New metadata: {file_to_update.meta_data}")

        return {"id": file_id, "meta_data": file_to_update.meta_data}

    except json.JSONDecodeError:
        logger.error("Invalid JSON received for metadata update.")
        raise HTTPException(status_code=400, detail="Invalid JSON format")
    except Exception as e:
        logger.error(f"Error updating file metadata for {file_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to update file metadata: {str(e)}")

@router.post("/attach-to-message")
async def attach_file_to_message(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(current_user_dependency) # Ensure user is authenticated
):
    """
    Attach a file to a message by creating a FileAttachment record.
    Expects a JSON body with "file_id" and "message_id".
    """
    try:
        data = await request.json()
        file_id = data.get("file_id")
        message_id = data.get("message_id")

        if not file_id or not message_id:
            raise HTTPException(status_code=400, detail="Missing file_id or message_id in request payload")

        # Ensure current_user is awaited if it's a coroutine
        user = await current_user if isawaitable(current_user) else current_user

        # Validate that the file exists and belongs to the user
        file_repo = FileRepository(db)
        file_obj = await file_repo.get(file_id)
        if not file_obj or file_obj.user_id != user.id:
            raise HTTPException(status_code=404, detail="File not found or not authorized")

        # Attempt to find the message with retries to handle potential race conditions
        # where the message record might not have been created yet.
        message_repo = MessageRepository(db) # Assuming MessageRepository is available
        message_obj = None
        max_retries = 5  # Increased from 3
        retry_delay = 1.0  # Increased from 0.5 seconds

        for attempt in range(max_retries):
            message_obj = await message_repo.get(message_id)
            if message_obj:
                # Basic ownership check (can be more thorough if conversation model is complex)
                # This assumes message_obj.conversation.user_id exists if message_obj.conversation is loaded.
                # Adjust based on your actual Message model structure and how user_id is linked.
                # For now, let's assume if the message exists, we can proceed with attachment,
                # and rely on other mechanisms for strict ownership if needed.
                # A more robust check would involve loading conversation and checking its user_id.
                # current_conversation = await db.get(Conversation, message_obj.conversation_id)
                # if not current_conversation or current_conversation.user_id != user.id:
                #     logger.warning(f"Attempt {attempt+1}: Message {message_id} found, but ownership check failed or conversation not found.")
                #     message_obj = None # Treat as not found for retry purposes if ownership fails
                # else:
                break # Message found

            logger.info(f"Attach attempt {attempt + 1}/{max_retries}: Message {message_id} not yet found. Retrying in {retry_delay}s...")
            await asyncio.sleep(retry_delay)
        
        if not message_obj:
            logger.error(f"Failed to find message {message_id} after {max_retries} attempts.")
            raise HTTPException(status_code=404, detail=f"Message with ID {message_id} not found after retries. Cannot attach file.")


        # Check if attachment already exists to prevent duplicates
        stmt = select(DBFileAttachment).where(
            DBFileAttachment.file_id == file_id,
            DBFileAttachment.message_id == message_id
        )
        result = await db.execute(stmt)
        existing_attachment = result.scalars().first()
        if existing_attachment:
            logger.info(f"File {file_id} is already attached to message {message_id}.")
            return {
                "status": "success", 
                "message": "File already attached to message", 
                "attachment_id": existing_attachment.id
            }

        # Create FileAttachment record
        # We need the FileAttachment model, assume it's DBFileAttachment from models.py
        # from db.models import FileAttachment as DBFileAttachment # Add this import if not present
        
        new_attachment = DBFileAttachment(
            id=str(uuid4()),
            file_id=file_id,
            message_id=message_id
        )
        db.add(new_attachment)
        await db.commit()
        await db.refresh(new_attachment)

        logger.info(f"Successfully attached file {file_id} to message {message_id}. Attachment ID: {new_attachment.id}")
        return {
            "status": "success", 
            "message": "File attached to message successfully", 
            "attachment_id": new_attachment.id
        }

    except HTTPException as http_exc:
        raise http_exc # Re-raise HTTPException
    except Exception as e:
        logger.error(f"Error attaching file to message: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to attach file to message: {str(e)}"
        ) 