from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

class BaseAgent(ABC):
    """
    Base class for all agents
    """
    
    @abstractmethod
    async def process(self, **kwargs) -> Dict[str, Any]:
        """
        Process the input and return the result
        
        Args:
            **kwargs: Agent-specific input parameters
            
        Returns:
            Dict[str, Any]: Agent-specific output
        """
        pass 