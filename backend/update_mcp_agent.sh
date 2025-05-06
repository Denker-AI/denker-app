#!/bin/bash
set -e

echo "Updating mcp-agent in Docker..."

# Navigate to the backend directory
cd "$(dirname "$0")"

# Stop and remove existing containers
echo "Stopping existing containers..."
docker-compose -f docker-compose.dev.yml down

# Rebuild the backend image with no-cache to ensure the latest mcp-agent is installed
echo "Rebuilding backend image with latest mcp-agent..."
docker-compose -f docker-compose.dev.yml build --no-cache backend

# Start the containers
echo "Starting containers with updated mcp-agent..."
docker-compose -f docker-compose.dev.yml up -d

echo "Update complete. Containers are running with the latest mcp-agent."
echo "Check logs with: docker-compose -f docker-compose.dev.yml logs -f backend" 