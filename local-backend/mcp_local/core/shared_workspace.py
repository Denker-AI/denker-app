"""
Shared Workspace Manager for Multi-Agent File Path Coordination

This module ensures all agents in the system can reliably share files by:
1. Maintaining a consistent shared workspace directory
2. Normalizing file paths across agents
3. Providing utilities for cross-agent file access
4. Managing workspace metadata and file tracking
"""

import os
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from datetime import datetime
import tempfile
import shutil

logger = logging.getLogger(__name__)

class SharedWorkspaceManager:
    """
    Manages shared workspace for multi-agent file coordination.
    
    Ensures all agents can access files created by other agents through:
    - Centralized workspace directory
    - Path normalization
    - File metadata tracking
    - Cross-agent file references
    """
    
    @staticmethod
    def _get_unified_workspace_path(session_id: str = "default") -> Path:
        """
        Get a unified workspace path that resolves consistently across all platforms.
        This ensures all components use exactly the same absolute path.
        
        Args:
            session_id: Session identifier for the workspace
            
        Returns:
            Unified workspace path resolved to /tmp/denker_workspace/{session_id}
        """
        # Force use of /tmp to avoid macOS temp directory variations
        # /tmp is a standard location that should work consistently
        unified_base = Path("/tmp/denker_workspace")
        unified_path = unified_base / session_id
        
        # Resolve to get absolute canonical path
        return unified_path.resolve()

    def __init__(self, workspace_root: Optional[str] = None, session_id: Optional[str] = None):
        """
        Initialize the shared workspace manager.
        
        Args:
            workspace_root: Root directory for shared workspace (uses temp if None)
            session_id: Optional session ID for organizing files
        """
        self.session_id = session_id or "default"
        
        # Set up workspace root
        if workspace_root:
            self.workspace_root = Path(workspace_root).resolve()
        else:
            # FIXED: Always use unified workspace path - resolve /tmp consistently
            self.workspace_root = self._get_unified_workspace_path(self.session_id)
            logger.info(f"[SharedWorkspaceManager] Using unified workspace: {self.workspace_root}")
            
            # Log environment variables for debugging but don't use them
            denker_memory_path = os.environ.get('DENKER_MEMORY_DATA_PATH')
            logger.info(f"[SharedWorkspaceManager] Environment variables detected but not used:")
            logger.info(f"  DENKER_MEMORY_DATA_PATH: {denker_memory_path}")
            logger.info(f"[SharedWorkspaceManager] Using unified workspace instead: {self.workspace_root}")
        
        # Ensure the workspace root exists
        self.workspace_root.mkdir(parents=True, exist_ok=True)
        logger.info(f"[SharedWorkspaceManager] Final workspace root: {self.workspace_root}")
        
        # Initialize the workspace metadata file
        self.metadata_file = self.workspace_root / "workspace_metadata.json"
        self.file_registry: Dict[str, Dict[str, Any]] = {}
        
        # Load existing metadata if available
        self._load_metadata()
    
    def _load_metadata(self):
        """Load file registry from metadata file."""
        if self.metadata_file.exists():
            try:
                with open(self.metadata_file, 'r') as f:
                    self.file_registry = json.load(f)
            except Exception as e:
                logger.warning(f"Could not load workspace metadata: {e}")
        else:
            self.file_registry = {
                "session_id": self.session_id,
                "created": datetime.now().isoformat(),
                "files": {},
                "agents": {}
            }
    
    def _save_registry(self):
        """Save file registry to metadata file."""
        try:
            with open(self.metadata_file, 'w') as f:
                json.dump(self.file_registry, f, indent=2)
        except Exception as e:
            logger.error(f"Could not save workspace metadata: {e}")
    
    def get_shared_path(self, category: str = None) -> Path:
        """
        Get the shared workspace path (no subdirectories - all files in root).
        
        Args:
            category: Ignored - all files go in workspace root
            
        Returns:
            Path object for the workspace root directory
        """
        return self.workspace_root
    
    def normalize_path(self, file_path: Union[str, Path], relative_to_workspace: bool = True) -> Path:
        """
        Normalize a file path to be workspace-relative or absolute.
        All files are stored directly in workspace root (no subdirectories).
        
        Args:
            file_path: Input file path
            relative_to_workspace: If True, return path relative to workspace
            
        Returns:
            Normalized Path object (always in workspace root)
        """
        path = Path(file_path)
        
        # Extract just the filename - no subdirectories allowed
        filename = path.name
        workspace_path = self.workspace_root / filename
        
        # If original file exists outside workspace, copy it to workspace
        if path.is_absolute() and path.exists() and not workspace_path.exists():
            try:
                # Check if path is within workspace
                path.relative_to(self.workspace_root)
            except ValueError:
                # Path is outside workspace, copy to workspace root
                shutil.copy2(path, workspace_path)
                logger.info(f"Copied external file {path} to workspace: {workspace_path}")
        
        if relative_to_workspace:
            try:
                return workspace_path.relative_to(self.workspace_root)
            except ValueError:
                return Path(filename)  # Just return filename
        else:
            return workspace_path.resolve()
    
    def register_file(self, file_path: Union[str, Path], agent_name: str, 
                     metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Register a file in the shared workspace.
        
        Args:
            file_path: Path to the file (like "report.md" or "charts/analysis.png")
            agent_name: Name of the agent that created the file
            metadata: Additional metadata about the file
            
        Returns:
            File ID for cross-agent reference
        """
        normalized_path = self.normalize_path(file_path, relative_to_workspace=True)
        absolute_path = self.workspace_root / normalized_path
        
        # Generate simple file ID based on the actual filename
        file_id = str(normalized_path).replace('/', '_').replace('\\', '_')
        
        # If file ID already exists, append timestamp
        if file_id in self.file_registry["files"]:
            timestamp = int(datetime.now().timestamp())
            file_id = f"{file_id}_{timestamp}"
        
        # Ensure file exists
        if not absolute_path.exists():
            logger.warning(f"Registering non-existent file: {absolute_path}")
        
        # Register in metadata
        file_info = {
            "file_id": file_id,
            "path": str(normalized_path),
            "absolute_path": str(absolute_path),
            "agent": agent_name,
            "created": datetime.now().isoformat(),
            "size": absolute_path.stat().st_size if absolute_path.exists() else 0,
            "metadata": metadata or {}
        }
        
        self.file_registry["files"][file_id] = file_info
        
        # Track agent activity
        if agent_name not in self.file_registry["agents"]:
            self.file_registry["agents"][agent_name] = []
        self.file_registry["agents"][agent_name].append(file_id)
        
        self._save_registry()
        logger.info(f"Registered file {file_id}: {normalized_path} (agent: {agent_name})")
        
        return file_id
    
    def find_file(self, file_reference: str, agent_name: Optional[str] = None) -> Optional[Path]:
        """
        Find a file by direct path, ID, name, or partial path.
        
        Args:
            file_reference: File path (like "report.md"), file ID, filename, or partial path
            agent_name: Optional agent name to filter by
            
        Returns:
            Absolute path to file if found, None otherwise
        """
        # Try direct path resolution first (most common case)
        direct_path = self.workspace_root / file_reference
        if direct_path.exists() and direct_path.is_file():
            return direct_path
        
        # Try exact file ID match
        if file_reference in self.file_registry["files"]:
            file_info = self.file_registry["files"][file_reference]
            return Path(file_info["absolute_path"])
        
        # Search by filename or partial path in registry
        matches = []
        for file_id, file_info in self.file_registry["files"].items():
            if agent_name and file_info["agent"] != agent_name:
                continue
                
            file_path = Path(file_info["path"])
            if (file_reference in str(file_path) or 
                file_reference == file_path.name or
                file_reference == file_path.stem):
                matches.append(Path(file_info["absolute_path"]))
        
        if len(matches) == 1:
            return matches[0]
        elif len(matches) > 1:
            logger.warning(f"Multiple files match '{file_reference}': {matches}")
            return matches[0]  # Return first match
        
        # Search in filesystem as fallback
        for pattern in ["**/*" + file_reference + "*", "**/" + file_reference]:
            for match in self.workspace_root.glob(pattern):
                if match.is_file():
                    return match
        
        return None
    
    def list_files(self, agent_name: Optional[str] = None, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List files in the workspace.
        
        Args:
            agent_name: Optional agent name filter
            category: Optional category filter
            
        Returns:
            List of file information dictionaries
        """
        results = []
        
        for file_id, file_info in self.file_registry["files"].items():
            if agent_name and file_info["agent"] != agent_name:
                continue
                
            if category:
                file_path = Path(file_info["path"])
                if not str(file_path).startswith(category):
                    continue
            
            results.append(file_info.copy())
        
        return results
    
    def get_agent_context(self, agent_name: str) -> Dict[str, Any]:
        """
        Get workspace context for a specific agent.
        
        Args:
            agent_name: Name of the agent
            
        Returns:
            Context dictionary with paths and file info
        """
        agent_files = self.list_files(agent_name=agent_name)
        
        return {
            "workspace_root": str(self.workspace_root),
            "agent_name": agent_name,
            "agent_files": agent_files,
            "file_count": len(agent_files),
            "available_files": [f["file_id"] for f in self.list_files()]
        }
    
    def create_file_path(self, filename: str, subdirectory: str = None) -> Path:
        """
        Create a file path in the workspace root (subdirectories ignored).
        
        Args:
            filename: Name of the file (like "report.md")
            subdirectory: Ignored - all files go in workspace root
            
        Returns:
            Absolute path where the file should be created (always in workspace root)
        """
        # Extract just filename, ignore any subdirectory parameter
        clean_filename = Path(filename).name
        file_path = self.workspace_root / clean_filename
        
        # Ensure workspace root exists (no subdirectories created)
        self.workspace_root.mkdir(parents=True, exist_ok=True)
        
        return file_path
    
    def cleanup_session(self):
        """Clean up workspace files for the session."""
        try:
            if self.workspace_root.exists():
                # Clean up if it's in temp directory OR in denker workspace areas
                workspace_path_str = str(self.workspace_root)
                should_cleanup = (
                    "temp" in workspace_path_str or 
                    "denker_workspace" in workspace_path_str or
                    "workspace" in workspace_path_str.split(os.sep)[-2:]  # workspace is one of last 2 path components
                )
                
                if should_cleanup:
                    shutil.rmtree(self.workspace_root)
                    logger.info(f"Cleaned up workspace: {self.workspace_root}")
                else:
                    logger.info(f"Skipping cleanup of non-temporary workspace: {self.workspace_root}")
        except Exception as e:
            logger.error(f"Error cleaning up workspace: {e}")
    
    def get_filesystem_friendly_path(self, file_reference: str) -> Optional[str]:
        """
        Get a filesystem-friendly path that can be used by both markdown-editor and filesystem tools.
        
        Args:
            file_reference: File ID, filename, or partial path
            
        Returns:
            Relative path from workspace root suitable for filesystem tools
        """
        found_path = self.find_file(file_reference)
        if found_path:
            try:
                # Return path relative to workspace root for filesystem tool compatibility
                return str(found_path.relative_to(self.workspace_root))
            except ValueError:
                # If file is outside workspace, return just the filename
                return found_path.name
        return None
    
    def suggest_simple_filename(self, filename: str, agent_name: str) -> str:
        """
        Suggest a simple, user-friendly filename while avoiding conflicts.
        
        Args:
            filename: Desired filename
            agent_name: Name of the creating agent
            
        Returns:
            Available filename (may add number suffix if needed)
        """
        base_name, ext = os.path.splitext(filename)
        candidate = filename
        counter = 1
        
        while (self.workspace_root / candidate).exists():
            candidate = f"{base_name}_{counter}{ext}"
            counter += 1
            
        return candidate

# Global workspace manager instance
_workspace_manager: Optional[SharedWorkspaceManager] = None

def get_shared_workspace(session_id: Optional[str] = None, workspace_root: Optional[str] = None) -> SharedWorkspaceManager:
    """
    Get or create the global shared workspace manager.
    
    Args:
        session_id: Optional session ID (ignored if workspace already exists)
        workspace_root: Optional workspace root directory (ignored if workspace already exists)
        
    Returns:
        SharedWorkspaceManager instance
    """
    global _workspace_manager
    
    if _workspace_manager is None:
        # Create new workspace manager if none exists
        _workspace_manager = SharedWorkspaceManager(
            workspace_root=workspace_root,
            session_id=session_id or "default"
        )
    
    # Always return the existing workspace manager to ensure consistency
    return _workspace_manager

def init_shared_workspace(session_id: str, workspace_root: Optional[str] = None) -> SharedWorkspaceManager:
    """
    Initialize the shared workspace for a session.
    
    Args:
        session_id: Session ID for the workspace
        workspace_root: Optional custom workspace root
        
    Returns:
        SharedWorkspaceManager instance
    """
    global _workspace_manager
    _workspace_manager = SharedWorkspaceManager(
        workspace_root=workspace_root,
        session_id=session_id
    )
    return _workspace_manager

def cleanup_all_sessions(base_path: Optional[str] = None):
    """
    Clean up all workspace sessions in the base directory.
    
    Args:
        base_path: Optional base path to clean (uses default locations if None)
    """
    base_paths = []
    
    if base_path:
        base_paths.append(Path(base_path))
    else:
        # Default cleanup locations
        if os.environ.get('DENKER_MEMORY_DATA_PATH'):
            base_paths.append(Path(os.environ.get('DENKER_MEMORY_DATA_PATH')).parent / "workspace")
        base_paths.append(Path("/tmp/denker_workspace"))
    
    for base in base_paths:
        if base.exists() and base.is_dir():
            try:
                shutil.rmtree(base)
                logger.info(f"Cleaned up all sessions in: {base}")
            except Exception as e:
                logger.error(f"Error cleaning up {base}: {e}")

def migrate_old_sessions_to_main(base_path: Optional[str] = None) -> bool:
    """
    Migrate files from old timestamp-based session directories to the main workspace.
    
    Args:
        base_path: Optional base path to search for old sessions
        
    Returns:
        True if migration was performed, False otherwise
    """
    import glob
    import shutil
    
    base_paths = []
    
    if base_path:
        base_paths.append(Path(base_path))
    else:
        # Default migration locations
        if os.environ.get('DENKER_MEMORY_DATA_PATH'):
            base_paths.append(Path(os.environ.get('DENKER_MEMORY_DATA_PATH')).parent / "workspace")
        base_paths.append(Path("/tmp/denker_workspace"))
    
    migrated = False
    
    for base in base_paths:
        if not base.exists():
            continue
            
        # Find old session directories (denker_* pattern)
        old_sessions = []
        for item in base.iterdir():
            if item.is_dir() and item.name.startswith('denker_') and item.name != 'default':
                # Check if it looks like a timestamp-based session
                try:
                    timestamp_part = item.name.split('_')[1]
                    int(timestamp_part)  # Will raise ValueError if not a number
                    old_sessions.append(item)
                except (IndexError, ValueError):
                    continue
        
        if not old_sessions:
            continue
            
        # Get the most recent session (highest timestamp)
        most_recent = max(old_sessions, key=lambda x: int(x.name.split('_')[1]))
        
        # Create default workspace if it doesn't exist
        default_workspace = base / "default"
        default_workspace.mkdir(exist_ok=True)
        
        logger.info(f"Migrating files from {most_recent} to {default_workspace}")
        
        # Copy files from most recent session to default workspace
        try:
            for item in most_recent.iterdir():
                dest = default_workspace / item.name
                if item.is_file():
                    if not dest.exists():  # Don't overwrite existing files
                        shutil.copy2(item, dest)
                        logger.info(f"Migrated file: {item.name}")
                elif item.is_dir():
                    # CHANGED: Don't migrate subdirectories - flatten structure
                    # Copy files from subdirectories directly to root
                    for subitem in item.iterdir():
                        if subitem.is_file():
                            subdest = default_workspace / subitem.name
                            if not subdest.exists():
                                shutil.copy2(subitem, subdest)
                                logger.info(f"Migrated file from {item.name}: {subitem.name}")
            
            migrated = True
            
            # Clean up old sessions after successful migration
            for old_session in old_sessions:
                try:
                    shutil.rmtree(old_session)
                    logger.info(f"Cleaned up old session: {old_session}")
                except Exception as e:
                    logger.warning(f"Could not clean up old session {old_session}: {e}")
                    
        except Exception as e:
            logger.error(f"Error during migration from {most_recent}: {e}")
    
    return migrated

def generate_session_id(user_id: Optional[str] = None, conversation_id: Optional[str] = None) -> str:
    """
    Generate a proper session ID for workspace isolation.
    
    Args:
        user_id: Optional user identifier
        conversation_id: Optional conversation identifier
        
    Returns:
        Session ID string
    """
    import time
    
    components = []
    
    if user_id:
        components.append(f"user_{user_id}")
    if conversation_id:
        components.append(f"conv_{conversation_id}")
    
    # Add timestamp for uniqueness
    timestamp = int(time.time())
    components.append(f"t_{timestamp}")
    
    if not components:
        return "default"
    
    return "_".join(components) 