import os
import json
import argparse

CONFIG_DIR = os.path.expanduser("~/.fixter")
VARS_FILE = os.path.join(CONFIG_DIR, "vars.json")

def ensure_config_dir():
    """Ensure the config directory exists"""
    if not os.path.exists(CONFIG_DIR):
        os.makedirs(CONFIG_DIR)

def load_vars():
    """Load variables from the vars file"""
    ensure_config_dir()
    if not os.path.exists(VARS_FILE):
        return {}
    
    try:
        with open(VARS_FILE, 'r') as f:
            return json.load(f)
    except json.JSONDecodeError:
        print("Warning: Variables file corrupted. Starting with empty variables.")
        return {}

def save_vars(vars_dict):
    """Save variables to the vars file"""
    ensure_config_dir()
    with open(VARS_FILE, 'w') as f:
        json.dump(vars_dict, f, indent=2)

def set_var(args):
    """Set a variable with the given name and value"""
    if not args.var_assignment or '=' not in args.var_assignment:
        print("Error: Invalid format. Use 'set var=value'")
        return
    
    name, value = args.var_assignment.split('=', 1)
    name = name.strip()
    value = value.strip()
    
    if not name:
        print("Error: Variable name cannot be empty")
        return
    
    vars_dict = load_vars()
    vars_dict[name] = value
    save_vars(vars_dict)
    print(f"Variable '{name}' set to '{value}'")

def get_var(args):
    """Get the value of a variable"""
    name = args.var_name
    vars_dict = load_vars()
    
    if name in vars_dict:
        print(f"{name}: {vars_dict[name]}")
    else:
        print(f"Variable '{name}' not found")

def list_vars(args):
    """List all variables"""
    vars_dict = load_vars()
    
    if not vars_dict:
        print("No variables set")
        return
    
    print("Current variables:")
    for name, value in vars_dict.items():
        print(f"{name}: {value}")

def interpolate_vars(text):
    """Replace {var} placeholders with their values"""
    vars_dict = load_vars()
    
    import re
    def replace_var(match):
        var_name = match.group(1)
        return vars_dict.get(var_name, match.group(0))
    
    return re.sub(r'\{(\w+)\}', replace_var, text)

def add_variable_commands(subparsers):
    set_parser = subparsers.add_parser('set', help='Set a variable')
    set_parser.add_argument('var_assignment', help='Variable assignment in format var=value')
    set_parser.set_defaults(func=set_var)
    
    get_parser = subparsers.add_parser('get', help='Get a variable value')
    get_parser.add_argument('var_name', help='Variable name to retrieve')
    get_parser.set_defaults(func=get_var)
    
    list_parser = subparsers.add_parser('vars', help='List all variables', aliases=['list-vars'])
    list_parser.set_defaults(func=list_vars)