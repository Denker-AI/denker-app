# Denker Database Setup

This directory contains the database models, repositories, and initialization code for the Denker application.

## Database Structure

The Denker application uses the following databases:

1. **PostgreSQL**: Main relational database for storing user data, conversations, messages, and file metadata.
2. **Qdrant**: Vector database for storing embeddings for semantic search and RAG operations.

## Models

The following models are defined in `models.py`:

- **User**: Represents a user of the application.
- **Conversation**: Represents a conversation between a user and the assistant.
- **Message**: Represents a message in a conversation.
- **File**: Represents a file uploaded by a user.
- **FileAttachment**: Represents a file attached to a message.
- **AgentLog**: Represents a log entry for an agent operation.

## Repositories

The repository pattern is implemented in `repositories.py` to provide a clean interface for database operations. The following repositories are available:

- **UserRepository**: CRUD operations for users.
- **ConversationRepository**: CRUD operations for conversations.
- **MessageRepository**: CRUD operations for messages.
- **FileRepository**: CRUD operations for files.
- **AgentLogRepository**: CRUD operations for agent logs.

## Database Initialization

The database initialization process is handled by the `init_db.py` script, which creates the PostgreSQL tables.

## Migrations

Database migrations are managed using Alembic. The migration files are stored in the `migrations` directory.

To create a new migration:

```bash
alembic revision --autogenerate -m "Description of the migration"
```

To apply migrations:

```bash
alembic upgrade head
```

## Setup

To set up the database for the first time, run the `setup_db.py` script from the root directory:

```bash
python setup_db.py
```

This script will:

1. Create the initial migration.
2. Apply the migration to create the database tables.

For Qdrant setup, run:

```bash
./scripts/setup_qdrant_dev.sh
```

## Configuration

Database configuration is stored in the `.env` file and loaded through the `config/settings.py` module. The following environment variables are used:

### PostgreSQL
- `POSTGRES_USER`: PostgreSQL username
- `POSTGRES_PASSWORD`: PostgreSQL password
- `POSTGRES_HOST`: PostgreSQL host
- `POSTGRES_PORT`: PostgreSQL port
- `POSTGRES_DB`: PostgreSQL database name
- `AUTO_INIT_DB`: Whether to automatically initialize the database on startup

### Qdrant
- `QDRANT_URL`: Qdrant URL (default: http://localhost:6333)
- `QDRANT_COLLECTION_NAME`: Qdrant collection name (default: denker_embeddings)
- `QDRANT_ENABLED`: Whether Qdrant is enabled
- `QDRANT_VECTOR_SIZE`: Size of embedding vectors (default: 768) 