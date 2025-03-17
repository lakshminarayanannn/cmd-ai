from typing import Dict, Any, List, Optional, Union
import re
import json
import logging

from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool
from langchain import hub
from langchain.agents import create_react_agent
from langgraph.graph import StateGraph, END
from langchain_core.agents import AgentAction, AgentFinish

from fixter.agents.agent_base import BaseAgent
from fixter.agents.extraction_agent import ExtractionAgent
from fixter.agents.conversation_agent import ConversationAgent
from fixter.session_memory import SessionManager, SessionMemory

from enum import Enum
from typing import List, Dict, Any, Optional
from langchain_core.prompts import ChatPromptTemplate

class Coordinator(BaseAgent): 
    def __init__(self, llm, tools, session_manager):
        """
        Maintains the same constructor signature as the original Coordinator
        """
        super().__init__(llm, tools, session_manager)
        
        self.extraction_agent = ExtractionAgent(llm, tools, session_manager)
        self.conversation_agent = ConversationAgent(llm, tools, session_manager)
        
        self.routing_prompt = ChatPromptTemplate.from_messages([
            ("system", """
            You are an intelligent query classifier. Your task is to determine 
            the type of query based on its intent.

            Query Types:
            - extraction: Queries involving file/content retrieval, repository cloning, 
                          specific file searches, directory listings
            - conversation: General information queries, reasoning tasks, 
                            open-ended questions, discussions

            Respond with ONLY the agent type: extraction or conversation
            """),
            ("human", "{input}")
        ])

    def _classify_query(self, query: str) -> str:
        """
        Classify the query type using LLM
        Returns 'extraction' or 'conversation'
        """
        try:
            prompt = self.routing_prompt.format_messages(input=query)
            response = self.llm.invoke(prompt)
            classification = response.content.strip().lower()
            
            if classification not in ['extraction', 'conversation']:
                return 'conversation'
            
            return classification
        except Exception:
            return self._fallback_routing(query)

    def _fallback_routing(self, query: str) -> str:
        """
        Fallback routing method using existing can_handle logic
        """
        extraction_confidence = self.extraction_agent.can_handle(query)
        conversation_confidence = self.conversation_agent.can_handle(query)
        
        return 'extraction' if extraction_confidence > conversation_confidence else 'conversation'

    def process(self, query: str, session_id: str = None) -> str:
        """
        Process query by routing to the appropriate agent
        Maintains exact same method signature and behavior
        """
        agent_type = self._classify_query(query)
        
        if agent_type == 'extraction':
            selected_agent = self.extraction_agent
        else:
            selected_agent = self.conversation_agent
        
        result = selected_agent.process(query, session_id)
        
        return result

    def register_agent(self, agent_type: str, agent: BaseAgent) -> None:
        """Maintain existing method for registering agents"""
        if not isinstance(agent, BaseAgent):
            raise ValueError("Agent must be an instance of BaseAgent")
        
        self.agents[agent_type] = agent
        self.logger.info(f"Registered agent: {agent_type}")

    def get_agents(self) -> Dict[str, BaseAgent]:
        """Retrieve all registered agents"""
        return self.agents