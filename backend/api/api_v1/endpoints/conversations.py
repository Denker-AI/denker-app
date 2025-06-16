from fastapi import APIRouter, Depends, HTTPException, status, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any, List, Optional
from uuid import uuid4
import json
from datetime import datetime
from inspect import isawaitable
from sqlalchemy.exc import SQLAlchemyError

from db.database import get_db
from db.repositories import ConversationRepository, MessageRepository, UserRepository
from db.models import User
from core.auth import get_current_user, get_current_user_dependency, verify_token
from config.settings import settings

router = APIRouter()

# Get the appropriate user dependency based on DEBUG mode
current_user_dependency = get_current_user_dependency()

@router.get("/list")
async def list_conversations(
    current_user: User = Depends(current_user_dependency),
    db: AsyncSession = Depends(get_db)
):
    """
    List all conversations for the current user, excluding soft-deleted ones.
    """
    # Ensure current_user is awaited if it's a coroutine
    user = await current_user if isawaitable(current_user) else current_user
    
    conversation_repo = ConversationRepository(db)
    conversations = await conversation_repo.get_by_user(user.id)
    
    return [
        {
            "id": conv.id,
            "title": conv.title,
            "created_at": conv.created_at,
            "updated_at": conv.updated_at
        }
        for conv in conversations if conv.is_active
    ]

@router.post("/new")
async def create_conversation(
    data: Dict[str, Any],
    current_user: User = Depends(current_user_dependency),
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new conversation
    """
    # Ensure current_user is awaited if it's a coroutine
    user = await current_user if isawaitable(current_user) else current_user
    
    conversation_repo = ConversationRepository(db)
    
    conversation = await conversation_repo.create({
        "user_id": user.id,
        "title": data.get("title", "New Conversation"),
        "metadata": data.get("metadata", {})
    })
    
    return {
        "id": conversation.id,
        "title": conversation.title,
        "created_at": conversation.created_at,
        "updated_at": conversation.updated_at
    }

@router.get("/{conversation_id}")
async def get_conversation(
    conversation_id: str,
    limit: Optional[int] = None,
    before_message_id: Optional[str] = None,
    current_user: User = Depends(current_user_dependency),
    db: AsyncSession = Depends(get_db)
):
    """
    Get a conversation by ID
    """
    # Ensure current_user is awaited if it's a coroutine
    user = await current_user if isawaitable(current_user) else current_user
    
    conversation_repo = ConversationRepository(db)
    conversation = await conversation_repo.get(conversation_id)
    
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )
    
    if conversation.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this conversation"
        )
    
    message_repo = MessageRepository(db)
    paginated_result = await message_repo.get_by_conversation(
        conversation_id=conversation_id,
        limit=limit,
        before_message_id=before_message_id
    )
    
    messages = paginated_result["messages"]
    has_more = paginated_result["has_more"]
    
    processed_messages = []
    for msg in messages:
        # --- ADDED LOG (Corrected) ---
        print(f"[CONV_EP - get_conversation] Message ID {msg.id} - meta_data from DB: {msg.meta_data}")
        # --- END ADDED LOG ---
        processed_messages.append({
            "id": msg.id,
            "content": msg.content,
            "role": msg.role,
            "created_at": msg.created_at,
            "metadata": msg.meta_data,
            "files": [
                {
                    "id": attachment.file.id,
                    "name": attachment.file.filename,
                    "file_type": attachment.file.file_type,
                    "file_size": attachment.file.file_size,
                    "created_at": attachment.file.created_at,
                    # Add other relevant file fields if needed, e.g., a download URL
                    # "url": f"/api/v1/files/{attachment.file.id}/download" # Example
                }
                for attachment in msg.file_attachments if attachment.file
            ]
        })

    return {
        "id": conversation.id,
        "title": conversation.title,
        "created_at": conversation.created_at,
        "updated_at": conversation.updated_at,
        "messages": processed_messages, # Use the processed list here
        "pagination": {
            "has_more": has_more
        }
    }

@router.put("/{conversation_id}")
async def update_conversation(
    conversation_id: str,
    data: Dict[str, Any],
    current_user: User = Depends(current_user_dependency),
    db: AsyncSession = Depends(get_db)
):
    """
    Update a conversation
    """
    # Ensure current_user is awaited if it's a coroutine
    user = await current_user if isawaitable(current_user) else current_user
    
    conversation_repo = ConversationRepository(db)
    conversation = await conversation_repo.get(conversation_id)
    
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )
    
    if conversation.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this conversation"
        )
    
    # Only allow updating certain fields
    allowed_fields = ["title", "metadata"]
    update_data = {k: v for k, v in data.items() if k in allowed_fields}
    
    updated_conversation = await conversation_repo.update(conversation_id, update_data)
    
    return {
        "id": updated_conversation.id,
        "title": updated_conversation.title,
        "created_at": updated_conversation.created_at,
        "updated_at": updated_conversation.updated_at
    }

@router.delete("/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    current_user: User = Depends(current_user_dependency),
    db: AsyncSession = Depends(get_db)
):
    """
    Delete a conversation (soft delete)
    """
    # Ensure current_user is awaited if it's a coroutine
    user = await current_user if isawaitable(current_user) else current_user
    
    conversation_repo = ConversationRepository(db)
    conversation = await conversation_repo.get(conversation_id)
    
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )
    
    if conversation.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this conversation"
        )
    
    success = await conversation_repo.delete(conversation_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete conversation"
        )
    
    return {"message": "Conversation deleted successfully"}

@router.post("/{conversation_id}/messages")
async def add_message(
    conversation_id: str,
    data: Dict[str, Any],
    current_user: User = Depends(current_user_dependency),
    db: AsyncSession = Depends(get_db)
):
    """
    Add a message to a conversation
    """
    # --- ADDED LOG ---
    print(f"[CONV_EP - add_message] Received data: {data}")
    print(f"[CONV_EP - add_message] Initial metadata from data: {data.get('metadata')}")
    # --- END ADDED LOG ---
    user = await current_user if isawaitable(current_user) else current_user
    
    conversation_repo = ConversationRepository(db)
    # Fetch conversation to check existence and ownership. 
    # .get() now eager loads messages, which isn't strictly needed here but is okay.
    conversation = await conversation_repo.get(conversation_id)
    
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )
    
    if conversation.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to add messages to this conversation"
        )
    
    message_repo = MessageRepository(db)
    new_message_data = {
        "id": data.get("id"),
        "conversation_id": conversation_id,
        "content": data["content"],
        "role": data["role"],
        "metadata": data.get("metadata", {})
    }
    # --- ADDED LOG ---
    print(f"[CONV_EP - add_message] new_message_data to be sent to repo: {new_message_data}")
    # --- END ADDED LOG ---

    try:
        # Call repository methods with commit=False
        created_message = await message_repo.create(new_message_data, commit=False)
    
    # Update conversation's updated_at timestamp
        await conversation_repo.update(conversation_id, {"updated_at": datetime.utcnow()}, commit=False)

        await db.commit() # Single commit for both operations

        # Refresh the created_message object AFTER the final commit to ensure all data is loaded,
        # especially if any relationships or further model-level changes were triggered by the commit.
        # The repository's refresh after flush should handle most cases, but an explicit refresh here
        # on the specific instance can be a safeguard.
        await db.refresh(created_message)
        # --- ADDED LOG ---
        print(f"[CONV_EP - add_message] created_message.meta_data after refresh: {created_message.meta_data}")
        # --- END ADDED LOG ---
        # If you also need to ensure the conversation object 'conversation' reflects the updated_at change immediately:
        # await db.refresh(conversation) 

        message_id = created_message.id
        message_content = created_message.content
        message_role = created_message.role
        message_created_at = created_message.created_at
        message_metadata = created_message.meta_data
        # --- ADDED LOG ---
        print(f"[CONV_EP - add_message] message_metadata before return: {message_metadata}")
        # --- END ADDED LOG ---
    
    except SQLAlchemyError as e:
        await db.rollback()
        print(f"Database error adding message: {e}") 
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to add message due to a database error."
        )
    except Exception as e:
        await db.rollback()
        print(f"Unexpected error adding message: {e}") 
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while adding the message."
        )
    
    return {
        "id": message_id,
        "content": message_content,
        "role": message_role,
        "created_at": message_created_at,
        "metadata": message_metadata
    }

@router.put("/{conversation_id}/messages/{message_id}")
async def update_message_in_conversation(
    conversation_id: str,
    message_id: str,
    data: Dict[str, Any],
    current_user: User = Depends(current_user_dependency),
    db: AsyncSession = Depends(get_db)
):
    """
    Update a message in a conversation
    """
    # Ensure current_user is awaited if it's a coroutine
    user = await current_user if isawaitable(current_user) else current_user
    
    conversation_repo = ConversationRepository(db)
    conversation = await conversation_repo.get(conversation_id)
    
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )
    
    if conversation.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this conversation"
        )
    
    message_repo = MessageRepository(db)
    message = await message_repo.get(message_id)
    
    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found"
        )
    
    if message.conversation_id != conversation_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this message"
        )
    
    # Only allow updating certain fields
    allowed_fields = ["content", "role", "metadata"]
    update_data = {k: v for k, v in data.items() if k in allowed_fields}
    
    updated_message = await message_repo.update(message_id, update_data)
    
    return {
        "id": updated_message.id,
        "content": updated_message.content,
        "role": updated_message.role,
        "created_at": updated_message.created_at,
        "metadata": updated_message.meta_data
    }

# WebSocket connection manager and endpoint have been removed as they are redundant.
# The MCP WebSocket implementation in the coordinator_agent.py should be used instead. 