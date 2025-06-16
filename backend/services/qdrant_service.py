import logging
from qdrant_client import QdrantClient, models
from config.settings import settings

logger = logging.getLogger(__name__)

class QdrantService:
    def __init__(self):
        # Check if necessary Qdrant settings are available
        if not all([hasattr(settings, 'QDRANT_URL'), hasattr(settings, 'QDRANT_COLLECTION_NAME')]):
            self.client = None
            logger.warning("Qdrant settings (QDRANT_URL, QDRANT_COLLECTION_NAME) not configured. QdrantService will be disabled.")
            return

        try:
            self.client = QdrantClient(
                url=settings.QDRANT_URL,
                api_key=getattr(settings, 'QDRANT_API_KEY', None), # Handles optional API key
                timeout=20,
            )
            self.collection_name = settings.QDRANT_COLLECTION_NAME
            logger.info("QdrantService initialized successfully.")
        except Exception as e:
            self.client = None
            logger.error(f"Failed to initialize Qdrant client: {e}", exc_info=True)

    async def delete_documents_by_file_id(self, file_id: str) -> dict:
        if not self.client:
            logger.warning("Qdrant client not initialized. Cannot delete documents.")
            return {"status": "error", "message": "Qdrant client not initialized."}

        try:
            logger.info(f"Attempting to delete points from Qdrant for file_id: {file_id} in collection: {self.collection_name}")
            
            response = await self.client.delete(
                collection_name=self.collection_name,
                points_selector=models.FilterSelector(
                    filter=models.Filter(
                        must=[
                            models.FieldCondition(
                                key="metadata.file_id",
                                match=models.MatchValue(value=file_id),
                            )
                        ]
                    )
                ),
            )
            
            logger.info(f"Qdrant deletion response for file_id {file_id}: {response}")

            if response.status in [models.UpdateStatus.COMPLETED, models.UpdateStatus.ACKNOWLEDGED]:
                logger.info(f"Successfully initiated deletion for file_id {file_id}. Operation status: {response.status}")
                return {"status": "success", "operation_id": response.operation_id, "operation_status": str(response.status)}
            else:
                logger.error(f"Qdrant delete operation did not complete successfully for file_id {file_id}. Status: {response.status}")
                return {"status": "error", "message": "Qdrant delete operation did not complete successfully.", "response": str(response)}

        except Exception as e:
            logger.error(f"Error deleting documents from Qdrant for file_id {file_id}: {e}", exc_info=True)
            return {"status": "error", "message": str(e)}

    # The following methods are handled by the local-backend and are not implemented here.
    async def store_document(self, *args, **kwargs):
        raise NotImplementedError("store_document is handled by the local backend (Electron app).")
    async def search_documents(self, *args, **kwargs):
        raise NotImplementedError("search_documents is handled by the local backend (Electron app).")
    async def health_check(self, *args, **kwargs):
        raise NotImplementedError("health_check is handled by the local backend (Electron app).")

# Create a singleton instance of the service
qdrant_service = QdrantService() 