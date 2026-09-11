######
#
# Emitter Prop object type V1.1 by Elvaerwyn MH_2 2026
# For use in the prop panel plugin for Makehuman 2
#
######

import random
import time
import numpy as np

class MH2LiveEmitterProp:
    def __init__(self, prop_id, raw_json_data):
        """
        Initializes an explicit Emitter Prop by map-matching 
        the raw attributes directly out of your JSON file.
        """
        self.prop_id = prop_id
        if raw_json_data is None:
            raw_json_data = {}
            
        print("emitter init", prop_id)
        
        self.name = raw_json_data.get("name", "Unnamed Emitter")
        self.mesh_path = raw_json_data.get("mesh_path", "")
        self.is_mesh_visible = raw_json_data.get("is_mesh_visible", True)
        self.max_particles = raw_json_data.get("particle_count", 300)
        self.particle_color = raw_json_data.get("color_rgba", raw_json_data.get("particle_color", [1.0, 1.0, 1.0, 1.0]))
        self.default_bone = raw_json_data.get("default_bone", "hand_R")
        
        # New Explicit Emitter Type Gate Parameter Target Link:
        # OPTIONS: "PARTICLES", "SPRITES", "TEXTURED_SPRITES", "PHYSICAL_MESH"
        self.emitter_mode = raw_json_data.get("emitter_mode", "PARTICLES").upper().strip()
        self.particle_texture = raw_json_data.get("particle_texture", "PLAIN")
        self.particle_draw_size = float(raw_json_data.get("particle_draw_size", 6.0))
        
        # Running Architecture Parameters
        self.state = 'holding'  # holding, placed, arranged, used
        self.world_position = [0.0, 0.0, 0.0]
        self.world_matrix = None 
        self.mesh_buffers = None  
        
        # Simulation Memory Allocations
        self.particles_pool = []    
        self.particles = []

class MH2PropParticle:
    """A single particle element spawned by an emitter prop module."""
    def __init__(self, origin_pos, color=None, mesh_ref=None):
        self.x = float(origin_pos[0])
        self.y = float(origin_pos[1])
        self.z = float(origin_pos[2])
        
        # Random vector dispersion trajectory calculation assignments
        self.vx = random.uniform(-0.3, 0.3)
        self.vy = random.uniform(1.2, 2.5)
        self.vz = random.uniform(-0.3, 0.3)

        # Retain independent transformations matrix for physical mesh instancing copies
        self.rotation = [random.uniform(0, 360), random.uniform(0, 360), random.uniform(0, 360)]
        self.scale = [1.0, 1.0, 1.0]
        self.mesh_ref = mesh_ref # Holds pointer to physical PropMesh context

        raw_color = color
        if hasattr(color, 'color_rgba'):
            raw_color = color.color_rgba
        elif hasattr(color, 'particle_color'):
            raw_color = color.particle_color

        if isinstance(raw_color, (list, tuple)) and len(raw_color) >= 3:
            self.color = [float(c) for c in raw_color[:4]]
            if len(self.color) == 3:
                self.color.append(1.0)
        else:
            self.color = [1.0, 0.4, 0.0, 1.0]

        self.lifetime = 0.0
        self.lifespan = random.uniform(0.6, 1.5)

    def is_dead(self):
        return self.lifetime > self.lifespan

    def update(self, span):
        self.lifetime += span
        self.x += self.vx * span  
        self.y += self.vy * span  
        self.z += self.vz * span  
        
        # Apply stable down-axis gravity velocity pull calculations over time frames
        self.vy -= 2.5 * span

