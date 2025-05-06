#!/usr/bin/env python3
"""
Markdown Editor MCP Server

A FastMCP server that provides tools for creating, editing, and converting
Markdown documents with live preview capabilities.
"""

from fastmcp import FastMCP
import os
import sys
import logging
import tempfile
import json
from typing import Dict, Any, List, Optional, Union

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("markdown-editor")

# Import module functionality
from .markdown_converter import convert_to_markdown, convert_from_markdown
from .markdown_editor import create_markdown, edit_markdown, append_to_markdown
from .markdown_preview import preview_markdown, start_live_preview
from .markdown_integration import add_chart_to_markdown, create_chart_from_markdown_data, extract_table_from_markdown

# Initialize FastMCP server
app = FastMCP(name="markdown-editor", version="1.0.0")

# Register tools
@app.tool()
def create_document(content: str, file_path: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Create a new Markdown document with the given content.
    
    Args:
        content: Markdown content to write
        file_path: Optional path to save the file (creates temp file if not provided)
        metadata: Optional metadata to store with the document
        
    Returns:
        Information about the created file
    """
    return create_markdown(content, file_path, metadata)

@app.tool()
def edit_document(file_path: str, operations: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Edit an existing Markdown document with a list of operations.
    
    Args:
        file_path: Path to the Markdown file
        operations: List of edit operations (replace, insert, delete)
        
    Returns:
        Information about the edited file
    """
    return edit_markdown(file_path, operations)

@app.tool()
def append_content(file_path: str, content: str, section: Optional[str] = None) -> Dict[str, Any]:
    """
    Append content to a Markdown document.
    
    Args:
        file_path: Path to the Markdown file
        content: Content to append
        section: Optional section heading to append under
        
    Returns:
        Information about the updated file
    """
    return append_to_markdown(file_path, content, section)

@app.tool()
def add_image(file_path: str, image_path: str, alt_text: str = "", position: Optional[int] = None) -> Dict[str, Any]:
    """
    Add an image to a Markdown document.
    
    Args:
        file_path: Path to the Markdown file
        image_path: Path to the image file
        alt_text: Alternative text for the image
        position: Optional line number to insert at (appends if None)
        
    Returns:
        Information about the updated file
    """
    if not os.path.exists(image_path):
        return {
            "success": False,
            "error": f"Image file not found: {image_path}"
        }
    
    # Convert absolute paths to relative if possible
    if os.path.isabs(image_path):
        try:
            # Get directory of markdown file
            md_dir = os.path.dirname(os.path.abspath(file_path))
            rel_path = os.path.relpath(image_path, md_dir)
            image_path = rel_path
        except:
            # Keep absolute path if relative conversion fails
            pass
    
    # Create markdown image syntax
    image_md = f"![{alt_text}]({image_path})"
    
    # Add to document at specified position or append
    if position is not None:
        return edit_markdown(file_path, [
            {
                "type": "insert_at_line",
                "line_number": position,
                "text": image_md
            }
        ])
    else:
        return append_to_markdown(file_path, f"\n\n{image_md}\n")

@app.tool()
def convert_to_md(source_file: str, output_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Convert a document (DOCX, PDF, HTML) to Markdown.
    
    Args:
        source_file: Path to the source document
        output_path: Optional path for the output Markdown file
        
    Returns:
        Information about the converted file
    """
    return convert_to_markdown(source_file, output_path)

@app.tool()
def convert_from_md(markdown_file: str, output_format: str, output_path: Optional[str] = None, options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Convert a Markdown document to another format (PDF, DOCX, HTML).
    
    Args:
        markdown_file: Path to the Markdown file
        output_format: Target format (pdf, docx, html)
        output_path: Optional path for the output file
        options: Optional format-specific conversion options
        
    Returns:
        Information about the converted file
    """
    return convert_from_markdown(markdown_file, output_format, output_path, options)

@app.tool()
def preview(file_path: str, format: str = "html") -> Dict[str, Any]:
    """
    Generate a preview of a Markdown document.
    
    Args:
        file_path: Path to the Markdown file
        format: Preview format (html or text)
        
    Returns:
        Preview content
    """
    return preview_markdown(file_path, format)

@app.tool()
def live_preview(file_path: str, port: int = 8000) -> Dict[str, Any]:
    """
    Start a live preview server for a Markdown document.
    
    Args:
        file_path: Path to the Markdown file
        port: Server port (default: 8000)
        
    Returns:
        Server information
    """
    return start_live_preview(file_path, port)

@app.tool()
def add_chart(markdown_file: str, chart_data: Dict[str, Any], position: Optional[int] = None, alt_text: str = "Chart") -> Dict[str, Any]:
    """
    Add a chart from the chartgenerator server to a Markdown document.
    
    Args:
        markdown_file: Path to the Markdown file
        chart_data: Chart data returned from chartgenerator
        position: Optional line number to insert at (appends if None)
        alt_text: Alternative text for the chart
        
    Returns:
        Information about the updated file
    """
    # This is a synchronous wrapper for the async function
    import asyncio
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(add_chart_to_markdown(markdown_file, chart_data, position, alt_text))

@app.tool()
def extract_table(markdown_file: str, table_index: int = 0) -> Dict[str, Any]:
    """
    Extract tabular data from a Markdown document.
    
    Args:
        markdown_file: Path to the Markdown file
        table_index: Index of the table to extract (0-based)
        
    Returns:
        Extracted table data
    """
    # This is a synchronous wrapper for the async function
    import asyncio
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(extract_table_from_markdown(markdown_file, table_index))

# Run the server when the script is executed directly
if __name__ == "__main__":
    logger.info("Starting Markdown Editor MCP Server")
    app.run() 