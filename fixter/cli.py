
import argparse
import os
import json
from fixter.main import run_query, session_manager
from fixter.config_commands import add_variable_commands, interpolate_vars

SESSION_FILE = os.path.expanduser("~/.fixter/current_session")

def get_current_session_id():
    """Get the current session ID for this terminal"""
    if os.path.exists(SESSION_FILE):
        try:
            with open(SESSION_FILE, 'r') as f:
                return f.read().strip()
        except:
            pass
    return None

def save_current_session_id(session_id):
    """Save the current session ID for this terminal"""
    os.makedirs(os.path.dirname(SESSION_FILE), exist_ok=True)
    with open(SESSION_FILE, 'w') as f:
        f.write(session_id)

def list_sessions(args):
    """List all available sessions"""
    sessions = session_manager.list_sessions()
    
    current_session = get_current_session_id()
    
    if not sessions:
        print("No sessions found.")
        return
    
    print("Available sessions:")
    for session in sessions:
        session_id = session['session_id']
        is_current = "(current)" if session_id == current_session else ""
        print(f"{session_id} {is_current}")
        print(f"  Created: {session['created_at']}")
        print(f"  Last accessed: {session['last_accessed']}")
        print(f"  Conversation turns: {session['conversation_turns']}")
        print()

def clear_session(args):
    """Clear the current session"""
    if os.path.exists(SESSION_FILE):
        os.remove(SESSION_FILE)
    print("Session cleared. A new session will be used for the next query.")

def main():
    parser = argparse.ArgumentParser(description="Fixter AI command-line tool")
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')
    
    ai_parser = subparsers.add_parser('ai', help='Send a query to the AI system')
    ai_parser.add_argument('query', help='Query to send to the AI system')
    ai_parser.add_argument('--new-session', action='store_true', 
                          help='Start a new session instead of continuing the current one')
    
    session_parser = subparsers.add_parser('sessions', help='List all available sessions')
    session_parser.set_defaults(func=list_sessions)
    
    clear_parser = subparsers.add_parser('clear-session', help='Clear the current session')
    clear_parser.set_defaults(func=clear_session)
    
    add_variable_commands(subparsers)
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    if hasattr(args, 'func'):
        args.func(args)
        return
    
    if args.command == 'ai':
        session_id = None if args.new_session else get_current_session_id()
        
        processed_query = interpolate_vars(args.query)
        
        result = run_query(processed_query, session_id)
        
        if not session_id:
            new_sessions = session_manager.list_sessions()
            if new_sessions:
                latest_session = max(new_sessions, key=lambda s: s['last_accessed'])
                save_current_session_id(latest_session['session_id'])
        
        print(result)

if __name__ == "__main__":
    main()