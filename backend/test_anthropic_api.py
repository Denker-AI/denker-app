#!/usr/bin/env python3
"""
Test script to check both the MCP agent endpoint and direct Anthropic API calls
"""

import requests
import json
import os
import sys
import uuid

# API KEYS and CONFIG
ANTHROPIC_API_KEY = "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"
MCP_AGENT_URL = "http://localhost:8001/api/v1/agents/coordinator/mcp-agent"
ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_MODEL = "claude-3-7-sonnet-20250219"

def test_anthropic_direct():
    """Test a direct API call to Anthropic's API"""
    print("\n==== Testing Direct Anthropic API Call ====")
    
    headers = {
        "Content-Type": "application/json",
        "anthropic-version": "2023-06-01",
        "x-api-key": ANTHROPIC_API_KEY
    }
    
    # Standard message format for Anthropic API
    payload = {
        "model": ANTHROPIC_MODEL,
        "max_tokens": 1000,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "Hello, world!"
                    }
                ]
            }
        ]
    }
    
    print(f"Sending request to {ANTHROPIC_API_URL}")
    print(f"Headers: {json.dumps(headers, indent=2)}")
    print(f"Payload: {json.dumps(payload, indent=2)}")
    
    try:
        response = requests.post(
            ANTHROPIC_API_URL,
            headers=headers,
            json=payload
        )
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"Response: {json.dumps(result, indent=2)}")
            return True
        else:
            print(f"Error: {response.text}")
            return False
            
    except Exception as e:
        print(f"Exception: {str(e)}")
        return False

def test_mcp_agent():
    """Test MCP agent endpoint"""
    print("\n==== Testing MCP Agent Endpoint ====")
    
    headers = {
        "Content-Type": "application/json"
    }
    
    # Generate a query ID
    query_id = str(uuid.uuid4())
    
    # Payload format for MCP agent - updated with query_id
    payload = {
        "query": "Hello, world!",
        "user_id": "test-user",
        "source": "test-script",
        "query_id": query_id
    }
    
    print(f"Sending request to {MCP_AGENT_URL}")
    print(f"Payload: {json.dumps(payload, indent=2)}")
    
    try:
        response = requests.post(
            MCP_AGENT_URL,
            headers=headers,
            json=payload
        )
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"Response: {json.dumps(result, indent=2)}")
            return True
        else:
            print(f"Error: {response.text}")
            return False
            
    except Exception as e:
        print(f"Exception: {str(e)}")
        return False

def test_anthropic_direct_with_different_models():
    """Test direct API call with different model names"""
    print("\n==== Testing Direct Anthropic API Call with Different Models ====")
    
    headers = {
        "Content-Type": "application/json",
        "anthropic-version": "2023-06-01",
        "x-api-key": ANTHROPIC_API_KEY
    }
    
    models_to_try = [
        "claude-3-7-sonnet-20250219",  # Current model
        "claude-3-sonnet-20240229",    # Standard model
        "claude-3-7-sonnet-latest"     # Latest version
    ]
    
    for model in models_to_try:
        print(f"\nTrying model: {model}")
        
        payload = {
            "model": model,
            "max_tokens": 1000,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Hello, world!"
                        }
                    ]
                }
            ]
        }
        
        try:
            response = requests.post(
                ANTHROPIC_API_URL,
                headers=headers,
                json=payload
            )
            
            print(f"Status Code: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                print(f"Success with model {model}")
                print(f"Response: {json.dumps(result, indent=2)}")
            else:
                print(f"Error with model {model}: {response.text}")
                
        except Exception as e:
            print(f"Exception with model {model}: {str(e)}")

def test_anthropic_direct_with_different_versions():
    """Test direct API call with different API versions"""
    print("\n==== Testing Direct Anthropic API Call with Different API Versions ====")
    
    versions_to_try = [
        "2023-06-01",  # Current version
        "2023-01-01",  # Older version
        "2024-04-01"   # Newer version (might not exist)
    ]
    
    for version in versions_to_try:
        print(f"\nTrying API version: {version}")
        
        headers = {
            "Content-Type": "application/json",
            "anthropic-version": version,
            "x-api-key": ANTHROPIC_API_KEY
        }
        
        payload = {
            "model": ANTHROPIC_MODEL,
            "max_tokens": 1000,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Hello, world!"
                        }
                    ]
                }
            ]
        }
        
        try:
            response = requests.post(
                ANTHROPIC_API_URL,
                headers=headers,
                json=payload
            )
            
            print(f"Status Code: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                print(f"Success with version {version}")
            else:
                print(f"Error with version {version}: {response.text}")
                
        except Exception as e:
            print(f"Exception with version {version}: {str(e)}")

def main():
    """Run all tests"""
    # First test direct Anthropic API
    anthro_result = test_anthropic_direct()
    
    # Then test MCP agent endpoint
    mcp_result = test_mcp_agent()
    
    # If direct API call fails, try different models
    if not anthro_result:
        test_anthropic_direct_with_different_models()
    
    # If direct API call fails, try different API versions
    if not anthro_result:
        test_anthropic_direct_with_different_versions()
    
    print("\n==== Test Summary ====")
    print(f"Direct Anthropic API: {'SUCCESS' if anthro_result else 'FAILED'}")
    print(f"MCP Agent Endpoint: {'SUCCESS' if mcp_result else 'FAILED'}")

if __name__ == "__main__":
    main() 