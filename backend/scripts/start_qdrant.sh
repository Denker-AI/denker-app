#!/bin/bash

# Script to be executed on Qdrant VM to install and start Qdrant

echo "Starting Qdrant installation/restart..."

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "Docker not found, installing..."
    sudo apt-get update
    sudo apt-get install -y apt-transport-https ca-certificates curl gnupg lsb-release
    sudo mkdir -p /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/debian/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker-archive-keyring.gpg
    echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/debian $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
    sudo apt-get update
    sudo apt-get install -y docker-ce docker-ce-cli containerd.io
    sudo systemctl enable docker
    sudo systemctl start docker
else
    echo "Docker is already installed"
fi

# Stop and remove any existing Qdrant container
echo "Stopping any existing Qdrant container..."
sudo docker stop qdrant 2>/dev/null || true
sudo docker rm qdrant 2>/dev/null || true

# Create data directory
echo "Creating data directory..."
sudo mkdir -p /qdrant_data

# Start Qdrant container
echo "Starting Qdrant container..."
sudo docker run -d --name qdrant \
  -p 6333:6333 -p 6334:6334 \
  -v /qdrant_data:/qdrant/storage \
  qdrant/qdrant

# Check if container is running
echo "Checking if Qdrant container is running..."
if sudo docker ps | grep -q qdrant; then
    echo "Qdrant container is running"
    echo "Container details:"
    sudo docker ps | grep qdrant
else
    echo "Failed to start Qdrant container"
    echo "Docker logs:"
    sudo docker logs qdrant
fi

# Test Qdrant API
echo "Testing Qdrant API..."
curl -v localhost:6333/collections || echo "Failed to connect to Qdrant API"

echo "Qdrant setup complete" 