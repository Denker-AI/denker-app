#!/bin/bash

# Wait for Qdrant to be ready
echo "Waiting for Qdrant to start..."
max_retries=30
retry_count=0

while [ $retry_count -lt $max_retries ]; do
  echo "Attempt $((retry_count+1))/$max_retries: Checking if Qdrant is ready..."
  if curl -s http://qdrant:6333/collections > /dev/null; then
    echo "✅ Qdrant is ready!"
    break
  else
    echo "⏳ Qdrant not ready yet, waiting..."
    sleep 2
    retry_count=$((retry_count+1))
  fi
done

if [ $retry_count -eq $max_retries ]; then
  echo "❌ Failed to connect to Qdrant after $max_retries attempts"
  exit 1
fi

# Check if collection exists
COLLECTION_NAME=${QDRANT_COLLECTION_NAME:-"denker_embeddings"}
VECTOR_SIZE=${QDRANT_VECTOR_SIZE:-768}

echo "Checking if collection '$COLLECTION_NAME' exists..."
if curl -s http://qdrant:6333/collections/$COLLECTION_NAME > /dev/null; then
  echo "✅ Collection '$COLLECTION_NAME' already exists"
else
  echo "🔧 Creating collection '$COLLECTION_NAME'..."
  
  # Create the collection
  curl -X PUT "http://qdrant:6333/collections/$COLLECTION_NAME" \
    -H 'Content-Type: application/json' \
    -d "{
      \"vectors\": {
        \"size\": $VECTOR_SIZE,
        \"distance\": \"Cosine\"
      }
    }"
    
  if [ $? -eq 0 ]; then
    echo "✅ Collection created successfully"
  else
    echo "❌ Failed to create collection"
    exit 1
  fi
fi

echo "✅ Qdrant initialization complete!" 