######
#
# Particle Engine for the Emitter system in Prop Panel V1.5
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
        """Processes position updates and gravity drag on all active emitters without pause jumps."""
        current_time = time.time()
        raw_dt = current_time - self.last_update_tick
        
        # =======================
        # 🛠️ THE PAUSE GAUNTLET:
        # =======================
        if raw_dt > 0.1:
            raw_dt = 0.033 # Treat the first frame back like a standard tick fraction
            
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

            from mh2_official_tools.prop_panel.core.json_manager import load_props_manifest
            manifest = load_props_manifest()
            asset_config = manifest.get(prop_id, {})
            physics_block = asset_config.get("physics", {})
            

            gx = 0.0
            gy = -2.5
            gz = 0.0
            s_min = 1.8
            s_max = 3.5

            if p_emitter and hasattr(prop, 'emitter') and prop.emitter:
                # Read the active runtime configuration variables directly from the object
                physics_config = getattr(prop.emitter, 'physics', {})
                if isinstance(physics_config, dict):
                    # Extract velocity values
                    speed_limits = physics_config.get("initialSpeed", {})
                    s_min = float(speed_limits.get("min", s_min))
                    s_max = float(speed_limits.get("max", s_max))
                    
                    # Extract gravity vectors
                    grav_forces = physics_config.get("gravity", {})
                    gx = float(grav_forces.get("x", gx))
                    gy = float(grav_forces.get("y", gy))
                    gz = float(grav_forces.get("z", gz))


            # 1. Spawn points utilizing your dynamic speed entries natively
            if is_emitting and len(self.emitter_pools[prop_id]) < int(p_emitter.max_particles):
                for _ in range(4): 
                    # If the json gravity is highly negative (like rain), shoot particles down natively!
                    y_speed = random.uniform(-s_max, -s_min) if gy < -5.0 else random.uniform(s_min, s_max)
                    
                    self.emitter_pools[prop_id].append({
                        "pos": [float(flat_pos[0]), float(flat_pos[1]), float(flat_pos[2])],
                        "vel": np.array([random.uniform(-0.5, 0.5), y_speed, random.uniform(-0.5, 0.5)], dtype=np.float32),
                        "age": 0.0,
                        "life": random.uniform(1.2, 2.5) if gy < -5.0 else random.uniform(0.6, 1.8)
                    })

            # 2. Iterate physics and apply gravity vectors dynamically
            for p in self.emitter_pools[prop_id]:
                p["age"] += dt
                p["pos"][0] += p["vel"][0] * dt  
                p["pos"][1] += p["vel"][1] * dt  
                p["pos"][2] += p["vel"][2] * dt  
                
                # Apply the true gravity parameters directly from a JSON configuration!
                p["vel"][0] += gx * dt
                p["vel"][1] += gy * dt
                p["vel"][2] += gz * dt

            # 3. Clean spent data components out of memory allocations
            self.emitter_pools[prop_id] = [p for p in self.emitter_pools[prop_id] if p["age"] < p["life"]]


    def extract_flat_vertex_array(self, prop_id):
        """
        UNIVERSAL BRIDGE:
        Tracks down particle pools by matching any part of the active asset ID string 
        case-insensitively. 
        """
        target_key = str(prop_id).replace("prop_", "").strip().lower()
        
        pool = self.emitter_pools.get(target_key, None)
        if pool is None:
            # Universal loop tracks down tools by checking partial text string keys natively
            for active_key, active_pool in self.emitter_pools.items():
                if target_key in active_key.lower() or active_key.lower() in target_key:
                    pool = active_pool
                    break
                    
        if pool is None:
            return []
            
        flat_list = []
        for p in pool:
            if isinstance(p, dict) and "pos" in p:
                pos_vec = p["pos"]
                try:
                    # Protects against scalar array indexing loops safely
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
