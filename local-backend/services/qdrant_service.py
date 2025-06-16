import logging
import os
import uuid
from typing import List, Dict, Any, Optional
from qdrant_client import QdrantClient, models
# Remove immediate import of SentenceTransformer for lazy loading
# from sentence_transformers import SentenceTransformer
from config.settings import settings

logger = logging.getLogger(__name__)

class DirectQdrantService:
    def __init__(self):
        qdrant_url = settings.QDRANT_URL
        api_key = settings.QDRANT_API_KEY
        self.collection_name = settings.QDRANT_COLLECTION_NAME
        self.embedding_model_name = settings.EMBEDDING_MODEL
        self.vector_name = settings.VECTOR_NAME
        
        # Lazy initialization - don't load the heavy model at startup
        self._embedding_model: Optional[Any] = None
        self._model_loading_failed = False

        if not all([qdrant_url, self.collection_name, self.embedding_model_name, self.vector_name]):
            self.client = None
            logger.warning("Qdrant direct service is not configured. Missing required environment variables (QDRANT_URL, QDRANT_COLLECTION_NAME, EMBEDDING_MODEL, VECTOR_NAME).")
            return

        try:
            self.client = QdrantClient(url=qdrant_url, api_key=api_key)
            logger.info("Qdrant client initialized successfully for direct service (model will be loaded on-demand).")
        except Exception as e:
            self.client = None
            logger.error(f"Failed to initialize DirectQdrantService client: {e}", exc_info=True)

    @property
    def embedding_model(self):
        """Lazy load the SentenceTransformer model only when needed"""
        if self._embedding_model is None and not self._model_loading_failed:
            try:
                logger.info(f"Loading SentenceTransformer model '{self.embedding_model_name}' on-demand...")
                from sentence_transformers import SentenceTransformer
                self._embedding_model = SentenceTransformer(self.embedding_model_name)
                logger.info(f"SentenceTransformer model '{self.embedding_model_name}' loaded successfully.")
            except Exception as e:
                self._model_loading_failed = True
                logger.error(f"Failed to load SentenceTransformer model: {e}", exc_info=True)
                return None
        return self._embedding_model

    async def store_chunks(self, chunks: List[str], metadatas: List[Dict[str, Any]]) -> dict:
        if not self.client:
            msg = "DirectQdrantService client is not available."
            logger.error(msg)
            return {"status": "error", "message": msg}
            
        # This will trigger lazy loading of the model
        if not self.embedding_model:
            msg = "DirectQdrantService embedding model is not available."
            logger.error(msg)
            return {"status": "error", "message": msg}

        if len(chunks) != len(metadatas):
            msg = f"Mismatch between number of chunks ({len(chunks)}) and metadatas ({len(metadatas)})."
            logger.error(msg)
            return {"status": "error", "message": msg}
        
        try:
            logger.info(f"Starting to process {len(chunks)} chunks for storage.")
            # 1. Create embeddings for all chunks in a batch
            embeddings = self.embedding_model.encode(chunks, show_progress_bar=False).tolist()
            logger.info(f"Successfully created {len(embeddings)} embeddings.")
            
            # 2. Prepare points for Qdrant
            points = []
            for i in range(len(chunks)):
                payload = {"document": chunks[i], "metadata": metadatas[i]}
                point = models.PointStruct(
                    id=str(uuid.uuid4()),
                    vector={self.vector_name: embeddings[i]},
                    payload=payload,
                )
                points.append(point)
            
            logger.info(f"Prepared {len(points)} points for upsertion.")
            
            # 3. Upsert points to Qdrant in a single batch
            operation_info = self.client.upsert(
                collection_name=self.collection_name,
                wait=True,
                points=points
            )
            
            logger.info(f"Successfully upserted {len(points)} points to Qdrant. Status: {operation_info.status}")
            return {"status": "success", "message": f"Stored {len(points)} chunks successfully."}

        except Exception as e:
            logger.error(f"Error storing chunks in Qdrant: {e}", exc_info=True)
            return {"status": "error", "message": str(e)}

# Singleton instance for direct Qdrant access
direct_qdrant_service = DirectQdrantService() 