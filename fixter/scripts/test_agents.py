import sys
import os
import argparse

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from fixter.main import run_query
from fixter.agents import Coordinator
from fixter.agents.extraction_agent import ExtractionAgent
from fixter.agents.conversation_agent import ConversationAgent
from fixter.tools import ALL_TOOLS
from fixter.session_memory import SessionManager

def test_extraction(query, session_id=None):
    """Test the extraction agent directly"""
    from langchain_openai import ChatOpenAI
    
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0,
    )
    
    session_manager = SessionManager()
    agent = ExtractionAgent(llm, ALL_TOOLS, session_manager)
    
    result = agent.process(query, session_id)
    print(f"\n--- EXTRACTION AGENT RESULT ---\n{result}\n")
    return result

def test_conversation(query, session_id=None):
    """Test the conversation agent directly"""
    from langchain_openai import ChatOpenAI
    
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0,
    )
    
    session_manager = SessionManager()
    agent = ConversationAgent(llm, ALL_TOOLS, session_manager)
    
    result = agent.process(query, session_id)
    print(f"\n--- CONVERSATION AGENT RESULT ---\n{result}\n")
    return result

def test_coordinator(query, session_id=None):
    """Test the full coordinator with all agents"""
    result = run_query(query, session_id)
    print(f"\n--- COORDINATOR RESULT ---\n{result}\n")
    return result

def main():
    parser = argparse.ArgumentParser(description="Test the agent system")
    parser.add_argument('--agent', choices=['extraction', 'conversation', 'coordinator'], 
                        default='coordinator', help='Agent to test')
    parser.add_argument('query', help='Query to test')
    parser.add_argument('--session', help='Session ID to use (optional)')
    
    args = parser.parse_args()
    
    if args.agent == 'extraction':
        test_extraction(args.query, args.session)
    elif args.agent == 'conversation':
        test_conversation(args.query, args.session)
    else:
        test_coordinator(args.query, args.session)

if __name__ == "__main__":
    main()