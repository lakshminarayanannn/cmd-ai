
import os
from typing import Dict, Any, Optional

from langchain_openai import ChatOpenAI
from dotenv import load_dotenv

from fixter.session_memory import SessionManager
from fixter.tools import ALL_TOOLS
from fixter.agents import Coordinator

load_dotenv()

API_KEY = os.getenv("OPENAI_API_KEY")
llm = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0,
    max_tokens=None,
    timeout=None,
    max_retries=2,
    api_key=API_KEY,
)

session_manager = SessionManager()

coordinator = Coordinator(llm, ALL_TOOLS, session_manager)

def run_query(query: str, session_id: str = None) -> str:
    """Run a query through the coordinator"""
    return coordinator.process(query, session_id)