"""
Vertex AI wrapper for Anthropic models

This module provides a thin wrapper around the AnthropicAugmentedLLM class
to support using Anthropic models deployed on Google Cloud Vertex AI.
"""

import os
import json
import logging
from typing import Dict, Any, List, Optional, Callable, Union, Type
import anthropic
from pydantic import BaseModel
from google.oauth2 import service_account
from google.cloud import aiplatform

# Import AnthropicAugmentedLLM and dependencies
from mcp_agent.workflows.llm.augmented_llm import RequestParams, AugmentedLLM
from mcp_agent.workflows.llm.augmented_llm_anthropic import (
    AnthropicAugmentedLLM,
    MessageParam,
    Message
)

# Import logging utilities
from mcp_agent.logging.logger import get_logger

# Setup logger
logger = logging.getLogger(__name__)

class VertexAnthropicConfig(BaseModel):
    """Configuration for Vertex Anthropic LLM"""
    project_id: str
    location: str = "europe-west1"
    api_endpoint: Optional[str] = None
    model_endpoint: Optional[str] = None
    api_key: Optional[str] = None
    default_model: str = "claude-3-7-sonnet@20250219"
    service_account_key_path: Optional[str] = None

class VertexAnthropicAugmentedLLM(AnthropicAugmentedLLM):
    """
    Wrapper for Anthropic models deployed on Vertex AI.
    
    This class extends the standard AnthropicAugmentedLLM but configures
    the client to use Anthropic models deployed on Vertex AI.
    """
    
    def __init__(
        self,
        tools: Optional[List[Dict[str, Any]]] = None,
        stream_callback: Optional[Callable] = None,
        agent: Optional[Any] = None,
        name: Optional[str] = None,
        instruction: Optional[str] = None,
        server_names: Optional[List[str]] = None,
        **kwargs
    ):
        """
        Initialize the VertexAnthropicAugmentedLLM with Vertex AI configuration.
        
        Args:
            tools: List of tools available to the LLM
            stream_callback: Optional callback for streaming updates
            agent: Optional agent instance 
            name: Optional name for the LLM (from agent)
            instruction: Optional instruction for the LLM (from agent)
            server_names: Optional list of server names
            **kwargs: Additional keyword arguments
        """
        # Initialize the base AnthropicAugmentedLLM
        super().__init__(
            agent=agent, 
            name=name, 
            instruction=instruction, 
            server_names=server_names,
            **kwargs
        )
        
        # Set provider name to indicate Vertex
        self.provider = "Vertex-Anthropic"
        
        # Initialize logger with name
        self.logger = get_logger(f"{__name__}.{self.name}" if self.name else __name__)
        
        # Save tools and callback
        self.tools = tools or []
        self.stream_callback = stream_callback
        
        # Get Vertex configuration from context
        self.vertex_config = self._get_vertex_config()
        
        # Initialize Vertex AI SDK with service account credentials
        self._initialize_vertex_ai()
        
        # Log configuration
        self.logger.info(f"Initialized VertexAnthropicAugmentedLLM with project: {self.vertex_config.project_id}, model: {self.vertex_config.default_model}")
    
    def _get_vertex_config(self) -> VertexAnthropicConfig:
        """
        Get Vertex AI configuration from context or environment.
        
        Returns:
            VertexAnthropicConfig: Configuration for Vertex AI
        """
        # Try to get from context
        if hasattr(self.context, "config") and hasattr(self.context.config, "vertex"):
            vertex_config = self.context.config.vertex
            # Extract relevant fields if they exist
            config_dict = {
                "project_id": getattr(vertex_config, "project_id", None),
                "location": getattr(vertex_config, "location", "europe-west1"),
                "api_endpoint": getattr(vertex_config, "api_endpoint", None),
                "model_endpoint": getattr(vertex_config, "model_endpoint", None),
                "api_key": getattr(vertex_config, "api_key", None),
                "default_model": getattr(vertex_config, "anthropic_model", "claude-3-7-sonnet@20250219"),
                "service_account_key_path": getattr(vertex_config, "service_account_key_path", None)
            }
            # Filter out None values
            config_dict = {k: v for k, v in config_dict.items() if v is not None}
            return VertexAnthropicConfig(**config_dict)
        
        # Fallback to environment variables
        return VertexAnthropicConfig(
            project_id=os.environ.get("VERTEX_PROJECT_ID", ""),
            location=os.environ.get("VERTEX_LOCATION", "europe-west1"),
            api_endpoint=os.environ.get("VERTEX_API_ENDPOINT", None),
            model_endpoint=os.environ.get("VERTEX_MODEL_ENDPOINT", None),
            api_key=os.environ.get("VERTEX_API_KEY", None),
            default_model=os.environ.get("VERTEX_ANTHROPIC_MODEL", "claude-3-7-sonnet@20250219"),
            service_account_key_path=os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", None)
        )
    
    def _initialize_vertex_ai(self):
        """
        Initialize the Vertex AI SDK with service account credentials.
        
        This sets up the Vertex AI SDK to use either:
        1. Service account credentials from a key file
        2. Application Default Credentials
        3. Explicit project/location configuration
        """
        config = self.vertex_config
        
        try:
            # Check if we have a service account key file
            if config.service_account_key_path and os.path.exists(config.service_account_key_path):
                self.logger.info(f"Initializing Vertex AI with service account credentials from: {config.service_account_key_path}")
                
                # Create credentials from service account key file
                credentials = service_account.Credentials.from_service_account_file(
                    config.service_account_key_path
                )
                
                # Initialize the Vertex AI SDK with these credentials
                aiplatform.init(
                    project=config.project_id,
                    location=config.location,
                    credentials=credentials
                )
                
                # Store credentials for later use
                self.credentials = credentials
                
            else:
                # Fall back to application default credentials
                self.logger.info(f"Initializing Vertex AI with application default credentials")
                
                # Initialize the Vertex AI SDK with project and location
                aiplatform.init(
                    project=config.project_id,
                    location=config.location
                )
                
                # Set credentials to None, will use application default
                self.credentials = None
                
            self.logger.info(f"Successfully initialized Vertex AI SDK for project: {config.project_id}, location: {config.location}")
            
        except Exception as e:
            self.logger.error(f"Error initializing Vertex AI: {str(e)}")
            self.logger.warning("Will attempt to continue without Vertex AI initialization")
    
    async def generate(
        self,
        message,
        request_params: RequestParams | None = None,
    ):
        """
        Process a query using an Anthropic LLM via Vertex AI.
        
        This overrides the base generate method to use Vertex AI endpoints
        instead of direct Anthropic API.
        
        Args:
            message: User message (string or message dict or list of message dicts)
            request_params: Optional request parameters
            
        Returns:
            List of Message objects
        """
        # Configure the Anthropic client with Vertex AI settings
        anthropic_client = self._get_anthropic_client()
        
        # Save the original client factory
        original_client_factory = anthropic.Anthropic
        
        try:
            # Replace the client factory with our custom one
            # This is a monkey patch to make the base implementation use our client
            anthropic.Anthropic = lambda *args, **kwargs: anthropic_client
            
            # Call the parent implementation which will now use our client
            return await super().generate(message, request_params)
        finally:
            # Restore the original client factory
            anthropic.Anthropic = original_client_factory
    
    def _get_anthropic_client(self) -> anthropic.Anthropic:
        """
        Create an Anthropic client configured to use Vertex AI.
        
        This is where the magic happens - we create a client that looks like
        a standard Anthropic client but actually points to Vertex AI.
        
        Returns:
            anthropic.Anthropic: Configured Anthropic client
        """
        # Get the configuration
        config = self.vertex_config
        
        # Get API key either from config, environment, or generate token from credentials
        api_key = config.api_key
        if not api_key and hasattr(self.context.config, "anthropic") and hasattr(self.context.config.anthropic, "api_key"):
            api_key = self.context.config.anthropic.api_key
            
        # If we still don't have an API key but we have credentials, try to generate a token
        if not api_key and hasattr(self, "credentials") and self.credentials:
            try:
                # Get an access token from the credentials
                auth_req = self.credentials.get_access_token()
                if auth_req and hasattr(auth_req, "token"):
                    api_key = auth_req.token
                    self.logger.info("Generated access token from service account credentials")
            except Exception as e:
                self.logger.error(f"Error generating access token: {str(e)}")
        
        # Configure the base URL for Vertex AI
        vertex_base_url = config.api_endpoint or f"https://{config.location}-aiplatform.googleapis.com"
        model_endpoint = config.model_endpoint or f"projects/{config.project_id}/locations/{config.location}/publishers/anthropic/models/{self.default_request_params.model}"
        
        # Create the client with appropriate configuration
        client = anthropic.Anthropic(
            # Use the API key we determined above
            api_key=api_key,
            # Set the base URL to the Vertex endpoint
            base_url=vertex_base_url,
            # Additional Vertex specific configuration
            default_headers={
                "X-Vertex-AI-Project": config.project_id,
                "X-Vertex-AI-Location": config.location, 
                "X-Vertex-AI-Model-Endpoint": model_endpoint
            }
        )
        
        # Log that we're using a custom client
        self.logger.info(f"Created Anthropic client pointing to Vertex AI: {vertex_base_url}")
        
        return client
        
    async def select_model(self, params: RequestParams) -> str:
        """
        Select the appropriate model to use based on request parameters.
        
        This overrides the base method to ensure we use Vertex AI models.
        
        Args:
            params: Request parameters
            
        Returns:
            str: The selected model name
        """
        # Use the model from params, falling back to default model from Vertex config
        model = params.model or self.vertex_config.default_model
        
        self.logger.info(f"Selected Vertex AI Anthropic model: {model}")
        return model 