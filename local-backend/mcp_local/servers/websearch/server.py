#!/usr/bin/env python3
"""
WebSearch MCP Server
Provides a MCP server that integrates with Google Search API to perform web searches.
"""

import asyncio
import os
import json
import logging
import sys
from typing import Dict, Any, List

import httpx
from mcp.server.fastmcp import Context, FastMCP

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration from environment variables
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")
GOOGLE_CSE_ID = os.environ.get("GOOGLE_CSE_ID", "")
MAX_RESULTS = int(os.environ.get("MAX_RESULTS", "5"))

# Validate configuration
if not GOOGLE_API_KEY:
    logger.warning("GOOGLE_API_KEY not set. Web search functionality will be limited.")
if not GOOGLE_CSE_ID:
    logger.warning("GOOGLE_CSE_ID not set. Web search functionality will be limited.")

class GoogleSearchClient:
    """Client for interacting with Google Custom Search API."""
    
    def __init__(self, api_key: str, cse_id: str):
        self.api_key = api_key
        self.cse_id = cse_id
        self.base_url = "https://www.googleapis.com/customsearch/v1"
    
    async def search(self, query: str, num_results: int = 5) -> List[Dict[str, Any]]:
        """
        Perform a Google search and return results.
        
        Args:
            query: Search query string
            num_results: Number of results to return (max 10)
            
        Returns:
            List of search result items
        """
        if not self.api_key or not self.cse_id:
            logger.error("Google Search API credentials not configured")
            return [{"error": "Google Search API credentials not configured"}]
        
        params = {
            "key": self.api_key,
            "cx": self.cse_id,
            "q": query,
            "num": min(num_results, 10)  # Google API limits to 10 max results per request
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(self.base_url, params=params)
                response.raise_for_status()
                data = response.json()
                
                if "items" not in data:
                    logger.warning(f"No search results found for query: {query}")
                    return []
                
                results = []
                for item in data["items"]:
                    result = {
                        "title": item.get("title", ""),
                        "link": item.get("link", ""),
                        "snippet": item.get("snippet", ""),
                        "displayLink": item.get("displayLink", "")
                    }
                    results.append(result)
                
                return results
                
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error during Google search: {e}")
            return [{"error": f"HTTP error: {e.response.status_code}"}]
        except httpx.RequestError as e:
            logger.error(f"Request error during Google search: {e}")
            return [{"error": f"Request error: {str(e)}"}]
        except Exception as e:
            logger.error(f"Unexpected error during Google search: {e}")
            return [{"error": f"Unexpected error: {str(e)}"}]

class WebSearchServer(FastMCP):
    """MCP Server for web search capabilities using FastMCP framework."""
    
    def __init__(self, api_key: str = GOOGLE_API_KEY, cse_id: str = GOOGLE_CSE_ID, name: str = "websearch"):
        """Initialize the WebSearch server."""
        # Initialize FastMCP with server name
        super().__init__(name=name)
        
        # Create search client
        self.search_client = GoogleSearchClient(api_key, cse_id)
        logger.info(f"WebSearchServer initialized with Google API key and CSE ID")
        
        # Set up tools
        self.setup_tools()
    
    def setup_tools(self):
        """Set up the tools for this server."""
        
        async def search(ctx: Context, query: str, num_results: int = MAX_RESULTS) -> List[Dict[str, Any]]:
            """
            Search the web using Google Search API.
            
            Args:
                ctx: Request context
                query: Search query string
                num_results: Number of results to return (default: 5, max: 10)
                
            Returns:
                List of search results with titles, snippets, and links
            """
            await ctx.debug(f"Searching for: {query}")
            logger.info(f"Executing web search for query: {query}, num_results: {num_results}")
            
            if not query:
                logger.warning("Search query is empty")
                return [{"error": "Query parameter is required"}]
            
            results = await self.search_client.search(query, num_results)
            return results
        
        # Register tools with predictable names (following Qdrant pattern)
        self.add_tool(
            search,
            name="websearch-search",  # Use consistent fully-qualified name
            description="Search the web using Google Search API. Returns a list of relevant search results including titles, snippets, and links. Use fetch to retrieve content from URLs."
        )

# Create a simple server instance
mcp = WebSearchServer(name="websearch")

# Simple entry point that matches Qdrant\'s pattern
# if __name__ == "__main__":
#     logger.info("Starting WebSearch MCP server")
#     try:
#         # Use the simplest pattern for running the server
#         asyncio.run(mcp.run(transport="stdio"))
#     except RuntimeError as e:
#         if "Already running" in str(e):
#             # Handle the case when there\'s already a running event loop
#             logger.warning("Asyncio event loop already running, using existing loop")
#             loop = asyncio.get_event_loop()
#             loop.run_until_complete(mcp.run(transport="stdio"))
#         else:
#             logger.error(f"Error starting server: {e}")
#             sys.exit(1)
#     except Exception as e:
#         logger.error(f"Error in main: {e}")
#         sys.exit(1)

def main():
    """Entry point for the WebSearch MCP server script."""
    logger.info("Starting WebSearch MCP server via main()")
    try:
        # Use the simplest pattern for running the server
        asyncio.run(mcp.run(transport="stdio"))
    except RuntimeError as e:
        if "Already running" in str(e):
            # Handle the case when there's already a running event loop
            logger.warning("Asyncio event loop already running, using existing loop")
            loop = asyncio.get_event_loop()
            loop.run_until_complete(mcp.run(transport="stdio"))
        else:
            logger.error(f"Error starting server: {e}")
            sys.exit(1)
    except Exception as e:
        logger.error(f"Error in main: {e}")
        sys.exit(1) 

if __name__ == "__main__":
    main() 