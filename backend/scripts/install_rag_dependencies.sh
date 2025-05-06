#!/bin/bash
# Install dependencies for RAG functionality

set -e  # Exit on error

echo "Installing RAG dependencies..."

# Install system dependencies for OCR if this is a Debian/Ubuntu system
if command -v apt-get &> /dev/null; then
  echo "Installing system dependencies for OCR..."
  apt-get update && apt-get install -y tesseract-ocr
fi

# Install Python packages
pip3 install --no-cache-dir \
  langchain \
  langchain-community \
  langchain-text-splitters \
  qdrant-client \
  unstructured \
  "unstructured[all-docs]" \
  "unstructured[image]" \
  "unstructured[pdf]" \
  pdfminer.six \
  python-docx \
  python-pptx \
  openpyxl \
  google-cloud-storage \
  pandas \
  # Additional dependencies for document processing
  pillow \
  beautifulsoup4 \
  lxml \
  tiktoken \
  pytesseract \
  # Image processing dependencies
  pdf2image \
  img2pdf

echo "Testing imports..."

# Test if imports work
python3 -c "
try:
    from langchain_community.document_loaders import PyPDFLoader, TextLoader, UnstructuredWordDocumentLoader, BSHTMLLoader, UnstructuredExcelLoader, UnstructuredMarkdownLoader
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    from qdrant_client import QdrantClient
    import pytesseract
    from PIL import Image
    from unstructured.partition.image import partition_image
    print('Imports successful!')
except ImportError as e:
    print(f'Import error: {e}')
    exit(1)
"

echo "All RAG dependencies installed successfully!" 