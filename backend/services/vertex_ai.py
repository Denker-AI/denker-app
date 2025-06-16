"""
Vertex AI service for Denker using Gemini models
"""
import logging
import sys
from typing import List, Dict, Any, Optional
from google.cloud import aiplatform
from vertexai.generative_models import GenerativeModel, GenerationConfig, Part
import vertexai
from config.settings import settings
import base64
import time
import traceback
import asyncio
from contextlib import asynccontextmanager

# Configure logging with reduced overhead
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)  # Changed from DEBUG to INFO
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.INFO)  # Changed from DEBUG to INFO
formatter = logging.Formatter('%(levelname)s - %(message)s')  # Simplified format
handler.setFormatter(formatter)
logger.addHandler(handler)

class VertexAIService:
    """Service for interacting with Vertex AI Gemini models"""
    
    def __init__(self):
        """Initialize the Vertex AI service"""
        self.project = settings.VERTEX_AI_PROJECT
        self.location = "europe-west4"  # Override to use europe-west4 specifically for Vertex AI
        self.initialized = False
        self.model = None
        self.model_name = "gemini-2.0-flash-001"
        self._lock = asyncio.Lock()
        self._active_requests = set()
        
    def initialize(self):
        """Initialize the Vertex AI service"""
        if settings.VERTEX_AI_ENABLED:
            try:
                # Initialize Vertex AI
                vertexai.init(
                    project=self.project,
                    location=self.location,
                )
                
                # Initialize model
                self.model = GenerativeModel(self.model_name)
                self.initialized = True
                logger.info(f"✅ Vertex AI initialized with project {self.project}")
            except Exception as e:
                logger.error(f"❌ Failed to initialize Vertex AI: {str(e)}")

    async def cleanup(self):
        """Cleanup resources and wait for active requests to complete"""
        try:
            # Wait for all active requests to complete
            if self._active_requests:
                logger.info(f"Waiting for {len(self._active_requests)} active requests to complete...")
                await asyncio.gather(*self._active_requests, return_exceptions=True)
            
            # Clear the set of active requests
            self._active_requests.clear()
            
            # Reset the model
            self.model = None
            self.initialized = False
            
            logger.info("✅ VertexAI service cleanup completed")
        except Exception as e:
            logger.error(f"❌ Error during cleanup: {str(e)}")

    @asynccontextmanager
    async def _track_request(self):
        """Track active requests for cleanup"""
        request_task = asyncio.current_task()
        try:
            self._active_requests.add(request_task)
            yield
        finally:
            self._active_requests.discard(request_task)

    async def reinitialize(self):
        """Reinitialize the service if needed"""
        async with self._lock:
            if not self.initialized:
                try:
                    # Initialize Vertex AI
                    vertexai.init(
                        project=self.project,
                        location=self.location,  # Uses europe-west4 from self.location
                    )
                    
                    # Initialize model
                    self.model = GenerativeModel(self.model_name)
                    self.initialized = True
                    logger.info(f"✅ Vertex AI reinitialized with project {self.project} in location {self.location}")
                except Exception as e:
                    logger.error(f"❌ Failed to reinitialize Vertex AI: {str(e)}")
                    raise

    async def get_text_embedding(self, text: str) -> Optional[List[float]]:
        """Get text embedding from Vertex AI"""
        if not self.initialized:
            await self.reinitialize()
            
        async with self._track_request():
            try:
                # Get the text embedding model
                model_name = "textembedding-gecko@latest"
                
                # Create the model
                model = aiplatform.TextEmbeddingModel.from_pretrained(model_name)
                
                # Get embeddings
                embeddings = model.get_embeddings([text])
                
                if embeddings and len(embeddings) > 0 and embeddings[0].values:
                    return embeddings[0].values
                else:
                    logger.error("No embeddings returned from Vertex AI")
                    return None
            except Exception as e:
                logger.error(f"Error getting text embedding: {e}")
                return None
    
    async def process_multimodal_input(
        self,
        text: str,
        image_base64: Optional[str] = None,
        image_mime_type: Optional[str] = None,
        max_tokens: int = 1024,
        temperature: float = 0.4
    ) -> Optional[str]:
        """
        Process multimodal input (text and image) using Gemini model
        """
        if not self.initialized:
            await self.reinitialize()

        async with self._track_request():
            try:
                start_time = time.time()
                
                # Prepare content parts
                content_parts = []
                image_data = None
                
                # Add image if provided (add it first for better performance)
                if image_base64:
                    try:
                        # Remove data URL prefix if present
                        if ',' in image_base64:
                            image_base64 = image_base64.split(',')[1]
                        
                        # Decode image data
                        image_data = base64.b64decode(image_base64)
                        
                        # Create image part
                        image_part = Part.from_data(
                            image_data,
                            mime_type=image_mime_type or "image/png"
                        )
                        content_parts.append(image_part)
                    except Exception as img_error:
                        logger.error(f"❌ Error processing image: {str(img_error)}")
                        # Continue without image if image processing fails
                    finally:
                        # Clear image data from memory
                        image_data = None
                
                # Add text part
                content_parts.append(text)
                
                # Generate content with configuration
                model_start_time = time.time()
                
                response = self.model.generate_content(
                    content_parts,
                    generation_config=GenerationConfig(
                        max_output_tokens=max_tokens,
                        temperature=temperature,
                        top_p=0.8,
                        top_k=40
                    )
                )
                
                model_processing_time = time.time() - model_start_time
                total_time = time.time() - start_time
                
                if not response or not response.text:
                    logger.warning("⚠️ Empty response from Gemini")
                    return None
                    
                return response.text
                
            except Exception as e:
                logger.error(f"❌ Error in multimodal processing: {str(e)}")
                return None
            finally:
                # Clear content parts to free memory
                content_parts.clear()

    async def generate_text(
        self,
        prompt: str,
        max_tokens: int = 1024,
        temperature: float = 0.4,
        model: Optional[str] = None
    ) -> Optional[str]:
        """
        Generate text using Gemini model
        
        Args:
            prompt (str): The input prompt for text generation
            max_tokens (int, optional): Maximum number of tokens to generate. Defaults to 1024.
            temperature (float, optional): Sampling temperature. Defaults to 0.4.
            model (str, optional): The model name to use (e.g., "gemini-pro", "gemini-2.0-pro"). Defaults to None.
            
        Returns:
            Optional[str]: Generated text or None if generation fails
        """
        if not self.initialized:
            await self.reinitialize()

        async with self._track_request():
            try:
                start_time = time.time()
                
                # Use specified model or default
                model_name = model or self.model_name
                
                # Get the model instance with the specified name if it's different from current
                current_model = self.model
                if model_name != self.model_name:
                    current_model = GenerativeModel(model_name)
                
                # Generate content with configuration
                response = current_model.generate_content(
                    prompt,
                    generation_config=GenerationConfig(
                        max_output_tokens=max_tokens,
                        temperature=temperature,
                        top_p=0.8,
                        top_k=40
                    )
                )
                
                total_time = time.time() - start_time
                logger.debug(f"Text generation completed in {total_time:.2f}s using model {model_name}")
                
                if not response or not response.text:
                    logger.warning("⚠️ Empty response from Gemini")
                    return None
                    
                return response.text.strip() if response.text else None
                
            except Exception as e:
                logger.error(f"❌ Error in text generation: {str(e)}")
                logger.error(traceback.format_exc())
                return None

    async def chat(
        self,
        message: str,
        system: Optional[str] = None,
        max_tokens: int = 1024,
        temperature: float = 0.4,
        model: Optional[str] = None
    ) -> Optional[str]:
        """
        Chat method for simple conversations using Gemini model
        
        Args:
            message (str): The chat message
            system (str, optional): System context message
            max_tokens (int, optional): Maximum number of tokens to generate. Defaults to 1024.
            temperature (float, optional): Sampling temperature. Defaults to 0.4.
            model (str, optional): The model name to use (e.g., "gemini-2.0-pro"). Defaults to gemini-2.0-flash-001.
            
        Returns:
            Optional[str]: Generated response or None if generation fails
        """
        # Default system message about Denker if none provided
        default_system = """You are Denker, an AI assistant that helps users with comprehensive content and research tasks.
        Your core capabilities include:
        - Research: Finding and synthesizing information from multiple sources
        - Structure: Creating clear organizational frameworks and outlines
        - Writing: Transforming outlines into polished content
        - Proofreading: Reviewing for grammar, spelling, and clarity
        - Fact Checking: Verifying accuracy and consistency of information
        - Formatting: Ensuring professional presentation and layout
        - Style Enforcement: Maintaining consistent tone and style

        You work with users through a collaborative process, breaking down complex tasks into manageable steps.
        Always be helpful, professional, and direct in your responses.
        If you don't know something, say so honestly.
        Keep responses concise but informative."""

        # Combine system message (if any) with default context
        system_message = system if system else default_system
        
        # Construct the full prompt
        full_prompt = f"{system_message}\n\nUser: {message}\nAssistant:"
        
        return await self.generate_text(
            prompt=full_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            model=model
        )

    async def __aenter__(self):
        """Async context manager entry"""
        if not self.initialized:
            await self.reinitialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.cleanup()

# Create a singleton instance
vertex_ai_service = VertexAIService() 