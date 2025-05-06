from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File as FastAPIFile, Form, Response, BackgroundTasks
from sqlalchemy.orm import Session
from typing import Dict, Any, List, Optional
from uuid import uuid4
import os
import shutil
from google.cloud import storage
from google.oauth2 import service_account
from datetime import datetime, timedelta
from fastapi.responses import FileResponse
import logging
import tempfile
import json

from db.database import get_db
from db.repositories import FileRepository, UserRepository
from db.models import User, File as DBFile
from core.auth import get_current_user_dependency
from config.settings import settings
from services.security import current_user_dependency
from services.file_processing import extract_content  # We'll create this next
from services.qdrant_service import mcp_qdrant_service
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
    db: Session = Depends(get_db)
):
    """
    List all files for the current user
    """
    file_repo = FileRepository(db)
    files = file_repo.get_by_user(current_user.id)
    
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
        for file in files
    ]

@router.post("/upload")
async def upload_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = FastAPIFile(...),
    query_id: Optional[str] = Form(None),
    message_id: Optional[str] = Form(None),
    current_user: User = Depends(current_user_dependency),
    db: Session = Depends(get_db)
):
    """
    Upload a file
    """
    try:
        # Generate a unique file ID
        file_id = str(uuid4())
        
        # Get file extension
        filename = file.filename
        file_extension = os.path.splitext(filename)[1] if "." in filename else ""
        
        # Create storage path
        storage_path = f"users/{current_user.id}/{file_id}{file_extension}"
        
        # Upload to Google Cloud Storage
        blob = bucket.blob(storage_path)
        
        # Read file content
        content = await file.read()
        
        # Upload to GCS
        blob.upload_from_string(content, content_type=file.content_type)
        
        # Create file record in database
        file_repo = FileRepository(db)
        file_obj = file_repo.create({
            "id": file_id,
            "user_id": current_user.id,
            "filename": filename,
            "file_type": file.content_type,
            "file_size": len(content),
            "storage_path": storage_path,
            "metadata": {
                "indexed_in_qdrant": False,
                "processing_status": "pending"
            }
        })
        
        # --- ADDED: Log successful file record creation ---
        logger.info(f"[UploadEndpoint] Successfully created DB record for file_id: {file_obj.id}. QueryID: {query_id}, MessageID: {message_id}")
        # --- END ADDED ---
        
        # Add task to process file using MCP-Agent with qdrant-store
        background_tasks.add_task(
            process_file_with_mcp_qdrant,
            file_id=file_id,
            file_content=content,
            file_type=file.content_type,
            filename=filename,
            user_id=current_user.id,
            db_session=db,
            websocket_manager=get_websocket_manager(),
            query_id=query_id,
            message_id=message_id
        )
        
        return {
            "id": file_obj.id,
            "filename": file_obj.filename,
            "file_type": file_obj.file_type,
            "file_size": file_obj.file_size,
            "created_at": file_obj.created_at
        }
        
    except Exception as e:
        logger.error(f"Error uploading file: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to upload file"
        )

async def process_file_with_mcp_qdrant(
    file_id: str,
    file_content: bytes,
    file_type: str,
    filename: str,
    user_id: str,
    db_session: Session,
    websocket_manager: Optional[Any] = None,
    query_id: Optional[str] = None,
    message_id: Optional[str] = None
):
    """
    Process a file using mcp-server-qdrant directly
    """
    temp_file_path = None
    try:
        # Create a temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(filename)[1]) as temp_file:
            temp_file.write(file_content)
            temp_file_path = temp_file.name
        
        # Extract content from file
        content = extract_content(temp_file_path)
        if not content:
            raise ValueError(f"Failed to extract content from {filename}")
        
        # Update file status to processing
        file_repo = FileRepository(db_session)
        file_repo.update(file_id, {
            "metadata": {
                "indexed_in_qdrant": False,
                "processing_status": "processing"
            }
        })
        
        # Prepare metadata
        metadata = {
            "file_id": file_id,
            "user_id": user_id,
            "filename": filename,
            "file_type": file_type,
            "created_at": datetime.utcnow().isoformat(),
            "source_type": "user_upload"
        }
        
        # Store in Qdrant using our service
        store_result = await mcp_qdrant_service.store_document(
            content=content,
            metadata=metadata
        )
        
        logger.info(f"Stored file in Qdrant: {store_result}")
        
        # --- ADDED: Log before updating status to completed --- 
        metadata_to_set = {
            "indexed_in_qdrant": True,
            "processing_status": "completed",
            "processed_at": datetime.utcnow().isoformat(),
            "qdrant_result": store_result
        }
        logger.info(f"[{file_id}] Attempting to update DB metadata to: {metadata_to_set}")
        # --- END ADDED ---

        # Update file metadata
        file_repo.update(file_id, {"metadata": metadata_to_set})
        
        # --- ADDED: Explicitly commit the session --- 
        try:
            db_session.commit()
            logger.info(f"[{file_id}] Committed DB session after successful status update.")
        except Exception as commit_err:
            logger.error(f"[{file_id}] Failed to commit DB session after status update: {commit_err}", exc_info=True)
            db_session.rollback() # Rollback on commit error
            # Re-raise or handle appropriately - maybe send error WS message? 
            raise commit_err # Re-raise for now
        # --- END ADDED ---
        
        logger.info(f"Successfully processed file {file_id} using mcp-server-qdrant")
        
        # --- RE-ADDED: Send WebSocket notification on success --- 
        if websocket_manager and query_id:
            # We now have the specific query_id passed from the upload request
            logger.info(f"Attempting to notify query {query_id} about file {file_id} processing completion")
            await websocket_manager.send_consolidated_update(
                query_id=query_id,
                update_type="file_processed",
                message=f"File '{filename}' processed successfully.",
                data={
                    "file_id": file_id,
                    "filename": filename,
                    "status": "completed",
                    "messageId": message_id # Include messageId for frontend correlation
                }
            )
        elif websocket_manager:
             logger.warning(f"File {file_id} processed, but no query_id provided to send WebSocket success notification.")
        # --- END RE-ADDED --- 
        
    except Exception as e:
        # --- ADDED: Rollback session on error --- 
        try:
            db_session.rollback()
            logger.warning(f"[{file_id}] Rolled back DB session due to processing error.")
        except Exception as rollback_err:
            logger.error(f"[{file_id}] Error rolling back DB session after processing error: {rollback_err}", exc_info=True)
        # --- END ADDED ---

        # --- MODIFIED: Enhance error logging --- 
        error_stage = "unknown"
        if temp_file_path is None: error_stage = "temp file creation"
        elif 'content' not in locals(): error_stage = "content extraction"
        elif 'store_result' not in locals(): error_stage = "storing in Qdrant"
        else: error_stage = "updating DB status or sending WS notification"
        
        logger.error(f"Error processing file {file_id} during stage '{error_stage}': {str(e)}", exc_info=True) # Added exc_info=True
        # --- END MODIFIED --- 
        
        # --- RE-ADDED: Send WebSocket notification on error --- 
        if websocket_manager and query_id:
            logger.info(f"Attempting to notify query {query_id} about file {file_id} processing error")
            await websocket_manager.send_consolidated_update(
                query_id=query_id,
                update_type="file_error",
                message=f"Error processing file '{filename}'.",
                data={
                    "file_id": file_id,
                    "filename": filename,
                    "status": "error",
                    "error_message": str(e),
                    "messageId": message_id # Include messageId for frontend correlation
                }
            )
        elif websocket_manager:
            logger.warning(f"File {file_id} failed processing, but no query_id provided to send WebSocket error notification.")
        # --- END RE-ADDED --- 
        
        # Update file with error
        try:
            file_repo = FileRepository(db_session)
            file_obj = file_repo.get(file_id)
            if file_obj:
                metadata = file_obj.meta_data or {}
                metadata["processing_error"] = str(e)
                metadata["processing_status"] = "error"
                file_repo.update(file_id, {"metadata": metadata})
                # --- ADDED: Commit after setting error status --- 
                try:
                    db_session.commit()
                    logger.info(f"[{file_id}] Committed DB session after setting error status.")
                except Exception as commit_err:
                    logger.error(f"[{file_id}] Failed to commit DB session after setting error status: {commit_err}", exc_info=True)
                    db_session.rollback()
                # --- END ADDED ---
        except Exception as inner_e:
            logger.error(f"[{file_id}] Failed to update DB metadata to 'error' status after primary processing error: {str(inner_e)}", exc_info=True)
            # --- ADDED: Rollback if inner update fails --- 
            try:
                db_session.rollback()
            except Exception as rollback_err:
                logger.error(f"[{file_id}] Error rolling back DB session after inner error: {rollback_err}", exc_info=True)
            # --- END ADDED ---
        
    finally:
        # Clean up temporary file
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.unlink(temp_file_path)
            except Exception as e:
                logger.error(f"Error removing temporary file: {str(e)}")

@router.get("/{file_id}")
async def get_file(
    file_id: str,
    current_user: User = Depends(current_user_dependency),
    db: Session = Depends(get_db)
):
    """
    Get file metadata
    """
    file_repo = FileRepository(db)
    file = file_repo.get(file_id)
    
    if not file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found"
        )
    
    if file.user_id != current_user.id:
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
    db: Session = Depends(get_db)
):
    """Download a file by ID"""
    try:
        # Get file from database
        file = db.query(DBFile).filter(
            DBFile.id == file_id,
            DBFile.user_id == current_user.id,
            DBFile.is_deleted == False  # Don't allow downloading deleted files
        ).first()
        
        if not file:
            raise HTTPException(
                status_code=404,
                detail="File not found"
            )
            
        try:
            # Get the blob from Google Cloud Storage
            blob = bucket.blob(file.storage_path)
            
            # Download the content
            content = blob.download_as_bytes()
            
            # Create a response with the file content
            return Response(
                content=content,
                media_type=file.file_type or "application/octet-stream",
                headers={
                    "Content-Disposition": f'attachment; filename="{file.filename}"'
                }
            )
        except Exception as e:
            logger.error(f"Error downloading file from storage: {str(e)}")
            raise HTTPException(
                status_code=404,
                detail="File not found in storage"
            )
    except Exception as e:
        logger.error(f"Error downloading file: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to download file"
        )

@router.get("/{file_id}/direct-download")
async def direct_download_file(
    file_id: str,
    current_user: User = Depends(current_user_dependency),
    db: Session = Depends(get_db)
):
    """
    Direct download endpoint as fallback
    """
    file_repo = FileRepository(db)
    file = file_repo.get(file_id)
    
    if not file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found"
        )
    
    if file.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this file"
        )
    
    try:
        # Get the blob
        blob = bucket.blob(file.storage_path)
        
        # Download the content
        content = blob.download_as_bytes()
        
        # Create a response with the file content
        return Response(
            content=content,
            media_type=file.file_type or "application/octet-stream",
            headers={
                "Content-Disposition": f'attachment; filename="{file.filename}"'
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to download file: {str(e)}"
        )

@router.delete("/{file_id}")
async def delete_file(
    file_id: str,
    current_user: User = Depends(current_user_dependency),
    db: Session = Depends(get_db)
):
    """
    Mark a file as deleted (soft delete)
    """
    file_repo = FileRepository(db)
    file = file_repo.get(file_id)
    
    if not file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found"
        )
    
    if file.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this file"
        )
    
    # Mark the file as deleted instead of removing it
    success = file_repo.update(file_id, {"is_deleted": True})
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete file"
        )
    
    return {"message": "File deleted successfully"}

@router.get("/", response_model=List[Dict[str, Any]])
async def get_files(
    current_user: User = Depends(current_user_dependency),
    db: Session = Depends(get_db)
):
    """Get all files for the current user"""
    try:
        # Get files from database, excluding deleted ones
        files = db.query(DBFile).filter(
            DBFile.user_id == current_user.id,
            DBFile.is_deleted == False  # Only show non-deleted files
        ).all()
        
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
            for file in files
        ]
    except Exception as e:
        logger.error(f"Error getting files: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to get files"
        )

@router.post("/search")
async def search_files(
    query: str = Form(...),
    current_user: User = Depends(current_user_dependency),
    db: Session = Depends(get_db)
):
    """
    Search for files based on content using mcp-server-qdrant
    """
    try:
        # Search in Qdrant
        result_data = await mcp_qdrant_service.search_documents(query=query)
        
        # Debug logging
        logger.info(f"Search results type: {type(result_data)}, content: {result_data}")
        logger.info(f"Current user ID: {current_user.id}")
        
        # Check if the results are in the expected format
        if isinstance(result_data, dict) and 'content' in result_data and isinstance(result_data['content'], list):
            results = result_data['content']
            
            # First item is usually "Results for the query..."
            if len(results) > 1:
                # Process the entries, which are XML-like strings
                file_ids = set()
                user_results = []
                
                # Process all entries after the first one
                for i in range(1, len(results)):
                    result_item = results[i]
                    
                    # Check if the item is a dictionary with 'text' field
                    if isinstance(result_item, dict) and 'text' in result_item:
                        entry = result_item['text']
                    else:
                        # Skip if not the expected format
                        continue
                    
                    # Debug log the entry
                    logger.info(f"Processing entry {i}: {entry}")
                    
                    # Check if it's a string containing an XML-like entry
                    if isinstance(entry, str) and "<entry>" in entry:
                        # Extract content and metadata from the XML-like format
                        content_start = entry.find("<content>") + len("<content>")
                        content_end = entry.find("</content>")
                        content = entry[content_start:content_end] if content_start > 0 and content_end > 0 else ""
                        
                        metadata_start = entry.find("<metadata>") + len("<metadata>")
                        metadata_end = entry.find("</metadata>")
                        metadata_str = entry[metadata_start:metadata_end] if metadata_start > 0 and metadata_end > 0 else "{}"
                        
                        logger.info(f"Extracted metadata string: {metadata_str}")
                        
                        try:
                            metadata = json.loads(metadata_str) if metadata_str else {}
                            logger.info(f"Parsed metadata: {metadata}")
                            logger.info(f"Metadata user_id: {metadata.get('user_id')}, comparing with: {current_user.id}")
                            
                            # For development, if the user is the dev user, accept any results
                            should_include = (
                                metadata.get("user_id") == current_user.id or
                                (settings.DEBUG and current_user.email == "dev@example.com")
                            )
                            
                            logger.info(f"Should include result: {should_include}")
                            
                            # Check if the result belongs to the current user
                            if should_include:
                                # Add file_id to set of seen files
                                file_id = metadata.get("file_id")
                                if file_id:
                                    file_ids.add(file_id)
                                
                                # Add to results
                                user_results.append({
                                    "content": content,
                                    "metadata": metadata,
                                    "score": 0  # Score not available in the current response format
                                })
                        except json.JSONDecodeError:
                            logger.error(f"Failed to parse metadata JSON: {metadata_str}")
                
                # Get full file information for each file_id
                file_repo = FileRepository(db)
                files_info = []
                
                for file_id in file_ids:
                    file = file_repo.get(file_id)
                    if file:
                        files_info.append({
                            "id": file.id,
                            "filename": file.filename,
                            "file_type": file.file_type,
                            "file_size": file.file_size,
                            "created_at": file.created_at,
                            "metadata": file.meta_data
                        })
                
                return {
                    "results": user_results,
                    "files": files_info
                }
        
        # If we reach here, either no results or unexpected format
        return {
            "results": [],
            "files": []
        }
        
    except Exception as e:
        logger.error(f"Error searching files: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error searching files: {str(e)}"
        ) 