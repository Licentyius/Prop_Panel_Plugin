######
#
# Particle Engine for the Emitter system in Prop Panel V1.4
# Contributed to Makehuman 2 by Elvaerwyn_MH2 2026
#
######

import random
import time
import numpy as np

class PrimitiveParticleEngine:
    def __init__(self):
        self.emitter_pools = {}
        self.last_update_tick = time.time()

    def tick_physics(self, active_props_list):
        """Processes position updates and gravity drag on all active emitters."""
        current_time = time.time()
        raw_dt = current_time - self.last_update_tick
        self.last_update_tick = current_time

        dt = max(0.016, min(0.033, raw_dt))

        for prop in active_props_list:

            raw_name = getattr(prop, 'name', '')
            if not raw_name:
                continue
                
            # Safely unify the key string across all framework scripts
            prop_id = raw_name.replace("prop_", "").strip().lower()
            p_emitter = getattr(prop, 'emitter', None)

            if p_emitter is None:
                continue

            if prop_id not in self.emitter_pools:
                self.emitter_pools[prop_id] = []

            is_emitting = getattr(prop, 'is_emitting', True)


            # TARGET ANCHOR: Check if parented to read live hand joint translations
            origin_pos = getattr(prop, 'position', [0.0, 0.0, 0.0])
            if getattr(prop, 'use_parenting', False) and getattr(prop, 'parent_bone', 'None') != "None":
                m = getattr(prop, 'runtime_gl_matrix', None)
                if m is not None and len(m) >= 16:
                    origin_pos = [float(m[12]), float(m[13]), float(m[14])]

            flat_pos = [0.0, 0.0, 0.0]
            try:
                if hasattr(origin_pos, 'tolist'):
                    native_list = origin_pos.tolist()
                else:
                    native_list = list(origin_pos) if hasattr(origin_pos, '__iter__') else [origin_pos]
                
                for i in range(min(3, len(native_list))):
                    item = native_list[i]
                    if isinstance(item, (list, tuple, np.ndarray)) and len(item) > 0:
                        flat_pos[i] = float(item[0])
                    else:
                        flat_pos[i] = float(item)
            except Exception as e:
                print(f"[Prop Engine Warning] Positional extraction loop fallback: {e}")
                flat_pos = [0.0, 0.0, 0.0]

            # 1. Spawn points
            if is_emitting and len(self.emitter_pools[prop_id]) < int(p_emitter.max_particles):
                for _ in range(4): 
                    self.emitter_pools[prop_id].append({
                        "pos": [float(flat_pos[0]), float(flat_pos[1]), float(flat_pos[2])],
                        "vel": np.array([random.uniform(-0.5, 0.5), random.uniform(1.8, 3.5), random.uniform(-0.5, 0.5)], dtype=np.float32),
                        "age": 0.0,
                        "life": random.uniform(0.6, 1.8)
                    })

            # 2. Iterate physics and apply downward gravity pull on the Y axis
            for p in self.emitter_pools[prop_id]:
                p["age"] += dt
                p["pos"][0] += p["vel"][0] * dt  
                p["pos"][1] += p["vel"][1] * dt  
                p["pos"][2] += p["vel"][2] * dt  
                p["vel"][1] -= 2.5 * dt 

            # 3. Clean spent data components out of memory allocations
            self.emitter_pools[prop_id] = [p for p in self.emitter_pools[prop_id] if p["age"] < p["life"]]

    def extract_flat_vertex_array(self, prop_id):
        """Flattens structured dictionaries into sequential coordinates for OpenGL inputs."""
        # Unify the target string layout case-insensitively
        clean_key = str(prop_id).replace("prop_", "").strip().lower()
        
        pool = self.emitter_pools.get(clean_key, [])
        flat_list = []
        
        for p in pool:
            if isinstance(p, dict) and "pos" in p:
                pos_vec = p["pos"]
                try:
                    x = float(pos_vec[0])
                    y = float(pos_vec[1])
                    z = float(pos_vec[2])
                    flat_list.extend([x, y, z])
                except (IndexError, TypeError, ValueError):
                    flat_list.extend([0.0, 0.0, 0.0])
                    
        return flat_list


live_particle_system = PrimitiveParticleEngine()
