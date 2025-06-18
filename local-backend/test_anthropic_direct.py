#!/usr/bin/env python3
"""
Direct test of AnthropicVertex to isolate the issue.
"""

import os
import sys

# Set environment variables
os.environ["VERTEX_PROJECT_ID"] = "modular-bucksaw-424010-p6"
os.environ["VERTEX_REGION"] = "europe-west1"

def test_anthropic_imports():
    """Test if we can import Anthropic clients."""
    try:
        from anthropic import Anthropic, AnthropicVertex
        print("✓ Successfully imported Anthropic and AnthropicVertex")
        return True
    except Exception as e:
        print(f"✗ Failed to import Anthropic clients: {e}")
        return False

def test_direct_anthropic():
    """Test direct Anthropic client."""
    try:
        from anthropic import Anthropic
        client = Anthropic()
        print("✓ Successfully created direct Anthropic client")
        
        # Check if messages attribute exists
        if hasattr(client, 'messages'):
            print("✓ Client has messages attribute")
            if hasattr(client.messages, 'create'):
                print("✓ messages.create method exists")
            if hasattr(client.messages, 'acreate'):
                print("✓ messages.acreate method exists")
            else:
                print("✗ messages.acreate method does NOT exist")
        else:
            print("✗ Client does NOT have messages attribute")
        
        return True
    except Exception as e:
        print(f"✗ Failed to create direct Anthropic client: {e}")
        return False

def test_vertex_anthropic():
    """Test Vertex AI Anthropic client."""
    try:
        from anthropic import AnthropicVertex
        client = AnthropicVertex(
            project_id=os.environ.get("VERTEX_PROJECT_ID"),
            region=os.environ.get("VERTEX_REGION")
        )
        print("✓ Successfully created AnthropicVertex client")
        
        # Check if messages attribute exists
        if hasattr(client, 'messages'):
            print("✓ Vertex client has messages attribute")
            if hasattr(client.messages, 'create'):
                print("✓ Vertex messages.create method exists")
            if hasattr(client.messages, 'acreate'):
                print("✗ Vertex messages.acreate method exists (should NOT exist)")
            else:
                print("✓ Vertex messages.acreate method does NOT exist (correct)")
        else:
            print("✗ Vertex client does NOT have messages attribute")
        
        return True
    except Exception as e:
        print(f"✗ Failed to create AnthropicVertex client: {e}")
        return False

def test_simple_api_call():
    """Test a simple API call."""
    try:
        from anthropic import AnthropicVertex
        client = AnthropicVertex(
            project_id=os.environ.get("VERTEX_PROJECT_ID"),
            region=os.environ.get("VERTEX_REGION")
        )
        
        response = client.messages.create(
            model="claude-3-7-sonnet@20250219",
            max_tokens=10,
            messages=[{"role": "user", "content": "Hello"}]
        )
        
        print("✓ Successfully made API call to Vertex AI")
        print(f"Response: {response.content[0].text}")
        return True
    except Exception as e:
        print(f"✗ Failed to make API call: {e}")
        return False

if __name__ == "__main__":
    print("=== Testing Anthropic Client Creation ===")
    
    test_anthropic_imports()
    print()
    
    test_direct_anthropic()
    print()
    
    test_vertex_anthropic()
    print()
    
    test_simple_api_call() 