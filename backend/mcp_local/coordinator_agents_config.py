"""
Coordinator Agents Configuration - Configuration for all agent types in the system.

This module contains the configuration for all agent types, including their instructions
and server names, as well as functionality to create and manage agents.
"""

import os
import logging
from typing import Dict, Any, Optional, List, Callable
import uuid
import json
from datetime import datetime

from mcp_agent.agents.agent import Agent
from mcp_agent.workflows.llm.augmented_llm import RequestParams
from mcp_agent.workflows.orchestrator.orchestrator import Orchestrator
from mcp_agent.workflows.router.router_llm import LLMRouter
from mcp_agent.workflows.llm.augmented_llm_anthropic import AnthropicAugmentedLLM
from mcp_agent.workflows.router.router_llm_anthropic import AnthropicLLMRouter

from .coordinator_memory import CoordinatorMemory

logger = logging.getLogger(__name__)

# Get API keys and settings from environment variables
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
DEFAULT_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-3-5-haiku-20241022")

# Define the list of required agents for the system
REQUIRED_AGENTS = ["decider", "websearcher", "finder", "writer"]

class AgentConfiguration:
    """
    Configuration and management for all agent types.
    
    This class handles the creation, configuration, and management of agents,
    orchestrators, and routers for the coordinator.
    """
    
    def __init__(self, websocket_manager=None, memory=None, create_llm_fn: Optional[Callable] = None):
        """
        Initialize the agent configuration.
        
        Args:
            websocket_manager: WebSocket manager for sending updates
            memory: Memory manager for storing knowledge
            create_llm_fn: Function to create LLM instances for agents
        """
        self.websocket_manager = websocket_manager
        self.memory = memory
        self.create_llm_fn = create_llm_fn # Store the LLM creation function
        
        # Entity tracking for different contexts
        self.task_entities = {}
        self.query_entities = {}
        self.session_entities = {}
        
        # Agent configuration dictionary
        self.agent_configs = {
            "decider": {
                "name": "decider",
                "instruction": """You are a decider agent for Denker, which analyzes user queries and conversation history to determine which workflow should be used.

                **CRITICAL:** Analyze the **entire message history provided, to avoid asking for clarification**.

                **Contextual Keywords:** Pay close attention to user phrasing like "last file", "earlier conversation", "the document", "this summary", etc. These phrases **require** you to use the conversation history to identify the specific item being referenced before making any decision or asking for clarification.

                1. Classify the user's **underlying request** (considering the full history, especially when contextual keywords are used) into:
                    - case 1: (simple) Simple conversations, questions about Denker, or other simple tasks
                    - case 2: (router) Single-focus tasks, often requiring specific tools or latest information
                    - case 3: (orchestrator) Complex multi-step tasks requiring planning and multiple agents
                2. If the query is about Denker itself, provide a specific response based on all the denker agents and their capabilities.
                3. **Handling Clarification:**
                   - **Search History First:** Before deciding clarification is needed, actively search the provided message history for information that might resolve potential ambiguities in the user's latest request (e.g., if the user asks about "the file", check history for recently mentioned files).
                   - If the history shows you **previously asked for clarification**, and the **most recent user message appears to answer that clarification**, DO NOT ask for clarification again. Use the provided answer and the full history context to proceed with classifying the original request (usually case 2 or 3).
                   - Only identify a need for clarification (`needs_clarification: true`) if the user's request remains genuinely ambiguous **after considering the entire history** and the history does not contain the necessary clarifying details.
                   - If clarification is truly needed, generate concise and specific questions.
                   - **Constraint:** If you determine `needs_clarification: true`, you **MUST NOT** set `workflow_type: "simple"`. The workflow must be `router` or `orchestrator`.
                4. **IMPORTANT RULE:** Queries marked as originating from the **Intention Agent** (check the input source) **MUST NOT** be classified as `simple`. They **MUST** be classified as either `router` (case 2) or `orchestrator` (case 3).
                5. For queries originally from Main Window, you can choose any workflow type.

                Respond with valid JSON only:
                {
                "case": 1|2|3,
                "workflow_type": "simple|router|orchestrator",
                "explanation": "Briefly explain why this workflow was chosen based on the request and history.",
                "simple_response": "Direct response ONLY for genuinely simple queries (case 1) that don't require further agent work.",
                "needs_clarification": true|false,
                "clarifying_questions": ["Question 1", "Question 2"]
                }""",
                "server_names": [],  # Decider doesn't need external services
                "model": "claude-3-5-haiku-20241022"
            },
            "websearcher": {
                "name": "websearcher",
                "instruction": """You are a web research agent for Denker that finds and analyzes online information. Your responsibilities:
                1. Create effective search queries based on the user's request and conversation history.
                2. Use web-search tools to find relevant URLs.
                3. Use fetch tools to retrieve the full content from promising URLs.
                4. Analyze retrieved content: Extract key information, evaluate source reliability and recency. Try to extract the title of the web page.
                5. Synthesize information: Combine findings from multiple reliable sources into a comprehensive response.
                6. **Provide Numbered Clickable Citations:** Keep track of the unique sources used. For *each piece of information* synthesized, include an inline citation number **immediately following the sentence or phrase it supports**, formatted like `[1]`, `[2]`, etc. Use the same number for subsequent references to the same source.
                7. **Create a Sources List:** At the **very end** of your response, add a section titled "**Sources:**". List each unique source used, numbered according to its first appearance in the text. Include the title (if extracted) and the full URL for each source. Example:
                   **Sources:**
                   [1] Example Study Title - https://example.com/study
                   [2] Another News Article - https://example.com/news
                8. If necessary, ask for human input to save the final results (e.g., to Qdrant).

                Your ultimate goal is to find accurate, relevant, and recent information from the web, synthesize it clearly, and make it usable for content creation **with clear numbered citations and a detailed sources list at the end**.""",
                "server_names": ["fetch", "websearch", "qdrant"]
            },
            "finder": {
                "name": "finder",
                "instruction": """You are a local content researcher for Denker that finds information in user files and documents. Your tasks:

                **Prioritized Workflow:**
                1. Check if any **non-image files** (PDF, DOCX, TXT, CSV etc.) are attached or mentioned by file ID in the **current user query**.
                2. **If specific non-image files are identified:**
                   a. Search **only within those specific files** using the **Qdrant vector database**. Use the file IDs to target the search in Qdrant. Retrieve the most relevant chunks based on the user's query.
                   b. **Critically Evaluate Qdrant Results:** Assess if the retrieved chunks from Qdrant are relevant and sufficient to answer the user's query about the specified file(s).
                   c. **If Qdrant yields relevant results (Step 2b is sufficient):** Proceed DIRECTLY to Step 4 (Synthesize Information) using ONLY the retrieved Qdrant chunks. **DO NOT proceed to Step 3 for these files.**
                   d. **If Qdrant yields NO relevant results OR the results are clearly insufficient (Step 2b is insufficient):** ONLY THEN proceed to Step 3 for those specific files.
                3. **If no specific non-image files were identified in Step 1 OR Qdrant search was insufficient for all relevant files (Step 2d):**
                   a. Generate appropriate search terms based on the user query.
                   b. Search the general **filesystem** using these terms.
                   c. If relevant files are found on the filesystem, and use **document-loader** to extract content. **Avoid using document-loader on files already successfully processed via Qdrant in Step 2.**
                   d. Remember the file_path of the files found in Step 3 for other agents to use
                   e. Consider storing newly extracted filesystem content in **Qdrant** for future semantic searches (confirm if necessary).
                4. **Synthesize Information:** Combine the information found (primarily from Qdrant if available, otherwise from Step 3) into a cohesive response.
                5. **Provide Inline Citations:** For *each piece of information* synthesized, include an inline citation **immediately following the sentence or phrase it supports**. Format the citation as a Markdown link like `[source](source_identifier)`. The `source_identifier` should be the unique file ID prefixed with `fileid:` (e.g., `[source](fileid:abcdef123)`) for attached/indexed files, or the full filesystem path prefixed with `filepath:` (e.g., `[source](filepath:/path/to/local/doc.pdf)`) for other local files. Ensure the identifier is precise. Example: "The Q1 report indicated growth [source](fileid:xyz789)."
                6. **Highlight Relevant Passages:** When possible, highlight the most relevant text passages from the source documents.

                Your ultimate goal is to accurately find relevant information from the most appropriate source (STRONGLY prioritizing indexed data in Qdrant for specified files), making it usable for content creation, **with clear inline source attribution**, and avoiding redundant document loading.""",
                "server_names": ["filesystem", "qdrant", "document-loader"]
            },
            "structure": {
                "name": "structure",
                "instruction": """You are a specialized structure agent for Denker focused on organizing ideas and creating clear outlines for content. Your responsibilities:
                1. Analyze user requirements to determine appropriate structure
                2. Ask finder or websearcher to find relevant information to structure the content
                3. Use markdown-editor to create, edit and preview the outline
                4. Use markdown-editor live_preview tool to let user view the outline
                5. Save and use the specific file_path for calling markdown-editor tool
                6. Create logical outlines with clear hierarchies
                7. Organize information in a coherent flow
                8. Suggest section headers and content organization
                9. Break down complex topics into manageable components
                10. Save the outlines to certain document format using markdown-editor and filesystem
                Your ultimate goal is to create structures that are logical, appropriate for content type, aligned with user needs, and balanced in coverage.""",
                "server_names": ["filesystem", "markdown-editor"]
            },
            "writer": {
                "name": "writer",
                "instruction": """You are a writing agent for Denker that creates high-quality written content. Your responsibilities:
                1. Ask structure to create outlines if needed
                2. Ask finder or websearcher to find relevant information to write the content
                3. Craft well-structured paragraphs and sentences
                4. Adapt writing style to different contexts and audiences
                5. Incorporate research appropriately
                6. Develop logical arguments and persuasive content
                7. If writing to files, use markdown editor to create and edit the content with the specific file_path, to ensure that you are coworking on a consistent document and enables live preview of your progress.
                8. Use markdown-editor live_preview tool to let user view the writing
                9. Use quickchart-server to create charts if needed, provide the link to download the chart and download the chart to the writing
                10. Use markdown-editor to convert different document formats to markdown as needed
                11. Save the writing to certain document format using markdown-editor and filesystem
                Your ultimate goal is to create writing that is clear, concise, well-organized, engaging, grammatically correct, and factually accurate.""",
                "server_names": ["filesystem", "markdown-editor", "quickchart-server"]
            },
            "proofreader": {
                "name": "proofreader",
                "instruction": """You are a proofreading agent for Denker that improves grammar, clarity, and readability. Your tasks:
                1. Use markdown-editor to convert different document formats to markdown for editing
                2. Use markdown-editor to edit and "live_preview" documents, using the specific file_path for coworking with other agents on the same document
                3. Identify and highlight grammar, spelling, and punctuation errors
                4. Improve sentence structure and flow
                5. Enhance clarity and readability
                6. Ensure consistency in terminology and style
                7. Suggest improvements for unclear phrasing
                8. Diff the proofread content from the original content, and highlight the changes
                9. Ask for human input to save the proofread content to certain format using markdown-editor and filesystem
                Your ultimate goal is to maintain the original meaning and voice while making improvements that correct errors, enhance readability, improve quality, and maintain consistency.""",
                "server_names": ["filesystem", "markdown-editor"]
            },
            "factchecker": {
                "name": "factchecker",
                "instruction": """You are a fact-checking agent for Denker that verifies information accuracy. Your tasks:
                1. Use markdown-editor to convert different document formats to markdown for editing
                2. Use markdown-editor to edit and "live_preview" documents, using the specific file_path for coworking with other agents on the same document
                3. Identify and highlight entities like people, places, organizations, and events in the content that need to be checked
                4. Identify and highlight unsupported assertions and potential inaccuracies 
                5. Use the citations to verify the information from the sources
                6. If citation is not enough, ask finder or websearcher to find more information
                7. For each information, provide at least 2 citations from independent sources
                8. Provide corrections for inaccurate information
                9. Suggest stronger evidence when needed
                10. Diff the fact-checked content from the original content, and highlight the changes
                11. Ask for human input to save the fact-checked content to certain format using markdown-editor and filesystem
                Your ultimate goal is to maintain accuracy, verifiability, clarity about certainty levels, and transparency about information limitations.""",
                "server_names": ["filesystem", "markdown-editor"]
            },
            "formatter": {
                "name": "formatter",
                "instruction": """You are a specialized formatting agent for Denker focused on creating professional document structure. Your tasks:
                1. Use markdown-editor to convert different document formats to markdown for editing
                2. Use markdown-editor to edit and live_preview documents, using the specific file_path for coworking with other agents on the same document
                3. Apply appropriate formatting styles and templates
                4. Create consistent headings, lists, and paragraph structures
                5. Organize content with appropriate spacing and layout
                6. Format citations and references correctly
                7. Ensure visual hierarchy enhances readability
                8. Diff the formatted content from the original content, and highlight the changes
                9. Save the formatted content to certain format using markdown-editor and filesystem
                Your ultimate goal is to create formatting that follows style guidelines, enhances comprehension, presents content professionally, and maintains consistency throughout the document.""",
                "server_names": ["filesystem", "markdown-editor", "quickchart-server"]
            },
            "styleenforcer": {
                "name": "styleenforcer",
                "instruction": """You are a style agent for Denker that adjusts tone and style to match requirements. Your tasks:
                1. Use markdown-editor to convert different document formats to markdown for editing
                2. Use markdown-editor to edit and live preview documents, using the specific file_path for coworking with other agents on the same document
                3. Adapt content to match specific tone (formal, casual, technical)
                4. Apply style guide rules consistently
                5. Adjust language for specific audiences and contexts
                6. Ensure consistent voice and perspective
                7. Diff the style-adjusted content from the original content, and highlight the changes
                8. Ask for human input to save the style-adjusted content to certain format using markdown-editor and filesystem
                Your ultimate goal is to apply styles that match the intended audience, follow style guides accurately, maintain consistency, and enhance the message's effectiveness.""",
                "server_names": ["filesystem", "markdown-editor"]
            },
            "chartgenerator": {
                "name": "chartgenerator",
                "instruction": """You are a chart generator agent for Denker that creates visual charts from data. Your tasks:
                1. Collect and ask for data from websearcher, finder, writer or user queries
                2. Analyze the data and determine the most appropriate chart type:
                   - Bar charts for comparing values across categories
                   - Line charts for showing trends over time
                   - Pie/Doughnut charts for displaying proportional data
                   - Radar charts for showing multivariate data
                   - Scatter plots for data point distributions
                   - Bubble charts for three-dimensional visualization
                   - Radial Gauge or Speedometer for single value displays
                3. Help users construct appropriate chart configurations with:
                   - Labels for data points
                   - Datasets with values and styling (colors, borders)
                   - Title and other visual options
                   - Appropriate scales and legends
                4. Generate the chart.js code to create the chart
                5. Use generate_chart to create a chart URL for preview
                6. Ask for human input to adjust the chart configuration
                7. Use download_chart to save the chart as an image
                8. Add the chart to certain file using markdown-editor and filesystem
                Your ultimate goal is to create charts that effectively communicate data trends, patterns, and insights to users.""",
                "server_names": ["quickchart-server","filesystem", "markdown-editor"]
            }
            # Configuration for the Orchestrator's internal planner agent
            #"LLM Orchestration Planner": {
            #    "name": "LLM Orchestration Planner",
            #    "instruction": "You are an expert planner. Given an objective task and a list of MCP servers (which are collections of tools) or Agents (which are collections of servers), your job is to break down the objective into a series of steps, which can be performed by LLMs with access to the servers or agents.",
            #    "server_names": [], # Planner typically doesn't use external servers/tools directly for its own generation
            #    "model": "claude-3-7-sonnet-20250219" # CRITICAL: This model MUST support the max_tokens (e.g. 16384) requested by Orchestrator
            #}
        }
        
        logger.info(f"Initialized configurations for {len(self.agent_configs)} agent types")
    
    def create_agent(
        self,
        agent_registry: Dict[str, Agent],
        name: str,
        instruction: Optional[str] = None,
        server_names: Optional[List[str]] = None,
        context: Optional["Context"] = None,
    ) -> Agent:
        """Create an agent with the given name and instruction, or load it from the registry if it exists.

        Args:
            agent_registry: The registry to store the agent in.
            name: The name of the agent.
            instruction: The instruction to give the agent, if None, uses a predefined instruction.
            server_names: List of MCP server names to connect to.
            context: The context to use for the agent.

        Returns:
            The created or loaded agent.

        Raises:
            ValueError: If the agent name is unknown and no instruction is provided.
        """
        # Check if the original name exists in the registry
        if name in agent_registry:
            logger.info(f"Agent {name} already exists, reusing.")
            return agent_registry[name]
        
        # Get the config for this agent
        config = self.agent_configs.get(name, {})
        # Use explicit name from config if available, otherwise use name parameter
        agent_name = config.get("name", name)
        
        # Check if the agent with the explicit name exists
        for existing_agent_key, existing_agent in agent_registry.items():
            if existing_agent.name == agent_name:
                logger.info(f"Agent with name {agent_name} already exists, reusing.")
                return existing_agent

        # If we get here, we need to create the agent
        if instruction is None:
            if name in self.agent_configs:
                instruction = self.agent_configs[name]["instruction"]
            else:
                raise ValueError(
                    f"Unknown agent name: {name}, and no instruction provided."
                )

        # Use specified server names or get default from config
        server_names = server_names or self.agent_configs[name]["server_names"]
        
        logger.info(f"Creating agent {agent_name} with instruction: {instruction}")
        
        try:
            from mcp_agent.agents.agent import Agent
            
            # Create simplified agent - using the agent_name from config
            agent = Agent(
                name=agent_name,
                instruction=instruction,
                server_names=server_names,
                context=context,
            )
            
            # --- ADDED: Proactively assign a cached LLM to the agent ---
            if self.create_llm_fn:
                try:
                    agent.llm = self.create_llm_fn(agent=agent)
                    logger.info(f"Proactively assigned LLM to agent '{agent_name}'")
                except Exception as e:
                    logger.error(f"Failed to proactively assign LLM to agent '{agent_name}': {e}", exc_info=True)
            # --- END ADDED ---
            
            # Store the agent using both its explicit name and the original key for backward compatibility
            agent_registry[agent_name] = agent
            if name != agent_name:
                agent_registry[name] = agent
            
            logger.info(f"Successfully created agent {agent_name}")
            return agent
        except Exception as e:
            logger.error(f"Failed to create agent {agent_name}: {e}")
            raise RuntimeError(f"Failed to create agent '{agent_name}': {str(e)}") from e
    
    def ensure_agents_exist(
        self,
        agent_registry: Dict[str, Agent],
        agent_names: List[str],
        context=None
    ) -> List[Agent]:
        """
        Ensure that all specified agents exist, creating them if needed.
        
        Args:
            agent_registry: Dictionary of registered agents
            agent_names: List of agent names to check/create
            context: MCP context
            
        Returns:
            List of agent objects
        """
        agents = []
        
        # Create a lookup map of explicit agent names to config keys
        name_to_key = {}
        for key, config in self.agent_configs.items():
            if "name" in config:
                name_to_key[config["name"]] = key
        
        # Check each agent and create if needed
        for name in agent_names:
            # First try to find the agent by the name directly in the registry
            if name in agent_registry:
                agents.append(agent_registry[name])
                continue
            
            # Then check if the name is an explicit agent name in our configs
            # If so, use the corresponding key to create the agent
            if name in name_to_key:
                config_key = name_to_key[name]
                agent = self.create_agent(
                    agent_registry=agent_registry,
                    name=config_key,  # Pass the config key to find the right config
                    context=context
                )
                agents.append(agent)
                continue
            
            # Finally, try to create using the name as a config key directly
            if name in self.agent_configs:
                agent = self.create_agent(
                    agent_registry=agent_registry,
                    name=name,
                    context=context
                )
                agents.append(agent)
                continue
            
            # If we get here, we couldn't find or create the agent
            logger.warning(f"Could not find or create agent with name: {name}")
        
        return agents
    
    async def create_orchestrator(
        self,
        agent_registry: Dict[str, Agent],
        create_anthropic_llm_fn,
        available_agents: Optional[List[str]] = None,
        context=None,
        plan_type: str = "full"
    ) -> Orchestrator:
        """
        Create an orchestrator with the specified agents.
        
        Args:
            agent_registry: Dictionary of registered agents
            create_anthropic_llm_fn: Function to create Anthropic LLM
            available_agents: List of agent names to include
            context: MCP context
            plan_type: Type of planning to use
            
        Returns:
            Orchestrator instance
        """
        logger.info(f"Creating orchestrator with agents: {available_agents}")
        
        # Ensure the agents exist - this will use the original names
        agents_list = self.ensure_agents_exist(
            agent_registry=agent_registry,
            agent_names=available_agents or ["finder", "writer"],  # Use original lowercase names
            context=context
        )
        
        # We'll use the list returned from ensure_agents_exist directly
        agents_to_use = agents_list
        
        if not agents_to_use:
            logger.warning("No agents available for orchestrator, using finder and writer as defaults")
            default_agents = []
            
            # Look for agents by name in registry
            finder_agent = None
            for agent_name, agent in agent_registry.items():
                if agent.name == "finder":
                    finder_agent = agent
                    break
                    
            writer_agent = None
            for agent_name, agent in agent_registry.items():
                if agent.name == "writer":
                    writer_agent = agent
                    break
                    
            # If we can't find them by name, try the keys
            if finder_agent is None and "finder" in agent_registry:
                finder_agent = agent_registry["finder"]
            if writer_agent is None and "writer" in agent_registry:
                writer_agent = agent_registry["writer"]
                
            # Add the agents if found
            if finder_agent:
                default_agents.append(finder_agent)
            if writer_agent:
                default_agents.append(writer_agent)
            
            if not default_agents:
                logger.error("Cannot create orchestrator: no agents available")
                raise ValueError("No agents available to create orchestrator")
                
            agents_to_use = default_agents
        
        # Create the orchestrator
        try:
            # Define the LLM factory function that will create LLMs for each agent
            def llm_factory(agent):
                return create_anthropic_llm_fn(agent=agent)
                
            # Create the orchestrator directly using the standard pattern
            orchestrator = Orchestrator(
                llm_factory=llm_factory,
                available_agents=agents_to_use,
                plan_type=plan_type,
                context=context
            )
            
            # Explicitly set the model in the default request params to override model selection
            if not hasattr(orchestrator, 'default_request_params') or orchestrator.default_request_params is None:
                orchestrator.default_request_params = RequestParams(model=DEFAULT_MODEL)
            else:
                orchestrator.default_request_params.model = DEFAULT_MODEL
            
            logger.info(f"Created orchestrator with {len(agents_to_use)} agents and default model {DEFAULT_MODEL}")
            return orchestrator
        except Exception as e:
            logger.error(f"Error creating orchestrator: {str(e)}")
            raise ValueError(f"Failed to create orchestrator: {str(e)}")
    
    async def create_router(
        self,
        agent_registry: Dict[str, Agent],
        create_anthropic_llm_fn,
        available_agents: Optional[List[str]] = None,
        context=None
    ) -> AnthropicLLMRouter:
        """
        Create a router with the specified agents.
        
        Args:
            agent_registry: Dictionary of registered agents
            create_anthropic_llm_fn: Function to create Anthropic LLM (used as fallback)
            available_agents: List of agent names to include
            context: MCP context
            
        Returns:
            Router instance
        """
        logger.info(f"Creating router with agents: {available_agents}")
        
        # Default agent names - include all available agents
        default_agent_names = [
            "decider", 
            "websearcher", 
            "finder", 
            "structure", 
            "writer", 
            "proofreader", 
            "factchecker", 
            "formatter", 
            "styleenforcer", 
            "chartgenerator"
        ]
        
        # Ensure the agents exist - this will use the original names
        agents_list = self.ensure_agents_exist(
            agent_registry=agent_registry,
            agent_names=available_agents or default_agent_names,
            context=context
        )
        
        # We'll use the list returned from ensure_agents_exist directly
        agents_to_use = agents_list
        
        if not agents_to_use:
            logger.warning("No agents available for router, using all available agents as defaults")
            agents_to_use = list(agent_registry.values())  # Convert dict values to list
            
            if not agents_to_use:
                logger.error("Cannot create router: no agents available")
                raise ValueError("No agents available to create router")
        
        # Create the router
        if context:
            try:
                # Use the AnthropicLLMRouter directly - it creates its own LLM instance
                router = await AnthropicLLMRouter.create(
                    agents=agents_to_use,
                    context=context
                )
                
                logger.info(f"Created AnthropicLLMRouter with {len(agents_to_use)} agents")
                return router
            except Exception as e:
                logger.error(f"Error creating router: {str(e)}")
                
                # Fallback: create the LLM and pass it explicitly
                llm = create_anthropic_llm_fn()
                router = AnthropicLLMRouter(
                    agents=agents_to_use,
                    context=context
                )
                logger.info(f"Created AnthropicLLMRouter with {len(agents_to_use)} agents using direct initialization")
                return router
        else:
            logger.error("Cannot create router: context is missing")
            raise ValueError("Context is required to create router")

    async def _validate_and_refresh_config(self):
        """
        Validate the configuration and refresh cached values.
        
        This is called when the configuration is updated to ensure
        all cached values are refreshed from the updated config.
        """
        # Refresh agents from config
        self._refresh_agents_from_config()
        
        # Validate required agent configs
        logger.info(f"Validating agent configurations...")
        for required_agent in REQUIRED_AGENTS:
            if required_agent not in self.agent_configs:
                logger.warning(f"Required agent '{required_agent}' not found in configuration")
                
        # Log available agents
        available_agents = list(self.agent_configs.keys())
        logger.info(f"Available agents: {available_agents}")
        
        # Save last validated timestamp
        self.last_validated = datetime.now()
        
        return True
    
    def get_available_agents(self) -> List[str]:
        """
        Get a list of all available agent names from the configuration.
        
        Returns:
            List of agent names
        """
        return list(self.agent_configs.keys()) 