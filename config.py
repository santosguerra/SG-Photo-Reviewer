import json
import os

CONFIG_FILE = 'config.json'

DEFAULT_CONFIG = {
    'mount_points': ['/mnt/nvme', '/data1'],
    'destination_folder': 'para-revision',
    'enable_delete_button': False
}

def load_config():
    """Load configuration from JSON file or return defaults"""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading config: {e}")
            return DEFAULT_CONFIG.copy()
    return DEFAULT_CONFIG.copy()

def save_config(config):
    """Save configuration to JSON file"""
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
        return True
    except Exception as e:
        print(f"Error saving config: {e}")
        return False

def is_path_allowed(path, mount_points):
    """Check if path is within allowed mount points (prevent path traversal)"""
    try:
        real_path = os.path.realpath(path)
        for mount_point in mount_points:
            real_mount = os.path.realpath(mount_point)
            if real_path.startswith(real_mount):
                return True
        return False
    except Exception:
        return False
