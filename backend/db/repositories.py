from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from uuid import uuid4
from datetime import datetime
from sqlalchemy.orm import Session
import httpx
import os
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import update, delete, func

from db.models import User, Conversation, Message, File, FileAttachment, AgentLog, Document, DocumentChunk, SearchQuery, SearchResult
from config.settings import settings

logger = logging.getLogger(__name__)

# Abstract base repositories
class BaseRepository(ABC):
    @abstractmethod
    def create(self, obj_in: Dict[str, Any]) -> Any:
        pass
    
    @abstractmethod
    def get(self, id: str) -> Optional[Any]:
        pass
    
    @abstractmethod
    def update(self, id: str, obj_in: Dict[str, Any]) -> Any:
        pass
    
    @abstractmethod
    def delete(self, id: str) -> bool:
        pass

class UserRepository(BaseRepository):
    def __init__(self, db: Session):
        self.db = db
    
    def create(self, obj_in: Dict[str, Any]) -> User:
        db_obj = User(
            id=obj_in.get("id", str(uuid4())),
            email=obj_in["email"],
            name=obj_in.get("name", ""),
            meta_data=obj_in.get("metadata", {})
        )
        self.db.add(db_obj)
        self.db.commit()
        self.db.refresh(db_obj)
        return db_obj
    
    def get(self, id: str) -> Optional[User]:
        return self.db.query(User).filter(User.id == id).first()
    
    def get_by_email(self, email: str) -> Optional[User]:
        return self.db.query(User).filter(User.email == email).first()
    
    def update(self, id: str, obj_in: Dict[str, Any]) -> User:
        db_obj = self.get(id)
        if db_obj:
            if "metadata" in obj_in:
                obj_in["meta_data"] = obj_in.pop("metadata")
                
            for key, value in obj_in.items():
                setattr(db_obj, key, value)
            db_obj.updated_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(db_obj)
        return db_obj
    
    def delete(self, id: str) -> bool:
        db_obj = self.get(id)
        if db_obj:
            db_obj.is_active = False
            db_obj.updated_at = datetime.utcnow()
            self.db.commit()
            return True
        return False
        
    async def provision_trieve_dataset(self, user_id: str) -> Optional[str]:
        """
        Create a Trieve dataset for a user and store the dataset ID in the user record.
        
        Args:
            user_id: The ID of the user to provision a dataset for
            
        Returns:
            The ID of the created dataset, or None if the creation failed
        """
        user = self.get(user_id)
        if not user:
            logger.error(f"User {user_id} not found")
            return None
            
        # Skip if user already has a dataset
        if user.trieve_dataset_id:
            logger.info(f"User {user_id} already has Trieve dataset: {user.trieve_dataset_id}")
            return user.trieve_dataset_id
            
        try:
            dataset_name = f"user_{user_id}_dataset"
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{settings.TRIEVE_URL}/api/dataset",
                    headers={
                        "Authorization": f"Bearer {settings.TRIEVE_API_KEY}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "dataset_name": dataset_name,
                        "server_configuration": {
                            "chunk_size": settings.TRIEVE_CHUNK_SIZE,
                            "chunk_overlap": settings.TRIEVE_CHUNK_OVERLAP
                        },
                        "metadata": {
                            "user_id": user_id,
                            "email": user.email
                        }
                    },
                    timeout=30.0  # 30 second timeout
                )
                
                if response.status_code == 200:
                    data = response.json()
                    dataset_id = data.get("dataset_id")
                    if dataset_id:
                        # Update user with dataset ID
                        user.trieve_dataset_id = dataset_id
                        self.db.commit()
                        logger.info(f"Created Trieve dataset {dataset_id} for user {user_id}")
                        return dataset_id
                else:
                    logger.error(f"Failed to create Trieve dataset: {response.status_code} - {response.text}")
                    
        except Exception as e:
            logger.error(f"Error creating Trieve dataset for user {user_id}: {str(e)}")
            
        return None

class ConversationRepository(BaseRepository):
    def __init__(self, db: Session):
        self.db = db
    
    def create(self, obj_in: Dict[str, Any]) -> Conversation:
        db_obj = Conversation(
            id=obj_in.get("id", str(uuid4())),
            user_id=obj_in["user_id"],
            title=obj_in.get("title", "New Conversation"),
            meta_data=obj_in.get("metadata", {})
        )
        self.db.add(db_obj)
        self.db.commit()
        self.db.refresh(db_obj)
        return db_obj
    
    def get(self, id: str) -> Optional[Conversation]:
        return self.db.query(Conversation).filter(Conversation.id == id).first()
    
    def get_by_user(self, user_id: str) -> List[Conversation]:
        return self.db.query(Conversation).filter(
            Conversation.user_id == user_id,
            Conversation.is_active == True
        ).order_by(Conversation.updated_at.desc()).all()
    
    def update(self, id: str, obj_in: Dict[str, Any]) -> Conversation:
        db_obj = self.get(id)
        if db_obj:
            if "metadata" in obj_in:
                obj_in["meta_data"] = obj_in.pop("metadata")
                
            for key, value in obj_in.items():
                setattr(db_obj, key, value)
            db_obj.updated_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(db_obj)
        return db_obj
    
    def delete(self, id: str) -> bool:
        db_obj = self.get(id)
        if db_obj:
            db_obj.is_active = False
            db_obj.updated_at = datetime.utcnow()
            self.db.commit()
            return True
        return False

class MessageRepository(BaseRepository):
    DEFAULT_LIMIT = 50 # Define a default limit

    def __init__(self, db: Session):
        self.db = db
    
    def create(self, obj_in: Dict[str, Any]) -> Message:
        db_obj = Message(
            id=obj_in.get("id", str(uuid4())),
            conversation_id=obj_in["conversation_id"],
            content=obj_in["content"],
            role=obj_in["role"],
            meta_data=obj_in.get("metadata", {})
        )
        self.db.add(db_obj)
        self.db.commit()
        self.db.refresh(db_obj)
        return db_obj
    
    def get(self, id: str) -> Optional[Message]:
        return self.db.query(Message).filter(Message.id == id).first()
    
    def get_by_conversation(
        self,
        conversation_id: str,
        limit: Optional[int] = None,
        before_message_id: Optional[str] = None,
    ) -> Dict[str, Any]: # Return a dict with messages and pagination info
        """
        Get messages for a conversation, ordered by creation time descending, with pagination.
        """
        query = self.db.query(Message).filter(Message.conversation_id == conversation_id)

        if before_message_id:
            # Get the timestamp of the 'before' message
            before_message = self.get(before_message_id)
            
            if before_message:
                # --- Add extra logging --- 
                logger.info(f"[Pagination Debug] Fetched before_message: ID={before_message.id}, CreatedAt={repr(before_message.created_at)}, Type={type(before_message.created_at)}")
                # --- End extra logging ---
                
                # Only apply the filter if the timestamp exists
                if before_message.created_at is not None:
                    query = query.filter(Message.created_at < before_message.created_at)
            else:
                logger.warning(f"'before_message_id' {before_message_id} not found, ignoring pagination cursor.")

        # Always order by creation time descending for pagination
        query = query.order_by(Message.created_at.desc())

        # Determine the actual limit to use (fetch one extra to check for more)
        fetch_limit = (limit or self.DEFAULT_LIMIT) + 1
        
        messages = query.limit(fetch_limit).all()

        # Check if there are more messages
        has_more = len(messages) == fetch_limit
        
        # If we fetched an extra message, remove it from the result list
        if has_more:
            messages = messages[:-1]
        
        return {
            "messages": messages, 
            "has_more": has_more
        }
    
    def update(self, id: str, obj_in: Dict[str, Any]) -> Message:
        db_obj = self.get(id)
        if db_obj:
            if "metadata" in obj_in:
                obj_in["meta_data"] = obj_in.pop("metadata")
                
            for key, value in obj_in.items():
                setattr(db_obj, key, value)
            self.db.commit()
            self.db.refresh(db_obj)
        return db_obj
    
    def delete(self, id: str) -> bool:
        db_obj = self.get(id)
        if db_obj:
            self.db.delete(db_obj)
            self.db.commit()
            return True
        return False

class FileRepository(BaseRepository):
    def __init__(self, db: Session):
        self.db = db
    
    def create(self, obj_in: Dict[str, Any]) -> File:
        db_obj = File(
            id=obj_in.get("id", str(uuid4())),
            user_id=obj_in["user_id"],
            filename=obj_in["filename"],
            file_type=obj_in["file_type"],
            file_size=obj_in["file_size"],
            storage_path=obj_in["storage_path"],
            is_processed=obj_in.get("is_processed", False),
            vector_id=obj_in.get("vector_id"),
            meta_data=obj_in.get("metadata", {})
        )
        self.db.add(db_obj)
        self.db.commit()
        self.db.refresh(db_obj)
        return db_obj
    
    def get(self, id: str) -> Optional[File]:
        return self.db.query(File).filter(File.id == id).first()
    
    def get_by_user(self, user_id: str) -> List[File]:
        return self.db.query(File).filter(File.user_id == user_id).all()
    
    def update(self, id: str, obj_in: Dict[str, Any]) -> File:
        db_obj = self.get(id)
        if db_obj:
            if "metadata" in obj_in:
                obj_in["meta_data"] = obj_in.pop("metadata")
                
            for key, value in obj_in.items():
                setattr(db_obj, key, value)
            self.db.commit()
            self.db.refresh(db_obj)
        return db_obj
    
    def delete(self, id: str) -> bool:
        db_obj = self.get(id)
        if db_obj:
            self.db.delete(db_obj)
            self.db.commit()
            return True
        return False

class AgentLogRepository(BaseRepository):
    def __init__(self, db: Session):
        self.db = db
    
    def create(self, obj_in: Dict[str, Any]) -> AgentLog:
        db_obj = AgentLog(
            id=obj_in.get("id", str(uuid4())),
            agent_type=obj_in["agent_type"],
            query_id=obj_in["query_id"],
            input_data=obj_in["input_data"],
            output_data=obj_in.get("output_data", {}),
            processing_time=obj_in.get("processing_time", 0),
            status=obj_in.get("status", "success"),
            error_message=obj_in.get("error_message")
        )
        self.db.add(db_obj)
        self.db.commit()
        self.db.refresh(db_obj)
        return db_obj
    
    def get(self, id: str) -> Optional[AgentLog]:
        return self.db.query(AgentLog).filter(AgentLog.id == id).first()
    
    def get_by_query_id(self, query_id: str) -> List[AgentLog]:
        return self.db.query(AgentLog).filter(AgentLog.query_id == query_id).all()
    
    def update(self, id: str, obj_in: Dict[str, Any]) -> AgentLog:
        db_obj = self.get(id)
        if db_obj:
            for key, value in obj_in.items():
                setattr(db_obj, key, value)
            self.db.commit()
            self.db.refresh(db_obj)
        return db_obj
    
    def delete(self, id: str) -> bool:
        db_obj = self.get(id)
        if db_obj:
            self.db.delete(db_obj)
            self.db.commit()
            return True
        return False 

# New repository classes for document processing and RAG

class DocumentRepository(BaseRepository):
    async def get_by_id(self, document_id: str) -> Optional[Document]:
        query = select(Document).where(Document.id == document_id)
        result = await self.session.execute(query)
        return result.scalars().first()
    
    async def get_by_file_id(self, file_id: str) -> Optional[Document]:
        query = select(Document).where(Document.file_id == file_id)
        result = await self.session.execute(query)
        return result.scalars().first()
    
    async def create(self, document_data: Dict[str, Any]) -> Document:
        document = Document(**document_data)
        self.session.add(document)
        await self.session.commit()
        await self.session.refresh(document)
        return document
    
    async def update(self, document_id: str, document_data: Dict[str, Any]) -> Optional[Document]:
        query = update(Document).where(Document.id == document_id).values(**document_data)
        await self.session.execute(query)
        await self.session.commit()
        return await self.get_by_id(document_id)
    
    async def mark_as_processed(self, document_id: str) -> Optional[Document]:
        query = update(Document).where(Document.id == document_id).values(processed=True)
        await self.session.execute(query)
        await self.session.commit()
        return await self.get_by_id(document_id)
    
    async def get_unprocessed_documents(self, limit: int = 10) -> List[Document]:
        query = select(Document).where(Document.processed == False).limit(limit)
        result = await self.session.execute(query)
        return result.scalars().all()

class DocumentChunkRepository(BaseRepository):
    async def get_by_id(self, chunk_id: str) -> Optional[DocumentChunk]:
        query = select(DocumentChunk).where(DocumentChunk.id == chunk_id)
        result = await self.session.execute(query)
        return result.scalars().first()
    
    async def get_by_document_id(self, document_id: str) -> List[DocumentChunk]:
        query = select(DocumentChunk).where(DocumentChunk.document_id == document_id)
        result = await self.session.execute(query)
        return result.scalars().all()
    
    async def create(self, chunk_data: Dict[str, Any]) -> DocumentChunk:
        chunk = DocumentChunk(**chunk_data)
        self.session.add(chunk)
        await self.session.commit()
        await self.session.refresh(chunk)
        return chunk
    
    async def create_many(self, chunks_data: List[Dict[str, Any]]) -> List[DocumentChunk]:
        chunks = [DocumentChunk(**data) for data in chunks_data]
        self.session.add_all(chunks)
        await self.session.commit()
        return chunks
    
    async def update_vector_id(self, chunk_id: str, vector_id: str) -> Optional[DocumentChunk]:
        query = update(DocumentChunk).where(DocumentChunk.id == chunk_id).values(vector_id=vector_id)
        await self.session.execute(query)
        await self.session.commit()
        return await self.get_by_id(chunk_id)

class SearchQueryRepository(BaseRepository):
    async def create(self, query_data: Dict[str, Any]) -> SearchQuery:
        query = SearchQuery(**query_data)
        self.session.add(query)
        await self.session.commit()
        await self.session.refresh(query)
        return query
    
    async def get_by_user(self, user_id: str, limit: int = 50) -> List[SearchQuery]:
        query = select(SearchQuery).where(SearchQuery.user_id == user_id).order_by(
            SearchQuery.created_at.desc()
        ).limit(limit)
        result = await self.session.execute(query)
        return result.scalars().all()

class SearchResultRepository(BaseRepository):
    async def create_many(self, results_data: List[Dict[str, Any]]) -> List[SearchResult]:
        results = [SearchResult(**data) for data in results_data]
        self.session.add_all(results)
        await self.session.commit()
        return results
    
    async def get_by_query_id(self, query_id: str) -> List[SearchResult]:
        query = select(SearchResult).where(SearchResult.search_query_id == query_id).order_by(
            SearchResult.position
        )
        result = await self.session.execute(query)
        return result.scalars().all() 