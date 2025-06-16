"""
Markdown editing utilities for the Markdown Editor MCP server.
Provides functions to create, edit, and manipulate Markdown documents.
"""

import os
import json
import tempfile
import logging
from typing import Dict, Any, List, Optional, Union

logger = logging.getLogger("markdown-editor")

def create_markdown(content: str, file_path: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Create a Markdown document with the given content.
    
    Args:
        content: Markdown content to write
        file_path: Optional path to save the file (creates temp file if not provided)
        metadata: Optional metadata to store with the document
        
    Returns:
        Information about the created file
    """
    try:
        # Create file path if not provided
        if not file_path:
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.md')
            file_path = temp_file.name
            temp_file.close()
        else:
            # Always extract only filename - no subdirectories or absolute paths
            filename_only = os.path.basename(file_path)
            
            # Try to get workspace path
            try:
                from core.shared_workspace import get_shared_workspace
                workspace = get_shared_workspace()
                file_path = str(workspace.workspace_root / filename_only)
                logger.info(f"[create_markdown] Using shared workspace: {file_path}")
            except Exception as e:
                logger.warning(f"[create_markdown] Could not use shared workspace: {e}")
                # FIXED: Always use unified temp workspace as fallback
                try:
                    from mcp_local.core.shared_workspace import SharedWorkspaceManager
                    fallback_path = SharedWorkspaceManager._get_unified_workspace_path("default")
                    logger.info(f"[create_markdown] Using unified temp workspace: {fallback_path}")
                    
                    # Ensure the directory exists
                    fallback_path.mkdir(parents=True, exist_ok=True)
                    file_path = str(fallback_path / filename_only)
                    logger.info(f"[create_markdown] Final path: {file_path}")
                except Exception as e2:
                    logger.warning(f"Could not get unified workspace path: {e2}")
                    fallback_dir = '/tmp/denker_workspace/default'
                    logger.info(f"[create_markdown] Fallback to unified temp workspace: {fallback_dir}")
                    
                    # Ensure the directory exists
                    os.makedirs(fallback_dir, exist_ok=True)
                    file_path = os.path.join(fallback_dir, filename_only)
                    logger.info(f"[create_markdown] Final path: {file_path}")
        
        # Create the document directory if it doesn't exist
        os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
        
        # Generate content with optional YAML frontmatter for metadata
        final_content = content
        if metadata and isinstance(metadata, dict):
            yaml_metadata = "---\n"
            for key, value in metadata.items():
                if isinstance(value, (list, dict)):
                    # For complex structures, convert to YAML format
                    try:
                        import yaml
                        yaml_value = yaml.dump({key: value}, default_flow_style=False)
                        # Extract just the value part (remove the key)
                        yaml_value = "\n".join(yaml_value.splitlines()[1:])
                        yaml_metadata += f"{key}:\n{yaml_value}"
                    except (ImportError, Exception):
                        # Fallback if yaml module is not available
                        yaml_metadata += f"{key}: {json.dumps(value)}\n"
                else:
                    yaml_metadata += f"{key}: {value}\n"
            yaml_metadata += "---\n\n"
            final_content = yaml_metadata + content
        
        # Write content to file
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(final_content)
        
        return {
            "success": True,
            "file_path": os.path.basename(file_path),  # Return relative path (filename only)
            "message": "Markdown document created successfully"
        }
    except Exception as e:
        logger.error(f"Error creating Markdown: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

def edit_markdown(file_path: str, operations: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Edit a Markdown document with a list of operations.
    
    Args:
        file_path: Path to the Markdown file
        operations: List of edit operations (replace, insert, delete)
        
    Returns:
        Information about the edited file
    """
    try:
        if not os.path.exists(file_path):
            return {
                "success": False,
                "error": f"File not found: {file_path}"
            }
        
        # Read current content
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Track if any changes were made
        changes_made = False
        
        # Apply operations in sequence
        for op in operations:
            op_type = op.get("type", "").lower()
            
            if op_type == "replace":
                if "target" in op and "replacement" in op:
                    old_content = content
                    content = content.replace(op["target"], op["replacement"])
                    changes_made = changes_made or (old_content != content)
                    
            elif op_type == "replace_regex":
                if "pattern" in op and "replacement" in op:
                    import re
                    old_content = content
                    pattern = re.compile(op["pattern"], re.MULTILINE if op.get("multiline", False) else 0)
                    content = pattern.sub(op["replacement"], content)
                    changes_made = changes_made or (old_content != content)
                    
            elif op_type == "insert_at_line":
                if "line_number" in op and "text" in op:
                    line_num = op["line_number"]
                    lines = content.splitlines()
                    
                    # Insert line at the specified position
                    if 0 <= line_num <= len(lines):
                        lines.insert(line_num, op["text"])
                        content = "\n".join(lines)
                        changes_made = True
                        
            elif op_type == "delete_lines":
                if "start_line" in op and "end_line" in op:
                    start = op["start_line"]
                    end = op["end_line"]
                    lines = content.splitlines()
                    
                    # Delete lines in the specified range
                    if 0 <= start < len(lines) and start <= end < len(lines):
                        content = "\n".join(lines[:start] + lines[end+1:])
                        changes_made = True
                        
            elif op_type == "append":
                if "text" in op:
                    content += "\n" + op["text"]
                    changes_made = True
                    
            elif op_type == "insert_at_position":
                if "position" in op and "text" in op:
                    pos = op["position"]
                    if 0 <= pos <= len(content):
                        content = content[:pos] + op["text"] + content[pos:]
                        changes_made = True
                        
        # Write updated content only if changes were made
        if changes_made:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            return {
                "success": True,
                "file_path": os.path.basename(file_path),  # Return relative path (filename only)
                "message": "Markdown document updated successfully"
            }
        else:
            return {
                "success": True,
                "file_path": os.path.basename(file_path),  # Return relative path (filename only)
                "message": "No changes made to the document"
            }
            
    except Exception as e:
        logger.error(f"Error editing Markdown: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

def append_to_markdown(file_path: str, content: str, section: Optional[str] = None) -> Dict[str, Any]:
    """
    Append content to a Markdown document, optionally under a specific section.
    
    Args:
        file_path: Path to the Markdown file
        content: Content to append
        section: Optional section heading to append under
        
    Returns:
        Information about the updated file
    """
    try:
        if not os.path.exists(file_path):
            return {
                "success": False,
                "error": f"File not found: {file_path}"
            }
        
        # Read current content
        with open(file_path, 'r', encoding='utf-8') as f:
            current_content = f.read()
        
        if section:
            # Try to find the section in the document
            import re
            # Match various heading levels (e.g., # Section, ## Section, etc.)
            section_pattern = re.compile(r'^(#+)\s+' + re.escape(section) + r'\s*$', re.MULTILINE)
            match = section_pattern.search(current_content)
            
            if match:
                # Found the section, now find the next section or end of file
                heading_level = len(match.group(1))  # Count the number of # characters
                start_pos = match.end()
                
                # Look for the next heading of same or higher level
                next_heading_pattern = re.compile(r'^#{1,' + str(heading_level) + r'}\s+', re.MULTILINE)
                next_match = next_heading_pattern.search(current_content, start_pos)
                
                if next_match:
                    # Insert before the next heading
                    insert_pos = next_match.start()
                    updated_content = (
                        current_content[:insert_pos] + 
                        "\n\n" + content + "\n\n" + 
                        current_content[insert_pos:]
                    )
                else:
                    # Append to the end of the file
                    updated_content = current_content + "\n\n" + content
            else:
                # Section not found, append to the end with a new section
                updated_content = current_content + f"\n\n## {section}\n\n{content}"
        else:
            # No section specified, simply append to the end
            updated_content = current_content + "\n\n" + content
        
        # Write updated content
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(updated_content)
        
        return {
            "success": True,
            "file_path": os.path.basename(file_path),  # Return relative path (filename only)
            "message": f"Content {'appended to section ' + section if section else 'appended'} successfully"
        }
        
    except Exception as e:
        logger.error(f"Error appending to Markdown: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

def extract_metadata(file_path: str) -> Dict[str, Any]:
    """
    Extract YAML frontmatter metadata from a Markdown file.
    
    Args:
        file_path: Path to the Markdown file
        
    Returns:
        Extracted metadata or empty dict if none found
    """
    try:
        if not os.path.exists(file_path):
            return {
                "success": False,
                "error": f"File not found: {file_path}"
            }
        
        # Read the file
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check for YAML frontmatter
        if content.startswith('---'):
            try:
                # Try to parse YAML frontmatter
                import yaml
                # Find the end of the frontmatter block
                end_marker = content.find('---', 3)
                if end_marker > 0:
                    frontmatter = content[3:end_marker].strip()
                    metadata = yaml.safe_load(frontmatter)
                    return {
                        "success": True,
                        "metadata": metadata
                    }
            except (ImportError, Exception) as e:
                logger.warning(f"Error parsing YAML frontmatter: {str(e)}")
        
        # No metadata found or parsing failed
        return {
            "success": True,
            "metadata": {}
        }
        
    except Exception as e:
        logger.error(f"Error extracting metadata: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        } 