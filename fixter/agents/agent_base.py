import os
from typing import Dict, Any, Optional, List, Union
from langchain_core.agents import AgentAction, AgentFinish
from fixter.session_memory import SessionManager, SessionMemory
from abc import ABC, abstractmethod

class BaseAgent(ABC):
    """Base class for all agents in the multi-agent system"""
    
    def __init__(self, llm, tools, session_manager=None):
        """Initialize the agent with language model, tools, and session manager"""
        self.llm = llm
        self.tools = tools
        self.session_manager = session_manager or SessionManager()
        self.name = self.__class__.__name__
    
    @abstractmethod
    def process(self, query: str, session_id: str = None) -> str:
        """
        Process a query and return the result
        
        Args:
            query: The user query to process
            session_id: Optional session ID for memory persistence
            
        Returns:
            The agent's response as a string
        """
        pass
    
    def _get_session(self, session_id: str = None) -> SessionMemory:
        """Get or create a session"""
        return self.session_manager.get_session(session_id)
    
    def _save_session(self, session_id: str) -> bool:
        """Save the session to disk"""
        return self.session_manager.save_session(session_id)
    
    def _add_to_conversation_history(self, session: SessionMemory, query: str, response: str) -> None:
        """Add the query and response to the session's conversation history"""
        session.add_conversation_turn(query, response)
        
    def can_handle(self, query: str) -> float:
        """
        Determine if this agent can handle the given query, returning a confidence score
        
        Args:
            query: The user query to check
            
        Returns:
            A confidence score between 0.0 and 1.0
        """
        return 0.5
    
    def _enhance_with_memory(self, query: str, session: SessionMemory) -> str:
        """
        Enhance the query with memory context
        
        Args:
            query: The original query
            session: The session memory
            
        Returns:
            The enhanced query with context
        """
        session.extract_entities_from_query(query)
        
        return query