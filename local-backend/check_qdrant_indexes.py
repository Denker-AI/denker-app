#!/usr/bin/env python3
"""
Script to check Qdrant collection indexes and document structure.
This will help us understand what indexes exist and what the stored data looks like.
"""

import os
import sys
import logging
from qdrant_client import QdrantClient
from qdrant_client.http.exceptions import UnexpectedResponse

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def check_qdrant_collection():
    """Check Qdrant collection indexes and structure."""
    
    # Use local Qdrant settings - adjust these based on your local setup
    qdrant_url = "http://localhost:6333"  # Local Qdrant
    collection_name = "denker_embeddings"
    
    try:
        # Connect to Qdrant
        client = QdrantClient(url=qdrant_url)
        
        # Check if collection exists
        try:
            collection_info = client.get_collection(collection_name)
            print(f"✅ Collection '{collection_name}' exists")
            print(f"   Vector config: {collection_info.config.params.vectors}")
            print(f"   Points count: {collection_info.points_count}")
            print()
        except Exception as e:
            print(f"❌ Error getting collection info: {e}")
            return
        
        # Get collection information with payload schema
        try:
            collection_details = client.get_collection(collection_name)
            payload_schema = collection_details.config.params.payload_schema
            if payload_schema:
                print("📋 Payload Schema (Indexes):")
                for field_name, field_info in payload_schema.items():
                    print(f"   {field_name}: {field_info}")
            else:
                print("⚠️  No payload schema/indexes found")
            print()
        except Exception as e:
            print(f"⚠️  Could not get payload schema: {e}")
            print()
        
        # Scroll through some points to see the structure
        try:
            print("🔍 Sample documents structure:")
            scroll_result = client.scroll(
                collection_name=collection_name,
                limit=3,
                with_payload=True,
                with_vectors=False
            )
            
            for i, point in enumerate(scroll_result[0], 1):
                print(f"\nSample Point {i}:")
                print(f"   ID: {point.id}")
                if point.payload:
                    print("   Payload:")
                    for key, value in point.payload.items():
                        if key == "metadata" and isinstance(value, dict):
                            print(f"     {key}:")
                            for meta_key, meta_value in value.items():
                                print(f"       {meta_key}: {meta_value}")
                        else:
                            print(f"     {key}: {str(value)[:100]}...")  # Truncate long values
                else:
                    print("   No payload found")
            
            if not scroll_result[0]:
                print("   No documents found in collection")
            
        except Exception as e:
            print(f"❌ Error scrolling through points: {e}")
        
        # Try to check if metadata.file_id index exists by testing a filter
        try:
            print("\n🧪 Testing metadata.file_id filter (this should reveal index issues):")
            test_result = client.scroll(
                collection_name=collection_name,
                scroll_filter=client.Filter(
                    must=[
                        client.FieldCondition(
                            key="metadata.file_id",
                            match=client.MatchValue(value="test-file-id-123")
                        )
                    ]
                ),
                limit=1,
                with_payload=True
            )
            print("   ✅ metadata.file_id filter works (index exists or collection is small)")
        except UnexpectedResponse as e:
            if "403" in str(e) and "Index required" in str(e):
                print("   ❌ metadata.file_id filter failed - INDEX MISSING")
                print(f"   Error: {e}")
            else:
                print(f"   ⚠️  Unexpected error: {e}")
        except Exception as e:
            print(f"   ⚠️  Filter test failed: {e}")
        
    except Exception as e:
        logger.error(f"Error connecting to Qdrant: {e}")
        print(f"❌ Failed to connect to Qdrant at {qdrant_url}")
        print(f"   Error: {e}")
        print(f"   Make sure Qdrant is running locally or adjust the qdrant_url variable")

if __name__ == "__main__":
    print("🔍 Checking Qdrant Collection Indexes and Structure")
    print("=" * 60)
    check_qdrant_collection() 