######
#
# Particle Engine for the Emitter system in Prop Panel V1.7
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
        """Processes position updates and gravity drag on all active emitters dynamically without hardcoded fallback overrides."""
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
                    item = native_list[i]
                    if isinstance(item, (list, tuple, np.ndarray)) and len(item) > 0:
                        flat_pos[i] = float(item[0])
                    else:
                        flat_pos[i] = float(item)
            except Exception:
                flat_pos = [0.0, 0.0, 0.0]

            from mh2_official_tools.prop_panel.core.json_manager import load_props_manifest
            manifest = load_props_manifest()
            asset_config = manifest.get(prop_id, {})
            physics_block = asset_config.get("physics", {})

            gx, gy, gz = 0.0, -2.5, 0.0
            s_min, s_max = 1.8, 3.5

            # Establish baseline falling physics defaults natively
            gx = 0.0
            gy = -2.5
            gz = 0.0
            s_min = 1.8
            s_max = 3.5

            if p_emitter and hasattr(prop, 'emitter') and prop.emitter:
                # THE SYNC PLUG: Prioritize the flat list variable where the UI sliders write data!
                # This instantly bridges the live Mixer EQ sliders to ANY current or future JSON asset dynamically.
                live_grav = getattr(prop.emitter, 'gravity', None)
                if isinstance(live_grav, (list, tuple, np.ndarray)) and len(live_grav) >= 3:
                    gx = float(live_grav[0])
                    gy = float(live_grav[1])
                    gz = float(live_grav[2])
                else:
                    # Original pass preserves the default nested JSON manifest layers cleanly if no slider is dragged
                    if isinstance(physics_block, dict) and "gravity" in physics_block:
                        grav_forces = physics_block.get("gravity", {})
                        if isinstance(grav_forces, dict):
                            gx = float(grav_forces.get("x", gx))
                            gy = float(grav_forces.get("y", gy))
                            gz = float(grav_forces.get("z", gz))

                # Extract initial velocity parameters safely out of active configurations
                if isinstance(physics_block, dict) and "initialSpeed" in physics_block:
                    speed_limits = physics_block.get("initialSpeed", {})
                    if isinstance(speed_limits, dict):
                        s_min = float(speed_limits.get("min", s_min))
                        s_max = float(speed_limits.get("max", s_max))


            # 1. Spawn points utilizing the dynamic speed entries natively
            if is_emitting and len(self.emitter_pools[prop_id]) < int(p_emitter.max_particles):
                for _ in range(4): 
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
                
                p["vel"][0] += gx * dt
                p["vel"][1] += gy * dt
                p["vel"][2] += gz * dt

            # 3. Clean spent data components out of memory allocations
            self.emitter_pools[prop_id] = [p for p in self.emitter_pools[prop_id] if p["age"] < p["life"]]

            # 4. UNIFIED TIMELINE EXPORT VALVE:
            flat_vertices = []
            for p in self.emitter_pools[prop_id]:
                flat_vertices.extend([float(p["pos"][0]), float(p["pos"][1]), float(p["pos"][2])])
            prop.emitter.particles = flat_vertices


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
