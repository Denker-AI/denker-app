import json
import logging
from typing import List

from mcp.server.fastmcp import Context, FastMCP

from .embeddings.factory import create_embedding_provider
from .qdrant import Entry, Metadata, QdrantConnector
from .settings import (
    EmbeddingProviderSettings,
    QdrantSettings,
    ToolSettings,
)

logger = logging.getLogger(__name__)


# FastMCP is an alternative interface for declaring the capabilities
# of the server. Its API is based on FastAPI.
class QdrantMCPServer(FastMCP):
    """
    A MCP server for Qdrant.
    """

    def __init__(
        self,
        tool_settings: ToolSettings,
        qdrant_settings: QdrantSettings,
        embedding_provider_settings: EmbeddingProviderSettings,
        name: str = "mcp-server-qdrant",
    ):
        self.tool_settings = tool_settings
        self.qdrant_settings = qdrant_settings
        self.embedding_provider_settings = embedding_provider_settings

        self.embedding_provider = create_embedding_provider(embedding_provider_settings)
        self.qdrant_connector = QdrantConnector(
            qdrant_settings.location,
            qdrant_settings.api_key,
            qdrant_settings.collection_name,
            self.embedding_provider,
            qdrant_settings.local_path,
        )

        super().__init__(name=name)

        self.setup_tools()

    def format_entry(self, entry: Entry) -> str:
        """
        Feel free to override this method in your subclass to customize the format of the entry.
        """
        entry_metadata = json.dumps(entry.metadata) if entry.metadata else ""
        return f"<entry><content>{entry.content}</content><metadata>{entry_metadata}</metadata></entry>"

    def setup_tools(self):
        async def store(
            ctx: Context,
            information: str,
            collection_name: str,
            # The `metadata` parameter is defined as non-optional, but it can be None.
            # If we set it to be optional, some of the MCP clients, like Cursor, cannot
            # handle the optional parameter correctly.
            metadata: Metadata = None,
            user_id: str = None,
        ) -> str:
            """
            Store some information in Qdrant.
            :param ctx: The context for the request.
            :param information: The information to store.
            :param metadata: JSON metadata to store with the information, optional.
            :param collection_name: The name of the collection to store the information in, optional. If not provided,
                                    the default collection is used.
            :param user_id: The user ID to associate with this entry for security filtering. If not provided, will attempt to get from environment.
            :return: A message indicating that the information was stored.
            """
            # Auto-get user_id from environment if not provided
            if not user_id:
                import os
                user_id = os.environ.get("DENKER_CURRENT_USER_ID")
                if not user_id:
                    await ctx.debug("WARNING: No user_id provided and DENKER_CURRENT_USER_ID not set - this is a security risk!")
                    
            await ctx.debug(f"Storing information {information} in Qdrant for user {user_id}")

            entry = Entry(content=information, metadata=metadata)

            await self.qdrant_connector.store(entry, collection_name=collection_name, user_id=user_id)
            if collection_name:
                return f"Remembered: {information} in collection {collection_name}"
            return f"Remembered: {information}"

        async def store_with_default_collection(
            ctx: Context,
            information: str,
            metadata: Metadata = None,
            user_id: str = None,
        ) -> str:
            return await store(
                ctx, information, self.qdrant_settings.collection_name, metadata, user_id
            )

        async def find(
            ctx: Context,
            query: str,
            collection_name: str,
            user_id: str = None,
        ) -> List[str]:
            """
            Find memories in Qdrant.
            :param ctx: The context for the request.
            :param query: The query to use for the search.
            :param collection_name: The name of the collection to search in, optional. If not provided,
                                    the default collection is used.
            :param user_id: The user ID to filter results by for security. If not provided, will attempt to get from environment.
            :return: A list of entries found.
            """
            # Auto-get user_id from environment if not provided
            if not user_id:
                import os
                user_id = os.environ.get("DENKER_CURRENT_USER_ID")
                if not user_id:
                    await ctx.debug("WARNING: No user_id provided and DENKER_CURRENT_USER_ID not set - this is a security risk!")
                    
            await ctx.debug(f"Finding results for query {query} for user {user_id}")
            if collection_name:
                await ctx.debug(
                    f"Overriding the collection name with {collection_name}"
                )

            entries = await self.qdrant_connector.search(
                query,
                collection_name=collection_name,
                limit=self.qdrant_settings.search_limit,
                user_id=user_id,
            )
            if not entries:
                return [f"No information found for the query '{query}'"]
            content = [
                f"Results for the query '{query}'",
            ]
            for entry in entries:
                content.append(self.format_entry(entry))
            return content

        async def find_with_default_collection(
            ctx: Context,
            query: str,
            user_id: str = None,
        ) -> List[str]:
            return await find(ctx, query, self.qdrant_settings.collection_name, user_id)

        # Register the tools depending on the configuration

        if self.qdrant_settings.collection_name:
            self.add_tool(
                find_with_default_collection,
                name="qdrant-find",
                description=self.tool_settings.tool_find_description,
            )
        else:
            self.add_tool(
                find,
                name="qdrant-find",
                description=self.tool_settings.tool_find_description,
            )

        if not self.qdrant_settings.read_only:
            # Those methods can modify the database

            if self.qdrant_settings.collection_name:
                self.add_tool(
                    store_with_default_collection,
                    name="qdrant-store",
                    description=self.tool_settings.tool_store_description,
                )
            else:
                self.add_tool(
                    store,
                    name="qdrant-store",
                    description=self.tool_settings.tool_store_description,
                )
