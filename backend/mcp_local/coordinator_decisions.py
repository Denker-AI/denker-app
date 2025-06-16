"""
Coordinator Decisions - Decision-making logic for Coordinator Agent.

This module contains the decision-making functionality, such as determining
which workflow to use (router, orchestrator, or simple) based on user queries.
"""

import json
import logging
import re
from typing import Dict, Any, Optional, List

from mcp_agent.workflows.llm.augmented_llm import RequestParams

logger = logging.getLogger(__name__)

# --- DecisionMaker logic is now handled by the local backend (Electron app) ---
# class DecisionMaker:
#     ... (comment out full class)

class DecisionMaker:
    def __init__(self, *args, **kwargs):
        raise NotImplementedError("DecisionMaker is now handled by the local backend (Electron app).")
    async def get_workflow_decision(self, *args, **kwargs):
        raise NotImplementedError("get_workflow_decision is now handled by the local backend (Electron app).")

# ... existing code ... 