# Setting up Auth0 for Denker App

Based on the code analysis, here are the configuration variables needed for both frontend and backend.

## Frontend Auth0 Configuration
Create a file named `.env` in the `frontend` directory with these variables:

```
# Auth0 Configuration
VITE_AUTH0_DOMAIN=your-auth0-domain.auth0.com
VITE_AUTH0_CLIENT_ID=your-auth0-client-id
VITE_AUTH0_AUDIENCE=your-auth0-audience-url

# API Configuration
VITE_API_URL=http://localhost:8001/api/v1
VITE_WS_URL=ws://localhost:8001

# Environment
VITE_NODE_ENV=development
```

## Backend Auth0 Configuration
Create a file named `.env` in the `backend` directory with these variables:

```
# Application settings
DEBUG=1
LOG_LEVEL=DEBUG

# Auth0 settings
AUTH0_DOMAIN=your-auth0-domain.auth0.com
AUTH0_API_AUDIENCE=your-auth0-audience-url

# Database settings (adjust as needed)
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=denker

# Google Cloud settings (if using)
VERTEX_AI_PROJECT=your-vertex-ai-project
VERTEX_AI_PROJECT_ID=your-vertex-ai-project-id
VERTEX_AI_LOCATION=europe-west4
GCS_BUCKET_NAME=your-gcs-bucket
GCS_ENABLED=true

# Anthropic settings (if using)
ANTHROPIC_API_KEY=your-anthropic-api-key
ANTHROPIC_MODEL=claude-3-7-sonnet-20250219
```

## Getting Auth0 Variables

To get the required Auth0 variables:

1. **Create an Auth0 account** if you don't have one: https://auth0.com/

2. **Create a new application in Auth0**:
   - Go to the Auth0 dashboard
   - Navigate to "Applications" > "Create Application"
   - Select "Single Page Application" for the frontend
   - Give it a name like "Denker App"

3. **Configure the application**:
   - In the application settings, add these URLs to "Allowed Callback URLs":
     - `http://localhost:5173/callback` (for development)
     - `http://localhost/callback` (for Electron app)
   - Add these URLs to "Allowed Logout URLs":
     - `http://localhost:5173`
     - `http://localhost`
   - Add these URLs to "Allowed Web Origins":
     - `http://localhost:5173`
     - `http://localhost`

4. **Get your Auth0 variables**:
   - `VITE_AUTH0_DOMAIN` / `AUTH0_DOMAIN`: Find this in your Auth0 application settings (e.g., `dev-abc123.us.auth0.com`)
   - `VITE_AUTH0_CLIENT_ID`: Find this in your Auth0 application settings
   - `VITE_AUTH0_AUDIENCE` / `AUTH0_API_AUDIENCE`: Create an API in Auth0 dashboard under "APIs" > "Create API". The audience is the API identifier you set.

5. **Insert these values** into your `.env` files as shown above. 