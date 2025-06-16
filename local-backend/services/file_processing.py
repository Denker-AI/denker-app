import os
import logging
import io
from typing import Optional, List

logger = logging.getLogger(__name__)

def extract_content(file_path: str) -> Optional[str]:
    """
    Extract content from a file based on its extension.
    Returns the extracted text content or None if extraction fails.
    
    Supported formats:
    - PDF (.pdf)
    - Text (.txt)
    - Word (.docx, .doc)
    - Excel (.xlsx, .xls)
    - HTML (.html, .htm)
    - Markdown (.md, .markdown)
    - CSV (.csv)
    - Images (.jpg, .jpeg, .png, .gif, .bmp)
    """
    try:
        # Lazy import heavy dependencies only when actually needed
        from langchain.text_splitter import RecursiveCharacterTextSplitter
        from langchain.docstore.document import Document
        from langchain_community.document_loaders import (
            PyPDFLoader,
            TextLoader,
            CSVLoader,
            UnstructuredWordDocumentLoader,
            UnstructuredExcelLoader,
            BSHTMLLoader,
            UnstructuredMarkdownLoader
        )
        
        file_ext = os.path.splitext(file_path)[1].lower()
        
        # Handle image files with OCR
        if file_ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp']:
            return extract_image_content(file_path)
        
        # Choose loader based on file extension
        if file_ext == '.pdf':
            loader = PyPDFLoader(file_path)
        elif file_ext == '.txt':
            loader = TextLoader(file_path)
        elif file_ext in ['.docx', '.doc']:
            try:
                loader = UnstructuredWordDocumentLoader(file_path)
            except Exception as word_error:
                logger.warning(f"Error with Word loader for {file_ext}: {word_error}. Falling back to TextLoader.")
                loader = TextLoader(file_path, encoding='utf-8', autodetect_encoding=True)
        elif file_ext == '.csv':
            loader = CSVLoader(file_path)
        elif file_ext in ['.xlsx', '.xls']:
            try:
                loader = UnstructuredExcelLoader(file_path)
            except Exception as excel_error:
                logger.warning(f"Error with Excel loader for {file_ext}: {excel_error}. Falling back to TextLoader.")
                loader = TextLoader(file_path, encoding='utf-8', autodetect_encoding=True)
        elif file_ext in ['.html', '.htm']:
            try:
                loader = BSHTMLLoader(file_path)
            except Exception as html_error:
                logger.warning(f"Error with HTML loader for {file_ext}: {html_error}. Falling back to TextLoader.")
                loader = TextLoader(file_path, encoding='utf-8', autodetect_encoding=True)
        elif file_ext in ['.md', '.markdown']:
            try:
                loader = UnstructuredMarkdownLoader(file_path)
            except Exception as md_error:
                logger.warning(f"Error with Markdown loader for {file_ext}: {md_error}. Falling back to TextLoader.")
                loader = TextLoader(file_path, encoding='utf-8', autodetect_encoding=True)
        else:
            # Try text loader as fallback
            logger.warning(f"Unknown file extension '{file_ext}', trying text loader")
            loader = TextLoader(file_path, encoding='utf-8', autodetect_encoding=True)
        
        # Load documents
        documents = loader.load()
        if not documents:
            logger.warning(f"No content extracted from {file_path}")
            return None
            
        # Combine all document content
        content = "\n\n".join(doc.page_content for doc in documents)
        logger.info(f"Successfully extracted content from {file_path}")
        
        return content
        
    except Exception as e:
        logger.error(f"Error extracting content from {file_path}: {str(e)}")
        return None

def extract_image_content(file_path: str) -> Optional[str]:
    """
    Extract text content from images using OCR with pytesseract.
    For more advanced processing, also tries unstructured's partition_image.
    Returns the extracted text content or None if extraction fails.
    """
    try:
        # Lazy import heavy image processing dependencies only when actually needed
        from PIL import Image
        import pytesseract
        from unstructured.partition.image import partition_image
        
        # Try using unstructured's image partitioning first
        try:
            elements = partition_image(file_path)
            if elements:
                unstructured_text = "\n".join([str(element) for element in elements])
                if unstructured_text.strip():
                    logger.info(f"Successfully extracted text from image using unstructured: {file_path}")
                    return unstructured_text
        except Exception as unstructured_error:
            logger.warning(f"Error using unstructured for image {file_path}: {unstructured_error}. Trying pytesseract.")
        
        # Fall back to pytesseract
        image = Image.open(file_path)
        text = pytesseract.image_to_string(image)
        
        if not text or not text.strip():
            logger.warning(f"No text detected in image {file_path}")
            return f"[Image file with no detectable text: {os.path.basename(file_path)}]"
        
        logger.info(f"Successfully extracted text from image using pytesseract: {file_path}")
        return text
    except Exception as e:
        logger.error(f"Error extracting text from image {file_path}: {str(e)}")
        return f"[Image file that could not be processed: {os.path.basename(file_path)}]"

def chunk_text(text: str, chunk_size: int = 1000, chunk_overlap: int = 200) -> List:
    """
    Splits a long text into smaller chunks based on a specified size and overlap.
    
    Args:
        text: The text content to be chunked.
        chunk_size: The maximum size of each chunk (in characters).
        chunk_overlap: The number of characters to overlap between consecutive chunks.
        
    Returns:
        A list of Langchain Document objects, each containing chunk text and metadata (like start_index).
    """
    try:
        # Lazy import only when actually needed
        from langchain.text_splitter import RecursiveCharacterTextSplitter
        from langchain.docstore.document import Document
        
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
            add_start_index=True,
        )
        # create_documents returns a list of Document objects, each with metadata
        documents = text_splitter.create_documents([text])
        logger.info(f"Successfully split text into {len(documents)} chunks.")
        return documents
    except Exception as e:
        logger.error(f"Error chunking text: {str(e)}")
        # If chunking fails, return the original text as a single chunk to avoid data loss
        # Lazy import for fallback as well
        from langchain.docstore.document import Document
        return [Document(page_content=text, metadata={"start_index": 0})] 