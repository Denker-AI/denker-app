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