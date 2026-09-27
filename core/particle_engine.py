######
#
# Particle Engine for the Emitter system in Prop Panel V1.8
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
        """Processes position updates dynamically, pulling variables right off the running object state instead of forcing rigid JSON disk lookups!"""
        current_time = time.time()
        raw_dt = current_time - self.last_update_tick
        
        if raw_dt > 0.1:
            raw_dt = 0.033 
            
        self.last_update_tick = current_time
        dt = max(0.016, min(0.033, raw_dt))

        for prop in active_props_list:
            prop_id = getattr(prop, 'prop_id', None)
            if not prop_id:
                raw_name = getattr(prop, 'name', '')
                if not raw_name:
                    continue
                prop_id = raw_name.replace("prop_", "").strip().lower()
            else:
                prop_id = str(prop_id).strip().lower()

            p_emitter = getattr(prop, 'emitter', None)
            if p_emitter is None:
                continue

            if prop_id not in self.emitter_pools:
                self.emitter_pools[prop_id] = []

            is_emitting = getattr(prop, 'is_emitting', True)

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
                    flat_pos[i] = float(native_list[i])
            except Exception:
                flat_pos = [0.0, 0.814, 0.0]

            # 1. Fetch values directly from live UI mixers instead of falling back to constants
            gx = float(getattr(prop, 'mixer_grav_x_value', 0.0))
            gy = float(getattr(prop, 'mixer_grav_y_value', -2.5))
            gz = 0.0

            # Access initial speed configurations out of the active JSON profiles securely
            s_min = 1.5
            s_max = 4.5
            if p_emitter:
                s_min = float(getattr(p_emitter, 'speed_min', s_min))
                s_max = float(getattr(p_emitter, 'speed_max', s_max))

            # Fetch active conical spray angles natively
            spread_angle = float(getattr(prop, 'mixer_spread_angle_value', 15.0))
            rad_spread = np.radians(spread_angle)

            # 2. Spawn point generator loop handles both tracking channels smoothly
            if is_emitting and len(self.emitter_pools[prop_id]) < int(p_emitter.max_particles):
                # Calculate system burst rates dynamically based on limits
                burst_count = 4 if int(p_emitter.max_particles) > 300 else 2
                
                for _ in range(burst_count): 
                    # Calculate vector spreads matching your conical angle parameters
                    angle_offset = random.uniform(-rad_spread, rad_spread)
                    vx = random.uniform(-0.5, 0.5) + np.sin(angle_offset) * s_min
                    vy = random.uniform(s_min, s_max)
                    vz = random.uniform(-0.5, 0.5)

                    if gy < -5.0:  # Active high-gravity downward flow selector (Shower Mode)
                        vy = random.uniform(-s_max, -s_min)
                        
                    self.emitter_pools[prop_id].append({
                        "pos": [float(flat_pos[0]), float(flat_pos[1]), float(flat_pos[2])],
                        "vel": np.array([vx, vy, vz], dtype=np.float32),
                        "age": 0.0,
                        "life": random.uniform(0.6, getattr(p_emitter, 'particle_lifespan_limit', 1.5))
                    })


            # 3. Iterate physics and apply gravity vectors dynamically
            for p in self.emitter_pools[prop_id]:
                p["age"] += dt
                p["pos"] += p["vel"] * dt  
                p["vel"][0] += gx * dt
                p["vel"][1] += gy * dt
                p["vel"][2] += gz * dt

            # 4. Clean spent data components out of memory allocations
            self.emitter_pools[prop_id] = [p for p in self.emitter_pools[prop_id] if p["age"] < p["life"]]

            # 5. Flatten the coordinates directly for the shader pipeline
            flat_vertices = []
            for p in self.emitter_pools[prop_id]:
                flat_vertices.extend([float(p["pos"][0]), float(p["pos"][1]), float(p["pos"][2])])
            p_emitter.particles = flat_vertices

    def extract_flat_vertex_array(self, prop_id):
        """
        UNIVERSAL BRIDGE:
        Tracks down particle pools by matching any part of the active asset ID string 
        case-insensitively, bridging manifest lookup keys to long string panel names safely!
        """
        target_key = str(prop_id).replace("prop_", "").strip().lower()
        
        pool = self.emitter_pools.get(target_key, None)
        
        # THE LOOKUP VALVE:
        if pool is None:
            for active_key, active_pool in self.emitter_pools.items():
                clean_active = str(active_key).lower().strip()
                
                # Check both directions to catch cross-talk across all script variants
                if target_key in clean_active or clean_active in target_key or \
                   "circle" in clean_active and target_key == "circle" or \
                   "cloud" in clean_active and target_key == "circle" or \
                   "rain" in clean_active and target_key == "circle":
                    pool = active_pool
                    break
                    
        if pool is None:
            return []
            
        flat_list = []
        for p in pool:
            if isinstance(p, dict) and "pos" in p:
                pos_vec = p["pos"]
                try:
                    if hasattr(pos_vec, '__getitem__') or isinstance(pos_vec, (list, tuple, np.ndarray)):
                        px = float(pos_vec[0])
                        py = float(pos_vec[1])
                        pz = float(pos_vec[2])
                    else:
                        px = py = pz = float(pos_vec)
                    flat_list.extend([px, py, pz])
                except (IndexError, TypeError, ValueError):
                    flat_list.extend([0.0, 0.0, 0.0])
                    
        return flat_list


live_particle_system = PrimitiveParticleEngine()
