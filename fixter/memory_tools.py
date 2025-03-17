from langchain_core.tools import tool
from fixter.session_memory import SessionManager
import os
import json
import datetime

session_manager = SessionManager()

@tool
def list_memory_sessions():
    """
    List all available memory sessions.
    
    Returns:
        str: A formatted list of available memory sessions.
    """
    sessions = session_manager.list_sessions()
    
    if not sessions:
        return "No memory sessions found."
    
    result = "Available memory sessions:\n\n"
    for session in sessions:
        result += f"Session ID: {session['session_id']}\n"
        result += f"  Created: {session['created_at']}\n"
        result += f"  Last accessed: {session['last_accessed']}\n"
        result += f"  Conversation turns: {session['conversation_turns']}\n"
        result += f"  Currently loaded: {'Yes' if session['in_memory'] else 'No'}\n\n"
    
    return result

@tool
def clear_memory_session():
    """
    Clear the current memory session.
    
    Returns:
        str: Confirmation that the session was cleared.
    """
    return "Current memory session has been cleared. A new session will be created for the next query."

@tool
def get_conversation_history(limit: int = 5):
    """
    Get the recent conversation history from the current session.
    
    Args:
        limit (int): Maximum number of conversation turns to retrieve.
        
    Returns:
        str: The recent conversation history.
    """
    session = session_manager.get_session()
    
    history = session.conversation_history[-limit:] if limit > 0 else session.conversation_history
    
    if not history:
        return "No conversation history found in the current session."
    
    result = "Recent conversation history:\n\n"
    for i, turn in enumerate(history):
        timestamp = turn.get("timestamp", 0)
        time_str = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
        result += f"[{time_str}] You: {turn.get('query', '')}\n"
        if turn.get("response"):
            result += f"Assistant: {turn.get('response')[:100]}{'...' if len(turn.get('response', '')) > 100 else ''}\n"
        result += "\n"
    
    return result

@tool
def get_memory_entities(entity_type: str = None, limit: int = 5):
    """
    Get entities stored in the current session memory.
    
    Args:
        entity_type (str, optional): Type of entities to filter by (e.g., "file", "directory", "repository").
        limit (int): Maximum number of entities to retrieve.
        
    Returns:
        str: The entities from the current session memory.
    """
    session = session_manager.get_session()
    
    entities = session.get_recent_entities(entity_type, limit)
    
    if not entities:
        entity_type_msg = f" of type '{entity_type}'" if entity_type else ""
        return f"No entities{entity_type_msg} found in the current session memory."
    
    result = f"Recent entities in memory:\n\n"
    for entity in entities:
        result += f"Type: {entity.type}\n"
        result += f"Value: {entity.value}\n"
        if entity.metadata:
            result += f"Metadata: {json.dumps(entity.metadata)}\n"
        result += "\n"
    
    return result