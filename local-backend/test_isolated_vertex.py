#!/usr/bin/env python3
"""
Isolated test of Vertex AI without any FastAPI or coordinator involvement.
"""

import os
import sys

# Set environment variables
os.environ["VERTEX_PROJECT_ID"] = "modular-bucksaw-424010-p6"
os.environ["VERTEX_REGION"] = "europe-west1"

def test_direct_vertex_call():
    """Test direct Vertex AI call completely isolated."""
    try:
        # Import directly 
        from anthropic import AnthropicVertex
        
        # Create client
        client = AnthropicVertex(
            project_id=os.environ.get("VERTEX_PROJECT_ID"),
            region=os.environ.get("VERTEX_REGION")
        )
        
        print(f"✓ Created client: {type(client)}")
        print(f"✓ Client has messages: {hasattr(client, 'messages')}")
        print(f"✓ Messages has create: {hasattr(client.messages, 'create')}")
        print(f"✓ Messages has acreate: {hasattr(client.messages, 'acreate')}")
        
        # Make API call
        response = client.messages.create(
            model="claude-3-5-haiku@20241022",  # Try a cheaper model first
            max_tokens=5,
            messages=[{"role": "user", "content": "Hi"}]
        )
        
        print(f"✓ API call successful!")
        print(f"Response: {response.content[0].text}")
        return True
        
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("=== Isolated Vertex AI Test ===")
    test_direct_vertex_call() 