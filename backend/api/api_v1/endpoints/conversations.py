from fastapi import APIRouter, Depends, HTTPException, status, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from typing import Dict, Any, List, Optional
from uuid import uuid4
import json
from datetime import datetime

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
    db: Session = Depends(get_db)
):
    """
    List all conversations for the current user, excluding soft-deleted ones.
    """
    conversation_repo = ConversationRepository(db)
    conversations = conversation_repo.get_by_user(current_user.id)
    
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
    db: Session = Depends(get_db)
):
    """
    Create a new conversation
    """
    conversation_repo = ConversationRepository(db)
    
    conversation = conversation_repo.create({
        "user_id": current_user.id,
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
    db: Session = Depends(get_db)
):
    """
    Get a conversation by ID
    """
    conversation_repo = ConversationRepository(db)
    conversation = conversation_repo.get(conversation_id)
    
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )
    
    if conversation.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this conversation"
        )
    
    message_repo = MessageRepository(db)
    paginated_result = message_repo.get_by_conversation(
        conversation_id=conversation_id,
        limit=limit,
        before_message_id=before_message_id
    )
    
    messages = paginated_result["messages"]
    has_more = paginated_result["has_more"]
    
    return {
        "id": conversation.id,
        "title": conversation.title,
        "created_at": conversation.created_at,
        "updated_at": conversation.updated_at,
        "messages": [
            {
                "id": msg.id,
                "content": msg.content,
                "role": msg.role,
                "created_at": msg.created_at,
                "metadata": msg.meta_data
            }
            for msg in messages
        ],
        "pagination": {
            "has_more": has_more
        }
    }

@router.put("/{conversation_id}")
async def update_conversation(
    conversation_id: str,
    data: Dict[str, Any],
    current_user: User = Depends(current_user_dependency),
    db: Session = Depends(get_db)
):
    """
    Update a conversation
    """
    conversation_repo = ConversationRepository(db)
    conversation = conversation_repo.get(conversation_id)
    
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )
    
    if conversation.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this conversation"
        )
    
    # Only allow updating certain fields
    allowed_fields = ["title", "metadata"]
    update_data = {k: v for k, v in data.items() if k in allowed_fields}
    
    updated_conversation = conversation_repo.update(conversation_id, update_data)
    
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
    db: Session = Depends(get_db)
):
    """
    Delete a conversation (soft delete)
    """
    conversation_repo = ConversationRepository(db)
    conversation = conversation_repo.get(conversation_id)
    
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )
    
    if conversation.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this conversation"
        )
    
    success = conversation_repo.delete(conversation_id)
    
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
    db: Session = Depends(get_db)
):
    """
    Add a message to a conversation
    """
    conversation_repo = ConversationRepository(db)
    conversation = conversation_repo.get(conversation_id)
    
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )
    
    if conversation.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to add messages to this conversation"
        )
    
    message_repo = MessageRepository(db)
    
    message = message_repo.create({
        "conversation_id": conversation_id,
        "content": data["content"],
        "role": data["role"],
        "metadata": data.get("metadata", {})
    })
    
    # Update conversation's updated_at timestamp
    conversation_repo.update(conversation_id, {})
    
    return {
        "id": message.id,
        "content": message.content,
        "role": message.role,
        "created_at": message.created_at,
        "metadata": message.meta_data
    }

# WebSocket connection manager and endpoint have been removed as they are redundant.
# The MCP WebSocket implementation in the coordinator_agent.py should be used instead. 