"""
Chart Generator for Markdown Editor

Provides chart generation capabilities using QuickChart.io API
with proper shared workspace integration.
"""

import os
import json
import base64
import logging
import asyncio
import aiohttp
from typing import Dict, Any, Optional, List, Union
from datetime import datetime
from pathlib import Path
from PIL import Image
import io

logger = logging.getLogger("markdown-editor")

# Try to import shared workspace for multi-agent coordination
try:
    from core.shared_workspace import get_shared_workspace
    SHARED_WORKSPACE_AVAILABLE = True
except ImportError:
    SHARED_WORKSPACE_AVAILABLE = False

# Beautiful color palettes for different chart types and themes
COLOR_PALETTES = {
    'modern': [
        '#667eea', '#764ba2', '#f093fb', '#f5576c', '#4facfe', '#00f2fe',
        '#43e97b', '#38f9d7', '#ffecd2', '#fcb69f', '#a8edea', '#fed6e3'
    ],
    'professional': [
        '#2563eb', '#dc2626', '#059669', '#d97706', '#7c3aed', '#db2777',
        '#0891b2', '#65a30d', '#c2410c', '#9333ea', '#be185d', '#0e7490'
    ],
    'pastel': [
        '#fecaca', '#fed7d7', '#fde68a', '#d9f99d', '#a7f3d0', '#bfdbfe',
        '#ddd6fe', '#f3e8ff', '#fce7f3', '#fed7e2', '#fef3c7', '#ecfdf5'
    ],
    'vibrant': [
        '#ef4444', '#f97316', '#eab308', '#22c55e', '#06b6d4', '#3b82f6',
        '#8b5cf6', '#ec4899', '#f59e0b', '#10b981', '#6366f1', '#84cc16'
    ],
    'ocean': [
        '#0ea5e9', '#0284c7', '#0369a1', '#075985', '#0c4a6e', '#164e63',
        '#155e75', '#0891b2', '#0e7490', '#06b6d4', '#67e8f9', '#a5f3fc'
    ],
    'sunset': [
        '#f97316', '#ea580c', '#dc2626', '#be123c', '#9f1239', '#881337',
        '#fbbf24', '#f59e0b', '#d97706', '#b45309', '#92400e', '#78350f'
    ],
    'forest': [
        '#059669', '#047857', '#065f46', '#064e3b', '#022c22', '#84cc16',
        '#65a30d', '#4d7c0f', '#365314', '#1a2e05', '#22c55e', '#16a34a'
    ]
}

# Typography and styling configurations
CHART_STYLES = {
    'modern': {
        'font_family': 'Inter, system-ui, -apple-system, sans-serif',
        'title_size': 18,
        'label_size': 12,
        'legend_size': 11,
        'grid_color': '#f1f5f9',
        'text_color': '#334155'
    },
    'elegant': {
        'font_family': 'Georgia, serif',
        'title_size': 20,
        'label_size': 13,
        'legend_size': 12,
        'grid_color': '#f8fafc',
        'text_color': '#1e293b'
    },
    'minimal': {
        'font_family': 'Helvetica Neue, Arial, sans-serif',
        'title_size': 16,
        'label_size': 11,
        'legend_size': 10,
        'grid_color': '#f9fafb',
        'text_color': '#6b7280'
    },
    'bold': {
        'font_family': 'Montserrat, sans-serif',
        'title_size': 22,
        'label_size': 14,
        'legend_size': 13,
        'grid_color': '#f3f4f6',
        'text_color': '#111827'
    }
}

def validate_image_file(file_path: str, min_size_bytes: int = 5000, chart_type: str = 'unknown') -> Dict[str, Any]:
    """
    Validate that an image file is properly created and not corrupted.
    
    Args:
        file_path: Path to the image file
        min_size_bytes: Minimum expected file size in bytes
        chart_type: Type of chart
        
    Returns:
        Dict with validation results
    """
    try:
        if not os.path.exists(file_path):
            return {
                'valid': False,
                'error': f'Image file does not exist: {file_path}'
            }
        
        # Check file size
        file_size = os.path.getsize(file_path)
        if file_size < min_size_bytes:
            return {
                'valid': False,
                'error': f'Image file too small ({file_size} bytes, expected at least {min_size_bytes})',
                'file_size': file_size
            }
        
        # Try to open and validate the image using PIL
        try:
            with Image.open(file_path) as img:
                # Check if image has reasonable dimensions
                width, height = img.size
                if width < 50 or height < 50:
                    return {
                        'valid': False,
                        'error': f'Image dimensions too small: {width}x{height}',
                        'file_size': file_size,
                        'dimensions': (width, height)
                    }
                
                # Check if image is mostly transparent/empty
                if img.mode in ('RGBA', 'LA'):
                    # For transparent images, check the non-transparent pixels
                    if img.mode == 'RGBA':
                        # Get alpha channel
                        alpha = img.split()[-1]
                        # Create mask of non-transparent pixels
                        non_transparent = [alpha.getpixel((x, y)) > 128 for x in range(0, width, max(1, width//20)) for y in range(0, height, max(1, height//20))]
                        non_transparent_count = sum(non_transparent)
                        
                        # Adjust threshold based on chart type
                        min_non_transparent = 10
                        if chart_type in ['line']:
                            min_non_transparent = 5  # Line charts can have very minimal content
                        elif chart_type in ['bar']:
                            min_non_transparent = 20  # Bar charts should have more content
                        elif chart_type in ['radar', 'scatter', 'bubble']:
                            min_non_transparent = 5  # Radar and scatter charts can be sparse
                        elif chart_type in ['sparkline']:
                            min_non_transparent = 3  # Sparklines are very minimal
                        
                        if non_transparent_count < min_non_transparent:
                            return {
                                'valid': False,
                                'error': f'Image appears to be mostly transparent ({non_transparent_count} non-transparent pixels in sample, expected at least {min_non_transparent})',
                                'file_size': file_size,
                                'dimensions': (width, height)
                            }
                        
                        # Sample non-transparent pixels for color analysis
                        rgb_img = Image.new('RGB', img.size, (255, 255, 255))
                        rgb_img.paste(img, mask=alpha)
                        
                        # Sample pixels from areas that are not transparent
                        sample_pixels = []
                        for x in range(0, width, max(1, width//10)):
                            for y in range(0, height, max(1, height//10)):
                                if alpha.getpixel((x, y)) > 128:  # Non-transparent
                                    sample_pixels.append(rgb_img.getpixel((x, y)))
                        
                        if len(sample_pixels) > 0:
                            unique_colors = set(sample_pixels)
                        else:
                            unique_colors = set()
                    else:
                        # Convert to RGB to check for content
                        rgb_img = Image.new('RGB', img.size, (255, 255, 255))
                        rgb_img.paste(img, mask=img.split()[-1])
                        img = rgb_img
                        pixels = list(img.getdata())
                        unique_colors = set(pixels[:min(1000, len(pixels))])
                else:
                    # Non-transparent image
                    pixels = list(img.getdata())
                    unique_colors = set(pixels[:min(1000, len(pixels))])
                
                # More lenient validation for charts - they might have large solid areas
                min_colors = 2 if width * height > 100000 else 3  # Large images can have fewer unique colors
                
                # Special handling for different chart types
                if chart_type in ['bar', 'line']:
                    min_colors = 1  # Bar and line charts can have very uniform backgrounds
                elif chart_type in ['pie', 'doughnut']:
                    min_colors = 2  # Pie charts should have at least 2 colors
                
                if len(unique_colors) < min_colors:
                    # Additional check: sample from different areas of the image
                    center_x, center_y = width // 2, height // 2
                    
                    # For transparent images, check if we have actual chart content
                    if img.mode == 'RGBA':
                        alpha = img.split()[-1]
                        # Check if center area has content
                        center_alpha = alpha.getpixel((center_x, center_y))
                        if center_alpha > 128:  # Center has content
                            return {
                                'valid': True,
                                'file_size': file_size,
                                'dimensions': (width, height),
                                'format': img.format,
                                'mode': img.mode,
                                'unique_colors': len(unique_colors),
                                'note': 'Validated as chart with transparent background'
                            }
                        
                        # For bar charts, check if there's any non-transparent content
                        if chart_type in ['bar', 'line']:
                            non_transparent_pixels = sum(1 for x in range(0, width, 10) for y in range(0, height, 10) if alpha.getpixel((x, y)) > 128)
                            if non_transparent_pixels > 50:  # Has substantial content
                                return {
                                    'valid': True,
                                    'file_size': file_size,
                                    'dimensions': (width, height),
                                    'format': img.format,
                                    'mode': img.mode,
                                    'unique_colors': len(unique_colors),
                                    'note': f'Validated as {chart_type} chart with {non_transparent_pixels} content pixels'
                                }
                    
                    corner_pixels = [
                        img.getpixel((0, 0)),
                        img.getpixel((width-1, 0)),
                        img.getpixel((0, height-1)),
                        img.getpixel((width-1, height-1)),
                        img.getpixel((center_x, center_y))
                    ]
                    corner_unique = set(corner_pixels)
                    
                    if len(corner_unique) < 2:
                        return {
                            'valid': False,
                            'error': f'Image appears to be empty or has minimal content (only {len(unique_colors)} unique colors in sample, {len(corner_unique)} in corners)',
                            'file_size': file_size,
                            'dimensions': (width, height),
                            'unique_colors': len(unique_colors),
                            'corner_colors': len(corner_unique)
                        }
                
                return {
                    'valid': True,
                    'file_size': file_size,
                    'dimensions': (width, height),
                    'format': img.format,
                    'mode': img.mode,
                    'unique_colors': len(unique_colors)
                }
                
        except Exception as img_error:
            return {
                'valid': False,
                'error': f'Cannot open image file: {str(img_error)}',
                'file_size': file_size
            }
            
    except Exception as e:
        return {
            'valid': False,
            'error': f'Error validating image: {str(e)}'
        }

class ChartGenerator:
    """
    Chart generator using QuickChart.io API with shared workspace integration.
    """
    
    def __init__(self):
        self.quickchart_base_url = "https://quickchart.io"
        
    def _get_workspace_path(self, filename: str) -> str:
        """Get the proper shared workspace path for a chart file."""
        logger.info(f"[ChartGenerator._get_workspace_path] Requested filename: {filename}")
        
        if SHARED_WORKSPACE_AVAILABLE:
            try:
                workspace = get_shared_workspace()
                # Use only filename - no subdirectories allowed
                filename_only = Path(filename).name
                file_path = workspace.workspace_root / filename_only
                
                logger.info(f"[ChartGenerator._get_workspace_path] Using shared workspace: {file_path}")
                return str(file_path)
            except Exception as e:
                logger.warning(f"Could not use shared workspace for chart: {e}")
        
        # FIXED: Always use unified temp workspace as fallback
        try:
            from mcp_local.core.shared_workspace import SharedWorkspaceManager
            fallback_path = SharedWorkspaceManager._get_unified_workspace_path("default")
            logger.info(f"[ChartGenerator._get_workspace_path] Using unified temp workspace: {fallback_path}")
            
            # Ensure directory exists
            fallback_path.mkdir(parents=True, exist_ok=True)
            
            # Strip any path components for security
            safe_filename = Path(filename).name
            final_path = str(fallback_path / safe_filename)
            logger.info(f"[ChartGenerator._get_workspace_path] Final path: {final_path}")
            return final_path
        except Exception as e:
            logger.warning(f"Could not get unified workspace path: {e}")
            fallback_dir = '/tmp/denker_workspace/default'
            logger.info(f"[ChartGenerator._get_workspace_path] Fallback to unified temp workspace: {fallback_dir}")
            
            # Ensure directory exists
            os.makedirs(fallback_dir, exist_ok=True)
            
            # Strip any path components for security
            safe_filename = Path(filename).name
            final_path = os.path.join(fallback_dir, safe_filename)
            logger.info(f"[ChartGenerator._get_workspace_path] Final path: {final_path}")
            return final_path
    
    def _register_chart_file(self, file_path: str, chart_config: Dict[str, Any]) -> Optional[str]:
        """Register a chart file in the shared workspace."""
        if SHARED_WORKSPACE_AVAILABLE:
            try:
                workspace = get_shared_workspace()
                return workspace.register_file(
                    file_path=file_path,
                    agent_name="markdown-editor",
                    metadata={
                        "type": "chart_image",
                        "chart_type": chart_config.get("type", "unknown"),
                        "created_by": "markdown-editor-chart-generator",
                        "chart_config": json.dumps(chart_config)
                    }
                )
            except Exception as e:
                logger.warning(f"Could not register chart file in workspace: {e}")
        
        return None
    
    async def create_chart(self, 
                          chart_config: Dict[str, Any], 
                          filename: Optional[str] = None,
                          width: int = 500,
                          height: int = 300) -> Dict[str, Any]:
        """
        Create a chart using QuickChart.io API and save it to shared workspace.
        
        Args:
            chart_config: Chart configuration (QuickChart format)
            filename: Optional filename (auto-generated if not provided)
            width: Chart width in pixels
            height: Chart height in pixels
            
        Returns:
            Dict with chart information including path and URLs
        """
        try:
            # Generate filename if not provided
            if not filename:
                chart_type = chart_config.get('type', 'chart')
                filename = f"{chart_type}.png"
            
            # Ensure .png extension
            if not filename.endswith('.png'):
                filename += '.png'
            
            # Get proper workspace path
            chart_path = self._get_workspace_path(filename)
            
            # Ensure directory exists
            os.makedirs(os.path.dirname(chart_path), exist_ok=True)
            
            # Create chart via QuickChart API
            async with aiohttp.ClientSession() as session:
                url = f"{self.quickchart_base_url}/chart"
                payload = {
                    'chart': json.dumps(chart_config),
                    'format': 'png',
                    'width': width,
                    'height': height
                }
                
                async with session.post(url, json=payload) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        raise Exception(f"QuickChart API error {response.status}: {error_text}")
                    
                    chart_data = await response.read()
                    
                    # Validate that we received actual image data
                    if len(chart_data) < 1000:  # Very small response is likely an error
                        raise Exception(f"Received suspiciously small chart data: {len(chart_data)} bytes")
                    
                    # Validate PNG header (first 8 bytes should be PNG signature)
                    png_signature = b'\x89PNG\r\n\x1a\n'
                    if not chart_data.startswith(png_signature):
                        raise Exception("Received data is not a valid PNG file (missing PNG signature)")
                    
                    # Save chart to workspace with proper error handling
                    try:
                        # Use atomic write: write to temp file first, then rename
                        temp_path = chart_path + '.tmp'
                        with open(temp_path, 'wb') as f:
                            f.write(chart_data)
                            f.flush()  # Force write to disk
                            os.fsync(f.fileno())  # Ensure data is written to storage
                        
                        # Atomic rename (this should be atomic on most filesystems)
                        os.rename(temp_path, chart_path)
                        
                        logger.info(f"Successfully wrote PNG chart: {chart_path} ({len(chart_data)} bytes)")
                        
                    except Exception as write_error:
                        # Clean up temp file if it exists
                        if os.path.exists(temp_path):
                            try:
                                os.remove(temp_path)
                            except:
                                pass
                        raise Exception(f"Failed to write PNG file: {write_error}")
                    
                    # Validate the created image file
                    chart_type = chart_config.get('type', 'unknown')
                    validation = validate_image_file(chart_path, min_size_bytes=1000, chart_type=chart_type)
                    if not validation['valid']:
                        # Remove the invalid file
                        try:
                            os.remove(chart_path)
                        except:
                            pass
                        
                        logger.error(f"Chart validation failed: {validation['error']}")
                        return {
                            'success': False,
                            'error': f"Chart creation failed validation: {validation['error']}",
                            'validation_details': validation,
                            'chart_data_size': len(chart_data),
                            'png_signature_valid': chart_data.startswith(png_signature)
                        }
                    
                    # Register file in workspace
                    file_id = self._register_chart_file(chart_path, chart_config)
                    
                    # NOTE: We don't need to generate QuickChart URL since we save the chart locally
                    # The local file path is sufficient for document integration
                    
                    result = {
                        'success': True,
                        'chart_path': os.path.basename(chart_path),  # Return relative path (filename only)
                        'filename': os.path.basename(chart_path),
                        'size_bytes': len(chart_data),
                        'width': width,
                        'height': height,
                        'chart_type': chart_config.get('type', 'unknown'),
                        'validation': validation  # Include validation details
                    }
                    
                    if file_id:
                        result['file_id'] = file_id
                    
                    logger.info(f"Created chart: {chart_path} (type: {chart_config.get('type')}, size: {len(chart_data)} bytes)")
                    return result
                    
        except Exception as e:
            logger.error(f"Failed to create chart: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def create_chart_from_data(self,
                                   chart_type: str,
                                   data: Dict[str, Any],
                                   title: Optional[str] = None,
                                   options: Optional[Union[str, Dict[str, Any]]] = None,
                                   filename: Optional[str] = None,
                                   width: int = 500,
                                   height: int = 300,
                                   color_theme: str = 'modern',
                                   style_theme: str = 'modern') -> Dict[str, Any]:
        """
        Create a chart from structured data with beautiful styling.
        
        Args:
            chart_type: Type of chart (bar, line, pie, doughnut, etc.)
            data: Chart data in Chart.js format
            title: Optional chart title
            options: Optional chart options
            filename: Optional filename
            width: Chart width
            height: Chart height
            color_theme: Color theme (modern, professional, pastel, vibrant, ocean, sunset, forest)
            style_theme: Style theme (modern, elegant, minimal, bold)
            
        Returns:
            Dict with chart information
        """
        try:
            # Enhance data with beautiful colors
            enhanced_data = enhance_chart_data_colors(data, chart_type, color_theme)
            
            # Build chart configuration
            chart_config = {
                'type': chart_type,
                'data': enhanced_data
            }
            
            # Handle options parameter - it might be a string that needs parsing
            chart_options = {}
            if options:
                if isinstance(options, str):
                    try:
                        chart_options = json.loads(options)
                        logger.debug(f"Parsed options string as JSON: {chart_options}")
                    except json.JSONDecodeError as e:
                        logger.warning(f"Failed to parse options string as JSON: {e}")
                        logger.warning(f"Options string was: {options[:200]}...")
                        # If JSON parsing fails, log the error but continue without custom options
                        chart_options = {}
                elif isinstance(options, dict):
                    chart_options = options.copy()
                else:
                    logger.warning(f"Options parameter has unexpected type: {type(options)}")
                    chart_options = {}
            
            # Add title if provided
            if title:
                chart_options.setdefault('plugins', {}).setdefault('title', {
                    'display': True,
                    'text': title
                })
            
            # Only add options if we have any
            if chart_options or title:
                chart_config['options'] = chart_options
            
            # Apply beautiful styling
            chart_config = apply_beautiful_styling(chart_config, style_theme)
            
            logger.info(f"Creating beautiful {chart_type} chart with {color_theme} colors and {style_theme} styling")
            
            return await self.create_chart(chart_config, filename, width, height)
            
        except Exception as e:
            logger.error(f"Failed to create chart from data: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_chart_template(self, chart_type: str) -> Dict[str, Any]:
        """
        Get a template configuration for a specific chart type.
        
        Args:
            chart_type: Type of chart
            
        Returns:
            Template configuration
        """
        templates = {
            'bar': {
                'type': 'bar',
                'data': {
                    'labels': ['Label 1', 'Label 2', 'Label 3'],
                    'datasets': [{
                        'label': 'Dataset 1',
                        'data': [10, 20, 30],
                        'backgroundColor': ['#FF6384', '#36A2EB', '#FFCE56']
                    }]
                },
                'options': {
                    'responsive': True,
                    'plugins': {
                        'title': {
                            'display': True,
                            'text': 'Bar Chart'
                        }
                    }
                }
            },
            'horizontalBar': {
                'type': 'horizontalBar',
                'data': {
                    'labels': ['Category A', 'Category B', 'Category C'],
                    'datasets': [{
                        'label': 'Values',
                        'data': [25, 35, 45],
                        'backgroundColor': ['#FF6384', '#36A2EB', '#FFCE56']
                    }]
                },
                'options': {
                    'responsive': True,
                    'plugins': {
                        'title': {
                            'display': True,
                            'text': 'Horizontal Bar Chart'
                        }
                    }
                }
            },
            'line': {
                'type': 'line',
                'data': {
                    'labels': ['Jan', 'Feb', 'Mar', 'Apr'],
                    'datasets': [{
                        'label': 'Data',
                        'data': [10, 15, 12, 18],
                        'borderColor': '#36A2EB',
                        'backgroundColor': 'rgba(54, 162, 235, 0.2)',
                        'fill': True
                    }]
                },
                'options': {
                    'responsive': True,
                    'plugins': {
                        'title': {
                            'display': True,
                            'text': 'Line Chart'
                        }
                    }
                }
            },
            'area': {
                'type': 'line',
                'data': {
                    'labels': ['Jan', 'Feb', 'Mar', 'Apr'],
                    'datasets': [{
                        'label': 'Area Data',
                        'data': [10, 15, 12, 18],
                        'borderColor': '#36A2EB',
                        'backgroundColor': 'rgba(54, 162, 235, 0.3)',
                        'fill': 'origin'
                    }]
                },
                'options': {
                    'responsive': True,
                    'plugins': {
                        'title': {
                            'display': True,
                            'text': 'Area Chart'
                        }
                    }
                }
            },
            'pie': {
                'type': 'pie',
                'data': {
                    'labels': ['Red', 'Blue', 'Yellow'],
                    'datasets': [{
                        'data': [30, 50, 20],
                        'backgroundColor': ['#FF6384', '#36A2EB', '#FFCE56']
                    }]
                },
                'options': {
                    'responsive': True,
                    'plugins': {
                        'title': {
                            'display': True,
                            'text': 'Pie Chart'
                        }
                    }
                }
            },
            'doughnut': {
                'type': 'doughnut',
                'data': {
                    'labels': ['Category A', 'Category B', 'Category C'],
                    'datasets': [{
                        'data': [35, 40, 25],
                        'backgroundColor': ['#FF6384', '#36A2EB', '#FFCE56']
                    }]
                },
                'options': {
                    'responsive': True,
                    'plugins': {
                        'title': {
                            'display': True,
                            'text': 'Doughnut Chart'
                        }
                    }
                }
            },
            'radar': {
                'type': 'radar',
                'data': {
                    'labels': ['Speed', 'Reliability', 'Comfort', 'Safety', 'Efficiency'],
                    'datasets': [{
                        'label': 'Product A',
                        'data': [80, 90, 70, 85, 75],
                        'backgroundColor': 'rgba(255, 99, 132, 0.2)',
                        'borderColor': 'rgba(255, 99, 132, 1)',
                        'pointBackgroundColor': 'rgba(255, 99, 132, 1)'
                    }]
                },
                'options': {
                    'responsive': True,
                    'plugins': {
                        'title': {
                            'display': True,
                            'text': 'Radar Chart'
                        }
                    }
                }
            },
            'polarArea': {
                'type': 'polarArea',
                'data': {
                    'labels': ['Red', 'Green', 'Yellow', 'Grey', 'Blue'],
                    'datasets': [{
                        'data': [11, 16, 7, 3, 14],
                        'backgroundColor': ['#FF6384', '#4BC0C0', '#FFCE56', '#E7E9ED', '#36A2EB']
                    }]
                },
                'options': {
                    'responsive': True,
                    'plugins': {
                        'title': {
                            'display': True,
                            'text': 'Polar Area Chart'
                        }
                    }
                }
            },
            'scatter': {
                'type': 'scatter',
                'data': {
                    'datasets': [{
                        'label': 'Scatter Dataset',
                        'data': [
                            {'x': -10, 'y': 0},
                            {'x': 0, 'y': 10},
                            {'x': 10, 'y': 5},
                            {'x': 0.5, 'y': 5.5}
                        ],
                        'backgroundColor': '#FF6384'
                    }]
                },
                'options': {
                    'responsive': True,
                    'plugins': {
                        'title': {
                            'display': True,
                            'text': 'Scatter Plot'
                        }
                    }
                }
            },
            'bubble': {
                'type': 'bubble',
                'data': {
                    'datasets': [{
                        'label': 'Bubble Dataset',
                        'data': [
                            {'x': 20, 'y': 30, 'r': 15},
                            {'x': 40, 'y': 10, 'r': 10},
                            {'x': 10, 'y': 40, 'r': 20}
                        ],
                        'backgroundColor': '#FF6384'
                    }]
                },
                'options': {
                    'responsive': True,
                    'plugins': {
                        'title': {
                            'display': True,
                            'text': 'Bubble Chart'
                        }
                    }
                }
            },
            'radialGauge': {
                'type': 'radialGauge',
                'data': {
                    'datasets': [{
                        'data': [70],
                        'backgroundColor': ['#4BC0C0']
                    }]
                },
                'options': {
                    'responsive': True,
                    'plugins': {
                        'title': {
                            'display': True,
                            'text': 'Radial Gauge'
                        }
                    }
                }
            },
            'gauge': {
                'type': 'gauge',
                'data': {
                    'datasets': [{
                        'value': 50,
                        'data': [20, 40, 60],
                        'backgroundColor': ['green', 'orange', 'red'],
                        'borderWidth': 2
                    }]
                },
                'options': {
                    'responsive': True,
                    'valueLabel': {
                        'fontSize': 22,
                        'backgroundColor': 'transparent',
                        'color': '#000'
                    },
                    'plugins': {
                        'title': {
                            'display': True,
                            'text': 'Speedometer Gauge'
                        }
                    }
                }
            },
            'violin': {
                'type': 'violin',
                'data': {
                    'labels': ['Dataset 1', 'Dataset 2', 'Dataset 3'],
                    'datasets': [{
                        'label': 'Violin Data',
                        'data': [
                            [12, 6, 3, 4, 8, 9, 11],
                            [1, 8, 8, 15, 12, 10, 7],
                            [1, 1, 1, 2, 3, 5, 9, 8]
                        ],
                        'backgroundColor': 'rgba(54, 162, 235, 0.2)',
                        'borderColor': 'rgba(54, 162, 235, 1)'
                    }]
                },
                'options': {
                    'responsive': True,
                    'plugins': {
                        'title': {
                            'display': True,
                            'text': 'Violin Chart'
                        }
                    }
                }
            },
            'boxplot': {
                'type': 'boxplot',
                'data': {
                    'labels': ['Dataset 1', 'Dataset 2', 'Dataset 3'],
                    'datasets': [{
                        'label': 'Box Plot Data',
                        'data': [
                            [1, 2, 3, 4, 5, 6, 7, 8, 9],
                            [2, 4, 6, 8, 10, 12, 14],
                            [1, 3, 5, 7, 9, 11, 13, 15]
                        ],
                        'backgroundColor': 'rgba(255, 99, 132, 0.2)',
                        'borderColor': 'rgba(255, 99, 132, 1)'
                    }]
                },
                'options': {
                    'responsive': True,
                    'plugins': {
                        'title': {
                            'display': True,
                            'text': 'Box Plot'
                        }
                    }
                }
            },
            'funnel': {
                'type': 'funnel',
                'data': {
                    'labels': ['Visitors', 'Leads', 'Prospects', 'Customers'],
                    'datasets': [{
                        'data': [1000, 500, 200, 50],
                        'backgroundColor': ['#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0']
                    }]
                },
                'options': {
                    'responsive': True,
                    'plugins': {
                        'title': {
                            'display': True,
                            'text': 'Funnel Chart'
                        }
                    }
                }
            },
            'sankey': {
                'type': 'sankey',
                'data': {
                    'datasets': [{
                        'data': [
                            {'from': 'Step A', 'to': 'Step B', 'flow': 10},
                            {'from': 'Step A', 'to': 'Step C', 'flow': 5},
                            {'from': 'Step B', 'to': 'Step C', 'flow': 10},
                            {'from': 'Step D', 'to': 'Step C', 'flow': 7}
                        ]
                    }]
                },
                'options': {
                    'responsive': True,
                    'plugins': {
                        'title': {
                            'display': True,
                            'text': 'Sankey Diagram'
                        }
                    }
                }
            },
            'sparkline': {
                'type': 'sparkline',
                'data': {
                    'datasets': [{
                        'data': [140, 60, 274, 370, 199, 245, 189]
                    }]
                },
                'options': {
                    'responsive': True
                }
            },
            'progressBar': {
                'type': 'progressBar',
                'data': {
                    'datasets': [{
                        'data': [75]
                    }]
                },
                'options': {
                    'responsive': True,
                    'plugins': {
                        'title': {
                            'display': True,
                            'text': 'Progress Bar (75%)'
                        }
                    }
                }
            },
            'candlestick': {
                'type': 'candlestick',
                'data': {
                    'datasets': [{
                        'label': 'Stock Price',
                        'data': [
                            {'x': '2023-01-01', 'o': 100, 'h': 110, 'l': 95, 'c': 105},
                            {'x': '2023-01-02', 'o': 105, 'h': 115, 'l': 100, 'c': 110},
                            {'x': '2023-01-03', 'o': 110, 'h': 120, 'l': 105, 'c': 115}
                        ]
                    }]
                },
                'options': {
                    'responsive': True,
                    'plugins': {
                        'title': {
                            'display': True,
                            'text': 'Candlestick Chart'
                        }
                    }
                }
            },
            'ohlc': {
                'type': 'ohlc',
                'data': {
                    'datasets': [{
                        'label': 'Stock Price',
                        'data': [
                            {'x': '2023-01-01', 'o': 100, 'h': 110, 'l': 95, 'c': 105},
                            {'x': '2023-01-02', 'o': 105, 'h': 115, 'l': 100, 'c': 110},
                            {'x': '2023-01-03', 'o': 110, 'h': 120, 'l': 105, 'c': 115}
                        ]
                    }]
                },
                'options': {
                    'responsive': True,
                    'plugins': {
                        'title': {
                            'display': True,
                            'text': 'OHLC Chart'
                        }
                    }
                }
            }
        }
        
        return templates.get(chart_type, {
            'error': f'Unknown chart type: {chart_type}',
            'available_types': list(templates.keys())
        })

# Global chart generator instance
chart_generator = ChartGenerator()

# Export functions for MCP tools
async def create_chart_tool(chart_config: Dict[str, Any], 
                           filename: Optional[str] = None,
                           width: int = 500,
                           height: int = 300) -> Dict[str, Any]:
    """MCP tool function for creating charts."""
    return await chart_generator.create_chart(chart_config, filename, width, height)

async def create_chart_from_data_tool(chart_type: str,
                                    data: Dict[str, Any],
                                    title: Optional[str] = None,
                                    options: Optional[Union[str, Dict[str, Any]]] = None,
                                    filename: Optional[str] = None,
                                    width: int = 500,
                                    height: int = 300,
                                    color_theme: str = 'modern',
                                    style_theme: str = 'modern') -> Dict[str, Any]:
    """
    MCP tool function for creating charts from data with beautiful styling.
    
    Args:
        chart_type: Type of chart (bar, line, pie, doughnut, etc.)
        data: Chart data in Chart.js format
        title: Optional chart title
        options: Optional chart options (JSON string or dict)
        filename: Optional filename for the chart
        width: Chart width in pixels
        height: Chart height in pixels
        color_theme: Color theme (modern, professional, pastel, vibrant, ocean, sunset, forest)
        style_theme: Style theme (modern, elegant, minimal, bold)
        
    Returns:
        Dict with chart creation results
    """
    return await chart_generator.create_chart_from_data(
        chart_type, data, title, options, filename, width, height, color_theme, style_theme
    )

def get_chart_template_tool(chart_type: str) -> Dict[str, Any]:
    """MCP tool function for getting chart templates."""
    return chart_generator.get_chart_template(chart_type) 

async def get_available_themes_tool() -> Dict[str, Any]:
    """
    Get available color and style themes for chart generation.
    
    Returns:
        Dictionary containing available themes and chart types
    """
    return {
        'color_themes': {
            'modern': {
                'description': 'Contemporary gradient colors with purples, blues, and pinks',
                'colors': ['#667eea', '#764ba2', '#f093fb', '#f5576c', '#4facfe', '#00f2fe']
            },
            'professional': {
                'description': 'Business-appropriate blues, reds, and greens',
                'colors': ['#2563eb', '#dc2626', '#059669', '#7c3aed', '#ea580c', '#0891b2']
            },
            'pastel': {
                'description': 'Soft, gentle colors perfect for presentations',
                'colors': ['#fecaca', '#fed7d7', '#fef3c7', '#d1fae5', '#dbeafe', '#e0e7ff']
            },
            'vibrant': {
                'description': 'Bold, high-impact colors for attention-grabbing charts',
                'colors': ['#ff6b6b', '#4ecdc4', '#45b7d1', '#96ceb4', '#ffeaa7', '#dda0dd']
            },
            'ocean': {
                'description': 'Blues and teals inspired by ocean depths',
                'colors': ['#0077be', '#00a8cc', '#0492c2', '#1e3a8a', '#0369a1', '#0284c7']
            },
            'sunset': {
                'description': 'Warm oranges, reds, and yellows',
                'colors': ['#ff7f50', '#ff6347', '#ffa500', '#ff4500', '#dc143c', '#b22222']
            },
            'forest': {
                'description': 'Nature-inspired greens and earth tones',
                'colors': ['#228b22', '#32cd32', '#90ee90', '#006400', '#8fbc8f', '#2e8b57']
            }
        },
        'style_themes': {
            'modern': {
                'description': 'Clean, contemporary styling with Inter font',
                'font_family': 'Inter',
                'font_size': 14,
                'grid_color': '#f1f5f9',
                'background_color': '#ffffff'
            },
            'elegant': {
                'description': 'Sophisticated, formal styling with Georgia serif',
                'font_family': 'Georgia',
                'font_size': 13,
                'grid_color': '#f8fafc',
                'background_color': '#fefefe'
            },
            'minimal': {
                'description': 'Subtle, minimalist design with Helvetica',
                'font_family': 'Helvetica',
                'font_size': 12,
                'grid_color': '#f9fafb',
                'background_color': '#ffffff'
            },
            'bold': {
                'description': 'Strong, impactful styling with Montserrat',
                'font_family': 'Montserrat',
                'font_size': 15,
                'grid_color': '#e5e7eb',
                'background_color': '#ffffff'
            }
        },
        'chart_types': {
            'basic': ['bar', 'horizontalBar', 'line', 'area', 'pie', 'doughnut'],
            'advanced': ['radar', 'polarArea', 'scatter', 'bubble'],
            'statistical': ['violin', 'boxplot'],
            'specialized': ['radialGauge', 'gauge', 'funnel', 'sankey', 'sparkline', 'progressBar'],
            'financial': ['candlestick', 'ohlc']
        },
        'chart_descriptions': {
            'bar': 'Vertical bar chart for comparing categories',
            'horizontalBar': 'Horizontal bar chart for comparing categories',
            'line': 'Line chart for showing trends over time',
            'area': 'Area chart (filled line chart) for showing cumulative data',
            'pie': 'Pie chart for showing proportions of a whole',
            'doughnut': 'Doughnut chart (pie chart with center hole)',
            'radar': 'Radar chart for comparing multiple variables',
            'polarArea': 'Polar area chart for radial data visualization',
            'scatter': 'Scatter plot for showing correlation between two variables',
            'bubble': 'Bubble chart for three-dimensional data (x, y, size)',
            'violin': 'Violin plot for statistical distribution visualization',
            'boxplot': 'Box plot for statistical summary visualization',
            'radialGauge': 'Radial gauge for showing single values',
            'gauge': 'Speedometer-style gauge chart',
            'funnel': 'Funnel chart for conversion processes',
            'sankey': 'Sankey diagram for flow visualization',
            'sparkline': 'Minimal line chart without axes',
            'progressBar': 'Progress bar for completion percentages',
            'candlestick': 'Candlestick chart for financial data (OHLC)',
            'ohlc': 'OHLC chart for financial data'
        },
        'usage_examples': {
            'bar': "create_chart_from_data(chart_type='bar', data={'labels': ['A', 'B', 'C'], 'datasets': [{'data': [10, 20, 30]}]})",
            'radar': "create_chart_from_data(chart_type='radar', data={'labels': ['Speed', 'Power', 'Efficiency'], 'datasets': [{'data': [80, 90, 70]}]})",
            'bubble': "create_chart_from_data(chart_type='bubble', data={'datasets': [{'data': [{'x': 10, 'y': 20, 'r': 15}]}]})"
        }
    }

def get_beautiful_colors(chart_type: str, data_count: int, theme: str = 'modern') -> List[str]:
    """
    Get a beautiful color palette based on chart type and theme.
    
    Args:
        chart_type: Type of chart (pie, bar, line, etc.)
        data_count: Number of data points/series
        theme: Color theme to use
        
    Returns:
        List of color codes
    """
    palette = COLOR_PALETTES.get(theme, COLOR_PALETTES['modern'])
    
    # For pie charts, use more diverse colors
    if chart_type in ['pie', 'doughnut']:
        if data_count <= len(palette):
            return palette[:data_count]
        else:
            # Generate additional colors by cycling through palette
            colors = []
            for i in range(data_count):
                colors.append(palette[i % len(palette)])
            return colors
    
    # For bar/line charts, use gradient or complementary colors
    elif chart_type in ['bar', 'line', 'area']:
        if data_count == 1:
            return [palette[0]]
        elif data_count <= 3:
            return palette[:data_count]
        else:
            # Use evenly spaced colors from palette
            step = len(palette) // data_count
            return [palette[i * step] for i in range(data_count)]
    
    # Default: return first N colors
    return palette[:min(data_count, len(palette))]

def apply_beautiful_styling(chart_config: Dict[str, Any], style_theme: str = 'modern') -> Dict[str, Any]:
    """
    Apply beautiful styling to chart configuration.
    
    Args:
        chart_config: Base chart configuration
        style_theme: Styling theme to apply
        
    Returns:
        Enhanced chart configuration with beautiful styling
    """
    style = CHART_STYLES.get(style_theme, CHART_STYLES['modern'])
    
    # Ensure options exist
    if 'options' not in chart_config:
        chart_config['options'] = {}
    
    options = chart_config['options']
    
    # Apply font styling
    options['font'] = {
        'family': style['font_family'],
        'size': style['label_size']
    }
    
    # Enhanced title styling
    if 'plugins' not in options:
        options['plugins'] = {}
    
    if 'title' in options['plugins']:
        title_config = options['plugins']['title']
        title_config.update({
            'font': {
                'family': style['font_family'],
                'size': style['title_size'],
                'weight': 'bold'
            },
            'color': style['text_color'],
            'padding': 20
        })
    
    # Enhanced legend styling
    if 'legend' not in options['plugins']:
        options['plugins']['legend'] = {}
    
    options['plugins']['legend'].update({
        'labels': {
            'font': {
                'family': style['font_family'],
                'size': style['legend_size']
            },
            'color': style['text_color'],
            'padding': 15,
            'usePointStyle': True
        },
        'position': 'bottom'
    })
    
    # Chart-specific styling
    chart_type = chart_config.get('type', '')
    
    if chart_type in ['bar', 'line']:
        # Enhanced scales for bar/line charts
        if 'scales' not in options:
            options['scales'] = {}
        
        # X-axis styling
        if 'x' not in options['scales']:
            options['scales']['x'] = {}
        
        options['scales']['x'].update({
            'grid': {
                'color': style['grid_color'],
                'lineWidth': 1
            },
            'ticks': {
                'font': {
                    'family': style['font_family'],
                    'size': style['label_size']
                },
                'color': style['text_color']
            }
        })
        
        # Y-axis styling
        if 'y' not in options['scales']:
            options['scales']['y'] = {}
        
        options['scales']['y'].update({
            'grid': {
                'color': style['grid_color'],
                'lineWidth': 1
            },
            'ticks': {
                'font': {
                    'family': style['font_family'],
                    'size': style['label_size']
                },
                'color': style['text_color']
            }
        })
    
    # Enhanced responsiveness and layout
    options.update({
        'responsive': True,
        'maintainAspectRatio': False,
        'layout': {
            'padding': {
                'top': 20,
                'right': 20,
                'bottom': 20,
                'left': 20
            }
        }
    })
    
    return chart_config

def enhance_chart_data_colors(data: Dict[str, Any], chart_type: str, color_theme: str = 'modern') -> Dict[str, Any]:
    """
    Enhance chart data with beautiful colors.
    
    Args:
        data: Chart data configuration
        chart_type: Type of chart
        color_theme: Color theme to use
        
    Returns:
        Enhanced data configuration with beautiful colors
    """
    if 'datasets' not in data:
        return data
    
    for i, dataset in enumerate(data['datasets']):
        data_count = len(dataset.get('data', []))
        colors = get_beautiful_colors(chart_type, data_count, color_theme)
        
        if chart_type in ['pie', 'doughnut', 'polarArea']:
            # For pie-like charts, each slice gets a different color
            dataset['backgroundColor'] = colors
            dataset['borderColor'] = '#ffffff'
            dataset['borderWidth'] = 2
        elif chart_type in ['line', 'area']:
            # For line charts, use single color with transparency for fill
            color = colors[i % len(colors)]
            dataset['borderColor'] = color
            dataset['backgroundColor'] = color + '20'  # Add transparency
            dataset['borderWidth'] = 3
            dataset['pointBackgroundColor'] = color
            dataset['pointBorderColor'] = '#ffffff'
            dataset['pointBorderWidth'] = 2
            dataset['pointRadius'] = 4
            dataset['tension'] = 0.4  # Smooth curves
        elif chart_type in ['bar', 'horizontalBar']:
            # For bar charts, use gradient-like colors
            color = colors[i % len(colors)]
            dataset['backgroundColor'] = color
            dataset['borderColor'] = color
            dataset['borderWidth'] = 1
            dataset['borderRadius'] = 4
            dataset['borderSkipped'] = False
        elif chart_type == 'radar':
            # For radar charts, use transparent fill with colored border
            color = colors[i % len(colors)]
            dataset['backgroundColor'] = color + '30'  # More transparency
            dataset['borderColor'] = color
            dataset['pointBackgroundColor'] = color
            dataset['pointBorderColor'] = '#ffffff'
            dataset['borderWidth'] = 2
            dataset['pointRadius'] = 3
        elif chart_type in ['scatter', 'bubble']:
            # For scatter/bubble charts, use solid colors
            color = colors[i % len(colors)]
            dataset['backgroundColor'] = color
            dataset['borderColor'] = color + 'CC'  # Slightly transparent border
        elif chart_type in ['violin', 'boxplot', 'horizontalBoxPlot', 'horizontalViolin']:
            # For statistical charts, use subtle colors
            color = colors[i % len(colors)]
            dataset['backgroundColor'] = color + '40'  # More transparency
            dataset['borderColor'] = color
            dataset['borderWidth'] = 2
        elif chart_type in ['radialGauge', 'gauge']:
            # For gauge charts, use gradient colors
            if 'backgroundColor' not in dataset:
                dataset['backgroundColor'] = colors[:min(len(colors), 3)]
        elif chart_type == 'funnel':
            # For funnel charts, use gradient from dark to light
            dataset['backgroundColor'] = colors
        elif chart_type in ['candlestick', 'ohlc']:
            # For financial charts, use traditional colors
            dataset['color'] = {
                'up': '#26a69a',    # Green for up
                'down': '#ef5350',  # Red for down
                'unchanged': '#757575'  # Gray for unchanged
            }
        elif chart_type == 'progressBar':
            # For progress bars, use single color
            color = colors[0]
            dataset['backgroundColor'] = color
            dataset['borderColor'] = color
        elif chart_type == 'sparkline':
            # For sparklines, use simple line styling
            color = colors[0]
            dataset['borderColor'] = color
            dataset['backgroundColor'] = 'transparent'
            dataset['borderWidth'] = 2
        # For sankey and other special charts, keep original data structure
    
    return data 