"""
Integration utilities for connecting the Markdown Editor with other MCP servers.
Provides functions for working with charts, images, and other external content.
"""

import os
import logging
import json
import tempfile
from typing import Dict, Any, List, Optional

logger = logging.getLogger("markdown-editor")

async def add_chart_to_markdown(
    markdown_file: str,
    chart_data: Dict[str, Any],
    position: Optional[int] = None,
    alt_text: str = "Chart"
) -> Dict[str, Any]:
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
    try:
        if not os.path.exists(markdown_file):
            return {
                "success": False,
                "error": f"Markdown file not found: {markdown_file}"
            }
        
        # Extract chart path from chart data
        if "chart_path" in chart_data:
            chart_path = chart_data["chart_path"]
        elif "file_path" in chart_data:
            chart_path = chart_data["file_path"]
        else:
            return {
                "success": False,
                "error": "No chart path found in chart data"
            }
        
        if not os.path.exists(chart_path):
            return {
                "success": False,
                "error": f"Chart file not found: {chart_path}"
            }
        
        # Get directory of markdown file
        md_dir = os.path.dirname(os.path.abspath(markdown_file))
        
        # Convert absolute path to relative if possible
        if os.path.isabs(chart_path):
            try:
                rel_path = os.path.relpath(chart_path, md_dir)
                chart_path = rel_path
            except:
                # Keep absolute path if relative conversion fails
                pass
        
        # Create markdown image syntax
        chart_md = f"![{alt_text}]({chart_path})"
        
        # Read the markdown file
        with open(markdown_file, 'r', encoding='utf-8') as f:
            content = f.read()
            lines = content.splitlines()
        
        # Insert the chart at the specified position or append
        if position is not None and 0 <= position <= len(lines):
            lines.insert(position, chart_md)
            updated_content = "\n".join(lines)
        else:
            # Append with a newline if needed
            if content and not content.endswith("\n\n"):
                updated_content = content + ("\n\n" if not content.endswith("\n") else "\n") + chart_md
            else:
                updated_content = content + chart_md
        
        # Write the updated content
        with open(markdown_file, 'w', encoding='utf-8') as f:
            f.write(updated_content)
        
        return {
            "success": True,
            "file_path": markdown_file,
            "chart_path": chart_path,
            "message": f"Chart added to Markdown document"
        }
        
    except Exception as e:
        logger.error(f"Error adding chart to Markdown: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

async def create_chart_from_markdown_data(
    agent_registry: Dict[str, Any],
    chart_type: str,
    data: Dict[str, Any],
    options: Optional[Dict[str, Any]] = None,
    title: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create a chart using the chartgenerator server based on data in a Markdown document.
    
    Args:
        agent_registry: Agent registry containing the chartgenerator agent
        chart_type: Type of chart to create
        data: Chart data
        options: Optional chart options
        title: Optional chart title
        
    Returns:
        Information about the created chart
    """
    try:
        # Get the chartgenerator agent
        chartgenerator = agent_registry.get("chartgenerator")
        if not chartgenerator:
            return {
                "success": False,
                "error": "Chartgenerator agent not found in registry"
            }
        
        # Prepare the chart request
        chart_request = {
            "type": chart_type,
            "data": data
        }
        
        if options:
            chart_request["options"] = options
            
        if title:
            chart_request["title"] = title
        
        # Call the chartgenerator to create the chart
        try:
            result = await chartgenerator.run("create_chart", chart_request)
            if not result.get("success", False):
                return {
                    "success": False,
                    "error": result.get("error", "Unknown error creating chart")
                }
                
            return result
            
        except Exception as e:
            logger.error(f"Error calling chartgenerator: {str(e)}")
            return {
                "success": False,
                "error": f"Error calling chartgenerator: {str(e)}"
            }
        
    except Exception as e:
        logger.error(f"Error creating chart from Markdown data: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

async def extract_table_from_markdown(markdown_file: str, table_index: int = 0) -> Dict[str, Any]:
    """
    Extract tabular data from a Markdown document.
    
    Args:
        markdown_file: Path to the Markdown file
        table_index: Index of the table to extract (0-based)
        
    Returns:
        Extracted table data
    """
    try:
        if not os.path.exists(markdown_file):
            return {
                "success": False,
                "error": f"Markdown file not found: {markdown_file}"
            }
        
        # Read the markdown file
        with open(markdown_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Extract tables
        import re
        table_pattern = r'(\|[^\n]+\|\n\|[: -]+\|\n(?:\|[^\n]+\|\n)+)'
        tables = re.findall(table_pattern, content)
        
        if not tables or table_index >= len(tables):
            return {
                "success": False,
                "error": f"No table found at index {table_index}"
            }
        
        table = tables[table_index]
        
        # Parse the table
        rows = table.strip().split('\n')
        
        # Extract headers
        headers = [cell.strip() for cell in rows[0].split('|')[1:-1]]
        
        # Skip the separator row
        data_rows = []
        for row in rows[2:]:
            if row.strip():
                cells = [cell.strip() for cell in row.split('|')[1:-1]]
                data_rows.append(cells)
        
        return {
            "success": True,
            "headers": headers,
            "data": data_rows,
            "table_index": table_index,
            "table_text": table
        }
        
    except Exception as e:
        logger.error(f"Error extracting table from Markdown: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        } 