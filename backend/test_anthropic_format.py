#!/usr/bin/env python3
"""
Specific test script to debug Anthropic API message formats
"""

import requests
import json
import os
import sys
import logging

# Configure detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# API KEYS and CONFIG
ANTHROPIC_API_KEY = "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"
ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"

def test_original_format():
    """Test using the format from the logs"""
    
    print("\n==== Testing Your Original Format ====")
    
    headers = {
        "Content-Type": "application/json",
        "anthropic-version": "2023-06-01",
        "x-api-key": ANTHROPIC_API_KEY
    }
    
    # The exact format from your logs
    payload = {
        "max_tokens": 1000, 
        "messages": [
            {
                "role": "user", 
                "content": [
                    {
                        "type": "text", 
                        "text": "Query: hello\nSource: Main Window"
                    }
                ]
            }
        ], 
        "model": "claude-3-7-sonnet-20250219", 
        "stop_sequences": None, 
        "system": None, 
        "tools": []
    }
    
    # Fix the None values to proper JSON null
    payload_json = json.dumps(payload).replace(': None', ': null')
    payload = json.loads(payload_json)
    
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

def test_debug_versions():
    """Test different API versions with the exact same payload"""
    
    print("\n==== Testing Different API Versions with Original Format ====")
    
    # The exact format from your logs with None converted to null
    payload = {
        "max_tokens": 1000, 
        "messages": [
            {
                "role": "user", 
                "content": [
                    {
                        "type": "text", 
                        "text": "Query: hello\nSource: Main Window"
                    }
                ]
            }
        ], 
        "model": "claude-3-7-sonnet-20250219", 
        "stop_sequences": None, 
        "system": None, 
        "tools": []
    }
    
    # Fix the None values to proper JSON null
    payload_json = json.dumps(payload).replace(': None', ': null')
    payload = json.loads(payload_json)
    
    versions = [
        "2023-06-01",  # Standard
        "2023-01-01",  # Old
        None           # No version header
    ]
    
    for version in versions:
        print(f"\n-- Testing with API version: {version or 'NONE'} --")
        
        headers = {
            "Content-Type": "application/json",
            "x-api-key": ANTHROPIC_API_KEY
        }
        
        if version:
            headers["anthropic-version"] = version
        
        try:
            response = requests.post(
                ANTHROPIC_API_URL,
                headers=headers,
                json=payload
            )
            
            print(f"Status Code: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                print(f"Success with version {version or 'NONE'}")
            else:
                print(f"Error with version {version or 'NONE'}: {response.text}")
                
        except Exception as e:
            print(f"Exception with version {version or 'NONE'}: {str(e)}")

def test_alternate_models():
    """Test with different Claude model versions"""
    
    print("\n==== Testing Different Claude Models ====")
    
    headers = {
        "Content-Type": "application/json",
        "anthropic-version": "2023-06-01",
        "x-api-key": ANTHROPIC_API_KEY
    }
    
    models = [
        "claude-3-7-sonnet-20250219",
        "claude-3-sonnet-20240229", 
        "claude-3-haiku-20240307"
    ]
    
    for model in models:
        print(f"\n-- Testing with model: {model} --")
        
        payload = {
            "max_tokens": 1000,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Query: hello\nSource: Main Window"
                        }
                    ]
                }
            ],
            "model": model,
            "stop_sequences": None,
            "system": None,
            "tools": []
        }
        
        # Fix the None values to proper JSON null
        payload_json = json.dumps(payload).replace(': None', ': null')
        payload = json.loads(payload_json)
        
        try:
            response = requests.post(
                ANTHROPIC_API_URL,
                headers=headers,
                json=payload
            )
            
            print(f"Status Code: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                print(f"Success with model: {model}")
            else:
                print(f"Error with model {model}: {response.text}")
                
        except Exception as e:
            print(f"Exception with model {model}: {str(e)}")

def main():
    """Run all tests"""
    # Test the original format from logs
    original_result = test_original_format()
    
    if not original_result:
        # If original format fails, try different API versions
        test_debug_versions()
        
        # Try different models
        test_alternate_models()
    
    print("\n==== Test Summary ====")
    print(f"Original Format Test: {'SUCCESS' if original_result else 'FAILED'}")
    
if __name__ == "__main__":
    main() 