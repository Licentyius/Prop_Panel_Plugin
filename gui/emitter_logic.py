######
#
# Emitter Logic  V1.0 by Elvaerwyn MH_2 2026
# For use in the prop panel plugin for Makehuman 2
#
######

import random
import time

class MH2EmitterObject:
    def __init__(self, name, bone="hand_R"):
        self.name = name
        self.bone = bone
        self.state = 'holding'  # Default state
        
        self.pos = [0.0, 0.0, 0.0]
        self.pool = []
        self.max_pool = 250

    def set_state(self, state_str):
        self.state = state_str

    def process_ticks(self, dt, skeleton_data=None):
        # 1. State positional tracking loops
        if self.state == 'holding' and skeleton_data:
            # Anchor to tracking coordinates matching your rig hierarchy
            self.pos = skeleton_data.get_joint_position(self.bone)
        elif self.state in ['placed', 'arranged']:
            pass # Keep static world coordinates

        # 2. Emission logic loops depending on states
        if self.state in ['holding', 'used']:
            self._emit_particles()

        # Update physical particles arrays
        for p in self.pool:
            p["age"] += dt
            p["coord"][0] += p["velocity"][0] * dt
            p["coord"][1] += p["velocity"][1] * dt  # Velocity up (Y)
            p["coord"][2] += p["velocity"][2] * dt
            p["velocity"][1] -= 2.0 * dt           # Simple internal gravity

        # Delete spent particles
        self.pool = [p for p in self.pool if p["age"] < p["lifetime"]]

    def _emit_particles(self):
        if len(self.pool) < self.max_pool:
            for _ in range(3):
                self.pool.append({
                    "coord": list(self.pos),
                    "velocity": [random.uniform(-0.4, 0.4), random.uniform(1.8, 3.2), random.uniform(-0.4, 0.4)],
                    "age": 0.0,
                    "lifetime": random.uniform(0.5, 1.5)
                })
