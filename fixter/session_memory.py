
import os
import json
import time
import uuid
import psutil
from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field
import re
from datetime import datetime

SESSION_DIR = os.path.expanduser("~/.fixter/sessions")

class EntityInfo(BaseModel):
    """Information about an entity mentioned in conversation"""
    type: str
    value: str
    last_mentioned: float = Field(default_factory=time.time)
    metadata: Dict[str, Any] = {}

class SessionMemory(BaseModel):
    """Memory structure for a terminal session"""
    session_id: str
    created_at: float = Field(default_factory=time.time)
    last_accessed: float = Field(default_factory=time.time)
    conversation_history: List[Dict[str, Any]] = []
    entities: Dict[str, EntityInfo] = {}
    context: Dict[str, Any] = {}
    active_task: Optional[Dict[str, Any]] = None

    def update_access_time(self):
        """Update the last accessed time"""
        self.last_accessed = time.time()
        
    def add_conversation_turn(self, query: str, response: str = None):
        """Add a conversation turn to history"""
        turn = {
            "timestamp": time.time(),
            "query": query,
            "response": response
        }
        self.conversation_history.append(turn)
        self.update_access_time()
        
        if len(self.conversation_history) > 20:
            self.conversation_history = self.conversation_history[-20:]

    def add_entity(self, entity_type: str, value: str, metadata: Dict[str, Any] = None):
        """Add or update an entity in memory"""
        key = f"{entity_type}:{value}"
        self.entities[key] = EntityInfo(
            type=entity_type,
            value=value,
            last_mentioned=time.time(),
            metadata=metadata or {}
        )
        self.update_access_time()
    
    def get_recent_entities(self, entity_type: str = None, limit: int = 5):
        """Get recently mentioned entities, optionally filtered by type"""
        entities = self.entities.values()
        if entity_type:
            entities = [e for e in entities if e.type == entity_type]
        
        sorted_entities = sorted(entities, key=lambda e: e.last_mentioned, reverse=True)
        return sorted_entities[:limit]
    
    def set_active_task(self, task_description: str, task_data: Dict[str, Any] = None):
        """Set the currently active task"""
        self.active_task = {
            "description": task_description,
            "started_at": time.time(),
            "data": task_data or {}
        }
        self.update_access_time()
    
    def clear_active_task(self):
        """Clear the active task"""
        self.active_task = None
        self.update_access_time()
    
    def extract_entities_from_query(self, query: str):
        """Extract entities from a query and add them to memory"""
        file_paths = re.findall(r'/[\w/\.-]+\.\w+', query)
        for path in file_paths:
            if os.path.exists(path):
                self.add_entity("file", path, {"exists": True})
        
        dir_paths = re.findall(r'/[\w/\.-]+/?', query)
        for path in dir_paths:
            if os.path.isdir(path):
                self.add_entity("directory", path, {"exists": True})
        
        repos = re.findall(r'(?:github\.com/|https://github\.com/)[\w-]+/[\w-]+', query)
        for repo in repos:
            self.add_entity("repository", repo)
        
        extensions = re.findall(r'\.([a-zA-Z0-9]+)\b', query)
        for ext in extensions:
            if len(ext) <= 5: 
                self.add_entity("extension", f".{ext}")

class SessionManager:
    """Manages session memory isolation and persistence"""
    
    def __init__(self):
        """Initialize the session manager"""
        os.makedirs(SESSION_DIR, exist_ok=True)
        self.active_sessions = {}
        
    def _generate_terminal_id(self):
        """Generate a unique ID for the current terminal session"""
        pid = os.getpid()
        
        try:
            parent = psutil.Process(pid).parent()
            ppid = parent.pid
            terminal_info = f"{parent.name()}-{ppid}"
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            terminal_info = f"unknown-terminal"
        
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        return f"{terminal_info}-{timestamp}"
    
    def get_session(self, session_id=None, create_if_missing=True):
        """Get an existing session or create a new one"""
        if not session_id:
            session_id = self._generate_terminal_id()
        
        if session_id in self.active_sessions:
            session = self.active_sessions[session_id]
            session.update_access_time()
            return session
        
        session_file = os.path.join(SESSION_DIR, f"{session_id}.json")
        if os.path.exists(session_file):
            try:
                with open(session_file, 'r') as f:
                    session_data = json.load(f)
                    session = SessionMemory(**session_data)
                    self.active_sessions[session_id] = session
                    return session
            except (json.JSONDecodeError, Exception) as e:
                print(f"Error loading session {session_id}: {e}")
        
        if create_if_missing:
            session = SessionMemory(session_id=session_id)
            self.active_sessions[session_id] = session
            return session
        
        return None
    
    def save_session(self, session_id):
        """Save a session to disk"""
        if session_id not in self.active_sessions:
            return False
        
        session = self.active_sessions[session_id]
        session_file = os.path.join(SESSION_DIR, f"{session_id}.json")
        
        try:
            with open(session_file, 'w') as f:
                json.dump(session.dict(), f, indent=2)
            return True
        except Exception as e:
            print(f"Error saving session {session_id}: {e}")
            return False
    
    def save_all_sessions(self):
        """Save all active sessions to disk"""
        for session_id in list(self.active_sessions.keys()):
            self.save_session(session_id)
    
    def list_sessions(self):
        """List all available sessions"""
        sessions = []
        
        for session_id, session in self.active_sessions.items():
            sessions.append({
                "session_id": session_id,
                "created_at": datetime.fromtimestamp(session.created_at).isoformat(),
                "last_accessed": datetime.fromtimestamp(session.last_accessed).isoformat(),
                "conversation_turns": len(session.conversation_history),
                "in_memory": True
            })
        
        for filename in os.listdir(SESSION_DIR):
            if filename.endswith('.json'):
                session_id = filename[:-5]
                if session_id not in self.active_sessions:
                    try:
                        with open(os.path.join(SESSION_DIR, filename), 'r') as f:
                            data = json.load(f)
                            sessions.append({
                                "session_id": session_id,
                                "created_at": datetime.fromtimestamp(data.get("created_at", 0)).isoformat(),
                                "last_accessed": datetime.fromtimestamp(data.get("last_accessed", 0)).isoformat(),
                                "conversation_turns": len(data.get("conversation_history", [])),
                                "in_memory": False
                            })
                    except Exception:
                        pass
        
        return sessions
    
    def clear_old_sessions(self, max_age_days=7):
        """Clear sessions older than the specified age"""
        cutoff_time = time.time() - (max_age_days * 24 * 60 * 60)
        
        for filename in os.listdir(SESSION_DIR):
            if filename.endswith('.json'):
                session_path = os.path.join(SESSION_DIR, filename)
                try:
                    with open(session_path, 'r') as f:
                        data = json.load(f)
                        last_accessed = data.get("last_accessed", 0)
                        if last_accessed < cutoff_time:
                            os.remove(session_path)
                except Exception:
                    pass
        
        for session_id in list(self.active_sessions.keys()):
            session = self.active_sessions[session_id]
            if session.last_accessed < cutoff_time:
                del self.active_sessions[session_id]