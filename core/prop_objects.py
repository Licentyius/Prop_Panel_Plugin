######
#
# Prop objects(structural metadata)  V1.0 Elvaerwyn_MH2 2026
# For use in the prop panel plugin for Makehuman 2
#
######

import numpy as np
import os
from obj3d.object3d import object3d
from opengl.buffers import OpenGlBuffers, RenderedObject

class PropObject:
    """Represents the metadata and structural transformation tracks of a scene prop."""
    def __init__(self, name, glob):
        self.glob = glob
        self.env = getattr(glob, 'env', None)
        self.name = name
        self._name = "prop_" + name
        
        self.visible = True
        self.is_mesh_visible = True
        self.is_emitting = False
        self.object_type = "STATIC"
        self.type = "STATIC"
        
        self.parent_bone = "None" 
        self.use_parenting = False
        self.local_offset_pos = np.array([0.0, 0.0, 0.0], dtype=np.float64)
        self.path = ""
        self.mesh_reference = None 
        self.material_path = ""    
        self.emitter = None             

        self.position = [0.0, 0.0, 0.0]
        self.rotation = [0.0, 0.0, 0.0] 
        self.scale = [1.0, 1.0, 1.0]
        self.max_particles = 300
        self.particle_draw_size = 16.0

    def set_transform(self, pos=None, rot=None, scl=None):
        """Sets raw 3D transformations and shatters the culling cage up to 50m."""
        if pos is not None: 
            self.position = np.array(pos, dtype=float)
            if hasattr(self, 'mesh_reference') and self.mesh_reference:
                mesh_container = getattr(self.mesh_reference, 'obj', None)
                if mesh_container and hasattr(mesh_container, 'bounds') and mesh_container.bounds:
                    mesh_container.bounds.min_x, mesh_container.bounds.max_x = -50.0, 50.0
                    mesh_container.bounds.min_y, mesh_container.bounds.max_y = -5.0,  50.0 
                    mesh_container.bounds.min_z, mesh_container.bounds.max_z = -50.0, 50.0

        if rot is not None: self.rotation = np.array(rot, dtype=float)
        if scl is not None: self.scale = np.array(scl, dtype=float)

    def set_visibility(self, vis):
        self.visible = vis
        self.is_mesh_visible = vis
