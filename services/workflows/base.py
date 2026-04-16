"""
Base classes for workflow agents
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """
    Base class for all workflow agents.
    
    Agents are specialized workers that handle specific tasks in the content generation pipeline.
    """
    
    def __init__(self, name: str, timeout: int = 30):
        self.name = name
        self.timeout = timeout
        self.execution_start: Optional[datetime] = None
        self.execution_end: Optional[datetime] = None
        
    @abstractmethod
    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the agent's primary task.
        
        Args:
            input_data: Input parameters for the agent
            
        Returns:
            Dictionary with results and metadata
        """
        pass
    
    @abstractmethod
    async def validate_input(self, input_data: Dict[str, Any]) -> bool:
        """
        Validate input data before execution.
        
        Args:
            input_data: Data to validate
            
        Returns:
            True if valid, raises exception otherwise
        """
        pass
    
    async def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        High-level run method with logging and error handling.
        """
        try:
            logger.info(f"[{self.name}] Starting execution")
            self.execution_start = datetime.now()
            
            # Validate input
            await self.validate_input(input_data)
            
            # Execute
            result = await self.execute(input_data)
            
            self.execution_end = datetime.now()
            execution_time = (self.execution_end - self.execution_start).total_seconds()
            
            logger.info(f"[{self.name}] Completed in {execution_time:.2f}s")
            
            return {
                "success": True,
                "agent": self.name,
                "data": result,
                "execution_time_seconds": execution_time,
                "timestamp": self.execution_end.isoformat(),
            }
            
        except Exception as e:
            self.execution_end = datetime.now()
            logger.error(f"[{self.name}] Error: {str(e)}")
            
            return {
                "success": False,
                "agent": self.name,
                "error": str(e),
                "execution_time_seconds": (self.execution_end - self.execution_start).total_seconds() 
                    if self.execution_start else 0,
                "timestamp": self.execution_end.isoformat(),
            }
    
    def _get_execution_time(self) -> float:
        """Get execution time in seconds"""
        if self.execution_start and self.execution_end:
            return (self.execution_end - self.execution_start).total_seconds()
        return 0.0


class CoordinatorAgent(BaseAgent):
    """
    Base class for coordinator/orchestrator agents that manage other agents.
    """
    
    def __init__(self, name: str, timeout: int = 60):
        super().__init__(name, timeout)
        self.managed_agents: Dict[str, BaseAgent] = {}
    
    def register_agent(self, agent_id: str, agent: BaseAgent):
        """Register a managed agent"""
        self.managed_agents[agent_id] = agent
    
    def get_agent(self, agent_id: str) -> Optional[BaseAgent]:
        """Get a registered agent"""
        return self.managed_agents.get(agent_id)


class AgentResponse:
    """Standardized response wrapper for agent execution"""
    
    def __init__(self, success: bool, data: Any = None, error: str = None, 
                 agent_name: str = None, execution_time: float = 0.0):
        self.success = success
        self.data = data
        self.error = error
        self.agent_name = agent_name
        self.execution_time = execution_time
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "success": self.success,
            "agent": self.agent_name,
            "data": self.data,
            "error": self.error,
            "execution_time": self.execution_time,
        }
