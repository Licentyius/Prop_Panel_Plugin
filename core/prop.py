"""
Prop Module Build with Interactive Map Integration.
Part of the MakeHuman 2 Project contributed by Elvaerwyn_MH2 2026.
"""

import numpy as np
import os
from PySide6.QtWidgets import (QListWidget, QListWidgetItem, QDoubleSpinBox, QFormLayout, 
                             QComboBox, QCheckBox, QVBoxLayout, QPushButton, QLabel, QHBoxLayout)
from PySide6.QtCore import Qt, QSize 
from PySide6.QtGui import QVector3D, QIcon, QPixmap
from gui.common import MHGroupBox, ErrorBox, HintBox
from obj3d.object3d import object3d
from opengl.buffers import OpenGlBuffers, RenderedObject

from OpenGL import GL as gl

from ..gui.propstate import PropStateMachine
from ..gui.roommap import MHRoomLayoutMap
from core.debug import dumper

class MHRoomFloorGeometry:
    """Dynamically constructs an isolated 4-corner floor square mesh overlay."""
    def __init__(self, glob):
        self.glob = glob
        self.obj = object3d(self.glob, None, "room_floor")
        self.obj.setName("room_layout_bounds")
        self.obj.visible = True
        self.obj.filename = "data/templates/room_floor_dummy.obj"
        self.render = None

    def build_square_mesh(self, width, length):
        x_half = float(width) / 2.0
        z_half = float(length) / 2.0

        self.obj.gl_coord = np.array([
            [-x_half, 0.0, -z_half], [ x_half, 0.0, -z_half],
            [ x_half, 0.0,  z_half], [-x_half, 0.0,  z_half]
        ], dtype=np.float32)

        self.obj.gl_norm = np.array([
            [0.0, 1.0, 0.0], [0.0, 1.0, 0.0], [0.0, 1.0, 0.0], [0.0, 1.0, 0.0]
        ], dtype=np.float32)

        self.obj.gl_uvcoord = np.array([
            [0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]
        ], dtype=np.float32)

        self.obj.initMaterial()

        if self.render is not None:
            self.render.delete()

        glbuffer = OpenGlBuffers()
        glbuffer.GetBuffers(self.obj.gl_coord, self.obj.gl_norm, self.obj.gl_uvcoord)
        self.render = RenderedObject(self.glob.openGLWindow, self.obj, None, glbuffer)

    def delete(self):
        if self.render is not None:
            self.render.delete()

class PropObject:
    """Represents the metadata and structural transformation tracks of a scene prop."""
    def __init__(self, name, glob):
        self.glob = glob
        self.env = getattr(glob, 'env', None)
        self._name = "prop_" + name
        self._material = None

        from types import SimpleNamespace
        self.openGL = SimpleNamespace(setMaterial=lambda material, update=True: True)

        self.name = name
        self.visible = True
        self.parent_bone = "None" 
        self.use_parenting = False
        self.local_offset_pos = np.array([0.0, 0.0, 0.0], dtype=np.float64)
        self.path = ""
        self.mesh_reference = None 
        self.material_path = ""    

        self.position = np.array([0.0, 0.0, 0.0], dtype=np.float64)
        self.rotation = np.array([0.0, 0.0, 0.0], dtype=np.float64) 
        self.scale = np.array([1.0, 1.0, 1.0], dtype=np.float64)

    @property
    def obj(self):
        if hasattr(self, 'mesh_reference') and self.mesh_reference and hasattr(self.mesh_reference, 'obj'):
            if self.mesh_reference.obj is not None:
                return self.mesh_reference.obj
        return self

    def getLowestPos(self, posed=True):
        if hasattr(self, 'mesh_reference') and self.mesh_reference and hasattr(self.mesh_reference, 'obj'):
            if hasattr(self.mesh_reference.obj, 'getLowestPos'):
                return self.mesh_reference.obj.getLowestPos(posed)
        return 0.0

    @property
    def material(self):
        if self.material_path and os.path.isfile(self.material_path):
            return self.material_path
        if self.mesh_reference and hasattr(self.mesh_reference, 'obj'):
            core_obj = self.mesh_reference.obj
            if hasattr(core_obj, 'material') and core_obj.material:
                return getattr(core_obj.material, 'filename', '')
        return ""

    @material.setter
    def material(self, value):
        if isinstance(value, str):
            self.material_path = value
        elif hasattr(value, 'filename'):
            self.material_path = value.filename
        self._material = value

    def set_transform(self, pos=None, rot=None, scl=None):
        """Sets raw 3D transformations and updates bounding mesh volumes up to 100m."""
        if pos is not None: 
            self.position = np.array(pos, dtype=float)
            
            if hasattr(self, 'mesh_reference') and self.mesh_reference:
                mesh = self.mesh_reference
                if hasattr(mesh, 'clear_bounds'):
                    mesh.clear_bounds()
                
                if hasattr(mesh, 'bounds') and mesh.bounds:
                    mesh.bounds.min_x, mesh.bounds.max_x = -50.0, 50.0
                    mesh.bounds.min_y, mesh.bounds.max_y = -5.0,  50.0 
                    mesh.bounds.min_z, mesh.bounds.max_z = -50.0, 50.0
                    
                if hasattr(mesh, 'update_spatial_node'):
                    mesh.update_spatial_node()

        if rot is not None: self.rotation = np.array(rot, dtype=float)
        if scl is not None: self.scale = np.array(scl, dtype=float)

    def set_visibility(self, vis):
        self.visible = vis

class PropMesh:
    def __init__(self, glob):
        self.glob = glob
        self.env = getattr(glob, 'env', None)
        self.obj = object3d(self.glob, None, "props")
        self.orig_name = "unknown"

    def getObj(self):
        return self.obj

    def getOriginalName(self):
        return self.orig_name

    def load(self, path):
        (res, err) = self.obj.load(path, True)
        if res == 0:
            return False, self.env.last_error if self.env else "Mesh loading error context."

        self.orig_name = self.obj.name 
        self.obj.setName("props_" + path)
        self.obj.initMaterial()

        all_materials = self.obj.listAllMaterials()
        for mat in all_materials:
            if mat:
                self.obj.loadMaterial(mat)

        glbuffer = OpenGlBuffers()
        glbuffer.GetBuffers(self.obj.gl_coord, self.obj.gl_norm, self.obj.gl_uvcoord)
        self.render = RenderedObject(self.glob.openGLWindow, self.obj, None, glbuffer)
        self.obj.openGL = self.render
        return True, ""

    def refresh_material(self, new_material_path):
        if not self.obj or not os.path.isfile(new_material_path):
            return False
        if hasattr(self.obj, 'material') and self.obj.material:
            self.obj.material.freeTextures()
        self.obj.loadMaterial(new_material_path)
        return True

    def delete(self):
        if hasattr(self, 'render') and self.render:
            self.render.delete()
        if hasattr(self.obj, 'material') and self.obj.material:
            self.obj.material.freeTextures()

class PropManLeftPanel(QVBoxLayout):
    def __init__(self, parent):
        self.glob = parent.glob
        self.env = self.glob.env
        self.propman = parent.prop_manager
        self.prop_update = self.propman.syncedFromLeft
        self.propman.setLeftPanel(self)
        super().__init__()

        self.controls_group = MHGroupBox("Transform")
        self.form = QFormLayout()
        
        self.pos_x = self._make_spinbox()
        self.pos_y = self._make_spinbox()
        self.pos_z = self._make_spinbox()
        
        self.rot_x = self._make_spinbox(is_rotation=True)
        self.rot_y = self._make_spinbox(is_rotation=True)
        self.rot_z = self._make_spinbox(is_rotation=True)
        
        self.scl_all = self._make_spinbox(is_scale=True)
        self.scl_all.setValue(1.0) 

        self.scl_x = self._make_spinbox(is_scale=True)
        self.scl_x.setValue(1.0)
        self.scl_y = self._make_spinbox(is_scale=True)
        self.scl_y.setValue(1.0)
        self.scl_z = self._make_spinbox(is_scale=True)
        self.scl_z.setValue(1.0)

        self.form.addRow("X Pos:", self.pos_x)
        self.form.addRow("Y Pos:", self.pos_y)
        self.form.addRow("Z Pos:", self.pos_z)
        self.form.addRow("Pitch:", self.rot_x)
        self.form.addRow("Yaw:", self.rot_y)
        self.form.addRow("Roll:", self.rot_z)
        self.form.addRow("Uniform Scale:", self.scl_all)
        self.form.addRow("X Scale (Stretch):", self.scl_x)
        self.form.addRow("Y Scale (Height):", self.scl_y)
        self.form.addRow("Z Scale (Depth):", self.scl_z)

        self.controls_group.setLayout(self.form)
        self.addWidget(self.controls_group)

        # 2D Blueprint Map Drawing Interfaces
        cached_x = getattr(self.glob, 'last_cached_prop_x', 0.0)
        cached_z = getattr(self.glob, 'last_cached_prop_z', 0.0)
        cached_w = getattr(self.glob, 'last_cached_room_w', 8.0)
        cached_l = getattr(self.glob, 'last_cached_room_l', 8.0)

        self.addWidget(QLabel("<b>2D Room Layout Coordinate Grid:</b>"))
        self.room_map_widget = MHRoomLayoutMap(parent=parent) 
        self.room_map_widget.glob = self.glob
        self.room_map_widget.parent_obj = self.propman
        self.room_map_widget.setMinimumSize(QSize(340, 340))
        self.room_map_widget.setMaximumSize(QSize(340, 340))
        self.room_map_widget.set_prop_coordinates(cached_x, cached_z)
        self.room_map_widget.coordinatesChanged.connect(self.sync_map_to_spinboxes)
        
        map_centering_box = QHBoxLayout()
        map_centering_box.addWidget(self.room_map_widget)
        self.addLayout(map_centering_box)

        # Catalog Asset Inventory List
        self.prop_list = QListWidget()
        self.prop_list.setViewMode(QListWidget.ListMode)
        self.prop_list.currentItemChanged.connect(self.select_prop)
        self.addWidget(self.prop_list)

        # Asset Specification Profiles
        if hasattr(parent, 'equipment') and "props" in parent.equipment:
            img_sel = parent.equipment["props"].get("func", None)
            if img_sel:
                self.addWidget(QLabel("<b>Selected Asset Specification Profile:</b>"))
                from gui.imageselector import InformationBox
                
                self.left_infobox_layout = QVBoxLayout()
                self.left_prop_infobox = InformationBox(self.left_infobox_layout)
                self.addLayout(self.left_infobox_layout)
                img_sel.infobox = self.left_prop_infobox

        # 2D Room Boundary Planner Map Setup
        self.addWidget(QLabel("<b>2D Room Boundary Planner Map:</b>"))
        self.room_boundary_map_widget = MHRoomLayoutMap(parent=parent, is_boundary_planner=True) 
        self.room_boundary_map_widget.glob = self.glob
        self.room_boundary_map_widget.parent_obj = self.propman
        self.room_boundary_map_widget.setMinimumSize(QSize(340, 340))  
        self.room_boundary_map_widget.setMaximumSize(QSize(340, 340))
        self.room_boundary_map_widget.set_room_dimensions(cached_w, cached_l)
        self.room_boundary_map_widget.set_prop_coordinates(cached_x, cached_z)
        
        self.room_boundary_map_widget.roomResized.connect(self.execute_room_resize_preview)
        self.room_boundary_map_widget.roomResizeFinalized.connect(self.execute_room_resize_final)
        self.room_boundary_map_widget.coordinatesChanged.connect(self.sync_map_to_spinboxes)

        boundary_centering_box = QHBoxLayout()
        boundary_centering_box.addWidget(self.room_boundary_map_widget)
        self.addLayout(boundary_centering_box)

        self.room_floor_mesh = MHRoomFloorGeometry(self.glob)
        self.room_floor_mesh.build_square_mesh(cached_w, cached_l)

        self.pos_x.valueChanged.connect(self.syncToObject)
        self.pos_y.valueChanged.connect(self.syncToObject)
        self.pos_z.valueChanged.connect(self.syncToObject)
        self.rot_x.valueChanged.connect(self.syncToObject)
        self.rot_y.valueChanged.connect(self.syncToObject)
        self.rot_z.valueChanged.connect(self.syncToObject)
        self.scl_all.valueChanged.connect(self.sync_uniform_scale)
        self.scl_x.valueChanged.connect(self.syncToObject)
        self.scl_y.valueChanged.connect(self.syncToObject)
        self.scl_z.valueChanged.connect(self.syncToObject)

        self.addStretch(1)

    def select_prop(self, current, previous):
        if not current: 
            return
        current_prop = self.propman.setCurrentProp(current.text())

        # =====================================================================
        # >>> FIXED: CORRECTED INSTANCE VARIABLE LOOKUP TYPO >>>
        # =====================================================================
        if current_prop:
            self.setValueFromProp(current_prop)

    def leave(self):
        if hasattr(self, 'room_floor_mesh') and self.room_floor_mesh:
            self.room_floor_mesh.delete()

    def execute_room_resize_preview(self, new_width, new_length, handle_type="bottom_right"):
        w = max(1.0, float(new_width))
        l = max(1.0, float(new_length))
        
        delta_w = w - self.glob.last_cached_room_w
        delta_l = l - self.glob.last_cached_room_l
        
        self.glob.last_cached_room_w = w
        self.glob.last_cached_room_l = l
        
        if hasattr(self, 'room_floor_mesh') and self.room_floor_mesh:
            self.room_floor_mesh.build_square_mesh(w, l)
            
            if hasattr(self, 'room_floor_mesh', 'position') and isinstance(self.room_floor_mesh.position, list):
                if "top" in handle_type:
                    self.room_floor_mesh.position[2] -= delta_l * 0.5
                if "bottom" in handle_type:
                    self.room_floor_mesh.position[2] += delta_l * 0.5
                if "left" in handle_type:
                    self.room_floor_mesh.position[0] -= delta_w * 0.5
                if "right" in handle_type:
                    self.room_floor_mesh.position[0] += delta_w * 0.5
                
        if self.glob and getattr(self.glob, 'openGLWindow', None):
            self.glob.openGLWindow.update()

    def execute_room_resize_final(self, final_width, final_length, handle_type="bottom_right"):
        """Resizes the floor bounds, adjusts layout anchors, and updates prop spacing."""
        w = max(1.0, min(100.0, float(final_width)))
        l = max(1.0, min(100.0, float(final_length)))
        
        if self.glob and getattr(self.glob, 'baseClass', None):
            bc = self.glob.baseClass
            if hasattr(bc, 'scene') and bc.scene:
                
                old_w = bc.scene.floorsize[0] if hasattr(bc.scene, 'floorsize') and len(bc.scene.floorsize) > 0 else w
                old_l = bc.scene.floorsize[2] if hasattr(bc.scene, 'floorsize') and len(bc.scene.floorsize) > 2 else l
                
                delta_w = w - old_w
                delta_l = l - old_l

                if hasattr(bc.scene, 'floorsize') and isinstance(bc.scene.floorsize, list):
                    bc.scene.floorsize[0] = w   
                    bc.scene.floorsize[2] = l   
                    bc.scene.floorsize[1] = 0.2 
                    
                if "floorcuboid" in bc.scene.prims:
                    prim = bc.scene.prims["floorcuboid"]
                    prim.newSize(bc.scene.floorsize)
                    
                    shift_x = 0.0
                    shift_z = 0.0
                    
                    if "top" in handle_type:    shift_z = -delta_l * 0.5
                    if "bottom" in handle_type: shift_z = delta_l * 0.5
                    if "left" in handle_type:   shift_x = -delta_w * 0.5
                    if "right" in handle_type:  shift_x = delta_w * 0.5
                    
                    if hasattr(prim, 'position') and isinstance(prim.position, list):
                        prim.position[0] += shift_x
                        prim.position[2] += shift_z

                    custom_props = getattr(self.glob, 'custom_props_list', None)
                    if custom_props:
                        for prop_data in custom_props:
                            if not prop_data or getattr(prop_data, 'parent_bone', 'None') != "None":
                                continue
                                
                            if hasattr(prop_data, 'position') and isinstance(prop_data.position, np.ndarray):
                                old_center_x = prim.position[0] - shift_x
                                old_center_z = prim.position[2] - shift_z
                                
                                local_pct_x = (prop_data.position[0] - old_center_x) / (old_w if old_w > 0 else 1.0)
                                local_pct_z = (prop_data.position[2] - old_center_z) / (old_l if old_l > 0 else 1.0)
                                
                                prop_data.position[0] = prim.position[0] + (local_pct_x * w)
                                prop_data.position[2] = prim.position[2] + (local_pct_z * l)
                                
                                half_w = w * 0.5
                                half_l = l * 0.5
                                min_x, max_x = prim.position[0] - half_w, prim.position[0] + half_w
                                min_z, max_z = prim.position[2] - half_l, prim.position[2] + half_l
                                
                                prop_data.position[0] = max(min_x, min(max_x, prop_data.position[0]))
                                prop_data.position[2] = max(min_z, min(max_z, prop_data.position[2]))
                        
                bc.scene.update()
                
        if hasattr(self, 'prop_update') and self.prop_update:
            self.prop_update()
            
        if self.glob and getattr(self.glob, 'openGLWindow', None):
            self.glob.openGLWindow.update()

    def sync_map_to_spinboxes(self, *args):
        if len(args) == 2:
            raw_x, raw_z = float(args[0]), float(args[1])
        else:
            raw_x = getattr(self.glob, 'last_cached_prop_x', 0.0)
            raw_z = getattr(self.glob, 'last_cached_prop_z', 0.0)

        max_floor_dimension = 10.0
        if self.glob:
            max_floor_dimension = float(getattr(self.glob, 'last_cached_room_w', 10.0))
                    
        half_floor = max_floor_dimension / 2.0

        raw_x = max(-half_floor, min(half_floor, raw_x))
        raw_z = max(-half_floor, min(half_floor, raw_z))

        self.glob.last_cached_prop_x = raw_x
        self.glob.last_cached_prop_z = raw_z
        
        widgets_to_block = [self.pos_x, self.pos_y, self.pos_z, self.room_map_widget, self.room_boundary_map_widget]
        for widget in widgets_to_block:
            if widget: 
                widget.blockSignals(True)
        
        self.pos_x.setValue(raw_x)
        self.pos_z.setValue(raw_z)
        self.room_map_widget.set_prop_coordinates(raw_x, raw_z)
        if hasattr(self, 'room_boundary_map_widget'):
            self.room_boundary_map_widget.set_prop_coordinates(raw_x, raw_z)
            
        for widget in widgets_to_block:
            if widget: 
                widget.blockSignals(False)
            
        unique_scale = [self.scl_x.value(), self.scl_y.value(), self.scl_z.value()]
        new_rot = [self.rot_x.value(), self.rot_y.value(), self.rot_z.value()]
        new_pos = [raw_x, self.pos_y.value(), raw_z]
        self.prop_update(new_pos, new_rot, unique_scale)

    def syncToObject(self):
        new_pos = [self.pos_x.value(), self.pos_y.value(), self.pos_z.value()]
        new_rot = [self.rot_x.value(), self.rot_y.value(), self.rot_z.value()]
        unique_scale = [max(0.001, abs(self.scl_x.value())), max(0.001, abs(self.scl_y.value())), max(0.001, abs(self.scl_z.value()))]
            
        for widget in [self.room_map_widget, self.room_boundary_map_widget]:
            if widget:
                widget.blockSignals(True)
                widget.set_prop_coordinates(new_pos[0], new_pos[2])
                widget.blockSignals(False)

        self.prop_update(new_pos, new_rot, unique_scale)

    def resetValues(self):
        widgets_to_reset = [self.pos_x, self.pos_y, self.pos_z, self.rot_x, self.rot_y, self.rot_z, self.scl_all, self.scl_x, self.scl_y, self.scl_z]
        for widget in widgets_to_reset: 
            widget.blockSignals(True)
        for w in widgets_to_reset[:6]: 
            w.setValue(0.0)
        for w in widgets_to_reset[6:]: 
            w.setValue(1.0)
        for widget in widgets_to_reset: 
            widget.blockSignals(False)
        self.room_map_widget.set_prop_coordinates(0.0, 0.0)
        if hasattr(self, 'room_boundary_map_widget'): 
            self.room_boundary_map_widget.set_prop_coordinates(0.0, 0.0)

    def setValueFromProp(self, prop):
        if not prop: 
            return
        p_pos = getattr(prop, 'position', [0.0, 0.0, 0.0])
        px, py, pz = float(p_pos[0]), float(p_pos[1]), float(p_pos[2])

        widgets_to_block = [self.pos_x, self.pos_y, self.pos_z, self.rot_x, self.rot_y, self.rot_z, self.scl_all, self.scl_x, self.scl_y, self.scl_z]
        for widget in widgets_to_block: 
            widget.blockSignals(True)

        self.pos_x.setValue(px)
        self.pos_y.setValue(py)
        self.pos_z.setValue(pz)

        p_rot = getattr(prop, 'rotation', [0.0, 0.0, 0.0])
        self.rot_x.setValue(float(p_rot[0]))
        self.rot_y.setValue(float(p_rot[1]))
        self.rot_z.setValue(float(p_rot[2]))

        saved_scale = getattr(prop, 'scale', [1.0, 1.0, 1.0])
        sx, sy, sz = float(saved_scale[0]), float(saved_scale[1]), float(saved_scale[2])
        self.scl_all.setValue(sx)
        self.scl_x.setValue(sx)
        self.scl_y.setValue(sy)
        self.scl_z.setValue(sz)

        for widget in widgets_to_block: 
            widget.blockSignals(False)
        self.room_map_widget.set_prop_coordinates(px, pz)
        if hasattr(self, 'room_boundary_map_widget'): 
            self.room_boundary_map_widget.set_prop_coordinates(px, pz)

    def sync_uniform_scale(self, value):
        for widget in [self.scl_x, self.scl_y, self.scl_z]:
            widget.blockSignals(True)
            widget.setValue(float(value))
            widget.blockSignals(False)
        self.syncToObject()

    def _make_spinbox(self, is_rotation=False, is_scale=False):
        sb = QDoubleSpinBox()
        if is_rotation:
            sb.setRange(-360.0, 360.0)
            sb.setSuffix("°")
            sb.setSingleStep(1.0)
        elif is_scale:
            sb.setRange(0.001, 1000.0) 
            sb.setSingleStep(0.1)
        else:
            sb.setRange(-50.0, 50.0) 
            sb.setSingleStep(0.1)
        sb.setDecimals(3)
        return sb

class PropManagerPanel(MHGroupBox):
    def __init__(self, parent):
        super().__init__("Prop Manager")
        self.parent = parent 
        self.glob = getattr(parent, 'glob', None)
        self.env = self.glob.env
        self.view = getattr(parent, 'graph', None).view if hasattr(parent, 'graph') else None
        self.current_prop = None 
        self.leftPanel = None
        
        layout = QVBoxLayout()
        self.setLayout(layout)

        self.visibility_toggle = QCheckBox("Prop Visible in Viewport")
        self.visibility_toggle.setChecked(True)
        self.visibility_toggle.stateChanged.connect(self.toggle_visibility)
        layout.addWidget(self.visibility_toggle)

        self.parent_toggle = QCheckBox("Enable Bone Parenting")
        self.parent_toggle.stateChanged.connect(self.toggle_parenting)
        layout.addWidget(self.parent_toggle)

        self.bone_label = QLabel("Target Bone Connection:")
        layout.addWidget(self.bone_label)

        self.bone_selector = QComboBox()
        self.bone_selector.addItems(["None", "head", "hand_L", "hand_R", "foot_L", "foot_R", "spine_03"])
        self.bone_selector.setEnabled(False)
        self.bone_selector.currentIndexChanged.connect(self.findBonePosition)
        layout.addWidget(self.bone_selector)

        self.state_label = QLabel("Current State Pipeline: IDLE")
        layout.addWidget(self.state_label)

        # Action Controls and Hooks
        self.equip_trigger_btn = QPushButton("Action: Equip Selected Prop")
        self.equip_trigger_btn.clicked.connect(lambda: self.prop_fsm.transition_to(self.current_prop.name, "EQUIPPING") if self.current_prop else None)
        self.equip_trigger_btn.setStyleSheet("background-color: #2b8f5c; color: white; font-weight: bold; padding: 5px;")
        layout.addWidget(self.equip_trigger_btn)

        self.save_btn = QPushButton("Save Transform to JSON")
        self.save_btn.clicked.connect(self.save_prop_data)
        self.save_btn.setStyleSheet("padding: 5px;")
        layout.addWidget(self.save_btn)

        self.drop_all_btn = QPushButton("💥 Drop All Active Assets")
        self.drop_all_btn.clicked.connect(self.drop_all_workspace_assets)
        self.drop_all_btn.setStyleSheet("background-color: #6a5acd; color: white; font-weight: bold; padding: 5px;")
        layout.addWidget(self.drop_all_btn)

        self.remove_btn = QPushButton("❌ Remove Selected Prop")
        self.remove_btn.clicked.connect(self.remove_current_prop)
        self.remove_btn.setStyleSheet("background-color: #a13d3d; color: white; font-weight: bold; padding: 5px;")
        layout.addWidget(self.remove_btn)

        self.prop_fsm = PropStateMachine(panel_ref=self)

        from PySide6.QtCore import QTimer
        self.state_heartbeat_clock = QTimer(self)
        self.state_heartbeat_clock.timeout.connect(self.pump_state_machine_tick)
        self.state_heartbeat_clock.start(50)

    def setCurrentProp(self, prop_name):
        self.current_prop = self.find_prop_by_name(prop_name)
        prop_visible = getattr(self.current_prop, 'visible', True)
        prop_parenting = getattr(self.current_prop, 'use_parenting', False)
        prop_bone = getattr(self.current_prop, 'parent_bone', 'None')

        self.visibility_toggle.setChecked(prop_visible)
        self.parent_toggle.setChecked(prop_parenting)
        self.bone_selector.setEnabled(prop_parenting)
            
        idx = self.bone_selector.findText(prop_bone)
        if idx >= 0: 
            self.bone_selector.setCurrentIndex(idx)

        if hasattr(self, 'prop_fsm'):
            self.state_label.setText(f"Current State Pipeline: {self.prop_fsm.current_state_name}")

        return self.current_prop

    def pump_state_machine_tick(self):
        """Pumps continuous frame updates down to the state machine architecture safely."""
        if self.glob is not None:
            settings_panel = getattr(self.glob, 'scene_settings_panel', None)
            if settings_panel:
                master_w = float(getattr(settings_panel, 'floor_allowance_width', 4.0))
                master_l = float(getattr(settings_panel, 'floor_allowance_length', 4.0))
                
                self.glob.last_cached_room_w = master_w
                self.glob.last_cached_room_l = master_l
                
                if self.leftPanel:
                    if hasattr(self.leftPanel, 'room_map_widget') and self.leftPanel.room_map_widget:
                        self.leftPanel.room_map_widget.set_room_dimensions(master_w, master_l)
                    if hasattr(self.leftPanel, 'room_boundary_map_widget') and self.leftPanel.room_boundary_map_widget:
                        self.leftPanel.room_boundary_map_widget.set_room_dimensions(master_w, master_l)

        if self.current_prop and hasattr(self, 'prop_fsm'):
            active_name = self.current_prop.name
            current_run_state = getattr(self.prop_fsm, 'current_state_name', 'IDLE')
            self.state_label.setText(f"Current State Pipeline: {current_run_state}")

            if current_run_state in ["EQUIPPING", "USING"] or getattr(self.current_prop, 'use_parenting', False):
                self.prop_fsm.update_machine(active_name)
                target_bone_name = getattr(self.current_prop, 'parent_bone', 'None')
                bc = getattr(self.glob, 'baseClass', None)
                
                if bc and getattr(bc, 'skeleton', None) is not None and target_bone_name != "None":
                    skeleton = bc.skeleton
                    if target_bone_name in skeleton.bones:
                        bone = skeleton.bones[target_bone_name]
                        try:
                            bone_matrix = bone.getMatrix(posed=True) if hasattr(bone, 'getMatrix') else bone.matrix
                        except TypeError:
                            bone_matrix = bone.getMatrix()
                        
                        bone_world_pos = bone_matrix[:3, 3]
                        
                        if not hasattr(self.current_prop, 'local_offset_pos') or np.all(self.current_prop.local_offset_pos == 0.0):
                            self.current_prop.local_offset_pos = np.array([0.0, 0.1, 0.0])
                        
                        local_offset = self.current_prop.local_offset_pos
                        self.current_prop.position = np.array(bone_world_pos) + np.array(local_offset)
                        self.update_prop()

    def sync_sidebar_list_display(self):
        self.leftPanel.prop_list.clear()
        custom_pool = self.glob.custom_props_list
        for active_item in custom_pool:
            item_row = QListWidgetItem()
            item_row.setText(active_item.name)
            thumb_path = active_item.path.replace(".obj", ".thumb")
            if os.path.isfile(thumb_path):
                item_row.setIcon(QIcon(QPixmap(thumb_path)))
            else:
                placeholder_img = os.path.join("makehuman2/data/sysicons", "eq_props.png")
                if os.path.isfile(placeholder_img):
                    item_row.setIcon(QIcon(QPixmap(placeholder_img)))
            self.leftPanel.prop_list.addItem(item_row)

    def refreshProps(self, dtype):
        data = []
        custom_pool = self.glob.custom_props_list
        bc = getattr(self.glob, 'baseClass', None)
        target_dir = os.path.join(self.env.stdUserPath(), "props")
        sys_icon_dir = self.env.path_sysicon

        if os.path.isdir(target_dir):
            for filename in os.listdir(target_dir):
                if filename.lower().endswith('.obj'):
                    base_name, _ = os.path.splitext(filename)
                    full_obj_path = os.path.normpath(os.path.join(target_dir, filename)).replace("\\", "/")
                    is_active = any(getattr(p, 'path', '') == full_obj_path for p in custom_pool)
                    target_thumb = full_obj_path.replace(".obj", ".thumb")
                    
                    if not os.path.isfile(target_thumb):
                        placeholder_img = os.path.normpath(os.path.join(sys_icon_dir, "none.png")).replace("\\", "/")
                        if not os.path.isfile(placeholder_img):
                            placeholder_img = os.path.normpath(os.path.join(sys_icon_dir, "reset.png")).replace("\\", "/")
                        if os.path.isfile(placeholder_img):
                            try:
                                px = QPixmap(placeholder_img)
                                px.save(target_thumb, "PNG")
                            except Exception:
                                pass

                    uuid = f"props_{base_name}"
                    tags = ["systemasset", base_name, filename, "user"]

                    if not any(getattr(a, 'path', '') == full_obj_path for a in self.glob.cachedInfo):
                        from core.globenv import cacheRepoEntry
                        native_asset = cacheRepoEntry(name=base_name, uuid=uuid, path=full_obj_path, folder="props", subfolder=None, thumbfile=target_thumb, author="User", tag=tags)
                        native_asset.filename = full_obj_path
                        native_asset.used = is_active
                        self.glob.cachedInfo.append(native_asset)
                    else:
                        for a in self.glob.cachedInfo:
                            if getattr(a, 'path', '') == full_obj_path: 
                                a.used = is_active

        for asset in self.glob.cachedInfo:
            if getattr(asset, 'folder', '') == "props":
                is_active = any(getattr(p, 'path', '') == asset.path for p in custom_pool)
                data.append([asset.name, "Active in Scene" if is_active else "Available File", "Double-click icon to remove" if is_active else "Click icon to add"])
                
        if "props" in getattr(self.parent, 'equipment', {}):
            props_tab_ui = self.parent.equipment["props"].get("func")
            if props_tab_ui and hasattr(props_tab_ui, 'refreshButtons'): 
                props_tab_ui.refreshButtons()
        return data

    def global_pipeline_refresh(self):
        self.sync_sidebar_list_display()
        self.refreshProps("props")
        self._trigger_viewport_redraw()

    def find_prop_by_name(self, prop_name):
        for prop in self.glob.custom_props_list:
            if getattr(prop, 'name', '') == prop_name: 
                return prop
        return None

    def add_prop_to_scene(self, asset):
        target_path = os.path.normpath(getattr(asset, 'path', getattr(asset, 'filename', str(asset))))
        pm = PropMesh(self.glob)
        res, err = pm.load(target_path)
        if res is False: 
            return False, err

        obj = pm.getObj()
        name = pm.getOriginalName()

        initial_pos = [0.0, 0.0, 0.0]
        initial_rot = [0.0, 0.0, 0.0]
        initial_scale = [1.0, 1.0, 1.0]
        initial_vis = True
        use_parent = False
        target_bone = "None"
        
        json_path = target_path.replace(".obj", ".json")
        if os.path.isfile(json_path):
            config_data = self.env.readJSON(json_path)
            if config_data is not None:
                name = config_data.get("name", name)
                initial_pos = config_data.get("offset", initial_pos)
                initial_rot = config_data.get("rotation", initial_rot)
                initial_scale = config_data.get("scale", initial_scale)
                initial_vis = config_data.get("visible", initial_vis)
                parenting_block = config_data.get("parenting", {})
                use_parent = parenting_block.get("enabled", use_parent)
                target_bone = parenting_block.get("target_bone", target_bone)

        s_val = float(initial_scale[0]) if isinstance(initial_scale, (list, np.ndarray, tuple)) else float(initial_scale)
        t_struct = {"translation": [float(p) for p in initial_pos], "rotation": [float(r) for r in initial_rot], "scale": [s_val, s_val, s_val]}

        if self.glob.prop_manager_pipeline:
            self.glob.prop_manager_pipeline.registerProp(name, obj, parent_bone=target_bone, relative_transform=t_struct)
        
        new_prop = PropObject(name, self.glob)
        new_prop.mesh_reference = pm 
        new_prop.path = target_path.replace("\\", "/")
        new_prop.position = [float(p) for p in initial_pos]
        new_prop.rotation = [float(r) for r in initial_rot]
        new_prop.scale = [s_val, s_val, s_val]
        new_prop.visible = initial_vis
        new_prop.use_parenting = use_parent
        new_prop.parent_bone = target_bone

        print(dumper(new_prop))
        
        self.current_prop = new_prop
        self.glob.custom_props_list.append(new_prop)

        if self.leftPanel: 
            self.leftPanel.setValueFromProp(new_prop)
            
        self.glob.openGLWindow.update()
        self.sync_sidebar_list_display()
        return True, ""

    def setLeftPanel(self, left):
        self.leftPanel = left

    def toggle_visibility(self, state):
        if self.current_prop: 
            self.current_prop.visible = (state != 0)

    def toggle_parenting(self, state):
        is_checked = (state == 2)
        self.bone_selector.setEnabled(is_checked)
        if self.current_prop and hasattr(self, 'prop_fsm'):
            if not is_checked and self.prop_fsm.current_state_name == "USING":
                self.prop_fsm.transition_to(self.current_prop.name, "UNEQUIPPING")
                return
            self.current_prop.use_parenting = is_checked
            self.current_prop.parent_bone = self.bone_selector.currentText() if is_checked else "None"
        self.update_prop()

    def syncedFromLeft(self, new_pos, new_rot, scl):
        if self.current_prop is not None: 
            self.current_prop.set_transform(pos=new_pos, rot=new_rot, scl=scl)
        self._trigger_viewport_redraw()

    def update_prop(self):
        if not self.current_prop: 
            return
        
        is_parented = getattr(self.current_prop, 'use_parenting', False)
        sm = getattr(self, 'state_machine', getattr(self.glob, 'prop_state_machine', None))
        
        pos = self.current_prop.position
        rot = self.current_prop.rotation
        scl = self.current_prop.scale
        
        if is_parented and sm and hasattr(sm, 'get_export_matrix'):
            bone_name, compound_matrix = sm.get_export_matrix(self.current_prop.name)
            pos = [compound_matrix[0, 3], compound_matrix[1, 3], compound_matrix[2, 3]]
            
            import math
            R = compound_matrix[0:3, 0:3]
            try:
                sy = math.sqrt(R[0,0] * R[0,0] + R[1,0] * R[1,0])
                if sy > 1e-6:
                    rx = math.atan2(R[2,1], R[2,2])
                    ry = math.atan2(-R[2,0], sy)
                    rz = math.atan2(R[1,0], R[0,0])
                else:
                    rx = math.atan2(-R[1,2], R[1,1])
                    ry = math.atan2(-R[2,0], sy)
                    rz = 0
                rot = [math.degrees(rx), math.degrees(ry), math.degrees(rz)]
            except Exception:
                pass 
        
        if self.glob.prop_manager_pipeline:
            self.glob.prop_manager_pipeline.updatePropTransform(self.current_prop.name, translation=pos, rotation=rot, scale=scl)
            if hasattr(self.current_prop, 'mesh_reference') and self.current_prop.mesh_reference:
                pm_mesh = self.current_prop.mesh_reference
                prop_mat_path = getattr(self.current_prop, 'material_path', '')
                if prop_mat_path and os.path.isfile(prop_mat_path): 
                    pm_mesh.refresh_material(prop_mat_path)
                if hasattr(pm_mesh, 'render') and pm_mesh.render:
                    glbuffer = OpenGlBuffers()
                    glbuffer.GetBuffers(pm_mesh.obj.gl_coord, pm_mesh.obj.gl_norm, pm_mesh.obj.gl_uvcoord)
                    pm_mesh.render.buffers = glbuffer
                    
        self._trigger_viewport_redraw()

    def remove_current_prop(self, current=None):
        if current is None:
            current = self.current_prop

        if current is None:
            return

        if hasattr(self.current_prop, 'mesh_reference') and self.current_prop.mesh_reference:
            self.current_prop.mesh_reference.delete()

        self.bone_selector.blockSignals(True)
        self.visibility_toggle.blockSignals(True)
        self.parent_toggle.blockSignals(True)
        
        target_uniq = current.path
        custom_pool = self.glob.custom_props_list
        for i in range(len(custom_pool) - 1, -1, -1):
            if getattr(custom_pool[i], 'path', '') == target_uniq: 
                custom_pool.pop(i)
            
        self.sync_sidebar_list_display()
        self.refreshProps("props")

        self.current_prop = None
        if self.leftPanel is not None: 
            self.leftPanel.resetValues()
            
        self.visibility_toggle.setChecked(True)
        self.parent_toggle.setChecked(False)
        self.bone_selector.setEnabled(False)
        self.bone_selector.setCurrentIndex(0)

        self.visibility_toggle.blockSignals(False)
        self.bone_selector.blockSignals(False)
        self.parent_toggle.blockSignals(False)
        self._trigger_viewport_redraw()

    def drop_all_workspace_assets(self):
        custom_pool = self.glob.custom_props_list
        if not custom_pool: 
            return
        for i in range(len(custom_pool) - 1, -1, -1):
            prop = custom_pool[i]
            if prop:
                if hasattr(self, 'prop_fsm') and self.prop_fsm: 
                    self.prop_fsm.transition_to(prop.name, "UNEQUIPPING")
                else:
                    prop.use_parenting = False
                    prop.parent_bone = "None"
                    if hasattr(prop, 'position') and isinstance(prop.position, (list, np.ndarray)) and len(prop.position) >= 3: 
                        prop.position = 0.0

        self.parent_toggle.blockSignals(True)
        self.bone_selector.blockSignals(True)
        self.parent_toggle.setChecked(False)
        self.bone_selector.setEnabled(False)
        self.bone_selector.setCurrentText("None")
        self.parent_toggle.blockSignals(False)
        self.bone_selector.blockSignals(False)

        self.sync_sidebar_list_display()
        self.refreshProps("props")
        self._trigger_viewport_redraw()

    def _trigger_viewport_redraw(self):
        if self.view: 
            self.view.Tweak()
        elif self.glob and getattr(self.glob, 'openGLWindow', None): 
            self.glob.openGLWindow.Tweak()

    def save_prop_data(self):
        if self.current_prop and getattr(self.current_prop, 'path', ''):
            sx, sy, sz = 1.0, 1.0, 1.0
            if self.leftPanel:
                sx = max(0.001, abs(float(self.leftPanel.scl_x.value())))
                sy = max(0.001, abs(float(self.leftPanel.scl_y.value())))
                sz = max(0.001, abs(float(self.leftPanel.scl_z.value())))

            data = {
                "name": self.current_prop.name,
                "visible": getattr(self.current_prop, 'visible', True),
                "offset": [float(p) for p in self.current_prop.position],
                "rotation": [float(r) for r in self.current_prop.rotation],
                "scale": [sx, sy, sz],
                "parenting": {"enabled": self.parent_toggle.isChecked(), "target_bone": self.bone_selector.currentText()}
            }
            json_path = self.current_prop.path.replace(".obj", ".json")
            if not self.env.writeJSON(json_path, data): 
                ErrorBox(self.parent.central_widget, self.env.last_error)
            else: 
                HintBox(self.parent.central_widget, "Saved transform profile to: " + json_path)

    def findBonePosition(self):
        pbone = self.bone_selector.currentText()
        if pbone == "None" or not self.parent_toggle.isChecked(): 
            return
        bc = self.glob.baseClass
        if bc is None: 
            return
        pinfo = bc.baseInfo
        if not "props" in pinfo or pbone not in pinfo["props"]: 
            return
        pbone = pinfo["props"][pbone]
        skeleton = bc.pose_skeleton if bc.in_posemode else bc.skeleton
        if skeleton is None: 
            skeleton = bc.default_skeleton
        if skeleton is None: 
            return
        if pbone in skeleton.bones:
            bone = skeleton.bones[pbone]
            b_coord = bone.posetailPos if bc.in_posemode else bone.tailPos
            if self.current_prop: 
                self.current_prop.position += b_coord
