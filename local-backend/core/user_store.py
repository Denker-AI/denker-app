# local-backend/core/user_store.py

import logging

logger = logging.getLogger(__name__)

class LocalUserStore:
    """
    In-memory singleton to store the current user's information for the local backend.
    This typically includes user_id (Auth0 sub) and the Auth0 access token.
    """
    _current_user = None # Class variable to store user_id and token

    @staticmethod
    def set_user(user_data: dict):
        """Store the current user's ID and token."""
        if user_data and 'user_id' in user_data and 'token' in user_data:
            LocalUserStore._current_user = {
                "user_id": user_data["user_id"],
                "token": user_data["token"],
            }
            logger.info(f"[LocalUserStore] User set: ID {LocalUserStore._current_user['user_id']}, Token {'PRESENT' if LocalUserStore._current_user['token'] else 'MISSING'}")
        else:
            logger.warning(f"[LocalUserStore] Attempted to set user with invalid data: {user_data}")
            LocalUserStore._current_user = None

    @staticmethod
    def get_user():
        """Retrieve the current user's ID and token."""
        return LocalUserStore._current_user

    @staticmethod
    def clear_user():
        """Clear the stored user information."""
        logger.info("[LocalUserStore] User cleared.")
        LocalUserStore._current_user = None 