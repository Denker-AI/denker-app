#!/usr/bin/env python3
"""
Table Generator for Markdown Editor

Provides beautiful themed table generation with various styling options.
"""

import logging
from typing import Dict, Any, List, Optional
import re

logger = logging.getLogger(__name__)

class TableThemes:
    """Table theming system with various beautiful styles."""
    
    @staticmethod
    def get_theme_config(theme: str) -> Dict[str, Any]:
        """Get configuration for a specific theme."""
        themes = {
            'modern': {
                'name': 'Modern',
                'description': 'Clean, contemporary table with subtle styling',
                'header_style': 'bold',
                'use_emojis': True,
                'add_spacing': True,
                'border_style': 'clean',
                'color_scheme': 'blue'
            },
            'elegant': {
                'name': 'Elegant',
                'description': 'Sophisticated table with refined typography',
                'header_style': 'italic_bold',
                'use_emojis': False,
                'add_spacing': True,
                'border_style': 'elegant',
                'color_scheme': 'neutral'
            },
            'minimal': {
                'name': 'Minimal',
                'description': 'Simple, clean table with minimal decoration',
                'header_style': 'simple',
                'use_emojis': False,
                'add_spacing': False,
                'border_style': 'minimal',
                'color_scheme': 'monochrome'
            },
            'bold': {
                'name': 'Bold',
                'description': 'Strong, impactful table with emphasis',
                'header_style': 'bold_caps',
                'use_emojis': True,
                'add_spacing': True,
                'border_style': 'strong',
                'color_scheme': 'high_contrast'
            },
            'colorful': {
                'name': 'Colorful',
                'description': 'Vibrant table with color indicators and emojis',
                'header_style': 'bold',
                'use_emojis': True,
                'add_spacing': True,
                'border_style': 'colorful',
                'color_scheme': 'rainbow'
            },
            'professional': {
                'name': 'Professional',
                'description': 'Business-appropriate table for reports and presentations',
                'header_style': 'professional',
                'use_emojis': False,
                'add_spacing': True,
                'border_style': 'professional',
                'color_scheme': 'corporate'
            }
        }
        
        return themes.get(theme, themes['modern'])

def format_header(header: str, theme_config: Dict[str, Any]) -> str:
    """Format a header according to the theme."""
    style = theme_config.get('header_style', 'bold')
    
    if style == 'bold':
        return f"**{header}**"
    elif style == 'italic_bold':
        return f"***{header}***"
    elif style == 'bold_caps':
        return f"**{header.upper()}**"
    elif style == 'professional':
        return f"**{header.title()}**"
    else:  # simple
        return header

def add_theme_decorations(markdown: str, theme_config: Dict[str, Any], title: Optional[str] = None) -> str:
    """Add theme-specific decorations to the table."""
    result = []
    
    # Add title with theme styling
    if title:
        theme_name = theme_config.get('name', 'Modern')
        if theme_config.get('use_emojis'):
            emoji_map = {
                'Modern': '📊',
                'Elegant': '📋',
                'Minimal': '📄',
                'Bold': '💪',
                'Colorful': '🌈',
                'Professional': '📈'
            }
            emoji = emoji_map.get(theme_name, '📊')
            result.append(f"## {emoji} {title}\n")
        else:
            result.append(f"## {title}\n")
    
    # Add spacing if theme requires it
    if theme_config.get('add_spacing'):
        result.append("")
    
    # Add the table
    result.append(markdown)
    
    # Add theme-specific footer
    if theme_config.get('use_emojis'):
        color_scheme = theme_config.get('color_scheme', 'blue')
        footer_emojis = {
            'blue': '💙',
            'rainbow': '🌈',
            'high_contrast': '⚡',
            'neutral': '✨',
            'monochrome': '⚪',
            'corporate': '🏢'
        }
        emoji = footer_emojis.get(color_scheme, '💙')
        result.append(f"\n*{emoji} Generated with {theme_name} theme*")
    
    return '\n'.join(result)

def create_alignment_row(headers: List[str], alignment: Optional[List[str]] = None) -> str:
    """Create the alignment row for markdown table."""
    if not alignment:
        alignment = ['left'] * len(headers)
    
    # Ensure alignment list matches headers length
    while len(alignment) < len(headers):
        alignment.append('left')
    
    align_chars = []
    for align in alignment[:len(headers)]:
        if align.lower() == 'center':
            align_chars.append(':---:')
        elif align.lower() == 'right':
            align_chars.append('---:')
        else:  # left or default
            align_chars.append('---')
    
    return '| ' + ' | '.join(align_chars) + ' |'

def enhance_cell_content(content: str, theme_config: Dict[str, Any], is_numeric: bool = False) -> str:
    """Enhance cell content based on theme."""
    if not content or content.strip() == '':
        return content
    
    # Add emojis for certain content types if theme supports it
    if theme_config.get('use_emojis'):
        content_lower = content.lower().strip()
        
        # Status indicators
        if content_lower in ['yes', 'true', 'completed', 'done', 'active', 'success']:
            return f"✅ {content}"
        elif content_lower in ['no', 'false', 'pending', 'inactive', 'failed', 'error']:
            return f"❌ {content}"
        elif content_lower in ['in progress', 'working', 'processing']:
            return f"🔄 {content}"
        elif content_lower in ['warning', 'caution', 'attention']:
            return f"⚠️ {content}"
        
        # Numeric enhancements
        if is_numeric and content.replace('.', '').replace(',', '').replace('-', '').isdigit():
            try:
                num = float(content.replace(',', ''))
                if num > 0:
                    return f"📈 {content}"
                elif num < 0:
                    return f"📉 {content}"
            except:
                pass
    
    return content

def detect_numeric_columns(data: List[List[str]]) -> List[bool]:
    """Detect which columns contain primarily numeric data."""
    if not data:
        return []
    
    num_cols = len(data[0]) if data else 0
    numeric_cols = [True] * num_cols
    
    for row in data:
        for i, cell in enumerate(row):
            if i < len(numeric_cols) and cell.strip():
                # Check if cell content is numeric
                clean_cell = cell.replace(',', '').replace('$', '').replace('%', '').strip()
                try:
                    float(clean_cell)
                except ValueError:
                    numeric_cols[i] = False
    
    return numeric_cols

async def create_themed_table(
    headers: List[str],
    data: List[List[str]],
    title: Optional[str] = None,
    theme: str = "professional",
    alignment: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Create a beautifully themed table in Markdown format.
    
    Args:
        headers: List of column headers
        data: List of rows, where each row is a list of cell values
        title: Optional title for the table
        theme: Theme to apply
        alignment: Optional list of alignments for each column
        
    Returns:
        Dictionary with success status and generated markdown
    """
    try:
        if not headers:
            return {
                "success": False,
                "error": "Headers list cannot be empty"
            }
        
        if not data:
            return {
                "success": False,
                "error": "Data list cannot be empty"
            }
        
        # Get theme configuration
        theme_config = TableThemes.get_theme_config(theme)
        
        # Detect numeric columns for enhancement
        numeric_cols = detect_numeric_columns(data)
        
        # Format headers according to theme
        formatted_headers = [format_header(header, theme_config) for header in headers]
        
        # Create header row
        header_row = '| ' + ' | '.join(formatted_headers) + ' |'
        
        # Create alignment row
        alignment_row = create_alignment_row(headers, alignment)
        
        # Create data rows with theme enhancements
        data_rows = []
        for row in data:
            # Ensure row has same number of columns as headers
            padded_row = row + [''] * (len(headers) - len(row))
            padded_row = padded_row[:len(headers)]  # Trim if too long
            
            # Enhance cell content based on theme
            enhanced_cells = []
            for i, cell in enumerate(padded_row):
                is_numeric = i < len(numeric_cols) and numeric_cols[i]
                enhanced_cell = enhance_cell_content(str(cell), theme_config, is_numeric)
                enhanced_cells.append(enhanced_cell)
            
            data_rows.append('| ' + ' | '.join(enhanced_cells) + ' |')
        
        # Combine all parts
        table_parts = [header_row, alignment_row] + data_rows
        table_markdown = '\n'.join(table_parts)
        
        # Add theme decorations
        final_markdown = add_theme_decorations(table_markdown, theme_config, title)
        
        return {
            "success": True,
            "markdown": final_markdown,
            "theme": theme,
            "theme_config": theme_config,
            "rows": len(data),
            "columns": len(headers)
        }
        
    except Exception as e:
        logger.error(f"Error creating themed table: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

async def get_available_table_themes() -> Dict[str, Any]:
    """
    Get available table themes and their descriptions.
    
    Returns:
        Dictionary containing available themes and examples
    """
    themes_info = {}
    
    for theme_name in ['modern', 'elegant', 'minimal', 'bold', 'colorful', 'professional']:
        config = TableThemes.get_theme_config(theme_name)
        themes_info[theme_name] = {
            'name': config['name'],
            'description': config['description'],
            'features': {
                'header_style': config['header_style'],
                'uses_emojis': config['use_emojis'],
                'spacing': config['add_spacing'],
                'border_style': config['border_style'],
                'color_scheme': config['color_scheme']
            }
        }
    
    # Create example table for demonstration
    example_headers = ['Product', 'Sales', 'Status']
    example_data = [
        ['Widget A', '1,250', 'Active'],
        ['Widget B', '890', 'Pending'],
        ['Widget C', '2,100', 'Completed']
    ]
    
    # Generate example for modern theme
    example_result = await create_themed_table(
        headers=example_headers,
        data=example_data,
        title="Sales Report Example",
        theme="modern"
    )
    
    return {
        'themes': themes_info,
        'example': {
            'headers': example_headers,
            'data': example_data,
            'markdown': example_result.get('markdown', ''),
            'usage': "create_table_with_theme(headers=['Product', 'Sales', 'Status'], data=[['Widget A', '1,250', 'Active']], theme='modern')"
        },
        'alignment_options': ['left', 'center', 'right'],
        'theme_features': {
            'emoji_enhancement': 'Automatically adds relevant emojis to status indicators and numeric data',
            'smart_formatting': 'Detects data types and applies appropriate formatting',
            'responsive_styling': 'Themes adapt to content type and context',
            'professional_output': 'All themes produce publication-ready tables'
        }
    } 