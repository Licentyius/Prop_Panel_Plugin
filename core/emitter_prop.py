######
#
# Emitter Prop object type V1.4 Elvaerwyn_MH2 2026
# For use in the prop panel plugin for Makehuman 2
#
######

import random
import time
import os
import numpy as np
from PySide6.QtGui import QVector3D
from OpenGL import GL as gl
from obj3d.object3d import object3d
from opengl.buffers import OpenGlBuffers, RenderedObject
from opengl.texture import MH_Texture

class MH2LiveEmitterProp:
    def __init__(self, glob, prop_id, raw_json_data):
        self.glob = glob        

        self.prop_id = str(prop_id).strip().lower()
        self.light = self.glob.openGLWindow.light
        
        if raw_json_data is None:
            raw_json_data = {}
            
        self.name = raw_json_data.get("name", "Unnamed Emitter")
        self.mesh_path = raw_json_data.get("mesh_path", "")
        self.emitter_obj_path = raw_json_data.get("emitter_object", None)
        self.is_mesh_visible = raw_json_data.get("is_mesh_visible", True)
        self.max_particles = raw_json_data.get("particle_count", 300)
        self.parented = raw_json_data.get("use_parenting", False)

        self.particle_color = raw_json_data.get("color_rgba", raw_json_data.get("particle_color", [1.0, 0.3, 1.0, 1.0]))
        self.a = float(self.particle_color[3]) if len(self.particle_color) >= 4 else 1.0
        self.r, self.g, self.b = float(self.particle_color[0]), float(self.particle_color[1]), float(self.particle_color[2])

        self.default_bone = raw_json_data.get("default_bone", "hand_R")
        self.emitter_mode = raw_json_data.get("emitter_mode", "PARTICLES").upper().strip()
        self.particle_texture = raw_json_data.get("particle_texture", "PLAIN")
        self.particle_draw_size = float(raw_json_data.get("particle_draw_size", 6.0))

        self.world_position = [0.0, 0.814, 0.0]
        self.texture = None
        self.obj = None             
        self.mesh_buffers = None    
        self.render = None          
        self.particles_pool = []    
        self.particles = np.array([], dtype=np.float32)

    def loadParticleMesh(self, path=None):
        if self.emitter_mode != "PHYSICAL_MESH":
            return True, "No mesh"
        if path is not None:
            self.emitter_obj_path = path
        self.obj = object3d(self.glob, None, "props")
        success, err = self.obj.load(self.emitter_obj_path, True)
        if not success:
            return False, err
        self.obj.initMaterial() 
        self.mesh_buffers = OpenGlBuffers()
        self.mesh_buffers.GetBuffers(self.obj.gl_coord, self.obj.gl_norm, self.obj.gl_uvcoord)
        self.render = RenderedObject(self.glob.openGLWindow, self.obj, None, self.mesh_buffers)
        return True, "okay"

    def loadParticleTexture(self):
        if self.emitter_mode != "TEXTURED_SPRITES":
            return True
        name = os.path.join(self.glob.env.path_sys, self.particle_texture)
        texture = MH_Texture(self.glob)
        self.texture = texture.load(name)
        if self.texture is None:
            self.emitter_mode = "PARTICLES"
        return self.texture

    def drawMesh(self, proj_view_matrix, campos):
        """Unified mesh instances position loop handles both dictionary formats and raw NumPy arrays safely."""
        for p in self.particles_pool:
            try:
                # Extract scalars safely from objects OR arrays
                if hasattr(p, 'x') and not isinstance(p, (np.ndarray, list, tuple)):
                    px, py, pz = float(p.x), float(p.y), float(p.z)
                elif hasattr(p, '__getitem__') or isinstance(p, (np.ndarray, list, tuple)):
                    px, py, pz = float(p[0]), float(p[1]), float(p[2])
                else:
                    continue
                
                self.render.setPosition(QVector3D(px, py, pz))
                self.render.setScale(QVector3D(float(p.scale[0]), float(p.scale[1]), float(p.scale[2])))
                self.render.setXRotation(p.rotation[0])
                self.render.setYRotation(p.rotation[1])
                self.render.setZRotation(p.rotation[2])
                self.render.draw(proj_view_matrix, campos, self.light, False)
            except Exception:
                pass # Fail silently on corrupted frames to protect the timeline execution pulse

    def newParticles(self, cnt):
        for _ in range(cnt):
            self.particles_pool.append(MH2PropParticle(self))

    def flushDead(self):
        self.particles_pool = [p for p in self.particles_pool if not p.is_dead()]

    def poolCopy(self):
        """
        Extract individual scalar elements by index explicitly!
        """
        flat_list = []
        for part in self.particles_pool:
            try:
                # Unpack the absolute coordinate positions cleanly by their index properties
                px = float(part.x[0]) if hasattr(part.x, '__getitem__') else float(part.x)
                py = float(part.y[1]) if hasattr(part.y, '__getitem__') else float(part.y)
                pz = float(part.z[2]) if hasattr(part.z, '__getitem__') else float(part.z)
                
                flat_list.extend([px, py, pz])
            except Exception:
                # Direct scalar fallback if the vectors are single floats
                flat_list.extend([float(part.x), float(part.y), float(part.z)])
            
        # Convert the continuous 1D sequence safely into the contiguous array structure
        self.particles = np.array(flat_list, dtype=np.float32)

    def getBonePosition(self):
        bc = self.glob.baseClass
        coord, bone = bc.getVirtualBonePosition(self.default_bone)
        if bone is not None:
            return [float(coord[0]), float(coord[1]), float(coord[2])]
        return self.world_position 

    def loop(self, new, progress):
        # 1. Update birth origin cleanly from the skeletal bone transformations matrix
        if self.parented:
            self.world_position = self.getBonePosition()

        # 2. Spawn particles up to current master manifest cap limit
        if len(self.particles_pool) < int(self.max_particles):
            self.newParticles(new)

        # 3. Apply a stable physics frame delta step calculation
        dt = float(progress) if (progress and float(progress) > 0.0) else 0.033

        # 4. Progress coordinates smoothly forward along velocity vectors
        for p in self.particles_pool:
            p.update(dt)          

        self.flushDead()
        self.poolCopy()

    def startOpenGL(self):
        gl.glPushMatrix()
        gl.glPushAttrib(gl.GL_POINT_BIT | gl.GL_CURRENT_BIT | gl.GL_ENABLE_BIT | gl.GL_TEXTURE_BIT)
        gl.glDisable(gl.GL_LIGHTING)

        gl.glEnable(gl.GL_NORMALIZE)

    def finishOpenGL(self):
        if hasattr(self, 'particles') and self.particles is not None and len(self.particles) > 0:
            gl.glEnableClientState(gl.GL_VERTEX_ARRAY)
            gl.glVertexPointer(3, gl.GL_FLOAT, 0, self.particles)
            gl.glDrawArrays(gl.GL_POINTS, 0, len(self.particles) // 3)
            gl.glDisableClientState(gl.GL_VERTEX_ARRAY)
        gl.glBindTexture(gl.GL_TEXTURE_2D, 0)
        gl.glPopAttrib()
        gl.glPopMatrix()

    def drawDustParticles(self):
        self.startOpenGL()
        gl.glDisable(gl.GL_TEXTURE_2D)
        gl.glDisable(gl.GL_POINT_SPRITE)
        gl.glEnable(gl.GL_BLEND)
        gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)
        gl.glPointSize(self.particle_draw_size)
        self.finishOpenGL()

    def drawSprites(self):
        self.startOpenGL()
        gl.glEnable(gl.GL_BLEND)
        gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)
        gl.glDisable(gl.GL_TEXTURE_2D)
        gl.glEnable(gl.GL_POINT_SPRITE)
        gl.glTexEnvi(gl.GL_POINT_SPRITE, gl.GL_COORD_REPLACE, gl.GL_TRUE)
        gl.glPointSize(self.particle_draw_size if self.particle_draw_size > 6.0 else 16.0)
        gl.glColor4f(self.r, self.g, self.b, self.a)
        self.finishOpenGL()

    def drawTexSprites(self):
        """Unified alpha shader pass binds native QOpenGLTextures and protects the stack."""
        try:
            self.startOpenGL()
            gl.glEnable(gl.GL_BLEND)
            gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE) # Immersive additive alpha blending
            gl.glEnable(gl.GL_POINT_SPRITE)
            gl.glTexEnvi(gl.GL_POINT_SPRITE, gl.GL_COORD_REPLACE, gl.GL_TRUE)
            gl.glEnable(gl.GL_TEXTURE_2D)
            gl.glActiveTexture(gl.GL_TEXTURE0)
            
            if self.texture is not None:

                # Call the native PySide6 .bind() routine directly on the QOpenGLTexture object wrapper!
                if hasattr(self.texture, 'bind'):
                    self.texture.bind() 
                elif hasattr(self.texture, 'textureId'):
                    gl.glBindTexture(gl.GL_TEXTURE_2D, self.texture.textureId())
                elif hasattr(self.texture, 'id'):
                    gl.glBindTexture(gl.GL_TEXTURE_2D, self.texture.id)
                else:
                    gl.glBindTexture(gl.GL_TEXTURE_2D, int(self.texture))
                
            gl.glPointSize(self.particle_draw_size if self.particle_draw_size > 6.0 else 48.0)
            gl.glColor4f(1.0, 1.0, 1.0, 1.0)
        except Exception as e:
            print(f"[Prop Studio Render Warning] Tex Sprite execution failed: {e}")
        finally:
            # Guarantees that OpenGL pops states even if an asset lookup glitches!
            self.finishOpenGL()

    def drawBillboards(self, campos):
        """MODE 5: True 3D Oriented Camera-Facing Billboard Quads Passes."""
        if not hasattr(self, 'particles_pool') or not self.particles_pool:
            return

        try:
            self.startOpenGL()
            gl.glEnable(gl.GL_BLEND)
            gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE)
            gl.glEnable(gl.GL_TEXTURE_2D)
            if self.texture and hasattr(self.texture, 'textureId'):
                gl.glBindTexture(gl.GL_TEXTURE_2D, self.texture.textureId())

            modelview = gl.glGetFloatv(gl.GL_MODELVIEW_MATRIX)
            right = [modelview[0], modelview[4], modelview[8]]
            up = [modelview[1], modelview[5], modelview[9]]

            size = self.particle_draw_size * 0.01  
            
            gl.glBegin(gl.GL_QUADS)
            for p in self.particles_pool:
                try:

                    if hasattr(p, 'x') and not isinstance(p, (np.ndarray, list, tuple)):
                        px, py, pz = float(p.x), float(p.y), float(p.z)
                    elif isinstance(p, dict) and "pos" in p:
                        v = p["pos"]
                        px, py, pz = float(v[0]), float(v[1]), float(v[2])
                    elif hasattr(p, '__getitem__') or isinstance(p, (np.ndarray, list, tuple)):
                        px, py, pz = float(p[0]), float(p[1]), float(p[2])
                    else:
                        continue

                    gl.glColor4f(1.0, 1.0, 1.0, 1.0)
                    
                    gl.glTexCoord2f(0.0, 0.0)
                    gl.glVertex3f(px - (right[0] + up[0]) * size, py - (right[1] + up[1]) * size, pz - (right[2] + up[2]) * size)
                    gl.glTexCoord2f(1.0, 0.0)
                    gl.glVertex3f(px + (right[0] - up[0]) * size, py + (right[1] - up[1]) * size, pz + (right[2] - up[2]) * size)
                    gl.glTexCoord2f(1.0, 1.0)
                    gl.glVertex3f(px + (right[0] + up[0]) * size, py + (right[1] + up[1]) * size, pz + (right[2] + up[2]) * size)
                    gl.glTexCoord2f(0.0, 1.0)
                    gl.glVertex3f(px - (right[0] - up[0]) * size, py - (right[1] - up[1]) * size, pz - (right[2] - up[2]) * size)
                except Exception:
                    pass
            gl.glEnd()
        except Exception as e:
            print(f"[Prop Studio Debug] Billboard render cycle failed: {e}")
        finally:
            self.finishOpenGL()

class MH2PropParticle:
    """A single particle element spawned by an emitter prop module."""
    def __init__(self, emitter):
        # 1. Skeletal tracking bone joint center offsets
        base_x = float(emitter.world_position[0]) if hasattr(emitter.world_position, '__getitem__') else float(emitter.world_position)
        base_y = float(emitter.world_position[1]) if hasattr(emitter.world_position, '__getitem__') else float(emitter.world_position)
        base_z = float(emitter.world_position[2]) if hasattr(emitter.world_position, '__getitem__') else float(emitter.world_position)

        offset_x = 0.0
        offset_y = 0.0
        offset_z = 0.0
        
        if hasattr(emitter, 'obj') and emitter.obj and hasattr(emitter.obj, 'gl_coord'):
            coords = emitter.obj.gl_coord
            if coords is not None and len(coords) > 0:
                offset_x = float(np.mean([c[0] for c in coords]))
                offset_y = float(np.mean([c[1] for c in coords]))
                offset_z = float(np.mean([c[2] for c in coords]))

        self.x = base_x + offset_x
        self.y = base_y + offset_y
        self.z = base_z + offset_z
 
        raw_color = getattr(emitter, 'particle_color', [1.0, 0.4, 0.0, 1.0])
        if hasattr(raw_color, 'color_rgba'):
            raw_color = raw_color.color_rgba
        elif hasattr(raw_color, 'particle_color'):
            raw_color = raw_color.particle_color

        if isinstance(raw_color, (list, tuple)) and len(raw_color) >= 3:
            self.color = [float(c) for c in raw_color[:4]]
            if len(self.color) == 3:
                self.color.append(1.0)
        else:
            self.color = [1.0, 0.4, 0.0, 1.0]
        
        # High-velocity trajectories to shoot them into viewport space
        self.vx = random.uniform(-0.5, 0.5)
        self.vy = random.uniform(4.5, 9.0)  
        self.vz = random.uniform(-0.5, 0.5)

        self.rotation = [random.uniform(0, 360), random.uniform(0, 360), random.uniform(0, 360)]
        self.scale = [0.1, 0.1, 0.1]
        self.lifetime = 0.0
        self.lifespan = random.uniform(0.6, 1.5)

    def is_dead(self):
        return self.lifetime > self.lifespan

    def update(self, span):
        """Unified particle physics updater advances coordinates along velocity vectors."""
        # Use a constant fallback fraction to bypass any framework thread delays
        dt = 0.033

        self.lifetime += dt
        
        # Advance positions forward along their velocity vectors
        self.x += self.vx * dt
        self.y += self.vy * dt  
        self.z += self.vz * dt
        
        # Apply stable down-axis gravity drag over time frames
        self.vy -= 2.5 * dt
