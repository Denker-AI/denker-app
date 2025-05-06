from datetime import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, JSON, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import TIMESTAMP # Import specific type

import uuid

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(255), unique=True, nullable=False)
    name = Column(String(255))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    is_active = Column(Boolean, default=True)
    meta_data = Column(JSON, default={})
    trieve_dataset_id = Column(String, nullable=True)  # Trieve dataset ID for this user
    
    conversations = relationship("Conversation", back_populates="user")
    files = relationship("File", back_populates="user")

class Conversation(Base):
    __tablename__ = "conversations"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    title = Column(String(255))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    is_active = Column(Boolean, default=True)
    meta_data = Column(JSON, default={})
    
    user = relationship("User", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")

class Message(Base):
    __tablename__ = "messages"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    conversation_id = Column(String(36), ForeignKey("conversations.id"), nullable=False)
    role = Column(String(50), nullable=False)  # 'user' or 'assistant'
    content = Column(Text)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    meta_data = Column(JSON, default={})
    
    conversation = relationship("Conversation", back_populates="messages")
    file_attachments = relationship("FileAttachment", back_populates="message", cascade="all, delete-orphan")

class File(Base):
    __tablename__ = "files"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    filename = Column(String(255), nullable=False)
    storage_path = Column(String(255), nullable=False)
    file_size = Column(Integer)
    file_type = Column(String(100))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    is_deleted = Column(Boolean, default=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    vector_id = Column(String, nullable=True)  # Reference to vector in Qdrant
    meta_data = Column(JSON, default={})
    is_processed = Column(Boolean, default=False)
    
    user = relationship("User", back_populates="files")
    file_attachments = relationship("FileAttachment", back_populates="file")
    document = relationship("Document", back_populates="file", uselist=False)

class FileAttachment(Base):
    __tablename__ = "file_attachments"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    message_id = Column(String(36), ForeignKey("messages.id"), nullable=False)
    file_id = Column(String(36), ForeignKey("files.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    message = relationship("Message", back_populates="file_attachments")
    file = relationship("File", back_populates="file_attachments")

class AgentLog(Base):
    __tablename__ = "agent_logs"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_type = Column(String(50), nullable=False)
    query_id = Column(String(36), nullable=False)
    input_data = Column(JSON)
    output_data = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    processing_time = Column(Float)
    status = Column(String(50), default="completed")
    error_message = Column(Text)

# New models for document processing and RAG

class Document(Base):
    __tablename__ = "documents"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    file_id = Column(String(36), ForeignKey("files.id"), nullable=True)
    title = Column(String(255), nullable=False)
    content = Column(Text)
    source_type = Column(String(50), nullable=False)  # 'file', 'web', 'text'
    source_url = Column(String(1024), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    processed = Column(Boolean, default=False)
    
    file = relationship("File", back_populates="document")
    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")

class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id = Column(String(36), ForeignKey("documents.id"), nullable=False)
    content = Column(Text, nullable=False)
    chunk_index = Column(Integer, nullable=False)
    chunk_metadata = Column(JSON, nullable=True)
    vector_id = Column(String(100), nullable=True)  # ID in Qdrant
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    document = relationship("Document", back_populates="chunks")

class SearchQuery(Base):
    __tablename__ = "search_queries"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    query_text = Column(Text, nullable=False)
    source = Column(String(50), nullable=False)  # 'web', 'document', 'file'
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    results_count = Column(Integer)

class SearchResult(Base):
    __tablename__ = "search_results"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    search_query_id = Column(String(36), ForeignKey("search_queries.id"), nullable=False)
    source_id = Column(String(255))  # Document ID, chunk ID, or URL
    source_type = Column(String(50), nullable=False)  # 'document', 'chunk', 'web'
    relevance_score = Column(Float)
    position = Column(Integer)
    created_at = Column(DateTime(timezone=True), server_default=func.now()) 