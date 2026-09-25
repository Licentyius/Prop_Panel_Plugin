######
#
# Prop Manager V2.7a (Fully Dynamic Unified Edition V1)Elvaerwyn_MH2 2026
# Cleaned
#
######
from PySide6.QtGui import QMatrix4x4, QVector3D, QVector4D, QQuaternion
import OpenGL
from OpenGL import GL as gl
import numpy as np

class MultiPropManager():
    """
    Manages active static props, socket attachment transformations,
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
        
        self.glob.prop_manager_pipeline = self
        self.fromGlobal(False)

    def fromGlobal(self, load_json):
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
                if len(val) >= 3: t_block[key] = [float(val[0]), float(val[1]), float(val[2])]
                else: t_block[key] = [1.0, 1.0, 1.0]
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
        self.active_props.clear()

    def updatePropTransform(self, asset_id, translation=None, rotation=None, scale=None):
        if asset_id in self.active_props:
            t_block = self.active_props[asset_id]["transform"]
            if translation is not None:
                t_block["translation"] = [float(translation[0]), float(translation[1]), float(translation[2])]
            if rotation is not None:
                t_block["rotation"] = [float(rotation[0]), float(rotation[1]), float(rotation[2])]
            if scale is not None:
                t_block["scale"] = [float(scale[0]), float(scale[1]), float(scale[2])]

    def drawProps(self, proj_view_matrix, campos, light_obj):
        custom_props = getattr(self.glob, 'custom_props_list', None)

        if custom_props:
            bc = getattr(self.glob, 'baseClass', None)

            for prop_data in custom_props:
                if not prop_data:
                    continue
                
                # Check normal visibility flags natively out of the live UI checkboxes
                if not getattr(prop_data, 'visible', True):
                    continue
                    
                prop_matrix = QMatrix4x4()
                bone_name = getattr(prop_data, 'parent_bone', 'None')
                bone = None
                is_parented = False
                
                if getattr(prop_data, 'use_parenting', False) and bone_name != "None" and bc:
                    skeleton = bc.pose_skeleton if bc.in_posemode else bc.skeleton
                    if skeleton is None: 
                        skeleton = bc.default_skeleton
                    if skeleton and hasattr(skeleton, 'bones') and bone_name in skeleton.bones: 
                        bone = skeleton.bones[bone_name]

                if bone:
                    is_parented = True
                    if bc.in_posemode:
                        b_rot = getattr(bone, 'matPoseVerts', None)
                        b_pos = getattr(bone, 'poseheadPos', None)
                    else:
                        b_rot = getattr(bone, 'matRestGlobal', None) 
                        b_pos = getattr(bone, 'headPos', None)

                    if b_rot is not None and b_pos is not None:
                        comp_m = np.eye(4, dtype=np.float32)
                        if b_rot.shape == (3, 3): comp_m[0:3, 0:3] = b_rot
                        elif b_rot.shape == (4, 4): comp_m[0:3, 0:3] = b_rot[0:3, 0:3]
                            
                        comp_m[0:3, 3] = [float(b_pos.x()), float(b_pos.y()), float(b_pos.z())]
                        for r in range(4):
                            prop_matrix.setRow(r, QVector4D(float(comp_m[r][0]), float(comp_m[r][1]), float(comp_m[r][2]), float(comp_m[r][3])))
                    else:
                        if b_pos is not None:
                            prop_matrix.translate(b_pos.x(), b_pos.y(), b_pos.z())

                user_transform = QMatrix4x4()
                pos = prop_data.position
                rot = prop_data.rotation
                scl = prop_data.scale

                if is_parented:
                    local_offset = getattr(prop_data, 'local_offset_pos', np.array([0.0, 0.0, 0.0]))
                    user_transform.translate(float(local_offset[0]), float(local_offset[1]), float(local_offset[2]))
                else:
                    user_transform.translate(float(pos[0]), float(pos[1]), float(pos[2]))

                q_pitch = QQuaternion.fromAxisAndAngle(QVector3D(1.0, 0.0, 0.0), float(rot[0]))
                q_yaw   = QQuaternion.fromAxisAndAngle(QVector3D(0.0, 1.0, 0.0), float(rot[1]))
                q_roll  = QQuaternion.fromAxisAndAngle(QVector3D(0.0, 0.0, 1.0), float(rot[2]))
                user_transform.rotate(q_yaw * q_pitch * q_roll)
                
                user_transform.scale(float(scl[0]), float(scl[1]), float(scl[2]))

                final_prop_matrix = prop_matrix * user_transform if is_parented else user_transform
                final_mvp = proj_view_matrix * final_prop_matrix
                prop_data.runtime_gl_matrix = final_prop_matrix.data()

                # =============================
                # THE PHYSICS UNCLOCK PLUG:
                # =============================
                if prop_data.emitter:
                    prop_data.emitter.world_position = [0.0, 0.0, 0.0]
                    prop_data.emitter.runtime_gl_matrix = final_prop_matrix.data()

                # ====================================
                # SOLID PROPERTIES RESTORATION TRACK:
                # ====================================
                gl.glEnable(gl.GL_DEPTH_TEST)
                gl.glDepthMask(gl.GL_TRUE)
                gl.glDisable(gl.GL_BLEND)

                # ===================================
                # Ghost Mode Intercept Verification 
                # ===================================
                mesh_vis = getattr(prop_data, 'is_mesh_visible', True)

                if mesh_vis and hasattr(prop_data, 'mesh_reference') and prop_data.mesh_reference:
                    if hasattr(prop_data.mesh_reference, 'render') and prop_data.mesh_reference.render:
                        prop_data.mesh_reference.render.draw(final_mvp, campos, light_obj, False)


                gl.glActiveTexture(gl.GL_TEXTURE0)
                gl.glBindTexture(gl.GL_TEXTURE_2D, 0)
                gl.glUseProgram(0)                     # Clean context register states
                
                gl.glEnable(gl.GL_DEPTH_TEST)
                gl.glDepthMask(gl.GL_TRUE)
                gl.glDisable(gl.GL_BLEND)


                # Route draw commands directly to the core emitter methods cleanly
                if prop_data.emitter and getattr(prop_data, 'is_emitting', True):
                    if hasattr(prop_data.emitter, 'startOpenGL'):
                        try:
                            prop_data.emitter.startOpenGL()

                            emode = prop_data.emitter.emitter_mode
                            if emode == "PHYSICAL_MESH":
                                prop_data.emitter.drawMesh(proj_view_matrix, campos)
                            elif emode == "PARTICLES":
                                prop_data.emitter.drawDustParticles()
                            elif emode == "SPRITES":
                                prop_data.emitter.drawSprites()
                            elif emode == "TEXTURED_SPRITES":
                                prop_data.emitter.drawTexSprites()
                            elif emode == "BILLBOARD":
                                prop_data.emitter.drawBillboards(campos)

                            if hasattr(prop_data.emitter, 'finishOpenGL'):
                                prop_data.emitter.finishOpenGL()
                        except Exception as e:
                            print(f"[Prop Studio Debug] Legacy drawing step bypassed: {e}")

                # =================================================================
                # Safely unbind the texture layer and clear active shader programs 
                # BEFORE resetting depth testing flags 
                # =================================================================
                gl.glActiveTexture(gl.GL_TEXTURE0)
                gl.glBindTexture(gl.GL_TEXTURE_2D, 0)
                gl.glUseProgram(0)                     # Clean context register states
                
                gl.glEnable(gl.GL_DEPTH_TEST)
                gl.glDepthMask(gl.GL_TRUE)
                gl.glDisable(gl.GL_BLEND)

        # Draw structural environment grid floor below everything safely
        if hasattr(self.glob, 'prop_manager_pipeline') and self.glob.prop_manager_pipeline:
            left_panel = getattr(self.glob.prop_manager_pipeline, 'leftPanel', None)
            if left_panel and hasattr(left_panel, 'room_floor_mesh') and left_panel.room_floor_mesh.render:
                floor_render_obj = left_panel.room_floor_mesh.render
                floor_matrix = QMatrix4x4()
                
                room_w, room_l = 10.0, 10.0
                if bc and hasattr(bc, 'scene') and bc.scene and hasattr(bc.scene, 'floorsize'):
                    f_size = bc.scene.floorsize
                    if isinstance(f_size, (list, tuple, np.ndarray)) and len(f_size) >= 3:
                        room_w = float(f_size[0])
                        room_l = float(f_size[2])
                        
                floor_matrix.scale(float(room_w), 1.0, float(room_l))
                floor_render_obj.draw(proj_view_matrix * floor_matrix, campos, light_obj, False)
                
                gl.glActiveTexture(gl.GL_TEXTURE0)
                gl.glBindTexture(gl.GL_TEXTURE_2D, 0)

        self.setShader()
        gl.glUseProgram(0)
