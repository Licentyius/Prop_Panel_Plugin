######
#
# Prop Renderer  V1.3 by Elvaerwyn MH_2 2026
# For use in the prop panel plugin for Makehuman 2
#
######

import sys
import os
import numpy as np
from OpenGL import GL as gl
from PySide6.QtGui import QMatrix4x4, QVector3D

from ..core.particle_engine import live_particle_system

TEXTURE_CACHE_REPOS = {}

def inject_particle_gl_draw_pass(glob, custom_props_list):
    """
    Renders particle streams dynamically based on 4 architectural modes:
    PARTICLES, SPRITES, TEXTURED_SPRITES, and PHYSICAL_MESH while respecting controls.
    """
    def internal_load_texture(glob_reference, relative_image_path):
        if not relative_image_path or relative_image_path == "PLAIN":
            return None
        if relative_image_path in TEXTURE_CACHE_REPOS:
            return TEXTURE_CACHE_REPOS[relative_image_path]

        full_disk_route = os.path.normpath(os.path.join(glob_reference.env.path_sysdata, "mh2_official_tools", relative_image_path)).replace("\\", "/")
        if not os.path.isfile(full_disk_route):
            return None

        try:
            from opengl.texture import Texture
            native_tex_layer = Texture(glob_reference.openGLWindow)
            native_tex_layer.load(full_disk_route)
            hardware_id = native_tex_layer.id
            TEXTURE_CACHE_REPOS[relative_image_path] = hardware_id
            return hardware_id
        except Exception as tex_err:
            print(f"[Prop Studio Texture Error] Framework collapsed: {tex_err}")
            return None

    # Step the underlying physics calculation engine uniformly once per frame call
    if not hasattr(glob, '_last_physics_frame_stamp'):
        glob._last_physics_frame_stamp = 0.0
    
    import time
    now = time.time()
    if now - glob._last_physics_frame_stamp > 0.016:
        live_particle_system.tick_physics(custom_props_list)
        glob._last_physics_frame_stamp = now

    for prop in custom_props_list:
        obj_type = getattr(prop, 'object_type', getattr(prop, 'type', 'STATIC'))
        if str(obj_type).upper() != 'EMITTER':
            continue

        # RESTORED ACTION GATE: Instantly skip drawing if user toggles emission off (Fixes Play/Pause)
        if not getattr(prop, 'is_emitting', True):
            continue

        prop_id = getattr(prop, 'name', None)
        vertices = []
        
        # Pull active coordinate vectors out of the simulation pools
        if prop_id and prop_id in live_particle_system.emitter_pools:
            pool_data = live_particle_system.emitter_pools[prop_id]
            for p in pool_data:
                if isinstance(p, dict) and "pos" in p:
                    v = p["pos"]
                    vertices.extend([float(v[0]), float(v[1]), float(v[2])])
                elif isinstance(p, dict) and "coord" in p:
                    v = p["coord"]
                    vertices.extend([float(v[0]), float(v[1]), float(v[2])])

        if not vertices and hasattr(prop, 'particles_pool') and prop.particles_pool:
            for p in prop.particles_pool:
                vertices.extend([float(getattr(p, 'x', 0.0)), float(getattr(p, 'y', 0.0)), float(getattr(p, 'z', 0.0))])

        if not vertices:
            continue

        vertex_data = np.array(vertices, dtype=np.float32)

        # Dynamic parameter extraction checks priority chains to eliminate white dots exceptions
        color_data = None
        for attr in ['particle_color', 'color_rgba']:
            val = getattr(prop, attr, None)
            if val is not None and hasattr(val, '__len__') and len(val) >= 3:
                color_data = val
                break
        
        if color_data is not None:
            r, g, b = float(color_data[0]), float(color_data[1]), float(color_data[2])
            a = float(color_data[3]) if len(color_data) >= 4 else 1.0
        else:
            r, g, b, a = 1.0, 0.4, 0.0, 1.0 # Safe programmatic orange baseline variable

        # Fetch mode flags from your schema maps
        mode = getattr(prop, 'emitter_mode', 'PARTICLES').upper().strip()
        size = float(getattr(prop, 'particle_draw_size', 6.0))

        # =====================================================================
        # MODE 4: PHYSICAL OBJECT MESH INSTANCING COPIES (.obj spawns)
        # =====================================================================
        if mode == "PHYSICAL_MESH" and hasattr(prop, 'mesh_reference') and prop.mesh_reference:
            render_pipeline = getattr(glob, 'prop_manager_pipeline', None)
            if render_pipeline:
                active_shader = getattr(render_pipeline, 'pbr', getattr(render_pipeline, 'phong', None))
                if active_shader and render_pipeline.shaders:
                    render_pipeline.shaders.bindShader(active_shader)
                    loc_mvp = gl.glGetUniformLocation(active_shader.program, "meshMVP")
                    viewport = getattr(glob, 'openGLWindow', None)
                    
                    if viewport and loc_mvp != -1:
                        proj_view = viewport.getProjViewMatrix()
                        for i in range(0, len(vertices), 3):
                            inst_m = QMatrix4x4()
                            inst_m.translate(vertices[i], vertices[i+1], vertices[i+2])
                            inst_m.scale(0.1, 0.1, 0.1) # Scale multiplier for small physical copies
                            
                            computed_mvp = proj_view * inst_m
                            gl.glUniformMatrix4fv(loc_mvp, 1, gl.GL_FALSE, computed_mvp.data())
                            prop.mesh_reference.render.draw(computed_mvp, viewport.campos, viewport.light, False)
            continue

        # =====================================================================
        # OPENGL BLIT VECTOR DRAW PASS (MODES 1, 2, & 3)
        # =====================================================================
        gl.glPushMatrix()
        gl.glPushAttrib(gl.GL_POINT_BIT | gl.GL_CURRENT_BIT | gl.GL_ENABLE_BIT | gl.GL_TEXTURE_BIT)
        gl.glDisable(gl.GL_LIGHTING)

        if hasattr(prop, 'runtime_gl_matrix') and prop.runtime_gl_matrix is not None:
            gl.glEnable(gl.GL_NORMALIZE)
            gl.glMultMatrixf(prop.runtime_gl_matrix)

        # MODE 3: TEXTURED IMAGE-BASED BILLBOARDS (flame.png or water.png)
        if mode == "TEXTURED_SPRITES":
            tex_file = getattr(prop, 'particle_texture', 'PLAIN')
            active_tex_id = internal_load_texture(glob, tex_file) if tex_file != "PLAIN" else None
            
            if active_tex_id is not None:
                gl.glEnable(gl.GL_BLEND)
                gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE) # Realistic additive blending
                gl.glEnable(gl.GL_POINT_SPRITE)
                gl.glTexEnvi(gl.GL_POINT_SPRITE, gl.GL_COORD_REPLACE, gl.GL_TRUE)
                gl.glEnable(gl.GL_TEXTURE_2D)
                gl.glBindTexture(gl.GL_TEXTURE_2D, active_tex_id)
                gl.glPointSize(size if size > 6.0 else 48.0)
                gl.glColor4f(1.0, 1.0, 1.0, 1.0)
            else:
                mode = "PARTICLES" # Drop back safely if file is missing

        # MODE 2: UNMASKED FLAT CARD SPRITES
        if mode == "SPRITES":
            gl.glEnable(gl.GL_BLEND)
            gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)
            gl.glDisable(gl.GL_TEXTURE_2D)
            gl.glEnable(gl.GL_POINT_SPRITE)
            gl.glTexEnvi(gl.GL_POINT_SPRITE, gl.GL_COORD_REPLACE, gl.GL_TRUE)
            gl.glPointSize(size if size > 6.0 else 16.0)
            gl.glColor4f(r, g, b, a)

        # MODE 1: PURE DUST PARTICLES ONLY
        if mode == "PARTICLES":
            gl.glDisable(gl.GL_TEXTURE_2D)
            gl.glDisable(gl.GL_POINT_SPRITE)
            gl.glEnable(gl.GL_BLEND)
            gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)
            gl.glPointSize(size)
            gl.glColor4f(r, g, b, a)

        gl.glEnableClientState(gl.GL_VERTEX_ARRAY)
        gl.glVertexPointer(3, gl.GL_FLOAT, 0, vertex_data)
        gl.glDrawArrays(gl.GL_POINTS, 0, len(vertex_data) // 3)

        gl.glDisableClientState(gl.GL_VERTEX_ARRAY)
        gl.glBindTexture(gl.GL_TEXTURE_2D, 0)
        gl.glPopAttrib()
        gl.glPopMatrix()
