#######
## Multi-Prop V2.0
## Part of the MakeHuman 2 Project contributed by Elvaerwyn_MH2 2026
#######

from PySide6.QtGui import QMatrix4x4, QVector3D, QVector4D
import OpenGL
from OpenGL import GL as gl
import numpy as np
import random

class Multi_Prop():
    """
    Manages active non-deforming static props, socket attachment transformations,
    and coordinates rendering states via direct injection into the OpenGL draw loops.
    """
    def __init__(self, shaders, glob):
        self.glob = glob
        self.shaders = shaders
        
        self.fixcolor = shaders.getShader("fixcolor") if shaders else None
        self.phong = shaders.getShader("phong") if shaders else None
        self.pbr = shaders.getShader("pbr") if shaders else None
        
        self.active_props = {} 
        self.show_bounding_boxes = False
        self.fallback_color = QVector4D(1.0, 0.0, 0.0, 1.0)
        
        self.fromGlobal(False)

    def fromGlobal(self, load_json):
        if load_json and hasattr(self.glob, 'readShaderInitJSON'):
            pass
        self.setShader()

    def toGlobal(self):
        pass

    def setShader(self):
        for shader in [self.phong, self.pbr]:
            if shader and self.shaders:
                self.shaders.bindShader(shader)

    def registerProp(self, asset_id, obj_mesh, parent_bone="None", relative_transform=None):
        if relative_transform is None:
            relative_transform = {
                "translation": [0.0, 0.0, 0.0],
                "rotation": [0.0, 0.0, 0.0],
                "scale": [1.0, 1.0, 1.0]
            }
            
        t_block = {}
        for key in ["translation", "rotation", "scale"]:
            val = relative_transform.get(key, [0.0, 0.0, 0.0] if key != "scale" else [1.0, 1.0, 1.0])
            if isinstance(val, (list, tuple, np.ndarray)):
                if len(val) >= 3: 
                    t_block[key] = [float(val[0]), float(val[1]), float(val[2])]
                elif len(val) == 1: 
                    t_block[key] = [float(val[0])] * 3
                else: 
                    t_block[key] = [0.0, 0.0, 0.0] if key != "scale" else [1.0, 1.0, 1.0]
            else:
                t_block[key] = [float(val)] * 3
                
        self.active_props[asset_id] = {
            "obj": obj_mesh,
            "parent_bone": parent_bone,
            "transform": t_block,
            "visible": True
        }

    def unregisterProp(self, asset_id):
        if asset_id in self.active_props:
            del self.active_props[asset_id]

    def clearAllProps(self):
        """Clears active dictionary AND synchronizes global list to wipe scene clean."""
        self.active_props.clear()
        if hasattr(self.glob, 'custom_props_list') and self.glob.custom_props_list is not None:
            self.glob.custom_props_list.clear()
        if hasattr(self.glob, 'selected_prop_node'):
            self.glob.selected_prop_node = None

    def updatePropTransform(self, asset_id, translation=None, rotation=None, scale=None):
        if asset_id in self.active_props:
            t_block = self.active_props[asset_id]["transform"]
            if translation is not None:
                t_block["translation"] = [float(translation[0]), float(translation[1]), float(translation[2])] if len(translation) >= 3 else [float(translation)] * 3
            if rotation is not None:
                t_block["rotation"] = [float(rotation[0]), float(rotation[1]), float(rotation[2])] if len(rotation) >= 3 else [float(rotation)] * 3
            if scale is not None:
                t_block["scale"] = [float(scale[0]), float(scale[1]), float(scale[2])] if len(scale) >= 3 else [float(scale[0])] * 3

    def select_prop_by_raycast(self, ray_origin, ray_direction):
        """Finds the closest intersecting bounding container to unlock individual manipulation."""
        custom_props = getattr(self.glob, 'custom_props_list', [])
        closest_prop = None
        min_dist = float('inf')
        
        for prop_data in custom_props:
            if not prop_data or not hasattr(prop_data, 'position'):
                continue
            
            p_pos = np.array(prop_data.position, dtype=np.float32)
            ray_org_np = np.array([ray_origin.x(), ray_origin.y(), ray_origin.z()], dtype=np.float32)
            vec_to_prop = p_pos - ray_org_np
            ray_dir_np = np.array([ray_direction.x(), ray_direction.y(), ray_direction.z()], dtype=np.float32)
            
            projection = np.dot(vec_to_prop, ray_dir_np)
            if projection < 0:
                continue
                
            closest_point = ray_org_np + ray_dir_np * projection
            dist_to_ray = np.linalg.norm(closest_point - p_pos)
            
            bounds_threshold = float(prop_data.scale[0]) * 1.5 if hasattr(prop_data, 'scale') else 1.5
            if dist_to_ray < bounds_threshold:
                if projection < min_dist:
                    min_dist = projection
                    closest_prop = prop_data
                    
        if closest_prop:
            self.glob.selected_prop_node = closest_prop
            print(f"[Engine picking] Selected prop updated successfully: {closest_prop.name}")
            return closest_prop
        return None

    def drawProps(self, proj_view_matrix, campos, light_obj):
        """Coordinates rendering states via direct injection into the OpenGL draw loops."""
        custom_props = getattr(self.glob, 'custom_props_list', [])
        if len(self.active_props) > 0 and custom_props:
            bc = getattr(self.glob, 'baseClass', None)
            
            for prop_data in custom_props:
                if not prop_data or getattr(prop_data, 'visible', True) is False:
                    continue
                if prop_data.name not in self.active_props:
                    continue
                if not hasattr(prop_data, 'mesh_reference') or not prop_data.mesh_reference.render:
                    continue
                    
                prop_matrix = QMatrix4x4()
                bone_name = getattr(prop_data, 'parent_bone', 'None')
                bone = None
                is_parented = False

