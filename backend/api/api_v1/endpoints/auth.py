from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any
from inspect import isawaitable

from db.database import get_db
from db.repositories import UserRepository
from core.auth import verify_token, get_token_data

router = APIRouter()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

@router.post("/login")
async def login(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)):
    """
    Verify Auth0 token and create or update user in database
    """
    try:
        # Verify token with Auth0
        token_data = await verify_token(token)
        
        # Get user info from token
        user_data = await get_token_data(token)
        
        # Check if user exists in database
        user_repo = UserRepository(db)
        user = await user_repo.get_by_email(user_data["email"])
        
        if not user:
            # Create new user
            user = await user_repo.create({
                "id": user_data["sub"],
                "email": user_data["email"],
                "name": user_data.get("name", ""),
                "meta_data": {
                    "picture": user_data.get("picture", ""),
                    "locale": user_data.get("locale", "en")
                }
            })
        
        return {
            "access_token": token,
            "token_type": "bearer",
            "user": {
                "id": user.id,
                "email": user.email,
                "name": user.name
            }
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid authentication credentials: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )

@router.post("/logout")
async def logout():
    """
    Logout user (client-side only, token is not invalidated on server)
    """
    return {"message": "Logged out successfully"} 