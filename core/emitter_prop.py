######
#
# Emitter Prop object type V1.0 by Elvaerwyn MH_2 2026
# For use in the prop panel plugin for Makehuman 2
#
######

import random
import time

class MH2LiveEmitterProp:
    def __init__(self, prop_id, raw_json_data):
        """
        Initializes an explicit Emitter Prop by map-matching 
        the raw attributes directly out of your JSON file.
        """
        self.prop_id = prop_id
        
        # Raw Data Parameter Mapping Match
        self.name = raw_json_data.get("name", "Unnamed Emitter")
        self.mesh_path = raw_json_data.get("mesh_path", "")
        self.is_mesh_visible = raw_json_data.get("is_mesh_visible", True)
        self.max_particles = raw_json_data.get("particle_count", 300)
        self.particle_color = raw_json_data.get("particle_color", [1.0, 1.0, 1.0, 1.0])
        self.default_bone = raw_json_data.get("default_bone", "hand_R")
        
        # Running Architecture Parameters
        self.state = 'holding'  # holding, placed, arranged, used
        self.world_position = [0.0, 0.0, 0.0]
        self.world_matrix = None # Assigned dynamically by viewport steps
        self.mesh_buffers = None  # Populated when an .obj is actively drawn
        
        # Simulation Allocations
        self.particles = []
