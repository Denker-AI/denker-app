#!/bin/bash
# Development Environment Setup for Consistent Workspace

# Set environment variables for development
export DENKER_MEMORY_DATA_PATH="$HOME/Library/Application Support/denker-app/memory_data"

# Create the directories if they don't exist
mkdir -p "$DENKER_MEMORY_DATA_PATH"

# Confirmation
echo "Environment variables set:"
echo "   DENKER_MEMORY_DATA_PATH=$DENKER_MEMORY_DATA_PATH"

# Migrate existing charts from temp workspace to production workspace
TEMP_WORKSPACE="/tmp/denker_workspace/default"
PROD_WORKSPACE="$HOME/Library/Application Support/denker-app/workspace/default"

if [ -d "$TEMP_WORKSPACE" ] && [ "$(ls -A $TEMP_WORKSPACE)" ]; then
    echo ""
    echo "🔄 Migrating files from temp workspace to production workspace..."
    cp -r "$TEMP_WORKSPACE"/* "$PROD_WORKSPACE/"
    echo "   Migrated $(ls -1 "$TEMP_WORKSPACE" | wc -l) files"
    echo "   Files now available at: $PROD_WORKSPACE"
fi

echo ""
echo "🚀 To use this environment, run:"
echo "   source set_dev_environment.sh"
echo "   # Then start your development servers" 