"""
Background preloader for heavy dependencies
Loads commonly used heavy imports in the background after startup
"""
import logging
import asyncio
from typing import Optional
import threading

logger = logging.getLogger(__name__)

class BackgroundPreloader:
    def __init__(self):
        self._preload_started = False
        self._preload_completed = False
        self._preload_lock = threading.Lock()
        
    def start_background_preload(self, delay_seconds: int = 3):
        """Start background preloading after a delay"""
        if self._preload_started:
            return
            
        with self._preload_lock:
            if self._preload_started:
                return
            self._preload_started = True
        
        # Start preloading in a separate thread to avoid blocking
        threading.Thread(
            target=self._preload_worker, 
            args=(delay_seconds,),
            daemon=True
        ).start()
        logger.info(f"Background preloading scheduled to start in {delay_seconds} seconds")
        
    def _preload_worker(self, delay_seconds: int):
        """Worker thread that handles background preloading"""
        import time
        time.sleep(delay_seconds)
        
        logger.info("Starting background preloading of heavy dependencies...")
        
        # Preload common heavy imports
        self._preload_document_processing()
        self._preload_ml_models()
        self._preload_web_operations()
        self._preload_mcp_agent_features()
        
        self._preload_completed = True
        logger.info("Background preloading completed")
        
    def _preload_document_processing(self):
        """Preload document processing libraries"""
        try:
            logger.info("Preloading document processing libraries...")
            
            # CRITICAL: Preload matplotlib early to avoid 16-second delay on first file upload
            self._preload_matplotlib()
            
            # Preload unstructured modules used for file processing
            self._preload_unstructured()
            
            # Check if we're in PyInstaller mode
            import sys
            if getattr(sys, 'frozen', False):
                logger.info("PyInstaller mode - directly importing document libraries")
                # Import libraries directly since setup_heavy_imports might have issues
                try:
                    import pypdf
                    import docx
                    import pandas as pd
                    # Test basic functionality
                    _ = pd.DataFrame({"test": [1, 2, 3]})
                    logger.info("Document processing libraries imported successfully")
                except ImportError as e:
                    logger.warning(f"Some document libraries not available in PyInstaller: {e}")
            else:
                # Normal development mode - use absolute import
                try:
                    import main
                    main.setup_heavy_imports()
                except ImportError:
                    logger.warning("Could not import main module for setup_heavy_imports")
            
            logger.info("Document processing libraries preloaded successfully")
        except Exception as e:
            logger.warning(f"Failed to preload document processing libraries: {e}")
            
    def _preload_matplotlib(self):
        """Preload matplotlib to prevent 16-second font cache delay on first file upload"""
        try:
            logger.info("Preloading matplotlib (used by unstructured for document processing)...")
            import time
            start_time = time.time()
            
            # Import matplotlib - this will trigger font cache build if needed
            # The environment variables we set in main.py will prevent the rebuild
            import matplotlib
            import matplotlib.pyplot as plt
            
            # Force matplotlib to initialize fully
            matplotlib.use('Agg')  # Non-interactive backend
            plt.ioff()  # Turn off interactive mode
            
            # Trigger any remaining initialization by creating a small plot
            fig, ax = plt.subplots(figsize=(1, 1))
            ax.plot([1, 2], [1, 2])
            plt.close(fig)
            
            elapsed = time.time() - start_time
            logger.info(f"Matplotlib preloaded successfully in {elapsed:.2f} seconds")
            
        except Exception as e:
            logger.warning(f"Failed to preload matplotlib: {e}")
            
    def _preload_unstructured(self):
        """Preload unstructured modules used for file processing"""
        try:
            logger.info("Preloading unstructured modules for file processing...")
            import time
            start_time = time.time()
            
            # Import the specific unstructured modules we use
            from unstructured.partition.image import partition_image
            from unstructured.partition.auto import partition
            
            # Import langchain document loaders we use in file_processing.py
            from langchain_community.document_loaders import (
                PyPDFLoader,
                UnstructuredWordDocumentLoader,
                UnstructuredExcelLoader,
                UnstructuredMarkdownLoader
            )
            
            elapsed = time.time() - start_time
            logger.info(f"Unstructured modules preloaded successfully in {elapsed:.2f} seconds")
            
        except Exception as e:
            logger.warning(f"Failed to preload unstructured modules: {e}")
            
    def _preload_ml_models(self):
        """Preload ML models that are commonly used"""
        try:
            logger.info("Preloading commonly used ML models...")
            
            # Preload the sentence transformer model by accessing it
            try:
                from services.qdrant_service import direct_qdrant_service
                if direct_qdrant_service.client:
                    # This will trigger the lazy loading of the embedding model
                    _ = direct_qdrant_service.embedding_model
                    if direct_qdrant_service.embedding_model:
                        logger.info("SentenceTransformer model preloaded successfully")
                    else:
                        logger.warning("Failed to preload SentenceTransformer model")
                else:
                    logger.info("Qdrant service not available, skipping model preload")
            except ImportError:
                logger.info("Qdrant service module not available, skipping model preload")
                
        except Exception as e:
            logger.warning(f"Failed to preload ML models: {e}")
            
    def _preload_web_operations(self):
        """Preload web operations and fetching libraries"""
        try:
            logger.info("Preloading web operations libraries...")
            
            # Preload markdownify and web fetching dependencies
            import markdownify
            import requests
            import urllib.parse
            
            # Initialize connection pools (this is the heavy part for requests)
            session = requests.Session()
            # Make a small test request to initialize connection pools
            session.close()
            
            # Trigger markdownify initialization by doing a small conversion
            _ = markdownify.markdownify("<p>test</p>")
            
            logger.info("Web operations libraries preloaded successfully")
        except Exception as e:
            logger.warning(f"Failed to preload web operations libraries: {e}")
            
    def _preload_mcp_agent_features(self):
        """Preload MCP Agent system for power users"""
        try:
            logger.info("Preloading MCP Agent features...")
            
            # Check if we're in PyInstaller mode
            import sys
            if getattr(sys, 'frozen', False):
                logger.info("PyInstaller mode detected - using embedded MCP agent modules")
                
            # Import and initialize MCP Agent components
            try:
                from mcp_agent.app import MCPApp
                from mcp_agent.agents.agent import Agent
                logger.info("Core MCP agent classes imported successfully")
            except ImportError as e:
                logger.warning(f"Failed to import core MCP classes: {e}")
                return
            
            # Try to preload config system (heavy initialization)
            try:
                from mcp_agent.config import get_settings
                # This loads and validates the config which is expensive
                settings = get_settings()
                if settings and settings.mcp:
                    logger.info(f"MCP config preloaded for {len(settings.mcp.servers or {})} servers")
            except Exception as e:
                logger.warning(f"MCP config preload failed: {e}")
            
            # Preload common MCP client components
            try:
                from mcp_agent.mcp.mcp_connection_manager import MCPConnectionManager
                from mcp_agent.mcp.mcp_aggregator import MCPAggregator
                from mcp_agent.mcp.mcp_agent_client_session import MCPAgentClientSession
                logger.info("MCP client components preloaded")
            except Exception as e:
                logger.warning(f"MCP client preload failed: {e}")
            
            logger.info("MCP Agent features preloaded successfully")
        except Exception as e:
            logger.warning(f"Failed to preload MCP Agent features: {e}")
            
    @property
    def is_preload_completed(self) -> bool:
        """Check if background preloading is completed"""
        return self._preload_completed

# Global singleton instance
background_preloader = BackgroundPreloader() 