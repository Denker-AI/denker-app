#!/bin/bash
# Script to test health of all MCP servers

# Set script directory path
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
BACKEND_DIR="$(dirname "$SCRIPT_DIR")"

echo "Running MCP server health checks..."
echo "Backend directory: $BACKEND_DIR"

# Activate virtual environment if it exists
if [ -d "$BACKEND_DIR/venv" ]; then
  echo "Activating virtual environment..."
  source "$BACKEND_DIR/venv/bin/activate"
fi

# Run the health check script
python "$SCRIPT_DIR/test_server_health.py"

# Store the exit status
EXIT_STATUS=$?

# Deactivate virtual environment if activated
if [ -n "$VIRTUAL_ENV" ]; then
  deactivate
fi

# Exit with the same status as the Python script
echo "Health check completed with status: $EXIT_STATUS"
exit $EXIT_STATUS 