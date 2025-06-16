#!/bin/bash
set -e

# Log environment info for debugging
echo "Starting Denker Backend"
echo "Python version: $(python --version)"
echo "Running on port: ${PORT:-8001}"

# Add CloudRun specific checks
if [ -n "$K_SERVICE" ]; then
    echo "Running in Cloud Run environment: $K_SERVICE"
    # CloudRun specific setup can go here
    export PUBLIC_URL="https://${K_SERVICE}-${K_REVISION}.run.app"
    echo "Public URL: $PUBLIC_URL"
fi

# Default to 8001 if PORT not set (for dev environments)
if [ -z "$PORT" ]; then
    export PORT=8001
fi

echo "Starting initialization..."
echo "All dependencies are pre-installed during image build"

# Set the Python path to include the current directory
export PYTHONPATH="${PYTHONPATH}:${PWD}"

# Load environment variables from .env file if it exists
if [ -f .env ]; then
  echo "Loading environment variables from .env file"
  export $(grep -v '^#' .env | xargs)
fi

# Set default POSTGRES_HOST for local Docker development if not already set
export POSTGRES_HOST="${POSTGRES_HOST:-host.docker.internal}"
export POSTGRES_PORT="${POSTGRES_PORT:-5432}"

echo "Using PostgreSQL connection: ${POSTGRES_HOST}:${POSTGRES_PORT}"

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

# Skip starting MCP servers as they'll be handled by the application if needed

# Start the main application
echo "Starting main application..."
# Check APP_ENV environment variable
if [ "${APP_ENV}" = "production" ]; then
  echo "Running in production mode (no reload)"
  exec python -m uvicorn main:app --host 0.0.0.0 --port $PORT --log-level debug
else
  echo "Running in development mode (with reload)"
  exec python -m uvicorn main:app --host 0.0.0.0 --port $PORT --reload --log-level debug
fi 