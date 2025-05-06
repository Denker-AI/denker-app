#!/bin/bash
set -e

echo "Starting initialization..."
echo "All dependencies are pre-installed during image build"

# Set the Python path to include the current directory
export PYTHONPATH="${PYTHONPATH}:${PWD}"

# Load environment variables from .env file if it exists
if [ -f .env ]; then
  echo "Loading environment variables from .env file"
  export $(grep -v '^#' .env | xargs)
fi

# Force PostgreSQL host to host.docker.internal for SSH tunnels
export POSTGRES_HOST="host.docker.internal"
export POSTGRES_PORT=${POSTGRES_PORT:-"5432"}

# Determine Qdrant connection
USE_LOCAL_QDRANT_LOWER=$(echo "${USE_LOCAL_QDRANT:-false}" | tr '[:upper:]' '[:lower:]')
if [ "${USE_LOCAL_QDRANT_LOWER}" = "true" ]; then
  # Force using local Qdrant container
  export QDRANT_URL="http://qdrant:6333"
  echo "Forcing use of local Qdrant container at ${QDRANT_URL}"
else
  # Check if using local Qdrant container
  if [[ "$QDRANT_URL" == http://qdrant* ]]; then
    echo "Using local Qdrant container at ${QDRANT_URL}"
  else
    # Use SSH tunnel for remote Qdrant
    export QDRANT_URL="http://host.docker.internal:6333"
    echo "Using remote Qdrant via SSH tunnel at ${QDRANT_URL}"
  fi
fi

echo "Using PostgreSQL connection: ${POSTGRES_HOST}:${POSTGRES_PORT}"
echo "Using Qdrant connection: ${QDRANT_URL}"

# Check PostgreSQL connectivity
echo "Checking PostgreSQL connectivity to ${POSTGRES_HOST}:${POSTGRES_PORT}..."
echo "Using database name: ${POSTGRES_DB}"
python -c "
import psycopg2
import time
import sys

# Connection parameters
params = {
    'host': '$POSTGRES_HOST',
    'port': $POSTGRES_PORT,
    'user': '$POSTGRES_USER',
    'password': '$POSTGRES_PASSWORD',
    'dbname': '$POSTGRES_DB'
}

print(f'Connection parameters: host={params[\"host\"]}, port={params[\"port\"]}, user={params[\"user\"]}, dbname={params[\"dbname\"]}')

# Try to connect with retries
max_retries = 5
retry_count = 0

while retry_count < max_retries:
    try:
        print(f'Attempt {retry_count + 1}: Connecting to PostgreSQL at {params[\"host\"]}:{params[\"port\"]}...')
        conn = psycopg2.connect(**params)
        cur = conn.cursor()
        cur.execute('SELECT version();')
        db_version = cur.fetchone()
        print(f'PostgreSQL database version: {db_version[0]}')
        
        # List available databases
        cur.execute(\"\"\"
            SELECT datname FROM pg_database
            WHERE datistemplate = false;
        \"\"\")
        databases = cur.fetchall()
        print('Available databases:')
        for db in databases:
            print(f'  - {db[0]}')
            
        cur.close()
        conn.close()
        print('Successfully connected to PostgreSQL!')
        sys.exit(0)
    except Exception as e:
        print(f'Error connecting to PostgreSQL: {e}')
        retry_count += 1
        if retry_count < max_retries:
            print(f'Retrying in 2 seconds...')
            time.sleep(2)
        else:
            print('Failed to connect to PostgreSQL after multiple attempts.')
            print('If you are using Google Cloud SQL:')
            print('1. Make sure the SSH tunnel is active')
            print('2. Verify your database name, username, and password are correct')
            print('3. Check that your database exists and the user has access')
            print('Database connection will be attempted again when the application starts')
"

echo "Database migrations will be handled by the application at startup"

# Convert QDRANT_ENABLED to lowercase for comparison
QDRANT_ENABLED_LOWER=$(echo "${QDRANT_ENABLED:-false}" | tr '[:upper:]' '[:lower:]')
echo "Qdrant enabled setting: ${QDRANT_ENABLED} (converted to ${QDRANT_ENABLED_LOWER} for check)"

# Check for Qdrant connection
if [ "${QDRANT_ENABLED_LOWER}" = "true" ]; then
  echo "Checking Qdrant connection..."
  
  # Wait longer for local Qdrant to be ready
  if [[ "$QDRANT_URL" == http://qdrant* ]]; then
    echo "Waiting for local Qdrant container to start up..."
    sleep 5
  fi
  
  # Check Qdrant API connectivity using curl with verbose output
  MAX_RETRIES=5
  RETRY_COUNT=0

  while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    echo "Attempt $((RETRY_COUNT+1))/$MAX_RETRIES: Connecting to Qdrant at ${QDRANT_URL}..."
    
    # Try to verify the connection using curl
    echo "Testing basic connectivity to Qdrant host..."
    curl -v --max-time 5 "${QDRANT_URL}" 2>&1 | grep -E '(Connected to|Failed to|Trying)'
    
    echo "Attempting to query collections endpoint..."
    if curl -s --max-time 5 "${QDRANT_URL}/collections" > /dev/null 2>&1; then
      echo "Successfully connected to Qdrant at ${QDRANT_URL}"
      
      # Check if the collection already exists
      COLLECTION_NAME=${QDRANT_COLLECTION_NAME:-"denker_embeddings"}
      
      echo "Checking for collection: ${COLLECTION_NAME}..."
      COLLECTIONS_RESPONSE=$(curl -s "${QDRANT_URL}/collections")
      
      if echo "${COLLECTIONS_RESPONSE}" | grep -q "$COLLECTION_NAME"; then
        echo "Collection ${COLLECTION_NAME} already exists in Qdrant."
      else
        echo "Creating collection ${COLLECTION_NAME} in Qdrant..."
        CREATION_RESPONSE=$(curl -X PUT "${QDRANT_URL}/collections/${COLLECTION_NAME}" \
          -H 'Content-Type: application/json' \
          -d "{
            \"vectors\": {
              \"size\": ${QDRANT_VECTOR_SIZE:-768},
              \"distance\": \"Cosine\"
            }
          }")
        echo "Collection creation response: ${CREATION_RESPONSE}"
      fi
      
      break
    else
      CURL_EXIT_CODE=$?
      echo "Qdrant not accessible yet at ${QDRANT_URL}. Curl exit code: ${CURL_EXIT_CODE}"
      RETRY_COUNT=$((RETRY_COUNT+1))
      if [ $RETRY_COUNT -lt $MAX_RETRIES ]; then
        echo "Retrying in 2 seconds..."
        sleep 2
      fi
    fi
  done

  if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    echo "WARNING: Could not connect to Qdrant after ${MAX_RETRIES} attempts."
    if [[ "$QDRANT_URL" == http://host.docker.internal* ]]; then
      echo "If you are using Google Cloud Qdrant:"
      echo "1. Make sure the SSH tunnel is active (check with: lsof -i :6333)"
      echo "2. Verify the Qdrant URL is correct: ${QDRANT_URL}"
      echo "3. Check if you can connect directly from the host: curl -v ${QDRANT_URL}/collections"
    else
      echo "If you are using local Qdrant container:"
      echo "1. Make sure the Qdrant container is running"
      echo "2. Check container logs: docker logs qdrant"
    fi
    echo "Will continue anyway, but RAG functionality may not work properly."
  fi
else
  echo "Qdrant is disabled (QDRANT_ENABLED=${QDRANT_ENABLED}). Skipping Qdrant connection checks."
fi

# Skip starting MCP servers as they'll be handled by the application if needed

# Start the main application
echo "Starting main application..."
# Check APP_ENV environment variable
if [ "${APP_ENV}" = "production" ]; then
  echo "Running in production mode (no reload)"
  exec uvicorn main:app --host 0.0.0.0 --port 8001
else
  echo "Running in development mode (with reload)"
  exec uvicorn main:app --host 0.0.0.0 --port 8001 --reload
fi 