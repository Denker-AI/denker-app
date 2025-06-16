from fastapi import APIRouter

from api.api_v1.endpoints import auth, users, conversations, files, agents, memory

api_router = APIRouter()

# Add a simple health check endpoint
@api_router.get("/health")
async def health_check():
    """Simple health check endpoint for basic availability testing"""
    return {"status": "ok", "message": "API is operational"}

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(conversations.router, prefix="/conversations", tags=["conversations"])
api_router.include_router(files.router, prefix="/files", tags=["files"])
api_router.include_router(agents.router, prefix="/agents", tags=["agents"])
api_router.include_router(memory.router, prefix="/memory", tags=["memory"]) 