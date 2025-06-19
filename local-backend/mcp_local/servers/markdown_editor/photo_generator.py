"""
Photo Generator for Markdown Editor

Provides photo search and download capabilities using Unsplash API
with proper shared workspace integration.
"""

import os
import json
import base64
import logging
import asyncio
import aiohttp
from typing import Dict, Any, Optional, List, Union
from datetime import datetime
from pathlib import Path
from PIL import Image
import io

logger = logging.getLogger("markdown-editor")

# Try to import shared workspace for multi-agent coordination
try:
    from core.shared_workspace import get_shared_workspace
    SHARED_WORKSPACE_AVAILABLE = True
except ImportError:
    SHARED_WORKSPACE_AVAILABLE = False

# Photo categories and search suggestions
PHOTO_CATEGORIES = {
    'nature': [
        'landscape', 'mountains', 'forest', 'ocean', 'sunset', 'sunrise', 'trees', 'flowers',
        'garden', 'beach', 'lake', 'river', 'sky', 'clouds', 'wildlife', 'animals'
    ],
    'business': [
        'office', 'meeting', 'laptop', 'workspace', 'teamwork', 'conference', 'presentation',
        'handshake', 'corporate', 'finance', 'charts', 'documents', 'planning', 'strategy'
    ],
    'technology': [
        'computer', 'coding', 'programming', 'data', 'AI', 'robot', 'innovation', 'digital',
        'software', 'hardware', 'network', 'server', 'smartphone', 'tablet', 'apps'
    ],
    'lifestyle': [
        'people', 'family', 'friends', 'travel', 'food', 'coffee', 'home', 'fitness',
        'health', 'education', 'learning', 'reading', 'music', 'art', 'creative'
    ],
    'architecture': [
        'building', 'city', 'urban', 'modern', 'interior', 'design', 'construction',
        'bridge', 'skyline', 'house', 'apartment', 'museum', 'church', 'historic'
    ],
    'abstract': [
        'pattern', 'texture', 'geometric', 'minimal', 'color', 'gradient', 'background',
        'artistic', 'creative', 'modern', 'contemporary', 'design', 'wallpaper'
    ]
}

# Photo sizes and orientations
PHOTO_SIZES = {
    'thumbnail': {'width': 200, 'height': 150},
    'small': {'width': 400, 'height': 300},
    'regular': {'width': 1080, 'height': 720},
    'large': {'width': 1920, 'height': 1280},
    'full': {'width': None, 'height': None}  # Original size
}

ORIENTATIONS = ['landscape', 'portrait', 'squarish']

def validate_image_file(file_path: str, min_size_bytes: int = 10000) -> Dict[str, Any]:
    """
    Validate that an image file is properly downloaded and not corrupted.
    
    Args:
        file_path: Path to the image file
        min_size_bytes: Minimum expected file size in bytes
        
    Returns:
        Dict with validation results
    """
    try:
        if not os.path.exists(file_path):
            return {
                'valid': False,
                'error': f'Image file does not exist: {file_path}'
            }
        
        # Check file size
        file_size = os.path.getsize(file_path)
        if file_size < min_size_bytes:
            return {
                'valid': False,
                'error': f'Image file too small ({file_size} bytes, expected at least {min_size_bytes})',
                'file_size': file_size
            }
        
        # Try to open and validate the image using PIL
        try:
            with Image.open(file_path) as img:
                # Check if image has reasonable dimensions
                width, height = img.size
                if width < 100 or height < 100:
                    return {
                        'valid': False,
                        'error': f'Image dimensions too small: {width}x{height}',
                        'file_size': file_size,
                        'dimensions': (width, height)
                    }
                
                return {
                    'valid': True,
                    'file_size': file_size,
                    'dimensions': (width, height),
                    'format': img.format
                }
        except Exception as e:
            return {
                'valid': False,
                'error': f'Cannot open image file: {str(e)}',
                'file_size': file_size
            }
            
    except Exception as e:
        return {
            'valid': False,
            'error': f'Error validating image: {str(e)}'
        }

class PhotoGenerator:
    """
    Photo generator for fetching beautiful images from Unsplash API.
    
    Provides search, download, and management capabilities for high-quality photos
    that can be embedded in markdown documents.
    """
    
    def __init__(self):
        self.api_key = None
        self.base_url = "https://api.unsplash.com"
        self._load_api_key()
    
    def _load_api_key(self):
        """Load API key from environment or .env file."""
        import os
        
        # Hardcoded API key to bypass environment variable issues
        self.api_key = "Rsz5zQR6q4ogic0dVVAgBlS32xzTYJP-O5Tdb4n_RJA"
        
        if self.api_key:
            logger.info("Unsplash API key loaded successfully (hardcoded)")
        else:
            logger.warning("No Unsplash API key found. Photo search/download will fail.")
        
    def _get_workspace_path(self, filename: str) -> str:
        """Get the proper shared workspace path for a photo file."""
        logger.info(f"[PhotoGenerator._get_workspace_path] Requested filename: {filename}")
        
        if SHARED_WORKSPACE_AVAILABLE:
            try:
                workspace = get_shared_workspace()
                # Use only filename - no subdirectories allowed
                filename_only = Path(filename).name
                file_path = workspace.workspace_root / filename_only
                
                logger.info(f"[PhotoGenerator._get_workspace_path] Using shared workspace: {file_path}")
                return str(file_path)
            except Exception as e:
                logger.warning(f"Could not use shared workspace for photo: {e}")
        
        # FIXED: Always use unified temp workspace as fallback
        try:
            from mcp_local.core.shared_workspace import SharedWorkspaceManager
            fallback_path = SharedWorkspaceManager._get_unified_workspace_path("default")
            logger.info(f"[PhotoGenerator._get_workspace_path] Using unified temp workspace: {fallback_path}")
            
            # Ensure directory exists
            fallback_path.mkdir(parents=True, exist_ok=True)
            
            # Strip any path components for security
            safe_filename = Path(filename).name
            final_path = str(fallback_path / safe_filename)
            logger.info(f"[PhotoGenerator._get_workspace_path] Final path: {final_path}")
            return final_path
        except Exception as e:
            logger.warning(f"Could not get unified workspace path: {e}")
            fallback_dir = '/tmp/denker_workspace/default'
            logger.info(f"[PhotoGenerator._get_workspace_path] Fallback to unified temp workspace: {fallback_dir}")
            
            # Ensure directory exists
            os.makedirs(fallback_dir, exist_ok=True)
            
            # Strip any path components for security
            safe_filename = Path(filename).name
            final_path = os.path.join(fallback_dir, safe_filename)
            logger.info(f"[PhotoGenerator._get_workspace_path] Final path: {final_path}")
            return final_path
    
    def _register_photo_file(self, file_path: str, photo_metadata: Dict[str, Any]) -> Optional[str]:
        """
        Register a photo file with the shared workspace for multi-agent coordination.
        
        Args:
            file_path: Path to the saved photo file
            photo_metadata: Metadata about the photo (from Unsplash API)
            
        Returns:
            File ID if registered successfully, None otherwise
        """
        if SHARED_WORKSPACE_AVAILABLE:
            try:
                workspace = get_shared_workspace()
                if workspace:
                    file_id = workspace.register_file(
                        file_path=file_path,
                        file_type="image",
                        metadata={
                            "source": "unsplash",
                            "photo_id": photo_metadata.get("id"),
                            "description": photo_metadata.get("description") or photo_metadata.get("alt_description"),
                            "photographer": photo_metadata.get("user", {}).get("name"),
                            "photographer_url": photo_metadata.get("user", {}).get("links", {}).get("html"),
                            "unsplash_url": photo_metadata.get("links", {}).get("html"),
                            "created_at": datetime.now().isoformat(),
                            "dimensions": {
                                "width": photo_metadata.get("width"),
                                "height": photo_metadata.get("height")
                            }
                        }
                    )
                    logger.info(f"Registered photo file {file_path} with workspace ID: {file_id}")
                    return file_id
            except Exception as e:
                logger.warning(f"Could not register photo with workspace: {e}")
        return None
    
    async def search_photos(self,
                          query: str,
                          page: int = 1,
                          per_page: int = 10,
                          orientation: Optional[str] = None,
                          category: Optional[str] = None,
                          color: Optional[str] = None,
                          order_by: str = "relevant") -> Dict[str, Any]:
        """
        Search for photos on Unsplash based on query and filters.
        
        Args:
            query: Search terms
            page: Page number (1-based)
            per_page: Number of results per page (max 30)
            orientation: Photo orientation ('landscape', 'portrait', 'squarish')
            category: Photo category for enhanced search
            color: Color filter ('black_and_white', 'black', 'white', 'yellow', etc.)
            order_by: Sort order ('relevant' or 'latest')
            
        Returns:
            Search results with photo metadata
        """
        try:
            if not self.api_key:
                return {
                    "success": False,
                    "error": "Unsplash API key not configured. Please set UNSPLASH_ACCESS_KEY environment variable."
                }
            
            # Enhance query with category suggestions if category is provided
            enhanced_query = query
            if category and category in PHOTO_CATEGORIES:
                category_terms = PHOTO_CATEGORIES[category]
                # Add relevant category terms to the query
                enhanced_query = f"{query} {' '.join(category_terms[:3])}"
            
            # Build API request URL
            url = f"{self.base_url}/search/photos"
            params = {
                'query': enhanced_query,
                'page': page,
                'per_page': min(per_page, 30),  # Unsplash API limit
                'order_by': order_by
            }
            
            if orientation in ORIENTATIONS:
                params['orientation'] = orientation
            if color:
                params['color'] = color
            
            headers = {
                'Authorization': f'Client-ID {self.api_key}',
                'Accept': 'application/json'
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        # Process results to include helpful metadata
                        processed_results = []
                        for photo in data.get('results', []):
                            processed_photo = {
                                'id': photo.get('id'),
                                'description': photo.get('description') or photo.get('alt_description'),
                                'photographer': photo.get('user', {}).get('name'),
                                'photographer_url': photo.get('user', {}).get('links', {}).get('html'),
                                'unsplash_url': photo.get('links', {}).get('html'),
                                'download_url': photo.get('links', {}).get('download_location'),
                                'urls': photo.get('urls', {}),
                                'width': photo.get('width'),
                                'height': photo.get('height'),
                                'likes': photo.get('likes', 0),
                                'created_at': photo.get('created_at')
                            }
                            processed_results.append(processed_photo)
                        
                        return {
                            "success": True,
                            "total": data.get('total', 0),
                            "total_pages": data.get('total_pages', 0),
                            "results": processed_results,
                            "query": query,
                            "enhanced_query": enhanced_query,
                            "page": page,
                            "per_page": per_page
                        }
                    else:
                        error_data = await response.text()
                        return {
                            "success": False,
                            "error": f"Unsplash API error {response.status}: {error_data}"
                        }
                        
        except Exception as e:
            logger.error(f"Error searching photos: {str(e)}")
            return {
                "success": False,
                "error": f"Search failed: {str(e)}"
            }
    
    async def download_photo(self,
                           photo_id: str,
                           size: str = "regular",
                           filename: Optional[str] = None,
                           custom_width: Optional[int] = None,
                           custom_height: Optional[int] = None) -> Dict[str, Any]:
        """
        Download a photo from Unsplash and save it locally.
        
        Args:
            photo_id: Unsplash photo ID
            size: Photo size ('thumbnail', 'small', 'regular', 'large', 'full')
            filename: Custom filename (will generate if not provided)
            custom_width: Custom width for resizing
            custom_height: Custom height for resizing
            
        Returns:
            Download result with file path and metadata
        """
        try:
            if not self.api_key:
                return {
                    "success": False,
                    "error": "Unsplash API key not configured"
                }
            
            # First, get photo metadata
            headers = {
                'Authorization': f'Client-ID {self.api_key}',
                'Accept': 'application/json'
            }
            
            async with aiohttp.ClientSession() as session:
                # Get photo details
                photo_url = f"{self.base_url}/photos/{photo_id}"
                async with session.get(photo_url, headers=headers) as response:
                    if response.status != 200:
                        error_data = await response.text()
                        return {
                            "success": False,
                            "error": f"Failed to get photo details: {error_data}"
                        }
                    
                    photo_data = await response.json()
                
                # Determine download URL
                urls = photo_data.get('urls', {})
                
                if custom_width or custom_height:
                    # Use raw URL with custom parameters
                    download_url = urls.get('raw', '')
                    if custom_width:
                        download_url += f"&w={custom_width}"
                    if custom_height:
                        download_url += f"&h={custom_height}"
                elif size in urls:
                    download_url = urls[size]
                else:
                    download_url = urls.get('regular', urls.get('full', ''))
                
                if not download_url:
                    return {
                        "success": False,
                        "error": "No download URL available for this photo"
                    }
                
                # Generate filename if not provided
                if not filename:
                    photographer = photo_data.get('user', {}).get('username', 'unknown')
                    description = photo_data.get('description') or photo_data.get('alt_description') or 'photo'
                    # Clean description for filename
                    clean_desc = ''.join(c for c in description[:30] if c.isalnum() or c in (' ', '-', '_')).strip()
                    clean_desc = clean_desc.replace(' ', '_').lower()
                    filename = f"{photo_id}_{photographer}_{clean_desc}.jpg"
                
                # Ensure filename has proper extension
                if not filename.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')):
                    filename += '.jpg'
                
                # Get full file path
                file_path = self._get_workspace_path(filename)
                
                # Download the image
                async with session.get(download_url) as img_response:
                    if img_response.status == 200:
                        image_data = await img_response.read()
                        
                        # Save the image
                        with open(file_path, 'wb') as f:
                            f.write(image_data)
                        
                        # Validate the downloaded image
                        validation = validate_image_file(file_path)
                        if not validation['valid']:
                            # Clean up invalid file
                            try:
                                os.remove(file_path)
                            except:
                                pass
                            return {
                                "success": False,
                                "error": f"Downloaded image is invalid: {validation['error']}"
                            }
                        
                        # Register with workspace if available
                        file_id = self._register_photo_file(file_path, photo_data)
                        
                        # Track download with Unsplash (required by API terms)
                        download_track_url = photo_data.get('links', {}).get('download_location')
                        if download_track_url:
                            try:
                                async with session.get(download_track_url, headers=headers) as track_response:
                                    pass  # Just need to make the request
                            except:
                                pass  # Non-critical if tracking fails
                        
                        result = {
                            "success": True,
                            "file_path": os.path.basename(file_path),  # Return relative path (filename only)
                            "filename": os.path.basename(file_path),
                            "file_size": validation['file_size'],
                            "dimensions": validation['dimensions'],
                            "format": validation.get('format'),
                            "photo_metadata": {
                                "id": photo_data.get('id'),
                                "description": photo_data.get('description') or photo_data.get('alt_description'),
                                "photographer": photo_data.get('user', {}).get('name'),
                                "photographer_url": photo_data.get('user', {}).get('links', {}).get('html'),
                                "unsplash_url": photo_data.get('links', {}).get('html'),
                                "likes": photo_data.get('likes', 0),
                                "created_at": photo_data.get('created_at')
                            }
                        }
                        
                        if file_id:
                            result["workspace_file_id"] = file_id
                        
                        logger.info(f"Successfully downloaded photo {photo_id} to {file_path}")
                        return result
                    else:
                        error_data = await img_response.text()
                        return {
                            "success": False,
                            "error": f"Failed to download image: HTTP {img_response.status} - {error_data}"
                        }
                        
        except Exception as e:
            logger.error(f"Error downloading photo {photo_id}: {str(e)}")
            return {
                "success": False,
                "error": f"Download failed: {str(e)}"
            }
    
    async def get_random_photo(self,
                             query: Optional[str] = None,
                             category: Optional[str] = None,
                             orientation: Optional[str] = None,
                             size: str = "regular",
                             filename: Optional[str] = None) -> Dict[str, Any]:
        """
        Get and download a random photo from Unsplash.
        
        Args:
            query: Optional search query to filter random selection
            category: Photo category for enhanced search
            orientation: Photo orientation filter
            size: Download size
            filename: Custom filename
            
        Returns:
            Download result with file path and metadata
        """
        try:
            if not self.api_key:
                return {
                    "success": False,
                    "error": "Unsplash API key not configured"
                }
            
            # Build random photo URL
            url = f"{self.base_url}/photos/random"
            params = {}
            
            if query:
                enhanced_query = query
                if category and category in PHOTO_CATEGORIES:
                    category_terms = PHOTO_CATEGORIES[category]
                    enhanced_query = f"{query} {' '.join(category_terms[:2])}"
                params['query'] = enhanced_query
            
            if orientation in ORIENTATIONS:
                params['orientation'] = orientation
            
            headers = {
                'Authorization': f'Client-ID {self.api_key}',
                'Accept': 'application/json'
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, headers=headers) as response:
                    if response.status == 200:
                        photo_data = await response.json()
                        
                        # Download the random photo
                        return await self.download_photo(
                            photo_id=photo_data['id'],
                            size=size,
                            filename=filename
                        )
                    else:
                        error_data = await response.text()
                        return {
                            "success": False,
                            "error": f"Failed to get random photo: {error_data}"
                        }
                        
        except Exception as e:
            logger.error(f"Error getting random photo: {str(e)}")
            return {
                "success": False,
                "error": f"Random photo failed: {str(e)}"
            }
    
    def set_api_key(self, api_key: str):
        """Set the Unsplash API key."""
        self.api_key = api_key
    
    def get_categories(self) -> Dict[str, List[str]]:
        """Get available photo categories and their search terms."""
        return PHOTO_CATEGORIES.copy()
    
    def get_photo_sizes(self) -> Dict[str, Dict[str, Any]]:
        """Get available photo sizes."""
        return PHOTO_SIZES.copy()
    
    def get_orientations(self) -> List[str]:
        """Get available photo orientations."""
        return ORIENTATIONS.copy()

# Tool functions for MCP integration

async def search_photos_tool(query: str,
                           page: int = 1,
                           per_page: int = 10,
                           orientation: Optional[str] = None,
                           category: Optional[str] = None,
                           color: Optional[str] = None,
                           order_by: str = "relevant",
                           api_key: Optional[str] = None) -> Dict[str, Any]:
    """
    Search for photos on Unsplash.
    
    Args:
        query: Search terms for photos
        page: Page number (default: 1)
        per_page: Results per page (max 30, default: 10)
        orientation: Photo orientation ('landscape', 'portrait', 'squarish')
        category: Photo category to enhance search ('nature', 'business', 'technology', 'lifestyle', 'architecture', 'abstract')
        color: Color filter ('black_and_white', 'black', 'white', 'yellow', 'orange', 'red', 'purple', 'magenta', 'green', 'teal', 'blue')
        order_by: Sort order ('relevant' or 'latest', default: 'relevant')
        api_key: Unsplash API key (uses environment variable if not provided)
        
    Returns:
        Search results with photo metadata
    """
    generator = PhotoGenerator()
    
    # Override API key if provided, or use hardcoded fallback
    if api_key:
        generator.set_api_key(api_key)
    elif not generator.api_key:
        generator.set_api_key("Rsz5zQR6q4ogic0dVVAgBlS32xzTYJP-O5Tdb4n_RJA")
    
    return await generator.search_photos(
        query=query,
        page=page,
        per_page=per_page,
        orientation=orientation,
        category=category,
        color=color,
        order_by=order_by
    )

async def download_photo_tool(photo_id: str,
                            size: str = "regular",
                            filename: Optional[str] = None,
                            custom_width: Optional[int] = None,
                            custom_height: Optional[int] = None,
                            api_key: Optional[str] = None) -> Dict[str, Any]:
    """
    Download a photo from Unsplash by ID.
    
    Args:
        photo_id: Unsplash photo ID
        size: Photo size ('thumbnail', 'small', 'regular', 'large', 'full')
        filename: Custom filename (auto-generated if not provided)
        custom_width: Custom width for resizing
        custom_height: Custom height for resizing
        api_key: Unsplash API key (uses environment variable if not provided)
        
    Returns:
        Download result with file path and metadata
    """
    generator = PhotoGenerator()
    
    # Override API key if provided, or use hardcoded fallback
    if api_key:
        generator.set_api_key(api_key)
    elif not generator.api_key:
        generator.set_api_key("Rsz5zQR6q4ogic0dVVAgBlS32xzTYJP-O5Tdb4n_RJA")
    
    return await generator.download_photo(
        photo_id=photo_id,
        size=size,
        filename=filename,
        custom_width=custom_width,
        custom_height=custom_height
    )

async def get_random_photo_tool(query: Optional[str] = None,
                              category: Optional[str] = None,
                              orientation: Optional[str] = None,
                              size: str = "regular",
                              filename: Optional[str] = None,
                              api_key: Optional[str] = None) -> Dict[str, Any]:
    """
    Get and download a random photo from Unsplash.
    
    Args:
        query: Optional search query to filter random selection
        category: Photo category ('nature', 'business', 'technology', 'lifestyle', 'architecture', 'abstract')
        orientation: Photo orientation ('landscape', 'portrait', 'squarish')
        size: Photo size ('thumbnail', 'small', 'regular', 'large', 'full')
        filename: Custom filename (auto-generated if not provided)
        api_key: Unsplash API key (uses environment variable if not provided)
        
    Returns:
        Download result with file path and metadata
    """
    generator = PhotoGenerator()
    
    # Override API key if provided, or use hardcoded fallback
    if api_key:
        generator.set_api_key(api_key)
    elif not generator.api_key:
        generator.set_api_key("Rsz5zQR6q4ogic0dVVAgBlS32xzTYJP-O5Tdb4n_RJA")
    
    return await generator.get_random_photo(
        query=query,
        category=category,
        orientation=orientation,
        size=size,
        filename=filename
    )

async def get_photo_categories_tool() -> Dict[str, Any]:
    """
    Get available photo categories and their associated search terms.
    
    Returns:
        Dictionary of categories and their search terms
    """
    generator = PhotoGenerator()
    return {
        "success": True,
        "categories": generator.get_categories(),
        "orientations": generator.get_orientations(),
        "sizes": generator.get_photo_sizes()
    }

async def search_and_download_photo_tool(query: str,
                                      size: str = "regular",
                                      orientation: Optional[str] = None,
                                      category: Optional[str] = None,
                                      filename: Optional[str] = None,
                                      api_key: Optional[str] = None) -> Dict[str, Any]:
    """
    Search for a photo and download it in one step (like chart generation workflow).
    This is the preferred tool for agents to get images for documents.
    
    Args:
        query: Search query for the photo
        size: Photo size ('thumbnail', 'small', 'regular', 'large', 'full')
        orientation: Photo orientation filter ('landscape', 'portrait', 'squarish')
        category: Photo category for enhanced search
        filename: Custom filename (will generate if not provided)
        api_key: Optional API key (uses default if not provided)
        
    Returns:
        Download result with file path and metadata, similar to chart generator
    """
    generator = PhotoGenerator()
    # Use provided API key or hardcoded fallback
    if api_key:
        generator.set_api_key(api_key)
    elif not generator.api_key:
        generator.set_api_key("Rsz5zQR6q4ogic0dVVAgBlS32xzTYJP-O5Tdb4n_RJA")
    
    try:
        # First search for photos
        search_result = await generator.search_photos(
            query=query,
            page=1,
            per_page=1,  # Only need the best match
            orientation=orientation,
            category=category
        )
        
        if not search_result.get("success") or not search_result.get("results"):
            return {
                "success": False,
                "error": f"No photos found for query: '{query}'"
            }
        
        # Get the first (best) photo
        photo = search_result["results"][0]
        photo_id = photo["id"]
        
        # Generate filename if not provided (similar to chart generator)
        if not filename:
            # Create a descriptive filename from query and photo info
            photographer = photo.get("photographer", "unknown")
            clean_query = ''.join(c for c in query[:20] if c.isalnum() or c in (' ', '-', '_')).strip()
            clean_query = clean_query.replace(' ', '_').lower()
            filename = f"{clean_query}_{photographer}_{photo_id}.jpg"
        
        # Download the photo
        download_result = await generator.download_photo(
            photo_id=photo_id,
            size=size,
            filename=filename
        )
        
        if download_result.get("success"):
            # Return result in chart generator style (filename only for consistency)
            result = {
                "success": True,
                "photo_path": download_result["filename"],  # Return relative path (filename only) like chart generator
                "filename": download_result["filename"],
                "size_bytes": download_result["file_size"],
                "dimensions": download_result["dimensions"],
                "format": download_result.get("format", "jpg"),
                "query_used": query,
                "photo_metadata": download_result["photo_metadata"]
            }
            
            if download_result.get("workspace_file_id"):
                result["file_id"] = download_result["workspace_file_id"]
            
            logger.info(f"Successfully searched and downloaded photo for query '{query}': {download_result['filename']}")
            return result
        else:
            return download_result
            
    except Exception as e:
        logger.error(f"Error in search_and_download_photo_tool: {str(e)}")
        return {
            "success": False,
            "error": f"Failed to search and download photo: {str(e)}"
        } 