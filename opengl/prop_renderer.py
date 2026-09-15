######
#
# Prop Renderer V1.5 (Unified Build - Clean Patch) Elvaerwyn_MH2 2026
# Fixes path truncation and quad mapping for pristine GIMP alpha textures
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
    Renders particle streams dynamically across active memory buffers,
    binding true alpha quads instead of raw un-masked point squares.
    """
    def internal_load_texture(glob_reference, relative_image_path):
        """Loads images directly relative to the active plugin workspace paths."""
        if not relative_image_path or relative_image_path == "PLAIN":
            return None
        if relative_image_path in TEXTURE_CACHE_REPOS:
            return TEXTURE_CACHE_REPOS[relative_image_path]

        # Dynamic path compilation matches the local subdirectory routes cleanly
        current_script_dir = os.path.dirname(os.path.abspath(__file__))
        plugin_root_folder = os.path.abspath(os.path.join(current_script_dir, ".."))
        
        clean_relative_path = relative_image_path.split("prop_panel/")[-1] if "prop_panel/" in relative_image_path else relative_image_path
        full_disk_route = os.path.normpath(os.path.join(plugin_root_folder, clean_relative_path)).replace("\\", "/")

        if not os.path.isfile(full_disk_route):
            fallback_route = os.path.normpath(os.path.join(plugin_root_folder, "data", "props", os.path.basename(relative_image_path))).replace("\\", "/")
            if os.path.isfile(fallback_route):
                full_disk_route = fallback_route
            else:
                return None

        try:

            from PySide6.QtGui import QImage
            
            raw_img = QImage(full_disk_route)
            if raw_img.isNull():
                return None
                
            # Convert any optimized PNG formats directly into 32-bit channels
            rgba_img = raw_img.convertToFormat(QImage.Format.Format_RGBA8888)
            width, height = rgba_img.width(), rgba_img.height()
            pixel_bytes = rgba_img.bits().tobytes() if hasattr(rgba_img.bits(), 'tobytes') else rgba_img.bits()

            # Generate a raw OpenGL texture slot handle natively
            tex_id = gl.glGenTextures(1)
            gl.glBindTexture(gl.GL_TEXTURE_2D, tex_id)

            # Force standard image scaling parameters to unblock texturing calculations
            gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR)
            gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR)
            
            # Overrides GL_CLAMP constraints 
            gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_S, gl.GL_REPEAT)
            gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_T, gl.GL_REPEAT)

            # Upload the raw RGBA pixel arrays directly to computer's graphics card
            gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_RGBA8, width, height, 0, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE, pixel_bytes)
            
            gl.glBindTexture(gl.GL_TEXTURE_2D, 0)
            
            TEXTURE_CACHE_REPOS[relative_image_path] = tex_id
            return tex_id
            
        except Exception as tex_err:
            print(f"[Prop Studio Texture Error] Alternate color pipeline failed: {tex_err}")
            return None

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

        if not getattr(prop, 'is_emitting', True):
            continue

        mode = getattr(prop, 'emitter_mode', 'PARTICLES').upper().strip()
        if prop.emitter and mode == "PHYSICAL_MESH":
            continue

        vertices = []

        if hasattr(prop, 'emitter') and prop.emitter and hasattr(prop.emitter, 'particles'):
            emitter_data = prop.emitter.particles
            if emitter_data is not None and len(emitter_data) > 0:
                try:
                    vertices = [float(x) for x in emitter_data]
                except Exception:
                    vertices = []

        if not vertices:
            prop_id = getattr(prop, 'name', None)
            if prop_id and prop_id in live_particle_system.emitter_pools:
                pool_data = live_particle_system.emitter_pools[prop_id]
                for p in pool_data:
                    if isinstance(p, dict) and "pos" in p:
                        v = p["pos"]
                        if len(v) >= 3: vertices.extend([float(v[0]), float(v[1]), float(v[2])])
                    elif isinstance(p, dict) and "coord" in p:
                        v = p["coord"]
                        if len(v) >= 3: vertices.extend([float(v[0]), float(v[1]), float(v[2])])

        if not vertices:
            continue

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
            r, g, b, a = 1.0, 0.4, 0.0, 1.0

        size = float(getattr(prop, 'particle_draw_size', 6.0))

        # ================================================
        # OPENGL BLIT VECTOR DRAW PASS (MODES 1, 2, & 3)
        # ================================================
        gl.glPushMatrix()
        gl.glPushAttrib(gl.GL_POINT_BIT | gl.GL_CURRENT_BIT | gl.GL_ENABLE_BIT | gl.GL_TEXTURE_BIT)
        gl.glDisable(gl.GL_LIGHTING)
        
        # THE SHADER UNLINK 
        gl.glUseProgram(0)

        if hasattr(prop, 'runtime_gl_matrix') and prop.runtime_gl_matrix is not None:
            gl.glEnable(gl.GL_NORMALIZE)
            gl.glMultMatrixf(prop.runtime_gl_matrix)


        # MODE 3: SMOOTH ALPHA RENDER PASS
        if mode == "TEXTURED_SPRITES":
            tex_file = getattr(prop, 'particle_texture', 'PLAIN')
            active_tex_id = internal_load_texture(glob, tex_file) if tex_file != "PLAIN" else None
            
            if active_tex_id is not None:
                gl.glEnable(gl.GL_BLEND)
                gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE)
                gl.glDisable(gl.GL_DEPTH_TEST)
                gl.glDepthMask(gl.GL_FALSE)
                gl.glEnable(gl.GL_TEXTURE_2D)
                gl.glBindTexture(gl.GL_TEXTURE_2D, active_tex_id)
                
                quad_size = (size if size > 0.0 else 48.0) * 0.001
                
                gl.glBegin(gl.GL_QUADS)
                for idx in range(0, len(vertices), 3):
                    gl.glColor4f(r, g, b, a)
                    px, py, pz = vertices[idx], vertices[idx+1], vertices[idx+2]
                    
                    gl.glTexCoord2f(0.0, 0.0); gl.glVertex3f(px - quad_size, py - quad_size, pz)
                    gl.glTexCoord2f(1.0, 0.0); gl.glVertex3f(px + quad_size, py - quad_size, pz)
                    gl.glTexCoord2f(1.0, 1.0); gl.glVertex3f(px + quad_size, py + quad_size, pz)
                    gl.glTexCoord2f(0.0, 1.0); gl.glVertex3f(px - quad_size, py + quad_size, pz)
                gl.glEnd()
                
                gl.glEnable(gl.GL_DEPTH_TEST)
                gl.glDepthMask(gl.GL_TRUE)
                gl.glPopAttrib()
                gl.glPopMatrix()
                continue
            else:
                mode = "PARTICLES"

        # MODE 2: FLAT SOLID SPRITES
        if mode == "SPRITES":
            gl.glEnable(gl.GL_BLEND)
            gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)
            gl.glDisable(gl.GL_TEXTURE_2D)
            gl.glEnable(gl.GL_POINT_SPRITE)
            gl.glTexEnvi(gl.GL_POINT_SPRITE, gl.GL_COORD_REPLACE, gl.GL_TRUE)
            gl.glPointSize(size if size > 6.0 else 16.0)
            gl.glColor4f(r, g, b, a)

        # MODE 1: PURE DUST
        if mode == "PARTICLES":
            gl.glDisable(gl.GL_TEXTURE_2D)
            gl.glDisable(gl.GL_POINT_SPRITE)
            gl.glEnable(gl.GL_BLEND)
            gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)
            gl.glPointSize(size)
            gl.glColor4f(r, g, b, a)

        vertex_data = np.array(vertices, dtype=np.float32)
        gl.glEnableClientState(gl.GL_VERTEX_ARRAY)
        gl.glVertexPointer(3, gl.GL_FLOAT, 0, vertex_data)
        gl.glDrawArrays(gl.GL_POINTS, 0, len(vertex_data) // 3)

        gl.glDisableClientState(gl.GL_VERTEX_ARRAY)
        gl.glBindTexture(gl.GL_TEXTURE_2D, 0)
        gl.glPopAttrib()
        gl.glPopMatrix()
