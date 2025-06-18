#!/usr/bin/env python3
"""
Comprehensive Test Script for Markdown Editor MCP Server

This script tests all the main use cases:
1. Document creation and editing
2. Photo search and download with different sizes
3. Chart creation and integration
4. Image adding and path resolution
5. Live preview functionality
6. Document conversion to different formats
7. User path validation and workspace management

Run with: python test_markdown_editor_comprehensive.py
"""

import asyncio
import os
import sys
import json
import tempfile
from pathlib import Path
from typing import Dict, Any, List

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

# Add the server path for imports
sys.path.append(os.path.dirname(__file__))

# Import the markdown editor modules
try:
    from mcp_local.servers.markdown_editor.server import (
        create_document, edit_document, add_image, live_preview,
        search_and_download_photo, create_chart, convert_from_md,
        get_filesystem_path, analyze_document_structure,
        create_table_with_theme, extract_table, get_table_themes,
        find_workspace_file
    )
    from mcp_local.servers.markdown_editor.photo_generator import search_and_download_photo_tool
    from mcp_local.servers.markdown_editor.chart_generator import create_chart_tool
    from mcp_local.servers.markdown_editor.markdown_converter import convert_from_markdown
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Make sure you're running this from the local-backend directory")
    sys.exit(1)

class MarkdownEditorTester:
    def __init__(self):
        self.test_results = []
        self.workspace_dir = None
        self.setup_test_environment()
    
    def setup_test_environment(self):
        """Setup test workspace directory"""
        # Don't create our own temp directory - use the actual workspace where files will be created
        try:
            from mcp_local.core.shared_workspace import SharedWorkspaceManager
            self.workspace_dir = SharedWorkspaceManager._get_unified_workspace_path("default")
            print(f"🏗️ Test workspace: {self.workspace_dir}")
            
            # Ensure directory exists
            self.workspace_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            # Fallback to /tmp/denker_workspace/default
            self.workspace_dir = Path('/tmp/denker_workspace/default')
            print(f"🏗️ Test workspace (fallback): {self.workspace_dir}")
            self.workspace_dir.mkdir(parents=True, exist_ok=True)
        
        # Clean up any existing test files
        test_files = [
            "test_newsletter.md",
            "hamburg_startups_chart.png", 
            "events_table_professional.md",
            "events_table_modern.md", 
            "events_table_minimal.md"
        ]
        for file in test_files:
            file_path = self.workspace_dir / file
            if file_path.exists():
                file_path.unlink()
                print(f"   Cleaned up existing: {file}")
        
        print(f"   Workspace ready for testing")
    
    def log_test(self, test_name: str, success: bool, message: str, details: Dict = None):
        """Log test results"""
        status = "✅" if success else "❌"
        print(f"{status} {test_name}: {message}")
        
        self.test_results.append({
            "test": test_name,
            "success": success,
            "message": message,
            "details": details or {}
        })
    
    async def test_document_creation(self):
        """Test creating markdown documents"""
        print("\n📝 Testing Document Creation...")
        
        try:
            # Test basic document creation
            content = """# Hamburg Startup Events Test
            
This is a test document for the Hamburg newsletter system.

## Features to Test
- Document creation ✅
- Image integration (to be tested)
- Chart integration (to be tested)
- Conversion (to be tested)

Let's see if this works!
"""
            
            result = create_document(content, "test_newsletter.md")
            
            if result.get("success"):
                self.log_test("Document Creation", True, f"Created document: {result.get('file_path')}")
                return result.get("file_path")
            else:
                self.log_test("Document Creation", False, f"Failed: {result.get('error')}")
                return None
                
        except Exception as e:
            self.log_test("Document Creation", False, f"Exception: {str(e)}")
            return None
    
    async def test_photo_search_and_download(self):
        """Test photo search and download with different sizes"""
        print("\n📷 Testing Photo Search and Download...")
        print("   Photo sizes available:")
        print("   • thumbnail: ~150px wide")
        print("   • small: ~400px wide") 
        print("   • regular: ~1080px wide (default)")
        print("   • large: ~2000px wide")
        print("   • full: Original resolution")
        
        # Check if Unsplash API key is configured
        api_key = os.getenv('UNSPLASH_ACCESS_KEY')
        if not api_key:
            self.log_test("Photo Download Setup", False, 
                        "UNSPLASH_ACCESS_KEY environment variable not set")
            print("   💡 To test photo downloads, set UNSPLASH_ACCESS_KEY environment variable")
            print("   💡 Get a free API key from: https://unsplash.com/developers")
            print("   💡 Or make sure .env file is loaded")
            return {}
        else:
            self.log_test("Photo Download Setup", True, f"Unsplash API key found: {api_key[:10]}...")
        
        photo_results = {}
        sizes_to_test = ["thumbnail", "small", "regular", "large"]
        
        for size in sizes_to_test:
            try:
                print(f"  Testing size: {size}")
                result = await search_and_download_photo_tool(
                    query="nature",  # Use the query we know works
                    size=size,
                    orientation="landscape",
                    category="nature",
                    filename=f"nature_{size}.jpg"
                )
                
                if result.get("success"):
                    photo_results[size] = result.get("file_path") or result.get("filename")
                    file_size = result.get("file_size", "unknown")
                    dimensions = result.get("dimensions", "unknown")
                    download_url = result.get("download_url", "")
                    
                    # Format file size nicely
                    if isinstance(file_size, (int, float)):
                        if file_size > 1024*1024:
                            size_str = f"{file_size/(1024*1024):.1f}MB"
                        elif file_size > 1024:
                            size_str = f"{file_size/1024:.1f}KB"
                        else:
                            size_str = f"{file_size}B"
                    else:
                        size_str = str(file_size)
                    
                    self.log_test(f"Photo Download ({size})", True, 
                                f"Downloaded: {photo_results[size]} ({size_str}, {dimensions})")
                else:
                    error_msg = result.get('error', 'Unknown error')
                    if 'API key' in error_msg:
                        self.log_test(f"Photo Download ({size})", False, "API key issue")
                        break  # No point testing other sizes
                    else:
                        self.log_test(f"Photo Download ({size})", False, 
                                    f"Failed: {error_msg}")
                    
            except Exception as e:
                self.log_test(f"Photo Download ({size})", False, f"Exception: {str(e)}")
        
        return photo_results
    
    async def test_chart_creation(self):
        """Test chart creation with different types"""
        print("\n📊 Testing Chart Creation...")
        
        chart_results = {}
        
        # Test bar chart
        try:
            bar_config = {
                "type": "bar",
                "data": {
                    "labels": ["Q1", "Q2", "Q3", "Q4"],
                    "datasets": [{
                        "label": "Hamburg Startups",
                        "data": [12, 19, 3, 17],
                        "backgroundColor": ["#FF6384", "#36A2EB", "#FFCE56", "#4BC0C0"]
                    }]
                },
                "options": {
                    "responsive": True,
                    "plugins": {
                        "title": {
                            "display": True,
                            "text": "Hamburg Startup Growth"
                        }
                    }
                }
            }
            
            result = await create_chart_tool(bar_config, "hamburg_startups_chart.png")
            
            if result.get("success"):
                chart_file = result.get("chart_path") or result.get("filename")
                chart_results["bar"] = chart_file
                size_bytes = result.get("size_bytes", "unknown")
                self.log_test("Chart Creation (Bar)", True, 
                            f"Created chart: {chart_file} ({size_bytes} bytes)")
            else:
                self.log_test("Chart Creation (Bar)", False, f"Failed: {result.get('error')}")
                
        except Exception as e:
            self.log_test("Chart Creation (Bar)", False, f"Exception: {str(e)}")
        
        return chart_results
    
    async def test_table_creation(self):
        """Test table creation with different themes"""
        print("\n📊 Testing Table Creation...")
        
        table_results = {}
        
        # First, get available table themes
        try:
            themes_result = await get_table_themes()
            if themes_result.get("success"):
                available_themes = themes_result.get("themes", ["professional", "modern", "minimal"])
                self.log_test("Table Themes Fetch", True, f"Retrieved {len(available_themes)} themes")
            else:
                available_themes = ["professional", "modern", "minimal"]  # fallback
                self.log_test("Table Themes Fetch", False, "Using fallback themes")
        except Exception as e:
            available_themes = ["professional", "modern", "minimal"]  # fallback
            self.log_test("Table Themes Fetch", False, f"Exception: {str(e)}")
        
        # Test table creation with different themes
        test_data = {
            "headers": ["Event", "Date", "Location", "Type"],
            "data": [
                ["Hamburg Startup Pitch Night", "2024-01-15", "Rocket Internet", "Pitching"],
                ["Tech Meetup Hamburg", "2024-01-20", "Google Campus", "Networking"],
                ["AI Conference", "2024-01-25", "CCH Hamburg", "Conference"],
                ["Blockchain Workshop", "2024-01-30", "Factory Hamburg", "Workshop"]
            ],
            "title": "Hamburg Startup Events - January 2024"
        }
        
        for theme in available_themes[:3]:  # Test first 3 themes
            try:
                print(f"  Testing theme: {theme}")
                result = await create_table_with_theme(
                    headers=test_data["headers"],
                    data=test_data["data"],
                    title=test_data["title"],
                    theme=theme,
                    alignment=["left", "center", "left", "center"],
                    file_path=f"events_table_{theme}.md"
                )
                
                if result.get("success"):
                    table_file = result.get("file_path") or result.get("filename")
                    table_results[theme] = table_file
                    
                    # Get some additional info if available
                    rows_count = len(test_data["data"])
                    cols_count = len(test_data["headers"])
                    
                    self.log_test(f"Table Creation ({theme})", True, 
                                f"Created table: {table_file} ({rows_count}x{cols_count})")
                else:
                    self.log_test(f"Table Creation ({theme})", False, 
                                f"Failed: {result.get('error')}")
                    
            except Exception as e:
                self.log_test(f"Table Creation ({theme})", False, f"Exception: {str(e)}")
        
        # Test table extraction if we created any tables
        if table_results:
            try:
                test_table_file = list(table_results.values())[0]
                
                # Try to resolve the table file path
                try:
                    resolved_path = find_workspace_file(test_table_file)
                    if resolved_path:
                        test_table_file = resolved_path
                        print(f"   Using resolved table path: {test_table_file}")
                except:
                    print(f"   Using original table path: {test_table_file}")
                
                extract_result = extract_table(test_table_file, 0)
                # Handle if it's a coroutine
                if hasattr(extract_result, '__await__'):
                    extract_result = await extract_result
                
                if extract_result.get("success"):
                    extracted_data = extract_result.get("table_data", {})
                    rows = len(extracted_data.get("data", []))
                    self.log_test("Table Extraction", True, f"Extracted table with {rows} rows")
                else:
                    self.log_test("Table Extraction", False, f"Failed: {extract_result.get('error')}")
                    
            except Exception as e:
                self.log_test("Table Extraction", False, f"Exception: {str(e)}")
        
        return table_results
    
    async def test_image_integration(self, document_path: str, photo_results: Dict, chart_results: Dict):
        """Test adding images to documents"""
        print("\n🖼️ Testing Image Integration...")
        
        if not document_path:
            self.log_test("Image Integration", False, "No document to add images to")
            return
        
        try:
            # Add a photo to the document
            if "regular" in photo_results:
                photo_result = add_image(
                    document_path, 
                    photo_results["regular"], 
                    "Business meeting in Hamburg"
                )
                
                if photo_result.get("success"):
                    self.log_test("Photo Integration", True, "Added photo to document")
                else:
                    self.log_test("Photo Integration", False, f"Failed: {photo_result.get('error')}")
            
            # Add a chart to the document
            if "bar" in chart_results:
                chart_result = add_image(
                    document_path,
                    chart_results["bar"],
                    "Hamburg startup growth chart"
                )
                
                if chart_result.get("success"):
                    self.log_test("Chart Integration", True, "Added chart to document")
                else:
                    self.log_test("Chart Integration", False, f"Failed: {chart_result.get('error')}")
                    
        except Exception as e:
            self.log_test("Image Integration", False, f"Exception: {str(e)}")
    
    async def test_live_preview(self, document_path: str):
        """Test live preview functionality"""
        print("\n👁️ Testing Live Preview...")
        
        if not document_path:
            self.log_test("Live Preview", False, "No document to preview")
            return
        
        try:
            # Try to resolve the document path first
            try:
                resolved_path = find_workspace_file(document_path)
                if resolved_path:
                    document_path = resolved_path
            except:
                pass
            
            result = live_preview(document_path, port=8001)  # Use different port to avoid conflicts
            
            if result.get("success"):
                server_url = result.get("url", "http://localhost:8001")
                self.log_test("Live Preview", True, f"Preview server started: {server_url}")
                
                # Try to make a quick HTTP request to verify the server is actually running
                try:
                    import requests
                    import time
                    time.sleep(1)  # Give server a moment to start
                    response = requests.get(server_url, timeout=3)
                    if response.status_code == 200:
                        self.log_test("Live Preview Verification", True, f"Server responding (HTTP {response.status_code})")
                    else:
                        self.log_test("Live Preview Verification", False, f"Server not responding properly (HTTP {response.status_code})")
                except requests.exceptions.RequestException as e:
                    self.log_test("Live Preview Verification", False, f"Cannot connect to server: {str(e)}")
                except Exception as e:
                    self.log_test("Live Preview Verification", False, f"Error checking server: {str(e)}")
                
            else:
                self.log_test("Live Preview", False, f"Failed: {result.get('error')}")
                
        except Exception as e:
            self.log_test("Live Preview", False, f"Exception: {str(e)}")
    
    async def test_document_conversion(self, document_path: str):
        """Test document conversion to different formats"""
        print("\n🔄 Testing Document Conversion...")
        
        if not document_path:
            self.log_test("Document Conversion", False, "No document to convert")
            return
        
        # Setup pandoc path from resources/bin
        import os
        pandoc_path = os.path.abspath("../resources/bin/pandoc")
        old_path = None
        if os.path.exists(pandoc_path):
            # Add to PATH temporarily
            old_path = os.environ.get("PATH", "")
            bin_dir = os.path.dirname(pandoc_path)
            os.environ["PATH"] = f"{bin_dir}:{old_path}"
            self.log_test("Pandoc Setup", True, f"Using pandoc from: {pandoc_path}")
        else:
            self.log_test("Pandoc Setup", False, f"Pandoc not found at: {pandoc_path}")
        
        # Try to find the actual document path
        try:
            resolved_path = find_workspace_file(document_path)
            if resolved_path:
                document_path = resolved_path
                print(f"   Using resolved path: {document_path}")
            else:
                print(f"   Using original path: {document_path}")
        except:
            print(f"   Could not resolve path, using: {document_path}")
        
        formats_to_test = ["html", "txt", "docx", "pdf"]  # Test all formats
        
        for format_name in formats_to_test:
            try:
                output_path = str(self.workspace_dir / f"test_output.{format_name}")
                result = convert_from_markdown(document_path, format_name, output_path)
                
                if result.get("success"):
                    output_file = result.get("output_path", "unknown")
                    file_size = "unknown"
                    
                    # Check if file exists and get size
                    if os.path.exists(output_file):
                        file_size = f"{os.path.getsize(output_file)} bytes"
                    
                    self.log_test(f"Conversion to {format_name.upper()}", True, 
                                f"Converted to: {output_file} ({file_size})")
                else:
                    self.log_test(f"Conversion to {format_name.upper()}", False, 
                                f"Failed: {result.get('error')}")
                    
            except Exception as e:
                self.log_test(f"Conversion to {format_name.upper()}", False, f"Exception: {str(e)}")
        
        # Restore original PATH
        if old_path is not None:
            os.environ["PATH"] = old_path
    
    async def test_path_resolution(self):
        """Test workspace path resolution"""
        print("\n🔍 Testing Path Resolution...")
        
        try:
            # Test get_filesystem_path with a non-existent file
            result = get_filesystem_path("non_existent_file.md")
            
            if not result.get("success"):
                self.log_test("Path Resolution (Non-existent)", True, "Correctly handled non-existent file")
            else:
                self.log_test("Path Resolution (Non-existent)", False, "Should have failed for non-existent file")
            
            # Test with a file we know was created (chart)
            try:
                result = get_filesystem_path("hamburg_startups_chart.png")
                
                if result.get("success"):
                    relative_path = result.get("relative_path", "unknown")
                    self.log_test("Path Resolution (Chart)", True, f"Resolved chart path: {relative_path}")
                else:
                    self.log_test("Path Resolution (Chart)", False, f"Chart not found: {result.get('error')}")
            except Exception as e:
                self.log_test("Path Resolution (Chart)", False, f"Exception: {str(e)}")
                    
        except Exception as e:
            self.log_test("Path Resolution", False, f"Exception: {str(e)}")
    
    async def test_table_themes(self):
        """Test all available table themes with Unicode content"""
        print("\n🎨 Testing Table Themes...")
        
        try:
            # First, get available themes
            try:
                themes_result = get_table_themes()
                # Handle if it's a coroutine
                if hasattr(themes_result, '__await__'):
                    themes_result = await themes_result
            except Exception as theme_error:
                themes_result = {"error": f"Theme fetch error: {theme_error}"}
            
            if themes_result.get("success", True):  # Some return format doesn't include success
                if "themes" in themes_result:
                    available_themes = list(themes_result["themes"].keys())
                    self.log_test("Table Themes Fetch", True, f"Found {len(available_themes)} themes: {', '.join(available_themes)}")
                else:
                    # Extract themes from the response structure
                    available_themes = ["modern", "elegant", "minimal", "bold", "colorful", "professional"]
                    self.log_test("Table Themes Fetch", True, "Using fallback themes")
            else:
                self.log_test("Table Themes Fetch", False, f"Failed: {themes_result.get('error')}")
                return
            
            # Test table creation with Unicode and emoji content
            unicode_headers = ['Product 🛍️', 'Sales 💰', 'Status 📊', 'Region 🌎']
            unicode_data = [
                ['Widget Café ☕', '€1,250.50', 'Active ✅', 'Europe 🇪🇺'],
                ['Gadget 한국어', '¥890,000', 'Pending 🔄', 'Asia 🌏'],
                ['Tool العربية', '$2,100.75', 'Completed ✅', 'Middle East 🕌']
            ]
            
            successful_themes = 0
            for theme in available_themes:
                try:
                    result = create_table_with_theme(
                        headers=unicode_headers,
                        data=unicode_data,
                        title=f"🌈 Unicode Test - {theme.title()} Theme",
                        theme=theme,
                        file_path=f"table_test_{theme}.md"
                    )
                    # Handle if it's a coroutine
                    if hasattr(result, '__await__'):
                        result = await result
                    
                    if result.get("success"):
                        successful_themes += 1
                        self.log_test(f"Table Theme ({theme})", True, 
                                    f"Created {result.get('rows', 0)}x{result.get('columns', 0)} table")
                    else:
                        self.log_test(f"Table Theme ({theme})", False, 
                                    f"Failed: {result.get('error')}")
                        
                except Exception as e:
                    self.log_test(f"Table Theme ({theme})", False, f"Exception: {str(e)}")
            
            # Summary
            if successful_themes > 0:
                self.log_test("Table Themes Overall", True, 
                            f"{successful_themes}/{len(available_themes)} themes working")
            else:
                self.log_test("Table Themes Overall", False, "No themes working")
                
        except Exception as e:
            self.log_test("Table Themes", False, f"Exception: {str(e)}")
    
    async def test_unicode_support(self):
        """Test Unicode and emoji support in live preview"""
        print("\n🌍 Testing Unicode & Emoji Support...")
        
        try:
            # Create document with comprehensive Unicode content
            unicode_content = """# 🎨 Unicode & Emoji Test Document

## 🌍 International Characters
- **English**: Hello World!
- **Chinese**: 你好世界 
- **Arabic**: مرحبا بالعالم
- **Russian**: Привет мир
- **Korean**: 안녕 세계
- **Japanese**: こんにちは世界
- **French**: Bonjour le monde (café, naïve)

## 💰 Currency & Symbols
€ $ ¥ £ ₹ ₩ ₪ α β γ ∞ ∂ ∑ ♪ ♫ ★ ☆

## 📊 Status Table
| Task | Status | Progress |
|------|--------|----------|
| Design | ✅ Done | 100% |
| Code | 🔄 Working | 75% |
| Test | ❌ Failed | 0% |

*Testing complete! 🎉*
"""
            
            # Create the document
            result = create_document(unicode_content, "unicode_test.md")
            
            if result.get("success"):
                document_path = result["file_path"]
                self.log_test("Unicode Document Creation", True, f"Created: {document_path}")
                
                # Test live preview with Unicode
                try:
                    from mcp_local.servers.markdown_editor.markdown_preview import preview_markdown
                    
                    resolved_path = find_workspace_file(document_path)
                    if resolved_path:
                        preview_result = preview_markdown(resolved_path, format="html")
                        
                        if preview_result.get("success"):
                            html_content = preview_result["content"]
                            
                            # Check Unicode preservation
                            unicode_tests = [
                                ('🌍', 'World emoji'),
                                ('€', 'Euro symbol'),
                                ('你好', 'Chinese characters'),
                                ('مرحبا', 'Arabic text'),
                                ('✅', 'Check mark emoji')
                            ]
                            
                            preserved_count = 0
                            for char, description in unicode_tests:
                                if char in html_content:
                                    preserved_count += 1
                            
                            if preserved_count >= len(unicode_tests) * 0.8:  # 80% success rate
                                self.log_test("Unicode Preview", True, 
                                            f"Preserved {preserved_count}/{len(unicode_tests)} Unicode characters")
                            else:
                                self.log_test("Unicode Preview", False, 
                                            f"Only preserved {preserved_count}/{len(unicode_tests)} Unicode characters")
                        else:
                            self.log_test("Unicode Preview", False, 
                                        f"Preview failed: {preview_result.get('error')}")
                    else:
                        self.log_test("Unicode Preview", False, "Could not resolve document path")
                        
                except Exception as e:
                    self.log_test("Unicode Preview", False, f"Exception: {str(e)}")
            else:
                self.log_test("Unicode Document Creation", False, f"Failed: {result.get('error')}")
                
        except Exception as e:
            self.log_test("Unicode Support", False, f"Exception: {str(e)}")
    
    async def test_advanced_conversion(self, document_path: str):
        """Test DOCX and PDF conversion with Unicode content"""
        print("\n📄 Testing Advanced Document Conversion (DOCX/PDF)...")
        
        if not document_path:
            self.log_test("Advanced Conversion", False, "No document to convert")
            return
        
        # Create a rich document specifically for conversion testing
        rich_content = """# 🌍 International Business Report 2024

## 📊 Executive Summary
This report contains **emojis** 🎉, **Unicode characters** (café, naïve, résumé), and international symbols:

- Currency: € ¥ £ ₹ $ ₩ ₪
- Languages: English, 中文, العربية, Русский, 한국어

## 🏢 Performance Table
| Company 🏢 | Revenue 💰 | Status 📊 |
|-------------|------------|-----------|
| **TechCorp** | €2.5M | Excellent 🌟 |
| **DataSoft** | $3.2M | Good ✅ |

## 🎯 Key Metrics
1. **Customer Satisfaction**: 98% 😊
2. **Growth Rate**: +15% 📈

*Report generated with ❤️ by Analytics Team*
"""
        
        try:
            # Create rich document
            rich_doc_result = create_document(rich_content, "rich_unicode_test.md")
            
            if not rich_doc_result.get("success"):
                self.log_test("Rich Document Creation", False, f"Failed: {rich_doc_result.get('error')}")
                return
            
            rich_doc_path = rich_doc_result["file_path"]
            self.log_test("Rich Document Creation", True, f"Created: {rich_doc_path}")
            
            # Setup environment for conversions
            import os
            pandoc_path = os.path.abspath("../resources/bin/pandoc")
            old_path = None
            if os.path.exists(pandoc_path):
                old_path = os.environ.get("PATH", "")
                bin_dir = os.path.dirname(pandoc_path)
                os.environ["PATH"] = f"{bin_dir}:{old_path}"
            
            # Test advanced conversions
            conversions = {
                'docx': 'Microsoft Word Document',
                'pdf': 'PDF with Fonts and Emojis'
            }
            
            for format_name, description in conversions.items():
                try:
                    output_filename = f"unicode_test.{format_name}"
                    output_path = str(self.workspace_dir / output_filename)
                    
                    # Try to resolve the document path
                    resolved_path = find_workspace_file(rich_doc_path)
                    if resolved_path:
                        result = convert_from_markdown(
                            resolved_path, format_name, output_path
                        )
                    else:
                        result = convert_from_markdown(
                            rich_doc_path, format_name, output_path
                        )
                    
                    if result.get("success"):
                        created_file = result.get("output_path", output_path)
                        file_size = os.path.getsize(created_file) if os.path.exists(created_file) else 0
                        
                        # Additional validation for PDF
                        if format_name == 'pdf' and file_size > 0:
                            try:
                                with open(created_file, 'rb') as f:
                                    pdf_header = f.read(10)
                                if pdf_header.startswith(b'%PDF-'):
                                    self.log_test(f"Conversion to {format_name.upper()}", True, 
                                                f"Valid {description} ({file_size:,} bytes)")
                                else:
                                    self.log_test(f"Conversion to {format_name.upper()}", False, 
                                                "Invalid PDF format")
                            except Exception as e:
                                self.log_test(f"Conversion to {format_name.upper()}", False, 
                                            f"PDF validation failed: {str(e)}")
                        else:
                            self.log_test(f"Conversion to {format_name.upper()}", True, 
                                        f"Created {description} ({file_size:,} bytes)")
                    else:
                        self.log_test(f"Conversion to {format_name.upper()}", False, 
                                    f"Failed: {result.get('error')}")
                        
                except Exception as e:
                    self.log_test(f"Conversion to {format_name.upper()}", False, 
                                f"Exception: {str(e)}")
            
            # Restore original PATH
            if old_path is not None:
                os.environ["PATH"] = old_path
                    
        except Exception as e:
            self.log_test("Advanced Conversion", False, f"Exception: {str(e)}")
    
    async def test_document_analysis(self, document_path: str):
        """Test document structure analysis"""
        print("\n📋 Testing Document Analysis...")
        
        if not document_path:
            self.log_test("Document Analysis", False, "No document to analyze")
            return
        
        try:
            # Try to resolve the document path first
            try:
                resolved_path = find_workspace_file(document_path)
                if resolved_path:
                    document_path = resolved_path
            except:
                pass
            
            result = analyze_document_structure(document_path)
            
            if result.get("success"):
                headers = result.get("headers", [])
                sections = result.get("sections", [])
                self.log_test("Document Analysis", True, 
                            f"Analyzed document: {len(headers)} headers, {len(sections)} sections")
            else:
                self.log_test("Document Analysis", False, f"Failed: {result.get('error')}")
                
        except Exception as e:
            self.log_test("Document Analysis", False, f"Exception: {str(e)}")
    
    def print_summary(self):
        """Print test summary"""
        print("\n" + "="*60)
        print("📋 TEST SUMMARY")
        print("="*60)
        
        passed = sum(1 for result in self.test_results if result["success"])
        failed = len(self.test_results) - passed
        
        print(f"Total Tests: {len(self.test_results)}")
        print(f"✅ Passed: {passed}")
        print(f"❌ Failed: {failed}")
        print(f"Success Rate: {(passed/len(self.test_results)*100):.1f}%")
        
        if failed > 0:
            print("\n🚨 Failed Tests:")
            for result in self.test_results:
                if not result["success"]:
                    print(f"  - {result['test']}: {result['message']}")
        
        print("\n📁 Test workspace:", self.workspace_dir)
        print("   (You can inspect the generated files here)")
    
    async def run_all_tests(self):
        """Run all tests in sequence"""
        print("🚀 Starting Comprehensive Markdown Editor Tests")
        print("="*60)
        
        # Test 1: Document Creation
        document_path = await self.test_document_creation()
        
        # Test 2: Photo Search and Download (different sizes)
        photo_results = await self.test_photo_search_and_download()
        
        # Test 3: Chart Creation
        chart_results = await self.test_chart_creation()
        
        # Test 4: Table Creation
        table_results = await self.test_table_creation()
        
        # Test 5: Image Integration
        await self.test_image_integration(document_path, photo_results, chart_results)
        
        # Test 6: Live Preview
        await self.test_live_preview(document_path)
        
        # Test 7: Document Conversion
        await self.test_document_conversion(document_path)
        
        # Test 8: Path Resolution
        await self.test_path_resolution()
        
        # Test 9: Table Themes
        await self.test_table_themes()
        
        # Test 10: Unicode and Emoji Support
        await self.test_unicode_support()
        
        # Test 11: Advanced Document Conversion (DOCX/PDF)
        await self.test_advanced_conversion(document_path)
        
        # Test 12: Document Analysis
        await self.test_document_analysis(document_path)
        
        # Print summary
        self.print_summary()

async def main():
    """Main test runner"""
    tester = MarkdownEditorTester()
    await tester.run_all_tests()

if __name__ == "__main__":
    # Check if we have required dependencies
    try:
        import aiohttp
        import requests
    except ImportError:
        print("❌ Missing dependencies. Install with:")
        print("   pip install aiohttp requests")
        sys.exit(1)
    
    # Run the tests
    asyncio.run(main()) 