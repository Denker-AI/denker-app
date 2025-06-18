import os
from typing import Dict, Any, Optional, List, ClassVar
from pydantic_settings import BaseSettings
from pydantic import Field
from dotenv import load_dotenv
from urllib.parse import urlparse, urlunparse # Added for URL manipulation

# Load environment variables from .env file
load_dotenv()

def get_root_remote_url_from_env():
    """
    Determines the root remote URL, preferring specific root env vars,
    then stripping /api/v1 from VITE_API_URL if necessary,
    and finally falling back to DENKER_BACKEND_URL (stripping /api/v1 as a precaution) or a hardcoded default.
    Ensures the returned URL does not have a trailing slash.
    """
    url_str = None
    source_log = [] # To log where the URL came from for easier debugging

    # 1. Prefer DENKER_ROOT_REMOTE_URL (expected to be the clean root)
    denker_root_url = os.getenv("DENKER_ROOT_REMOTE_URL")
    if denker_root_url:
        url_str = denker_root_url
        source_log.append(f"DENKER_ROOT_REMOTE_URL ('{url_str}')")

    # 2. Try VITE_API_URL (often includes /api/v1)
    if not url_str:
        vite_api_url = os.getenv("VITE_API_URL")
        if vite_api_url:
            source_log.append(f"VITE_API_URL ('{vite_api_url}')")
            parsed = urlparse(vite_api_url)
            if parsed.path.rstrip('/').endswith('/api/v1'):
                # Strip /api/v1 and anything after it from the path
                new_path = parsed.path.rsplit('/api/v1', 1)[0]
                url_str = urlunparse(parsed._replace(path=new_path))
                source_log.append(f"Stripped to '{url_str}'")
            else:
                # Assume VITE_API_URL is already a root or doesn't have /api/v1 in a way we should strip
                url_str = vite_api_url

    # 3. Fallback to DENKER_BACKEND_URL (user's current one, might be root or have /api/v1)
    if not url_str:
        denker_backend_url = os.getenv("DENKER_BACKEND_URL")
        if denker_backend_url:
            source_log.append(f"DENKER_BACKEND_URL ('{denker_backend_url}')")
            # Similar stripping logic as for VITE_API_URL, just in case
            parsed = urlparse(denker_backend_url)
            if parsed.path.rstrip('/').endswith('/api/v1'):
                new_path = parsed.path.rsplit('/api/v1', 1)[0]
                url_str = urlunparse(parsed._replace(path=new_path))
                source_log.append(f"Stripped to '{url_str}'")
            else:
                url_str = denker_backend_url
    
    # 4. Final hardcoded default if no environment variables provide a URL
    if not url_str:
        url_str = "http://localhost:8001" # Default to root
        source_log.append(f"Hardcoded Default ('{url_str}')")

    # print(f"DEBUG: Determined BACKEND_URL: '{url_str.rstrip('/')}' from sources: {', '.join(source_log)}")
    return url_str.rstrip('/')


class Settings(BaseSettings):
    # Application settings
    APP_NAME: str = "Denker"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = Field(default=False)
    LOG_LEVEL: str = Field(default="INFO")
    API_PREFIX: str = "/api/v1" # This is for constructing URLs *exposed by* this local backend
    
    # Server settings (for Uvicorn)
    SERVER_HOST: str = Field(default="0.0.0.0", description="Host for the Uvicorn server.")
    SERVER_PORT: int = Field(default=9001, description="Port for the Uvicorn server.")
    RELOAD_SERVER: bool = Field(default=False, description="Enable Uvicorn auto-reload (typically for development).")
    
    # Google Cloud settings
    GOOGLE_API_KEY: str = Field(default="")
    GOOGLE_CSE_ID: str = Field(default="")
    
    # MCP Client Settings
    MCP_REQUEST_TIMEOUT: int = Field(default=30)
    MCP_MAX_RETRIES: int = Field(default=3)
    
    # Qdrant settings
    QDRANT_URL: str = Field(default="http://localhost:6333")
    QDRANT_API_KEY: Optional[str] = Field(default=None)
    QDRANT_COLLECTION_NAME: str = Field(default="denker_embeddings")
    QDRANT_ENABLED: bool = Field(default=True)
    QDRANT_VECTOR_SIZE: int = Field(default=384)
    EMBEDDING_MODEL: Optional[str] = Field(default=None)
    VECTOR_NAME: Optional[str] = Field(default=None)
    
    # Auth settings
    AUTH0_DOMAIN: str = Field(default="auth.denker.ai")
    AUTH0_API_AUDIENCE: str = Field(default="https://api.denker.ai")
    
    # Vertex AI settings
    VERTEX_AI_ENABLED: bool = Field(default=True)
    VERTEX_AI_PROJECT_ID: str = Field(default="modular-bucksaw-424010-p6")
    VERTEX_AI_LOCATION: str = Field(default="europe-west3")
    
    # Anthropic settings
    ANTHROPIC_API_KEY: str = Field(default="")
    ANTHROPIC_MODEL: str = Field(default="claude-3-5-haiku-20241022")
    
    # Unsplash API settings
    UNSPLASH_ACCESS_KEY: str = Field(default="")
    UNSPLASH_SECRET_KEY: str = Field(default="")


    # Security settings
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key-here")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # File storage settings
    UPLOAD_DIR: str = "uploads"
    MAX_FILE_SIZE: int = 30 * 1024 * 1024  # 30MB
    ALLOWED_FILE_TYPES: list = [
        # Documents
        "pdf", "txt", "doc", "docx", 
        # Spreadsheets
        "csv", "xls", "xlsx",
        # Web content
        "html", "htm", "md", "markdown",
        # Images
        "jpg", "jpeg", "png", "gif", "bmp", "tiff", "webp"
    ]
    
    # Auth0 settings
    AUTH0_ALGORITHMS: list = ["RS256"]
    
    # Scheduler
    SCHEDULER_ENABLED: bool = Field(default=False)
    
    # Backend API URL for memory operations and other remote calls
    # This URL should be the ROOT of the remote backend, e.g., http://localhost:8001
    BACKEND_URL: str = Field(
        default_factory=get_root_remote_url_from_env,
        description="Root URL of the remote backend API. Determined from DENKER_ROOT_REMOTE_URL, VITE_API_URL (with /api/v1 stripped), DENKER_BACKEND_URL, or a default."
    )
    
    def __init__(self, **data: Any):
        super().__init__(**data)
    
    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"

# Create settings instance
settings = Settings()