"""
Markdown conversion utilities for the Markdown Editor MCP server.
Provides functions to convert between Markdown and other formats.
"""

import os
import tempfile
import subprocess
import logging
from typing import Dict, Any, Optional, List

logger = logging.getLogger("markdown-editor")

def convert_to_markdown(source_file: str, output_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Convert a document (DOCX, PDF, HTML) to Markdown.
    
    Args:
        source_file: Path to the source document
        output_path: Optional path for the output Markdown file
        
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
        _, ext = os.path.splitext(source_file)
        ext = ext.lower()
        
        # Create output path if not provided
        if not output_path:
            output_path = os.path.splitext(source_file)[0] + '.md'
        
        # Check if pandoc is available
        try:
            subprocess.run(['pandoc', '--version'], check=True, capture_output=True)
        except (subprocess.SubprocessError, FileNotFoundError):
            return {
                "success": False,
                "error": "Pandoc is not installed or not in PATH. Please install pandoc to convert documents."
            }
        
        # Prepare pandoc command
        cmd = ['pandoc', source_file, '-o', output_path]
        
        # Add format-specific options
        if ext == '.pdf':
            # PDF requires additional tooling like pdftotext
            cmd.append('--pdf-engine=pdftotext')
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
            "message": f"Successfully converted {source_file} to Markdown"
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
    Convert a Markdown document to another format (PDF, DOCX, HTML).
    
    Args:
        markdown_file: Path to the Markdown file
        output_format: Target format (pdf, docx, html)
        output_path: Optional path for the output file
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
        
        # Create output path if not provided
        if not output_path:
            output_path = os.path.splitext(markdown_file)[0] + '.' + output_format
        
        # Check if pandoc is available
        try:
            subprocess.run(['pandoc', '--version'], check=True, capture_output=True)
        except (subprocess.SubprocessError, FileNotFoundError):
            return {
                "success": False,
                "error": "Pandoc is not installed or not in PATH. Please install pandoc to convert documents."
            }
        
        # Prepare pandoc command
        cmd = ['pandoc', markdown_file, '-o', output_path]
        
        # Process options and add format-specific settings
        if options is None:
            options = {}
            
        if output_format == 'pdf':
            # Use specified PDF engine or default to wkhtmltopdf
            pdf_engine = options.get('pdf_engine', 'wkhtmltopdf')
            cmd.extend(['--pdf-engine=' + pdf_engine])
            
            # Add table of contents if requested
            if options.get('toc', False):
                cmd.append('--toc')
                
            # Add specific CSS
            if 'css' in options:
                cmd.extend(['--css', options['css']])
                
        elif output_format == 'docx':
            # Use reference doc if provided
            if 'reference_doc' in options and os.path.exists(options['reference_doc']):
                cmd.extend(['--reference-doc', options['reference_doc']])
                
        elif output_format == 'html':
            # Standalone HTML with CSS
            cmd.append('--standalone')
            
            if options.get('self_contained', True):
                cmd.append('--self-contained')
                
            # Add specific CSS
            if 'css' in options:
                cmd.extend(['--css', options['css']])
                
            # Add syntax highlighting
            if options.get('highlight_code', True):
                cmd.extend(['--highlight-style', options.get('highlight_style', 'github')])
        
        # Add any additional pandoc arguments
        if 'pandoc_args' in options and isinstance(options['pandoc_args'], list):
            cmd.extend(options['pandoc_args'])
        
        # Run conversion
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        
        return {
            "success": True,
            "file_path": output_path,
            "format": output_format,
            "message": f"Successfully converted Markdown to {output_format}"
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

# Additional helper functions

def check_pandoc_installation() -> Dict[str, Any]:
    """
    Check if Pandoc is installed and return version information.
    
    Returns:
        Information about the Pandoc installation
    """
    try:
        result = subprocess.run(['pandoc', '--version'], check=True, capture_output=True, text=True)
        
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