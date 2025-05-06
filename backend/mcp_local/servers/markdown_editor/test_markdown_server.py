#!/usr/bin/env python3
"""
Test script for the Markdown Editor MCP Server.
Tests basic functionality of the server.
"""

import os
import sys
import logging
import tempfile
import subprocess
import time
import json
import argparse

# Add parent directory to path to allow importing server module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configure logging
logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("markdown-editor-test")

def run_command(cmd, input_data=None):
    """Run a command and return the output."""
    logger.info(f"Running command: {cmd}")
    process = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE if input_data else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        shell=True
    )
    
    stdout, stderr = process.communicate(input=input_data)
    
    if process.returncode != 0:
        logger.error(f"Command failed with return code {process.returncode}")
        logger.error(f"STDERR: {stderr}")
        return None
    
    return stdout

def send_mcp_request(request_type, name=None, arguments=None):
    """Send a request to the MCP server and return the response."""
    request = {"type": request_type}
    
    if name:
        request["name"] = name
    
    if arguments:
        request["arguments"] = arguments
    
    # Convert request to JSON
    request_json = json.dumps(request)
    
    # Send request to server
    response = run_command("python -m markdown_editor.server", input_data=request_json)
    
    if response:
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            logger.error(f"Failed to parse response as JSON: {response}")
            return None
    
    return None

def test_create_document():
    """Test creating a Markdown document."""
    logger.info("Testing create_document...")
    
    # Create a temporary file
    temp_dir = tempfile.gettempdir()
    test_file = os.path.join(temp_dir, "test_markdown.md")
    
    # Test content
    test_content = """# Test Markdown Document
    
This is a test Markdown document created by the test script.

## Features

- Item 1
- Item 2
- Item 3

## Code Example

```python
def hello_world():
    print("Hello, world!")
```

## Table Example

| Header 1 | Header 2 | Header 3 |
|----------|----------|----------|
| Cell 1   | Cell 2   | Cell 3   |
| Cell 4   | Cell 5   | Cell 6   |
"""
    
    # Send request to create document
    response = send_mcp_request(
        "tool_call",
        "create_document",
        {
            "content": test_content,
            "file_path": test_file
        }
    )
    
    if not response or response.get("type") != "tool_result":
        logger.error(f"Failed to create document: {response}")
        return False
    
    result = response.get("result", {})
    if not result.get("success", False):
        logger.error(f"Failed to create document: {result.get('error')}")
        return False
    
    logger.info(f"Document created successfully at {result.get('file_path')}")
    
    return test_file

def test_preview_document(file_path):
    """Test previewing a Markdown document."""
    logger.info("Testing preview...")
    
    # Send request to preview document
    response = send_mcp_request(
        "tool_call",
        "preview",
        {
            "file_path": file_path,
            "format": "html"
        }
    )
    
    if not response or response.get("type") != "tool_result":
        logger.error(f"Failed to preview document: {response}")
        return False
    
    result = response.get("result", {})
    if not result.get("success", False):
        logger.error(f"Failed to preview document: {result.get('error')}")
        return False
    
    preview_path = result.get("preview_path")
    logger.info(f"Document previewed successfully, HTML at {preview_path}")
    
    return True

def test_edit_document(file_path):
    """Test editing a Markdown document."""
    logger.info("Testing edit_document...")
    
    # Send request to edit document
    response = send_mcp_request(
        "tool_call",
        "edit_document",
        {
            "file_path": file_path,
            "operations": [
                {
                    "type": "replace",
                    "target": "# Test Markdown Document",
                    "replacement": "# Updated Test Document"
                },
                {
                    "type": "append",
                    "text": "\n\n## Added Section\n\nThis section was added by the test script."
                }
            ]
        }
    )
    
    if not response or response.get("type") != "tool_result":
        logger.error(f"Failed to edit document: {response}")
        return False
    
    result = response.get("result", {})
    if not result.get("success", False):
        logger.error(f"Failed to edit document: {result.get('error')}")
        return False
    
    logger.info(f"Document edited successfully at {result.get('file_path')}")
    
    return True

def test_convert_from_md(file_path):
    """Test converting a Markdown document to HTML."""
    logger.info("Testing convert_from_md...")
    
    # Create output path
    output_path = os.path.splitext(file_path)[0] + ".html"
    
    # Send request to convert document
    response = send_mcp_request(
        "tool_call",
        "convert_from_md",
        {
            "markdown_file": file_path,
            "output_format": "html",
            "output_path": output_path
        }
    )
    
    if not response or response.get("type") != "tool_result":
        logger.error(f"Failed to convert document: {response}")
        return False
    
    result = response.get("result", {})
    if not result.get("success", False):
        logger.error(f"Failed to convert document: {result.get('error')}")
        return False
    
    logger.info(f"Document converted successfully to {result.get('file_path')}")
    
    return True

def test_extract_table(file_path):
    """Test extracting a table from a Markdown document."""
    logger.info("Testing extract_table...")
    
    # Send request to extract table
    response = send_mcp_request(
        "tool_call",
        "extract_table",
        {
            "markdown_file": file_path,
            "table_index": 0
        }
    )
    
    if not response or response.get("type") != "tool_result":
        logger.error(f"Failed to extract table: {response}")
        return False
    
    result = response.get("result", {})
    if not result.get("success", False):
        logger.error(f"Failed to extract table: {result.get('error')}")
        return False
    
    headers = result.get("headers", [])
    data = result.get("data", [])
    
    logger.info(f"Table extracted successfully:")
    logger.info(f"Headers: {headers}")
    logger.info(f"Data: {data}")
    
    return True

def run_tests():
    """Run all tests."""
    logger.info("Starting tests...")
    
    # Start the server in a separate process
    server_process = subprocess.Popen(
        "python server.py",
        shell=True,
        cwd=os.path.dirname(os.path.abspath(__file__))
    )
    
    try:
        # Give the server time to start
        time.sleep(2)
        
        # Run the tests
        test_file = test_create_document()
        if not test_file:
            return False
        
        if not test_preview_document(test_file):
            return False
        
        if not test_edit_document(test_file):
            return False
        
        if not test_convert_from_md(test_file):
            return False
        
        if not test_extract_table(test_file):
            return False
        
        logger.info("All tests passed successfully!")
        return True
    
    finally:
        # Terminate the server
        server_process.terminate()
        server_process.wait()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test the Markdown Editor MCP Server")
    args = parser.parse_args()
    
    success = run_tests()
    sys.exit(0 if success else 1) 