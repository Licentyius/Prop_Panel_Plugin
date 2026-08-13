#####
## Prop Module v2.0 
## Part of the MakeHuman 2 Project contributed by Elvaerwyn_MH2 2026
#####

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

from .propstate import PropStateMachine
from .roommap import MHRoomLayoutMap
from core.json_manager import load_props_manifest, update_prop_json_entry
from core.json_io import save_prop_changes_to_json
from core.emitter_prop import MH2LiveEmitterProp
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

#class PropObject(object3d):
class PropObject():
    """Represents the metadata and structural transformation tracks of a scene prop."""
    def __init__(self, name, glob):
        self.glob = glob
        # super(object3d, self).__init__(self.glob, None, "props")
        self.env = getattr(glob, 'env', None)
        self._name = "prop_" + name
        self._material = None

        from types import SimpleNamespace
        self.openGL = SimpleNamespace(setMaterial=lambda material, update=True: True)

        self.name = name
        self.visible = True
        self.parent_bone = "None" 
        self.use_parenting = False
        self.local_offset_pos = np.array([0.0, 0.0, 0.0])
        self.path = ""
        self.mesh_reference = None 
        self.material_path = ""    

        self.position = np.array([0.0, 0.0, 0.0])
        self.rotation = np.array([0.0, 0.0, 0.0]) 
        self.scale = np.array([1.0, 1.0, 1.0])

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
        if pos is not None: self.position = np.array(pos, dtype=float)
        if rot is not None: self.rotation = np.array(rot, dtype=float)
        if scl is not None: self.scale = np.array(scl, dtype=float)

    def set_visibility(self, vis):
        self.visible = vis

class PropMesh():
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
        # Establish local asset folder tracking path dynamically
        base_asset_directory = os.path.dirname(os.path.abspath(path))
        
        class DecoupledEnvSandboxProxy:
            def __init__(self, original_env):
                self._original = original_env
            def stdSysPath(self, itype):
                return base_asset_directory
            def __getattr__(self, name):
                return getattr(self._original, name)

        self.obj.env = DecoupledEnvSandboxProxy(self.env)

        (res, err) = self.obj.load(path, True)
        if res == 0:
            return False, self.env.last_error if self.env else "Mesh loading error context."

        self.orig_name = self.obj.name 
        self.obj.setName("props_" + path)
        self.obj.initMaterial()

        all_materials = self.obj.listAllMaterials()
        for mat in all_materials:
            if mat:
                if not os.path.isabs(mat) and os.path.exists(os.path.join(base_asset_directory, mat)):
                    mat_target_route = os.path.join(base_asset_directory, mat)
                else:
                    mat_target_route = mat
                
                try:
                    self.obj.loadMaterial(mat_target_route)
                except Exception as ex:
                    print(f"[Prop Studio Warning] Suppressed local texture path failure: {ex}")

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

        self.inventory_table = QTableWidget()
        self.inventory_table.setColumnCount(3)
        self.inventory_table.setHorizontalHeaderLabels(["Name", "Status", "Action"])
        header = self.inventory_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.addWidget(self.inventory_table)

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

        self.prop_list = QListWidget()
        self.prop_list.setViewMode(QListWidget.ListMode)
        self.prop_list.currentItemChanged.connect(self.select_prop)
        self.addWidget(self.prop_list)

        self.build_emitter_ui_context(parent_layout)

        if hasattr(parent, 'equipment') and "props" in parent.equipment:
            img_sel = parent.equipment["props"].get("func", None)
            if img_sel:
                self.addWidget(QLabel("<b>Selected Asset Specification Profile:</b>"))
                from gui.imageselector import InformationBox
                
                self.left_infobox_layout = QVBoxLayout()
                self.left_prop_infobox = InformationBox(self.left_infobox_layout)
                self.addLayout(self.left_infobox_layout)
                img_sel.infobox = self.left_prop_infobox

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

    def refresh_inventory_list(self):
        """Clears and rebuilds the inventory table view rows."""
        props_source = getattr(self.glob, 'custom_props_list', getattr(self, 'loaded_props', []))
        self.inventory_table.setRowCount(0)
        
        for index, prop in enumerate(props_source):
            self.inventory_table.insertRow(index)
            
            prop_name = getattr(prop, 'name', f"Asset_{index}")
            name_item = QTableWidgetItem(str(prop_name))
            self.inventory_table.setItem(index, 0, name_item)
            
            status_text = "Active in Scene" if getattr(prop, 'visible', True) else "Hidden"
            status_item = QTableWidgetItem(status_text)
            self.inventory_table.setItem(index, 1, status_item)
            
            action_item = QTableWidgetItem("Click to Focus")
            self.inventory_table.setItem(index, 2, action_item)

    def select_prop(self, current, previous):
        if not current: 
            return
        current_prop = self.propman.setCurrentProp(current.text())
        if current_prop:
            self.setValueFromProp(current_prop) 

    def leave(self):
        if hasattr(self, 'room_floor_mesh') and self.room_floor_mesh:
            self.room_floor_mesh.delete()

    def execute_room_resize_preview(self, new_width, new_length, handle_type="bottom_right"):
        """Calculates dynamic floor updates during active dragging frames."""
        w = max(1.0, float(new_width))
        l = max(1.0, float(new_length))
        
        delta_w = w - self.glob.last_cached_room_w
        delta_l = l - self.glob.last_cached_room_l
        
        self.glob.last_cached_room_w = w
        self.glob.last_cached_room_l = l
        
        if hasattr(self, 'room_floor_mesh') and self.room_floor_mesh:
            self.room_floor_mesh.build_square_mesh(w, l)
                
        if self.glob and getattr(self.glob, 'openGLWindow', None):
            self.glob.openGLWindow.update()

    def execute_room_resize_final(self, final_width, final_length, handle_type="bottom_right"):
        """Forces the 2D blueprint handles to scale your 3D floor primitive array dynamically."""
        w = max(1.0, min(100.0, float(final_width)))
        l = max(1.0, min(100.0, float(final_length)))
        
        self.glob.last_cached_room_w = w
        self.glob.last_cached_room_l = l
        
        if self.glob and getattr(self.glob, 'baseClass', None):
            bc = self.glob.baseClass
            if hasattr(bc, 'scene') and bc.scene:
                if hasattr(bc.scene, 'floorsize') and isinstance(bc.scene.floorsize, list):
                    bc.scene.floorsize[0] = w   
                    bc.scene.floorsize[2] = l   
                    bc.scene.floorsize[1] = 0.2 
                    
                if "floorcuboid" in bc.scene.prims:
                    prim = bc.scene.prims["floorcuboid"]
                    prim.newSize(bc.scene.floorsize)
                    if hasattr(prim, 'build'):
                        prim.build()
                        
                bc.scene.update()
                
        if self.glob and getattr(self.glob, 'openGLWindow', None):
            self.glob.openGLWindow.update()

    def sync_map_to_spinboxes(self, *args):
        if len(args) == 2:
            raw_x, raw_z = float(args[0]), float(args[1])
        else:
            raw_x = getattr(self.glob, 'last_cached_prop_x', 0.0)
            raw_z = getattr(self.glob, 'last_cached_prop_z', 0.0)

        max_floor_dimension = 10.0
        if self.glob and getattr(self.glob, 'baseClass', None):
            bc = self.glob.baseClass
            if hasattr(bc, 'scene') and bc.scene and hasattr(bc.scene, 'floorsize'):
                max_floor_dimension = float(bc.scene.floorsize[0])
                    
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

    def build_emitter_ui_context(self, parent_layout):
        """Creates the absolute layout structure for your particle systems"""
        # GroupBox container keeps the context grouped visually
        self.emitter_context_box = QtWidgets.QGroupBox("Editable Emitter Modifiers")
        ctx_layout = QtWidgets.QVBoxLayout()

        # Context Checkbox: Pure Ghost Controller Switch
        self.ghost_mode_cb = QtWidgets.QCheckBox("Hide Object Mesh (Pure Ghost)")
        self.ghost_mode_cb.toggled.connect(self.on_ghost_cb_clicked)
        ctx_layout.addWidget(self.ghost_mode_cb)

        # Context Slider: Particle Multiplier Limit
        ctx_layout.addWidget(QtWidgets.QLabel("Particle Array Limit:"))
        self.density_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.density_slider.setRange(20, 1000)
        self.density_slider.valueChanged.connect(self.on_density_slider_moved)
        ctx_layout.addWidget(self.density_slider)

        self.emitter_context_box.setLayout(ctx_layout)
        parent_layout.addWidget(self.emitter_context_box)
        
        # SENSE LOCK: Hide the context menu by default on boot up!
        self.emitter_context_box.setVisible(False)

    # =============================================================
    # UI Interactions: Changes state variables AND writes the data
    # =============================================================
    def on_ghost_cb_clicked(self, checked):
        if self.active_prop_object:
            is_visible = not checked
            self.active_prop_object.is_mesh_visible = is_visible
            
            # Rewrite raw property values back to your data folder json file
            save_prop_changes_to_json(self.active_prop_object.prop_id, {
                "is_mesh_visible": is_visible
            })

    def on_density_slider_moved(self, value):
        if self.active_prop_object:
            self.active_prop_object.max_particles = value
            
            # Overwrite the numeric field parameter inside your JSON file
            save_prop_changes_to_json(self.active_prop_object.prop_id, {
                "particle_count": value
            })

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

        from .propstate import PropStateMachine
        self.prop_fsm = PropStateMachine(panel_ref=self)

        from PySide6.QtCore import QTimer
        self.state_heartbeat_clock = QTimer(self)
        self.state_heartbeat_clock.timeout.connect(self.pump_state_machine_tick)
        self.state_heartbeat_clock.start(50)
        print("done")

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
        """Pumps continuous frame updates and links the 3D dropdown directly to the 2D map."""
        if self.glob is not None:
            bc = getattr(self.glob, 'baseClass', None)
            
            if bc and hasattr(bc, 'scene') and bc.scene and hasattr(bc.scene, 'floorsize'):
                master_w = float(bc.scene.floorsize[0])
                master_l = float(bc.scene.floorsize[2])
                
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

            if current_run_state in ["EQUIPPING", "USING"] and getattr(self.current_prop, 'use_parenting', False):
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
                        
                        if hasattr(bone_matrix, 'row'):
                            bone_world_pos = np.array([bone_matrix.row(0).w(), bone_matrix.row(1).w(), bone_matrix.row(2).w()], dtype=np.float64)
                        elif hasattr(bone_matrix, 'column'):
                            t_vec = bone_matrix.column(3)
                            bone_world_pos = np.array([t_vec.x(), t_vec.y(), t_vec.z()], dtype=np.float64)
                        else:
                            b_arr = np.asarray(bone_matrix).reshape(4, 4)
                            bone_world_pos = np.array(b_arr[:3, 3], dtype=np.float64)
                        
                        if not hasattr(self.current_prop, 'local_offset_pos') or np.all(self.current_prop.local_offset_pos == 0.0):
                            self.current_prop.local_offset_pos = np.array([0.0, 0.1, 0.0], dtype=np.float64)
                        
                        local_offset = self.current_prop.local_offset_pos
                        target_computed_pos = np.array(bone_world_pos) + np.array(local_offset)
                        
                        current_pos = getattr(self.current_prop, 'position', np.array([0.0, 0.0, 0.0]))
                        if np.linalg.norm(target_computed_pos - current_pos) > 0.001:
                            self.current_prop.position = target_computed_pos
                            self.update_prop()
            
            elif current_run_state == 'IDLE' and getattr(self, 'leftPanel', None) is not None:
                if hasattr(self.leftPanel, 'room_map_widget') and self.leftPanel.room_map_widget.is_dragging:
                    return
                    
                if hasattr(self.leftPanel, 'pos_x') and self.leftPanel.pos_x:
                    if getattr(self, 'is_updating_ui', False):
                        return
                    self.is_updating_ui = True
                    
                    try:
                        px = float(self.leftPanel.pos_x.value())
                        py = float(self.leftPanel.pos_y.value())
                        pz = float(self.leftPanel.pos_z.value())
                        
                        c_pos = getattr(self.current_prop, 'position', [0.0, 0.0, 0.0])
                        cx = float(c_pos[0]) if len(c_pos) > 0 else 0.0
                        cy = float(c_pos[1]) if len(c_pos) > 1 else 0.0
                        cz = float(c_pos[2]) if len(c_pos) > 2 else 0.0
                        
                        if abs(px - cx) > 0.001 or abs(py - cy) > 0.001 or abs(pz - cz) > 0.001:
                            target_list = [px, py, pz]
                            
                            if hasattr(self.current_prop, 'set_transform'):
                                self.current_prop.set_transform(pos=target_list)
                            else:
                                self.current_prop.position = target_list
                            
                            self.update_prop()
                    finally:
                        self.is_updating_ui = False

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

        search_directories = []
        target_dir = os.path.join(self.env.stdUserPath(), "props")
        search_directories.append(target_dir)
        
        local_plugin_data = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "props"))
        search_directories.append(local_plugin_data)
        
        """
        env = getattr(self.glob, 'env', None)
        
        target_dir = "f:/mh2_assets/makehuman2/data/props/"
        if not os.path.isdir(target_dir):
            target_dir = "makehuman2/data/props/"
        """

        sys_icon_dir = self.env.path_sysicon
        processed_obj_paths = set()

        for current_search_dir in search_directories:
            if os.path.isdir(current_search_dir):
                for filename in os.listdir(current_search_dir):
                    if filename.lower().endswith('.obj'):
                        base_name, _ = os.path.splitext(filename)
                        full_obj_path = os.path.normpath(os.path.join(current_search_dir, filename)).replace("\\", "/")
                        
                        if full_obj_path in processed_obj_paths:
                            continue
                        processed_obj_paths.add(full_obj_path)
                        
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

        if len(data) == 0:
            data = [["no props existent"]]

        return data


    def global_pipeline_refresh(self):
        self.refreshProps("props")
        self.sync_sidebar_list_display()
        self._trigger_viewport_redraw()

    def find_prop_by_name(self, prop_name):
        if not prop_name or not hasattr(self.glob, 'custom_props_list'):
            return None
        target_name = str(prop_name).lower().strip()
        for prop in self.glob.custom_props_list:
            if hasattr(prop, 'name') and prop.name:
                if prop.name.lower().strip() == target_name: 
                    return prop
        return None

    def add_prop_to_scene(self, asset):
        target_path = os.path.normpath(getattr(asset, 'path', getattr(asset, 'filename', str(asset))))
        pm = PropMesh(self.glob)
        res, err = pm.load(target_path)
        if res is False: 
            return False, err

        obj = pm.getObj()
        name = pm.getOriginalName().lower().strip()

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
                name = config_data.get("name", name).lower().strip()
                initial_pos = config_data.get("offset", initial_pos)
                initial_rot = config_data.get("rotation", initial_rot)
                initial_scale = config_data.get("scale", initial_scale)
                initial_vis = config_data.get("visible", initial_vis)
                parenting_block = config_data.get("parenting", {})
                use_parent = parenting_block.get("enabled", use_parent)
                target_bone = parenting_block.get("target_bone", target_bone)

        safe_pos = [float(p) for p in initial_pos] if isinstance(initial_pos, list) else [0.0, 0.0, 0.0]
        safe_rot = [float(r) for r in initial_rot] if isinstance(initial_rot, list) else [0.0, 0.0, 0.0]
        
        if isinstance(initial_scale, (list, np.ndarray, tuple)) and len(initial_scale) > 0:
            s_val = float(initial_scale[0])
        else:
            s_val = float(initial_scale) if initial_scale is not None else 1.0
            
        t_struct = {
            "translation": safe_pos, 
            "rotation": safe_rot, 
            "scale": [s_val, s_val, s_val]
        }

        existing_names = [getattr(p, 'name', '').lower() for p in getattr(self.glob, 'custom_props_list', [])]
        if name in existing_names:
            import time
            name = f"{name}_{int(time.time()) % 1000}"

        pipeline = getattr(self.glob, 'prop_manager_pipeline', None)
        if pipeline and hasattr(pipeline, 'registerProp'):
            pipeline.registerProp(name, obj, parent_bone=target_bone, relative_transform=t_struct)
            if name not in pipeline.active_props:
                pipeline.active_props[name] = {
                    "obj": obj, 
                    "parent_bone": target_bone, 
                    "transform": t_struct, 
                    "visible": initial_vis
                }

        new_prop = PropObject(name, self.glob)
        new_prop.mesh_reference = pm 
        new_prop.path = target_path.replace("\\", "/")
        new_prop.position = safe_pos
        new_prop.rotation = safe_rot
        new_prop.scale = [s_val, s_val, s_val]
        new_prop.visible = initial_vis
        new_prop.use_parenting = use_parent
        new_prop.parent_bone = target_bone

        print(dumper(new_prop))
        
        self.current_prop = new_prop
        self.glob.custom_props_list.append(new_prop)

        if self.leftPanel: 
            self.leftPanel.setValueFromProp(new_prop)
            
        self.global_pipeline_refresh()
        return True, ""

    def setLeftPanel(self, left):
        self.leftPanel = left

    def toggle_visibility(self, state):
        if self.current_prop: 
            self.current_prop.visible = (state != 0)

    def toggle_parenting(self, state):
        is_checked = (state == 2)
        self.bone_selector.setEnabled(is_checked)
        if self.current_prop:
            if not is_checked and hasattr(self, 'prop_fsm') and self.prop_fsm.current_state_name == "USING":
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
                sy = math.sqrt(R[0, 0] * R[0, 0] + R[1, 0] * R[1, 0])
                if sy > 1e-6:
                    rx = math.atan2(R[2, 1], R[2, 2])
                    ry = math.atan2(-R[2, 0], sy)
                    rz = math.atan2(R[1, 0], R[0, 0])
                else:
                    rx = math.atan2(-R[1, 2], R[1, 1])
                    ry = math.atan2(-R[2, 0], sy)
                    rz = 0
                rot = [math.degrees(rx), math.degrees(ry), math.degrees(rz)]
            except Exception:
                pass
        
        pipeline = getattr(self.glob, 'prop_manager_pipeline', None)
        if pipeline:
            pipeline.updatePropTransform(self.current_prop.name, translation=pos, rotation=rot, scale=scl)
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
        if isinstance(current, bool) or current is None:
            current = self.current_prop

        if current is None:
            return

        self.bone_selector.blockSignals(True)
        self.visibility_toggle.blockSignals(True)
        self.parent_toggle.blockSignals(True)
        if self.leftPanel:
            self.leftPanel.room_map_widget.blockSignals(True)
            if hasattr(self.leftPanel, 'room_boundary_map_widget'):
                self.leftPanel.room_boundary_map_widget.blockSignals(True)

        if hasattr(current, 'mesh_reference') and current.mesh_reference:
            current.mesh_reference.delete()

        target_name = current.name.lower().strip()
        
        pipeline = getattr(self.glob, 'prop_manager_pipeline', None)
        if pipeline and hasattr(pipeline, 'unregisterProp'):
            pipeline.unregisterProp(current.name)
            if hasattr(pipeline, 'active_props') and current.name in pipeline.active_props:
                del pipeline.active_props[current.name]

        custom_pool = self.glob.custom_props_list
        for i in range(len(custom_pool) - 1, -1, -1):
            if getattr(custom_pool[i], 'name', '').lower().strip() == target_name: 
                custom_pool.pop(i)

        self.current_prop = None
        if self.leftPanel is not None: 
            self.leftPanel.resetValues()
            
        self.visibility_toggle.setChecked(True)
        self.parent_toggle.setChecked(False)
        self.bone_selector.setEnabled(False)
        self.bone_selector.setCurrentIndex(0)

        self.sync_sidebar_list_display()
        self.refreshProps("props")

        self.visibility_toggle.blockSignals(False)
        self.bone_selector.blockSignals(False)
        self.parent_toggle.blockSignals(False)
        if self.leftPanel:
            self.leftPanel.room_map_widget.blockSignals(False)
            if hasattr(self.leftPanel, 'room_boundary_map_widget'):
                self.leftPanel.room_boundary_map_widget.blockSignals(False)
                
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
                        prop.position = np.array([0.0, 0.0, 0.0], dtype=np.float64)

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
        cv = getattr(self.glob, "openGLWindow", None)
        if not cv and hasattr(self.parent, 'graph') and self.parent.graph:
            cv = getattr(self.parent.graph, 'view', None)
        if not cv and hasattr(self.parent, 'glWindow'):
            cv = self.parent.glWindow
            
        if cv:
            from PySide6.QtCore import QTimer
            def safe_asynchronous_paint_flush():
                try:
                    if hasattr(cv, "update"): 
                        cv.update()
                    elif hasattr(cv, "repaint"): 
                        cv.repaint()
                    elif hasattr(cv, "updateGL"): 
                        cv.updateGL()
                        
                    if self.view and hasattr(self.view, 'Tweak'):
                        self.view.Tweak()
                    elif getattr(self.glob, 'openGLWindow', None) and hasattr(self.glob.openGLWindow, 'Tweak'):
                        self.glob.openGLWindow.Tweak()
                except Exception as thread_err:
                    print(f"[Prop Studio Debug] Thread-safe redraw loop skipped: {thread_err}")

            QTimer.singleShot(0, safe_asynchronous_paint_flush)

    def save_prop_data(self):
        import json
        active_prop = getattr(self, "current_prop", None)
        if not active_prop or not getattr(active_prop, "path", None):
            print("[Prop Studio Error] Cannot save configurations: No active prop asset selected.")
            return False

        target_obj_path = os.path.normpath(active_prop.path)
        destination_json_path = target_obj_path.replace(".obj", ".json")

        try:
            pos = getattr(active_prop, 'position', [0.0, 0.0, 0.0])
            rot = getattr(active_prop, 'rotation', [0.0, 0.0, 0.0])
            scl = getattr(active_prop, 'scale', [1.0, 1.0, 1.0])
            
            pos_list = [float(p) for p in pos] if hasattr(pos, '__len__') else [0.0, 0.0, 0.0]
            rot_list = [float(r) for r in rot] if hasattr(rot, '__len__') else [0.0, 0.0, 0.0]
            scl_list = [float(s) for s in scl] if hasattr(scl, '__len__') else [1.0, 1.0, 1.0]

            json_structure = {
                "name": str(getattr(active_prop, "name", "NewProp")),
                "offset": pos_list,
                "rotation": rot_list,
                "scale": scl_list,
                "visible": bool(getattr(active_prop, "visible", True)),
                "parenting": {
                    "enabled": bool(getattr(active_prop, "use_parenting", False)),
                    "target_bone": str(getattr(active_prop, "parent_bone", "None"))
                }
            }

            with open(destination_json_path, 'w', encoding='utf-8') as json_file:
                json.dump(json_structure, json_file, indent=4)
                
            print(f"[Prop Studio Core] Successfully exported layout asset presets file to: {destination_json_path}")
            return True

        except Exception as export_fault_err:
            print(f"[Prop Studio Error] System asset serialization pipeline failed: {export_fault_err}")
            return False

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
                current_pos = list(getattr(self.current_prop, 'position', [0.0, 0.0, 0.0]))
                self.current_prop.position = [
                    current_pos[0] + float(b_coord.x()),
                    current_pos[1] + float(b_coord.y()),
                    current_pos[2] + float(b_coord.z())
                ]
                if self.leftPanel:
                    self.leftPanel.setValueFromProp(self.current_prop)
                self._trigger_viewport_redraw()

class CoreMH2PropPanel(QtWidgets.QWidget):
    def __init__(self, parent_layout):
        super().__init__()
        self.active_prop_object = None
        self.manifest_data = load_props_manifest()
        
        self.inject_ui_into_panel(parent_layout)

    def inject_ui_into_panel(self, layout):
        """Builds controls directly inline with your current Prop Panel setup"""
        self.emitter_box = QtWidgets.QGroupBox("Live Emitter Configurations (JSON Connected)")
        v_layout = QtWidgets.QVBoxLayout()

        # Checkbox 1: Toggle Object Mesh Visibility (Ghost Mode Selector)
        self.hide_mesh_cb = QtWidgets.QCheckBox("Hide Object Mesh (Pure Ghost Emitter)")
        self.hide_mesh_cb.toggled.connect(self.on_visibility_toggled)
        v_layout.addWidget(self.hide_mesh_cb)

        # Slider 1: Dynamic Max Particle Adjuster
        v_layout.addWidget(QtWidgets.QLabel("Max Particles Density:"))
        self.count_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.count_slider.setRange(50, 1000)
        self.count_slider.valueChanged.connect(self.on_density_slider_changed)
        v_layout.addWidget(self.count_slider)

        self.emitter_box.setLayout(v_layout)
        layout.addWidget(self.emitter_box)
        
        # Hide editing options until an asset marked as EMITTER gets selected
        self.emitter_box.setVisible(False)

    def select_prop_by_id(self, prop_id):
        """Triggered when choosing items inside your object asset selector list"""
        prop_config = self.manifest_data.get(prop_id)
        
        if prop_config and prop_config["type"] == "EMITTER":
            # Initialize live emitter object tracking logic
            self.active_prop_object = MH2LiveEmitterProp(prop_id, prop_config)
            
            # Map existing file configurations out of JSON straight to UI handles
            self.hide_mesh_cb.setChecked(not prop_config["is_mesh_visible"])
            self.count_slider.setValue(prop_config["particle_count"])
            
            self.emitter_box.setVisible(True)
        else:
            self.emitter_box.setVisible(False)

    # Real-Time UI Editing Callbacks that Rewrite the JSON on the fly
    def on_visibility_toggled(self, checked):
        if self.active_prop_object:
            # Update memory representation variable
            self.active_prop_object.is_mesh_visible = not checked
            
            # Commit the property value edit directly back to your resource JSON file
            update_prop_json_entry(self.active_prop_object.prop_id, {
                "is_mesh_visible": not checked
            })

    def on_density_slider_changed(self, value):
        if self.active_prop_object:
            self.active_prop_object.max_particles = value
            
            # Commit the changed slider limit calculation to disk configuration
            update_prop_json_entry(self.active_prop_object.prop_id, {
                "particle_count": value
            })
