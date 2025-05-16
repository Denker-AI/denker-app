# Dependency Management

This document explains how dependencies are managed in the backend service Docker container.

## Overview

Previously, dependencies were installed in two places:
1. Basic dependencies in the Dockerfile
2. Additional dependencies at runtime in the docker-entrypoint.sh script

This led to compatibility issues and made it hard to ensure consistent environments.

## New Approach

Now, all dependencies are:
1. Specified in `requirements.txt` with fixed versions
2. Installed during Docker image build time
3. No dependencies are installed at runtime

This ensures:
- Consistent environment every time
- No runtime failures due to dependency issues
- Better control over package versions

## Rebuilding the Docker Image

To rebuild the Docker image with the updated dependencies:

```bash
# Navigate to the backend directory
cd backend

# Rebuild the Docker image
docker compose -f docker-compose.dev.yml build backend

# Restart the backend service
docker compose -f docker-compose.dev.yml up -d backend
```

## Updating Dependencies

If you need to add or update dependencies:

1. Update the `requirements.txt` file in the backend directory
2. Rebuild the Docker image as shown above

Do NOT manually install packages at runtime inside the container, as they will be lost when the container restarts.

## Current Dependencies

The current dependencies include:
- Core FastAPI and database dependencies
- Google Cloud dependencies with specific versions for compatibility
- LangChain and RAG-related dependencies
- Vertex AI dependencies

All these are specified in the `requirements.txt` file with pinned versions to ensure consistent behavior. 