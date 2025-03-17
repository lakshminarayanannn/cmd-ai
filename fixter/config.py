
import os
import json

CONFIG_DIR = os.path.expanduser("~/.fixter")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config")
AI_CONFIG_FILE = os.path.join(CONFIG_DIR, "aiconfig")
EXTRACTIONS_DIR = os.path.join(CONFIG_DIR, "extractions")
SESSIONS_DIR = os.path.join(CONFIG_DIR, "sessions")

def ensure_config_dirs():
    """Create all necessary configuration directories"""
    for directory in [CONFIG_DIR, EXTRACTIONS_DIR, SESSIONS_DIR]:
        os.makedirs(directory, exist_ok=True)

def load_config():
    """Load the main configuration file"""
    ensure_config_dirs()
    
    if not os.path.exists(CONFIG_FILE):
        default_config = {
            "master_folder": os.path.join(CONFIG_DIR, "workspace"),
            "default_model": "gpt-4o-mini",
            "default_temperature": 0,
            "max_history": 20
        }
        save_config(default_config)
        return default_config
    
    try:
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    except json.JSONDecodeError:
        default_config = {
            "master_folder": os.path.join(CONFIG_DIR, "workspace"),
            "default_model": "gpt-4o-mini",
            "default_temperature": 0,
            "max_history": 20
        }
        save_config(default_config)
        return default_config

def save_config(config):
    """Save configuration to the config file"""
    ensure_config_dirs()
    
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)

def get_master_folder():
    """Get the configured master folder, creating it if necessary"""
    config = load_config()
    master_folder = config.get("master_folder", os.path.join(CONFIG_DIR, "workspace"))
    
    os.makedirs(master_folder, exist_ok=True)
    os.makedirs(os.path.join(master_folder, "extractions"), exist_ok=True)
    os.makedirs(os.path.join(master_folder, "local_cloned"), exist_ok=True)
    
    return master_folder

def set_master_folder(path):
    """Set the master folder to a new path"""
    config = load_config()
    config["master_folder"] = os.path.expanduser(path)
    save_config(config)
    
    os.makedirs(os.path.join(config["master_folder"], "extractions"), exist_ok=True)
    os.makedirs(os.path.join(config["master_folder"], "local_cloned"), exist_ok=True)
    
    return config["master_folder"]