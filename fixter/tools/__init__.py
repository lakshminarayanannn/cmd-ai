from fixter.tools.extraction_tools import extract_git_content, extract_content_local
from fixter.tools.memory_tools import list_memory_sessions, clear_memory_session, get_conversation_history, get_memory_entities
from fixter.tools.utility_tools import get_system_time, search_tool

EXTRACTION_TOOLS = [extract_git_content, extract_content_local]
MEMORY_TOOLS = [list_memory_sessions, clear_memory_session, get_conversation_history, get_memory_entities]
UTILITY_TOOLS = [get_system_time, search_tool]

ALL_TOOLS = EXTRACTION_TOOLS + MEMORY_TOOLS + UTILITY_TOOLS