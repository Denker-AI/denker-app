"""
Markdown preview utilities for the Markdown Editor MCP server.
Provides functions to preview and render Markdown content.
"""

import os
import tempfile
import threading
import logging
import json
import base64
import urllib.parse
import webbrowser
from typing import Dict, Any, List, Optional
from http.server import HTTPServer, BaseHTTPRequestHandler

logger = logging.getLogger("markdown-editor")

def preview_markdown(file_path: str, format: str = "html") -> Dict[str, Any]:
    """
    Generate a preview of a Markdown document.
    
    Args:
        file_path: Path to the Markdown file
        format: Preview format ('html' or 'text')
        
    Returns:
        Preview content
    """
    try:
        if not os.path.exists(file_path):
            return {
                "success": False,
                "error": f"File not found: {file_path}"
            }
        
        # Read markdown content
        with open(file_path, 'r', encoding='utf-8') as f:
            md_content = f.read()
        
        if format.lower() == "html":
            # Import markdown with appropriate extensions
            try:
                import markdown
                from markdown.extensions import fenced_code, tables, toc
                
                # Convert to HTML with extensions
                html = markdown.markdown(
                    md_content,
                    extensions=[
                        'markdown.extensions.tables',
                        'markdown.extensions.fenced_code',
                        'markdown.extensions.codehilite',
                        'markdown.extensions.toc',
                        'markdown.extensions.nl2br',
                        'markdown.extensions.extra'
                    ]
                )
            except ImportError:
                # Fallback to simpler rendering if markdown package is not available
                try:
                    import commonmark
                    parser = commonmark.Parser()
                    ast = parser.parse(md_content)
                    renderer = commonmark.HtmlRenderer()
                    html = renderer.render(ast)
                except ImportError:
                    # Very basic fallback
                    html = "<pre>" + md_content.replace("<", "&lt;").replace(">", "&gt;") + "</pre>"
                    return {
                        "success": False,
                        "error": "Markdown conversion packages not available. Install 'markdown' or 'commonmark' package."
                    }
            
            # Create a complete HTML document with styling
            styled_html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>Markdown Preview</title>
                <style>
                    body {{
                        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
                        line-height: 1.6;
                        padding: 20px;
                        max-width: 800px;
                        margin: 0 auto;
                        color: #24292e;
                    }}
                    pre, code {{
                        background-color: #f6f8fa;
                        border-radius: 3px;
                        padding: 0.2em 0.4em;
                        font-family: SFMono-Regular, Consolas, "Liberation Mono", Menlo, monospace;
                    }}
                    pre code {{
                        padding: 0;
                    }}
                    pre {{
                        padding: 16px;
                        overflow: auto;
                        line-height: 1.45;
                    }}
                    blockquote {{
                        padding: 0 1em;
                        color: #6a737d;
                        border-left: 0.25em solid #dfe2e5;
                        margin: 0;
                    }}
                    table {{
                        border-collapse: collapse;
                        width: 100%;
                        margin-bottom: 16px;
                    }}
                    table, th, td {{
                        border: 1px solid #dfe2e5;
                    }}
                    th, td {{
                        padding: 6px 13px;
                    }}
                    img {{
                        max-width: 100%;
                    }}
                    h1, h2, h3, h4, h5, h6 {{
                        margin-top: 24px;
                        margin-bottom: 16px;
                        font-weight: 600;
                        line-height: 1.25;
                    }}
                    h1 {{
                        padding-bottom: 0.3em;
                        font-size: 2em;
                        border-bottom: 1px solid #eaecef;
                    }}
                    h2 {{
                        padding-bottom: 0.3em;
                        font-size: 1.5em;
                        border-bottom: 1px solid #eaecef;
                    }}
                    a {{
                        color: #0366d6;
                        text-decoration: none;
                    }}
                    a:hover {{
                        text-decoration: underline;
                    }}
                    ul, ol {{
                        padding-left: 2em;
                    }}
                    li+li {{
                        margin-top: 0.25em;
                    }}
                </style>
            </head>
            <body>
                {html}
            </body>
            </html>
            """
            
            # Save to temp file
            html_file = tempfile.NamedTemporaryFile(delete=False, suffix='.html')
            html_path = html_file.name
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(styled_html)
            
            return {
                "success": True,
                "format": "html",
                "preview_path": html_path,
                "content": styled_html
            }
        
        elif format.lower() == "text":
            return {
                "success": True,
                "format": "text",
                "content": md_content
            }
        
        return {
            "success": False,
            "error": f"Unsupported preview format: {format}"
        }
    
    except Exception as e:
        logger.error(f"Error generating preview: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

class LivePreviewHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the live preview server."""
    
    def __init__(self, *args, markdown_file=None, **kwargs):
        self.markdown_file = markdown_file
        # Call the parent class constructor
        super().__init__(*args, **kwargs)
    
    def log_message(self, format, *args):
        # Redirect logs to the logger
        logger.info(format % args)
    
    def do_GET(self):
        """Handle GET requests."""
        if self.path == '/' or self.path == '/index.html':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            
            # Create a simple editor with split view
            with open(self.server.markdown_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>Markdown Live Editor - {os.path.basename(self.server.markdown_file)}</title>
                <style>
                    body {{ 
                        margin: 0; 
                        padding: 0; 
                        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
                        overflow: hidden;
                    }}
                    .container {{ 
                        display: flex; 
                        height: calc(100vh - 40px); 
                    }}
                    .editor, .preview {{ 
                        flex: 1; 
                        overflow: auto; 
                        box-sizing: border-box;
                    }}
                    .editor {{ 
                        border-right: 1px solid #ccc;
                        padding: 0;
                    }}
                    .preview {{
                        padding: 20px;
                        line-height: 1.6;
                        color: #24292e;
                    }}
                    #editor {{ 
                        width: 100%; 
                        height: 100%; 
                        border: none; 
                        resize: none; 
                        font-family: SFMono-Regular, Consolas, "Liberation Mono", Menlo, monospace;
                        font-size: 14px;
                        line-height: 1.6;
                        padding: 10px;
                        box-sizing: border-box;
                    }}
                    #editor:focus {{ 
                        outline: none; 
                    }}
                    pre, code {{
                        background-color: #f6f8fa;
                        border-radius: 3px;
                        font-family: SFMono-Regular, Consolas, "Liberation Mono", Menlo, monospace;
                    }}
                    pre {{ 
                        padding: 16px; 
                        overflow: auto; 
                    }}
                    code {{ 
                        padding: 0.2em 0.4em; 
                    }}
                    blockquote {{
                        padding: 0 1em;
                        color: #6a737d;
                        border-left: 0.25em solid #dfe2e5;
                        margin: 0;
                    }}
                    table {{ 
                        border-collapse: collapse; 
                        width: 100%; 
                        margin-bottom: 16px;
                    }}
                    table, th, td {{ 
                        border: 1px solid #dfe2e5; 
                    }}
                    th, td {{ 
                        padding: 6px 13px; 
                    }}
                    img {{ 
                        max-width: 100%; 
                    }}
                    .toolbar {{
                        background: #f1f1f1;
                        padding: 8px;
                        display: flex;
                        justify-content: space-between;
                        align-items: center;
                        height: 40px;
                        box-sizing: border-box;
                    }}
                    .btn {{
                        padding: 6px 12px;
                        background: #0366d6;
                        color: white;
                        border: none;
                        border-radius: 3px;
                        cursor: pointer;
                    }}
                    .btn:hover {{
                        background: #0246a2;
                    }}
                    h1, h2, h3, h4, h5, h6 {{
                        margin-top: 24px;
                        margin-bottom: 16px;
                        font-weight: 600;
                        line-height: 1.25;
                    }}
                    h1 {{
                        padding-bottom: 0.3em;
                        font-size: 2em;
                        border-bottom: 1px solid #eaecef;
                    }}
                    h2 {{
                        padding-bottom: 0.3em;
                        font-size: 1.5em;
                        border-bottom: 1px solid #eaecef;
                    }}
                    a {{
                        color: #0366d6;
                        text-decoration: none;
                    }}
                    a:hover {{
                        text-decoration: underline;
                    }}
                    ul, ol {{
                        padding-left: 2em;
                    }}
                    li+li {{
                        margin-top: 0.25em;
                    }}
                    .status {{
                        color: #666;
                        margin-right: 10px;
                    }}
                </style>
                <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
            </head>
            <body>
                <div class="toolbar">
                    <div>
                        <b>Editing:</b> {os.path.basename(self.server.markdown_file)}
                    </div>
                    <div>
                        <span class="status" id="status"></span>
                        <button class="btn" onclick="saveChanges()">Save Changes</button>
                    </div>
                </div>
                <div class="container">
                    <div class="editor">
                        <textarea id="editor" oninput="updatePreview()">{content}</textarea>
                    </div>
                    <div class="preview" id="preview"></div>
                </div>
                
                <script>
                    // Initialize marked options
                    marked.setOptions({{
                        highlight: function(code, lang) {{
                            return code;
                        }},
                        breaks: true,
                        gfm: true,
                        tables: true
                    }});
                    
                    // Initialize preview
                    function updatePreview() {{
                        const text = document.getElementById('editor').value;
                        const preview = document.getElementById('preview');
                        preview.innerHTML = marked.parse(text);
                    }}
                    
                    // Save changes
                    function saveChanges() {{
                        const text = document.getElementById('editor').value;
                        const statusEl = document.getElementById('status');
                        statusEl.textContent = 'Saving...';
                        
                        fetch('/save', {{
                            method: 'POST',
                            headers: {{
                                'Content-Type': 'application/x-www-form-urlencoded',
                            }},
                            body: 'content=' + encodeURIComponent(text)
                        }})
                        .then(response => response.json())
                        .then(data => {{
                            if (data.success) {{
                                statusEl.textContent = 'Saved successfully!';
                                setTimeout(() => {{ statusEl.textContent = ''; }}, 3000);
                            }} else {{
                                statusEl.textContent = 'Error: ' + data.error;
                            }}
                        }})
                        .catch(error => {{
                            statusEl.textContent = 'Error: ' + error;
                        }});
                    }}
                    
                    // Initialize
                    updatePreview();
                    
                    // Keyboard shortcuts
                    document.getElementById('editor').addEventListener('keydown', function(e) {{
                        // Ctrl+S / Cmd+S to save
                        if ((e.ctrlKey || e.metaKey) && e.key === 's') {{
                            e.preventDefault();
                            saveChanges();
                        }}
                    }});
                </script>
            </body>
            </html>
            """
            
            self.wfile.write(html.encode())
            
        elif self.path.startswith('/img/'):
            # Handle image requests - allows loading local images in the preview
            try:
                # Decode the URL-encoded path
                img_path = urllib.parse.unquote(self.path[5:])
                
                # Try to resolve the image relative to the markdown file
                md_dir = os.path.dirname(os.path.abspath(self.server.markdown_file))
                full_img_path = os.path.join(md_dir, img_path)
                
                if os.path.exists(full_img_path) and os.path.isfile(full_img_path):
                    # Determine content type based on extension
                    content_type = "image/jpeg"  # Default
                    if img_path.lower().endswith('.png'):
                        content_type = "image/png"
                    elif img_path.lower().endswith('.gif'):
                        content_type = "image/gif"
                    elif img_path.lower().endswith('.svg'):
                        content_type = "image/svg+xml"
                        
                    # Send the image
                    self.send_response(200)
                    self.send_header('Content-type', content_type)
                    self.end_headers()
                    
                    with open(full_img_path, 'rb') as f:
                        self.wfile.write(f.read())
                else:
                    # Image not found
                    self.send_response(404)
                    self.end_headers()
                    self.wfile.write(b"Image not found")
            except Exception as e:
                # Error handling
                self.send_response(500)
                self.end_headers()
                self.wfile.write(f"Error: {str(e)}".encode())
        else:
            # Path not found
            self.send_response(404)
            self.end_headers()
    
    def do_POST(self):
        """Handle POST requests."""
        if self.path == '/save':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length).decode('utf-8')
            parsed_data = urllib.parse.parse_qs(post_data)
            
            # Get the content and write to file
            if 'content' in parsed_data:
                content = parsed_data['content'][0]
                
                try:
                    with open(self.server.markdown_file, 'w', encoding='utf-8') as f:
                        f.write(content)
                        
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    
                    self.wfile.write(json.dumps({
                        'success': True,
                        'message': 'Changes saved successfully'
                    }).encode())
                    
                except Exception as e:
                    self.send_response(500)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    
                    self.wfile.write(json.dumps({
                        'success': False,
                        'error': str(e)
                    }).encode())
            else:
                self.send_response(400)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                
                self.wfile.write(json.dumps({
                    'success': False,
                    'error': 'No content provided'
                }).encode())
        else:
            self.send_response(404)
            self.end_headers()

def start_live_preview(file_path: str, port: int = 8000) -> Dict[str, Any]:
    """
    Start a live preview server for a Markdown document.
    
    Args:
        file_path: Path to the Markdown file
        port: Server port
        
    Returns:
        Server information including a 'open_browser' flag to tell frontend to open a browser
    """
    try:
        if not os.path.exists(file_path):
            return {
                "success": False,
                "error": f"File not found: {file_path}"
            }
        
        # Get absolute path
        abs_path = os.path.abspath(file_path)
        
        # Create a custom HTTP server with file path
        class LivePreviewServer(HTTPServer):
            def __init__(self, server_address, RequestHandlerClass, markdown_file):
                self.markdown_file = markdown_file
                super().__init__(server_address, RequestHandlerClass)
        
        # Try to find an available port
        server = None
        actual_port = port
        
        # Try up to 10 ports if the requested one is in use
        for port_offset in range(10):
            try_port = port + port_offset
            try:
                # Bind to all interfaces (0.0.0.0) to allow external connections
                # This is needed for Docker container access
                server = LivePreviewServer(('0.0.0.0', try_port), LivePreviewHandler, abs_path)
                actual_port = try_port
                break
            except OSError:
                # Port already in use, try the next one
                pass
        
        if not server:
            return {
                "success": False,
                "error": "Could not find an available port"
            }
        
        # Start server in a separate thread
        thread = threading.Thread(target=server.serve_forever)
        thread.daemon = True
        thread.start()
        
        # Determine if we're in a Docker container
        in_container = os.path.exists('/.dockerenv') or os.path.exists('/run/.containerenv')
        
        # Generate the URL - use host.docker.internal for Mac/Windows Docker to access host
        host_name = "localhost"
        server_url = f'http://{host_name}:{actual_port}'
        
        # Try to open browser directly if not in container (fallback approach)
        if not in_container:
            try:
                webbrowser.open(server_url)
                logger.info(f"Opened browser to {server_url}")
            except Exception as browser_error:
                logger.error(f"Failed to open browser: {str(browser_error)}")
        else:
            logger.info(f"Running in container - access the server at {server_url} from host machine")
        
        # Send WebSocket notification if possible
        try:
            # Try to import the WebSocket manager - this will only work if running within Denker backend
            from mcp_local.core.websocket_manager import get_websocket_manager
            from fastapi import WebSocket
            import asyncio
            import json
            
            # Get the WebSocket manager singleton
            try:
                # Use the singleton getter function to access the manager
                websocket_manager = get_websocket_manager()
                
                # If we found a WebSocket manager, send notification to open browser
                if websocket_manager:
                    # Create browser action data
                    browser_data = {
                        "url": server_url,
                        "title": f"Markdown Preview: {os.path.basename(file_path)}",
                        "action": "preview"
                    }
                    
                    # Use the consolidated update format - will be picked up by the frontend
                    async def send_notification():
                        try:
                            # Send to all active connections since we don't know which client requested this
                            # In real-world usage, the query_id would be passed from the tool invocation
                            for query_id in websocket_manager.active_connections:
                                await websocket_manager.send_consolidated_update(
                                    query_id=query_id,
                                    update_type="browser_action",
                                    message="Opening browser for markdown preview",
                                    data=browser_data
                                )
                            logger.info("Sent WebSocket notification to open browser")
                        except Exception as ws_error:
                            logger.error(f"Error sending WebSocket notification: {str(ws_error)}")
                    
                    # Schedule the coroutine to run
                    asyncio.create_task(send_notification())
                    logger.info("Scheduled WebSocket notification")
            except Exception as e:
                logger.warning(f"Could not access WebSocket manager: {str(e)}")
        except ImportError:
            logger.warning("WebSocket manager not available - browser won't open automatically")
        
        return {
            "success": True,
            "server_url": server_url,
            "file_path": file_path,
            "message": f"Live preview server running at {server_url}",
            "in_container": in_container,
            "open_browser": True,  # Signal to frontend that a browser should be opened
            "help": "If running in a container, ensure port forwarding is set up correctly to access this URL from the host"
        }
        
    except Exception as e:
        logger.error(f"Error starting live preview: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        } 