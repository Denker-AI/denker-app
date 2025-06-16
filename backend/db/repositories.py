from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from uuid import uuid4
from datetime import datetime
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.orm.attributes import flag_modified
import httpx
import os
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import update as sqlalchemy_update_stmt, delete, func, and_, or_, cast, Text
from sqlalchemy.dialects.postgresql import JSONB
import json

from db.models import User, Conversation, Message, File, FileAttachment, AgentLog, Document, DocumentChunk, SearchQuery, SearchResult, MemoryEntity, MemoryRelation, MemoryObservation
from config.settings import settings

logger = logging.getLogger(__name__)

# Abstract base repositories
class BaseRepository(ABC):
    @abstractmethod
    async def create(self, obj_in: Dict[str, Any]) -> Any:
        pass
    
    @abstractmethod
    async def get(self, id: str) -> Optional[Any]:
        pass
    
    @abstractmethod
    async def update(self, id: str, obj_in: Dict[str, Any]) -> Any:
        pass
    
    @abstractmethod
    async def delete(self, id: str) -> bool:
        pass

class UserRepository(BaseRepository):
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create(self, obj_in: Dict[str, Any], commit: bool = True) -> User:
        db_obj = User(
            id=obj_in.get("id", str(uuid4())),
            email=obj_in["email"],
            name=obj_in.get("name", ""),
            meta_data=obj_in.get("meta_data", {})
        )
        self.db.add(db_obj)
        if commit:
            await self.db.commit()
            await self.db.refresh(db_obj)
        else:
            await self.db.flush()
            await self.db.refresh(db_obj)
        return db_obj
    
    async def get(self, id: str) -> Optional[User]:
        result = await self.db.execute(select(User).where(User.id == id))
        return result.scalars().first()
    
    async def get_by_email(self, email: str) -> Optional[User]:
        result = await self.db.execute(select(User).where(User.email == email))
        return result.scalars().first()
    
    async def update(self, id: str, obj_in: Dict[str, Any], commit: bool = True) -> Optional[User]:
        logger.info(f"UserRepository.update: Entered for user_id: {id}")
        
        result = await self.db.execute(select(User).where(User.id == id))
        db_obj = result.scalars().first()
        
        if not db_obj:
            logger.warning(f"UserRepository.update: User {id} not found in DB. Returning None.")
            return None

        logger.info(f"UserRepository.update: User {id} FOUND. Processing update.")
        data_to_set = obj_in.copy()

        if "meta_data" in data_to_set:
            logger.info(f"UserRepository.update: USER {id} - 'meta_data' found in input. Processing.")
            incoming_meta_data = data_to_set.pop("meta_data")
            
            if db_obj.meta_data is not None:
                logger.info(f"UserRepository.update: USER {id}, Current DB meta_data type: {type(db_obj.meta_data)}")
            else:
                logger.info(f"UserRepository.update: USER {id}, Current DB meta_data is None.")

            logger.info(f"UserRepository.update: USER {id}, Incoming meta_data type: {type(incoming_meta_data)}")

            current_db_meta = db_obj.meta_data.copy() if isinstance(db_obj.meta_data, dict) else {}
            
            if isinstance(incoming_meta_data, dict):
                current_db_meta.update(incoming_meta_data)
            else:
                logger.warning(f"UserRepository.update: USER {id}, incoming_meta_data is not a dict (type: {type(incoming_meta_data)}). Not merging.")

            db_obj.meta_data = current_db_meta
            flag_modified(db_obj, "meta_data")
            logger.info(f"UserRepository.update: USER {id}, meta_data prepared for commit. Type: {type(db_obj.meta_data)}")
        else:
            logger.info(f"UserRepository.update: USER {id} - 'meta_data' NOT found in input.")

        for key, value in data_to_set.items():
            logger.info(f"UserRepository.update: USER {id}, setting field {key}")
            setattr(db_obj, key, value)
        
        if "updated_at" not in obj_in:
            db_obj.updated_at = datetime.utcnow()

        if commit:
            logger.info(f"UserRepository.update: USER {id}, Committing changes.")
            await self.db.commit()
            await self.db.refresh(db_obj)
            final_meta_data_type = type(db_obj.meta_data) if db_obj else 'User object is None after refresh'
            logger.info(f"UserRepository.update: USER {id}, Commit and refresh DONE. Final meta_data type: {final_meta_data_type}")
        else:
            logger.info(f"UserRepository.update: USER {id}, Flushing changes (commit=False).")
            await self.db.flush()
            await self.db.refresh(db_obj)
            final_meta_data_type_flush = type(db_obj.meta_data) if db_obj else 'User object is None after refresh'
            logger.info(f"UserRepository.update: USER {id}, Flush and refresh DONE. Final meta_data type: {final_meta_data_type_flush}")
            
        return db_obj
    
    async def delete(self, id: str, commit: bool = True) -> bool:
        result = await self.db.execute(select(User).where(User.id == id))
        db_obj = result.scalars().first()
        if db_obj:
            db_obj.is_active = False
            db_obj.updated_at = datetime.utcnow()
            if commit:
                await self.db.commit()
            else:
                await self.db.flush()
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
        user = await self.get(user_id)
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
                        await self.update(user_id, {"trieve_dataset_id": dataset_id}, commit=True)
                        logger.info(f"Created Trieve dataset {dataset_id} for user {user_id}")
                        return dataset_id
                else:
                    logger.error(f"Failed to create Trieve dataset: {response.status_code} - {response.text}")
                    
        except Exception as e:
            logger.error(f"Error creating Trieve dataset for user {user_id}: {str(e)}")
            
        return None

class ConversationRepository(BaseRepository):
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, obj_in: Dict[str, Any], commit: bool = True) -> Conversation:
        db_obj = Conversation(
            id=obj_in.get("id", str(uuid4())),
            user_id=obj_in["user_id"],
            title=obj_in.get("title", "New Conversation"),
            meta_data=obj_in.get("meta_data", {})
        )
        self.db.add(db_obj)
        if commit:
            await self.db.commit()
            await self.db.refresh(db_obj)
        else:
            await self.db.flush()
            await self.db.refresh(db_obj)
        return db_obj

    async def get(self, id: str) -> Optional[Conversation]:
        stmt = select(Conversation).options(selectinload(Conversation.messages)).where(Conversation.id == id)
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def get_by_user(self, user_id: str) -> List[Conversation]:
        stmt = (
            select(Conversation)
            .options(selectinload(Conversation.messages))
            .where(Conversation.user_id == user_id, Conversation.is_active == True)
            .order_by(Conversation.updated_at.desc())
        )
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def update(self, id: str, obj_in: Dict[str, Any], commit: bool = True) -> Optional[Conversation]:
        result = await self.db.execute(select(Conversation).where(Conversation.id == id))
        db_obj = result.scalars().first()
        
        if db_obj:
            for key, value in obj_in.items():
                setattr(db_obj, key, value)
            
            if "updated_at" not in obj_in:
                db_obj.updated_at = datetime.utcnow()

            if commit:
                await self.db.commit()
                await self.db.refresh(db_obj)
            else:
                await self.db.flush()
                await self.db.refresh(db_obj)
        return db_obj

    async def delete(self, id: str, commit: bool = True) -> bool:
        result = await self.db.execute(select(Conversation).where(Conversation.id == id))
        db_obj = result.scalars().first()
        if db_obj:
            db_obj.is_active = False
            db_obj.updated_at = datetime.utcnow()
            if commit:
                await self.db.commit()
            else:
                await self.db.flush()
            return True
        return False

class MessageRepository(BaseRepository):
    DEFAULT_LIMIT = 50

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, obj_in: Dict[str, Any], commit: bool = True) -> Message:
        message_id = obj_in.get("id")
        if not message_id:
            # If no ID is provided by frontend (e.g. for assistant messages generated server-side), generate one.
            message_id = str(uuid4())
            logger.info(f"MessageRepository: No ID provided in obj_in. Generated new message ID: {message_id}")
        else:
            logger.info(f"MessageRepository: ID provided in obj_in: {message_id}")

        # --- ADDED LOG ---
        print(f"[MSG_REPO - create] obj_in received: {obj_in}")
        print(f"[MSG_REPO - create] metadata from obj_in: {obj_in.get('metadata')}")
        # --- END ADDED LOG ---

        # Attempt to fetch existing message
        existing_message = await self.get(message_id) # Use the existing get method which logs

        if existing_message:
            logger.info(f"MessageRepository: Message with ID {message_id} found. Updating existing message.")
            # Update existing message
            existing_message.content = obj_in.get("content", existing_message.content)
            existing_message.role = obj_in.get("role", existing_message.role)
            # Merge metadata: Start with existing, then update with new, prioritizing new values
            new_meta_data = existing_message.meta_data.copy() if existing_message.meta_data else {}
            if "metadata" in obj_in and isinstance(obj_in["metadata"], dict):
                new_meta_data.update(obj_in["metadata"])
            existing_message.meta_data = new_meta_data
            # Manually set updated_at if your model doesn't auto-update it
            # existing_message.updated_at = datetime.utcnow() 

            if commit:
                logger.info(f"MessageRepository: About to commit update for message ID {message_id}")
                await self.db.commit()
                logger.info(f"MessageRepository: Successfully committed update for message ID {message_id}")
                await self.db.refresh(existing_message)
                logger.info(f"MessageRepository: Successfully refreshed updated message ID {message_id}")
            else:
                await self.db.flush()
                await self.db.refresh(existing_message)
            return existing_message
        else:
            logger.info(f"MessageRepository: Message with ID {message_id} not found. Creating new message.")
            # Create new message (original logic)
            obj_in["id"] = message_id # Ensure the ID used is stored in obj_in for the model
            logger.info(f"MessageRepository: Attempting to create message. Effective ID to be used: {message_id}. Conversation: {obj_in.get('conversation_id')}, Role: {obj_in.get('role')}, Content preview: {str(obj_in.get('content', ''))[:50]}...")

            db_obj = Message(
                id=message_id,
                conversation_id=obj_in["conversation_id"],
                content=obj_in["content"],
                role=obj_in["role"],
                meta_data=obj_in.get("metadata", {})
            )
            self.db.add(db_obj)
            # --- ADDED LOG ---
            print(f"[MSG_REPO - create] db_obj.meta_data after add and before flush/commit: {db_obj.meta_data}")
            # --- END ADDED LOG ---
            if commit:
                logger.info(f"MessageRepository: About to commit creation of new message ID {message_id}")
                await self.db.commit()
                logger.info(f"MessageRepository: Successfully committed new message ID {message_id}")
                await self.db.refresh(db_obj)
                logger.info(f"MessageRepository: Successfully refreshed new message ID {message_id}")
                # --- ADDED LOG ---
                print(f"[MSG_REPO - create] db_obj.meta_data after commit and refresh: {db_obj.meta_data}")
                # --- END ADDED LOG ---
            else:
                await self.db.flush()
                await self.db.refresh(db_obj)
                # --- ADDED LOG ---
                print(f"[MSG_REPO - create] db_obj.meta_data after flush and refresh (commit=False): {db_obj.meta_data}")
                # --- END ADDED LOG ---
            return db_obj

    async def get(self, id: str) -> Optional[Message]:
        logger.info(f"MessageRepository: Attempting to get message with ID {id}")
        stmt = select(Message).options(selectinload(Message.conversation)).where(Message.id == id)
        result = await self.db.execute(stmt)
        message = result.scalars().first()
        if message:
            logger.info(f"MessageRepository: Found message with ID {id}")
        else:
            logger.info(f"MessageRepository: Message with ID {id} NOT FOUND")
        return message

    async def get_by_conversation(
        self,
        conversation_id: str,
        limit: int = DEFAULT_LIMIT,
        before_message_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        query = select(Message).where(Message.conversation_id == conversation_id)

        if before_message_id:
            before_message_stmt = select(Message).where(Message.id == before_message_id)
            before_message_res = await self.db.execute(before_message_stmt)
            before_message = before_message_res.scalars().first()
            
            if before_message and before_message.created_at is not None:
                    query = query.where(Message.created_at < before_message.created_at)
        
        # Eager load file_attachments and the related file details
        query = query.options(
            selectinload(Message.file_attachments).selectinload(FileAttachment.file)
        )
        query = query.order_by(Message.created_at.desc())
        
        fetch_limit = (limit or self.DEFAULT_LIMIT) + 1
        result = await self.db.execute(query.limit(fetch_limit))
        messages = result.scalars().all()
        
        has_more = len(messages) == fetch_limit
        if has_more:
            messages = messages[:-1]
            
        return {
            "messages": list(reversed(messages)),
            "has_more": has_more
        }

    async def update(self, id: str, obj_in: Dict[str, Any], commit: bool = True) -> Optional[Message]:
        result = await self.db.execute(select(Message).where(Message.id == id))
        db_obj = result.scalars().first()
        if db_obj:
            for key, value in obj_in.items():
                setattr(db_obj, key, value)
            if commit:
                await self.db.commit()
                await self.db.refresh(db_obj)
            else:
                await self.db.flush()
                await self.db.refresh(db_obj)
            return db_obj

    async def delete(self, id: str, commit: bool = True) -> bool:
        result = await self.db.execute(select(Message).where(Message.id == id))
        db_obj = result.scalars().first()
        if db_obj:
            await self.db.delete(db_obj)
            if commit:
                await self.db.commit()
            else:
                await self.db.flush()
            return True
        return False

class FileRepository(BaseRepository):
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create(self, obj_in: Dict[str, Any]) -> File:
        # --- DUPLICATE CHECK LOGIC ---
        # When called from /files/metadata endpoint, obj_in is the 'create_payload'
        # create_payload = { "id": ..., "user_id": metadata_from_local['user_id'], ..., "meta_data": metadata_from_local }
        # metadata_from_local = { "file_id": ..., "user_id": ..., "file_hash": ... }

        user_id_for_check = obj_in.get("user_id") # This gets create_payload['user_id']
        
        # The actual dictionary containing 'file_hash' is in obj_in['meta_data']
        actual_metadata_payload_containing_hash = obj_in.get("meta_data", {}) 
        file_hash_for_check = None

        if isinstance(actual_metadata_payload_containing_hash, dict):
            file_hash_for_check = actual_metadata_payload_containing_hash.get("file_hash")

        logger.info(f"FileRepository.create: Initial obj_in for create: {obj_in}")
        logger.info(f"FileRepository.create: For duplicate check - user_id_for_check='{user_id_for_check}', actual_metadata_payload_containing_hash='{actual_metadata_payload_containing_hash}', extracted file_hash_for_check='{file_hash_for_check}'")

        if user_id_for_check and file_hash_for_check:
            logger.info(f"FileRepository.create: Calling get_by_user_and_hash with user_id='{user_id_for_check}', file_hash='{file_hash_for_check}'.")
            existing_file = await self.get_by_user_and_hash(user_id_for_check, file_hash_for_check)
            logger.info(f"FileRepository.create: Result of get_by_user_and_hash: {existing_file}")
            if existing_file:
                logger.info(f"FileRepository.create: Duplicate found. Returning existing file ID: {existing_file.id}.")
                return existing_file
        else:
            logger.info(f"FileRepository.create: Skipped duplicate check. user_id_for_check='{user_id_for_check}', file_hash_for_check='{file_hash_for_check}'.")
        
        logger.info(f"FileRepository.create: No duplicate found or check skipped. Proceeding to create new File object.")
        # meta_data_to_be_saved is obj_in.get('meta_data', {}) which is actual_metadata_payload_containing_hash
        meta_data_to_be_saved = obj_in.get('meta_data', {})
        
        # --- CORRECTED LINTING ERROR IN LOG --- 
        log_file_id = obj_in.get("id", "generated_uuid")
        log_user_id = obj_in.get("user_id")
        log_filename = obj_in.get("filename")
        logger.info(f"FileRepository.create: About to create File object. ID='{log_file_id}', UserID='{log_user_id}', Filename='{log_filename}'. meta_data_to_be_saved: {meta_data_to_be_saved}")
        # --- END CORRECTION ---

        db_obj = File(
            id=obj_in.get("id", str(uuid4())),
            user_id=obj_in["user_id"], # Should be from create_payload['user_id']
            filename=obj_in["filename"], # Should be from create_payload['filename']
            file_type=obj_in["file_type"],
            file_size=obj_in["file_size"],
            storage_path=obj_in["storage_path"],
            is_processed=obj_in.get("is_processed", False),
            vector_id=obj_in.get("vector_id"),
            meta_data=meta_data_to_be_saved # This saves actual_metadata_payload_containing_hash (with file_hash) into File.meta_data
        )
        self.db.add(db_obj)
        # Log the meta_data just before commit for the created/updated object
        logger.info(f"FileRepository.create: FINAL meta_data to be saved for file ID '{db_obj.id}': {db_obj.meta_data}")
        await self.db.commit()
        await self.db.refresh(db_obj)
        return db_obj
    
    async def get(self, id: str) -> Optional[File]:
        result = await self.db.execute(select(File).where(File.id == id))
        return result.scalars().first()
    
    async def get_by_user(self, user_id: str) -> List[File]:
        result = await self.db.execute(select(File).where(File.user_id == user_id))
        return result.scalars().all()
    
    async def get_by_user_and_hash(self, user_id: str, file_hash: str) -> Optional[File]:
        logger.info(f"FileRepository.get_by_user_and_hash: Received user_id='{user_id}', file_hash='{file_hash}'") # Log input params
        # Query for a file with the same user_id and file_hash in meta_data
        stmt = select(File).where(
            File.user_id == user_id,
            File.meta_data["file_hash"].cast(Text) == file_hash
        )
        result = await self.db.execute(stmt)
        all_found = result.scalars().all() # Get all results
        count = len(all_found)
        logger.info(f"FileRepository.get_by_user_and_hash: Query found {count} records.") # Log count
        return all_found[0] if count > 0 else None # Return first if found, else None
    
    async def update(self, id: str, obj_in: Dict[str, Any]) -> File:
        db_obj = await self.get(id)
        if db_obj:
            # Directly iterate and set attributes.
            # The cloud endpoint 'update_file_metadata' already ensures that 
            # obj_in["meta_data"] is the fully merged metadata.
            for key, value in obj_in.items():
                setattr(db_obj, key, value)
            
            # Ensure updated_at is set (if not already handled by the model default/trigger)
            # db_obj.updated_at = datetime.utcnow() # Add if not auto-managed by your DB model

            await self.db.commit()
            await self.db.refresh(db_obj)
        return db_obj
    
    async def delete(self, id: str) -> bool:
        db_obj = await self.get(id)
        if db_obj:
            await self.db.delete(db_obj)
            await self.db.commit()
            return True
        return False

class AgentLogRepository(BaseRepository):
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create(self, obj_in: Dict[str, Any]) -> AgentLog:
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
        await self.db.commit()
        await self.db.refresh(db_obj)
        return db_obj
    
    async def get(self, id: str) -> Optional[AgentLog]:
        result = await self.db.execute(select(AgentLog).where(AgentLog.id == id))
        return result.scalars().first()
    
    async def get_by_query_id(self, query_id: str) -> List[AgentLog]:
        result = await self.db.execute(select(AgentLog).where(AgentLog.query_id == query_id))
        return result.scalars().all()
    
    async def update(self, id: str, obj_in: Dict[str, Any]) -> AgentLog:
        db_obj = await self.get(id)
        if db_obj:
            for key, value in obj_in.items():
                setattr(db_obj, key, value)
            await self.db.commit()
            await self.db.refresh(db_obj)
        return db_obj
    
    async def delete(self, id: str) -> bool:
        db_obj = await self.get(id)
        if db_obj:
            await self.db.delete(db_obj)
            await self.db.commit()
            return True
        return False

# New repository classes for document processing and RAG

class DocumentRepository(BaseRepository):
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, document_id: str) -> Optional[Document]:
        query = select(Document).where(Document.id == document_id)
        result = await self.db.execute(query)
        return result.scalars().first()
    
    async def get_by_file_id(self, file_id: str) -> Optional[Document]:
        query = select(Document).where(Document.file_id == file_id)
        result = await self.db.execute(query)
        return result.scalars().first()
    
    async def create(self, document_data: Dict[str, Any]) -> Document:
        document = Document(**document_data)
        self.db.add(document)
        await self.db.commit()
        await self.db.refresh(document)
        return document
    
    async def update(self, document_id: str, document_data: Dict[str, Any]) -> Optional[Document]:
        query = sqlalchemy_update_stmt(Document).where(Document.id == document_id).values(**document_data)
        await self.db.execute(query)
        await self.db.commit()
        return await self.get_by_id(document_id)
    
    async def mark_as_processed(self, document_id: str) -> Optional[Document]:
        query = sqlalchemy_update_stmt(Document).where(Document.id == document_id).values(processed=True)
        await self.db.execute(query)
        await self.db.commit()
        return await self.get_by_id(document_id)
    
    async def get_unprocessed_documents(self, limit: int = 10) -> List[Document]:
        query = select(Document).where(Document.processed == False).limit(limit)
        result = await self.db.execute(query)
        return result.scalars().all()

class DocumentChunkRepository(BaseRepository):
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, chunk_id: str) -> Optional[DocumentChunk]:
        query = select(DocumentChunk).where(DocumentChunk.id == chunk_id)
        result = await self.db.execute(query)
        return result.scalars().first()
    
    async def get_by_document_id(self, document_id: str) -> List[DocumentChunk]:
        query = select(DocumentChunk).where(DocumentChunk.document_id == document_id)
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def create(self, chunk_data: Dict[str, Any]) -> DocumentChunk:
        chunk = DocumentChunk(**chunk_data)
        self.db.add(chunk)
        await self.db.commit()
        await self.db.refresh(chunk)
        return chunk
    
    async def create_many(self, chunks_data: List[Dict[str, Any]]) -> List[DocumentChunk]:
        chunks = [DocumentChunk(**data) for data in chunks_data]
        self.db.add_all(chunks)
        await self.db.commit()
        # Refreshing multiple objects created with add_all needs individual handling
        # For simplicity, returning them without refresh, or caller handles refresh if needed.
        return chunks
    
    async def update_vector_id(self, chunk_id: str, vector_id: str) -> Optional[DocumentChunk]:
        query = sqlalchemy_update_stmt(DocumentChunk).where(DocumentChunk.id == chunk_id).values(vector_id=vector_id)
        await self.db.execute(query)
        await self.db.commit()
        return await self.get_by_id(chunk_id)

class SearchQueryRepository(BaseRepository):
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, query_data: Dict[str, Any]) -> SearchQuery:
        query = SearchQuery(**query_data)
        self.db.add(query)
        await self.db.commit()
        await self.db.refresh(query)
        return query
    
    async def get_by_user(self, user_id: str, limit: int = 50) -> List[SearchQuery]:
        query = select(SearchQuery).where(SearchQuery.user_id == user_id).order_by(
            SearchQuery.created_at.desc()
        ).limit(limit)
        result = await self.db.execute(query)
        return result.scalars().all()

class SearchResultRepository(BaseRepository):
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_many(self, results_data: List[Dict[str, Any]]) -> List[SearchResult]:
        results = [SearchResult(**data) for data in results_data]
        self.db.add_all(results)
        await self.db.commit()
        # Similar to DocumentChunkRepository.create_many, refresh is omitted for simplicity
        return results
    
    async def get_by_query_id(self, query_id: str) -> List[SearchResult]:
        query = select(SearchResult).where(SearchResult.search_query_id == query_id).order_by(
            SearchResult.position
        )
        result = await self.db.execute(query)
        return result.scalars().all()

class MemoryRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_entities(self, entities: List[Dict[str, Any]]) -> Dict[str, Any]:
        created = 0
        for entity in entities:
            name = entity["name"]
            db_entity = await self.session.get(MemoryEntity, name)
            if db_entity:
                # Update existing
                db_entity.entity_type = entity["entityType"]
                db_entity.conversation_ref = entity.get("conversation_id")
                db_entity.message_ref = entity.get("message_id")
                db_entity.meta_data = entity.get("meta_data", {})
                db_entity.updated_at = datetime.now()
                # Remove old observations
                await self.session.execute(delete(MemoryObservation).where(MemoryObservation.entity_name == name))
            else:
                db_entity = MemoryEntity(
                    entity_name=name,
                    entity_type=entity["entityType"],
                    conversation_ref=entity.get("conversation_id"),
                    message_ref=entity.get("message_id"),
                    meta_data=entity.get("meta_data", {}),
                    updated_at=datetime.now()
                )
                self.session.add(db_entity)
            # Add observations
            observations = entity.get("observations", [])
            for obs in observations:
                self.session.add(MemoryObservation(entity_name=name, content=obs))
            created += 1
        await self.session.commit()
        return {"status": "success", "created": created}

    async def create_relations(self, relations: List[Dict[str, Any]]) -> Dict[str, Any]:
        created = 0
        for relation in relations:
            rel = MemoryRelation(
                id=str(uuid4()),
                from_entity=relation["from"],
                to_entity=relation["to"],
                relation_type=relation["relationType"]
            )
            self.session.add(rel)
            created += 1
        await self.session.commit()
        return {"status": "success", "created": created}

    async def add_observations(self, observations: List[Dict[str, Any]]) -> Dict[str, Any]:
        count = 0
        for observation_item in observations:
            entity_name = observation_item["entityName"]
            for content in observation_item["contents"]:
                self.session.add(MemoryObservation(entity_name=entity_name, content=content))
                count += 1
        await self.session.commit()
        return {"status": "success", "added": count}

    async def delete_entities(self, entityNames: List[str]) -> Dict[str, Any]:
        count = 0
        relation_count = 0
        for name in entityNames:
            # Delete observations
            await self.session.execute(delete(MemoryObservation).where(MemoryObservation.entity_name == name))
            # Delete relations
            rel_result = await self.session.execute(delete(MemoryRelation).where(or_(MemoryRelation.from_entity == name, MemoryRelation.to_entity == name)))
            relation_count += rel_result.rowcount or 0
            # Delete entity
            result = await self.session.execute(delete(MemoryEntity).where(MemoryEntity.entity_name == name))
            count += result.rowcount or 0
        await self.session.commit()
        return {"status": "success", "deleted": count, "relations_deleted": relation_count}

    async def delete_observations(self, deletions: List[Dict[str, Any]]) -> Dict[str, Any]:
        count = 0
        for deletion in deletions:
            entity_name = deletion["entityName"]
            obs_to_delete = deletion["observations"]
            result = await self.session.execute(
                delete(MemoryObservation).where(
                    and_(
                        MemoryObservation.entity_name == entity_name,
                        MemoryObservation.content.in_(obs_to_delete)
                    )
                )
            )
            count += result.rowcount or 0
        await self.session.commit()
        return {"status": "success", "deleted": count}

    async def delete_relations(self, relations: List[Dict[str, Any]]) -> Dict[str, Any]:
        count = 0
        for relation in relations:
            result = await self.session.execute(
                delete(MemoryRelation).where(
                    and_(
                        MemoryRelation.from_entity == relation["from"],
                        MemoryRelation.to_entity == relation["to"],
                        MemoryRelation.relation_type == relation["relationType"]
                    )
                )
            )
            count += result.rowcount or 0
        await self.session.commit()
        return {"status": "success", "deleted": count}

    async def read_graph(self) -> Dict[str, Any]:
        entities_result = await self.session.execute(select(MemoryEntity))
        entities = entities_result.scalars().all()
        nodes = []
        for entity in entities:
            obs_result = await self.session.execute(
                select(MemoryObservation.content).where(MemoryObservation.entity_name == entity.entity_name).order_by(MemoryObservation.created_at)
            )
            observations = [row[0] for row in obs_result.all()]
            nodes.append({
                "name": entity.entity_name,
                "entityType": entity.entity_type,
                "observations": observations,
                "conversationRef": entity.conversation_ref,
                "messageRef": entity.message_ref,
                "ttl": entity.ttl,
                "meta_data": entity.meta_data,
                "created_at": entity.created_at,
                "updated_at": entity.updated_at,
            })
        rels_result = await self.session.execute(select(MemoryRelation))
        relations = rels_result.scalars().all()
        rels = []
        for rel in relations:
            rels.append({
                "id": str(rel.id),
                "from": rel.from_entity,
                "to": rel.to_entity,
                "relationType": rel.relation_type,
                "created_at": rel.created_at,
            })
        return {"nodes": nodes, "relations": rels}

    async def search_nodes(self, query: str) -> Dict[str, Any]:
        query_lower = query.lower()
        entities_result = await self.session.execute(select(MemoryEntity))
        entities = entities_result.scalars().all()
        nodes = []
        for entity in entities:
            obs_result = await self.session.execute(
                select(MemoryObservation.content).where(MemoryObservation.entity_name == entity.entity_name)
            )
            observations = [row[0] for row in obs_result.all()]
            if (
                query_lower in entity.entity_name.lower() or
                query_lower in entity.entity_type.lower() or
                any(query_lower in obs.lower() for obs in observations)
            ):
                nodes.append({
                    "name": entity.entity_name,
                    "entityType": entity.entity_type,
                    "observations": observations,
                    "conversation_id": entity.conversation_ref,
                    "message_id": entity.message_ref,
                    "meta_data": entity.meta_data
                })
        return {"nodes": nodes}

    async def open_nodes(self, names: List[str]) -> Dict[str, Any]:
        nodes = []
        for name in names:
            entity = await self.session.get(MemoryEntity, name)
            if entity:
                obs_result = await self.session.execute(
                    select(MemoryObservation.content).where(MemoryObservation.entity_name == name).order_by(MemoryObservation.created_at)
                )
                observations = [row[0] for row in obs_result.all()]
                nodes.append({
                    "name": entity.entity_name,
                    "entityType": entity.entity_type,
                    "observations": observations,
                    "conversation_id": entity.conversation_ref,
                    "message_id": entity.message_ref,
                    "meta_data": entity.meta_data
                })
        return {"nodes": nodes}

    async def update_entities(self, entities: List[Dict[str, Any]]) -> Dict[str, Any]:
        updated = 0
        for entity in entities:
            db_entity = await self.session.get(MemoryEntity, entity["name"])
            if db_entity:
                db_entity.entity_type = entity["entityType"]
                db_entity.conversation_ref = entity.get("conversation_id")
                db_entity.message_ref = entity.get("message_id")
                db_entity.meta_data = entity.get("meta_data", {})
                db_entity.updated_at = datetime.now()
                # Remove old observations
                await self.session.execute(delete(MemoryObservation).where(MemoryObservation.entity_name == entity["name"]))
                # Add new observations
                for obs in entity.get("observations", []):
                    self.session.add(MemoryObservation(entity_name=entity["name"], content=obs))
                updated += 1
        await self.session.commit()
        return {"status": "success", "updated": updated}

    async def update_relations(self, relations: List[Dict[str, Any]]) -> Dict[str, Any]:
        updated = 0
        for relation in relations:
            # Find the relation by (from, to, relationType)
            result = await self.session.execute(
                select(MemoryRelation).where(
                    and_(
                        MemoryRelation.from_entity == relation["from"],
                        MemoryRelation.to_entity == relation["to"],
                        MemoryRelation.relation_type == relation["relationType"]
                    )
                )
            )
            rel = result.scalars().first()
            if rel:
                rel.id = relation.get("id", rel.id)
                updated += 1
        await self.session.commit()
        return {"status": "success", "updated": updated} 