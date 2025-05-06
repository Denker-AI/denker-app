from sqlalchemy import text
from db.database import engine
from config.settings import settings
import logging

logger = logging.getLogger(__name__)

async def init_postgres():
    """Initialize PostgreSQL database with required tables"""
    try:
        with engine.connect() as connection:
            # Create tables
            connection.execute(text("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    email VARCHAR(255) UNIQUE NOT NULL,
                    hashed_password VARCHAR(255) NOT NULL,
                    full_name VARCHAR(255),
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
            """))
            
            connection.execute(text("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER REFERENCES users(id),
                    title VARCHAR(255),
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
            """))
            
            connection.execute(text("""
                CREATE TABLE IF NOT EXISTS messages (
                    id SERIAL PRIMARY KEY,
                    conversation_id INTEGER REFERENCES conversations(id),
                    role VARCHAR(50) NOT NULL,
                    content TEXT NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
            """))
            
            connection.execute(text("""
                CREATE TABLE IF NOT EXISTS files (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER REFERENCES users(id),
                    filename VARCHAR(255) NOT NULL,
                    file_path VARCHAR(255) NOT NULL,
                    file_type VARCHAR(50),
                    file_size INTEGER,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
            """))
            
            # Create memory tables
            connection.execute(text("""
                -- Memory Entities Table
                CREATE TABLE IF NOT EXISTS memory_entities (
                    entity_name VARCHAR(255) PRIMARY KEY,
                    entity_type VARCHAR(100) NOT NULL,
                    conversation_ref VARCHAR(255) NULL,
                    message_ref VARCHAR(255) NULL,
                    ttl TIMESTAMP NULL,
                    metadata JSONB DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                -- Memory Observations Table
                CREATE TABLE IF NOT EXISTS memory_observations (
                    id SERIAL PRIMARY KEY,
                    entity_name VARCHAR(255) REFERENCES memory_entities(entity_name) ON DELETE CASCADE,
                    content TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                -- Memory Relations Table
                CREATE TABLE IF NOT EXISTS memory_relations (
                    id UUID PRIMARY KEY,
                    from_entity VARCHAR(255) REFERENCES memory_entities(entity_name) ON DELETE CASCADE,
                    to_entity VARCHAR(255) REFERENCES memory_entities(entity_name) ON DELETE CASCADE,
                    relation_type VARCHAR(100) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(from_entity, to_entity, relation_type)
                );

                -- Add indexes for common queries
                CREATE INDEX IF NOT EXISTS idx_entity_type ON memory_entities(entity_type);
                CREATE INDEX IF NOT EXISTS idx_observation_entity ON memory_observations(entity_name);
                CREATE INDEX IF NOT EXISTS idx_relation_from ON memory_relations(from_entity);
                CREATE INDEX IF NOT EXISTS idx_relation_to ON memory_relations(to_entity);
            """))
            
            connection.commit()
            logger.info("PostgreSQL tables created successfully")
            
    except Exception as e:
        logger.error(f"Failed to initialize PostgreSQL: {e}")
        raise

async def init_db():
    """Initialize all databases"""
    logger.info("Initializing databases...")
    
    # Initialize PostgreSQL
    await init_postgres()
    logger.info("Database initialization completed successfully")

if __name__ == "__main__":
    import asyncio
    asyncio.run(init_db()) 