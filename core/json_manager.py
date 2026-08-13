######
#
# .json Manager  V1.0 by Elvaerwyn MH_2 2026
# For use in the prop panel plugin for Makehuman 2
#
######

import os
import json

# Saves it relative to your plugin setup directory inside mh2_official_tools
PLUGIN_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JSON_PATH = os.path.join(PLUGIN_DIR, "resource", "props_config.json")

def load_props_manifest():
    """Reads the JSON manifest file or creates an initial fallback configuration if empty"""
    if not os.path.exists(JSON_PATH):
        # Create resource folder directory safely if it does not exist
        os.makedirs(os.path.dirname(JSON_PATH), exist_ok=True)
        default_data = {
            "torch_01": {
                "name": "Fire Magic Torch",
                "type": "EMITTER",
                "mesh_path": "resource/obj3d/torch.obj",
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
