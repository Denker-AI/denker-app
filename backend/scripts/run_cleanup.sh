#!/bin/bash

# Load environment variables from .env file
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Run the cleanup script
# Default to 30 days if no argument is provided
DAYS=${1:-30}
python cleanup_deleted_files.py $DAYS 