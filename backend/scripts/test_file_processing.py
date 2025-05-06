#!/usr/bin/env python
"""
Test script for enhanced file processing.
This script tests extraction of content from various file types.
"""

import os
import sys
import logging
import argparse
from services.file_processing import extract_content

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_file_extraction(file_path):
    """Test content extraction from a file."""
    if not os.path.exists(file_path):
        logger.error(f"File does not exist: {file_path}")
        return False
    
    try:
        logger.info(f"Attempting to extract content from: {file_path}")
        content = extract_content(file_path)
        
        if content:
            logger.info(f"Successfully extracted content from: {file_path}")
            preview = content[:500] + "..." if len(content) > 500 else content
            logger.info(f"Content preview: {preview}")
            return True
        else:
            logger.error(f"Failed to extract content from: {file_path}")
            return False
    except Exception as e:
        logger.error(f"Error extracting content from {file_path}: {str(e)}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Test file content extraction")
    parser.add_argument("file_path", help="Path to the file to test")
    args = parser.parse_args()
    
    success = test_file_extraction(args.file_path)
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main() 