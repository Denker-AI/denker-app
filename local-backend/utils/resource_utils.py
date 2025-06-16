import sys
import os
import shutil # For shutil.which
import logging

logger = logging.getLogger(__name__)

def get_bundled_binary_path(binary_name: str) -> str:
    """
    Locates a binary (like pandoc, pdftotext) within the bundled
    application's resources.
    Falls back to system PATH if not found bundled (for dev or if bundling failed).
    """
    # Ensure correct binary name for Windows
    if sys.platform == "win32" and not binary_name.endswith(".exe"):
        binary_name_platform = binary_name + ".exe"
    else:
        binary_name_platform = binary_name

    if getattr(sys, 'frozen', False):  # Running as a bundled exe (PyInstaller)
        # Path to the directory where the main executable is (e.g., dist/main_onefile/ or dist/main_onedir/)
        application_path = os.path.dirname(sys.executable)
        # When packaged by Electron, the PyInstaller output (e.g., local-backend-pkg dir)
        # is placed in the resources directory. The separate 'bin' folder (with pandoc etc.)
        # is also in the resources directory, as a sibling to 'local-backend-pkg'.
        # So, from the executable inside 'local-backend-pkg', we go up one level to resources,
        # then into 'bin'.
        bundled_bin_path = os.path.join(application_path, '..', 'bin', binary_name_platform)
        # Normalize the path to resolve ".."
        bundled_bin_path = os.path.normpath(bundled_bin_path)
        
        logger.info(f"Packaged app: Looking for '{binary_name_platform}' at '{bundled_bin_path}'")
        if os.path.exists(bundled_bin_path) and os.access(bundled_bin_path, os.X_OK):
            return bundled_bin_path
        else:
            print(f"WARNING: Bundled binary '{binary_name_platform}' not found or not executable at '{bundled_bin_path}'. Attempting system PATH.")
            system_path = shutil.which(binary_name) # Use original name for shutil.which
            if system_path:
                print(f"Found '{binary_name}' on system PATH: {system_path}")
                return system_path
            else:
                print(f"ERROR: '{binary_name}' not found bundled or on system PATH.")
                return binary_name # Fallback to name, relying on subprocess to fail
    else:  # Running as a .py script (development mode)
        print(f"Development mode: Attempting to use '{binary_name}' from system PATH.")
        system_path = shutil.which(binary_name)
        if system_path:
            return system_path
        print(f"WARNING: '{binary_name}' not found on system PATH during development. You may need to install it.")
        return binary_name # Fallback to name 