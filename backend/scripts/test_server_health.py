#!/usr/bin/env python3
"""
MCP Server Health Check Script

This script tests the health of all configured MCP servers, including:
- qdrant
- fetch
- websearch
- filesystem
- quickchart-server
- document-loader
- markdown-editor

Usage:
    python test_server_health.py
"""

import asyncio
import logging
import os
import sys
import json
from typing import Dict, Any

# Add the parent directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Now we can import from the backend directory
from services.health_checks import mcp_health_service

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("server-health-check")

async def main():
    """Run health checks for all MCP servers"""
    logger.info("Starting MCP server health checks...")
    
    # Initialize the MCP health service
    initialized = await mcp_health_service.initialize()
    if not initialized:
        logger.error("Failed to initialize MCP health service")
        return False
        
    # Run all health checks
    health_status = await mcp_health_service.check_all_health()
    
    # Pretty print the results
    logger.info("\n" + "=" * 40)
    logger.info("MCP SERVER HEALTH CHECK RESULTS")
    logger.info("=" * 40)
    
    # Format results as a table
    server_status = []
    for server, is_healthy in health_status.items():
        if server in ["error", "status", "initialization_failed", "mcp_available"]:
            continue
            
        status_text = "✅ HEALTHY" if is_healthy else "❌ UNHEALTHY"
        server_status.append((server, status_text))
    
    # Sort servers alphabetically
    server_status.sort(key=lambda x: x[0])
    
    # Print each server status
    for server, status in server_status:
        logger.info(f"{server.ljust(20)} {status}")
    
    logger.info("=" * 40)
    
    # Print overall status
    if "status" in health_status:
        overall_status = health_status["status"].upper()
        logger.info(f"Overall Status: {overall_status}")
    
    # Print any errors
    if "error" in health_status:
        logger.error(f"Error: {health_status['error']}")
    
    # Return success based on health status
    return "status" in health_status and health_status["status"] == "healthy"

if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("Health check interrupted")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        sys.exit(1) 