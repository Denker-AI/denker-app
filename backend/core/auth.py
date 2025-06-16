import jwt
from jwt import PyJWK
import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
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
            jwks_response = await client.get(jwks_url)
            jwks_response.raise_for_status()
            jwks = jwks_response.json()
        
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
                break
        
        if not rsa_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Unable to find appropriate key for token verification",
                headers={"WWW-Authenticate": "Bearer"},
            )
            
        payload = jwt.decode(
            token,
            jwt.PyJWK.from_dict(rsa_key).key,
            algorithms=settings.AUTH0_ALGORITHMS,
            audience=settings.AUTH0_API_AUDIENCE,
            issuer=f"https://{settings.AUTH0_DOMAIN}/"
        )
        return payload
    
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.PyJWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token or claims: {e}",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except httpx.HTTPStatusError as http_err:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to fetch JWKS: {http_err}",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        print(f"Error during token verification: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Unable to parse or verify authentication token: {type(e).__name__}",
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
            response.raise_for_status()
            return response.json()
    
    except httpx.HTTPStatusError as http_err:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Unable to get user info from Auth0: {http_err}",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        print(f"Error fetching user info: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Unable to get user info: {type(e).__name__}",
            headers={"WWW-Authenticate": "Bearer"},
        )

async def get_current_user(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)):
    """
    Get current user from token
    """
    user_repo = UserRepository(db)

    try:
        # If no token is provided by FastAPI (e.g. an optional token on an unprotected route, 
        # or if oauth2_scheme itself is optional), then 'token' might be None.
        # In a typical protected route, FastAPI & Depends(oauth2_scheme) would raise an error 
        # before this function is even called if the token is missing/malformed.
        if token is None:
            # This case should ideally be handled by FastAPI's dependency injection for oauth2_scheme
            # on protected routes. If a route is optionally authenticated, this check might be relevant.
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated (no token provided)",
                headers={"WWW-Authenticate": "Bearer"},
            )
            
        payload = await verify_token(token)
        user_id = payload.get("sub")
        
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials (no sub)",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Directly await async repository method
        user = await user_repo.get(user_id)
        
        if user is None:
            # Create user if it's their first login and token is valid
            # Attempt to get more user info from the token or /userinfo endpoint if needed
            user_email = payload.get("email") 
            if not user_email:
                # Fallback: if email is not in the validated token, try /userinfo
                # This requires the original token, not just the payload
                try:
                    user_info_data = await get_token_data(token) # Assumes get_token_data uses the raw token
                    user_email = user_info_data.get("email")
                except HTTPException:
                    # If /userinfo fails or doesn't provide email, create user without it or handle error
                    pass # Or raise an error if email is strictly required
            
            user_name = payload.get("name") or payload.get("nickname") or user_email or user_id
            picture = payload.get("picture")

            new_user_payload = {
                "id": user_id, # This is the 'sub' from the token
                "email": user_email or f"{user_id}@placeholder.auth0", # Ensure email has a value
                "name": user_name,
                "meta_data": {"auth0_payload": payload, "picture": picture}
            }
            user = await user_repo.create(new_user_payload) # Create the user
            # Log user creation for auditing if necessary
            print(f"New user created in DB: {user_id} - {user_email}")
        
        return user
    except HTTPException as e: # Re-raise HTTPExceptions from verify_token or this function
        raise e
    except jwt.PyJWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token (PyJWTError): {e}",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        print(f"Unexpected error in get_current_user: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server error during authentication",
            headers={"WWW-Authenticate": "Bearer"}
        )

# Create a dummy user function that doesn't require authentication
async def get_dummy_user(db: AsyncSession = Depends(get_db)):
    """
    Get a dummy user for development
    """
    user_repo = UserRepository(db)
    
    # Directly await async repository methods
    dev_user = await user_repo.get_by_email("dev@example.com")
    if not dev_user:
        dev_user_payload = {
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
        }
        dev_user = await user_repo.create(dev_user_payload)
    return dev_user

# This function will be used in API endpoints
def get_current_user_dependency():
    """
    Returns the appropriate dependency based on DEBUG mode
    """
    # Always return get_current_user to enable real authentication even in DEBUG mode.
    # The settings.DEBUG flag can be used for other purposes like verbose logging,
    # but authentication should consistently use real tokens if provided.
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