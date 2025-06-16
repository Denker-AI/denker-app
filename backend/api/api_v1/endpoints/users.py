from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any
from inspect import isawaitable
import logging
import json

from db.database import get_db
from db.repositories import UserRepository
from db.models import User
from core.auth import get_current_user_dependency

router = APIRouter()
logger = logging.getLogger(__name__)

# Get the appropriate user dependency based on DEBUG mode
current_user_dependency = get_current_user_dependency()

@router.get("/profile")
async def get_user_profile(current_user: User = Depends(current_user_dependency)):
    """
    Get current user profile
    """
    # Ensure current_user is awaited if it's a coroutine
    user = await current_user if isawaitable(current_user) else current_user
    
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "metadata": user.meta_data
    }

@router.put("/profile")
async def update_user_profile(
    user_data: Dict[str, Any],
    current_user: User = Depends(current_user_dependency),
    db: AsyncSession = Depends(get_db)
):
    """
    Update user profile
    """
    # Ensure current_user is awaited if it's a coroutine
    user = await current_user if isawaitable(current_user) else current_user
    
    user_repo = UserRepository(db)
    
    # Only allow updating certain fields
    allowed_fields = ["name", "metadata"]
    update_data = {k: v for k, v in user_data.items() if k in allowed_fields}
    
    updated_user = await user_repo.update(user.id, update_data)
    
    return {
        "id": updated_user.id,
        "email": updated_user.email,
        "name": updated_user.name,
        "metadata": updated_user.meta_data
    }

@router.get("/settings")
async def get_user_settings(current_user: User = Depends(current_user_dependency)):
    """
    Get user settings
    """
    user = await current_user if isawaitable(current_user) else current_user
    settings_data = user.meta_data.get("settings", {})
    logger.info(f"Remote GET /settings: Returning for user {user.id}: {json.dumps(settings_data)}")
    return settings_data

@router.put("/settings")
async def update_user_settings(
    settings: Dict[str, Any],
    current_user: User = Depends(current_user_dependency),
    db: AsyncSession = Depends(get_db)
):
    """
    Update user settings
    """
    user = await current_user if isawaitable(current_user) else current_user
    logger.info(f"Remote PUT /settings: Received for user {user.id}. Incoming settings payload: {json.dumps(settings)}")

    user_repo = UserRepository(db)
    
    # Get current metadata
    metadata = user.meta_data or {}
    
    # Update settings in metadata
    # The entire incoming 'settings' dict (which includes accessibleFolders)
    # is placed under a "settings" key in the user's meta_data JSONB field.
    metadata["settings"] = settings
    
    # Update user in the database
    updated_user = await user_repo.update(user.id, {"meta_data": metadata})
    logger.info(f"Remote PUT /settings: User {user.id} metadata updated. Full new metadata: {json.dumps(updated_user.meta_data if updated_user else {})}")
    
    # Return the 'settings' part of the updated metadata
    final_settings = updated_user.meta_data.get("settings", {}) if updated_user and updated_user.meta_data else {}
    logger.info(f"Remote PUT /settings: Returning for user {user.id}: {json.dumps(final_settings)}")
    return final_settings 