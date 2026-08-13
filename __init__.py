"""
Prop Studio & Stage Wing Expansion Tool
Official decoupled standalone workspace environment suite for MakeHuman 2.
"""
__version__ = "2.1.0"
__author__ = "Elvaerwyn_MH2"

import sys
import os
import json

_root = os.path.dirname(os.path.abspath(__file__))
if _root not in sys.path:
    sys.path.insert(0, _root)

from .gui.prop_module import initialize_prop_studio

def load_local_props_manifest():
    """
    Safely reads your raw data file out of your local data/ folder.
    Returns a blank dictionary fallback if the file is missing or contains a syntax typo.
    """
    json_path = os.path.join(_root, "data", "props_config.json")
    if not os.path.exists(json_path):
        print(f"[Prop Studio Core] WARNING: Target data path not found at {json_path}")
        return {}
    try:
        with open(json_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"[Prop Studio Core] ERROR parsing JSON configurations: {e}")
        return {}

def initialize_extension(app_reference, glob_reference):
    """
    Fires automatically when the extension loader hooks the plugin checkbox.
    Routes system variables safely through verified local package directories.
    """
    print("[Prop Studio Core] Executing native decoupled plugin initialization sequence...")
    
    # 1. Load your editable configurations array right at the runtime entry point
    props_manifest = load_local_props_manifest()
    
    # 2. Pass the data manifest into your studio constructor alongside your app references
    return initialize_prop_studio(app_reference, glob_reference, manifest_data=props_manifest)

__all__ = [
    "initialize_prop_studio",
    "initialize_extension",
    "__version__",
    "__author__"
]
