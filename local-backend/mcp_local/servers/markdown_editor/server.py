#!/usr/bin/env python3
"""
Markdown Editor MCP Server

A Model Context Protocol server that provides comprehensive markdown editing,
conversion, and preview capabilities.

🏗️ ARCHITECTURE:
- CREATE/EDIT functions: ALWAYS work in workspace (/tmp/denker_workspace/default)
- CONVERT functions: Can output to user-configured directories (with validation)
- FILESYSTEM operations: For moving files from workspace to user folders

📁 WORKFLOW:
1. Create documents in workspace using create_document, create_csv_document, etc.
2. Edit documents in workspace using edit_document, add_image, etc.
3. Convert final documents to user folders using convert_from_md (if needed)
4. Use filesystem tools to move/copy files from workspace to user folders
"""

import os
import sys
import logging
import asyncio
from typing import Dict, Any, List, Optional, Union
from fastmcp import FastMCP
from pathlib import Path
from datetime import datetime

# Add the parent directory to the path to import local modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

# Try to import from relative path first (PyInstaller), then from same directory
try:
    from .markdown_editor import create_markdown, edit_markdown, append_to_markdown
    from .markdown_converter import convert_to_markdown, convert_from_markdown, check_pandoc_installation
    from .markdown_preview import preview_markdown, start_live_preview
    from .markdown_integration import add_chart_to_markdown, extract_table_from_markdown
    from .chart_generator import create_chart_tool, create_chart_from_data_tool, get_chart_template_tool
    from .photo_generator import search_photos_tool, download_photo_tool, get_photo_categories_tool, search_and_download_photo_tool
except ImportError:
    # Fallback for development environment
    from markdown_editor import create_markdown, edit_markdown, append_to_markdown
    from markdown_converter import convert_to_markdown, convert_from_markdown, check_pandoc_installation
    from markdown_preview import preview_markdown, start_live_preview
    from markdown_integration import add_chart_to_markdown, extract_table_from_markdown
    from chart_generator import create_chart_tool, create_chart_from_data_tool, get_chart_template_tool
    from photo_generator import search_photos_tool, download_photo_tool, get_photo_categories_tool, search_and_download_photo_tool

# Try to import shared workspace for multi-agent coordination
try:
    from core.shared_workspace import get_shared_workspace
    SHARED_WORKSPACE_AVAILABLE = True
except ImportError:
    SHARED_WORKSPACE_AVAILABLE = False

logger = logging.getLogger("markdown-editor")

# Initialize FastMCP server
app = FastMCP(name="markdown-editor", version="1.0.0")

def get_workspace_path(filename: str, category: str = None) -> str:
    """
    Get a shared workspace path for file operations.
    
    Args:
        filename: Name of the file (uses only filename, no subdirectories)
        category: Ignored - kept for compatibility
        
    Returns:
        Absolute path within shared workspace root
    """
    logger.info(f"[get_workspace_path] Requested filename: {filename}, SHARED_WORKSPACE_AVAILABLE: {SHARED_WORKSPACE_AVAILABLE}")
    
    if SHARED_WORKSPACE_AVAILABLE:
        try:
            workspace = get_shared_workspace()
            
            # Extract just the filename - no subdirectories allowed
            filename_only = os.path.basename(filename)
            file_path = workspace.workspace_root / filename_only
            
            logger.info(f"[get_workspace_path] Using shared workspace: {file_path}")
            return str(file_path)
        except Exception as e:
            logger.warning(f"Could not use shared workspace: {e}")
    
    # FIXED: Always use unified temp workspace as fallback
    try:
        from mcp_local.core.shared_workspace import SharedWorkspaceManager
        fallback_path = SharedWorkspaceManager._get_unified_workspace_path("default")
        fallback_dir = str(fallback_path)
        logger.info(f"[get_workspace_path] Using unified temp workspace: {fallback_dir}")
    except Exception as e:
        logger.warning(f"Could not get unified workspace path: {e}")
        fallback_dir = '/tmp/denker_workspace/default'
        logger.info(f"[get_workspace_path] Fallback to unified temp workspace: {fallback_dir}")
    
    # Ensure the directory exists
    os.makedirs(fallback_dir, exist_ok=True)
    final_path = os.path.join(fallback_dir, os.path.basename(filename))
    logger.info(f"[get_workspace_path] Final path: {final_path}")
    return final_path

def register_workspace_file(file_path: str, metadata: Optional[Dict[str, Any]] = None) -> Optional[str]:
    """
    Register a file in the shared workspace for cross-agent access.
    
    Args:
        file_path: Path to the file
        metadata: Additional file metadata
        
    Returns:
        File ID for cross-agent reference, or None if not available
    """
    if SHARED_WORKSPACE_AVAILABLE:
        try:
            workspace = get_shared_workspace()
            return workspace.register_file(
                file_path=file_path,
                agent_name="markdown-editor",
                metadata=metadata
            )
        except Exception as e:
            logger.warning(f"Could not register file in workspace: {e}")
    
    return None

def find_workspace_file(file_reference: str) -> Optional[str]:
    """
    Find a file in the shared workspace by reference.
    
    Args:
        file_reference: File name only (like "report.md") - no subdirectories
        
    Returns:
        Absolute path to file if found, None otherwise
    """
    logger.info(f"[find_workspace_file] Looking for file: {file_reference}")
    
    if SHARED_WORKSPACE_AVAILABLE:
        try:
            workspace = get_shared_workspace()
            
            # Use only filename - no subdirectories
            filename_only = os.path.basename(file_reference)
            direct_path = workspace.workspace_root / filename_only
            if direct_path.exists():
                logger.info(f"[find_workspace_file] Found in shared workspace: {direct_path}")
                return str(direct_path)
            
            # Fallback to registry-based search
            found_path = workspace.find_file(filename_only)
            if found_path:
                logger.info(f"[find_workspace_file] Found via registry: {found_path}")
                return str(found_path)
        except Exception as e:
            logger.warning(f"Could not find file in workspace: {e}")
    
    # FIXED: Always use unified temp workspace as fallback
    try:
        from mcp_local.core.shared_workspace import SharedWorkspaceManager
        fallback_path = SharedWorkspaceManager._get_unified_workspace_path("default")
        filename_only = os.path.basename(file_reference)
        candidate_path = str(fallback_path / filename_only)
        logger.info(f"[find_workspace_file] Using unified temp workspace: {candidate_path}")
    except Exception as e:
        logger.warning(f"Could not get unified workspace path: {e}")
        filename_only = os.path.basename(file_reference)
        fallback_dir = '/tmp/denker_workspace/default'
        candidate_path = os.path.join(fallback_dir, filename_only)
        logger.info(f"[find_workspace_file] Fallback to unified temp workspace: {candidate_path}")
    
    if os.path.exists(candidate_path):
        logger.info(f"[find_workspace_file] Found file: {candidate_path}")
        return candidate_path
    else:
        logger.info(f"[find_workspace_file] File not found: {file_reference}")
        return None

# Register tools
@app.tool()
def create_document(content: str, file_path: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Create a new Markdown document with the given content.
    
    ⚠️ IMPORTANT: This function ALWAYS creates files in the workspace only.
    To output to user folders, first create in workspace, then use convert_from_md.
    
    Args:
        content: Markdown content to write
        file_path: Optional filename to save the file (like "report.md") - no subdirectories, workspace only
        metadata: Optional metadata to store with the document
        
    Returns:
        Information about the created file
    """
    if not file_path:
        # Generate filename from content or use default
        import re
        # Try to extract title from content
        title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
        if title_match:
            title = re.sub(r'[^\w\s-]', '', title_match.group(1))
            title = re.sub(r'[-\s]+', '-', title).strip('-')
            filename = f"{title}.md"
        else:
            filename = "document.md"
        
        file_path = filename  # Use filename directly
    
    result = create_markdown(content, file_path, metadata)
    
    # Register in shared workspace if successful
    if result.get("success") and result.get("file_path"):
        # Get the full path for registration
        full_path = get_workspace_path(result["file_path"])
        file_id = register_workspace_file(
            file_path=full_path,
            metadata={
                "type": "markdown_document",
                "content_preview": content[:100] + "..." if len(content) > 100 else content,
                **(metadata or {})
            }
        )
        if file_id:
            result["file_id"] = file_id
            result["message"] += f" (Workspace ID: {file_id})"
    
    return result

@app.tool()
def create_csv_document(csv_data: str, file_path: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Create a new CSV document with the given data.
    
    ⚠️ IMPORTANT: This function ALWAYS creates files in the workspace only.
    To output to user folders, use the filesystem tool to move the file after creation.
    
    Args:
        csv_data: CSV content to write (including headers)
        file_path: Optional filename to save the file (like "data.csv") - no subdirectories, workspace only
        metadata: Optional metadata to store with the document
        
    Returns:
        Information about the created file
    """
    import csv
    import io
    
    try:
        # Validate CSV content
        try:
            csv_reader = csv.reader(io.StringIO(csv_data))
            rows = list(csv_reader)
            if not rows:
                return {
                    "success": False,
                    "error": "CSV data is empty"
                }
        except csv.Error as e:
            return {
                "success": False,
                "error": f"Invalid CSV format: {str(e)}"
            }
        
        # Generate filename if not provided
        if not file_path:
            file_path = "data.csv"
        
        # Ensure it's just a filename (no paths)
        filename_only = os.path.basename(file_path)
        if not filename_only.endswith('.csv'):
            filename_only = filename_only.split('.')[0] + '.csv'
        
        # Get workspace path
        try:
            from mcp_local.core.shared_workspace import SharedWorkspaceManager
            workspace_path = SharedWorkspaceManager._get_unified_workspace_path("default")
            workspace_path.mkdir(parents=True, exist_ok=True)
            full_path = str(workspace_path / filename_only)
            logger.info(f"[create_csv_document] Creating CSV in workspace: {full_path}")
        except Exception as e:
            logger.warning(f"Could not get unified workspace path: {e}")
            # Fallback to unified temp directory
            fallback_dir = '/tmp/denker_workspace/default'
            os.makedirs(fallback_dir, exist_ok=True)
            full_path = os.path.join(fallback_dir, filename_only)
            logger.info(f"[create_csv_document] Using fallback path: {full_path}")
        
        # Write CSV content to file
        with open(full_path, 'w', encoding='utf-8', newline='') as f:
            f.write(csv_data)
        
        # Register in shared workspace if successful
        file_id = register_workspace_file(
            file_path=full_path,
            metadata={
                "type": "csv_document",
                "rows": len(rows),
                "columns": len(rows[0]) if rows else 0,
                **(metadata or {})
            }
        )
        
        result = {
            "success": True,
            "file_path": filename_only,  # Return relative path (filename only)
            "full_path": full_path,
            "message": f"CSV document created successfully in workspace with {len(rows)} rows"
        }
        
        if file_id:
            result["file_id"] = file_id
            result["message"] += f" (Workspace ID: {file_id})"
        
        return result
        
    except Exception as e:
        logger.error(f"Error creating CSV: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

@app.tool()
def edit_document(file_path: str, operations: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Edit an existing Markdown document with a list of operations.
    
    Args:
        file_path: Path to the Markdown file or workspace file ID
        operations: List of edit operations (replace, insert, delete)
        
    Returns:
        Information about the edited file
    """
    # Try to resolve file path from workspace
    resolved_path = find_workspace_file(file_path)
    if resolved_path:
        file_path = resolved_path
        logger.info(f"Resolved file path from workspace: {file_path}")
    
    return edit_markdown(file_path, operations)

@app.tool()
def append_content(file_path: str, content: str, section: Optional[str] = None) -> Dict[str, Any]:
    """
    Append content to a Markdown document.
    
    Args:
        file_path: Path to the Markdown file or workspace file ID
        content: Content to append
        section: Optional section heading to append under
        
    Returns:
        Information about the updated file
    """
    # Try to resolve file path from workspace
    resolved_path = find_workspace_file(file_path)
    if resolved_path:
        file_path = resolved_path
        logger.info(f"Resolved file path from workspace: {file_path}")
    
    return append_to_markdown(file_path, content, section)

@app.tool()
def add_image(file_path: str, image_path: str, alt_text: str = "", position: Optional[int] = None) -> Dict[str, Any]:
    """
    Add an image to a Markdown document.
    
    Args:
        file_path: Path to the Markdown file (filename only for workspace files, like "report.md")
        image_path: Path to the image file (filename only for workspace files, like "photo.jpg")
        alt_text: Alternative text for the image
        position: Optional line number to insert at (appends if None)
        
    Returns:
        Information about the updated file
    """
    logger.info(f"[add_image] Adding image {image_path} to {file_path}")
    
    # Try to resolve both file paths from workspace
    resolved_file_path = find_workspace_file(file_path)
    if resolved_file_path:
        file_path = resolved_file_path
        logger.info(f"Resolved markdown file path from workspace: {file_path}")
    
    # Try to resolve image file path from workspace first
    resolved_image_path = find_workspace_file(image_path)
    if resolved_image_path:
        image_path = resolved_image_path
        logger.info(f"Resolved image file path from workspace: {image_path}")
    elif not os.path.isabs(image_path):
        # If not found in workspace and not absolute, try workspace lookup
        if SHARED_WORKSPACE_AVAILABLE:
            try:
                workspace = get_shared_workspace()
                image_name = os.path.basename(image_path)
                
                # Look for the image in the workspace root
                potential_path = workspace.workspace_root / image_name
                if potential_path.exists():
                    image_path = str(potential_path)
                    logger.info(f"Found image via workspace direct access: {image_path}")
            except Exception as e:
                logger.warning(f"Could not locate image via workspace: {e}")
        
        # Fallback to unified temp workspace for image path
        if not os.path.exists(image_path):
            try:
                from mcp_local.core.shared_workspace import SharedWorkspaceManager
                fallback_path = SharedWorkspaceManager._get_unified_workspace_path("default")
                filename_only = os.path.basename(image_path)
                candidate_path = str(fallback_path / filename_only)
                logger.info(f"[add_image] Checking unified temp workspace for image: {candidate_path}")
                if os.path.exists(candidate_path):
                    image_path = candidate_path
                    logger.info(f"Found image via unified temp workspace: {image_path}")
            except Exception as e:
                logger.warning(f"Could not get unified workspace path for image: {e}")
                filename_only = os.path.basename(image_path)
                fallback_dir = '/tmp/denker_workspace/default'
                candidate_path = os.path.join(fallback_dir, filename_only)
                if os.path.exists(candidate_path):
                    image_path = candidate_path
                    logger.info(f"Found image via fallback temp workspace: {image_path}")
    
    if not os.path.exists(image_path):
        return {
            "success": False,
            "error": f"Image file not found: {image_path}",
            "note": "Make sure the image is downloaded to workspace first using search_and_download_photo or create_chart"
        }
    
    # Simple validation - just check if file is not empty and can be opened
    try:
        file_size = os.path.getsize(image_path)
        if file_size < 100:  # Very basic check - less than 100 bytes is definitely empty
            return {
                "success": False,
                "error": f"Image file too small ({file_size} bytes), likely empty",
                "file_size": file_size
            }
        
        # Try to open the image to ensure it's a valid image file
        try:
            from PIL import Image
            with Image.open(image_path) as img:
                width, height = img.size
                logger.info(f"Image validation passed: {image_path} ({file_size} bytes, {width}x{height})")
        except ImportError:
            logger.warning("PIL not available, skipping image format validation")
        except Exception as img_error:
            return {
                "success": False,
                "error": f"Cannot open image file (corrupted or invalid format): {str(img_error)}",
                "file_size": file_size
            }
            
    except Exception as e:
        logger.warning(f"Error during basic image validation: {e}")
        # Continue with basic existence check
    
    # For workspace files, use simple filename-only relative path
    image_relative_path = os.path.basename(image_path)
    
    # Check if both files are in the same workspace directory
    md_dir = os.path.dirname(os.path.abspath(file_path))
    img_dir = os.path.dirname(os.path.abspath(image_path))
    
    if md_dir == img_dir:
        # Same directory - use filename only
        image_relative_path = os.path.basename(image_path)
        logger.info(f"Same directory detected, using filename: {image_relative_path}")
    else:
        # Different directories - calculate relative path
        try:
            image_relative_path = os.path.relpath(image_path, md_dir)
            logger.info(f"Different directories, calculated relative path: {image_relative_path}")
            
            # If relative path goes up directories (../) but ends in same filename,
            # prefer simple filename for workspace consistency
            if image_relative_path.count('../') > 0 and os.path.basename(image_relative_path) == os.path.basename(image_path):
                logger.info(f"Using simple filename instead of complex relative path for workspace consistency")
                image_relative_path = os.path.basename(image_path)
        except Exception as e:
            logger.warning(f"Could not calculate relative path: {e}")
            # Fallback to just the filename
            image_relative_path = os.path.basename(image_path)
    
    # Create markdown image syntax
    image_md = f"![{alt_text}]({image_relative_path})"
    
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
        # Auto-detect best position when none provided
        try:
            # Get image description from alt_text if available, otherwise use generic description
            image_description = alt_text if alt_text else "Image for document"
            
            # Get position suggestions
            suggestions_result = suggest_image_positions(file_path, image_description, alt_text)
            
            if suggestions_result.get("success") and suggestions_result.get("suggestions"):
                # Use the first (best) suggestion
                best_position = suggestions_result["suggestions"][0]["position"]
                logger.info(f"Auto-detected best position for image: line {best_position} - {suggestions_result['suggestions'][0]['explanation']}")
                
                return edit_markdown(file_path, [
                    {
                        "type": "insert_at_line",
                        "line_number": best_position,
                        "text": image_md
                    }
                ])
            else:
                logger.warning("Could not auto-detect position, falling back to append")
                # Fallback to appending if auto-detection fails
                return append_to_markdown(file_path, f"\n\n{image_md}\n")
        except Exception as e:
            logger.warning(f"Error during auto-detection of image position: {e}, falling back to append")
            # Fallback to appending if any error occurs
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
    # Try to resolve source file path from workspace
    resolved_source = find_workspace_file(source_file)
    if resolved_source:
        source_file = resolved_source
        logger.info(f"Resolved source file path from workspace: {source_file}")
    
    return convert_to_markdown(source_file, output_path)

@app.tool()
def convert_from_md(markdown_file: str, output_format: str, output_path: Optional[str] = None, options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Convert a Markdown document to another format (PDF, DOCX, HTML, JSON, TXT, XLSX).
    
    Args:
        markdown_file: Path to the Markdown file
        output_format: Target format (pdf, docx, html, json, txt, xlsx, text, excel)
        output_path: Optional path for the output file
        options: Optional format-specific conversion options
        
    Returns:
        Information about the converted file
    """
    # Try to resolve markdown file path from workspace
    resolved_markdown = find_workspace_file(markdown_file)
    if resolved_markdown:
        markdown_file = resolved_markdown
        logger.info(f"Resolved markdown file path from workspace: {markdown_file}")
    
    return convert_from_markdown(markdown_file, output_format, output_path, options)

# @app.tool()
# def preview(file_path: str, format: str = "html") -> Dict[str, Any]:
#     """
#     Generate a preview of a Markdown document.
#     
#     Args:
#         file_path: Path to the Markdown file
#         format: Preview format (html or text)
#         
#     Returns:
#         Preview content
#     """
#     # Try to resolve file path from workspace
#     resolved_path = find_workspace_file(file_path)
#     if resolved_path:
#         file_path = resolved_path
#         logger.info(f"Resolved file path from workspace: {file_path}")
#     
#     return preview_markdown(file_path, format)

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
    # Try to resolve file path from workspace
    resolved_path = find_workspace_file(file_path)
    if resolved_path:
        file_path = resolved_path
        logger.info(f"Resolved file path from workspace: {file_path}")
    
    return start_live_preview(file_path, port)

@app.tool()
async def add_chart(markdown_file: str, chart_data: Dict[str, Any], position: Optional[int] = None, alt_text: str = "Chart") -> Dict[str, Any]:
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
    # Try to resolve markdown file path from workspace
    resolved_markdown = find_workspace_file(markdown_file)
    if resolved_markdown:
        markdown_file = resolved_markdown
        logger.info(f"Resolved markdown file path from workspace: {markdown_file}")
    
    return await add_chart_to_markdown(markdown_file, chart_data, position, alt_text)

@app.tool()
async def extract_table(markdown_file: str, table_index: int = 0) -> Dict[str, Any]:
    """
    Extract tabular data from a Markdown document.
    
    Args:
        markdown_file: Path to the Markdown file
        table_index: Index of the table to extract (0-based)
        
    Returns:
        Extracted table data
    """
    # Try to resolve markdown file path from workspace
    resolved_markdown = find_workspace_file(markdown_file)
    if resolved_markdown:
        markdown_file = resolved_markdown
        logger.info(f"Resolved markdown file path from workspace: {markdown_file}")
    
    return await extract_table_from_markdown(markdown_file, table_index)

@app.tool()
async def create_table_with_theme(
    headers: List[str],
    data: List[List[str]],
    title: Optional[str] = None,
    theme: str = "professional",
    alignment: Optional[List[str]] = None,
    file_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create a beautifully themed table in Markdown format.
    
    Args:
        headers: List of column headers
        data: List of rows, where each row is a list of cell values
        title: Optional title for the table
        theme: Theme to apply ('modern', 'elegant', 'minimal', 'bold', 'colorful', 'professional')
        alignment: Optional list of alignments for each column ('left', 'center', 'right')
        file_path: Optional filename to save the table (like "table.md") - workspace only
        
    Returns:
        Information about the created table
    """
    try:
        from .table_generator import create_themed_table
        
        # Create the themed table
        table_result = await create_themed_table(
            headers=headers,
            data=data,
            title=title,
            theme=theme,
            alignment=alignment
        )
        
        if not table_result.get("success"):
            return table_result
        
        table_markdown = table_result["markdown"]
        
        # If file_path is provided, save to workspace
        if file_path:
            if not file_path:
                # Generate filename from title or use default
                import re
                if title:
                    clean_title = re.sub(r'[^\w\s-]', '', title)
                    clean_title = re.sub(r'[-\s]+', '-', clean_title).strip('-')
                    filename = f"{clean_title}_table.md"
                else:
                    filename = "table.md"
                file_path = filename
            
            # Create document with the table
            doc_result = create_markdown(table_markdown, file_path)
            
            if doc_result.get("success"):
                return {
                    "success": True,
                    "markdown": table_markdown,
                    "file_path": doc_result["file_path"],
                    "full_path": doc_result.get("full_path"),
                    "file_id": doc_result.get("file_id"),
                    "theme": theme,
                    "rows": len(data),
                    "columns": len(headers),
                    "message": f"Themed table created successfully with {theme} theme"
                }
            else:
                return doc_result
        else:
            # Return just the markdown
            return {
                "success": True,
                "markdown": table_markdown,
                "theme": theme,
                "rows": len(data),
                "columns": len(headers),
                "message": f"Themed table generated successfully with {theme} theme"
            }
            
    except Exception as e:
        logger.error(f"Error creating themed table: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

@app.tool()
async def get_table_themes() -> Dict[str, Any]:
    """
    Get available table themes and their descriptions.
    
    Returns:
        Dictionary containing available table themes and examples
    """
    try:
        from .table_generator import get_available_table_themes
        return await get_available_table_themes()
    except Exception as e:
        logger.error(f"Error getting table themes: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

@app.tool()
async def create_chart(chart_config: Dict[str, Any], 
                      output_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Create a chart using Plotly and save it as an image.
    
    ⚠️ IMPORTANT: This function ALWAYS creates files in the workspace only.
    To output to user folders, use the filesystem tool to move the file after creation.
    
    Args:
        chart_config: Chart configuration dictionary
        output_path: Optional filename to save chart (like "chart.png") - no subdirectories, workspace only
        
    Returns:
        Information about the created chart file
    """
    from .chart_generator import ChartGenerator
    
    generator = ChartGenerator()
    result = await generator.create_chart(chart_config, output_path)
    
    # Register in shared workspace if successful
    if result.get("success"):
        # Chart generator returns 'chart_path' and 'filename' - both are just filenames
        chart_file = result.get("chart_path") or result.get("filename")
        if chart_file:
            full_path = get_workspace_path(chart_file)
            file_id = register_workspace_file(
                file_path=full_path,
                metadata={
                    "type": "chart_image",
                    "chart_type": chart_config.get("type", "unknown"),
                    "format": "png"
                }
            )
            if file_id:
                result["file_id"] = file_id
                result["message"] = result.get("message", "") + f" (Workspace ID: {file_id})"
            
            # Standardize the return field as 'file_path' for consistency with other tools
            result["file_path"] = chart_file
    
    return result

@app.tool()
async def create_chart_from_data(chart_type: str,
                               data: List[Dict[str, Any]],
                               x_axis: str,
                               y_axis: str,
                                title: Optional[str] = None,
                               output_path: Optional[str] = None,
                               color_theme: str = 'professional',
                               style_theme: str = 'elegant') -> Dict[str, Any]:
    """
    Create a chart from tabular data with beautiful styling.
    
    Args:
        chart_type: Type of chart (bar, line, pie, etc.)
        data: List of data objects
        x_axis: Field name for x-axis
        y_axis: Field name for y-axis  
        title: Optional chart title
        output_path: Optional output file path
        color_theme: Color theme (modern, professional, pastel, vibrant, ocean, sunset, forest)
        style_theme: Style theme (modern, elegant, minimal, bold)
        
    Returns:
        Information about the created chart
    """
    try:
        # Convert tabular data to Chart.js format
        labels = [str(item.get(x_axis, '')) for item in data]
        values = [float(item.get(y_axis, 0)) for item in data]
        
        chart_data = {
            'labels': labels,
            'datasets': [{
                'label': y_axis,
                'data': values
            }]
        }
        
        # Use the chart generator with beautiful theming
        from mcp_local.servers.markdown_editor.chart_generator import create_chart_from_data_tool
        
        result = await create_chart_from_data_tool(
            chart_type=chart_type,
            data=chart_data,
            title=title,
            filename=output_path,
            color_theme=color_theme,
            style_theme=style_theme
        )
        
        if result.get('success'):
            logger.info(f"Created beautiful {chart_type} chart with {color_theme} theme: {result.get('chart_path')}")
        
        return result
        
    except Exception as e:
        logger.error(f"Failed to create chart from data: {e}")
        return {
            'success': False,
            'error': str(e)
        }

@app.tool()
def get_chart_template(chart_type: str) -> Dict[str, Any]:
    """
    Get a template configuration for a specific chart type.
    
    Args:
        chart_type: Type of chart (bar, line, pie, doughnut)
        
    Returns:
        Template configuration that can be customized and used with create_chart
    """
    return get_chart_template_tool(chart_type)

@app.tool()
async def search_photos(query: str, 
                       per_page: int = 10, 
                       orientation: Optional[str] = None,
                       color: Optional[str] = None,
                       category: Optional[str] = None) -> Dict[str, Any]:
    """
    Search for photos on Unsplash (for browsing only - use search_and_download_photo for actual use).
    
    Args:
        query: Search query
        per_page: Number of results (max 30)
        orientation: "landscape", "portrait", or "squarish"
        color: Color filter like "black_and_white", "black", "white", "yellow", "orange", "red", "purple", "magenta", "green", "teal", "blue"
        category: Category hint for better results
        
    Returns:
        Search results with photo IDs and metadata
    """
    return await search_photos_tool(query, per_page=per_page, orientation=orientation, color=color, category=category)

@app.tool()
async def download_photo(photo_id: str, 
                        size: str = "regular",
                        file_name: Optional[str] = None,
                        add_credit: bool = True) -> Dict[str, Any]:
    """
    Download a specific photo by ID from Unsplash search results.
    
    Args:
        photo_id: Unique ID of the photo from search results
        size: Photo size - "raw", "full", "regular", "small", "thumb" (default: "regular")
        file_name: Optional custom filename (will use photo description if not provided)
        add_credit: Whether to add photographer credit to filename (default: True)
        
    Returns:
        Information about the downloaded photo including local path
    """
    return await download_photo_tool(photo_id, size, file_name, add_credit)

@app.tool()
def get_photo_categories() -> Dict[str, Any]:
    """
    Get available photo categories for filtering searches.
    
    Returns:
        List of available photo categories and search tips
    """
    return get_photo_categories_tool()

@app.tool()
async def search_and_download_photo(query: str,
                                   size: str = "regular",
                                   orientation: Optional[str] = None,
                                   category: Optional[str] = None,
                                   filename: Optional[str] = None) -> Dict[str, Any]:
    """
    🎯 RECOMMENDED: Search for and download a photo in one step (like chart generation).
    This is the preferred tool for getting images for documents.
    
    Args:
        query: Search query for the photo (be descriptive for better results)
        size: Photo size - "thumbnail", "small", "regular", "large", "full" (default: "regular")
        orientation: Photo orientation - "landscape", "portrait", "squarish" (optional)
        category: Photo category hint - "nature", "business", "technology", "lifestyle", "architecture", "abstract"
        filename: Custom filename (will generate descriptive name if not provided)
        
    Returns:
        Downloaded photo information with filename for use in documents
        
    Usage:
        1. Use this tool to get a photo: photo = await search_and_download_photo("business meeting")
        2. Use add_image tool to add it to document: add_image("document.md", photo["file_path"], "Business meeting photo")
    """
    return await search_and_download_photo_tool(query, size, orientation, category, filename)

@app.tool()
async def create_document_with_chart(content: str,
                                   chart_config: Dict[str, Any],
                                    file_path: Optional[str] = None,
                                   chart_position: str = "end") -> Dict[str, Any]:
    """
    Create a Markdown document with an embedded chart.
    
    ⚠️ IMPORTANT: This function ALWAYS creates files in the workspace only.
    To output to user folders, first create in workspace, then use convert_from_md.
    
    Args:
        content: Markdown content
        chart_config: Chart configuration dictionary
        file_path: Optional filename for the document (like "report.md") - no subdirectories, workspace only
        chart_position: Where to place the chart ("start", "end", or line number)
        
    Returns:
        Information about the created document
    """
    from .chart_generator import ChartGenerator
    from .markdown_integration import create_chart_from_markdown_data
    
    try:
        # First create the chart
        generator = ChartGenerator()
        chart_result = await generator.create_chart(chart_config)
        
        if not chart_result.get("success"):
            return chart_result
        
        # Chart generator returns 'chart_path' and 'filename' - both are just filenames
        chart_file = chart_result.get("chart_path") or chart_result.get("filename")
        if not chart_file:
            return {
                "success": False,
                "error": "Chart creation succeeded but no filename returned"
            }
        
        # Create the markdown document
        if chart_position == "start":
            full_content = f"![Chart]({chart_file})\n\n{content}"
        elif chart_position == "end":
            full_content = f"{content}\n\n![Chart]({chart_file})"
        else:
            # Try to insert at specific line
            try:
                line_num = int(chart_position)
                lines = content.split('\n')
                lines.insert(line_num, f"![Chart]({chart_file})")
                full_content = '\n'.join(lines)
            except (ValueError, IndexError):
                # Fallback to end if line number is invalid
                full_content = f"{content}\n\n![Chart]({chart_file})"
        
        # Create the document
        doc_result = create_markdown(full_content, file_path)
        
        if doc_result.get("success"):
            # Register both files
            chart_full_path = get_workspace_path(chart_file)
            doc_full_path = get_workspace_path(doc_result["file_path"])
            
            chart_id = register_workspace_file(
                file_path=chart_full_path,
                metadata={"type": "chart_image", "chart_type": chart_config.get("type", "unknown")}
            )
            
            doc_id = register_workspace_file(
                file_path=doc_full_path,
                metadata={
                    "type": "markdown_document_with_chart",
                    "linked_chart": chart_file,
                    "chart_position": chart_position
                }
            )
            
            doc_result["chart_file"] = chart_file
            if chart_id and doc_id:
                doc_result["file_id"] = doc_id
                doc_result["chart_id"] = chart_id
                doc_result["message"] += f" with chart (Doc ID: {doc_id}, Chart ID: {chart_id})"
        
        return doc_result
        
    except Exception as e:
        logger.error(f"Error creating document with chart: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

@app.tool()
def get_filesystem_path(file_reference: str) -> Dict[str, Any]:
    """
    Get filesystem-compatible relative path for a workspace file reference.
    
    This tool bridges markdown-editor workspace files with filesystem server operations.
    Returns relative paths suitable for use with filesystem tools like get_file_info, move_file, etc.
    
    Args:
        file_reference: File ID, filename, or partial path from workspace
        
    Returns:
        Filesystem-compatible relative path information for cross-server operations
    """
    logger.info(f"[get_filesystem_path] Looking for workspace file: {file_reference}")
    
    if SHARED_WORKSPACE_AVAILABLE:
        try:
            workspace = get_shared_workspace()
            
            # Get absolute path
            absolute_path = workspace.find_file(file_reference)
            
            # Get filesystem-friendly relative path 
            relative_path = workspace.get_filesystem_friendly_path(file_reference)
            
            if absolute_path and relative_path:
                logger.info(f"[get_filesystem_path] Found workspace file: {relative_path}")
                
                return {
                    "success": True,
                    "relative_path": relative_path,
                    "workspace_root": str(workspace.workspace_root),
                    "filename": os.path.basename(str(absolute_path)),
                    "exists_in_workspace": True,
                    "usage": f"Use with filesystem tools like: filesystem.get_file_info('{relative_path}')"
                }
        except Exception as e:
            logger.warning(f"Could not access shared workspace: {e}")
    
    # Fallback to unified temp workspace 
    filename_only = os.path.basename(file_reference)
    fallback_dir = '/tmp/denker_workspace/default'
    
    if os.path.exists(os.path.join(fallback_dir, filename_only)):
        logger.info(f"[get_filesystem_path] Found in temp workspace: {filename_only}")
        return {
            "success": True,
            "relative_path": filename_only,
            "workspace_root": fallback_dir,
            "filename": filename_only,
            "exists_in_workspace": True,
            "usage": f"Use with filesystem tools like: filesystem.get_file_info('{filename_only}')"
        }
    else:
        logger.info(f"[get_filesystem_path] File not found in workspace: {file_reference}")
        return {
            "success": False,
            "error": f"File not found in workspace: {file_reference}",
            "note": "File must exist in workspace before getting filesystem path"
        }

@app.tool()
def analyze_document_structure(file_path: str) -> Dict[str, Any]:
    """
    Analyze the structure of a markdown document to help with content placement decisions.
    
    Args:
        file_path: Path to the Markdown file or workspace file ID
        
    Returns:
        Document structure analysis including headers, sections, and line information
    """
    # Try to resolve file path from workspace
    resolved_file_path = find_workspace_file(file_path)
    if resolved_file_path:
        file_path = resolved_file_path
        logger.info(f"Resolved markdown file path from workspace: {file_path}")
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            lines = content.splitlines()
    except Exception as e:
        return {
            "success": False,
            "error": f"Could not read markdown file: {str(e)}"
        }
    
    # Analyze document structure
    headers = []
    sections = []
    current_section = None
    
    for i, line in enumerate(lines):
        stripped = line.strip()
        
        # Detect headers
        if stripped.startswith('#'):
            level = len(line) - len(line.lstrip('#'))
            header_text = stripped.lstrip('#').strip()
            
            header_info = {
                'line_number': i,
                'level': level,
                'text': header_text,
                'line_content': line
            }
            headers.append(header_info)
            
            # End previous section and start new one
            if current_section:
                current_section['end_line'] = i - 1
                current_section['line_count'] = current_section['end_line'] - current_section['start_line'] + 1
                sections.append(current_section)
            
            current_section = {
                'header': header_info,
                'start_line': i,
                'content_start_line': i + 1,
                'end_line': len(lines) - 1,  # Will be updated when next section starts
                'preview': ''
            }
    
    # Close last section
    if current_section:
        current_section['end_line'] = len(lines) - 1
        current_section['line_count'] = current_section['end_line'] - current_section['start_line'] + 1
        sections.append(current_section)
    
    # Add content previews to sections
    for section in sections:
        content_lines = lines[section['content_start_line']:min(section['content_start_line'] + 3, section['end_line'] + 1)]
        section['preview'] = '\n'.join(content_lines).strip()
    
    # Document statistics
    total_lines = len(lines)
    non_empty_lines = len([line for line in lines if line.strip()])
    
    return {
        "success": True,
        "file_path": file_path,
        "total_lines": total_lines,
        "non_empty_lines": non_empty_lines,
        "headers": headers,
        "sections": sections,
        "document_preview": '\n'.join(lines[:5]).strip() + ('...' if len(lines) > 5 else ''),
        "analysis": {
            "has_clear_structure": len(headers) > 0,
            "main_sections": len([h for h in headers if h['level'] <= 2]),
            "subsections": len([h for h in headers if h['level'] > 2]),
            "estimated_reading_sections": len(sections)
        }
    }

@app.tool()
def suggest_image_positions(file_path: str, image_description: str, image_alt_text: str = "") -> Dict[str, Any]:
    """
    Suggest potential positions for inserting an image based on document analysis and image context.
    
    Args:
        file_path: Path to the Markdown file or workspace file ID
        image_description: Description of what the image shows (for context matching)
        image_alt_text: Alternative text for the image
        
    Returns:
        Suggested positions with explanations for each suggestion
    """
    # First analyze the document structure
    structure_analysis = analyze_document_structure(file_path)
    
    if not structure_analysis.get("success"):
        return structure_analysis
    
    suggestions = []
    
    # Try to resolve file path from workspace
    resolved_file_path = find_workspace_file(file_path)
    if resolved_file_path:
        file_path = resolved_file_path
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.read().splitlines()
    except Exception as e:
        return {
            "success": False,
            "error": f"Could not read markdown file: {str(e)}"
        }
    
    sections = structure_analysis.get("sections", [])
    headers = structure_analysis.get("headers", [])
    
    # Suggestion 1: After document title/introduction
    if headers:
        first_header = headers[0]
        if first_header['level'] == 1:  # Main title
            suggestions.append({
                "position": first_header['line_number'] + 2,
                "location": "After document title",
                "explanation": f"Place after the main title '{first_header['text']}' to serve as a lead image",
                "context": "Introduction/Overview"
            })
    else:
        suggestions.append({
            "position": 1,
            "location": "Beginning of document",
            "explanation": "Place at the beginning since no clear title structure was found",
            "context": "Introduction"
        })
    
    # Suggestion 2: After first main section
    main_sections = [s for s in sections if s['header']['level'] <= 2]
    if len(main_sections) > 1:
        second_section = main_sections[1]
        suggestions.append({
            "position": second_section['header']['line_number'] + 2,
            "location": f"In section: {second_section['header']['text']}",
            "explanation": f"Place in the '{second_section['header']['text']}' section",
            "context": "Main content section"
        })
    
    # Suggestion 3: Middle of document
    if len(lines) > 10:
        middle_line = len(lines) // 2
        # Find nearest section boundary around middle
        for section in sections:
            if section['start_line'] <= middle_line <= section['end_line']:
                suggestions.append({
                    "position": section['content_start_line'] + 1,
                    "location": f"Middle of document in section: {section['header']['text']}",
                    "explanation": f"Place in the middle section '{section['header']['text']}' for visual balance",
                    "context": "Middle content"
                })
                break
    
    # Suggestion 4: Before conclusion/end
    if sections:
        last_section = sections[-1]
        if any(word in last_section['header']['text'].lower() for word in ['conclusion', 'summary', 'end', 'final']):
            suggestions.append({
                "position": last_section['header']['line_number'],
                "location": "Before conclusion",
                "explanation": f"Place before the conclusion section '{last_section['header']['text']}'",
                "context": "Pre-conclusion"
            })
        else:
            # Just suggest end of content
            suggestions.append({
                "position": len(lines) - 2,
                "location": "Near end of document",
                "explanation": "Place near the end of the document",
                "context": "Conclusion area"
            })
    
    return {
        "success": True,
        "file_path": file_path,
        "image_description": image_description,
        "image_alt_text": image_alt_text,
        "suggestions": suggestions,
        "document_structure": {
            "total_sections": len(sections),
            "total_lines": len(lines),
            "has_clear_structure": len(headers) > 0
        },
        "recommendation": "Review the suggestions and choose the position that best fits the image content and document flow. Consider the image's relevance to each section."
    }

# @app.tool()
# def add_image_at_position(file_path: str, image_path: str, position: int, alt_text: str = "") -> Dict[str, Any]:
#     """
#     Add an image to a specific position in a markdown document.
#     
#     Args:
#         file_path: Path to the Markdown file or workspace file ID
#         image_path: Path to the image file or workspace file ID
#         position: Line number (1-based) to insert the image at
#         alt_text: Alternative text for the image
#         
#     Returns:
#         Information about the updated file
#     """
#     # Convert to 0-based indexing for internal use
#     zero_based_position = max(0, position - 1)
#     
#     # Use the existing add_image function but with explicit position
#     return add_image(file_path, image_path, alt_text, zero_based_position)

def main():
    """Entry point for the Markdown Editor MCP server script."""
    logger.info("Starting Markdown Editor MCP server via main()")
    try:
        app.run(transport="stdio")  # Or your preferred transport
    except Exception as e:
        logger.error(f"Error starting Markdown Editor server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 