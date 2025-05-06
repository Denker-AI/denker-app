# Denker Backend

This is the backend API for the Denker application, an AI-powered desktop assistant.

## Features

- RESTful API built with FastAPI
- Authentication with Auth0
- PostgreSQL database for data storage
- Qdrant vector database for semantic search
- Redis for caching and real-time features
- WebSocket support for real-time communication
- File upload and management with Google Cloud Storage
- AI integration with Vertex AI

## Prerequisites

- Python 3.9+
- PostgreSQL 13+
- Redis 6.0+
- Google Cloud Storage account
- Auth0 account
- Qdrant vector database for RAG functionality

## Installation

1. Clone the repository:

```bash
git clone https://github.com/yourusername/denker-app.git
cd denker-app/backend
```

2. Create a virtual environment:

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Create a `.env` file based on `.env.example`:

```bash
cp .env.example .env
```

5. Edit the `.env` file with your configuration.

## Database Setup

The application uses PostgreSQL as the main database and Redis for caching.

To set up the database:

```bash
python setup_db.py
```

This script will:

1. Create the initial migration
2. Apply the migration to create the database tables

## Qdrant Setup for RAG

The application uses Qdrant for Retrieval-Augmented Generation (RAG) with user files. This allows the AI to reference user-uploaded documents when generating responses.

To set up Qdrant:

1. Start Qdrant (for development):

```bash
docker run -d -p 6333:6333 -p 6334:6334 -v ./qdrant_data:/qdrant/storage qdrant/qdrant
```

2. Run the setup script:

```bash
./scripts/setup_qdrant_dev.sh
```

This script will:
1. Install necessary dependencies
2. Create the Qdrant collection
3. Load sample data

### File Processing for RAG

When users upload files through the frontend, they are automatically:
1. Saved to Google Cloud Storage
2. Processed and chunked into smaller segments
3. Embedded using Vertex AI embeddings
4. Stored in Qdrant for semantic retrieval

Supported file types include:
- PDF (.pdf)
- Text (.txt)
- Word documents (.docx, .doc)
- Excel spreadsheets (.xlsx, .xls)
- HTML (.html, .htm)
- Markdown (.md)
- CSV (.csv)

To manually process a file:

```bash
python scripts/process_file_to_qdrant.py --file path/to/file.pdf --url http://localhost:6333
```

## Running the Application

To run the application in development mode:

```bash
uvicorn main:app --reload
```

The API will be available at http://localhost:8000.

The API documentation is available at:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Project Structure

- `api/`: API endpoints
  - `api_v1/`: API version 1
    - `endpoints/`: API endpoint modules
    - `api.py`: API router
- `config/`: Configuration files
  - `settings.py`: Application settings
- `core/`: Core functionality
  - `auth.py`: Authentication utilities
  - `security.py`: Security utilities
- `db/`: Database models and utilities
  - `models.py`: SQLAlchemy models
  - `database.py`: Database connection
  - `repositories.py`: Repository pattern implementation
  - `init_db.py`: Database initialization
- `migrations/`: Alembic migrations
- `services/`: Service layer
  - `ai_service.py`: AI service
  - `file_service.py`: File service
- `utils/`: Utility functions
- `main.py`: Application entry point

## API Endpoints

### Root Endpoints

- `GET /api/v1/health`: Simple health check endpoint for basic availability testing

### Authentication

- `POST /api/v1/auth/login`: Login with Auth0
- `POST /api/v1/auth/logout`: Logout

### Users

- `GET /api/v1/users/profile`: Get user profile
- `PUT /api/v1/users/profile`: Update user profile
- `GET /api/v1/users/settings`: Get user settings
- `PUT /api/v1/users/settings`: Update user settings

### Conversations

- `GET /api/v1/conversations/list`: List conversations
- `POST /api/v1/conversations/new`: Create a new conversation
- `GET /api/v1/conversations/{conversation_id}`: Get a conversation
- `PUT /api/v1/conversations/{conversation_id}`: Update a conversation
- `DELETE /api/v1/conversations/{conversation_id}`: Delete a conversation
- `POST /api/v1/conversations/{conversation_id}/messages`: Add a message to a conversation

### Files

- `GET /api/v1/files/list`: List files
- `POST /api/v1/files/upload`: Upload a file
- `GET /api/v1/files/{file_id}`: Get file metadata
- `GET /api/v1/files/{file_id}/download`: Download a file
- `GET /api/v1/files/{file_id}/direct-download`: Get direct download URL for a file
- `DELETE /api/v1/files/{file_id}`: Delete a file
- `GET /api/v1/files/`: List all files (alternative endpoint)
- `POST /api/v1/files/search`: Search for files

### Agents

- `POST /api/v1/agents/intention`: Process user intention
- `POST /api/v1/agents/coordinator/mcp-agent`: Process MCP agent coordinator
- `GET /api/v1/agents/status/{query_id}`: Get query status
- `WebSocket /api/v1/agents/ws/mcp-agent/{query_id}`: WebSocket for real-time agent updates
- `GET /api/v1/agents/health/mcp-agent`: Check health of MCP-Agent servers
- `POST /api/v1/agents/generate-text`: Generate text using AI models
- `POST /api/v1/agents/gemini`: Generate text using Gemini AI model
- `GET /api/v1/agents/qdrant/health`: Check health of Qdrant vector database
- `GET /api/v1/agents/session/{session_id}`: Get session history with queries and results

## Global Coordinator

The application uses a global coordinator singleton for managing MCP agent interactions. This ensures:

1. Proper lifecycle management of the MCP agent
2. Efficient resource usage across requests
3. Consistent state management

The global coordinator is initialized during application startup and cleaned up during shutdown. API endpoints interact with it through dependency injection.

## Testing

To run tests:

```bash
pytest
```

## License

This project is licensed under the MIT License - see the LICENSE file for details.