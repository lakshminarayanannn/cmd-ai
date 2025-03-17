"""
Memory system for Fixter using langmem.
Provides both short-term (session) and long-term (persistent) memory capabilities.
"""

import time
import uuid
import os
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import json

from langmem import (
    create_memory_manager,
    create_memory_store_manager,
    create_search_memory_tool,
    create_manage_memory_tool,
    ReflectionExecutor
)
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AnyMessage
from langgraph.store.base import BaseStore

from fixter.config import SESSIONS_DIR

class MemorySystem:
    """Unified memory system combining short-term and long-term memory."""
    
    def __init__(
        self, 
        llm: BaseChatModel,
        store: BaseStore,
        namespace: Tuple[str, ...] = ("fixter", "{user_id}")
    ):
        """Initialize the memory system.
        
        Args:
            llm: Language model for memory operations
            store: BaseStore for persistent storage
            namespace: Namespace for memory storage (templates supported)
        """
        self.llm = llm
        self.store = store
        self.namespace = namespace
        
        self.sessions: Dict[str, Dict[str, Any]] = {}
        
        self.memory_manager = create_memory_manager(
            llm, 
            enable_inserts=True,
            enable_updates=True,
            enable_deletes=True
        )
        
        self.memory_store_manager = create_memory_store_manager(
            llm,
            namespace=namespace,
            store=store
        )
        
        self.search_tool = create_search_memory_tool(
            namespace=namespace,
            store=store
        )
        
        self.manage_tool = create_manage_memory_tool(
            namespace=namespace,
            store=store
        )
        
        self.reflection = ReflectionExecutor(
            self.memory_store_manager,
            store=store
        )
    
    def get_session(self, session_id: Optional[str] = None) -> Dict[str, Any]:
        """Get or create a session."""
        if not session_id:
            session_id = str(uuid.uuid4())
        
        if session_id not in self.sessions:
            session_file = os.path.join(SESSIONS_DIR, f"{session_id}.json")
            if os.path.exists(session_file):
                with open(session_file, 'r') as f:
                    self.sessions[session_id] = json.load(f)
            else:
                self.sessions[session_id] = {
                    "session_id": session_id,
                    "created_at": time.time(),
                    "last_accessed": time.time(),
                    "conversation_history": [],
                    "entities": {},
                    "context": {}
                }
        
        self.sessions[session_id]["last_accessed"] = time.time()
        return self.sessions[session_id]
    
    def save_session(self, session_id: str) -> None:
        """Save session to disk."""
        if session_id not in self.sessions:
            return
        
        session_file = os.path.join(SESSIONS_DIR, f"{session_id}.json")
        os.makedirs(os.path.dirname(session_file), exist_ok=True)
        
        with open(session_file, 'w') as f:
            json.dump(self.sessions[session_id], f, indent=2)
    
    def add_message(self, session_id: str, query: str, response: Optional[str] = None) -> None:
        """Add a message to the session conversation history."""
        session = self.get_session(session_id)
        
        message = {
            "timestamp": time.time(),
            "query": query,
            "response": response
        }
        
        session["conversation_history"].append(message)
        
        max_history = 10 
        if len(session["conversation_history"]) > max_history:
            session["conversation_history"] = session["conversation_history"][-max_history:]
        
        self.save_session(session_id)
    
    def get_recent_history(self, session_id: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Get recent conversation history for a session."""
        session = self.get_session(session_id)
        history = session["conversation_history"]
        
        return history[-limit:] if limit > 0 else history
    
    def add_entity(self, session_id: str, entity_type: str, value: str, metadata: Dict[str, Any] = None) -> None:
        """Add an entity to the session memory."""
        session = self.get_session(session_id)
        
        key = f"{entity_type}:{value}"
        session["entities"][key] = {
            "type": entity_type,
            "value": value,
            "last_mentioned": time.time(),
            "metadata": metadata or {}
        }
        
        self.save_session(session_id)
    
    def get_entities(self, session_id: str, entity_type: Optional[str] = None, limit: int = 5) -> List[Dict[str, Any]]:
        """Get entities from session memory, optionally filtered by type."""
        session = self.get_session(session_id)
        entities = list(session["entities"].values())
        
        if entity_type:
            entities = [e for e in entities if e["type"] == entity_type]
        
        entities = sorted(entities, key=lambda e: e.get("last_mentioned", 0), reverse=True)
        
        return entities[:limit] if limit > 0 else entities
    
    def extract_context(self, session_id: str, query: str) -> str:
        """Extract relevant context from memory to enhance a query."""
        session = self.get_session(session_id)
        
        history = self.get_recent_history(session_id, 3)
        history_text = ""
        if history:
            history_text = "Recent conversation:\n"
            for msg in history:
                history_text += f"User: {msg.get('query', '')}\n"
                if msg.get('response'):
                    response = msg.get('response', '')
                    if len(response) > 150:
                        response = response[:150] + "..."
                    history_text += f"Assistant: {response}\n"
        
        entities = self.get_entities(session_id, limit=5)
        entities_text = ""
        if entities:
            entities_text = "\nRecently mentioned entities:\n"
            for entity in entities:
                entities_text += f"- {entity.get('type')}: {entity.get('value')}\n"
        
        if history_text or entities_text:
            context = f"Context from memory:\n{history_text}{entities_text}\n\nCurrent query: {query}"
            return context
        
        return query
    
    async def process_memory_async(self, session_id: str, messages: List[AnyMessage], user_id: str) -> None:
        """Process conversation and update long-term memory asynchronously."""
        config = {"configurable": {"user_id": user_id}}
        
        self.reflection.submit(
            {"messages": messages},
            config=config,
            after_seconds=0  
        )
    
    def search_memory(self, query: str, user_id: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Search long-term memory for relevant information."""
        config = {"configurable": {"user_id": user_id}}
        results, _ = self.search_tool.invoke(
            {"query": query, "limit": limit},
            config=config
        )
        return results