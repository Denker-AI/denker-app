"""
Global Coordinator Singleton

This module provides a singleton instance of the CoordinatorAgent with
proper lifecycle management for application-wide usage.
"""

import asyncio
import logging
import os
import sys
import json
import tempfile
import yaml
import uuid
import signal
from typing import Optional, Dict, Any
import inspect

from fastapi import Depends
from mcp_local.coordinator_agent import CoordinatorAgent
from mcp_local.core.shared_workspace import init_shared_workspace, get_shared_workspace, migrate_old_sessions_to_main

logger = logging.getLogger(__name__)

# Global coordinator instance
_coordinator: Optional[CoordinatorAgent] = None
_initialization_lock = asyncio.Lock()
_initialization_task = None
_cleanup_task = None
_initialized = False
_temp_config_path: Optional[str] = None # To store the path of the temporary config file
_restart_in_progress = False # Flag to prevent concurrent restarts

# Helper function to get user settings file path (can be moved to a common utils later)
def get_user_settings_file_path():
    return os.environ.get("DENKER_USER_SETTINGS_PATH", "./denker_user_settings.json")

def is_coordinator_restart_in_progress():
    """Check if coordinator restart/initialization is currently in progress."""
    return _restart_in_progress

def get_initialization_task():
    """Get the current initialization task if one exists."""
    return _initialization_task

async def wait_for_coordinator_ready(timeout_seconds: int = None):
    """
    Wait for coordinator to be fully initialized and ready.
    
    Args:
        timeout_seconds: Maximum time to wait. If None, uses environment variable 
                        DENKER_COORDINATOR_TIMEOUT_SECONDS (default: 120 for production startup)
    
    Returns:
        tuple: (success: bool, status: str, details: dict)
    """
    # Get timeout from environment or use default (increased to 120s for production startup)
    if timeout_seconds is None:
        timeout_seconds = int(os.environ.get("DENKER_COORDINATOR_TIMEOUT_SECONDS", "120"))
    
    logger.info(f"Waiting for coordinator readiness with timeout: {timeout_seconds}s")
    
    start_time = asyncio.get_event_loop().time()
    details = {
        "timeout_seconds": timeout_seconds,
        "start_time": start_time,
        "phases_completed": []
    }
    
    # Phase 1: Wait for restart flag to clear
    if _restart_in_progress:
        logger.info(f"Coordinator initialization in progress, waiting up to {timeout_seconds} seconds...")
        details["phases_completed"].append("waiting_for_restart_flag")
        
        for i in range(timeout_seconds):
            if not _restart_in_progress:
                logger.info("Coordinator initialization completed while waiting")
                details["restart_wait_seconds"] = i
                break
            await asyncio.sleep(1)
        else:
            elapsed = asyncio.get_event_loop().time() - start_time
            logger.warning(f"Timeout waiting {timeout_seconds}s for coordinator initialization")
            details["timeout_phase"] = "restart_flag"
            details["elapsed_seconds"] = elapsed
            return False, "timeout_waiting_for_restart", details
    
    # Phase 2: Wait for initialization task
    if _initialization_task is not None and not _initialization_task.done():
        remaining_time = timeout_seconds - (asyncio.get_event_loop().time() - start_time)
        if remaining_time <= 0:
            details["timeout_phase"] = "initialization_task"
            details["elapsed_seconds"] = asyncio.get_event_loop().time() - start_time
            return False, "timeout_before_task_wait", details
            
        logger.info(f"Coordinator initialization task in progress, waiting {remaining_time:.1f}s for completion...")
        details["phases_completed"].append("waiting_for_initialization_task")
        
        try:
            await asyncio.wait_for(_initialization_task, timeout=remaining_time)
            logger.info("Coordinator initialization task completed")
            details["task_completed"] = True
        except asyncio.TimeoutError:
            elapsed = asyncio.get_event_loop().time() - start_time
            logger.warning(f"Timeout waiting {remaining_time:.1f}s for initialization task")
            details["timeout_phase"] = "initialization_task"
            details["elapsed_seconds"] = elapsed
            return False, "timeout_waiting_for_task", details
        except Exception as e:
            elapsed = asyncio.get_event_loop().time() - start_time
            logger.error(f"Error waiting for initialization task: {e}")
            details["error_phase"] = "initialization_task"
            details["error"] = str(e)
            details["elapsed_seconds"] = elapsed
            return False, f"error_waiting_for_task: {e}", details
    
    # Phase 3: Final readiness check
    details["phases_completed"].append("final_readiness_check")
    try:
        coordinator = await get_coordinator()
        if coordinator and hasattr(coordinator, '_initialized') and coordinator._initialized:
            elapsed = asyncio.get_event_loop().time() - start_time
            details["elapsed_seconds"] = elapsed
            details["coordinator_ready"] = True
            logger.info(f"Coordinator ready after {elapsed:.1f}s")
            return True, "ready", details
        else:
            elapsed = asyncio.get_event_loop().time() - start_time
            details["elapsed_seconds"] = elapsed
            details["coordinator_ready"] = False
            details["coordinator_exists"] = coordinator is not None
            details["coordinator_initialized"] = hasattr(coordinator, '_initialized') and coordinator._initialized if coordinator else False
            return False, "not_initialized", details
    except Exception as e:
        elapsed = asyncio.get_event_loop().time() - start_time
        logger.error(f"Error checking coordinator readiness: {e}")
        details["error_phase"] = "readiness_check"
        details["error"] = str(e)
        details["elapsed_seconds"] = elapsed
        return False, f"error_checking_readiness: {e}", details

async def initialize_coordinator():
    """
    Initialize the global coordinator.
    This function is idempotent - calling it multiple times will only
    initialize the coordinator once.
    """
    global _coordinator, _initialized, _initialization_task, _temp_config_path, _restart_in_progress
    
    async with _initialization_lock:
        # Check if restart is already in progress
        if _restart_in_progress:
            logger.info("Coordinator restart already in progress, skipping duplicate request")
            # Wait for up to 30 seconds for the current restart to complete
            for i in range(30):
                if not _restart_in_progress:
                    logger.info("Coordinator restart completed while waiting")
                    return
                await asyncio.sleep(1)
            logger.warning("Timeout waiting for coordinator restart to complete")
            return
        
        if _initialized:
            logger.info("Global coordinator already initialized")
            return
            
        if _initialization_task is not None and not _initialization_task.done():
            logger.info("Coordinator initialization already in progress")
            return
        
        # Set restart flag to prevent concurrent restarts
        _restart_in_progress = True
        logger.info("Coordinator restart flag set - preventing concurrent restarts")
        
        logger.info("Initializing global coordinator instance")
        try:
            if _coordinator is None:
                # --- Initialize Shared Workspace (NEW) ---
                # Create session-specific workspace for multi-agent coordination
                # CHANGED: Use consistent session ID instead of timestamp-based
                # This ensures files persist across backend restarts
                session_id = "default"  # Use default session ID
                
                # Initialize shared workspace for this session
                # SharedWorkspaceManager will automatically use the unified workspace path
                shared_workspace = init_shared_workspace(
                    session_id=session_id,
                    workspace_root=None  # Let SharedWorkspaceManager use unified workspace
                )
                logger.info(f"Initialized shared workspace: {shared_workspace.workspace_root}")
                
                # --- ADDED: Migrate files from old session directories ---
                try:
                    migrated = migrate_old_sessions_to_main()
                    if migrated:
                        logger.info("Successfully migrated files from old session directories to main workspace")
                    else:
                        logger.info("No old session directories found to migrate")
                except Exception as e:
                    logger.warning(f"Could not migrate old session directories: {e}")
                
                # --- Dynamically configure filesystem server paths ---
                # Get config file path - handle both dev and production modes
                if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
                    # PyInstaller frozen app - config is in sys._MEIPASS/mcp_local/
                    config_file_path = os.path.join(sys._MEIPASS, 'mcp_local', 'mcp_agent.config.yaml')
                    logger.info(f"[FROZEN] Loading MCP Agent config from PyInstaller bundle: {config_file_path}")
                else:
                    # Development mode - use relative path from current file
                    config_file_path = os.path.join(os.path.dirname(__file__), "../mcp_local/mcp_agent.config.yaml")
                    config_file_path = os.path.abspath(config_file_path)
                    logger.info(f"[DEV] Loading MCP Agent config from development path: {config_file_path}")

                if not os.path.exists(config_file_path):
                    # Additional debugging for frozen mode
                    if getattr(sys, 'frozen', False):
                        mcp_local_path = os.path.join(sys._MEIPASS, 'mcp_local')
                        if os.path.exists(mcp_local_path):
                            logger.error(f"mcp_local directory exists but config file missing. Contents: {os.listdir(mcp_local_path)}")
                        else:
                            logger.error(f"mcp_local directory not found at: {mcp_local_path}")
                            logger.error(f"Available in _MEIPASS: {os.listdir(sys._MEIPASS)}")
                    
                    logger.error(f"MCP Agent config file not found at {config_file_path}")
                    raise FileNotFoundError(f"MCP Agent config file not found at {config_file_path}")

                logger.info(f"Successfully found MCP Agent config at: {config_file_path}")
                with open(config_file_path, 'r') as f:
                    config_content = f.read()
                
                # Perform environment variable substitution
                config_content = os.path.expandvars(config_content)
                agent_config_dict = yaml.safe_load(config_content)

                # Ensure anthropic config section exists for the Anthropic LLM client
                # This allows the Anthropic client to gracefully fall back to environment variables
                # if api_key is null or not set here.
                if 'anthropic' not in agent_config_dict:
                    agent_config_dict['anthropic'] = {'api_key': None} 
                elif not isinstance(agent_config_dict.get('anthropic'), dict):
                    # If 'anthropic' exists but is not a dict, overwrite with a valid structure
                    agent_config_dict['anthropic'] = {'api_key': None}
                elif 'api_key' not in agent_config_dict['anthropic']:
                    # If 'anthropic' dict exists but 'api_key' is missing, add it as None
                    agent_config_dict['anthropic']['api_key'] = None

                # Use shared workspace as the default accessible path
                default_fs_root = str(shared_workspace.workspace_root)
                if not os.path.exists(default_fs_root):
                     os.makedirs(default_fs_root, exist_ok=True)

                # Get user-defined accessible paths from local settings JSON
                user_settings_json_path = get_user_settings_file_path()
                user_accessible_folders = []
                if os.path.exists(user_settings_json_path):
                    try:
                        with open(user_settings_json_path, 'r') as f:
                            user_settings = json.load(f)
                        user_accessible_folders = user_settings.get('accessibleFolders', [])
                        if not isinstance(user_accessible_folders, list):
                            logger.warning(f"'accessibleFolders' in {user_settings_json_path} is not a list. Ignoring.")
                            user_accessible_folders = []
                    except json.JSONDecodeError:
                        logger.error(f"Error decoding JSON from {user_settings_json_path}. No user folders will be added.")
                    except Exception as e:
                        logger.error(f"Error reading user settings from {user_settings_json_path}: {e}. No user folders will be added.")
                else:
                    logger.info(f"User settings file not found at {user_settings_json_path}. No user-specific folders will be added initially.")

                # Always include shared workspace root in accessible folders (NEW)
                if str(shared_workspace.workspace_root) not in user_accessible_folders:
                    user_accessible_folders.insert(0, str(shared_workspace.workspace_root))

                # Construct the new arguments for the filesystem server
                # Default args for @modelcontextprotocol/server-filesystem often include the script path and a base app path.
                # We need to preserve these if they exist, or use a sensible default set.
                # For this example, let's assume the original YAML specifies the script path and we add others.
                
                filesystem_config = agent_config_dict.get('mcp', {}).get('servers', {}).get('filesystem', {})
                if not filesystem_config:
                    logger.warning("Filesystem server configuration not found in mcp_agent.config.yaml. Cannot set accessible paths.")
                else:
                    original_args = filesystem_config.get('args', [])
                    # Typically, the first arg is the script/package, second might be a base like '/app'.
                    # We need to be careful not to remove essential startup args for the server itself.
                    # The paths we add should be *additional* arguments.
                    
                    # Example: server-filesystem expects paths as separate arguments AFTER its own initial args.
                    # Let's assume the YAML already contains the necessary command and initial args like the package name.
                    # Example original_args from your YAML: 
                    # ["/usr/local/lib/node_modules/@modelcontextprotocol/server-filesystem/dist/index.js", "/app"]
                    # or for npx: ["-y", "@modelcontextprotocol/server-filesystem"]

                    new_paths_to_add = []
                    if default_fs_root:
                        new_paths_to_add.append(default_fs_root)
                    new_paths_to_add.extend(user_accessible_folders)
                    
                    # Ensure paths are unique and valid strings
                    final_paths = sorted(list(set(p for p in new_paths_to_add if isinstance(p, str) and p)))
                    logger.info(f"[GlobalCoordinator] Paths after filtering and unique: {final_paths}")

                    if not final_paths:
                        logger.warning("No valid default or user-defined paths for filesystem server. It might not function correctly.")
                        # Fallback: ensure at least one dummy/default path if absolutely required by the server to start
                        # This depends on server-filesystem's behavior with no paths.
                        # For now, we'll let it be empty if no paths are found, but often a default is needed.
                        # A robust solution would ensure the default_fs_root is always valid and present.
                        final_paths.append(default_fs_root) # Re-add default if list became empty

                    # Update the args in the config dictionary
                    # Assuming the original args list in YAML contains the command and its fixed options, and paths are appended.                    
                    # If your YAML args for filesystem were just ["@modelcontextprotocol/server-filesystem", "/app"], 
                    # then it should become ["@modelcontextprotocol/server-filesystem", "/app", path1, path2...]
                    # If it was ["node", "path/to/script.js", "/app"], it becomes ["node", "path/to/script.js", "/app", path1, path2...]
                    
                    # Let's try to find where to insert. If '/app' is present, insert after it.
                    # This is a heuristic. A more robust way is to structure config to clearly separate fixed args from path args.
                    base_args_for_server_itself = []
                    path_insertion_index = 0 
                    # Heuristic: look for common server-filesystem args to determine where paths should be appended.
                    # If using npx, paths are added after package name (and potentially -y option)
                    # If using node, paths are added after the script and any fixed args for that script.

                    if original_args and "@modelcontextprotocol/server-filesystem" in original_args[0]: # direct node call
                        base_args_for_server_itself = original_args[:2] # e.g. [script_path, "/app"]
                        path_insertion_index = 2
                    elif original_args and "@modelcontextprotocol/server-filesystem" in original_args: # npx call
                        idx = original_args.index("@modelcontextprotocol/server-filesystem")
                        base_args_for_server_itself = original_args[:idx+1]
                        if "-y" in base_args_for_server_itself: # ensure -y is kept if it was there
                             pass # it's already included
                        elif "-y" in original_args[:idx]:
                             base_args_for_server_itself = original_args[:idx+1]
                        path_insertion_index = len(base_args_for_server_itself)
                    else: # fallback or different server structure
                        base_args_for_server_itself = list(original_args) # copy
                        path_insertion_index = len(base_args_for_server_itself)
                        logger.warning(f"FS server args structure in YAML not recognized for dynamic path insertion. Appending paths to original args: {original_args}")

                    updated_fs_args = base_args_for_server_itself + final_paths
                    agent_config_dict['mcp']['servers']['filesystem']['args'] = updated_fs_args
                    logger.info(f"[GlobalCoordinator] User Accessible Folders read from settings: {user_accessible_folders}")
                    logger.info(f"[GlobalCoordinator] default_fs_root: {default_fs_root}")
                    logger.info(f"[GlobalCoordinator] new_paths_to_add before filtering: {new_paths_to_add}")
                    logger.info(f"[GlobalCoordinator] base_args_for_server_itself determined as: {base_args_for_server_itself}")
                    logger.info(f"Updated filesystem server args to: {updated_fs_args}")

                # --- Replace 'python' with sys.executable for frozen apps ---
                # When PyInstaller creates a frozen app, 'python' in PATH might not have access
                # to the bundled modules. We need to use sys.executable instead.
                if getattr(sys, 'frozen', False):
                    logger.info("[GlobalCoordinator] App is frozen (PyInstaller). Replacing 'python' commands with sys.executable for MCP servers.")
                    mcp_servers = agent_config_dict.get('mcp', {}).get('servers', {})
                    
                    for server_name, server_config in mcp_servers.items():
                        command = server_config.get('command')
                        if command == 'python':
                            logger.info(f"[GlobalCoordinator] Replacing 'python' with '{sys.executable}' for server '{server_name}'")
                            server_config['command'] = sys.executable
                        elif command and 'python' in command.lower():
                            logger.warning(f"[GlobalCoordinator] Server '{server_name}' uses command '{command}' containing 'python'. Consider reviewing if this needs to be updated.")

                # --- SECURITY: Replace user_id placeholder with actual user_id from LocalUserStore ---
                try:
                    from core.user_store import LocalUserStore
                    stored_user_info = LocalUserStore.get_user()
                    
                    if stored_user_info and stored_user_info.get("user_id"):
                        current_user_id = stored_user_info.get("user_id")
                        logger.info(f"[SECURITY] Found user_id in LocalUserStore: {current_user_id}")
                        
                        # Replace user_id placeholder in qdrant server environment variables
                        mcp_servers = agent_config_dict.get('mcp', {}).get('servers', {})
                        qdrant_config = mcp_servers.get('qdrant', {})
                        
                        if qdrant_config and 'env' in qdrant_config:
                            qdrant_env = qdrant_config['env']
                            if 'DENKER_CURRENT_USER_ID' in qdrant_env:
                                old_value = qdrant_env['DENKER_CURRENT_USER_ID']
                                qdrant_env['DENKER_CURRENT_USER_ID'] = current_user_id
                                logger.info(f"[SECURITY] Updated qdrant DENKER_CURRENT_USER_ID: '{old_value}' -> '{current_user_id}'")
                            else:
                                # Add user_id if not present in config
                                qdrant_env['DENKER_CURRENT_USER_ID'] = current_user_id
                                logger.info(f"[SECURITY] Added qdrant DENKER_CURRENT_USER_ID: '{current_user_id}'")
                        else:
                            logger.warning("[SECURITY] Qdrant server configuration not found or missing env section")
                    else:
                        logger.warning("[SECURITY] No user_id found in LocalUserStore - qdrant will use placeholder")
                except Exception as e:
                    logger.error(f"[SECURITY] Error updating user_id in qdrant config: {e}")

                # Ensure agent_config_dict is fully prepared before this point

                # Create a temporary file to store the modified configuration
                with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as tmp_cfg_file:
                    yaml.dump(agent_config_dict, tmp_cfg_file, sort_keys=False)
                    _temp_config_path = tmp_cfg_file.name # Store the path for cleanup

                # <<< ADDED LOGGING TO PRINT TEMP FILE CONTENT >>>
                try:
                    with open(_temp_config_path, 'r') as f_read_temp:
                        temp_config_content = f_read_temp.read()
                    logger.info(f"[GlobalCoordinator] Content of temporary MCP config file ({_temp_config_path}):\n{temp_config_content}")
                except Exception as e_log_temp:
                    logger.error(f"[GlobalCoordinator] Error reading temporary config file for logging: {e_log_temp}")
                # <<< END ADDED LOGGING >>>

                logger.info(f"Dynamically constructed MCP config saved to temporary file: {_temp_config_path}")
                _coordinator = CoordinatorAgent(config_path=_temp_config_path) # Use config_path with the temp file
                logger.info("Created global coordinator instance with dynamically constructed config from temporary file.")
                
                # Store shared workspace reference in coordinator (NEW)
                _coordinator.shared_workspace = shared_workspace
                
                await _coordinator.setup()
            logger.info("Global coordinator setup complete")
            
            await _coordinator._create_required_agents()
            logger.info("Decider agent initialized successfully")

            _initialized = True
        except Exception as e:
            logger.error(f"Failed to initialize global coordinator: {str(e)}", exc_info=True)
            if _temp_config_path and os.path.exists(_temp_config_path):
                try:
                    os.unlink(_temp_config_path) # Clean up temp file on init failure
                    logger.info(f"Cleaned up temporary config file: {_temp_config_path}")
                    _temp_config_path = None
                except Exception as e_unlink:
                    logger.error(f"Error cleaning up temporary config file {_temp_config_path} on init failure: {e_unlink}")
            _coordinator = None
            _initialized = False
            raise
        finally:
            # Always clear the restart flag
            _restart_in_progress = False
            logger.info("Coordinator restart flag cleared")

async def get_coordinator() -> CoordinatorAgent:
    """
    Get the global coordinator instance.
    If the coordinator is not initialized, it will be initialized automatically.
    This function can be used as a FastAPI dependency.
    """
    global _coordinator, _initialized
    
    if not _initialized:
        await initialize_coordinator()
    
    if not _coordinator:
        raise RuntimeError("Coordinator not available - initialization may have failed")
    
    return _coordinator

async def cleanup_coordinator():
    """
    Clean up the global coordinator and its resources.
    """
    global _coordinator, _initialized, _temp_config_path, _restart_in_progress
    
    logger.info("Cleaning up global coordinator")
    
    try:
        if _coordinator:
            # --- ADDED: Cleanup workspace before shutting down ---
            if hasattr(_coordinator, 'shared_workspace') and _coordinator.shared_workspace:
                try:
                    _coordinator.shared_workspace.cleanup_session()
                    logger.info("Successfully cleaned up workspace cache")
                except Exception as e:
                    logger.warning(f"Could not cleanup workspace cache: {e}")
            
            # Close the coordinator
            await _coordinator.close()
            logger.info("Coordinator closed successfully")
    except Exception as e:
        logger.error(f"Error during coordinator cleanup: {e}")
    finally:
        _coordinator = None
        _initialized = False
        _restart_in_progress = False
        
        # Clean up temporary config file
        if _temp_config_path and os.path.exists(_temp_config_path):
            try:
                os.unlink(_temp_config_path)
                logger.info(f"Cleaned up temporary config file: {_temp_config_path}")
            except Exception as e:
                logger.warning(f"Could not clean up temporary config file: {e}")
            finally:
                _temp_config_path = None

# FastAPI dependency for injecting the coordinator
def get_coordinator_dependency():
    """
    A FastAPI dependency that provides the global coordinator instance.
    This is an awaitable function that can be used with Depends().
    
    Example:
        @router.post("/endpoint")
        async def endpoint(coordinator: CoordinatorAgent = Depends(get_coordinator_dependency())):
            # Use coordinator here
    """
    async def _get_coordinator_dependency():
        return await get_coordinator()
    
    return _get_coordinator_dependency

async def force_coordinator_reset():
    """
    Force reset the coordinator when it's stuck in initialization.
    This should only be used as a last resort.
    """
    global _coordinator, _initialized, _restart_in_progress, _initialization_task
    
    logger.warning("Force resetting coordinator due to stuck initialization")
    
    try:
        # Cancel any running initialization task
        if _initialization_task and not _initialization_task.done():
            _initialization_task.cancel()
            try:
                await _initialization_task
            except asyncio.CancelledError:
                logger.info("Cancelled stuck initialization task")
            except Exception as e:
                logger.warning(f"Error cancelling initialization task: {e}")
        
        # Clean up existing coordinator
        if _coordinator:
            try:
                await _coordinator.close()
            except Exception as e:
                logger.warning(f"Error closing coordinator during force reset: {e}")
        
        # Reset all global state
        _coordinator = None
        _initialized = False
        _restart_in_progress = False
        _initialization_task = None
        
        logger.info("Coordinator force reset completed")
        return True, "reset_completed"
        
    except Exception as e:
        logger.error(f"Error during force coordinator reset: {e}")
        return False, f"reset_failed: {e}"

# --- ADDED: Signal handlers for graceful shutdown ---
def setup_signal_handlers():
    """Setup signal handlers for graceful shutdown and workspace cleanup."""
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}, initiating graceful shutdown...")
        # Create a new event loop if none exists
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        # Run cleanup in the event loop
        if loop.is_running():
            # If loop is running, schedule cleanup as a task
            asyncio.create_task(cleanup_coordinator())
        else:
            # If loop is not running, run cleanup directly
            loop.run_until_complete(cleanup_coordinator())
        
        logger.info("Graceful shutdown complete")
        sys.exit(0)
    
    # Register signal handlers for common termination signals
    signal.signal(signal.SIGTERM, signal_handler)  # Termination signal
    signal.signal(signal.SIGINT, signal_handler)   # Interrupt signal (Ctrl+C)
    if hasattr(signal, 'SIGHUP'):  # Hangup signal (Unix only)
        signal.signal(signal.SIGHUP, signal_handler)

# Setup signal handlers when module is imported
setup_signal_handlers() 