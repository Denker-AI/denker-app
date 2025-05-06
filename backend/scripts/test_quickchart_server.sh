#!/bin/bash
# Test if the QuickChart MCP Server is working correctly

echo "Testing QuickChart MCP Server..."

# First check if quickchart-mcp-server is installed
if ! npm list -g | grep -q "@gongrzhe/quickchart-mcp-server"; then
  echo "ERROR: quickchart-mcp-server is not installed globally"
  echo "Would you like to install it? (y/N)"
  read answer
  if [ "$answer" == "y" ] || [ "$answer" == "Y" ]; then
    npm install -g @gongrzhe/quickchart-mcp-server
  else
    echo "Installation cancelled. Exiting."
    exit 1
  fi
fi

echo "QuickChart MCP Server is installed."

# Check the directory structure
echo "Checking directory structure..."
DIR="/usr/local/lib/node_modules/@gongrzhe/quickchart-mcp-server"

if [ -d "$DIR" ]; then
  echo "Directory exists: $DIR"
  echo "Contents:"
  ls -la "$DIR"
  
  # Check if build directory exists
  if [ -d "$DIR/build" ]; then
    echo "Build directory exists."
    echo "Contents of build directory:"
    ls -la "$DIR/build"
    
    # Check if the index.js file is executable
    if [ -f "$DIR/build/index.js" ]; then
      echo "index.js exists. Testing execution..."
      
      # Try running the server with a timeout
      echo "Running QuickChart MCP Server (will timeout after 5 seconds)..."
      timeout 5 node "$DIR/build/index.js" || echo "Server started correctly (timeout as expected)"
    else
      echo "ERROR: index.js not found in build directory."
      exit 1
    fi
  else
    echo "ERROR: build directory not found."
    exit 1
  fi
else
  echo "ERROR: $DIR does not exist. QuickChart MCP Server is not installed correctly."
  exit 1
fi

echo ""
echo "QuickChart MCP Server test complete."
echo "If the server returned no errors, it should be working correctly."
echo "You may need to update the mcp_agent.config.yaml to use:"
echo "  command: \"node\""
echo "  args: [\"$DIR/build/index.js\"]"
echo ""
echo "Also check that the server is properly started when the MCP agent is initialized." 