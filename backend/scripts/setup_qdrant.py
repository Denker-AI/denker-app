#!/usr/bin/env python3
"""
Setup script for initializing a Qdrant collection for RAG.
This creates the collection and configures it for use with the MCP server.
"""

import os
import sys
import logging
import argparse
from qdrant_client import QdrantClient
from qdrant_client.http import models as rest
from qdrant_client.http.exceptions import UnexpectedResponse

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def create_collection(
    client: QdrantClient,
    collection_name: str,
    vector_size: int = 1536,  # Default size for OpenAI embeddings, adjust for your embedding model
):
    """Create a collection in Qdrant with the specified parameters."""
    try:
        # Check if collection exists
        collections = client.get_collections().collections
        collection_names = [collection.name for collection in collections]
        
        if collection_name in collection_names:
            logger.info(f"Collection '{collection_name}' already exists")
            return True
        
        # Create the collection
        client.create_collection(
            collection_name=collection_name,
            vectors_config=rest.VectorParams(
                size=vector_size,
                distance=rest.Distance.COSINE,
            ),
            # Optional: Set up payload indexing for efficient filtering
            optimizers_config=rest.OptimizersConfigDiff(
                indexing_threshold=0,  # Index right away
            ),
            # Set up payload schema
            on_disk_payload=True,  # Store payload on disk to save memory
        )
        
        # Create payload indexes for efficient filtering
        client.create_payload_index(
            collection_name=collection_name,
            field_name="metadata.timestamp",
            field_schema=rest.PayloadSchemaType.DATE,
        )
        
        client.create_payload_index(
            collection_name=collection_name,
            field_name="metadata.source",
            field_schema=rest.PayloadSchemaType.KEYWORD,
        )
        
        client.create_payload_index(
            collection_name=collection_name,
            field_name="metadata.category",
            field_schema=rest.PayloadSchemaType.KEYWORD,
        )
        
        logger.info(f"Collection '{collection_name}' created successfully")
        return True
    
    except UnexpectedResponse as e:
        logger.error(f"Error while creating collection: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Set up a Qdrant collection for RAG")
    parser.add_argument("--url", default=os.environ.get("QDRANT_URL", "http://localhost:6333"),
                        help="Qdrant server URL")
    parser.add_argument("--collection", default=os.environ.get("COLLECTION_NAME", "denker_embeddings"),
                        help="Collection name to create")
    parser.add_argument("--vector-size", type=int, default=1536, 
                        help="Vector size for embeddings (default: 1536 for OpenAI embeddings)")
    
    args = parser.parse_args()
    
    logger.info(f"Connecting to Qdrant at {args.url}")
    client = QdrantClient(url=args.url)
    
    logger.info(f"Setting up collection '{args.collection}'")
    success = create_collection(
        client=client,
        collection_name=args.collection,
        vector_size=args.vector_size,
    )
    
    if success:
        logger.info("Setup completed successfully")
        return 0
    else:
        logger.error("Setup failed")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 