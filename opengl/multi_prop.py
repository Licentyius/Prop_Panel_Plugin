#######
## Multi-Prop V2.1
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
    TODO: class not used at all
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
        #print("drawProps from prop_manager draw")
        """Coordinates rendering states via direct injection into the OpenGL draw loops."""
        custom_props = getattr(self.glob, 'custom_props_list', [])
        bc = getattr(self.glob, 'baseClass', None)
 
        # 1. COMPUTE AND DRAW THE PARTICLE SIMULATION STREAMS FIRST
        if custom_props:
            from OpenGL import GL as gl
            gl.glUseProgram(0)  # Release modern pipeline shader hold safely
            
            from .prop_renderer import inject_particle_gl_draw_pass
            
            # Temporary storage to match matrix variables inside drawing queues
            for prop_data in custom_props:
                obj_type = getattr(prop_data, 'object_type', getattr(prop_data, 'type', 'STATIC'))
                if str(obj_type).upper() != 'EMITTER':
                    continue
                    
                p_matrix = QMatrix4x4()
                bone_name = getattr(prop_data, 'parent_bone', 'None')
                is_parented = getattr(prop_data, 'use_parenting', False) and bone_name != "None"
                bone = None
                
                if is_parented and bc:
                    skeleton = bc.pose_skeleton if bc.in_posemode else bc.skeleton
                    if skeleton and bone_name in getattr(skeleton, 'bones', {}):
                        bone = skeleton.bones[bone_name]
                        
                if is_parented and bone is not None:
                    b_pos = getattr(bone, 'poseheadPos', getattr(bone, 'headPos', None))
                    b_rot = getattr(bone, 'matPoseVerts', getattr(bone, 'matRestGlobal', None))
                    if b_pos is not None and b_rot is not None:
                        comp_m = np.eye(4, dtype=np.float32)
                        
                        if hasattr(b_rot, 'shape'):
                            if b_rot.shape == (3, 3): comp_m[0:3, 0:3] = b_rot
                            elif b_rot.shape == (4, 4): comp_m[0:3, 0:3] = b_rot[0:3, 0:3]
                        
                        comp_m[0:3, 3] = [float(b_pos.x()), float(b_pos.y()), float(b_pos.z())]

                        flat_list = [float(x) for x in comp_m.T.flatten()]
                        p_matrix = QMatrix4x4(flat_list)
                else:
                    p_pos = getattr(prop_data, 'position', [0.0, 0.0, 0.0])
                    p_matrix.setToIdentity()
                    
                    mx = float(p_pos[0]) if hasattr(p_pos, '__getitem__') and len(p_pos) > 0 else 0.0
                    my = float(p_pos[1]) if hasattr(p_pos, '__getitem__') and len(p_pos) > 1 else 0.0
                    mz = float(p_pos[2]) if hasattr(p_pos, '__getitem__') and len(p_pos) > 2 else 0.0
                    p_matrix.translate(QVector3D(mx, my, mz))
                    
                u_transform = QMatrix4x4()
                rot = getattr(prop_data, 'rotation', [0.0, 0.0, 0.0])
                scl = getattr(prop_data, 'scale', [1.0, 1.0, 1.0])
                
                if is_parented:
                    local_offset = getattr(prop_data, 'local_offset_pos', np.array([0.0, 0.1, 0.0]))
                    u_transform.translate(float(local_offset[0]), float(local_offset[1]), float(local_offset[2]))
                    
                from PySide6.QtGui import QQuaternion
                q_pitch = QQuaternion.fromAxisAndAngle(QVector3D(1.0, 0.0, 0.0), float(rot[0]))
                q_yaw   = QQuaternion.fromAxisAndAngle(QVector3D(0.0, 1.0, 0.0), float(rot[1]))
                q_roll  = QQuaternion.fromAxisAndAngle(QVector3D(0.0, 0.0, 1.0), float(rot[2]))
                u_transform.rotate(q_yaw * q_pitch * q_roll)
                u_transform.scale(float(scl[0]), float(scl[1]), float(scl[2]))
                
                model_matrix = p_matrix * u_transform

                prop_data.runtime_gl_matrix = [float(x) for x in model_matrix.copyData()]
                
            inject_particle_gl_draw_pass(self.glob, custom_props)

        # 2. RENDER THE 3D SOLID PROP GEOMETRY MESHES DIRECTLY FROM ATTACHED PARAMETERS
        if custom_props:
            for prop_data in custom_props:
                if not prop_data:
                    continue
                    
                prop_vis = getattr(prop_data, 'visible', True)
                mesh_vis = getattr(prop_data, 'is_mesh_visible', True)
                if not prop_vis or not mesh_vis:
                    continue
                    
                if not hasattr(prop_data, 'mesh_reference') or not prop_data.mesh_reference.render:
                    continue
                    
                prop_matrix = QMatrix4x4()
                bone_name = getattr(prop_data, 'parent_bone', 'None')
                is_parented = getattr(prop_data, 'use_parenting', False) and bone_name != "None"
                bone = None

                if is_parented and bc:
                    skeleton = bc.pose_skeleton if bc.in_posemode else bc.skeleton
                    if skeleton is None:
                        skeleton = bc.default_skeleton
                    if skeleton and bone_name in getattr(skeleton, 'bones', {}):
                        bone = skeleton.bones[bone_name]

                if is_parented and bone is not None:
                    b_pos = getattr(bone, 'poseheadPos', getattr(bone, 'headPos', None))
                    b_rot = getattr(bone, 'matPoseVerts', getattr(bone, 'matRestGlobal', None))
                    if b_pos is not None and b_rot is not None:
                        comp_m = np.eye(4, dtype=np.float32)
                        
                        if hasattr(b_rot, 'shape'):
                            if b_rot.shape == (3, 3): comp_m[0:3, 0:3] = b_rot
                            elif b_rot.shape == (4, 4): comp_m[0:3, 0:3] = b_rot[0:3, 0:3]
                        
                        comp_m[0:3, 3] = [float(b_pos.x()), float(b_pos.y()), float(b_pos.z())]

                        flat_list = [float(x) for x in comp_m.T.flatten()]
                        prop_matrix = QMatrix4x4(flat_list)
                else:
                    p_pos = getattr(prop_data, 'position', [0.0, 0.0, 0.0])
                    prop_matrix.setToIdentity()
                    
                    mx = float(p_pos[0]) if hasattr(p_pos, '__getitem__') and len(p_pos) > 0 else 0.0
                    my = float(p_pos[1]) if hasattr(p_pos, '__getitem__') and len(p_pos) > 1 else 0.0
                    mz = float(p_pos[2]) if hasattr(p_pos, '__getitem__') and len(p_pos) > 2 else 0.0
                    prop_matrix.translate(QVector3D(mx, my, mz))

                user_transform = QMatrix4x4()
                rot = getattr(prop_data, 'rotation', [0.0, 0.0, 0.0])
                scl = getattr(prop_data, 'scale', [1.0, 1.0, 1.0])
                
                if is_parented:
                    local_offset = getattr(prop_data, 'local_offset_pos', np.array([0.0, 0.1, 0.0]))
                    user_transform.translate(float(local_offset[0]), float(local_offset[1]), float(local_offset[2]))

                from PySide6.QtGui import QQuaternion
                q_pitch = QQuaternion.fromAxisAndAngle(QVector3D(1.0, 0.0, 0.0), float(rot[0]))
                q_yaw   = QQuaternion.fromAxisAndAngle(QVector3D(0.0, 1.0, 0.0), float(rot[1]))
                q_roll  = QQuaternion.fromAxisAndAngle(QVector3D(0.0, 0.0, 1.0), float(rot[2]))
                user_transform.rotate(q_yaw * q_pitch * q_roll)
                user_transform.scale(float(scl[0]), float(scl[1]), float(scl[2]))

                final_mvp = proj_view_matrix * (prop_matrix * user_transform)
                
                active_shader = self.pbr if self.pbr else self.phong
                if active_shader and self.shaders:
                    self.shaders.bindShader(active_shader)
                    loc_mvp = gl.glGetUniformLocation(active_shader.program, "meshMVP")
                    if loc_mvp != -1:
                        gl.glUniformMatrix4fv(loc_mvp, 1, gl.GL_FALSE, final_mvp.data())
                        
                    prop_data.mesh_reference.render.draw(final_mvp, campos, light_obj, False)


class MHRuntimeParticleEmitter:
    """Manages active live viewport particle simulation calculations over time frames."""
    # tick_physics in PrimitiveParticleEngine and calculate_live_particle_physics_tick in gui/prop_module
    # we need to decide for one engine even if we have more than one calculation
    # TODO Class not used at all
    def __init__(self, config_data):
        self.config = config_data
        dynamics = config_data.get("particle_dynamics", {})
        
        self.max_particles = dynamics.get("max_particles", 100)
        self.particles = [] # Holds live dictionaries: {"pos": [x,y,z], "vel": [x,y,z], "life": float}
        
    def advance_simulation_tick(self, delta_time, origin_pos):
        """Advances positions along velocity vectors and spawns new particle nodes."""  # never called!!!
        dynamics = self.config.get("particle_dynamics", {})
        vel = dynamics.get("initial_velocity_xyz", [0.0, 1.0, 0.0])
        drift = dynamics.get("velocity_drift_xyz", [0.1, 0.1, 0.1])
        gravity = dynamics.get("gravity_acceleration_y", 0.0)

        # 1. Update existing particle positions array lines
        for p in self.particles[:]:
            p["life"] -= delta_time
            if p["life"] <= 0:
                self.particles.remove(p)
                continue
                
            # Apply acceleration vectors over time
            p["pos"][0] += p["vel"][0] * delta_time
            p["pos"][1] += (p["vel"][1] - gravity) * delta_time
            p["pos"][2] += p["vel"][2] * delta_time

        # 2. Spawn fresh points if room remains active under the cap limit
        if len(self.particles) < self.max_particles:
            random_drift_x = (np.random.rand() - 0.5) * drift[0]
            random_drift_y = (np.random.rand() - 0.5) * drift[1]
            random_drift_z = (np.random.rand() - 0.5) * drift[2]
            
            new_particle = {
                "pos": [float(origin_pos[0]), float(origin_pos[1]), float(origin_pos[2])],
                "vel": [vel[0] + random_drift_x, vel[1] + random_drift_y, vel[2] + random_drift_z],
                "life": float(np.random.uniform(0.5, 2.0))
            }
            self.particles.append(new_particle)


