#!/bin/bash
# Setup Qdrant for development with file processing support

set -e  # Exit on error

echo "Setting up Qdrant for development with file processing support..."

# Check if Qdrant server is running
if ! curl -s "http://localhost:6333/collections" > /dev/null; then
    echo "ERROR: Qdrant server is not running at http://localhost:6333"
    echo "Please start Qdrant first with:"
    echo "  docker run -d -p 6333:6333 -p 6334:6334 -v ./qdrant_data:/qdrant/storage qdrant/qdrant"
    exit 1
fi

# Install dependencies if needed
if ! python3 -c "import langchain_community, qdrant_client" 2>/dev/null; then
    echo "Installing dependencies..."
    bash scripts/install_rag_dependencies.sh
fi

# Initialize Qdrant collection
echo "Creating Qdrant collection for file storage..."
python3 scripts/setup_qdrant.py --url http://localhost:6333 --collection denker_embeddings

# Load sample data
echo "Loading sample data..."
python3 scripts/load_qdrant_data.py --url http://localhost:6333 --collection denker_embeddings --sample

echo ""
echo "Qdrant setup complete! You can now:"
echo "1. Upload files through the Denker UI"
echo "2. Test file processing with:"
echo "   python3 scripts/process_file_to_qdrant.py --file <path_to_file> --url http://localhost:6333"
echo ""
echo "The RAG agent in your Denker chat will now be able to reference your uploaded files." 