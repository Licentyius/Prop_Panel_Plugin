####
#
# Particle Engine for the Emitter system in Prop Panel V1.2
# Contributed to Makehuman 2 by Elvaerwyn_MH2 2026
#
####

import random
import time
import numpy as np

class PrimitiveParticleEngine:
    def __init__(self):
        # Dictionary linking prop IDs to active live floating point streams
        self.emitter_pools = {}
        self.last_update_tick = time.time()

    def tick_physics(self, active_props_list):
        """Processes position updates and gravity drag on all active emitters."""
        current_time = time.time()
        raw_dt = current_time - self.last_update_tick
        self.last_update_tick = current_time

        # Stable fixed physics timestep gating
        dt = max(0.016, min(0.033, raw_dt))

        for prop in active_props_list:
            # Only loop math rules if the asset is recognized as an active EMITTER
            obj_type = getattr(prop, 'object_type', getattr(prop, 'type', 'STATIC'))
            if str(obj_type).upper() != 'EMITTER':
                continue

            prop_id = getattr(prop, 'name', None)
            if not prop_id: 
                continue

            # Ensure an active list exists for this asset key tracker
            if prop_id not in self.emitter_pools:
                self.emitter_pools[prop_id] = []

            max_particles = getattr(prop, 'max_particles', 200)
            is_emitting = getattr(prop, 'is_emitting', True)
            
            # Fetch the raw position tracker variable safely
            origin_pos = getattr(prop, 'position', [0.0, 0.0, 0.0])

            flat_pos = [0.0, 0.0, 0.0]
            try:
                if hasattr(origin_pos, 'tolist'):
                    # Natively handle and convert any variant of NumPy array maps
                    native_list = origin_pos.tolist()
                else:
                    native_list = list(origin_pos) if hasattr(origin_pos, '__iter__') else [origin_pos]
                
                # Unpack up to 3 individual scalar channels sequentially 
                for i in range(min(3, len(native_list))):
                    item = native_list[i]
                    # Handle nested float sequences safely if packed inside matrix arrays
                    if isinstance(item, (list, tuple, np.ndarray)) and len(item) > 0:
                        flat_pos[i] = float(item[0])
                    else:
                        flat_pos[i] = float(item)
            except Exception as e:
                print(f"[Prop Engine Warning] Positional extraction loop fallback: {e}")
                flat_pos = [0.0, 0.0, 0.0]

            # 1. Spawn a burst of new primitive points if emitter isn't blocked
            if is_emitting and len(self.emitter_pools[prop_id]) < int(max_particles):
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
                
                # AXIS INDICES: Explicitly segment 0, 1, and 2
                # so that X, Y, and Z can compute separate movement offsets
                p["pos"][0] += p["vel"][0] * dt  # X Axis translates outward
                p["pos"][1] += p["vel"][1] * dt  # Y Axis RISES UPWARD
                p["pos"][2] += p["vel"][2] * dt  # Z Axis translates outward
                
                # Apply stable gravity downward velocity pull strictly onto the Y axis channel vector
                p["vel"][1] -= 2.5 * dt 

            # 3. Clean spent data components out of memory allocations
            self.emitter_pools[prop_id] = [p for p in self.emitter_pools[prop_id] if p["age"] < p["life"]]

    def extract_flat_vertex_array(self, prop_id):
        """Flattens structured dictionaries into sequential coordinates for OpenGL inputs."""
        pool = self.emitter_pools.get(prop_id, [])
        flat_list = []
        
        for p in pool:
            if isinstance(p, dict) and "pos" in p:
                pos_vec = p["pos"]

                try:
                    # Explicitly extract each index channel as a separate float string parameter
                    x = float(pos_vec[0])
                    y = float(pos_vec[1])
                    z = float(pos_vec[2])

                    flat_list.extend([x, y, z])
                except (IndexError, TypeError, ValueError):
                    # Fail silently to a baseline floor point if any index slips out of scope
                    flat_list.extend([0.0, 0.0, 0.0])
                    
        return flat_list


# Instantiate a single workspace driver engine
live_particle_system = PrimitiveParticleEngine()
