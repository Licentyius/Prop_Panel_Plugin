######
#
# .json Manager  V1.2 by Elvaerwyn MH_2 2026
# For use in the prop panel plugin for Makehuman 2
#
######

import os
import json

CORE_DIRECTORY_LOCATION = os.path.dirname(os.path.abspath(__file__))

PROP_PANEL_ROOT_DIR = os.path.dirname(CORE_DIRECTORY_LOCATION)

PLUGIN_DIR = os.path.normpath(PROP_PANEL_ROOT_DIR).replace("\\", "/")

JSON_PATH = os.path.join(PLUGIN_DIR, "resource", "props_config.json").replace("\\", "/")

def load_props_manifest():
    """Reads the JSON manifest file or creates an initial fallback configuration if empty"""
    if not os.path.exists(JSON_PATH):
        # Create resource folder directory safely if it does not exist
        os.makedirs(os.path.dirname(JSON_PATH), exist_ok=True)
        default_data = {
            "torch_01": {
                "name": "Fallback Magic Item",
                "type": "EMITTER",
                "mesh_path": "data/props/cone.obj",
                "is_mesh_visible": True,
                "particle_count": 250,
                "color_rgba": [1.0, 0.4, 0.0, 1.0]
            }
        }
        with open(JSON_PATH, 'w') as f:
            json.dump(default_data, f, indent=4)
        return default_data

    with open(JSON_PATH, 'r') as f:
        return json.load(f)

def update_prop_json_entry(prop_id, update_dict):
    """Saves edited modifications directly back to disk from the MH2 workspace UI"""
    current_data = load_props_manifest()
    if prop_id in current_data:
        current_data[prop_id].update(update_dict)
        with open(JSON_PATH, 'w') as f:
            json.dump(current_data, f, indent=4)

def load_individual_asset_json(mesh_path_string):
    """
    Dynamically searches for a standalone companion .json file right next to 
    the loaded .obj model mesh anywhere on your hard drive natively!
    """
    if not mesh_path_string:
        return None
        
    # Standardize the file separators to prevent OS path desynchronization splits
    clean_mesh_path = os.path.normpath(mesh_path_string).replace("\\", "/")
    target_json_path = str(clean_mesh_path).replace(".obj", ".json")
    
    if os.path.isfile(target_json_path):
        try:
            with open(target_json_path, 'r', encoding='utf-8') as f:
                raw_data = json.load(f)
                if isinstance(raw_data, dict):
                    print(f"[Prop Dynamic JSON] Successfully loaded standalone companion: {target_json_path}")
                    return raw_data
        except Exception as e:
            print(f"[Prop Dynamic JSON Warning] Failed to parse separate file '{target_json_path}': {e}")
            
    return None
