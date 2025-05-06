#!/usr/bin/env python3
"""
Script to load sample data into Qdrant for Retrieval-Augmented Generation.
"""

import os
import sys
import logging
import argparse
import json
from datetime import datetime
from typing import List, Dict, Any, Optional
from qdrant_client import QdrantClient
from qdrant_client.http.exceptions import UnexpectedResponse

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def get_embedding(text: str) -> List[float]:
    """
    Get an embedding for the provided text.
    This uses the Vertex AI embedding model.
    """
    try:
        # Import the embedding service from your project
        from services.vertex_ai import vertex_ai_service
        
        # Get embedding asynchronously (make sure to await if necessary)
        embedding = vertex_ai_service.get_embedding(text)
        return embedding
    except Exception as e:
        logger.error(f"Error getting embedding: {e}")
        # Return a dummy embedding for testing if real embedding fails
        return [0.0] * 1536  # Return a zero vector of size 1536

def load_data_from_file(filepath: str) -> List[Dict[str, Any]]:
    """Load data from a JSON file."""
    try:
        with open(filepath, 'r') as f:
            data = json.load(f)
        return data
    except Exception as e:
        logger.error(f"Error loading data from {filepath}: {e}")
        return []

def upsert_data(
    client: QdrantClient,
    collection_name: str,
    data: List[Dict[str, Any]],
) -> bool:
    """
    Upsert data into the Qdrant collection.
    Each data item should have 'text' and 'metadata' fields.
    """
    try:
        # Process data into points
        points = []
        for i, item in enumerate(data):
            text = item.get("text", "")
            metadata = item.get("metadata", {})
            
            # Add timestamp if not present
            if "timestamp" not in metadata:
                metadata["timestamp"] = datetime.now().isoformat()
            
            # Get embedding for text
            embedding = get_embedding(text)
            
            # Create point
            points.append({
                "id": i,
                "vector": embedding,
                "payload": {
                    "text": text,
                    "metadata": metadata,
                }
            })
        
        # Upsert points in batches
        batch_size = 100
        for i in range(0, len(points), batch_size):
            batch = points[i:i+batch_size]
            client.upsert(
                collection_name=collection_name,
                points=batch,
            )
            logger.info(f"Uploaded batch {i//batch_size + 1}/{(len(points)-1)//batch_size + 1}")
        
        logger.info(f"Successfully uploaded {len(points)} points to collection '{collection_name}'")
        return True
    
    except UnexpectedResponse as e:
        logger.error(f"Error upserting data: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return False

def create_sample_data() -> List[Dict[str, Any]]:
    """Create some sample data entries for testing."""
    return [
        {
            "text": "Denker is an AI assistant designed to help users with various tasks including web browsing, file management, and content generation.",
            "metadata": {
                "source": "documentation",
                "category": "product_info",
                "timestamp": datetime.now().isoformat()
            }
        },
        {
            "text": "The MCP (Model Context Protocol) is a standardized way for language models to interact with external tools and data sources.",
            "metadata": {
                "source": "documentation",
                "category": "technical",
                "timestamp": datetime.now().isoformat()
            }
        },
        {
            "text": "Qdrant is a vector database optimized for storing and searching embeddings using similarity metrics like cosine similarity.",
            "metadata": {
                "source": "documentation", 
                "category": "technical",
                "timestamp": datetime.now().isoformat()
            }
        },
        {
            "text": "Puppeteer is a Node.js library that provides a high-level API for controlling headless Chrome or Chromium browsers.",
            "metadata": {
                "source": "documentation",
                "category": "technical",
                "timestamp": datetime.now().isoformat()
            }
        },
        {
            "text": "RAG (Retrieval-Augmented Generation) is a technique that enhances LLM responses by first retrieving relevant information and then using it to generate more accurate answers.",
            "metadata": {
                "source": "documentation",
                "category": "technical",
                "timestamp": datetime.now().isoformat()
            }
        }
    ]

def main():
    parser = argparse.ArgumentParser(description="Load data into a Qdrant collection for RAG")
    parser.add_argument("--url", default=os.environ.get("QDRANT_URL", "http://localhost:6333"),
                        help="Qdrant server URL")
    parser.add_argument("--collection", default=os.environ.get("COLLECTION_NAME", "denker_embeddings"),
                        help="Collection name to load data into")
    parser.add_argument("--file", help="Path to JSON file containing data to load")
    parser.add_argument("--sample", action="store_true", help="Load sample data for testing")
    
    args = parser.parse_args()
    
    # Validate arguments
    if not args.file and not args.sample:
        logger.warning("No data source specified. Use --file or --sample.")
        parser.print_help()
        return 1
    
    logger.info(f"Connecting to Qdrant at {args.url}")
    client = QdrantClient(url=args.url)
    
    # Load data
    data = []
    if args.file:
        logger.info(f"Loading data from file: {args.file}")
        data = load_data_from_file(args.file)
    
    if args.sample or not data:
        logger.info("Loading sample data")
        data = create_sample_data()
    
    logger.info(f"Upserting {len(data)} items into collection '{args.collection}'")
    success = upsert_data(
        client=client,
        collection_name=args.collection,
        data=data,
    )
    
    if success:
        logger.info("Data loading completed successfully")
        return 0
    else:
        logger.error("Data loading failed")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 