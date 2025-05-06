from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Dict, Any

from db.database import get_db
from db.repositories import UserRepository
from db.models import User
from core.auth import get_current_user_dependency

router = APIRouter()

# Get the appropriate user dependency based on DEBUG mode
current_user_dependency = get_current_user_dependency()

@router.get("/profile")
async def get_user_profile(current_user: User = Depends(current_user_dependency)):
    """
    Get current user profile
    """
    return {
        "id": current_user.id,
        "email": current_user.email,
        "name": current_user.name,
        "metadata": current_user.meta_data
    }

@router.put("/profile")
async def update_user_profile(
    user_data: Dict[str, Any],
    current_user: User = Depends(current_user_dependency),
    db: Session = Depends(get_db)
):
    """
    Update user profile
    """
    user_repo = UserRepository(db)
    
    # Only allow updating certain fields
    allowed_fields = ["name", "metadata"]
    update_data = {k: v for k, v in user_data.items() if k in allowed_fields}
    
    updated_user = user_repo.update(current_user.id, update_data)
    
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
    # Settings are stored in metadata
    settings = current_user.meta_data.get("settings", {})
    return settings

@router.put("/settings")
async def update_user_settings(
    settings: Dict[str, Any],
    current_user: User = Depends(current_user_dependency),
    db: Session = Depends(get_db)
):
    """
    Update user settings
    """
    user_repo = UserRepository(db)
    
    # Get current metadata
    metadata = current_user.meta_data or {}
    
    # Update settings in metadata
    metadata["settings"] = settings
    
    # Update user
    updated_user = user_repo.update(current_user.id, {"metadata": metadata})
    
    return updated_user.meta_data.get("settings", {}) 