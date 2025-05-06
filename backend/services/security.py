from fastapi import Depends, HTTPException, status
from typing import Optional
from core.auth import get_current_user_dependency
from db.models import User

# Get the appropriate user dependency based on DEBUG mode
current_user_dependency = get_current_user_dependency()

def get_current_user(current_user: User = Depends(current_user_dependency)) -> User:
    """
    Helper function to get the current user.
    This is a simple wrapper around the current_user_dependency
    that can be imported consistently across endpoints.
    """
    return current_user 