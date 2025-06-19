from typing import Callable, List, Optional, TYPE_CHECKING

from mcp_agent.agents.agent import Agent
from mcp_agent.workflows.router.router_llm_anthropic import AnthropicLLMRouter

if TYPE_CHECKING:
    from mcp_agent.context import Context

ROUTING_SYSTEM_INSTRUCTION = """
You are a highly accurate request router that directs incoming requests to the most appropriate category.
A category is a specialized destination, such as a Function, an MCP Server (a collection of tools/functions), or an Agent (a collection of servers).
You will be provided with a request and a list of categories to choose from.
You can choose one or more categories, or choose none if no category is appropriate.
"""


class FixedAnthropicLLMRouter(AnthropicLLMRouter):
    """
    A minimal patch of AnthropicLLMRouter that uses our FixedAnthropicAugmentedLLM 
    (with Vertex AI support) instead of the original AnthropicAugmentedLLM.
    
    This is a simple override that only changes the LLM creation while inheriting
    all other functionality from the original router.
    """

    def __init__(
        self,
        server_names: List[str] | None = None,
        agents: List[Agent] | None = None,
        functions: List[Callable] | None = None,
        routing_instruction: str | None = None,
        context: Optional["Context"] = None,
        **kwargs,
    ):
        # Lazy import to avoid circular dependency
        from .coordinator_agent import FixedAnthropicAugmentedLLM
        
        # Create our fixed LLM instead of the original one
        anthropic_llm = FixedAnthropicAugmentedLLM(
            instruction=ROUTING_SYSTEM_INSTRUCTION, 
            context=context
        )
        
        # Call parent's parent (LLMRouter) directly to avoid the original AnthropicLLMRouter's LLM creation
        super(AnthropicLLMRouter, self).__init__(
            llm=anthropic_llm,
            server_names=server_names,
            agents=agents,
            functions=functions,
            routing_instruction=routing_instruction,
            context=context,
            **kwargs,
        )

    @classmethod
    async def create(
        cls,
        server_names: List[str] | None = None,
        agents: List[Agent] | None = None,
        functions: List[Callable] | None = None,
        routing_instruction: str | None = None,
        context: Optional["Context"] = None,
    ) -> "FixedAnthropicLLMRouter":
        """
        Factory method to create and initialize a router.
        Use this instead of constructor since we need async initialization.
        """
        instance = cls(
            server_names=server_names,
            agents=agents,
            functions=functions,
            routing_instruction=routing_instruction,
            context=context,
        )
        await instance.initialize()
        return instance 