#!/bin/bash
# This script initializes Qdrant with a collection and sample data from within a Docker container

set -e  # Exit on error

echo "Initializing Qdrant for Docker environment..."

# Make sure Qdrant is accessible
QDRANT_URL="http://host.docker.internal:6333"
MAX_RETRIES=5
RETRY_DELAY=5

echo "Checking Qdrant connection at $QDRANT_URL..."
retry_count=0
while [ $retry_count -lt $MAX_RETRIES ]; do
    if curl -s "$QDRANT_URL/collections" > /dev/null; then
        echo "Successfully connected to Qdrant"
        break
    else
        retry_count=$((retry_count+1))
        if [ $retry_count -eq $MAX_RETRIES ]; then
            echo "ERROR: Could not connect to Qdrant after $MAX_RETRIES attempts"
            echo "Please make sure Qdrant is running at $QDRANT_URL"
            exit 1
        fi
        echo "Retry $retry_count/$MAX_RETRIES - Waiting ${RETRY_DELAY}s before retrying..."
        sleep $RETRY_DELAY
    fi
done

# Create a collection for vector storage
COLLECTION_NAME="denker_embeddings"
VECTOR_SIZE=768  # Use 768 for BGE embedding model

echo "Creating Qdrant collection '$COLLECTION_NAME'..."
curl -X PUT "$QDRANT_URL/collections/$COLLECTION_NAME" \
     -H 'Content-Type: application/json' \
     -d "{
         \"vectors\": {
           \"size\": $VECTOR_SIZE,
           \"distance\": \"Cosine\"
         }
     }"

echo -e "\nCollection created successfully!"

# Add some sample data with fake embeddings
echo "Loading sample data..."
curl -X PUT "$QDRANT_URL/collections/$COLLECTION_NAME/points" \
     -H 'Content-Type: application/json' \
     -d '{
         "points": [
             {
                 "id": "sample1",
                 "vector": '"$(python -c 'import json,random; print(json.dumps([random.random() for _ in range('$VECTOR_SIZE')]))')"',
                 "payload": {
                     "text": "Sample text for testing the RAG system",
                     "metadata": {
                         "source": "sample_data",
                         "source_type": "system"
                     }
                 }
             },
             {
                 "id": "sample2",
                 "vector": '"$(python -c 'import json,random; print(json.dumps([random.random() for _ in range('$VECTOR_SIZE')]))')"',
                 "payload": {
                     "text": "Vector databases are optimized for storing and searching embeddings",
                     "metadata": {
                         "source": "sample_data",
                         "source_type": "system"
                     }
                 }
             }
         ]
     }'

echo -e "\nSample data loaded successfully!"
echo -e "\nQdrant initialization complete!" 