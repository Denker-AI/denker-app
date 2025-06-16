#!/usr/bin/env python3
"""
PyInstaller runtime hook for Node.js path configuration.
This ensures that Node.js can be found when the MCP servers are started.
"""

import os
import sys
import subprocess
from pathlib import Path

def setup_node_environment():
    """Setup Node.js environment for MCP servers running in Electron context."""
    
    # In Electron apps, Node.js should be available through the app's resources
    app_path = Path(sys.executable).parent.parent.parent  # Go up from local-backend-pkg
    
    # Common Node.js locations in Electron apps
    possible_node_paths = [
        app_path / "Frameworks" / "Electron Framework.framework" / "Versions" / "A" / "Resources" / "node",
        app_path / "Resources" / "app.asar.unpacked" / "node_modules" / ".bin" / "node",
        Path("/usr/local/bin/node"),  # System Node.js
        Path("/opt/homebrew/bin/node"),  # Homebrew on Apple Silicon
    ]
    
    # Check if node is already in PATH
    try:
        subprocess.run(["node", "--version"], 
                      stdout=subprocess.DEVNULL, 
                      stderr=subprocess.DEVNULL, 
                      check=True)
        print("[Runtime Hook] Node.js already available in PATH", file=sys.stderr)
        return
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    
    # Try to find and set Node.js path
    for node_path in possible_node_paths:
        if node_path.exists():
            node_dir = str(node_path.parent)
            current_path = os.environ.get("PATH", "")
            if node_dir not in current_path:
                os.environ["PATH"] = f"{node_dir}:{current_path}"
                print(f"[Runtime Hook] Added Node.js path: {node_dir}", file=sys.stderr)
            return
    
    print("[Runtime Hook] Warning: Node.js not found in expected locations", file=sys.stderr)
    print(f"[Runtime Hook] App path: {app_path}", file=sys.stderr)
    print(f"[Runtime Hook] Current PATH: {os.environ.get('PATH', 'Not set')}", file=sys.stderr)

# Run the setup when the hook is loaded
if __name__ == "__main__":
    setup_node_environment()
else:
    # This runs when imported as a hook
    setup_node_environment() 