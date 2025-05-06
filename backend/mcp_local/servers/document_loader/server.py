#!/usr/bin/env python3
"""
Document Loader MCP Server

A FastMCP server that extracts text content from various document formats.
This server acts as a bridge between the filesystem and Qdrant servers,
converting document files into plain text that can be indexed and searched.

Supported formats:
- PDF
- DOCX/DOC
- CSV
- TXT/MD
- Images (JPG, PNG) via OCR
"""

from fastmcp import FastMCP
from typing import Dict, Any, Optional
import os
import mimetypes
import traceback
import logging
import tempfile

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("document-loader")

# Initialize FastMCP server
app = FastMCP(name="document-loader", version="1.0.0")

# Import extractors - using try/except to handle potential missing dependencies
try:
    import PyPDF2
    def extract_pdf(file_path: str) -> str:
        try:
            text = ""
            with open(file_path, "rb") as file:
                reader = PyPDF2.PdfReader(file)
                for page_num in range(len(reader.pages)):
                    page_text = reader.pages[page_num].extract_text() or ""
                    text += page_text + "\n\n"
            return text
        except Exception as e:
            logger.error(f"Error extracting PDF content: {str(e)}")
            return f"[Error extracting PDF content: {str(e)}]"
except ImportError:
    logger.warning("PyPDF2 not installed. PDF extraction will not be available.")
    def extract_pdf(file_path: str) -> str:
        return "[PDF extraction not available: PyPDF2 not installed]"

try:
    import docx
    def extract_docx(file_path: str) -> str:
        try:
            doc = docx.Document(file_path)
            text = "\n".join([paragraph.text for paragraph in doc.paragraphs])
            return text
        except Exception as e:
            logger.error(f"Error extracting DOCX content: {str(e)}")
            return f"[Error extracting DOCX content: {str(e)}]"
except ImportError:
    logger.warning("python-docx not installed. DOCX extraction will not be available.")
    def extract_docx(file_path: str) -> str:
        return "[DOCX extraction not available: python-docx not installed]"

try:
    import pandas as pd
    def extract_csv(file_path: str) -> str:
        try:
            df = pd.read_csv(file_path)
            return df.to_string()
        except Exception as e:
            logger.error(f"Error extracting CSV content: {str(e)}")
            return f"[Error extracting CSV content: {str(e)}]"
except ImportError:
    logger.warning("pandas not installed. CSV extraction will not be available.")
    def extract_csv(file_path: str) -> str:
        return "[CSV extraction not available: pandas not installed]"

try:
    from PIL import Image
    import pytesseract
    def extract_image(file_path: str) -> str:
        try:
            image = Image.open(file_path)
            text = pytesseract.image_to_string(image)
            if not text or not text.strip():
                return f"[Image file with no detectable text: {os.path.basename(file_path)}]"
            return text
        except Exception as e:
            logger.error(f"Error extracting image content: {str(e)}")
            return f"[Error extracting image content: {str(e)}]"
except ImportError:
    logger.warning("PIL or pytesseract not installed. Image extraction will not be available.")
    def extract_image(file_path: str) -> str:
        return "[Image extraction not available: PIL or pytesseract not installed]"

def extract_txt(file_path: str) -> str:
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as file:
            return file.read()
    except Exception as e:
        logger.error(f"Error reading text file: {str(e)}")
        return f"[Error reading text file: {str(e)}]"

# Factory to get the right extractor
def get_extractor(file_path: str) -> Optional[callable]:
    ext = os.path.splitext(file_path)[1].lower()
    
    extractors = {
        ".pdf": extract_pdf,
        ".docx": extract_docx, 
        ".doc": extract_docx,
        ".csv": extract_csv,
        ".txt": extract_txt,
        ".md": extract_txt,
        ".jpg": extract_image,
        ".jpeg": extract_image,
        ".png": extract_image,
        ".html": extract_txt,
        ".htm": extract_txt,
        ".json": extract_txt,
        ".xml": extract_txt,
    }
    
    return extractors.get(ext)

@app.tool()
def load_document(file_path: str) -> Dict[str, Any]:
    """
    Extract text content from a document file.
    Supports PDF, DOCX, CSV, TXT, MD, and image files (JPG, JPEG, PNG).
    
    Args:
        file_path: Path to the document file
        
    Returns:
        Dictionary containing:
        - success: Whether extraction was successful
        - content: Extracted text content
        - metadata: File metadata (name, type, size)
    """
    try:
        # Check if file exists
        if not os.path.exists(file_path):
            return {
                "success": False,
                "error": f"File not found: {file_path}"
            }
        
        # Get file metadata
        file_name = os.path.basename(file_path)
        file_size = os.path.getsize(file_path)
        mime_type, _ = mimetypes.guess_type(file_path)
        
        # Get appropriate extractor
        extractor = get_extractor(file_path)
        if not extractor:
            return {
                "success": False,
                "error": f"Unsupported file type: {os.path.splitext(file_path)[1]}",
                "metadata": {
                    "file_name": file_name,
                    "file_path": file_path,
                    "file_size": file_size,
                    "mime_type": mime_type
                }
            }
        
        # Extract content
        content = extractor(file_path)
        
        return {
            "success": True,
            "content": content,
            "metadata": {
                "file_name": file_name,
                "file_path": file_path,
                "file_size": file_size,
                "mime_type": mime_type,
                "content_length": len(content) if content else 0
            }
        }
        
    except Exception as e:
        logger.error(f"Error loading document: {str(e)}")
        logger.error(traceback.format_exc())
        
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }

if __name__ == "__main__":
    app.run() 