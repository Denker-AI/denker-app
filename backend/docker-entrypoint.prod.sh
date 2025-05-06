#!/bin/bash
set -e

echo "Starting initialization..."
echo "All dependencies are pre-installed during image build"

# Set the Python path to include the current directory
export PYTHONPATH="${PYTHONPATH}:${PWD}"

# Environment variables (like POSTGRES_*, QDRANT_*, etc.)
# are expected to be injected by the Cloud Run environment
# No need to load .env file in production

# Verify necessary variables are set (Optional but recommended)
: "${POSTGRES_HOST:?Need to set POSTGRES_HOST}"
: "${POSTGRES_PORT:?Need to set POSTGRES_PORT}"
: "${POSTGRES_USER:?Need to set POSTGRES_USER}"
: "${POSTGRES_PASSWORD:?Need to set POSTGRES_PASSWORD}"
: "${POSTGRES_DB:?Need to set POSTGRES_DB}"
: "${QDRANT_ENABLED:?Need to set QDRANT_ENABLED}"

QDRANT_ENABLED_LOWER=$(echo "${QDRANT_ENABLED:-false}" | tr '[:upper:]' '[:lower:]')

if [ "${QDRANT_ENABLED_LOWER}" = "true" ]; then
  : "${QDRANT_URL:?Need to set QDRANT_URL}"
  # QDRANT_API_KEY will be used by the client library, not explicitly checked here
  echo "Using Qdrant connection: ${QDRANT_URL}"
else
  echo "Qdrant is disabled (QDRANT_ENABLED=${QDRANT_ENABLED})."
fi

echo "Using PostgreSQL connection: ${POSTGRES_HOST}:${POSTGRES_PORT}, Database: ${POSTGRES_DB}"


# Check PostgreSQL connectivity (simplified for production)
echo "Checking PostgreSQL connectivity to ${POSTGRES_HOST}:${POSTGRES_PORT}..."
python -c "
import psycopg2
import time
import sys
import os

params = {
    'host': os.getenv('POSTGRES_HOST'),
    'port': os.getenv('POSTGRES_PORT'),
    'user': os.getenv('POSTGRES_USER'),
    'password': os.getenv('POSTGRES_PASSWORD'),
    'dbname': os.getenv('POSTGRES_DB')
}

max_retries = 5
for attempt in range(max_retries):
    try:
        print(f'Attempt {attempt + 1}: Connecting to PostgreSQL...')
        conn = psycopg2.connect(**params)
        conn.close()
        print('Successfully connected to PostgreSQL!')
        sys.exit(0)
    except Exception as e:
        print(f'Error connecting to PostgreSQL: {e}')
        if attempt < max_retries - 1:
            print('Retrying in 5 seconds...')
            time.sleep(5)
        else:
            print('Failed to connect to PostgreSQL after multiple attempts.')
            # Decide if you want to exit or let the app try later
            # sys.exit(1) # Exit if connection is critical at startup

print('Continuing startup despite PostgreSQL connection issue...')
" # Removed the database listing part for brevity

echo "Database migrations will be handled by the application at startup"


# Check for Qdrant connection (simplified for production)
if [ "${QDRANT_ENABLED_LOWER}" = "true" ]; then
  echo "Checking Qdrant connection to ${QDRANT_URL}..."
  MAX_RETRIES=5
  RETRY_COUNT=0
  while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    # Use a simple endpoint like /readyz if available, or /collections
    if curl -sf --max-time 5 "${QDRANT_URL}/readyz" > /dev/null 2>&1 || curl -sf --max-time 5 "${QDRANT_URL}/collections" > /dev/null 2>&1; then
      echo "Successfully connected to Qdrant API at ${QDRANT_URL}"
      # NOTE: Collection creation logic removed - should be handled by app logic or manually?
      # Consider if the app should create the collection if it doesn't exist.
      break
    else
      CURL_EXIT_CODE=$?
      echo "Qdrant not accessible yet at ${QDRANT_URL}. Curl exit code: ${CURL_EXIT_CODE}"
      RETRY_COUNT=$((RETRY_COUNT+1))
      if [ $RETRY_COUNT -lt $MAX_RETRIES ]; then
        echo "Retrying in 5 seconds..."
        sleep 5
      fi
    fi
  done
  if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    echo "WARNING: Could not connect to Qdrant API after ${MAX_RETRIES} attempts."
    echo "Please check the QDRANT_URL and ensure the Qdrant cluster is healthy."
    # Decide if you want to exit or let the app try later
    # exit 1 # Exit if connection is critical
  fi
fi

# Start the main application (removed --reload)
echo "Starting main application (prod)..."
exec uvicorn main:app --host 0.0.0.0 --port 8001 