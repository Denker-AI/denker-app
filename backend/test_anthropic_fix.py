#!/usr/bin/env python3
"""
Test script with corrected Anthropic API message format
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

def test_fixes():
    """Test different fixes for the Anthropic API error"""
    
    print("\n==== Testing Various Format Fixes ====")
    
    # Fix 1: Remove system parameter entirely
    print("\n-- Fix 1: Remove system parameter entirely --")
    payload1 = {
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
        "tools": []
    }
    
    # Fix 2: Set system as empty string
    print("\n-- Fix 2: Set system as empty string --")
    payload2 = {
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
        "system": "",
        "tools": []
    }
    
    # Fix 3: Set system as a list with empty string
    print("\n-- Fix 3: Set system as a list with empty string --")
    payload3 = {
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
        "system": [""],
        "tools": []
    }
    
    # Fix 4: Set system as a list with instruction
    print("\n-- Fix 4: Set system as a list with instruction --")
    payload4 = {
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
        "system": ["You are a helpful AI assistant"],
        "tools": []
    }
    
    # Common headers
    headers = {
        "Content-Type": "application/json",
        "anthropic-version": "2023-06-01",
        "x-api-key": ANTHROPIC_API_KEY
    }
    
    # Test all payloads
    payloads = [
        ("Fix 1", payload1),
        ("Fix 2", payload2),
        ("Fix 3", payload3),
        ("Fix 4", payload4)
    ]
    
    results = {}
    
    for name, payload in payloads:
        print(f"\nTesting {name}:")
        # Fix the None values
        payload_json = json.dumps(payload).replace(': None', ': null')
        fixed_payload = json.loads(payload_json)
        
        print(f"Payload: {json.dumps(fixed_payload, indent=2)}")
        
        try:
            response = requests.post(
                ANTHROPIC_API_URL,
                headers=headers,
                json=fixed_payload
            )
            
            print(f"Status Code: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ SUCCESS: {name}")
                results[name] = True
            else:
                print(f"❌ ERROR: {response.text}")
                results[name] = False
                
        except Exception as e:
            print(f"❌ EXCEPTION: {str(e)}")
            results[name] = False
    
    return results

def main():
    """Run all tests"""
    results = test_fixes()
    
    print("\n==== Test Summary ====")
    for name, success in results.items():
        print(f"{name}: {'✅ SUCCESS' if success else '❌ FAILED'}")
    
    # Determine which fix works
    working_fixes = [name for name, success in results.items() if success]
    if working_fixes:
        print(f"\n✅ RECOMMENDED FIX: {working_fixes[0]}")
        print("To fix the issue in your code, use this format for your Anthropic API requests.")
    else:
        print("\n❌ NO WORKING FIX FOUND")
        print("Please contact Anthropic support for assistance.")
        
if __name__ == "__main__":
    main() 