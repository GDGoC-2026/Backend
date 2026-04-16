"""
Type definitions and protocols for the workflow system
"""

from typing import Protocol, Dict, Any, List
from abc import abstractmethod


class Agent(Protocol):
    """Protocol for all agents in the workflow"""
    
    name: str
    timeout: int
    
    @abstractmethod
    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute agent's main task"""
        ...
    
    @abstractmethod
    async def validate_input(self, input_data: Dict[str, Any]) -> bool:
        """Validate input data"""
        ...
    
    async def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Run agent with error handling"""
        ...


class Coordinator(Protocol):
    """Protocol for coordinator agents"""
    
    managed_agents: Dict[str, Agent]
    
    def register_agent(self, agent_id: str, agent: Agent) -> None:
        """Register a managed agent"""
        ...
    
    def get_agent(self, agent_id: str) -> Agent:
        """Get a registered agent"""
        ...


class WorkflowResponse(Protocol):
    """Standard workflow response"""
    
    success: bool
    student_id: str
    topic: str
    generated_content: List[Dict[str, Any]]
    execution_summary: Dict[str, Any]
    quality_metrics: Dict[str, Any]
    workflow_log: List[Dict[str, Any]]


# Type aliases for common structures
AgentResult = Dict[str, Any]
WorkflowRequest = Dict[str, Any]
ContentBundle = List[Dict[str, Any]]
QualityMetrics = Dict[str, Any]
ExecutionLog = Dict[str, Any]
