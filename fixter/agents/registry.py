from typing import Dict, Type, Set, List
import inspect
import importlib

from fixter.agents.agent_base import BaseAgent

class AgentRegistry:
    """Registry for agent classes that can be dynamically loaded"""
    
    _registry: Dict[str, Type[BaseAgent]] = {}
    
    @classmethod
    def register(cls, agent_class: Type[BaseAgent]) -> Type[BaseAgent]:
        """Register an agent class in the registry"""
        agent_type = agent_class.__name__.lower().replace('agent', '')
        cls._registry[agent_type] = agent_class
        return agent_class
    
    @classmethod
    def get(cls, agent_type: str) -> Type[BaseAgent]:
        """Get an agent class by type"""
        if agent_type not in cls._registry:
            raise ValueError(f"Agent type '{agent_type}' not found in registry")
        return cls._registry[agent_type]
    
    @classmethod
    def list(cls) -> List[str]:
        """List all registered agent types"""
        return list(cls._registry.keys())
    
    @classmethod
    def load_all(cls):
        """Load all agent classes from the agents package"""
        from fixter.agents import ExtractionAgent, ConversationAgent
        
        cls.register(ExtractionAgent)
        cls.register(ConversationAgent)
        
        
        return cls._registry