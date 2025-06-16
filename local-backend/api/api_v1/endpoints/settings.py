import os
import logging
from fastapi import APIRouter, Depends, HTTPException

# Assuming fetch_and_save_remote_settings is in agents.py and handles coordinator restart
# This creates a direct import dependency, consider refactoring to a service/util if this grows.
from .agents import fetch_and_save_remote_settings, LocalLoginRequest # LocalLoginRequest might not be needed here, but user_id/token/remote_api_url are
from core.user_store import LocalUserStore
# initialize_coordinator and cleanup_coordinator are called by fetch_and_save_remote_settings

logger = logging.getLogger(__name__)
router = APIRouter()

# Helper to get current user from LocalUserStore, similar to agents.py
def get_current_user_local_settings():
    user = LocalUserStore.get_user()
    return user # Endpoint will handle if None

current_user_dependency_settings = get_current_user_local_settings

@router.post("/refresh-cache", name="Refresh Local Settings Cache from Remote")
async def refresh_local_settings_cache_endpoint(current_user: dict = Depends(current_user_dependency_settings)):
    raw_user_from_store = LocalUserStore.get_user()
    logger.info(f"[SETTINGS_REFRESH_ENDPOINT] LocalUserStore.get_user() returned: {raw_user_from_store}")
    logger.info(f"[SETTINGS_REFRESH_ENDPOINT] current_user (from Depends) is: {current_user}")

    if not current_user:
        raise HTTPException(status_code=401, detail="User not authenticated locally for settings refresh (current_user is None).")

    user_id = current_user.get("user_id")
    token = current_user.get("token")

    if not user_id or not token:
        logger.warning(f"[SETTINGS_REFRESH_ENDPOINT] User ID or token missing. UserID: {user_id}, Token Present: {bool(token)}")
        raise HTTPException(status_code=401, detail="User ID or token missing in local session for settings refresh.")
    
    # remote_api_url is no longer taken from current_user here or passed to the helper.
    # fetch_and_save_remote_settings will get it from os.environ.get("VITE_API_URL")
    logger.info(f"Endpoint /refresh-cache called for user {user_id}. fetch_and_save_remote_settings will use VITE_API_URL env var.")
    
    try:
        # Call fetch_and_save_remote_settings with restart_coordinator=False
        settings_result = await fetch_and_save_remote_settings(
            user_id=user_id, 
            token=token,
            restart_coordinator=False 
        )

        if settings_result.get("success"):
            logger.info(f"Settings refreshed for user {user_id} via /refresh-cache. Coordinator restart was skipped by request.")
            return {"status": "success", "message": "Settings refreshed. Coordinator restart deferred to app restart."}
        else:
            logger.error(f"Failed to refresh settings for user {user_id} via /refresh-cache: {settings_result.get('error')}")
            raise HTTPException(status_code=500, detail=f"Failed to refresh settings: {settings_result.get('error')}")

    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error in /refresh-cache endpoint for user {user_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred while refreshing settings: {str(e)}") 