"""
Qdrant User Filter Patch

This module provides a monkey patch for the MCP Qdrant server to add user filtering
to search operations, preventing users from seeing documents from other users.

SECURITY FIX: Addresses vulnerability where qdrant-find returns all documents
regardless of user ownership.
"""

import logging
import functools
from typing import Any, Dict, Optional, List
from qdrant_client import models

logger = logging.getLogger(__name__)

# Flag to ensure patch is only applied once
_patch_applied = False

def get_current_user_id() -> Optional[str]:
    """
    Extract the current user ID from the MCP agent context.
    
    Returns:
        str: The current user ID if available, None otherwise
    """
    try:
        # Try to get user context from the local user store
        from core.user_store import LocalUserStore
        
        stored_user_info = LocalUserStore.get_user()
        if stored_user_info and stored_user_info.get("user_id"):
            return stored_user_info.get("user_id")
            
    except ImportError:
        logger.warning("LocalUserStore not available for user context")
    except Exception as e:
        logger.warning(f"Error getting user context from LocalUserStore: {e}")
    
    try:
        # Fallback: Try to get from MCP agent context
        from mcp_agent.context import get_current_context
        
        context = get_current_context()
        # Look for user_id in various possible locations in context
        if hasattr(context, 'user_id'):
            return context.user_id
        if hasattr(context, 'session_data') and isinstance(context.session_data, dict):
            return context.session_data.get('user_id')
            
    except Exception as e:
        logger.warning(f"Error getting user context from MCP agent: {e}")
    
    # If we can't determine the user, we should fail securely
    logger.warning("Could not determine current user ID for Qdrant filtering - this is a security issue!")
    return None

def create_user_filter(user_id: str) -> models.Filter:
    """
    Create a Qdrant filter to only return documents for the specified user.
    
    Args:
        user_id: The user ID to filter by
        
    Returns:
        models.Filter: A Qdrant filter that restricts results to the user's documents
    """
    return models.Filter(
        must=[
            models.FieldCondition(
                key="metadata.user_id",
                match=models.MatchValue(value=user_id)
            )
        ]
    )

def patch_qdrant_search_with_user_filter():
    """
    Monkey patch the QdrantConnector.search method to add user filtering.
    
    This ensures that search operations only return documents belonging to the current user,
    preventing unauthorized access to other users' documents.
    """
    global _patch_applied
    
    if _patch_applied:
        logger.debug("Qdrant user filter patch already applied")
        return
    
    try:
        # Import the classes we need to patch
        from mcp_server_qdrant.qdrant import QdrantConnector
        from mcp_server_qdrant.qdrant import Entry
        
        # Store the original search method
        original_search = QdrantConnector.search
        
        @functools.wraps(original_search)
        async def search_with_user_filter(
            self, 
            query: str, 
            *, 
            collection_name: Optional[str] = None, 
            limit: int = 10
        ) -> List[Entry]:
            """
            Enhanced search method that filters results by user_id.
            
            This is a security-critical modification that ensures users can only
            access their own documents.
            """
            # Get the current user ID
            current_user_id = get_current_user_id()
            
            if not current_user_id:
                logger.error("Security: Cannot perform Qdrant search without user context - blocking request")
                # Return empty list instead of all documents for security
                return []
            
            logger.debug(f"Performing Qdrant search for user: {current_user_id}")
            
            collection_name = collection_name or self._default_collection_name
            collection_exists = await self._client.collection_exists(collection_name)
            if not collection_exists:
                return []

            # Embed the query (same as original)
            query_vector = await self._embedding_provider.embed_query(query)
            vector_name = self._embedding_provider.get_vector_name()

            # Create user filter
            user_filter = create_user_filter(current_user_id)

            # Search in Qdrant WITH USER FILTERING
            search_results = await self._client.query_points(
                collection_name=collection_name,
                query=query_vector,
                using=vector_name,
                limit=limit,
                filter=user_filter  # THIS IS THE CRITICAL SECURITY FIX
            )

            logger.debug(f"Qdrant search returned {len(search_results.points)} results for user {current_user_id}")

            return [
                Entry(
                    content=result.payload["document"],
                    metadata=result.payload.get("metadata"),
                )
                for result in search_results.points
            ]
        
        # Apply the monkey patch
        QdrantConnector.search = search_with_user_filter
        _patch_applied = True
        
        logger.info("Successfully applied Qdrant user filter patch - search operations are now secure")
        
    except ImportError as e:
        logger.warning(f"Could not import Qdrant classes for patching: {e}")
    except Exception as e:
        logger.error(f"Error applying Qdrant user filter patch: {e}")

def verify_patch_applied() -> bool:
    """
    Verify that the user filter patch has been successfully applied.
    
    Returns:
        bool: True if patch is applied, False otherwise
    """
    return _patch_applied

def apply_qdrant_security_patches():
    """
    Apply all Qdrant security patches.
    
    This is the main entry point that should be called during application startup
    to ensure Qdrant operations are secure.
    """
    logger.info("Applying Qdrant security patches...")
    patch_qdrant_search_with_user_filter()
    
    if verify_patch_applied():
        logger.info("✅ Qdrant security patches applied successfully")
    else:
        logger.error("❌ Failed to apply Qdrant security patches - THIS IS A SECURITY RISK!") 