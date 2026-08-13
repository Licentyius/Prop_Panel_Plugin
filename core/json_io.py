import os
import json

# Tracks the root folder of your standalone plugin directory
PLUGIN_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JSON_PATH = os.path.join(PLUGIN_ROOT, "data", "props_config.json")

def save_prop_changes_to_json(prop_id, incoming_updates):
    """
    Reads your raw props data, updates specific key values 
    on the fly, and dumps it right back into the file.
    """
    # Safety check: Ensure the file exists before attempting to read it
    if not os.path.exists(JSON_PATH):
        return

    # 1. Read existing raw configuration map from disk
    with open(JSON_PATH, 'r') as file_reader:
        current_data = json.load(file_reader)

    # 2. Apply modifications to the targeted prop entry dictionary
    if prop_id in current_data:
        current_data[prop_id].update(incoming_updates)

        # 3. Securely overwrite the file with the clean updated layout
        with open(JSON_PATH, 'w') as file_writer:
            json.dump(current_data, file_writer, indent=4)
