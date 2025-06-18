import sys
import os
import traceback
import time

# --- MCP SERVER MODULE ROUTING ---
# CRITICAL: This MUST be the first thing that runs to prevent MCP server calls
# from starting the full FastAPI backend and causing port conflicts.
def handle_mcp_server_execution():
    """Check if we're being called to run an MCP server module and route to it."""
    # Debug: Print sys.argv for debugging
    print(f"[MCP_ROUTER_DEBUG] sys.argv: {sys.argv}", file=sys.stderr)
    print(f"[MCP_ROUTER_DEBUG] sys.executable: {sys.executable}", file=sys.stderr)
    print(f"[MCP_ROUTER_DEBUG] Current working directory: {os.getcwd()}", file=sys.stderr)
    
    # Check if this is a secondary process spawn from MCP coordinator
    # Look for specific environment variables or other indicators
    mcp_spawn_indicator = os.environ.get("MCP_SPAWN_MODE") 
    if mcp_spawn_indicator:
        print(f"[MCP_ROUTER] Detected MCP spawn mode: {mcp_spawn_indicator}", file=sys.stderr)
        # This is a secondary spawn - we should exit to prevent infinite spawning
        print(f"[MCP_ROUTER] Exiting to prevent cascading backend spawns", file=sys.stderr)
        sys.exit(0)
    
    # Original logic for -m flag routing
    if len(sys.argv) >= 3 and sys.argv[1] == "-m":
        module_name = sys.argv[2]
        
        # Map module names to their main functions
        mcp_server_modules = {
            "mcp_server_fetch": "mcp_server_fetch:main",
            "mcp_server_qdrant.main": "mcp_server_qdrant.main:main", 
            "mcp_local.servers.websearch.server": "mcp_local.servers.websearch.server:main",
            "mcp_local.servers.document_loader.server": "mcp_local.servers.document_loader.server:main",
            "mcp_local.servers.markdown_editor.server": "mcp_local.servers.markdown_editor.server:main",
        }
        
        if module_name in mcp_server_modules:
            print(f"[MCP_ROUTER] Routing to MCP server module: {module_name}", file=sys.stderr)
            
            # Clean up sys.argv to remove the -m and module_name arguments
            # Keep the script name (sys.argv[0]) and any arguments after the module name
            original_argv = sys.argv[:]
            sys.argv = [sys.argv[0]] + sys.argv[3:]  # Keep script name + any remaining args
            print(f"[MCP_ROUTER] Cleaned sys.argv: {sys.argv}", file=sys.stderr)
            
            # Import and run the specific MCP server
            try:
                if module_name == "mcp_server_fetch":
                    from mcp_server_fetch import main
                    main()  # Let the server run indefinitely
                elif module_name == "mcp_server_qdrant.main":
                    from mcp_server_qdrant.main import main
                    main()  # Let the server run indefinitely
                elif module_name == "mcp_local.servers.websearch.server":
                    from mcp_local.servers.websearch.server import main
                    main()  # Let the server run indefinitely
                elif module_name == "mcp_local.servers.document_loader.server":
                    from mcp_local.servers.document_loader.server import main
                    main()  # Let the server run indefinitely
                elif module_name == "mcp_local.servers.markdown_editor.server":
                    from mcp_local.servers.markdown_editor.server import main
                    main()  # Let the server run indefinitely
            except Exception as e:
                print(f"[MCP_ROUTER] Error running MCP server {module_name}: {e}", file=sys.stderr)
                traceback.print_exc()
                # Restore original argv before exiting
                sys.argv = original_argv
                sys.exit(1)
        else:
            print(f"[MCP_ROUTER] Unknown MCP server module: {module_name}", file=sys.stderr)
            print(f"[MCP_ROUTER] Available modules: {list(mcp_server_modules.keys())}", file=sys.stderr)
            # Don't exit here - let the normal backend continue if it's not an MCP server call
    else:
        print(f"[MCP_ROUTER] Not an MCP server call. len(sys.argv)={len(sys.argv)}, argv[1]={sys.argv[1] if len(sys.argv) > 1 else 'N/A'}", file=sys.stderr)
        
        # Check if this is a multiprocessing resource tracker or similar subprocess
        if len(sys.argv) >= 5 and sys.argv[1:4] == ['-B', '-S', '-I'] and sys.argv[4] == '-c':
            print(f"[MCP_ROUTER] Detected multiprocessing subprocess call, exiting early to prevent backend startup", file=sys.stderr)
            print(f"[MCP_ROUTER] Command being executed: {sys.argv[5] if len(sys.argv) > 5 else 'N/A'}", file=sys.stderr)
            # Execute the intended multiprocessing command instead of starting FastAPI
            if len(sys.argv) > 5:
                try:
                    exec(sys.argv[5])
                except Exception as e:
                    print(f"[MCP_ROUTER] Error executing multiprocessing command: {e}", file=sys.stderr)
            sys.exit(0)
        
        # Check if this is a general subprocess call with -c flag (like matplotlib, torch, etc.)
        if len(sys.argv) >= 3 and sys.argv[1] == '-c':
            print(f"[MCP_ROUTER] Detected general subprocess call with -c flag, exiting early to prevent backend startup", file=sys.stderr)
            print(f"[MCP_ROUTER] Command being executed: {sys.argv[2] if len(sys.argv) > 2 else 'N/A'}", file=sys.stderr)
            # Execute the intended command instead of starting FastAPI
            try:
                exec(sys.argv[2])
            except Exception as e:
                print(f"[MCP_ROUTER] Error executing subprocess command: {e}", file=sys.stderr)
            sys.exit(0)
        
        # Check if this process was spawned by the MCP coordinator but not with -m flag
        # Look for specific patterns that indicate this is an unintended secondary spawn
        if len(sys.argv) == 1:  # No arguments except the executable name
            # Check if we have a parent process that might be the main backend
            try:
                import psutil
                current_process = psutil.Process()
                parent = current_process.parent()
                if parent and 'local-backend-pkg' in parent.name():
                    print(f"[MCP_ROUTER] Detected spawned process with no args under backend parent. Exiting to prevent cascade.", file=sys.stderr)
                    sys.exit(0)
            except (ImportError, Exception) as e:
                # psutil not available or other error, use alternative detection
                print(f"[MCP_ROUTER] Could not check parent process: {e}", file=sys.stderr)
                
            # Alternative detection: Check if we're in a PyInstaller frozen app and there's no clear purpose
            if getattr(sys, 'frozen', False):
                # Check if there's already a process on port 9001
                try:
                    import socket
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    result = sock.connect_ex(('localhost', 9001))
                    sock.close()
                    if result == 0:  # Port is in use
                        print(f"[MCP_ROUTER] Port 9001 already in use by another process. This appears to be a secondary spawn. Exiting.", file=sys.stderr)
                        sys.exit(0)
                except Exception as e:
                    print(f"[MCP_ROUTER] Could not check port 9001: {e}", file=sys.stderr)

# CRITICAL: Check for MCP server execution IMMEDIATELY, before any other setup
handle_mcp_server_execution()

# NOTE: Matplotlib environment configuration removed
# QuickChart uses remote quickchart.io API - no local matplotlib needed
# This saves ~16 seconds from startup by avoiding matplotlib font cache build

import logging
import asyncio
import os
import requests
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

# Continue with normal local-backend server startup
from core.global_coordinator import initialize_coordinator, cleanup_coordinator, get_coordinator
import uvicorn
from api.api_v1.api import api_router
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from config.settings import settings

# Configure logging as the VERY FIRST THING
# This ensures all subsequent logging calls, including from early path setup, are captured.
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout) # Ensure output to stdout
    ]
)
logger = logging.getLogger(__name__) # Get logger for this file

# Set mcp_agent logger to DEBUG for more detailed output from it, if it exists
try:
    logging.getLogger("mcp_agent").setLevel(logging.DEBUG)
except Exception: # pylint: disable=broad-except
    logger.warning("Could not set mcp_agent logger level at initial setup. Will try again later if needed.")

# Automatic Qdrant dev/prod switching - Use same cloud Qdrant as production
if os.environ.get("DENKER_DEV_MODE", "false").lower() == "true":
    # Use same cloud Qdrant as production for consistency
    os.environ["QDRANT_URL"] = "https://f1f12584-e161-4974-b6fa-eb2e8bc3fdfc.europe-west3-0.gcp.cloud.qdrant.io"
    os.environ["QDRANT_API_KEY"] = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhY2Nlc3MiOiJtIn0.u7ZjD6dc0cEIMMX2ZxDHio-xD1IIjwYaTSm3PZ-dLEE"

# Set up logging
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Denker Local Backend",
    description="Local backend for Denker App with MCP Agent integration",
    version="0.1.0",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",        # Frontend dev server
        "http://localhost:3000",        # Alternative dev server
        "http://localhost:8000",        # Another possible dev server
        "http://localhost:8080",        # Another possible dev server 
        "http://localhost:9000",        # Another possible dev server
        "http://localhost:9001",        # Local backend itself
        "http://localhost:8001",        # Remote backend
        "https://denker-frontend.app",  # Production frontend
        "denker://*",                   # Electron custom protocol
        "file://*",                     # Electron file protocol (if used)
    ],  # Never use wildcard with credentials: include
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)

# Health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "ok", "message": "Local backend is operational"}

# Startup event: prepare environment but don't initialize coordinator yet
@app.on_event("startup")
async def startup_event():
    try:
        logger.info("Local backend startup event initiated.")

        # REMOVED: The following block that checked LocalUserStore and called _perform_post_authentication_setup.
        # The coordinator will now ONLY be initialized/configured via an explicit call to an auth endpoint
        # like /auth/local-login, which should be triggered by the frontend once user identity is confirmed.
        # from core.user_store import LocalUserStore
        # from api.api_v1.endpoints.agents import _perform_post_authentication_setup 
        # existing_user = LocalUserStore.get_user()
        # if existing_user and existing_user.get("user_id") and existing_user.get("token"):
        #     logger.info(f"Found existing authenticated user {existing_user.get('user_id')} at startup. Performing post-authentication setup.")
        #     await _perform_post_authentication_setup(
        #         user_id=existing_user.get("user_id"),
        #         token=existing_user.get("token"),
        #         existing_user_info_for_scenario=existing_user
        #     )
        #     logger.info("Post-authentication setup for existing user at startup completed. Coordinator should be initialized with relevant settings.")
        # else:
        #     logger.info("No existing authenticated user found at startup. Coordinator will be initialized after first manual login via /auth/local-login.")
        logger.info("Local backend services started. Coordinator initialization is deferred to frontend-driven authentication.")
            
    except Exception as e:
        logger.error(f"Error during startup: {str(e)}")

# Shutdown event: cleanup coordinator
@app.on_event("shutdown")
async def shutdown_event():
    try:
        await cleanup_coordinator()
        logger.info("Local coordinator cleaned up")
    except Exception as e:
        logger.error(f"Error during shutdown: {str(e)}")
        logger.error(traceback.format_exc())

@app.get("/health/full")
async def full_health_check():
    # PyInstaller-compatible import with fallback
    try:
        from services.background_preloader import background_preloader
    except ImportError:
        logger.warning("Background preloader service not available")
        background_preloader = None
    
    coordinator = await get_coordinator()
    health_status = await coordinator.check_health()
    
    # Add preloader status to health check
    if background_preloader:
        health_status["background_preload_completed"] = background_preloader.is_preload_completed
    else:
        health_status["background_preload_completed"] = False
    
    # Add MCP server prewarming status
    try:
        from services.mcp_server_prewarmer import get_mcp_prewarmer
        prewarmer = get_mcp_prewarmer()
        health_status["mcp_prewarming"] = prewarmer.prewarming_status
    except Exception as e:
        health_status["mcp_prewarming"] = {"error": str(e), "available": False}
    
    return health_status

@app.get("/health/mcp-connections")
async def mcp_connections_health_check():
    """Get detailed information about MCP server connections and aggregators"""
    try:
        from services.mcp_server_prewarmer import get_mcp_prewarmer
        from mcp_local.core.context import get_current_context
        
        context = get_current_context()
        prewarmer = get_mcp_prewarmer()
        
        # Get prewarmed server info
        prewarming_status = prewarmer.prewarming_status
        
        # Get connection manager info if available
        connection_manager_info = {}
        if hasattr(context, '_mcp_connection_manager'):
            connection_manager = context._mcp_connection_manager
            if connection_manager and hasattr(connection_manager, 'running_servers'):
                connection_manager_info = {
                    "running_servers": list(connection_manager.running_servers.keys()),
                    "running_server_count": len(connection_manager.running_servers),
                    "server_health": {
                        name: {
                            "healthy": server.is_healthy(),
                            "server_name": server.server_name,
                            "error_state": server._error,
                            "error_message": server._error_message
                        }
                        for name, server in connection_manager.running_servers.items()
                    }
                }
            else:
                connection_manager_info = {"status": "no_running_servers"}
        else:
            connection_manager_info = {"status": "no_connection_manager"}
        
        # Get reference count info
        ref_count_info = {}
        if hasattr(context, '_mcp_connection_manager_ref_count'):
            ref_count_info = {
                "current_ref_count": context._mcp_connection_manager_ref_count,
                "has_lock": hasattr(context, '_mcp_connection_manager_lock')
            }
        else:
            ref_count_info = {"status": "no_ref_count_tracking"}
        
        return {
            "status": "ok",
            "prewarming_status": prewarming_status,
            "connection_manager": connection_manager_info,
            "reference_counting": ref_count_info,
            "timestamp": time.time()
        }
        
    except Exception as e:
        return JSONResponse(status_code=503, content={
            "status": "error",
            "message": f"MCP connections health check failed: {str(e)}"
        })

@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all incoming requests with method and path"""
    logger.info(f"Request: {request.method} {request.url.path}")
    response = await call_next(request)
    return response

@app.get("/qdrant/health")
async def qdrant_health_check():
    url = os.environ.get("QDRANT_URL")
    api_key = os.environ.get("QDRANT_API_KEY")
    headers = {"api-key": api_key} if api_key else {}
    try:
        resp = requests.get(f"{url}/collections", headers=headers, timeout=5)
        resp.raise_for_status()
        return {"status": "ok", "message": "Connected to Qdrant", "collections": resp.json()}
    except Exception as e:
        return JSONResponse(status_code=503, content={"status": "error", "message": str(e)})

@app.get("/health/file-processing")
async def file_processing_health_check():
    """Check if file processing libraries (including matplotlib) are ready"""
    try:
        from services.background_preloader import background_preloader
        
        # Check if background preloading is complete
        preload_complete = background_preloader.is_preload_completed
        
        # Check if matplotlib is imported and ready
        matplotlib_ready = 'matplotlib' in sys.modules
        unstructured_ready = 'unstructured.partition.image' in sys.modules
        
        return {
            "status": "ok" if preload_complete else "loading",
            "background_preload_completed": preload_complete,
            "matplotlib_ready": matplotlib_ready,
            "unstructured_ready": unstructured_ready,
            "message": "File processing ready" if (preload_complete and matplotlib_ready) else "File processing libraries still loading"
        }
    except Exception as e:
        return JSONResponse(status_code=503, content={
            "status": "error", 
            "message": f"File processing health check failed: {str(e)}"
        })

@app.on_event("startup")
async def check_qdrant_on_startup():
    url = os.environ.get("QDRANT_URL")
    api_key = os.environ.get("QDRANT_API_KEY")
    headers = {"api-key": api_key} if api_key else {}
    try:
        resp = requests.get(f"{url}/collections", headers=headers, timeout=5)
        resp.raise_for_status()
        logger.info("Successfully connected to Qdrant at startup.")
    except Exception as e:
        logger.error(f"Failed to connect to Qdrant at startup: {e}")

app.include_router(api_router, prefix="/api/v1")

# Determine if running in a PyInstaller bundle
def is_frozen():
    return getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS')

# Function to add a directory to PATH
def add_to_path(directory):
    current_path = os.environ.get("PATH", "")
    # Prepend the new directory
    new_path = directory + os.pathsep + current_path
    if directory not in current_path.split(os.pathsep): # Check to avoid duplicate logging if already there
        os.environ["PATH"] = new_path
        logger.info(f"Prepended to PATH: {directory}. New PATH: {new_path}")
    else:
        logger.info(f"{directory} already in PATH.")

# Get the base path for resources or application root
def get_base_path():
    if is_frozen():
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        logger.info(f"get_base_path (frozen): Returning sys._MEIPASS ({sys._MEIPASS})")
        return sys._MEIPASS
    else:
        # Not bundled, running from source
        # Assuming main.py is in local-backend, and resources is ../resources
        # For dev, base_path for resources is one level up from local-backend/
        dev_base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        logger.info(f"get_base_path (dev): Returning {dev_base_path}")
        return dev_base_path

# --- PATH Setup ---
# This should be one of the first things done, especially before mcp_agent or other modules
# that might spawn subprocesses are imported or initialized.
logger.info("--- Starting PATH Setup ---")
try:
    # Log initial state FOR DEBUGGING
    logger.info(f"Initial os.getcwd(): {os.getcwd()}")
    logger.info(f"Initial sys.path: {sys.path}")
    logger.info(f"Initial os.environ['PATH']: {os.environ.get('PATH', 'Not Set')}")

    app_base_dir = get_base_path() # This is MEIPASS if frozen, or project root dir for dev
    
    # Key change: Determine the correct path for 'resources/bin' based on execution context
    if is_frozen():
        # In a frozen app (PyInstaller, then packaged by Electron):
        # sys.executable is Denker.app/Contents/Resources/local-backend-pkg/local-backend-pkg
        # We want to add Denker.app/Contents/Resources/bin to PATH (for pandoc, etc.)
        # AND we want to add the directory of sys.executable itself to PATH (for PyInstaller-generated script wrappers)
        application_dir = os.path.dirname(sys.executable) # .../local-backend-pkg
        # Path to Denker.app/Contents/Resources/bin
        resources_bin_dir_for_path = os.path.normpath(os.path.join(application_dir, '..', 'bin'))
        logger.info(f"FROZEN: Target 'resources/bin' for PATH: {resources_bin_dir_for_path}")
        logger.info(f"FROZEN: Target sys.executable directory for PATH: {application_dir}")

        # Add sys.executable's directory to PATH first
        if os.path.isdir(application_dir):
            logger.info(f"Adding to PATH: {application_dir}")
            add_to_path(application_dir)
        else:
            logger.warning(f"ALERT: sys.executable directory NOT FOUND at {application_dir}")

    else:
        # Development mode: Add local project's resources/bin to PATH
        # Assumes main.py is in local-backend, and resources/ is a sibling of local-backend
        # So, ../resources/bin from the perspective of local-backend/main.py
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) # Up two levels to denker-app root
        resources_bin_dir_for_path = os.path.join(project_root, "resources", "bin")
        logger.info(f"DEVELOPMENT: Target 'resources/bin' for PATH: {resources_bin_dir_for_path}")


    # Add the determined resources_bin_dir_for_path to PATH
    if os.path.isdir(resources_bin_dir_for_path):
        logger.info(f"Adding to PATH: {resources_bin_dir_for_path}")
        add_to_path(resources_bin_dir_for_path)

        # Optional: Check for specific tools like pandoc, using the actual path added to PATH
        # This check is mostly for debugging; get_bundled_binary_path is the main function for locating them.
        pandoc_path_check = os.path.join(resources_bin_dir_for_path, "pandoc")
        if sys.platform == "win32":
            pandoc_path_check += ".exe"
        
        if os.path.exists(pandoc_path_check):
            if os.access(pandoc_path_check, os.X_OK):
                logger.info(f"Pandoc executable confirmed at: {pandoc_path_check} (and it is executable).")
            else:
                logger.warning(f"Pandoc executable found at: {pandoc_path_check}, but it is NOT EXECUTABLE. Please run 'chmod +x {pandoc_path_check}'.")
        else:
            logger.warning(f"Pandoc executable NOT found in the directory added to PATH: {pandoc_path_check}.")
            
    else:
        logger.warning(f"ALERT: Calculated 'resources/bin' directory NOT FOUND at {resources_bin_dir_for_path}. Associated bundled binaries will not be on PATH.")


    # If frozen, also add the _MEIPASS directory itself to PATH?
    # Some libraries or subprocesses might expect to find things relative to the executable's main directory.
    # if is_frozen():
    #    logger.info(f"Frozen mode: Adding sys._MEIPASS ({sys._MEIPASS}) to PATH as well.")
    #    add_to_path(sys._MEIPASS)

    # Debug: Print relevant paths if frozen - THIS IS THE KEY DEBUG SECTION
    if is_frozen():
        logger.info("--- PyInstaller Frozen App Debug Info (Post PATH Setup) ---")
        logger.info(f"sys.executable: {sys.executable}")
        logger.info(f"sys._MEIPASS: {sys._MEIPASS}")
        try:
            meipass_contents = os.listdir(sys._MEIPASS)
            logger.info(f"Contents of sys._MEIPASS ({sys._MEIPASS}): {meipass_contents}")
            
            # REMOVED: Specific checks for resources/bin inside _MEIPASS as we now rely on Electron's packaging for this.
            # The PATH setup earlier handles adding the correct Resources/bin to the PATH.
            # frozen_resources_dir = os.path.join(sys._MEIPASS, "resources")
            # if os.path.isdir(frozen_resources_dir):
            #     logger.info(f"FROZEN: 'resources' directory found inside _MEIPASS: {frozen_resources_dir}")
            #     logger.info(f"FROZEN: Contents of _MEIPASS/resources: {os.listdir(frozen_resources_dir)}")
            #     
            #     frozen_resources_bin_check = os.path.join(frozen_resources_dir, "bin")
            #     if os.path.isdir(frozen_resources_bin_check):
            #         logger.info(f"FROZEN: 'resources/bin' directory found inside _MEIPASS: {frozen_resources_bin_check}")
            #         logger.info(f"FROZEN: Contents of _MEIPASS/resources/bin: {os.listdir(frozen_resources_bin_check)}")
            #     else:
            #         logger.warning(f"FROZEN: 'resources/bin' directory NOT found inside _MEIPASS/resources at {frozen_resources_bin_check}")
            # else:
            #     logger.warning(f"FROZEN: 'resources' directory NOT found inside _MEIPASS at {frozen_resources_dir}")
                
        except Exception as e_frozen_list: # pylint: disable=broad-except
            logger.error(f"Error listing _MEIPASS or subdirectories contents: {e_frozen_list}")
            
        logger.info(f"os.getcwd() (frozen): {os.getcwd()}")
        logger.info(f"sys.path (frozen): {sys.path}")
        logger.info(f"os.environ['PATH'] (frozen, after modifications): {os.environ.get('PATH', 'Not Set')}")
        logger.info("--- End PyInstaller Frozen App Debug Info ---")

except Exception as e_path: # pylint: disable=broad-except
    logger.error(f"CRITICAL ERROR during PATH setup: {e_path}", exc_info=True)
logger.info("--- PATH Setup Complete ---")

# Continue with other imports after PATH setup
from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Delay heavy imports to speed up startup
import logging
logger = logging.getLogger(__name__)

# Delay other heavy imports until they're actually needed - COMPLETELY LAZY LOADING
_heavy_imports_loaded = False
pypdf = None
docx = None  
pandas = None

def setup_heavy_imports():
    """Import heavy dependencies only when actually needed"""
    global _heavy_imports_loaded, pypdf, docx, pandas
    if _heavy_imports_loaded:
        return
    
    try:
        # Only import these when actually needed by document processing
        import pypdf as _pypdf
        import docx as _docx
        import pandas as _pandas
        
        pypdf = _pypdf
        docx = _docx
        pandas = _pandas
        
        # NOTE: matplotlib removed - QuickChart uses remote API, no local matplotlib needed
        # If local matplotlib is ever needed in the future, it should be imported 
        # on-demand in the specific function that needs it
        
        _heavy_imports_loaded = True
        logger.info("Heavy document processing libraries loaded on-demand")
    except ImportError as e:
        logger.warning(f"Some document processing libraries not available: {e}")

# Configure matplotlib environment BEFORE unstructured imports it
# unstructured[image,pdf] uses matplotlib internally for document processing
try:
    import tempfile
    import os
    
    # Create matplotlib cache directory
    if getattr(sys, 'frozen', False):
        mpl_cache_dir = os.path.join(os.path.expanduser("~/Library/Application Support/denker-app"), "matplotlib_cache")
    else:
        mpl_cache_dir = os.path.join(tempfile.gettempdir(), "denker_matplotlib_cache")
    
    os.makedirs(mpl_cache_dir, exist_ok=True)
    
    # Set environment variables BEFORE unstructured imports matplotlib
    os.environ["MPLCONFIGDIR"] = mpl_cache_dir
    os.environ["MPLBACKEND"] = "Agg"  # Non-interactive backend
    os.environ["MATPLOTLIB_FORCE_REBUILD"] = "0"  # Skip font cache rebuild
    
    logger.info(f"Matplotlib environment configured for unstructured: {mpl_cache_dir}")
except Exception as e:
    logger.warning(f"Could not configure matplotlib environment: {e}")
    # Continue anyway - matplotlib will use defaults

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("FastAPI app lifespan startup...")
    
    # Heavy imports are now loaded on-demand when actually needed
    # setup_heavy_imports() <- REMOVED for performance
    
    # Start background preloading of heavy dependencies (non-blocking)
    try:
        from services.background_preloader import background_preloader
        background_preloader.start_background_preload(delay_seconds=2)  # Reduced from 10 to 2 seconds for faster preloading
        logger.info("Background preloader scheduled to start in 2 seconds (non-blocking)")
    except ImportError as e:
        logger.warning(f"Background preloader not available: {e}")
    except Exception as e:
        logger.error(f"Failed to start background preloader: {e}")
    
    # Load .env file for development mode (needed for Qdrant and other local services)
    if not is_frozen():
        from dotenv import load_dotenv
        env_path = os.path.join(os.path.dirname(__file__), '.env')
        if os.path.exists(env_path):
            load_dotenv(dotenv_path=env_path)
            logger.info(f"Loaded environment variables from {env_path}")
        else:
            logger.info(f".env file not found at {env_path}, relying on system environment variables.")
    
    # Log relevant environment variables for debugging (especially Qdrant)
    logger.info(f"QDRANT_URL: {os.getenv('QDRANT_URL')}")
    logger.info(f"QDRANT_API_KEY (first 5 chars): {os.getenv('QDRANT_API_KEY')[:5] if os.getenv('QDRANT_API_KEY') else 'Not set'}")
    logger.info(f"COLLECTION_NAME: {os.getenv('COLLECTION_NAME')}")
    logger.info(f"DENKER_MEMORY_DATA_PATH: {os.getenv('DENKER_MEMORY_DATA_PATH')}")
    logger.info(f"DENKER_USER_SETTINGS_PATH: {os.getenv('DENKER_USER_SETTINGS_PATH')}")
    logger.info(f"Current working directory: {os.getcwd()}")
    
    # Set up signal handlers for graceful shutdown
    
    # Coordinator initialization is now handled by the global_coordinator module
    # which is triggered by authentication endpoints (/auth/local-login)
    # and properly handles both dev and production modes
    logger.info("Local backend services started. Coordinator initialization is deferred to frontend-driven authentication.")

    yield
    logger.info("FastAPI app lifespan shutdown...")

if __name__ == "__main__":
    logger.info(f"Starting Uvicorn server. IS_FROZEN: {is_frozen()}")
    # PyInstaller creates a temp folder and stores path in _MEIPASS
    # Uvicorn running in a frozen app needs to be told about the app object directly
    if is_frozen():
        # When frozen, 'main:app' string for app loading might not work reliably
        # due to how PyInstaller packages. Instead, pass the app object.
        # Also, ensure host and port are configurable if needed, but defaults are fine.
        # The reload=True/False is also tricky with frozen apps. Typically False.
        logger.info("Running Uvicorn directly with app object (frozen).")
        uvicorn.run(
            app,  # Use the app object directly
            host=settings.SERVER_HOST, 
            port=settings.SERVER_PORT, 
            log_level="info", # Consistent log level
            reload=False # Reloading is problematic in frozen apps
        )
    else:
        # Development mode
        logger.info("Running Uvicorn with 'main:app' (development).")
        uvicorn.run(
            "main:app", 
            host=settings.SERVER_HOST, 
            port=settings.SERVER_PORT, 
            log_level="info", # Lower log level for dev if desired, e.g., "debug"
            reload=settings.RELOAD_SERVER # Enable reload in dev
        ) 