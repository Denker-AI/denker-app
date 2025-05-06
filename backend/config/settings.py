import os
from typing import Dict, Any, Optional, List, ClassVar
from pydantic_settings import BaseSettings
from pydantic import Field
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Settings(BaseSettings):
    # Application settings
    APP_NAME: str = "Denker"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = Field(default=False)
    LOG_LEVEL: str = Field(default="INFO")
    API_PREFIX: str = "/api/v1"
    
    # Database settings
    POSTGRES_HOST: str
    POSTGRES_PORT: int
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str
    
    # Google Cloud settings
    GOOGLE_APPLICATION_CREDENTIALS: str = Field(default="/app/vertexai.json")  # For Vertex AI / LLMs
    GCS_SERVICE_ACCOUNT_KEY: str = Field(default="/app/key.json")  # For GCS and database access
    VERTEX_AI_PROJECT: str
    VERTEX_AI_LOCATION: str = Field(default="europe-west3")
    GCS_BUCKET_NAME: str
    GCS_ENABLED: bool = Field(default=True)
    GOOGLE_API_KEY: str = Field(default="")
    GOOGLE_CSE_ID: str = Field(default="")
    
    # MCP Client Settings
    MCP_REQUEST_TIMEOUT: int = Field(default=30)
    MCP_MAX_RETRIES: int = Field(default=3)
    
    # Qdrant settings
    QDRANT_URL: str = Field(default="http://localhost:6333")
    QDRANT_COLLECTION_NAME: str = Field(default="denker_embeddings")
    QDRANT_ENABLED: bool = Field(default=True)
    QDRANT_VECTOR_SIZE: int = Field(default=768)  # Default for Gemini embeddings
    
    # Auth settings
    AUTH0_DOMAIN: str
    AUTH0_API_AUDIENCE: str
    
    # Vertex AI settings
    VERTEX_AI_ENABLED: bool = Field(default=True)
    VERTEX_AI_PROJECT_ID: str
    VERTEX_AI_LOCATION: str = Field(default="europe-west3")
    
    # Anthropic settings
    ANTHROPIC_API_KEY: str = Field(default="")
    ANTHROPIC_MODEL: str = Field(default="claude-3-7-sonnet-20250219")
    
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
    
    # Database initialization
    AUTO_INIT_DB: bool = os.getenv("AUTO_INIT_DB", "true").lower() == "true"
    
    # Auth0 settings
    AUTH0_ALGORITHMS: list = ["RS256"]
    
    # Google Cloud Storage
    GCS_ENABLED: bool = Field(default=True)
    
    # Scheduler
    SCHEDULER_ENABLED: bool = Field(default=False)
    
    def __init__(self, **data: Any):
        super().__init__(**data)
        # Set DATABASE_URL after initialization
        object.__setattr__(self, 'DATABASE_URL', f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}")
    
    class Config:
        env_file = ".env"
        case_sensitive = True

# Create settings instance
settings = Settings()

# Database connection configs
database_config: Dict[str, Dict[str, Any]] = {
    "postgres": {
        "host": settings.POSTGRES_HOST,
        "port": settings.POSTGRES_PORT,
        "user": settings.POSTGRES_USER,
        "password": settings.POSTGRES_PASSWORD,
        "database": settings.POSTGRES_DB,
    },
    "qdrant": {
        "url": settings.QDRANT_URL,
        "collection": settings.QDRANT_COLLECTION_NAME,
        "enabled": settings.QDRANT_ENABLED
    }
}