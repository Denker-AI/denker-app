"""
Test endpoint for Vertex AI Anthropic integration.
"""

import os
import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
import asyncio

router = APIRouter()
logger = logging.getLogger(__name__)

class VertexTestRequest(BaseModel):
    model: str = "claude-3-7-sonnet-20250219"
    message: str = "Hello, can you respond with a simple greeting?"
    use_vertex: bool = True

class VertexTestResponse(BaseModel):
    success: bool
    model_used: str
    response_text: str
    client_type: str
    error: Optional[str] = None
    conversion_result: str
    environment_info: Dict[str, Any]

@router.post("/test-vertex", response_model=VertexTestResponse)
async def test_vertex_anthropic(request: VertexTestRequest):
    """
    Test endpoint to verify Vertex AI Anthropic integration is working.
    """
    try:
        # Get environment info
        env_info = {
            "USE_VERTEX_ANTHROPIC": os.environ.get("USE_VERTEX_ANTHROPIC", "not_set"),
            "VERTEX_PROJECT_ID": os.environ.get("VERTEX_PROJECT_ID", "not_set"),
            "VERTEX_REGION": os.environ.get("VERTEX_REGION", "not_set"),
            "ANTHROPIC_API_KEY": "***" if os.environ.get("ANTHROPIC_API_KEY") else "not_set"
        }
        
        # Simple model conversion mapping (standalone)
        vertex_mappings = {
            "claude-3-7-sonnet-20250219": "claude-3-7-sonnet@20250219",
            "claude-3-5-haiku-20241022": "claude-3-5-haiku@20241022",
            "claude-3-5-sonnet-20241022": "claude-3-5-sonnet-v2@20241022",
        }
        converted_model = vertex_mappings.get(request.model, request.model)
        
        # Check if USE_VERTEX_ANTHROPIC is set to true - if so, force Vertex AI
        use_vertex_env = os.environ.get("USE_VERTEX_ANTHROPIC", "false").lower() == "true"
        logger.info(f"USE_VERTEX_ANTHROPIC env var: {os.environ.get('USE_VERTEX_ANTHROPIC')}, use_vertex_env: {use_vertex_env}, request.use_vertex: {request.use_vertex}")
        
        # Test client creation and call
        try:
            # Import clients directly
            from anthropic import Anthropic, AnthropicVertex
            
            if use_vertex_env:
                # When USE_VERTEX_ANTHROPIC=true, always use Vertex AI regardless of request.use_vertex
                logger.info(f"Forcing Vertex AI because USE_VERTEX_ANTHROPIC=true, request.use_vertex={request.use_vertex}")
                client = AnthropicVertex(
                    project_id=os.environ.get("VERTEX_PROJECT_ID", "modular-bucksaw-424010-p6"),
                    region=os.environ.get("VERTEX_REGION", "europe-west1")
                )
                client_type = "AnthropicVertex (forced by USE_VERTEX_ANTHROPIC=true)"
            elif request.use_vertex:
                client = AnthropicVertex(
                    project_id=os.environ.get("VERTEX_PROJECT_ID", "modular-bucksaw-424010-p6"),
                    region=os.environ.get("VERTEX_REGION", "europe-west1")
                )
                client_type = "AnthropicVertex"
            else:
                client = Anthropic()  # Uses environment variable for API key
                client_type = "Anthropic"
            
            # Test simple message
            # Both clients use the same create method (no acreate in anthropic 0.50.0)
            model_to_use = converted_model if (use_vertex_env or request.use_vertex) else request.model
            response = client.messages.create(
                model=model_to_use,
                max_tokens=100,
                messages=[{
                    "role": "user", 
                    "content": request.message
                }]
            )
            
            return VertexTestResponse(
                success=True,
                model_used=model_to_use,
                response_text=response.content[0].text if response.content else "No response",
                client_type=client_type,
                conversion_result=f"{request.model} → {converted_model}",
                environment_info=env_info
            )
            
        except Exception as api_error:
            logger.error(f"API call failed: {api_error}")
            return VertexTestResponse(
                success=False,
                model_used=converted_model if (use_vertex_env or request.use_vertex) else request.model,
                response_text="",
                client_type="Failed to create client",
                error=str(api_error),
                conversion_result=f"{request.model} → {converted_model}",
                environment_info=env_info
            )
            
    except Exception as e:
        logger.error(f"Test failed: {e}")
        raise HTTPException(status_code=500, detail=f"Test failed: {str(e)}")

@router.get("/vertex-info")
async def get_vertex_info():
    """
    Get current Vertex AI configuration information.
    """
    try:
        # Test model conversions using simple mapping
        test_models = [
            "claude-3-7-sonnet-20250219",
            "claude-3-5-haiku-20241022",
            "claude-3-5-sonnet-20241022"
        ]
        
        vertex_mappings = {
            "claude-3-7-sonnet-20250219": "claude-3-7-sonnet@20250219",
            "claude-3-5-haiku-20241022": "claude-3-5-haiku@20241022",
            "claude-3-5-sonnet-20241022": "claude-3-5-sonnet-v2@20241022",
        }
        
        conversions = {}
        for model in test_models:
            conversions[model] = vertex_mappings.get(model, model)
        
        return {
            "environment": {
                "USE_VERTEX_ANTHROPIC": os.environ.get("USE_VERTEX_ANTHROPIC", "not_set"),
                "VERTEX_PROJECT_ID": os.environ.get("VERTEX_PROJECT_ID", "not_set"),
                "VERTEX_REGION": os.environ.get("VERTEX_REGION", "not_set"),
                "ANTHROPIC_API_KEY": "***" if os.environ.get("ANTHROPIC_API_KEY") else "not_set"
            },
            "model_conversions": conversions,
            "client_selection": {
                "uses_vertex": os.environ.get("USE_VERTEX_ANTHROPIC", "").lower() == "true",
                "fallback_available": bool(os.environ.get("ANTHROPIC_API_KEY"))
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get info: {str(e)}")

@router.post("/test-models")
async def test_available_models():
    """
    Test which models are actually available in Vertex AI.
    """
    try:
        from anthropic import AnthropicVertex
        
        client = AnthropicVertex(
            region=os.environ.get("VERTEX_REGION", "europe-west1"),
            project_id=os.environ.get("VERTEX_PROJECT_ID", "modular-bucksaw-424010-p6")
        )
        
        # Test different model name formats
        test_models = [
            "claude-3-7-sonnet@20250219",
            "claude-3-5-haiku@20241022", 
            "claude-3-5-sonnet-v2@20241022",
            "claude-3-sonnet@20240229",
            "claude-3-haiku@20240307"
        ]
        
        results = {}
        for model in test_models:
            try:
                # Vertex AI client uses synchronous create
                response = client.messages.create(
                    model=model,
                    max_tokens=10,
                    messages=[{"role": "user", "content": "Hi"}]
                )
                results[model] = {"status": "available", "response": "success"}
            except Exception as e:
                results[model] = {"status": "error", "error": str(e)}
        
        return {"model_availability": results}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to test models: {str(e)}") 