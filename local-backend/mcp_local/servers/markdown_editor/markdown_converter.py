"""
Markdown conversion utilities for the Markdown Editor MCP server.
Provides functions to convert between Markdown and other formats.
"""

import os
import sys
import tempfile
import subprocess
import logging
from typing import Dict, Any, Optional, List
from enum import Enum
from pathlib import Path
from utils.resource_utils import get_bundled_binary_path
from datetime import datetime

logger = logging.getLogger("markdown-editor")

# Try to import shared workspace for secure path operations
try:
    from core.shared_workspace import get_shared_workspace
    SHARED_WORKSPACE_AVAILABLE = True
except ImportError:
    SHARED_WORKSPACE_AVAILABLE = False

def get_allowed_user_directories() -> List[Path]:
    """
    Get allowed directories from user settings only. No default directories.
    
    Returns:
        List of user-configured allowed directory paths (empty if none configured)
    """
    allowed_dirs = []
    
    # Try to get user-configured allowed directories
    try:
        import json
        import os
        
        # Get user settings file path (same as global coordinator)
        user_settings_path = os.environ.get("DENKER_USER_SETTINGS_PATH", "./denker_user_settings.json")
        
        if os.path.exists(user_settings_path):
            with open(user_settings_path, 'r') as f:
                user_settings = json.load(f)
            
            user_accessible_folders = user_settings.get('accessibleFolders', [])
            if isinstance(user_accessible_folders, list):
                for folder_str in user_accessible_folders:
                    try:
                        folder_path = Path(folder_str).resolve()
                        if folder_path.exists() and folder_path.is_dir():
                            allowed_dirs.append(folder_path)
                    except Exception as e:
                        logger.warning(f"Invalid user directory {folder_str}: {e}")
            
            if allowed_dirs:
                logger.info(f"[get_allowed_user_directories] Loaded {len(allowed_dirs)} directories from user settings")
            else:
                logger.info(f"[get_allowed_user_directories] No accessible folders configured in user settings")
        else:
            logger.info(f"[get_allowed_user_directories] User settings file not found: {user_settings_path}")
            
    except Exception as e:
        logger.warning(f"Could not load user accessible folders: {e}")
    
    # Only return user-configured directories - no defaults
    logger.info(f"[get_allowed_user_directories] Loaded {len(allowed_dirs)} user-configured directories")
    return allowed_dirs

def validate_output_path(output_path: str) -> tuple[str, str]:
    """
    Validate and secure the output path to prevent unauthorized file access.
    Uses user settings for allowed directories with clear messaging.
    
    Args:
        output_path: Requested output path
        
    Returns:
        tuple[validated_path, status_message]: The secured path and a message for the agent
        
    Raises:
        ValueError: If the path is outside allowed directories and cannot be redirected
    """
    if not output_path:
        raise ValueError("Output path cannot be empty")
    
    output_path_obj = Path(output_path).resolve()
    original_requested = str(output_path_obj)
    
    # Get allowed directories from user settings
    allowed_user_directories = get_allowed_user_directories()
    
    # Check if the output path is in an allowed user directory
    for allowed_dir in allowed_user_directories:
        try:
            if output_path_obj.parent == allowed_dir or output_path_obj.is_relative_to(allowed_dir):
                logger.info(f"[validate_output_path] ✅ Allowing user directory: {output_path}")
                # Ensure the directory exists
                output_path_obj.parent.mkdir(parents=True, exist_ok=True)
                return str(output_path_obj), f"✅ File will be saved to: {output_path_obj}"
        except Exception as e:
            logger.warning(f"Could not check allowed directory {allowed_dir}: {e}")
            continue
    
    # Path not in allowed directories - redirect to workspace for security
    logger.info(f"[validate_output_path] ⚠️ Path {original_requested} not in allowed directories")
    
    # Check if we have shared workspace (preferred for security)
    if SHARED_WORKSPACE_AVAILABLE:
        try:
            workspace = get_shared_workspace()
            workspace_root = workspace.workspace_root.resolve()
            
            # Redirect to workspace root with filename only for security and consistency
            filename = output_path_obj.name if output_path_obj.name else "output"
            secure_path = workspace_root / filename
            
            if allowed_user_directories:
                allowed_dirs_str = ", ".join(str(d) for d in allowed_user_directories)
                redirect_msg = (f"🔄 Security: Redirected from '{original_requested}' to workspace: '{secure_path}'. "
                              f"Currently allowed directories: [{allowed_dirs_str}]. "
                              f"To save to your desired location, add the parent directory to your "
                              f"accessible folders in Settings.")
            else:
                redirect_msg = (f"🔄 Security: Redirected from '{original_requested}' to workspace: '{secure_path}'. "
                              f"No accessible folders configured. "
                              f"To save to your desired location, add directories to your accessible folders in Settings.")
            
            logger.info(f"[validate_output_path] Redirecting to workspace: {output_path} -> {secure_path}")
            return str(secure_path), redirect_msg
                
        except Exception as e:
            logger.warning(f"Could not use shared workspace for validation: {e}")
    
    # FIXED: Always use unified temp workspace as fallback
    try:
        from mcp_local.core.shared_workspace import SharedWorkspaceManager
        temp_workspace = SharedWorkspaceManager._get_unified_workspace_path("default")
        logger.info(f"[validate_output_path] Using unified temp workspace path: {temp_workspace}")
    except Exception as e:
        logger.warning(f"Could not get unified workspace path: {e}")
        temp_workspace = Path("/tmp/denker_workspace/default")
        temp_workspace.mkdir(parents=True, exist_ok=True)
    
    temp_workspace.mkdir(parents=True, exist_ok=True)
    filename = output_path_obj.name if output_path_obj.name else "output"
    secure_path = temp_workspace / filename
    
    if allowed_user_directories:
        allowed_dirs_str = ", ".join(str(d) for d in allowed_user_directories)
        redirect_msg = (f"🔄 Security: Redirected from '{original_requested}' to workspace: '{secure_path}'. "
                       f"Currently allowed directories: [{allowed_dirs_str}]. "
                       f"To save to your desired location, add the parent directory to your accessible folders in Settings.")
    else:
        redirect_msg = (f"🔄 Security: Redirected from '{original_requested}' to workspace: '{secure_path}'. "
                       f"No accessible folders configured. "
                       f"To save to your desired location, add directories to your accessible folders in Settings.")
    
    logger.info(f"[validate_output_path] Redirecting to unified workspace: {output_path} -> {secure_path}")
    return str(secure_path), redirect_msg

class OutputFormat(Enum):
    MARKDOWN = "markdown"
    HTML = "html"
    PDF = "pdf"
    DOCX = "docx"
    TEXT = "text"

class MarkdownConverter:
    def __init__(self):
        pass

    def convert(self, source_file: str, output_format: OutputFormat, output_path: str = None) -> str:
        if not os.path.exists(source_file):
            logger.error(f"Source file not found: {source_file}")
            raise FileNotFoundError(f"Source file not found: {source_file}")

        if output_path is None:
            # Create a temporary file for the output
            temp_dir = tempfile.mkdtemp()
            # Use a more descriptive extension based on the output format
            file_ext = f".{output_format.value}"
            if output_format == OutputFormat.MARKDOWN and source_file.endswith(".md"):
                 # if converting md to md (e.g. for cleaning), use a different name
                 output_path = os.path.join(temp_dir, f"{os.path.basename(source_file)}_converted{file_ext}")
            else:
                 output_path = os.path.join(temp_dir, f"{os.path.splitext(os.path.basename(source_file))[0]}{file_ext}")
        else:
            # Ensure output directory exists if a full path is given
            os.makedirs(os.path.dirname(output_path), exist_ok=True)

        logger.info(f"Converting {source_file} to {output_path} (format: {output_format.value})")

        # Determine source file extension for specific input handling
        _, source_ext = os.path.splitext(source_file)
        source_ext = source_ext.lower()

        # Get path to pandoc executable
        pandoc_exe = get_bundled_binary_path("pandoc")

        # Prepare Pandoc command
        # Basic command: pandoc source -o output --to <format>
        cmd = [pandoc_exe, source_file, '-o', output_path, '--to', output_format.value]

        # Add format-specific options for INPUT formats
        if source_ext == '.docx' or source_ext == '.doc':
            cmd.extend(['--extract-media', os.path.dirname(output_path)]) # Extract media when source is docx
        elif source_ext == '.html' or source_ext == '.htm':
            cmd.insert(1, '--from') # Insert after pandoc_exe
            cmd.insert(2, 'html') # Specify HTML as source format for Pandoc

        # Note: If converting TO PDF, pandoc might need a --pdf-engine like xelatex, weasyprint etc.
        # This example assumes a default PDF engine is available or not strictly creating PDFs here.
        # If source_ext is '.pdf', pandoc will attempt to read it. It might use pdftotext internally.

        logger.info(f"Executing Pandoc command: {' '.join(cmd)}")

        # Prepare environment for subprocess: ensure our bundled bin is on PATH
        # so pandoc can find helper tools like pdftotext if it needs them.
        env = os.environ.copy()
        if getattr(sys, 'frozen', False): # PyInstaller bundle
            bundled_bin_dir = os.path.abspath(os.path.join(os.path.dirname(sys.executable), '..', 'bin'))
            if os.path.isdir(bundled_bin_dir):
                env["PATH"] = bundled_bin_dir + os.pathsep + env.get("PATH", "")
                logger.info(f"Temporarily added to PATH for subprocess: {bundled_bin_dir}")

        try:
            process = subprocess.run(cmd, capture_output=True, text=True, check=False, env=env)
            if process.returncode != 0:
                logger.error(f"Pandoc conversion failed. Return code: {process.returncode}")
                logger.error(f"Pandoc STDOUT: {process.stdout}")
                logger.error(f"Pandoc STDERR: {process.stderr}")
                # Try to read source_file if conversion failed, maybe it's already plain text
                if os.path.exists(source_file):
                    with open(source_file, 'r', encoding='utf-8', errors='ignore') as f_in:
                        return f_in.read()
                raise Exception(f"Pandoc conversion error: {process.stderr}")
            
            logger.info(f"Pandoc conversion successful. Output at: {output_path}")
            # Read the converted content from the output file
            with open(output_path, 'r', encoding='utf-8', errors='ignore') as f_out:
                converted_content = f_out.read()
            
            return converted_content

        except FileNotFoundError as e:
            logger.error(f"Pandoc executable not found or other FileNotFoundError: {e}. Ensure Pandoc is installed and accessible.")
            # Fallback: try to read the source file directly as plain text
            if os.path.exists(source_file):
                with open(source_file, 'r', encoding='utf-8', errors='ignore') as f_in:
                    return f_in.read()
            raise
        except Exception as e:
            logger.error(f"An unexpected error occurred during conversion: {e}")
            # Fallback
            if os.path.exists(source_file):
                with open(source_file, 'r', encoding='utf-8', errors='ignore') as f_in:
                    return f_in.read()
            raise
        finally:
            # Clean up temporary output file if it was created by this method
            if output_path.startswith(tempfile.gettempdir()) and os.path.exists(output_path):
                try:
                    os.remove(output_path)
                    # Clean up temp directory if it's empty
                    temp_dir_path = os.path.dirname(output_path)
                    if not os.listdir(temp_dir_path):
                        os.rmdir(temp_dir_path)
                except OSError as e_clean:
                    logger.warning(f"Could not remove temporary file/dir: {e_clean}")

def convert_to_markdown(source_file: str, output_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Convert a document (DOCX, PDF, HTML) to Markdown.
    
    Args:
        source_file: Path to the source document
        output_path: Optional path for the output Markdown file (will be validated for security)
        
    Returns:
        Information about the converted file
    """
    try:
        if not os.path.exists(source_file):
            return {
                "success": False,
                "error": f"Source file not found: {source_file}"
            }
        
        # Determine source file type
        base_name, ext = os.path.splitext(source_file)
        ext = ext.lower()
        
        # Create output path if not provided
        if not output_path:
            output_path = os.path.splitext(source_file)[0] + '.md'
        
        # SECURITY: Validate output path to prevent unauthorized file access
        security_message = None
        try:
            secure_output_path, security_message = validate_output_path(output_path)
            if secure_output_path != output_path:
                logger.info(f"Output path secured: {output_path} -> {secure_output_path}")
                output_path = secure_output_path
        except ValueError as e:
            return {
                "success": False,
                "error": f"Security error: {str(e)}"
            }
        
        # Check if pandoc is available
        try:
            pandoc_exe = get_bundled_binary_path("pandoc")
            subprocess.run([pandoc_exe, '--version'], check=True, capture_output=True)
        except (subprocess.SubprocessError, FileNotFoundError):
            return {
                "success": False,
                "error": "Pandoc is not installed or not in PATH. Please install pandoc to convert documents."
            }
        
        # Prepare pandoc command
        cmd = [pandoc_exe, source_file, '-o', output_path]
        
        # Add format-specific options
        if ext == '.pdf':
            # PDF requires additional tooling like pdftotext
            pdftotext_exe = get_bundled_binary_path("pdftotext")
            cmd.extend(['--pdf-engine=' + pdftotext_exe])
        elif ext == '.docx' or ext == '.doc':
            # Extract images from docx
            cmd.extend(['--extract-media', os.path.dirname(output_path)])
        elif ext == '.html' or ext == '.htm':
            # Clean up HTML
            cmd.extend(['--from', 'html', '--to', 'markdown'])
        
        # Run conversion
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        
        return {
            "success": True,
            "file_path": output_path,
            "message": f"Successfully converted {source_file} to Markdown",
            "security_note": security_message if security_message else None
        }
        
    except subprocess.CalledProcessError as e:
        error_message = e.stderr if e.stderr else str(e)
        logger.error(f"Error converting to Markdown: {error_message}")
        return {
            "success": False,
            "error": f"Conversion error: {error_message}"
        }
    except Exception as e:
        logger.error(f"Error converting to Markdown: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

def convert_from_markdown(markdown_file: str, output_format: str, output_path: Optional[str] = None, options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Convert a Markdown document to another format (PDF, DOCX, HTML, JSON, TXT, XLSX).
    
    Args:
        markdown_file: Path to the Markdown file
        output_format: Target format (pdf, docx, html, json, txt, xlsx)
        output_path: Optional path for the output file (will be validated for security)
        options: Optional format-specific conversion options
        
    Returns:
        Information about the converted file
    """
    try:
        if not os.path.exists(markdown_file):
            return {
                "success": False,
                "error": f"Markdown file not found: {markdown_file}"
            }
        
        # Normalize output format
        output_format = output_format.lower().strip('.')
        if output_format == 'text':
            output_format = 'txt'
        elif output_format == 'excel':
            output_format = 'xlsx'
        
        # Create output path if not provided
        if not output_path:
            output_path = os.path.splitext(markdown_file)[0] + '.' + output_format
        
        # SECURITY: Validate output path to prevent unauthorized file access
        security_message = None
        try:
            secure_output_path, security_message = validate_output_path(output_path)
            if secure_output_path != output_path:
                logger.info(f"Output path secured: {output_path} -> {secure_output_path}")
                output_path = secure_output_path
        except ValueError as e:
            return {
                "success": False,
                "error": f"Security error: {str(e)}"
            }
        
        # Read markdown content
        with open(markdown_file, 'r', encoding='utf-8') as f:
            markdown_content = f.read()
        
        # Handle special formats that don't use pandoc
        if output_format == 'json':
            return _convert_markdown_to_json(markdown_content, output_path, options)
        elif output_format == 'txt':
            return _convert_markdown_to_txt(markdown_content, output_path, options)
        elif output_format == 'xlsx':
            return _convert_markdown_to_xlsx(markdown_content, output_path, options)
        
        # For standard formats (pdf, docx, html), use pandoc
        # Check if pandoc is available
        try:
            pandoc_exe = get_bundled_binary_path("pandoc")
            subprocess.run([pandoc_exe, '--version'], check=True, capture_output=True)
        except (subprocess.SubprocessError, FileNotFoundError):
            return {
                "success": False,
                "error": "Pandoc is not installed or not in PATH. Please install pandoc to convert documents."
            }
        
        # Prepare pandoc command
        cmd = [pandoc_exe, markdown_file, '-o', output_path]
        
        # Process options and add format-specific settings
        if options is None:
            options = {}
        
        # Add format-specific options
        if output_format == 'pdf':
            # Basic PDF conversion options
            pdf_engine = options.get('pdf_engine', 'wkhtmltopdf')
            cmd.extend(['--pdf-engine', pdf_engine])
            
            # Add CSS styling if provided
            if 'css' in options:
                cmd.extend(['--css', options['css']])
                
        elif output_format == 'docx':
            # Word document options
            if 'reference_doc' in options:
                cmd.extend(['--reference-doc', options['reference_doc']])
                
        elif output_format == 'html':
            # HTML options
            if 'standalone' in options and options['standalone']:
                cmd.append('--standalone')
            if 'css' in options:
                cmd.extend(['--css', options['css']])
        
        # Add metadata options
        if 'metadata' in options:
            for key, value in options['metadata'].items():
                cmd.extend(['--metadata', f'{key}={value}'])
        
        # Add variables
        if 'variables' in options:
            for key, value in options['variables'].items():
                cmd.extend(['--variable', f'{key}={value}'])
        
        logger.info(f"Converting {markdown_file} to {output_path} (format: {output_format})")
        logger.debug(f"Pandoc command: {' '.join(cmd)}")
        
        # Ensure output directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Run conversion
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        
        return {
            "success": True,
            "file_path": output_path,
            "format": output_format,
            "message": f"Successfully converted Markdown to {output_format}",
            "security_note": security_message if security_message else None
        }
        
    except subprocess.CalledProcessError as e:
        error_message = e.stderr if e.stderr else str(e)
        logger.error(f"Error converting from Markdown: {error_message}")
        return {
            "success": False,
            "error": f"Conversion error: {error_message}"
        }
    except Exception as e:
        logger.error(f"Error converting from Markdown: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

def _convert_markdown_to_json(markdown_content: str, output_path: str, options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Convert markdown content to JSON format."""
    import json
    import re
    
    try:
        # Parse markdown into structured data
        lines = markdown_content.split('\n')
        sections = []
        current_section = None
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Check for headers
            if line.startswith('#'):
                if current_section:
                    sections.append(current_section)
                
                level = len(line) - len(line.lstrip('#'))
                title = line.lstrip('#').strip()
                current_section = {
                    "type": "header",
                    "level": level,
                    "title": title,
                    "content": []
                }
            elif line.startswith('- ') or line.startswith('* '):
                # List item
                if not current_section:
                    current_section = {"type": "content", "content": []}
                current_section["content"].append({
                    "type": "list_item",
                    "text": line[2:].strip()
                })
            elif line.startswith('|') and '|' in line[1:]:
                # Table row
                if not current_section:
                    current_section = {"type": "content", "content": []}
                cells = [cell.strip() for cell in line.split('|')[1:-1]]
                current_section["content"].append({
                    "type": "table_row",
                    "cells": cells
                })
            else:
                # Regular paragraph
                if not current_section:
                    current_section = {"type": "content", "content": []}
                current_section["content"].append({
                    "type": "paragraph",
                    "text": line
                })
        
        if current_section:
            sections.append(current_section)
        
        # Create JSON structure
        json_data = {
            "source": "markdown",
            "converted_at": datetime.now().isoformat(),
            "sections": sections,
            "metadata": options.get("metadata", {}) if options else {}
        }
        
        # Write to file
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, indent=2, ensure_ascii=False)
        
        return {
            "success": True,
            "file_path": output_path,
            "format": "json",
            "message": f"Successfully converted Markdown to JSON with {len(sections)} sections"
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"JSON conversion error: {str(e)}"
        }

def _convert_markdown_to_txt(markdown_content: str, output_path: str, options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Convert markdown content to plain text format."""
    import re
    
    try:
        # Remove markdown formatting
        text_content = markdown_content
        
        # Remove markdown syntax
        text_content = re.sub(r'^#+\s*', '', text_content, flags=re.MULTILINE)  # Headers
        text_content = re.sub(r'\*\*(.*?)\*\*', r'\1', text_content)  # Bold
        text_content = re.sub(r'\*(.*?)\*', r'\1', text_content)  # Italic
        text_content = re.sub(r'`(.*?)`', r'\1', text_content)  # Code
        text_content = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text_content)  # Links
        text_content = re.sub(r'!\[([^\]]*)\]\([^\)]+\)', r'\1', text_content)  # Images
        text_content = re.sub(r'^[-*+]\s+', '', text_content, flags=re.MULTILINE)  # Lists
        text_content = re.sub(r'^\d+\.\s+', '', text_content, flags=re.MULTILINE)  # Numbered lists
        text_content = re.sub(r'^\>\s+', '', text_content, flags=re.MULTILINE)  # Blockquotes
        text_content = re.sub(r'\|', ' ', text_content)  # Table separators
        text_content = re.sub(r'^[-\s]*$', '', text_content, flags=re.MULTILINE)  # Table separators
        
        # Clean up extra whitespace
        text_content = re.sub(r'\n\s*\n', '\n\n', text_content)  # Multiple newlines
        text_content = text_content.strip()
        
        # Write to file
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(text_content)
        
        return {
            "success": True,
            "file_path": output_path,
            "format": "txt",
            "message": f"Successfully converted Markdown to plain text ({len(text_content)} characters)"
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"Text conversion error: {str(e)}"
        }

def _convert_markdown_to_xlsx(markdown_content: str, output_path: str, options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Convert markdown content to Excel format."""
    try:
        # Check if pandas and openpyxl are available
        try:
            import pandas as pd
            import re
        except ImportError:
            return {
                "success": False,
                "error": "pandas library not available. Install with: pip install pandas openpyxl"
            }
        
        # Extract tables from markdown
        lines = markdown_content.split('\n')
        tables = []
        current_table = []
        
        for line in lines:
            line = line.strip()
            if line.startswith('|') and '|' in line[1:]:
                # Table row
                cells = [cell.strip() for cell in line.split('|')[1:-1]]
                if cells:  # Skip empty rows
                    current_table.append(cells)
            elif current_table:
                # End of table
                if len(current_table) > 1:  # Must have at least header + one data row
                    tables.append(current_table)
                current_table = []
        
        # Add the last table if exists
        if current_table and len(current_table) > 1:
            tables.append(current_table)
        
        # If no tables found, create a simple text export
        if not tables:
            # Convert to simple text data
            sections = []
            current_section = ""
            
            for line in markdown_content.split('\n'):
                line = line.strip()
                if line.startswith('#'):
                    if current_section:
                        sections.append(current_section)
                    current_section = line.lstrip('#').strip()
                elif line:
                    if current_section:
                        current_section += " | " + line
                    else:
                        current_section = line
            
            if current_section:
                sections.append(current_section)
            
            # Create a simple data structure
            data = [{"Section": i+1, "Content": section} for i, section in enumerate(sections)]
            if not data:
                data = [{"Content": "No structured content found"}]
            
            df = pd.DataFrame(data)
        else:
            # Create Excel file with multiple sheets for multiple tables
            with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
                for i, table in enumerate(tables):
                    headers = table[0]
                    data_rows = table[1:]
                    
                    # Skip separator rows (usually all dashes)
                    data_rows = [row for row in data_rows if not all(cell.replace('-', '').replace(' ', '') == '' for cell in row)]
                    
                    if data_rows:
                        # Create DataFrame
                        df = pd.DataFrame(data_rows, columns=headers)
                        sheet_name = f"Table_{i+1}" if len(tables) > 1 else "Sheet1"
                        df.to_excel(writer, sheet_name=sheet_name, index=False)
                        
                        # Format the sheet
                        worksheet = writer.sheets[sheet_name]
                        
                        # Auto-adjust column widths
                        for column in worksheet.columns:
                            max_length = 0
                            column_letter = column[0].column_letter
                            for cell in column:
                                try:
                                    if len(str(cell.value)) > max_length:
                                        max_length = len(str(cell.value))
                                except:
                                    pass
                            adjusted_width = min(max_length + 2, 50)  # Cap at 50 characters
                            worksheet.column_dimensions[column_letter].width = adjusted_width
                        
                        # Make header row bold
                        from openpyxl.styles import Font
                        header_font = Font(bold=True)
                        for cell in worksheet[1]:  # First row
                            cell.font = header_font
            
            return {
                "success": True,
                "file_path": output_path,
                "format": "xlsx",
                "message": f"Successfully converted Markdown to Excel with {len(tables)} table(s)"
            }
        
        # Single table case - save as simple Excel file
        df.to_excel(output_path, index=False, engine='openpyxl')
        
        return {
            "success": True,
            "file_path": output_path,
            "format": "xlsx",
            "message": f"Successfully converted Markdown to Excel ({len(df)} rows)"
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"Excel conversion error: {str(e)}"
        }

# Additional helper functions

def check_pandoc_installation() -> Dict[str, Any]:
    """
    Check if Pandoc is installed and return version information.
    
    Returns:
        Information about the Pandoc installation
    """
    try:
        pandoc_exe = get_bundled_binary_path("pandoc")
        result = subprocess.run([pandoc_exe, '--version'], check=True, capture_output=True, text=True)
        
        # Parse version from output
        version_line = result.stdout.splitlines()[0] if result.stdout else "Unknown version"
        
        return {
            "installed": True,
            "version": version_line,
            "message": "Pandoc is installed and available"
        }
    except (subprocess.SubprocessError, FileNotFoundError):
        return {
            "installed": False,
            "message": "Pandoc is not installed or not in PATH"
        } 