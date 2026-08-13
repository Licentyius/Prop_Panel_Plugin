####
#
# Particle Engine for the Emitter system in Prop Panel V1.0
# Contributed to Makehuman 2 by Elvaerwyn_MH2 2026
#
####

import random
import time

class PrimitiveParticleEngine:
    def __init__(self):
        # Dictionary linking prop IDs to active live floating point streams
        self.emitter_pools = {}
        self.last_update_tick = time.time()

    def tick_physics(self, active_props_list):
        """Processes position updates and gravity drag on all active emitters."""
        current_time = time.time()
        dt = current_time - self.last_update_tick
        self.last_update_tick = current_time

        # Prevent physics computation spikes over long freezes
        if dt > 0.1: 
            dt = 0.016

        for prop in active_props_list:
            # Only loop math rules if the asset is recognized as an active EMITTER
            if getattr(prop, 'object_type', 'STATIC') != 'EMITTER':
                continue

            prop_id = getattr(prop, 'name', None)
            if not prop_id: 
                continue

            # Ensure an active list exists for this asset key tracker
            if prop_id not in self.emitter_pools:
                self.emitter_pools[prop_id] = []

            # Initialize active configuration variables out of your object limits
            max_particles = getattr(prop, 'max_particles', 200)
            is_emitting = getattr(prop, 'is_emitting', True)
            origin_pos = getattr(prop, 'position', [0.0, 0.0, 0.0])

            # 1. Spawn a burst of new primitive points if emitter isn't blocked
            if is_emitting and len(self.emitter_pools[prop_id]) < max_particles:
                for _ in range(4): # Generation speed rate per frame loop iteration
                    self.emitter_pools[prop_id].append({
                        "pos": [float(origin_pos[0]), float(origin_pos[1]), float(origin_pos[2])],
                        "vel": [random.uniform(-0.4, 0.4), random.uniform(1.5, 3.0), random.uniform(-0.4, 0.4)],
                        "age": 0.0,
                        "life": random.uniform(0.5, 1.5)
                    })

            # 2. Iterate physics and apply downward gravity pull on the Y axis
            for p in self.emitter_pools[prop_id]:
                p["age"] += dt
                p["pos"][0] += p["vel"][0] * dt
                p["pos"][1] += p["vel"][1] * dt  # Rise upwards
                p["pos"][2] += p["vel"][2] * dt
                p["vel"][1] -= 2.0 * dt           # Simple downward gravity pull

            # 3. Clean spent data components out of memory allocations
            self.emitter_pools[prop_id] = [p for p in self.emitter_pools[prop_id] if p["age"] < p["life"]]

    def extract_flat_vertex_array(self, prop_id):
        """Flattens structured dictionaries into sequential coordinates for OpenGL inputs."""
        pool = self.emitter_pools.get(prop_id, [])
        flat_list = []
        for p in pool:
            flat_list.extend(p["pos"])
        return flat_list

# Instantiate a single workspace driver engine
live_particle_system = PrimitiveParticleEngine()
