######
#
# Prop Renderer  V1.0 by Elvaerwyn MH_2 2026
# For use in the prop panel plugin for Makehuman 2
#
######

import numpy as np
from OpenGL import GL as gl
from core.particle_engine import live_particle_system

def inject_particle_gl_draw_pass(custom_props_list):
    """
    Streams raw 3D coordinate floating point arrays straight to the 
    active MakeHuman 2 graphics buffer context.
    """
    # Run our background physics computation pass right before forcing a repaint draw
    live_particle_system.tick_physics(custom_props_list)

    for prop in custom_props_list:
        if getattr(prop, 'object_type', 'STATIC') != 'EMITTER':
            continue

        prop_id = getattr(prop, 'name', None)
        # Pull your flat coordinates array [x1, y1, z1, x2, y2, z2, ...]
        vertices = live_particle_system.extract_flat_vertex_array(prop_id)

        if not vertices:
            continue

        # Convert raw Python lists to fast native hardware float32 memory chunks
        vertex_data = np.array(vertices, dtype=np.float32)

        # Retrieve saved hex/array configurations from your JSON manifest definitions
        color = getattr(prop, 'particle_color', [1.0, 0.4, 0.0, 1.0])

        # ==========================================
        # IMMEDIATE OPENGL PRIMITIVE DRAW COMMANDS
        # ==========================================
        gl.glPushMatrix()
        gl.glPushAttrib(gl.GL_POINT_BIT | gl.GL_CURRENT_BIT | gl.GL_ENABLE_BIT)
        
        # Strip lighting constraints so your particles glow independently in dark areas
        gl.glDisable(gl.GL_LIGHTING)
        gl.glPointSize(6.0) # Visual weight thickness assignment
        
        # Bind structural color definitions
        gl.glColor4f(float(color[0]), float(color[1]), float(color[2]), float(color[3]))

        # Initialize native client-side pipeline array pointers
        gl.glEnableClientState(gl.GL_VERTEX_ARRAY)
        gl.glVertexPointer(3, gl.GL_FLOAT, 0, vertex_data)

        # Fire a hardware command drawing raw structural vertices as standalone points
        gl.glDrawArrays(gl.GL_POINTS, 0, len(vertex_data) // 3)

        # Flush arrays and safely restore matrix attributes to protect your scene meshes
        gl.glDisableClientState(gl.GL_VERTEX_ARRAY)
        gl.glPopAttrib()
        gl.glPopMatrix()
