######
#
# Prop Renderer  V1.2 by Elvaerwyn MH_2 2026
# For use in the prop panel plugin for Makehuman 2
#
######

import sys
import os
import numpy as np
from OpenGL import GL as gl

# Globally retain bound hardware identifiers to eliminate frame hiccups
TEXTURE_CACHE_REPOS = {}

def inject_particle_gl_draw_pass(custom_props_list):
    """
    Renders particle streams as either alpha-masked texture images 
    (flames, water drops) or plain vector points for basic light.
    """
    
    # 1. THREAD SAFE PATH EXTENSION: Discover sibling directories on execution
    _current_dir = os.path.dirname(os.path.abspath(__file__))
    _plugin_root = os.path.abspath(os.path.join(_current_dir, ".."))
    
    if _plugin_root not in sys.path:
        sys.path.insert(0, _plugin_root)

    # 2. RUN A SECURED LOCAL FALLBACK IMPORT FOR THE PHYSICS ENGINE
    try:
        from core.particle_engine import live_particle_system
    except ImportError:
        import importlib.util
        core_path = os.path.join(_plugin_root, "core", "particle_engine.py")
        if os.path.isfile(core_path):
            spec = importlib.util.spec_from_file_location("particle_engine", core_path)
            module = importlib.util.module_from_spec(spec)
            sys.modules["core.particle_engine"] = module
            spec.loader.exec_module(module)
            live_particle_system = module.live_particle_system
        else:
            return

    # Helper function moved inside to prevent scoping/threading lookup collapses
    def internal_load_texture(glob_reference, relative_image_path):
        if not relative_image_path or relative_image_path == "PLAIN":
            return None
        if relative_image_path in TEXTURE_CACHE_REPOS:
            return TEXTURE_CACHE_REPOS[relative_image_path]

        full_disk_route = os.path.normpath(os.path.join(_plugin_root, relative_image_path)).replace("\\", "/")
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

    # Advance particle tracking engine vectors
    live_particle_system.tick_physics(custom_props_list)

    for prop in custom_props_list:
        obj_type = getattr(prop, 'object_type', getattr(prop, 'type', 'STATIC'))
        if str(obj_type).upper() != 'EMITTER':
            continue

        prop_id = getattr(prop, 'name', None)
        vertices = []
        
        # Consolidate memory pools formatting safely
        if prop_id and prop_id in live_particle_system.emitter_pools:
            pool_data = live_particle_system.emitter_pools[prop_id]
            for p in pool_data:
                if isinstance(p, dict) and "pos" in p:
                    v = p["pos"]
                    if hasattr(v, '__getitem__') and len(v) >= 3:
                        vertices.extend([float(v[0]), float(v[1]), float(v[2])])
                elif isinstance(p, dict) and "coord" in p:
                    v = p["coord"]
                    if hasattr(v, '__getitem__') and len(v) >= 3:
                        vertices.extend([float(v[0]), float(v[1]), float(v[2])])

        if not vertices and hasattr(prop, 'particles_pool') and prop.particles_pool:
            for p in prop.particles_pool:
                vertices.extend([float(getattr(p, 'x', 0.0)), float(getattr(p, 'y', 0.0)), float(getattr(p, 'z', 0.0))])

        if not vertices:
            continue

        vertex_data = np.array(vertices, dtype=np.float32)
        
        # 3. SECURE LOCAL TEXTURE ASSIGNMENT
        tex_target = getattr(prop, 'particle_texture', 'PLAIN')
        active_tex_id = None
        if tex_target != "PLAIN":
            active_tex_id = internal_load_texture(prop.glob, tex_target) if hasattr(prop, 'glob') else None

        gl.glPushMatrix()
        gl.glPushAttrib(gl.GL_POINT_BIT | gl.GL_CURRENT_BIT | gl.GL_ENABLE_BIT | gl.GL_TEXTURE_BIT)
        gl.glDisable(gl.GL_LIGHTING)

        if hasattr(prop, 'runtime_gl_matrix') and prop.runtime_gl_matrix is not None:
            gl.glEnable(gl.GL_NORMALIZE)
            gl.glMultMatrixf(prop.runtime_gl_matrix)

        if active_tex_id is not None:
            gl.glEnable(gl.GL_BLEND)
            gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE)
            
            gl.glEnable(gl.GL_POINT_SPRITE)
            gl.glTexEnvi(gl.GL_POINT_SPRITE, gl.GL_COORD_REPLACE, gl.GL_TRUE)
            gl.glTexEnvi(gl.GL_TEXTURE_ENV, gl.GL_TEXTURE_ENV_MODE, gl.GL_MODULATE)
            
            gl.glEnable(gl.GL_TEXTURE_2D)
            gl.glBindTexture(gl.GL_TEXTURE_2D, active_tex_id)
            
            # Use slider sizing or fall back to 48px standard for textured cards
            chosen_size = getattr(prop, 'particle_draw_size', 48.0)
            gl.glPointSize(float(chosen_size)) 
            gl.glColor4f(1.0, 1.0, 1.0, 1.0)
        else:
            gl.glDisable(gl.GL_TEXTURE_2D)
            gl.glDisable(gl.GL_POINT_SPRITE)
            gl.glEnable(gl.GL_BLEND)
            gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)
            
            # Use slider sizing or fall back to 6px standard for flat dots
            chosen_size = getattr(prop, 'particle_draw_size', 6.0)
            gl.glPointSize(float(chosen_size))
            
            color = getattr(prop, 'particle_color', getattr(prop, 'color_rgba', [1.0, 0.4, 0.0, 1.0]))
            gl.glColor4f(float(color[0]), float(color[1]), float(color[2]), float(color[3]))

        gl.glEnableClientState(gl.GL_VERTEX_ARRAY)
        gl.glVertexPointer(3, gl.GL_FLOAT, 0, vertex_data)
        gl.glDrawArrays(gl.GL_POINTS, 0, len(vertex_data) // 3)

        gl.glDisableClientState(gl.GL_VERTEX_ARRAY)
        gl.glBindTexture(gl.GL_TEXTURE_2D, 0)
        gl.glPopAttrib()
        gl.glPopMatrix()
