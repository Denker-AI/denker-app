from fastapi import APIRouter

from api.api_v1.endpoints import agents, settings, test_vertex

api_router = APIRouter()

# Add a simple health check endpoint
@api_router.get("/health")
async def health_check():
    """Simple health check endpoint for basic availability testing"""
    return {"status": "ok", "message": "Local API is operational"}

api_router.include_router(agents.router, prefix="/agents", tags=["agents"])
api_router.include_router(settings.router, prefix="/settings", tags=["settings"])
api_router.include_router(test_vertex.router, prefix="/test", tags=["testing"]) 