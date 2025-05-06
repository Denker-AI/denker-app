import jwt
import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional

from config.settings import settings
from db.database import get_db
from db.repositories import UserRepository

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

async def verify_token(token: str) -> Dict[str, Any]:
    """
    Verify Auth0 token
    """
    try:
        jwks_url = f"https://{settings.AUTH0_DOMAIN}/.well-known/jwks.json"
        async with httpx.AsyncClient() as client:
            jwks = await client.get(jwks_url)
            jwks = jwks.json()
        
        unverified_header = jwt.get_unverified_header(token)
        rsa_key = {}
        
        for key in jwks["keys"]:
            if key["kid"] == unverified_header["kid"]:
                rsa_key = {
                    "kty": key["kty"],
                    "kid": key["kid"],
                    "use": key["use"],
                    "n": key["n"],
                    "e": key["e"]
                }
        
        if rsa_key:
            payload = jwt.decode(
                token,
                rsa_key,
                algorithms=settings.AUTH0_ALGORITHMS,
                audience=settings.AUTH0_API_AUDIENCE,
                issuer=f"https://{settings.AUTH0_DOMAIN}/"
            )
            return payload
        
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unable to find appropriate key",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.JWTClaimsError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect claims, please check the audience and issuer",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Unable to parse authentication token: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )

async def get_token_data(token: str) -> Dict[str, Any]:
    """
    Get user data from Auth0 token
    """
    try:
        # Get user info from Auth0
        url = f"https://{settings.AUTH0_DOMAIN}/userinfo"
        headers = {"Authorization": f"Bearer {token}"}
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers)
            return response.json()
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Unable to get user info: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )

async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    """
    Get current user from token
    """
    # For development, bypass authentication and return a mock user
    if settings.DEBUG:
        # Create a mock user repository
        user_repo = UserRepository(db)
        
        # Check if dev user exists, create if not
        dev_user = user_repo.get_by_email("dev@example.com")
        if not dev_user:
            dev_user = user_repo.create({
                "id": "dev-user-id",
                "email": "dev@example.com",
                "name": "Development User",
                "meta_data": {
                    "picture": "",
                    "locale": "en"
                }
            })
        return dev_user
    
    # Normal authentication flow for production
    try:
        payload = await verify_token(token)
        user_id = payload.get("sub")
        
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        user_repo = UserRepository(db)
        user = user_repo.get(user_id)
        
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        return user
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

# Create a dummy user function that doesn't require authentication
async def get_dummy_user(db: Session = Depends(get_db)):
    """
    Get a dummy user for development
    """
    # Create a mock user repository
    user_repo = UserRepository(db)
    
    # Check if dev user exists, create if not
    dev_user = user_repo.get_by_email("dev@example.com")
    if not dev_user:
        dev_user = user_repo.create({
            "id": "dev-user-id",
            "email": "dev@example.com",
            "name": "Development User",
            "meta_data": {
                "picture": "https://via.placeholder.com/150",
                "locale": "en",
                "settings": {
                    "theme": "dark",
                    "notifications": True,
                    "language": "en"
                }
            }
        })
    return dev_user

# This function will be used in API endpoints
def get_current_user_dependency():
    """
    Returns the appropriate dependency based on DEBUG mode
    """
    if settings.DEBUG:
        return get_dummy_user
    else:
        return get_current_user 

def setup_auth(app):
    """
    Set up authentication for the FastAPI app
    """
    # In debug mode, no additional setup is needed since we use get_dummy_user
    if settings.DEBUG:
        return
    
    # For production, we could add additional auth middleware or configuration here
    # This function is a placeholder for future authentication setup
    return 