"""
Prop Module v2.0 (Unified Master Edition).
Part of the MakeHuman 2 Project contributed by Elvaerwyn_MH2 2026.
"""

import numpy as np
import sys
import os

from PySide6.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QScrollArea, 
                             QListWidget, QListWidgetItem, QDoubleSpinBox, QFormLayout, 
                             QComboBox, QCheckBox, QPushButton, QLabel, QApplication,
                             QMainWindow, QTabWidget, QTableWidget, QHeaderView,
                             QDockWidget, QSplitter) 

from PySide6.QtCore import Qt, QSize, QTimer
from PySide6.QtGui import QVector3D, QVector4D, QIcon, QPixmap

from gui.common import MHGroupBox, ErrorBox, HintBox
from obj3d.object3d import object3d
from opengl.buffers import OpenGlBuffers, RenderedObject
from OpenGL import GL as gl

from .viewport_hook import perform_background_hardware_link
from .propstate import PropStateMachine
from .roommap import MHRoomLayoutMap
from core.debug import dumper

_current_dir = os.path.dirname(os.path.abspath(__file__))
_plugin_root = os.path.abspath(os.path.join(_current_dir, ".."))

if _plugin_root not in sys.path:
    sys.path.insert(0, _plugin_root)

from ..opengl.prop_manager import MultiPropManager
import random
import time

class MH2PropParticle:
    """A single particle dot spawned by an emitter prop."""
    def __init__(self, origin_pos, color=None):
        self.x = float(origin_pos[0])
        self.y = float(origin_pos[1])
        self.z = float(origin_pos[2])
        self.vx = random.uniform(-0.3, 0.3)
        self.vy = random.uniform(1.2, 2.5) 
        self.vz = random.uniform(-0.3, 0.3)
        
        # Safely extracts color properties from color, color_rgba, or particle_color
        raw_color = color
        if hasattr(color, 'color_rgba'):
            raw_color = color.color_rgba
        elif hasattr(color, 'particle_color'):
            raw_color = color.particle_color
            
        if isinstance(raw_color, (list, tuple)) and len(raw_color) >= 3:
            self.color = [float(c) for c in raw_color[:4]]
            if len(self.color) == 3:
                self.color.append(1.0) # Automatically inject fully opaque alpha target
        else:
            self.color = [1.0, 0.4, 0.0, 1.0] # Fire Magic Torch vibrant orange fallback
            
        self.birth_time = time.time()
        self.lifespan = random.uniform(0.6, 1.5)

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

class PropObject():
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

        self.type = "STATIC"            # Standard lookup fallback
        self.object_type = "STATIC"     # Matches list panel strings
        self.is_emitting = False        # Links directly to emission checkmark
        self.is_mesh_visible = True     # Links directly to ghost mode checkmark
        self.max_particles = 300
        self.particles = []             # Clean memory array loop holder

        self.position = np.array([0.0, 0.0, 0.0], dtype=np.float64)
        self.rotation = np.array([0.0, 0.0, 0.0], dtype=np.float64) 
        self.scale = np.array([1.0, 1.0, 1.0], dtype=np.float64)

    def set_transform(self, pos=None, rot=None, scl=None):
        """Sets raw 3D transformations and completely shatters the invisible culling cage."""
        if pos is not None: 
            self.position = np.array(pos, dtype=float)
            
            if hasattr(self, 'mesh_reference') and self.mesh_reference:
                # Track down into the object3d proxy where real spatial nodes reside
                mesh_container = getattr(self.mesh_reference, 'obj', None)
                if mesh_container and hasattr(mesh_container, 'bounds') and mesh_container.bounds:
                    mesh_container.bounds.min_x, mesh_container.bounds.max_x = -50.0, 50.0
                    mesh_container.bounds.min_y, mesh_container.bounds.max_y = -5.0,  50.0 
                    mesh_container.bounds.min_z, mesh_container.bounds.max_z = -50.0, 50.0

        if rot is not None: self.rotation = np.array(rot, dtype=float)
        if scl is not None: self.scale = np.array(scl, dtype=float)

    def set_visibility(self, vis):
        self.visible = vis
        self.is_mesh_visible = vis

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

class PropManLeftPanel(QWidget):
    def __init__(self, parent):
        super().__init__()
        self.glob = parent.glob
        self.env = self.glob.env
        self.parent_frame = parent 
        
        self.propman = getattr(parent, 'prop_manager', None)
        self.prop_update = self.propman.syncedFromLeft if self.propman else None
        
        if self.propman:
            self.propman.setLeftPanel(self)

        panel_outer_layout = QVBoxLayout(self)
        panel_outer_layout.setContentsMargins(0, 0, 0, 0)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        panel_outer_layout.addWidget(scroll_area)

        scroll_content_host = QWidget()
        scroll_area.setWidget(scroll_content_host)

        master_panel_flow = QVBoxLayout(scroll_content_host)
        master_panel_flow.setContentsMargins(6, 6, 6, 6)
        master_panel_flow.setSpacing(6)

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
        master_panel_flow.addWidget(self.controls_group)

        self.emitter_context_group = MHGroupBox("Dynamic Emitter Modifiers")
        context_layout = QVBoxLayout()

        self.ghost_mode_cb = QCheckBox("Hide Prop Mesh (Pure Ghost Emitter Only)")
        self.ghost_mode_cb.toggled.connect(self.on_ghost_toggled)
        context_layout.addWidget(self.ghost_mode_cb)


        self.active_emit_cb = QCheckBox("Enable Active Particle Emission Loop")
        self.active_emit_cb.setChecked(True)
        context_layout.addWidget(self.active_emit_cb)

        self.emitter_context_group.setLayout(context_layout)
        master_panel_flow.addWidget(self.emitter_context_group)
        
        self.emitter_context_group.setVisible(True) 

        self.inventory_table = QTableWidget()
        self.inventory_table.setColumnCount(3)
        self.inventory_table.setHorizontalHeaderLabels(["Name", "Status", "Action"])
        header = self.inventory_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        master_panel_flow.addWidget(self.inventory_table)

        cached_x = getattr(self.glob, 'last_cached_prop_x', 0.0)
        cached_z = getattr(self.glob, 'last_cached_prop_z', 0.0)
        cached_w = getattr(self.glob, 'last_cached_room_w', 8.0)
        cached_l = getattr(self.glob, 'last_cached_room_l', 8.0)

        master_panel_flow.addWidget(QLabel("<b>2D Room Layout Coordinate Grid:</b>"))
        self.room_map_widget = MHRoomLayoutMap(parent=parent) 
        self.room_map_widget.glob = self.glob
        self.room_map_widget.parent_obj = self.propman
        self.room_map_widget.setMinimumSize(QSize(340, 340))
        self.room_map_widget.setMaximumSize(QSize(340, 340))
        self.room_map_widget.set_prop_coordinates(cached_x, cached_z)
        self.room_map_widget.coordinatesChanged.connect(self.sync_map_to_spinboxes)
        
        map_centering_box = QHBoxLayout()
        map_centering_box.addWidget(self.room_map_widget)
        master_panel_flow.addLayout(map_centering_box)

        self.prop_list = QListWidget()
        self.prop_list.setViewMode(QListWidget.ListMode)
        self.prop_list.setMinimumHeight(120)  # Safe size target for list rows
        self.prop_list.currentItemChanged.connect(self.select_prop)
        master_panel_flow.addWidget(self.prop_list)

        if hasattr(parent, 'equipment') and "props" in parent.equipment:
            img_sel = parent.equipment["props"].get("func", None)
            if img_sel:
                master_panel_flow.addWidget(QLabel("<b>Selected Asset Specification Profile:</b>"))
                from gui.imageselector import InformationBox
                
                self.left_infobox_layout = QVBoxLayout()
                self.left_prop_infobox = InformationBox(self.left_infobox_layout)
                master_panel_flow.addLayout(self.left_infobox_layout)
                img_sel.infobox = self.left_prop_infobox

        master_panel_flow.addWidget(QLabel("<b>2D Room Boundary Planner Map:</b>"))
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
        master_panel_flow.addLayout(boundary_centering_box)

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

        self.emitter_context_group = MHGroupBox("Dynamic Emitter Modifiers")
        context_layout = QVBoxLayout()

        self.ghost_mode_cb = QCheckBox("Hide Prop Mesh (Pure Ghost Emitter Only)")
        self.ghost_mode_cb.toggled.connect(self.on_ghost_toggled)
        context_layout.addWidget(self.ghost_mode_cb)

        self.active_emit_cb = QCheckBox("Enable Active Particle Emission Loop")
        self.active_emit_cb.setChecked(True)

        self.active_emit_cb.toggled.connect(self.on_emission_loop_toggled)
        context_layout.addWidget(self.active_emit_cb)

        self.emitter_context_group.setLayout(context_layout)
        master_panel_flow.addWidget(self.emitter_context_group)
        
        self.emitter_context_group.setVisible(True)

        self.inventory_table = QTableWidget()
        self.inventory_table.setColumnCount(3)
        self.inventory_table.setHorizontalHeaderLabels(["Name", "Status", "Action"])
        header = self.inventory_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

        self.inventory_table.itemDoubleClicked.connect(self.on_inventory_row_clicked)
        master_panel_flow.addWidget(self.inventory_table)

        self.prop_list = QListWidget()
        self.prop_list.setViewMode(QListWidget.ListMode)
        self.prop_list.setMinimumHeight(120)  
        self.prop_list.currentItemChanged.connect(self.select_prop)
        master_panel_flow.addWidget(self.prop_list)

        QTimer.singleShot(10, self.refresh_inventory_list)

        master_panel_flow.addStretch(1)

    def select_prop(self, current, previous):
        """Monitors item row selections inside the layout table to toggle control panels on the fly."""
        if not current or not self.propman:
            self.emitter_context_group.setVisible(False)
            return

        # 1. Extract raw string data from the active list widget row item
        raw_text = current.text()
        print(f"[Prop Studio UI Check] Selected row entry text target string: '{raw_text}'")

        # 2. Extract the unformatted prop ID out of the raw string prefix labels safely
        if "| State:" in raw_text:
            left_segment = raw_text.split("|")[0]
            prop_id = left_segment.replace("[O]", "").strip()
        else:
            prop_id = raw_text.strip()

        print(f"[Prop Studio UI Check] Cleaned lookup ID key string: '{prop_id}'")

        # 3. Pull the active live model mesh instance from the plugin prop manager structures
        current_prop = self.propman.setCurrentProp(prop_id)
        if current_prop: 
            self.setValueFromProp(current_prop)

        # Update our focus tracker parameter across global dock widget attributes
        global _standalone_studio_dock_instance
        if _standalone_studio_dock_instance:
            _standalone_studio_dock_instance.setProperty("active_prop_id", prop_id)

        if hasattr(current_prop, 'object_type') and current_prop.object_type == "EMITTER":
            
            # Map saved parameters straight onto the checkboxes while cutting signal loops
            self.ghost_mode_cb.blockSignals(True)
            self.ghost_mode_cb.setChecked(not getattr(current_prop, 'is_mesh_visible', True))
            self.ghost_mode_cb.blockSignals(False)

            self.active_emit_cb.blockSignals(True)
            self.active_emit_cb.setChecked(getattr(current_prop, 'is_emitting', True))
            self.active_emit_cb.blockSignals(False)
            
            self.emitter_context_group.setVisible(True)
            print(f"[Prop Studio UI] UI intersection check passed. Displaying emitter tools group widget.")
        else:
            self.emitter_context_group.setVisible(False)

        if hasattr(self.glob, 'openGLWindow') and self.glob.openGLWindow:
            self.glob.openGLWindow.update()

    def refresh_inventory_list(self):
        """Clears and rebuilds the inventory table view rows cleanly using true manifest dictionaries."""
        try:

            from PySide6.QtWidgets import QTableWidgetItem
            from mh2_official_tools.prop_panel.core.json_manager import load_props_manifest
            props_manifest = load_props_manifest()
            
            self.inventory_table.setRowCount(0)
            
            for index, (prop_id, prop_info) in enumerate(props_manifest.items()):
                self.inventory_table.insertRow(index)
                
                # Column 1: Extract display name safely ("Fire Magic Torch")
                prop_name = prop_info.get("name", str(prop_id))
                name_item = QTableWidgetItem(str(prop_name))
                name_item.setData(Qt.UserRole, prop_id)
                self.inventory_table.setItem(index, 0, name_item)
                
                # Column 2: Status Column Text String showing active asset type tokens
                obj_type = str(prop_info.get("type", "STATIC")).upper()
                status_text = "🔥 FX EMITTER" if obj_type == "EMITTER" else "📦 SOLID MESH"
                status_item = QTableWidgetItem(status_text)
                self.inventory_table.setItem(index, 1, status_item)
                
                # Column 3: Action Trigger Guidelines
                action_item = QTableWidgetItem("Double-click row to equip")
                self.inventory_table.setItem(index, 2, action_item)
                
            print(f"[Prop Studio UI] Catalog initialized cleanly. Successfully loaded {len(props_manifest)} manifest tracks.")
        except Exception as err:
            print(f"[Prop Studio UI Error] Inventory listing loops collapsed on string assignments: {str(err)}")

    def on_inventory_row_clicked(self, item):
        """Redirects table row clicks directly to the active spawner pass."""
        if item and hasattr(self, 'deploy_scene_asset'):
            # Pulls the background ID key from the row memory
            true_id = item.data(Qt.UserRole)
            if not true_id:
                true_id = item.text().strip()
            self.deploy_scene_asset(true_id)

    def deploy_scene_asset(self, prop_id_key):
        """Loads items dynamically by matching manifest parameters directly to disk files."""
        from mh2_official_tools.prop_panel.core.json_manager import load_props_manifest
        manifest = load_props_manifest()
        
        asset_profile = manifest.get(prop_id_key, {})
        
        prop_name = asset_profile.get("name", str(prop_id_key))
        prop_type = asset_profile.get("type", "STATIC")
        raw_mesh_path = asset_profile.get("mesh_path", "data/props/ball.obj")
        
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        full_obj_path = os.path.normpath(os.path.join(base_dir, raw_mesh_path)).replace("\\", "/")

        print(f"[Prop Studio Core] Deploying scene initialization for manifest key: {prop_id_key}")
        
        class MHStudioLivePropObject:
            def __init__(self):

                self.prop_id = str(prop_id_key) 
                self.name = prop_name           
                self.type = prop_type
                self.object_type = prop_type
                self.path = full_obj_path
                self.material_path = ""
                self.position = [0.0, 0.814, 0.0] 
                self.rotation = [0.0, 0.0, 0.0]
                self.scale = [1.0, 1.0, 1.0]
                self.use_parenting = True if prop_type == "EMITTER" else False
                self.parent_bone = asset_profile.get("default_bone", "hand_R") if prop_type == "EMITTER" else "None"
                self.visible = True
                self.is_mesh_visible = asset_profile.get("is_mesh_visible", True)
                self.is_emitting = asset_profile.get("is_emitting", True)
                self.max_particles = asset_profile.get("particle_count", 300)
                self.particle_color = asset_profile.get("color_rgba", [1.0, 0.5, 0.0, 1.0])
                self.mesh_reference = None

        new_studio_asset = MHStudioLivePropObject()

        viewport_view = getattr(self.glob, 'openGLWindow', None)
        if viewport_view and hasattr(viewport_view, 'loadObjMesh'):
            new_studio_asset.mesh_reference = viewport_view.loadObjMesh(full_obj_path)
        elif hasattr(self, 'propman') and hasattr(self.propman, 'compile_mesh'):
            new_studio_asset.mesh_reference = self.propman.compile_mesh(full_obj_path)

        if not hasattr(self.glob, 'custom_props_list'):
            self.glob.custom_props_list = []
        self.glob.custom_props_list.append(new_studio_asset)
        
        print(f"[Prop Studio Core] Successfully loaded and registered manifest entry: '{prop_name}' ({prop_type})")
        
        if hasattr(self.glob, 'openGLWindow') and self.glob.openGLWindow:
            self.glob.openGLWindow.Tweak()
            if hasattr(self.glob.openGLWindow, 'update'):
                self.glob.openGLWindow.update()

    def on_ghost_toggled(self, checked):
        """Fires when clicking the ghost checkbox to update manifest states."""
        global _standalone_studio_dock_instance
        if not _standalone_studio_dock_instance:
            return

        active_id = _standalone_studio_dock_instance.property("active_prop_id")
        loaded_manifest = _standalone_studio_dock_instance.property("manifest_data") or {}

        if active_id and active_id in loaded_manifest:
            is_visible = not checked
            loaded_manifest[active_id]["is_mesh_visible"] = is_visible
            
            custom_pool = getattr(self.glob, 'custom_props_list', [])
            for prop in custom_pool:
                target_id = getattr(prop, 'prop_id', getattr(prop, 'name', ''))
                if str(target_id).lower() == str(active_id).lower():
                    prop.is_mesh_visible = is_visible
                    prop.visible = is_visible

            from mh2_official_tools.prop_panel.core.json_manager import update_prop_json_entry
            update_prop_json_entry(active_id, {"is_mesh_visible": is_visible})
            print(f"[Prop Studio Context] Ghost option updated and saved for item: {active_id}")

            if hasattr(self.glob, 'openGLWindow') and self.glob.openGLWindow:
                self.glob.openGLWindow.Tweak()
                if hasattr(self.glob.openGLWindow, 'update'):
                    self.glob.openGLWindow.update()

    def on_emission_loop_toggled(self, checked):
        """Fires when clicking the emission checkbox to flip asset types in real-time."""
        global _standalone_studio_dock_instance
        if not _standalone_studio_dock_instance:
            return

        active_id = _standalone_studio_dock_instance.property("active_prop_id")
        loaded_manifest = _standalone_studio_dock_instance.property("manifest_data") or {}

        if active_id and active_id in loaded_manifest:
            loaded_manifest[active_id]["is_emitting"] = checked
            target_type = "EMITTER" if checked else "STATIC"
            loaded_manifest[active_id]["type"] = target_type
            
            custom_pool = getattr(self.glob, 'custom_props_list', [])
            for prop in custom_pool:
                target_id = getattr(prop, 'prop_id', getattr(prop, 'name', ''))
                if str(target_id).lower() == str(active_id).lower():
                    prop.type = target_type
                    prop.object_type = target_type
                    prop.is_emitting = checked

            from mh2_official_tools.prop_panel.core.json_manager import update_prop_json_entry
            update_prop_json_entry(active_id, {"is_emitting": checked, "type": target_type})
            print(f"[Prop Studio Context] Emission loop updated and saved for item: {active_id}")
            
            if hasattr(self.glob, 'openGLWindow') and self.glob.openGLWindow:
                self.glob.openGLWindow.Tweak()
                if hasattr(self.glob.openGLWindow, 'update'):
                    self.glob.openGLWindow.update()

    def bind_emitter_ui_signals(self):
        """Helper to establish clean signal connection tracks safely using self properties."""
        if hasattr(self, 'ghost_mode_cb') and self.ghost_mode_cb:
            try: self.ghost_mode_cb.toggled.disconnect()
            except Exception: pass
            
            # Maps to the exact name target defined 
            self.ghost_mode_cb.toggled.connect(self.on_ghost_toggled)

        if hasattr(self, 'active_emit_cb') and self.active_emit_cb:
            try: self.active_emit_cb.toggled.disconnect()
            except Exception: pass
            self.active_emit_cb.toggled.connect(self.on_emission_loop_toggled)

    def select_prop(self, current, previous):
        """Selects the asset via the prop manager and checks for emitter characteristics."""
        if not current or not self.propman: 
            self.emitter_context_group.setVisible(False)
            return

        current_prop = self.propman.setCurrentProp(current.text())
        if current_prop: 
            self.setValueFromProp(current_prop)

        prop_id = current.text()
        global _standalone_studio_dock_instance
        loaded_manifest = {}
        if _standalone_studio_dock_instance:
            loaded_manifest = _standalone_studio_dock_instance.property("manifest_data") or {}

        asset_profile = loaded_manifest.get(prop_id, {})
        obj_type = str(asset_profile.get("type", "STATIC")).upper()

        if obj_type == "EMITTER":
            if _standalone_studio_dock_instance:
                _standalone_studio_dock_instance.setProperty("active_prop_id", prop_id)
            
            self.ghost_mode_cb.blockSignals(True)
            self.active_emit_cb.blockSignals(True)
            
            self.ghost_mode_cb.setChecked(not asset_profile.get("is_mesh_visible", True))
            self.active_emit_cb.setChecked(asset_profile.get("is_emitting", True))
            
            self.ghost_mode_cb.blockSignals(False)
            self.active_emit_cb.blockSignals(False)
            
            self.emitter_context_group.setVisible(True)
        else:
            self.emitter_context_group.setVisible(False)

    def leave(self):
        if hasattr(self, 'room_floor_mesh') and self.room_floor_mesh: 
            self.room_floor_mesh.delete()

    def execute_room_resize_preview(self, new_width, new_length, handle_type="bottom_right"):
        w, l = max(1.0, float(new_width)), max(1.0, float(new_length))
        self.glob.last_cached_room_w, self.glob.last_cached_room_l = w, l
        if hasattr(self, 'room_floor_mesh') and self.room_floor_mesh: 
            self.room_floor_mesh.build_square_mesh(w, l)
        if self.glob and getattr(self.glob, 'openGLWindow', None): 
            self.glob.openGLWindow.update()

    def execute_room_resize_final(self, final_width, final_length, handle_type="bottom_right"):
        w, l = max(1.0, min(100.0, float(final_width))), max(1.0, min(100.0, float(final_length)))
        self.glob.last_cached_room_w, self.glob.last_cached_room_l = w, l
        if self.glob and getattr(self.glob, 'baseClass', None):
            bc = self.glob.baseClass
            if hasattr(bc, 'scene') and bc.scene:
                if hasattr(bc.scene, 'floorsize') and isinstance(bc.scene.floorsize, list):
                    bc.scene.floorsize[0] = w   
                    bc.scene.floorsize[1] = l   
                    bc.scene.floorsize[2] = 0.2 
                elif hasattr(bc.scene, 'floorsize') and isinstance(bc.scene.floorsize, np.ndarray):
                    bc.scene.floorsize[0] = w
                    bc.scene.floorsize[1] = l
                    bc.scene.floorsize[2] = 0.2
                    
                if "floorcuboid" in bc.scene.prims:
                    prim = bc.scene.prims["floorcuboid"]
                    prim.newSize(bc.scene.floorsize)
                    if hasattr(prim, 'build'): 
                        prim.build()
                bc.scene.update()
        if hasattr(self, 'prop_update') and self.prop_update: 
            self.prop_update()
        if self.glob and getattr(self.glob, 'openGLWindow', None): 
            self.glob.openGLWindow.update()

    def sync_map_to_spinboxes(self, *args):
        if len(args) == 2: 
            raw_x, raw_z = float(args[0]), float(args[1])
        elif len(args) == 1 and isinstance(args[0], (list, tuple, np.ndarray)) and len(args[0]) >= 2:
            raw_x, raw_z = float(args[0][0]), float(args[0][1])
        else: 
            raw_x = float(getattr(self.glob, 'last_cached_prop_x', 0.0))
            raw_z = float(getattr(self.glob, 'last_cached_prop_z', 0.0))
            
        max_floor_dimension = float(getattr(self.glob, 'last_cached_room_w', 10.0))
        half_floor = max_floor_dimension / 2.0
        raw_x, raw_z = max(-half_floor, min(half_floor, raw_x)), max(-half_floor, min(half_floor, raw_z))
        self.glob.last_cached_prop_x, self.glob.last_cached_prop_z = raw_x, raw_z
        
        widgets = [self.pos_x, self.pos_y, self.pos_z, self.room_map_widget, getattr(self, 'room_boundary_map_widget', None)]
        for w in widgets:
            if w: 
                w.blockSignals(True)
        self.pos_x.setValue(raw_x)
        self.pos_z.setValue(raw_z)
        self.room_map_widget.set_prop_coordinates(raw_x, raw_z)
        if hasattr(self, 'room_boundary_map_widget') and self.room_boundary_map_widget: 
            self.room_boundary_map_widget.set_prop_coordinates(raw_x, raw_z)
        for w in widgets:
            if w: 
                w.blockSignals(False)
            
        if self.prop_update:
            unique_scale = [self.scl_x.value(), self.scl_y.value(), self.scl_z.value()]
            new_rot = [self.rot_x.value(), self.rot_y.value(), self.rot_z.value()]
            self.prop_update([raw_x, self.pos_y.value(), raw_z], new_rot, unique_scale)

        if self.glob and getattr(self.glob, 'openGLWindow', None):
            self.glob.openGLWindow.update()

    def syncToObject(self):
        """Pushes values from the UI spinboxes back to the active prop and maps."""
        new_pos = [self.pos_x.value(), self.pos_y.value(), self.pos_z.value()]
        new_rot = [self.rot_x.value(), self.rot_y.value(), self.rot_z.value()]
        unique_scale = [max(0.001, abs(self.scl_x.value())), max(0.001, abs(self.scl_y.value())), max(0.001, abs(self.scl_z.value()))]
        
        widgets = [self.room_map_widget, getattr(self, 'room_boundary_map_widget', None)]
        for w in widgets:
            if w:
                w.blockSignals(True)
                w.set_prop_coordinates(new_pos[0], new_pos[2])
                w.blockSignals(False)
        if self.prop_update: 
            self.prop_update(new_pos, new_rot, unique_scale)

        if self.glob and getattr(self.glob, 'openGLWindow', None):
            self.glob.openGLWindow.update()

    def resetValues(self):
        widgets = [self.pos_x, self.pos_y, self.pos_z, self.rot_x, self.rot_y, self.rot_z, self.scl_all, self.scl_x, self.scl_y, self.scl_z]
        for w in widgets: 
            w.blockSignals(True)
        for w in widgets[:6]: 
            w.setValue(0.0)
        for w in widgets[6:]: 
            w.setValue(1.0)
        for w in widgets: 
            w.blockSignals(False)
        self.room_map_widget.set_prop_coordinates(0.0, 0.0)
        if hasattr(self, 'room_boundary_map_widget') and self.room_boundary_map_widget: 
            self.room_boundary_map_widget.set_prop_coordinates(0.0, 0.0)

    def setValueFromProp(self, prop):
        if not prop: 
            return
        
        p_pos = getattr(prop, 'position', [0.0, 0.0, 0.0])
        if hasattr(p_pos, '__len__') and len(p_pos) >= 3:
            px, py, pz = float(p_pos[0]), float(p_pos[1]), float(p_pos[2])
        else:
            px = py = pz = float(p_pos) if p_pos is not None else 0.0

        widgets = [self.pos_x, self.pos_y, self.pos_z, self.rot_x, self.rot_y, self.rot_z, self.scl_all, self.scl_x, self.scl_y, self.scl_z]
        for w in widgets: 
            w.blockSignals(True)
        
        self.pos_x.setValue(px)
        self.pos_y.setValue(py)
        self.pos_z.setValue(pz)
        
        p_rot = getattr(prop, 'rotation', [0.0, 0.0, 0.0])
        if hasattr(p_rot, '__len__') and len(p_rot) >= 3:
            rx, ry, rz = float(p_rot[0]), float(p_rot[1]), float(p_rot[2])
        else:
            rx = ry = rz = float(p_rot) if p_rot is not None else 0.0
            
        self.rot_x.setValue(rx)
        self.rot_y.setValue(ry)
        self.rot_z.setValue(rz)
        
        saved_scale = getattr(prop, 'scale', [1.0, 1.0, 1.0])
        if hasattr(saved_scale, '__len__') and len(saved_scale) >= 3:
            sx, sy, sz = float(saved_scale[0]), float(saved_scale[1]), float(saved_scale[2])
        else:
            sx = sy = sz = float(saved_scale) if saved_scale is not None else 1.0

        # Average the custom vectors to show an accurate average visual scale value
        avg_scale = (sx + sy + sz) / 3.0
        self.scl_all.setValue(avg_scale)
        
        self.scl_x.setValue(sx)
        self.scl_y.setValue(sy)
        self.scl_z.setValue(sz)

        for w in widgets: 
            w.blockSignals(False)
            
        self.room_map_widget.set_prop_coordinates(px, pz)
        if hasattr(self, 'room_boundary_map_widget') and self.room_boundary_map_widget: 
            self.room_boundary_map_widget.set_prop_coordinates(px, pz)

    def sync_uniform_scale(self, value):
        """Maintains clean uniform size locks across XYZ axes sliders."""
        for w in [self.scl_x, self.scl_y, self.scl_z]:
            w.blockSignals(True)
            w.setValue(float(value))
            w.blockSignals(False)
        self.syncToObject()

    def _make_spinbox(self, is_rotation=False, is_scale=False):
        """Internal helper factory stamps out standardized PySide spinbox fields."""
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
        
        sb.setMinimumWidth(80)
        sb.setMaximumWidth(140)
        return sb

class PropManagerPanel(MHGroupBox):
    """The central manager panel containing FSM states, toggles, and deletion loops."""
    def __init__(self, parent):
        super().__init__("Prop Manager")
        self.parent = parent 
        self.glob = getattr(parent, 'glob', None)
        self.env = self.glob.env
        self.view = getattr(parent, 'graph', None).view if hasattr(parent, 'graph') else None
        self.current_prop = None 
        self.leftPanel = None
        self.is_updating_ui = False
        
        layout = QVBoxLayout()
        self.setLayout(layout)

        self.visibility_toggle = QCheckBox("Prop Visible in Viewport")
        self.visibility_toggle.setChecked(True)
        self.visibility_toggle.stateChanged.connect(self.toggle_visibility)
        layout.addWidget(self.visibility_toggle)

        self.dock_lock_checkbox = QCheckBox("🔒 Lock Workspace Panel Position")
        self.dock_lock_checkbox.setChecked(False)
        
        def handle_dock_lock_click(state):
            is_checked = (state == 2)
            from .prop_module import _standalone_studio_dock_instance
            if _standalone_studio_dock_instance:
                lock_func = _standalone_studio_dock_instance.property("set_dock_locked")
                if lock_func:
                    lock_func(is_checked)
                    
        self.dock_lock_checkbox.stateChanged.connect(handle_dock_lock_click)
        layout.addWidget(self.dock_lock_checkbox)

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

        self.remove_all_btn = QPushButton("🗑️ Remove All Props from Room")
        self.remove_all_btn.clicked.connect(self.execute_remove_all_button_logic)
        self.remove_all_btn.setStyleSheet("background-color: #d9534f; color: white; font-weight: bold; padding: 5px;")
        layout.addWidget(self.remove_all_btn)

        self.remove_btn = QPushButton("❌ Remove Selected Prop")
        self.remove_btn.clicked.connect(self.remove_current_prop)
        self.remove_btn.setStyleSheet("background-color: #a13d3d; color: white; font-weight: bold; padding: 5px;")
        layout.addWidget(self.remove_btn)

        self.export_scene_btn = QPushButton("📦 Export Full 3D Prop Scene")
        self.export_scene_btn.setMinimumHeight(32)
        self.export_scene_btn.setStyleSheet("font-weight: bold; background-color: #A1763D; color: #FFFFFF;")
        layout.addWidget(self.export_scene_btn)
        self.export_scene_btn.clicked.connect(self.trigger_addon_exporter)

        self.material_studio_group = MHGroupBox("Material Control Layout")
        material_studio_layout = QVBoxLayout()

        self.open_material_maker_btn = QPushButton("🎨 Open Native Material Studio Creator")
        self.open_material_maker_btn.setMinimumHeight(32)
        self.open_material_maker_btn.setStyleSheet("font-weight: bold; background-color: #4A2D7B; color: #FFFFFF;")
        self.open_material_maker_btn.clicked.connect(self.launch_native_material_maker)
        
        material_studio_layout.addWidget(self.open_material_maker_btn)
        self.material_studio_group.setLayout(material_studio_layout)
        layout.addWidget(self.material_studio_group)

        self.prop_fsm = PropStateMachine(panel_ref=self)

        self.state_heartbeat_clock = QTimer(self)
        self.state_heartbeat_clock.timeout.connect(self.execute_master_heartbeat_pulse)
        self.state_heartbeat_clock.start(33) # Accelerated to 33ms target (~30 FPS simulation delta)

    def execute_master_heartbeat_pulse(self):
        """Unified system heartbeat pumps FSM ticks and particle physics calculations."""
        # 1. Pump the state machine transition pipelines
        if hasattr(self, 'pump_state_machine_tick'):
            self.pump_state_machine_tick()
            
        # 2. Pump the live particle engine physics translations
        self.calculate_live_particle_physics_tick()

    def calculate_live_particle_physics_tick(self):
        """Computes particle vector increments inside memory tracking pools."""
        props_list = getattr(self.glob, 'custom_props_list', [])
        if not props_list:
            return

        for prop in props_list:
            # Check variable schemas safely across all script generations
            obj_type = getattr(prop, 'object_type', getattr(prop, 'type', 'STATIC'))
            if str(obj_type).upper() != 'EMITTER' and not getattr(prop, 'is_emitting', False):
                continue
            
            # Check left sidebar checkbox visibility state gate blocks
            if self.leftPanel and hasattr(self.leftPanel, 'active_emit_cb'):
                if not self.leftPanel.active_emit_cb.isChecked():
                    continue

            if not hasattr(prop, "particles_pool"):
                prop.particles_pool = []

            max_particles = getattr(prop, 'max_particles', getattr(prop, 'particle_count', 200))
            p_pos = getattr(prop, 'position', getattr(prop, 'world_position', [0.0, 0.0, 0.0]))

            # 1. Generate fresh particle records up to the assigned buffer threshold
            if len(prop.particles_pool) < int(max_particles):
                p_color = getattr(prop, 'particle_color', getattr(prop, 'color_rgba', [1.0, 0.4, 0.0, 1.0]))
                for _ in range(2):
                    new_particle = MH2PropParticle(p_pos, p_color)
                    prop.particles_pool.append(new_particle)

            # 2. Progress coordinates smoothly using a flat physics delta time step
            for p in prop.particles_pool:

                if hasattr(p, 'update'):
                    p.update(0.033) # Progress physics forward using 30fps step
                else:
                    # Fallback structural update if the raw particle class is raw list array format
                    pass 

            # 3. Flush expired particle nodes out of active drawing tracking lists
            if hasattr(prop, 'particles_pool'):
                prop.particles_pool = [p for p in prop.particles_pool if hasattr(p, 'is_dead') and not p.is_dead()]
            
            # 4. Bind values cleanly onto the shared object so opengl/multi_prop.py can read them
            prop.particles = [[float(part.x), float(part.y), float(part.z)] for part in prop.particles_pool]

        # Trigger an immediate OpenGL canvas buffer refresh to repaint the canvas scene
        if self.glob and getattr(self.glob, 'openGLWindow', None):
            self.glob.openGLWindow.update()

    def execute_remove_all_button_logic(self):
        """Wipes the active workspace cleanly and resets state parameters."""
        print("[Prop Studio Room] Executing full scene purge from control button signal...")
        if self.leftPanel and hasattr(self.leftPanel, 'prop_list'):
            self.leftPanel.prop_list.clear()
            
        if self.glob and hasattr(self.glob, 'custom_props_list') and self.glob.custom_props_list is not None:
            self.glob.custom_props_list.clear()
            
        if hasattr(self.glob, 'multi_prop_manager_instance') and self.glob.multi_prop_manager_instance:
            self.glob.multi_prop_manager_instance.clearAllProps()
            
        self.current_prop = None
        if self.glob and getattr(self.glob, 'openGLWindow', None):
            self.glob.openGLWindow.update()
        print("[Prop Studio Room] Success: Workspace reset complete.")

    def trigger_addon_exporter(self):
        """Streamlined Scene Exporter. Hard-coded to glTF standard format."""
        import os
        from PySide6.QtWidgets import QInputDialog, QLineEdit

        active_props = []
        sources = [
            getattr(self.glob, 'custom_props_list', []),
            getattr(self, 'loaded_props', []),
            getattr(self, 'props_list', [])
        ]
        if hasattr(self, 'leftPanel') and self.leftPanel:
            sources.append(getattr(self.leftPanel, 'loaded_props', []))
            sources.append(getattr(self.leftPanel, 'props_list', []))
            
        for source_list in sources:
            for item in source_list:
                if item and item not in active_props:
                    active_props.append(item)
                    
        if not active_props:
            print("[Prop Studio Error] Export aborted: No active props found in arrays.")
            return

        parent_window = self.parent if hasattr(self, 'parent') else None

        scene_name, name_ok = QInputDialog.getText(
            parent_window,
            "Name Your 3D Prop Scene",
            "Enter a filename for your combined glTF layout:",
            QLineEdit.EchoMode.Normal,
            "studio_combined_scene"
        )
        
        if not name_ok or not scene_name.strip():
            print("[Prop Studio Addon] Export cancelled by user.")
            return
            
        clean_scene_name = "".join([c for c in scene_name if c.isalpha() or c.isdigit() or c in (' ', '_', '-')]).strip()
        clean_scene_name = clean_scene_name.replace(" ", "_")
        if not clean_scene_name:
            clean_scene_name = "studio_combined_scene"

        export_dir = None
        if self.env and hasattr(self.env, 'stdUserPath'):
            try:
                export_dir = self.env.stdUserPath("scenes")
            except Exception:
                export_dir = None
                
        if not export_dir:
            export_dir = os.path.abspath(os.path.join(os.getcwd(), "data", "scenes"))
            
        if not os.path.exists(export_dir):
            os.makedirs(export_dir, exist_ok=True)
            
        destination_filepath = os.path.normpath(os.path.join(export_dir, f"{clean_scene_name}.gltf")).replace("\\", "/")

        skel = None
        if hasattr(self.glob, 'baseClass') and self.glob.baseClass:
            skel = getattr(self.glob.baseClass, 'skeleton', None)

        print(f"[Prop Studio Addon] Dispatching master scene graph to format channel: GLTF...")
        print(f"[Prop Studio Exporter] Target Destination: {destination_filepath}")

        from . import export_scene
        
        success, msg = export_scene.export_props_scene(
            filepath=destination_filepath, 
            format_type="gltf",
            custom_props_list=active_props, 
            skeleton_ref=skel
        )
        
        if success:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(parent_window, "Export Complete!", f"Successfully exported scene:\n{msg}")
            print(f"[Prop Studio Addon] Export Success: {msg}")
        else:
            print(f"[Prop Studio Addon] Export Failure: {msg}")

    def setLeftPanel(self, panel):
        """Links the numeric coordinate input forms to this panel manager."""
        self.leftPanel = panel

    def select_active_prop(self, prop_obj):
        """Sets the currently active workspace object for transformations and parenting updates."""
        self.current_prop = prop_obj
        if self.leftPanel and prop_obj:
            self.leftPanel.setValueFromProp(prop_obj)

    def launch_native_material_maker(self):
        """Dynamically verifies and constructs core engine Material layers before launching the editor."""
        active_prop = getattr(self, "current_prop", None)
        if not active_prop or not hasattr(active_prop, 'obj') or active_prop.obj is None:
            print("[Prop Studio Error] Cannot launch material suite: No active prop asset selected.")
            return

        engine_obj = active_prop.obj

        # Ensure the global engine workspace pointer is securely fetched on execution
        runtime_glob = self.glob
        if not runtime_glob and hasattr(self, 'parent') and self.parent:
            runtime_glob = getattr(self.parent, 'glob', None)
        if not runtime_glob:
            # Fall back directly to the global application state tracker mapping arrays
            from core.globenv import glob
            runtime_glob = glob

        try:
            from gui.materialeditor import MHMaterialEditor
            from opengl.material import Material
            print("[Prop Studio Core] Successfully loaded structural material libraries from opengl.")
        except ImportError:
            try:
                from apps.gui.materialeditor import MHMaterialEditor
                from apps.opengl.material import Material
                print("[Prop Studio Core] Successfully loaded material libraries via alternate paths.")
            except ImportError as fallback_err:
                print(f"[Prop Studio Error] Critical: Core application material packages could not be imported: {fallback_err}")
                return

        if not hasattr(engine_obj, 'material') or not isinstance(engine_obj.material, Material):
            obj_dir = os.path.dirname(active_prop.path)
            # Use our secured runtime global pointer handle safely here
            native_material_layer = Material(glob=runtime_glob, objdir=obj_dir, eqtype="props")
            native_material_layer.name = f"{active_prop.name}_material"
            
            original_is_existent = native_material_layer.isExistent
            
            def safe_decoupled_path_validator(filename):
                if os.path.isabs(filename) and os.path.exists(filename):
                    return filename
                local_dir_check = os.path.normpath(os.path.join(obj_dir, filename))
                if os.path.exists(local_dir_check):
                    return local_dir_check
                try:
                    return original_is_existent(filename)
                except Exception:
                    return os.path.abspath(filename)

            native_material_layer.isExistent = safe_decoupled_path_validator

            expected_mhmat_path = active_prop.path.replace(".obj", ".mhmat")
            if os.path.isfile(expected_mhmat_path):
                try:
                    native_material_layer.loadMatFile(expected_mhmat_path)
                except Exception as mat_read_err:
                    print(f"[Prop Studio Warning] Failed parsing .mhmat properties: {mat_read_err}")
            else:
                try:
                    native_material_layer.saveMatFile(expected_mhmat_path)
                except Exception as mat_write_err:
                    print(f"[Prop Studio Warning] Could not initialize material template file: {mat_write_err}")
                
            engine_obj.material = native_material_layer
            active_prop.material = native_material_layer

        try:
            self.mat_editor_window = MHMaterialEditor(parent=self, obj=engine_obj)
            self.mat_editor_window.updateWidgets(engine_obj)
            self.mat_editor_window.setWindowTitle(f"Material Studio Shaders ➔ Editing: {getattr(active_prop, 'name', 'Prop')}")
            
            self.mat_editor_window.show()
            self.mat_editor_window.raise_()
            self.mat_editor_window.activateWindow()
            print("[Prop Studio UI] Advanced Material Editor spawned directly and displayed successfully.")

        except Exception as launch_err:
            print(f"[Prop Studio Error] An unexpected error occurred while launching material shaders: {launch_err}")

    def save_prop_data(self):
        """Extracts live transformation coordinates and serializes them into a JSON file."""
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
                "type": str(getattr(active_prop, "object_type", "STATIC")),
                "mesh_path": str(active_prop.path.split("prop_panel/")[-1] if "prop_panel/" in active_prop.path else active_prop.path),
                "position": pos_list,
                "world_position": pos_list,
                "rotation": rot_list,
                "scale": scl_list,
                "visible": bool(getattr(active_prop, "visible", True)),
                "is_mesh_visible": bool(getattr(active_prop, "is_mesh_visible", True)),
                "is_emitting": bool(getattr(active_prop, "is_emitting", False)),
                "particle_count": int(getattr(active_prop, "max_particles", 300)),
                "color_rgba": [float(c) for c in getattr(active_prop, "particle_color", [1.0, 0.5, 0.0, 1.0])],
                "default_bone": str(getattr(active_prop, "parent_bone", "hand_R")),
                "use_parenting": bool(getattr(active_prop, "use_parenting", False))
            }

            with open(destination_json_path, 'w', encoding='utf-8') as json_file:
                json.dump(json_structure, json_file, indent=4)
                
            print(f"[Prop Studio Core] Successfully exported layout asset presets file to: {destination_json_path}")
            return True

        except Exception as export_fault_err:
            print(f"[Prop Studio Error] System asset serialization pipeline failed: {export_fault_err}")
            return False

    def toggle_visibility(self, state):
        is_visible = (state != 0)
        if self.current_prop: 
            self.current_prop.visible = is_visible
            self.current_prop.is_mesh_visible = is_visible
            if hasattr(self.current_prop, 'mesh_reference') and self.current_prop.mesh_reference:
                mesh_obj = self.current_prop.mesh_reference.getObj()
                if mesh_obj: 
                    mesh_obj.visible = is_visible
            self._trigger_viewport_redraw()

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

    def setCurrentProp(self, prop_name):

        self.current_prop = None
        props_pool = getattr(self.glob, 'custom_props_list', [])
        
        for prop in props_pool:
            target_id = getattr(prop, 'prop_id', getattr(prop, 'name', ''))
            if str(target_id).lower() == str(prop_name).lower() or str(getattr(prop, 'name', '')).lower() == str(prop_name).lower():
                self.current_prop = prop
                break
                
        if not self.current_prop: 
            return None
        
        prop_visible = getattr(self.current_prop, 'is_mesh_visible', getattr(self.current_prop, 'visible', True))
        prop_parenting = getattr(self.current_prop, 'use_parenting', False)
        prop_bone = getattr(self.current_prop, 'parent_bone', 'None')

        self.visibility_toggle.blockSignals(True)
        self.parent_toggle.blockSignals(True)
        self.bone_selector.blockSignals(True)

        self.visibility_toggle.setChecked(prop_visible)
        self.parent_toggle.setChecked(prop_parenting)
        self.bone_selector.setEnabled(prop_parenting)
            
        idx = self.bone_selector.findText(prop_bone)
        if idx >= 0: 
            self.bone_selector.setCurrentIndex(idx)
        
        self.visibility_toggle.blockSignals(False)
        self.parent_toggle.blockSignals(False)
        self.bone_selector.blockSignals(False)

        if hasattr(self, 'prop_fsm') and self.prop_fsm:
            self.state_label.setText(f"Current State Pipeline: {self.prop_fsm.current_state_name}")
        return self.current_prop

    def _trigger_viewport_redraw(self):
        """Helper to safely wake up and update the shared OpenGL scene viewport context."""
        if self.glob and getattr(self.glob, 'openGLWindow', None):
            self.glob.openGLWindow.update()

    def pump_state_machine_tick(self):
        if self.glob is not None:
            bc = getattr(self.glob, 'baseClass', None)
            if bc and hasattr(bc, 'scene') and bc.scene and hasattr(bc.scene, 'floorsize'):
                f_size = bc.scene.floorsize
                if isinstance(f_size, (list, tuple, np.ndarray)) and len(f_size) >= 3:
                    master_w = float(f_size[0])
                    master_l = float(f_size[2])
                else:
                    master_w = float(f_size) if f_size is not None else 10.0
                    master_l = float(f_size) if f_size is not None else 10.0
                
                cached_w = float(getattr(self.glob, 'last_cached_room_w', 0.0))
                cached_l = float(getattr(self.glob, 'last_cached_room_l', 0.0))
                
                if abs(master_w - cached_w) > 0.001 or abs(master_l - cached_l) > 0.001:
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
                
                if bc and (hasattr(bc, 'pose_skeleton') or hasattr(bc, 'skeleton')) and target_bone_name != "None":
                    # Access the skeleton mapping properties based on the active pose mode states
                    skeleton = bc.pose_skeleton if getattr(bc, 'in_posemode', False) else bc.skeleton
                    if skeleton and hasattr(skeleton, 'bones') and target_bone_name in skeleton.bones:
                        bone = skeleton.bones[target_bone_name]
                        
                        # Extract the structural coordinate translation positions out of the joint objects
                        b_pos = getattr(bone, 'poseheadPos', getattr(bone, 'headPos', None))
                        b_rot = getattr(bone, 'matPoseVerts', getattr(bone, 'matRestGlobal', None))
                        
                        if b_pos is not None:
                            pos_vector = [float(b_pos.x()), float(b_pos.y()), float(b_pos.z())]
                            
                            # Safely apply position coordinates directly into the PropObject tracker!
                            if hasattr(self.current_prop, 'set_transform'):
                                self.current_prop.set_transform(pos=pos_vector)
                            else:
                                self.current_prop.position = np.array(pos_vector, dtype=np.float64)

            elif current_run_state == "DEQUIPPING":
                if getattr(self.current_prop, 'use_parenting', False) and hasattr(self.current_prop, 'detach'):
                    self.current_prop.detach()
                self.prop_fsm.update_machine(active_name)

    def sync_sidebar_list_display(self):
        """Refreshes the itemized catalog rows displayed in the left workspace panel."""
        if not self.leftPanel or not hasattr(self.leftPanel, 'prop_list'): 
            return
            
        self.leftPanel.prop_list.blockSignals(True)
        self.leftPanel.prop_list.clear()
        
        custom_pool = getattr(self.glob, 'custom_props_list', [])
        sys_icon_dir = None
        if self.env and hasattr(self.env, 'path_sysicon'):
            sys_icon_dir = self.env.path_sysicon
            
        for active_item in custom_pool:
            item_row = QListWidgetItem()
            
            # Unpack properties with safety fallbacks
            name_token = getattr(active_item, 'name', 'unnamed')
            bone_target = getattr(active_item, 'parent_bone', 'None')
            use_parenting = getattr(active_item, 'use_parenting', False)
            
            state_str = f"[EQUIPPED ➔ {bone_target}]" if use_parenting else "[IDLE ➔ Floor]"
            
            # Forces the label prefix syntax to match what the row clicker splits look for
            item_row.setText(f"[O] {name_token} | State: {state_str}")
            item_row.setData(Qt.UserRole, name_token)
            
            thumb_path = active_item.path.replace(".obj", ".thumb") if hasattr(active_item, 'path') else ""
            
            if thumb_path and os.path.isfile(thumb_path):
                item_row.setIcon(QIcon(QPixmap(thumb_path)))
            else:
                placeholder_img = os.path.join("makehuman2/data/sysicons", "eq_props.png")
                if not os.path.isfile(placeholder_img):
                    if sys_icon_dir:
                        placeholder_img = os.path.normpath(os.path.join(sys_icon_dir, "reset.png")).replace("\\", "/")
                    else:
                        placeholder_img = ""
                    
                if placeholder_img and os.path.isfile(placeholder_img):
                    item_row.setIcon(QIcon(QPixmap(placeholder_img)))
                    
            self.leftPanel.prop_list.addItem(item_row)
            
            if getattr(self, 'current_prop', None) == active_item:
                self.leftPanel.prop_list.setCurrentItem(item_row)
                
        self.leftPanel.prop_list.blockSignals(False)

    def refreshProps(self, dtype):
        """Scans BOTH core plugin directories and user custom paths seamlessly to merge all data files."""
        data = []
        custom_pool = getattr(self.glob, 'custom_props_list', [])
        search_directories = []
        
        if self.env and hasattr(self.env, 'stdUserPath'):
            try:
                user_path = os.path.join(self.env.stdUserPath(), "props")
                search_directories.append(user_path)
            except Exception:
                pass
                
        local_plugin_data = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "props"))
        search_directories.append(local_plugin_data)
        
        sys_icon_dir = None
        if self.env and hasattr(self.env, 'path_sysicon'):
            sys_icon_dir = self.env.path_sysicon

        processed_obj_paths = set()

        for target_dir in search_directories:
            if not target_dir or not os.path.isdir(target_dir):
                continue
                
            for filename in os.listdir(target_dir):
                if filename.lower().endswith('.obj'):
                    base_name, _ = os.path.splitext(filename)
                    full_obj_path = os.path.normpath(os.path.join(target_dir, filename)).replace("\\", "/")
                    
                    if full_obj_path in processed_obj_paths:
                        continue
                    processed_obj_paths.add(full_obj_path)
                    
                    is_active = any(getattr(p, 'path', '') == full_obj_path for p in custom_pool)
                    target_thumb = full_obj_path.replace(".obj", ".thumb")
                    
                    if not os.path.isfile(target_thumb) and sys_icon_dir:
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

                    if not any(getattr(a, 'path', '') == full_obj_path for a in getattr(self.glob, 'cachedInfo', [])):
                        from types import SimpleNamespace
                        
                        native_asset = SimpleNamespace()
                        native_asset.name = base_name
                        native_asset.uuid = uuid
                        native_asset.path = full_obj_path
                        native_asset.obj_file = full_obj_path
                        native_asset.filename = full_obj_path
                        native_asset.folder = "props"
                        native_asset.thumbfile = target_thumb
                        native_asset.author = "User"
                        native_asset.tag = tags
                        native_asset.used = is_active
                        
                        if not hasattr(self.glob, 'cachedInfo'):
                            self.glob.cachedInfo = []
                        self.glob.cachedInfo.append(native_asset)
                    else:
                        for a in self.glob.cachedInfo:
                            if getattr(a, 'path', '') == full_obj_path: 
                                a.used = is_active


        if self.leftPanel and hasattr(self.leftPanel, 'inventory_table'):
            from PySide6.QtWidgets import QTableWidgetItem
            self.leftPanel.inventory_table.setRowCount(0)
            
            row_idx = 0
            for asset in getattr(self.glob, 'cachedInfo', []):
                if getattr(asset, 'folder', '') == "props":
                    is_active = any(getattr(p, 'path', '') == asset.path for p in custom_pool)
                    self.leftPanel.inventory_table.insertRow(row_idx)
                    
                    # Column 1: Asset Name
                    name_item = QTableWidgetItem(str(getattr(asset, 'name', 'Unknown')))
                    name_item.setData(Qt.UserRole, getattr(asset, 'name', ''))
                    self.leftPanel.inventory_table.setItem(row_idx, 0, name_item)
                    
                    # Column 2: Active State Status String
                    status_str = "Active in Scene" if is_active else "Available File"
                    self.leftPanel.inventory_table.setItem(row_idx, 1, QTableWidgetItem(status_str))
                    
                    # Column 3: Action Trigger guideline text
                    action_str = "Double-click to remove" if is_active else "Double-click to equip"
                    self.leftPanel.inventory_table.setItem(row_idx, 2, QTableWidgetItem(action_str))
                    
                    data.append([getattr(asset, 'name', 'Unknown Prop'), status_str, action_str])
                    row_idx += 1
                
        if "props" in getattr(self.parent, 'equipment', {}):
            props_tab_ui = self.parent.equipment["props"].get("func")
            if props_tab_ui and hasattr(props_tab_ui, 'refreshButtons'): 
                props_tab_ui.refreshButtons()

        if len(data) == 0: 
            data = [["no props existent"]]
        return data

    def global_pipeline_refresh(self):
        """Forces lists, directory arrays, and viewport renders to sync up."""
        self.refreshProps("props")
        self.sync_sidebar_list_display()
        self._trigger_viewport_redraw()

    def find_prop_by_name(self, name):
        """Looks up an active prop instance by its string identifier name case-insensitively."""
        if not name or not hasattr(self.glob, 'custom_props_list'):
            return None
            
        target_name = str(name).lower().strip()
        
        for prop in self.glob.custom_props_list:
            # Check custom prop_id tokens alongside readable display labels
            target_id = getattr(prop, 'prop_id', getattr(prop, 'name', ''))
            if str(target_id).lower().strip() == target_name or str(getattr(prop, 'name', '')).lower().strip() == target_name:
                return prop
                    
        return None

    def add_prop_to_scene(self, asset):
        """Instantiates a loose asset file and allocates standard hardware memory buffers."""
        target_path = os.path.normpath(getattr(asset, 'path', getattr(asset, 'filename', str(asset))))
        
        pm = PropMesh(self.glob)
        res, err = pm.load(target_path)
        if res is False: 
            return False, err

        obj = pm.getObj()
        
        name = pm.getOriginalName().lower().strip()
        prop_name = getattr(asset, 'name', name).lower().strip()

        # Fallback tracking parameters
        initial_pos = [0.0, 0.0, 0.0]
        initial_rot = [0.0, 0.0, 0.0]
        initial_scale = [1.0, 1.0, 1.0]
        initial_vis = True
        use_parent = False
        target_bone = "None"
        
        json_path = target_path.replace(".obj", ".json")
        if os.path.isfile(json_path):
            config_data = None
            if self.env and hasattr(self.env, 'readJSON'):
                try: config_data = self.env.readJSON(json_path)
                except Exception: config_data = None
                    
            if config_data is None:
                try:
                    import json
                    with open(json_path, 'r', encoding='utf-8') as j_f:
                        config_data = json.load(j_f)
                except Exception as json_err:
                    print(f"[Prop Studio Warning] Bypassed local layout config error: {json_err}")
                    config_data = None

            if config_data is not None:
                name = config_data.get("name", name).lower().strip()

                initial_pos = config_data.get("position", config_data.get("offset", initial_pos))
                initial_rot = config_data.get("rotation", initial_rot)
                initial_scale = config_data.get("scale", initial_scale)
                initial_vis = config_data.get("is_mesh_visible", config_data.get("visible", initial_vis))
                
                parenting_block = config_data.get("parenting", {})
                if isinstance(parenting_block, dict):
                    use_parent = parenting_block.get("enabled", config_data.get("use_parenting", use_parent))
                    target_bone = parenting_block.get("target_bone", config_data.get("default_bone", target_bone))
                else:
                    use_parent = config_data.get("use_parenting", use_parent)
                    target_bone = config_data.get("default_bone", target_bone)

        safe_pos = [float(p) for p in initial_pos] if hasattr(initial_pos, '__len__') else [0.0, 0.0, 0.0]
        safe_rot = [float(r) for r in initial_rot] if hasattr(initial_rot, '__len__') else [0.0, 0.0, 0.0]
        
        if hasattr(initial_scale, '__len__') and len(initial_scale) >= 3:
            safe_scale = [float(initial_scale[0]), float(initial_scale[1]), float(initial_scale[2])]
        elif hasattr(initial_scale, '__len__') and len(initial_scale) > 0:
            safe_scale = [float(initial_scale[0]), float(initial_scale[0]), float(initial_scale[0])]
        else:
            s_f = float(initial_scale) if initial_scale is not None else 1.0
            safe_scale = [s_f, s_f, s_f]
            
        t_struct = {
            "translation": safe_pos, 
            "rotation": safe_rot, 
            "scale": safe_scale
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
            print(f"[Prop Studio Core] Registered '{name}' directly inside core drawing pipeline arrays.")

        new_prop = PropObject(name, self.glob)
        new_prop.mesh_reference = pm 
        new_prop.obj = obj
        new_prop.path = target_path.replace("\\", "/")
        
        # Store dynamic layout configuration parameters safely
        new_prop.prop_id = getattr(asset, 'uuid', f"props_{name}")
        
        emitter_keywords = ["ball", "diamond", "cocoon", "torch", "wisp"]
        if any(keyword in name.lower() for keyword in emitter_keywords):
            new_prop.object_type = 'EMITTER'
            new_prop.type = 'EMITTER'
            new_prop.max_particles = int(config_data.get("particle_count", 300)) if config_data else 300
            new_prop.is_emitting = bool(config_data.get("is_emitting", True)) if config_data else True
            
            if self.leftPanel:
                is_mesh_visible = not self.leftPanel.ghost_mode_cb.isChecked()
                new_prop.is_mesh_visible = is_mesh_visible
                new_prop.set_visibility(is_mesh_visible)
            else:
                new_prop.is_mesh_visible = initial_vis

            print(f"[Prop Studio Core] Dynamic keyword intercept pass successful!")
            print(f"[Prop Studio Core] '{name}' has been successfully upgraded to an EMITTER.")
        else:
            new_prop.object_type = 'STATIC'
            new_prop.type = 'STATIC'
            new_prop.is_mesh_visible = initial_vis

        new_prop.position = np.array(safe_pos, dtype=np.float64)
        new_prop.rotation = np.array(safe_rot, dtype=np.float64)
        new_prop.scale = np.array(safe_scale, dtype=np.float64)
        
        new_prop.visible = initial_vis if new_prop.is_mesh_visible else False
        new_prop.use_parenting = use_parent
        new_prop.parent_bone = target_bone

        print(dumper(new_prop))
        
        if not hasattr(self.glob, 'custom_props_list'):
            self.glob.custom_props_list = []
        self.current_prop = new_prop
        self.glob.custom_props_list.append(new_prop)

        if self.leftPanel: 
            self.leftPanel.setValueFromProp(new_prop)
            
        self.global_pipeline_refresh()
        return True, ""

    def update_selection_focus_by_name(self, target_name):
        """Allows raycasting loops or text items to swap active selection focus cleanly."""
        found_prop = self.find_prop_by_name(target_name)
        if found_prop:
            self.current_prop = found_prop
            if self.leftPanel:
                self.leftPanel.setValueFromProp(found_prop)
            if self.glob and getattr(self.glob, 'openGLWindow', None):
                self.glob.openGLWindow.update()
            return True
        return False

    def setLeftPanel(self, left):
        """Binds the opposite layout panel instance into active widget memory blocks."""
        self.leftPanel = left

    def syncedFromLeft(self, new_pos, new_rot, scl):
        """Processes real-time adjustment updates coming directly from sliders or mapping blueprints."""
        if not self.current_prop: 
            return
            
        # This keeps data structures completely safe, preventing format errors
        self.current_prop.position = np.array(new_pos, dtype=np.float64)
        self.current_prop.rotation = np.array(new_rot, dtype=np.float64)
        self.current_prop.scale = np.array(scl, dtype=np.float64)
        self.update_prop()

    def update_prop(self):
        """Pushes raw numerical properties back to update active compiled shaders."""
        if not self.current_prop: 
            return
        pos, rot, scl = self.current_prop.position, self.current_prop.rotation, self.current_prop.scale
        
        pipeline = getattr(self.glob, 'prop_manager_pipeline', None)
        if pipeline:
            pipeline.updatePropTransform(self.current_prop.name, translation=pos, rotation=rot, scale=scl)
            if hasattr(self.current_prop, 'mesh_reference') and self.current_prop.mesh_reference:
                pm_mesh = self.current_prop.mesh_reference
                prop_mat_path = getattr(self.current_prop, 'material_path', '')
                if prop_mat_path and os.path.isfile(prop_mat_path): 
                    pm_mesh.refresh_material(prop_mat_path)
                
                # Slices away 'OpenGlBuffers()' allocations to reuse graphics drivers loops safely
                if hasattr(pm_mesh, 'render') and pm_mesh.render and hasattr(pm_mesh.render, 'buffers'):
                    active_gl_buffers = pm_mesh.render.buffers
                    if hasattr(active_gl_buffers, 'GetBuffers') and hasattr(pm_mesh, 'obj') and pm_mesh.obj:
                        active_gl_buffers.GetBuffers(pm_mesh.obj.gl_coord, pm_mesh.obj.gl_norm, pm_mesh.obj.gl_uvcoord)
                        
        self._trigger_viewport_redraw()

    def remove_current_prop(self, current=None):
        """Safely unloads an asset from screen space using individual instance tracking."""
        if isinstance(current, bool) or current is None: 
            current = self.current_prop
        if current is None: 
            return

        self.bone_selector.blockSignals(True)
        self.visibility_toggle.blockSignals(True)
        self.parent_toggle.blockSignals(True)
        if self.leftPanel:
            if hasattr(self.leftPanel, 'room_map_widget') and self.leftPanel.room_map_widget:
                self.leftPanel.room_map_widget.blockSignals(True)
            if hasattr(self.leftPanel, 'room_boundary_map_widget') and self.leftPanel.room_boundary_map_widget:
                self.leftPanel.room_boundary_map_widget.blockSignals(True)

        if hasattr(current, 'mesh_reference') and current.mesh_reference: 
            current.mesh_reference.delete()
            
        target_name = current.name.lower().strip()
        
        pipeline = getattr(self.glob, 'prop_manager_pipeline', None)
        if pipeline and hasattr(pipeline, 'unregisterProp'):
            pipeline.unregisterProp(current.name)
            if hasattr(pipeline, 'active_props') and current.name in pipeline.active_props:
                del pipeline.active_props[current.name]

        custom_pool = getattr(self.glob, 'custom_props_list', [])
        for i in range(len(custom_pool) - 1, -1, -1):
            if getattr(custom_pool[i], 'name', '').lower().strip() == target_name: 
                custom_pool.pop(i)

        self.current_prop = None
        if self.leftPanel is not None and hasattr(self.leftPanel, 'resetValues'): 
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
            if hasattr(self.leftPanel, 'room_map_widget') and self.leftPanel.room_map_widget:
                self.leftPanel.room_map_widget.blockSignals(False)
            if hasattr(self.leftPanel, 'room_boundary_map_widget') and self.leftPanel.room_boundary_map_widget: 
                self.leftPanel.room_boundary_map_widget.blockSignals(False)
                
        self._trigger_viewport_redraw()

    def drop_all_workspace_assets(self):
        """Sweeps across the full layout tracking arrays to unequip all items."""
        custom_pool = getattr(self.glob, 'custom_props_list', [])
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
                    # Reset back to baseline array formats cleanly
                    prop.position = np.array([0.0, 0.0, 0.0], dtype=np.float64)

        self.parent_toggle.blockSignals(True)
        self.bone_selector.blockSignals(True)
        self.parent_toggle.setChecked(False)
        self.bone_selector.setEnabled(False)
        
        idx = self.bone_selector.findText("None")
        if idx >= 0:
            self.bone_selector.setCurrentIndex(idx)
        else:
            self.bone_selector.setCurrentIndex(0)
            
        self.parent_toggle.blockSignals(False)
        self.bone_selector.blockSignals(False)
        
        self.sync_sidebar_list_display()
        self.refreshProps("props")
        self._trigger_viewport_redraw()

    def _trigger_viewport_redraw(self):
        """Forces the active standalone OpenGL canvas window layout to repaint its buffers safely."""
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
                        
                    if hasattr(self, 'view') and self.view and hasattr(self.view, 'Tweak'):
                        self.view.Tweak()
                    elif getattr(self.glob, 'openGLWindow', None) and hasattr(self.glob.openGLWindow, 'Tweak'):
                        self.glob.openGLWindow.Tweak()
                except Exception as thread_err:
                    print(f"[Prop Studio Debug] Thread-safe redraw loop skipped: {thread_err}")

            QTimer.singleShot(0, safe_asynchronous_paint_flush)

    def findBonePosition(self):
        """Snaps an object's position directly onto the skeleton's coordinates."""
        pbone = self.bone_selector.currentText()
        if pbone == "None" or not self.parent_toggle.isChecked(): 
            return
            
        bc = getattr(self.glob, 'baseClass', None)
        if bc is None: 
            return
            
        pinfo = getattr(bc, 'baseInfo', {})
        if not "props" in pinfo or pbone not in pinfo["props"]: 
            return
            
        pbone = pinfo["props"][pbone]
        skeleton = bc.pose_skeleton if getattr(bc, 'in_posemode', False) else bc.skeleton
        if skeleton is None: 
            skeleton = getattr(bc, 'default_skeleton', None)
        if skeleton is None: 
            return
            
        if hasattr(skeleton, 'bones') and pbone in skeleton.bones:
            bone = skeleton.bones[pbone]
            b_coord = bone.posetailPos if getattr(bc, 'in_posemode', False) else bone.tailPos
            
            if b_coord is not None and self.current_prop: 

                # Pull custom offset adjustments securely from local metadata slots
                offset = getattr(self.current_prop, 'local_offset_pos', np.array([0.0,0.0,0.0]))
                
                # Apply absolute snap coordinates without stacking values into an infinite drift loop
                aligned_pos = [
                    float(offset[0]) + float(b_coord.x()),
                    float(offset[1]) + float(b_coord.y()),
                    float(offset[2]) + float(b_coord.z())
                ]
                
                self.current_prop.position = np.array(aligned_pos, dtype=np.float64)
                
                if self.leftPanel:
                    self.leftPanel.setValueFromProp(self.current_prop)
                    
                self._trigger_viewport_redraw()

_standalone_studio_dock_instance = None


def initialize_prop_studio(app_reference, glob_reference, **kwargs):
    """Official decoupled entry point executed via the plugin panel."""
    global _standalone_studio_dock_instance
    import os

    main_window = None
    for widget in QApplication.topLevelWidgets():
        if isinstance(widget, QMainWindow) or widget.objectName() == "mainwindow" or hasattr(widget, "central_widget"):
            main_window = widget
            break

    if not main_window:
        main_window = app_reference

    if _standalone_studio_dock_instance is not None:
        if _standalone_studio_dock_instance.isVisible():
            _standalone_studio_dock_instance.hide()
            print("[Prop Studio] Dockable controller hidden.")
        else:
            _standalone_studio_dock_instance.show()
            _standalone_studio_dock_instance.raise_()
            print("[Prop Studio] Dockable controller restored.")
        return True

    _standalone_studio_dock_instance = QDockWidget("Prop Studio Workspace Controller", main_window)
    _standalone_studio_dock_instance.setObjectName("prop_studio_dockable_window_frame")
    _standalone_studio_dock_instance.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable | QDockWidget.DockWidgetClosable)
    _standalone_studio_dock_instance.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea | Qt.BottomDockWidgetArea)
    _standalone_studio_dock_instance.resize(1100, 850)


    from mh2_official_tools.prop_panel.core.json_manager import load_props_manifest, update_prop_json_entry
    loaded_manifest = load_props_manifest()
    
    # Store the real file records cache onto the dock window properties permanently
    _standalone_studio_dock_instance.setProperty("manifest_data", loaded_manifest)
    print(f"[Prop Studio] Initialized layout environment. Embedded data options count: {len(loaded_manifest)}")

    def apply_dock_layout_lock(should_lock=True):
        if _standalone_studio_dock_instance:
            if should_lock:
                _standalone_studio_dock_instance.setFeatures(QDockWidget.NoDockWidgetFeatures)
                print("[Prop Studio] Dock features safely locked in place.")
            else:
                _standalone_studio_dock_instance.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable | QDockWidget.DockWidgetClosable)
                print("[Prop Studio] Dock features unfrozen.")

    _standalone_studio_dock_instance.setProperty("set_dock_locked", apply_dock_layout_lock)

    master_workspace_container = QWidget()
    master_layout = QVBoxLayout(master_workspace_container)
    master_layout.setContentsMargins(4, 4, 4, 4)

    panel_slider_splitter = QSplitter(Qt.Horizontal)
    panel_slider_splitter.setObjectName("prop_studio_interactive_splitter_bar")
    
    left_scroll_wrapper = QScrollArea()
    left_scroll_wrapper.setWidgetResizable(True)
    left_scroll_wrapper.setMinimumWidth(320)  
    
    right_scroll_wrapper = QScrollArea()
    right_scroll_wrapper.setWidgetResizable(True)
    right_scroll_wrapper.setMinimumWidth(450)

    left_control_panel = QWidget()
    left_layout = QVBoxLayout(left_control_panel)
    left_layout.setContentsMargins(6, 6, 6, 6)

    left_layout.addWidget(QLabel("<b>Available Studio Props:</b>"))
    prop_list_widget = QListWidget()
    prop_list_widget.setObjectName("prop_studio_asset_selector_list")
    left_layout.addWidget(prop_list_widget)

    emitter_context_group = MHGroupBox("Dynamic Emitter Modifiers")
    context_layout = QVBoxLayout()

    ghost_mode_cb = QCheckBox("Hide Prop Mesh (Pure Ghost Emitter Only)")
    context_layout.addWidget(ghost_mode_cb)

    active_emit_cb = QCheckBox("Enable Active Particle Emission Loop")
    active_emit_cb.setChecked(True)
    context_layout.addWidget(active_emit_cb)

    emitter_context_group.setLayout(context_layout)
    left_layout.addWidget(emitter_context_group)
    
    emitter_context_group.setVisible(False)
    left_scroll_wrapper.setWidget(left_control_panel)

    for prop_id, prop_info in loaded_manifest.items():
        list_item = QListWidgetItem(prop_info.get("name", prop_id))
        list_item.setData(Qt.UserRole, prop_id)
        prop_list_widget.addItem(list_item)

    def on_prop_selection_changed():
        current_item = prop_list_widget.currentItem()
        if not current_item:
            return
            
        selected_id = current_item.data(Qt.UserRole)

        current_manifest = _standalone_studio_dock_instance.property("manifest_data") or {}
        asset_profile = current_manifest.get(selected_id, {})
        
        _standalone_studio_dock_instance.setProperty("active_prop_id", selected_id)
        obj_type = str(asset_profile.get("type", "STATIC")).upper()

        if obj_type == "EMITTER":
            ghost_mode_cb.blockSignals(True)
            active_emit_cb.blockSignals(True)
            
            ghost_mode_cb.setChecked(not asset_profile.get("is_mesh_visible", True))
            active_emit_cb.setChecked(asset_profile.get("is_emitting", True))
            
            ghost_mode_cb.blockSignals(False)
            active_emit_cb.blockSignals(False)
            
            emitter_context_group.setVisible(True)
        else:
            emitter_context_group.setVisible(False)

    prop_list_widget.itemSelectionChanged.connect(on_prop_selection_changed)

    def on_ghost_toggled(checked):
        active_id = _standalone_studio_dock_instance.property("active_prop_id")
        current_manifest = _standalone_studio_dock_instance.property("manifest_data") or {}
        
        if active_id and active_id in current_manifest:
            is_visible = not checked
            current_manifest[active_id]["is_mesh_visible"] = is_visible
            
            # Flush updates down to the property tracker loop so selections preserve states
            _standalone_studio_dock_instance.setProperty("manifest_data", current_manifest)
            
            update_prop_json_entry(active_id, {"is_mesh_visible": is_visible})
            print(f"[Prop Studio Context] Ghost option updated and saved for item: {active_id}")
            
            if hasattr(glob_reference, 'openGLWindow') and glob_reference.openGLWindow:
                glob_reference.openGLWindow.Tweak()
                if hasattr(glob_reference.openGLWindow, 'update'):
                    glob_reference.openGLWindow.update()

    ghost_mode_cb.toggled.connect(on_ghost_toggled)

    def on_emission_loop_toggled(checked):
        active_id = _standalone_studio_dock_instance.property("active_prop_id")
        current_manifest = _standalone_studio_dock_instance.property("manifest_data") or {}
        
        if active_id and active_id in current_manifest:
            current_manifest[active_id]["is_emitting"] = checked
            target_type = "EMITTER" if checked else "STATIC"
            current_manifest[active_id]["type"] = target_type
            
            # Sync directly with the core exporter custom props list array variables
            custom_pool = getattr(glob_reference, 'custom_props_list', [])
            for prop in custom_pool:

                target_id = getattr(prop, 'prop_id', getattr(prop, 'name', ''))
                if str(target_id).lower() == str(active_id).lower():
                    prop.type = target_type
                    prop.object_type = target_type
                    prop.is_emitting = checked

            # Update the stored manifest memory state tracking dictionary array values
            _standalone_studio_dock_instance.setProperty("manifest_data", current_manifest)

            # Saves emission state parameters straight to disk cleanly
            update_prop_json_entry(active_id, {"is_emitting": checked, "type": target_type})
            print(f"[Prop Studio Context] Emission loop saved for item: {active_id} (Mode: {target_type})")
            
            # Flush the viewport graphics buffers instantly
            if hasattr(glob_reference, 'openGLWindow') and glob_reference.openGLWindow:
                glob_reference.openGLWindow.Tweak()
                if hasattr(glob_reference.openGLWindow, 'update'):
                    glob_reference.openGLWindow.update()

    # Connect both checkboxes to their interactive tracking listeners cleanly
    if 'ghost_mode_cb' in locals() and 'active_emit_cb' in locals():
        ghost_mode_cb.toggled.connect(on_ghost_toggled)
        active_emit_cb.toggled.connect(on_emission_loop_toggled)

    right_dummy = QLabel("Loading 3D Room Grid Viewport...")
    right_dummy.setAlignment(Qt.AlignCenter)
    right_scroll_wrapper.setWidget(right_dummy)

    panel_slider_splitter.addWidget(left_scroll_wrapper)
    panel_slider_splitter.addWidget(right_scroll_wrapper)
    panel_slider_splitter.setSizes([380, 720])
    
    master_layout.addWidget(panel_slider_splitter)
    _standalone_studio_dock_instance.setWidget(master_workspace_container)
    

    # 1. Mount it to the main application interface grid system FIRST
    if main_window and hasattr(main_window, "addDockWidget"):
        main_window.addDockWidget(Qt.RightDockWidgetArea, _standalone_studio_dock_instance)
        
    # 2. Tell Qt to let it safely sit cleanly inside the side workspace panel on boot
    _standalone_studio_dock_instance.setFloating(False)
        
    # 3. Pull the window up onto the front monitor layers
    _standalone_studio_dock_instance.show()
    _standalone_studio_dock_instance.raise_()

    def force_minimize_buttons():
        if _standalone_studio_dock_instance and _standalone_studio_dock_instance.isFloating():
            top_frame = _standalone_studio_dock_instance.window()
            if top_frame:
                top_frame.setWindowFlags(Qt.Window | Qt.WindowMinMaxButtonsHint | Qt.WindowCloseButtonHint)
                top_frame.show()
    QTimer.singleShot(150, force_minimize_buttons)

    def dynamic_dock_toggle_trigger():
        if _standalone_studio_dock_instance:
            is_currently_floating = _standalone_studio_dock_instance.isFloating()
            _standalone_studio_dock_instance.setFloating(not is_currently_floating)
            
            btn_txt = "⚓ Dock Studio Window" if is_currently_floating else "🪟 Float Studio Window"
            
            active_panel_widget = _standalone_studio_dock_instance.widget()
            if active_panel_widget:
                for target_btn in active_panel_widget.findChildren(QPushButton):
                    if "dock" in str(target_btn.text()).lower() or "float" in str(target_btn.text()).lower():
                        target_btn.setText(btn_txt)

    _standalone_studio_dock_instance.setProperty("dock_toggle_func", dynamic_dock_toggle_trigger)

    def deferred_ui_assembly():
        nonlocal main_window
        print("[Prop Studio Core] Compiling workspace panel widgets layout...")
        
        studio_room_main = QWidget()
        studio_room_main.setObjectName("prop_studio_room_controller_canvas")
        
        master_dock_layout = QVBoxLayout(studio_room_main)
        master_dock_layout.setContentsMargins(4, 4, 4, 4)
        
        workspace_splitter = QSplitter(Qt.Horizontal)
        workspace_splitter.setObjectName("prop_studio_nested_workspace_splitter")

        # COLUMN 1: THE NATIVE LOCAL FILER ASSET GRID TAB VIEW
        asset_catalog_tabs = QTabWidget()
        asset_catalog_tabs.setMinimumWidth(280)
        
        plugin_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
        addon_props_dir = os.path.normpath(os.path.join(plugin_root, "data", "props")).replace("\\", "/")
        
        user_props_dir = ""
        if hasattr(main_window, 'glob') and hasattr(main_window.glob, 'env'):
            user_props_dir = os.path.normpath(os.path.join(main_window.glob.env.stdUserPath(), "props")).replace("\\", "/")
        else:
            user_props_dir = os.path.normpath(os.path.join(os.path.expanduser("~"), "makehuman2", "data", "props")).replace("\\", "/")

        local_grid_widget = QListWidget()
        local_grid_widget.setViewMode(QListWidget.IconMode)
        local_grid_widget.setIconSize(QSize(90, 90))
        local_grid_widget.setResizeMode(QListWidget.Adjust)
        local_grid_widget.setSpacing(8)
        local_grid_widget.setMovement(QListWidget.Static)

        scanned_model_assets = {}
        for search_folder in [addon_props_dir, user_props_dir]:
            if os.path.isdir(search_folder):
                for filename in os.listdir(search_folder):
                    if filename.lower().endswith('.obj'):
                        base_name, _ = os.path.splitext(filename)
                        full_obj_path = os.path.join(search_folder, filename).replace("\\", "/")
                        thumb_path = os.path.join(search_folder, f"{base_name}.thumb").replace("\\", "/")
                        png_path = os.path.join(search_folder, f"{base_name}.png").replace("\\", "/")
                        
                        active_icon_path = ""
                        if os.path.isfile(thumb_path): 
                            active_icon_path = thumb_path
                        elif os.path.isfile(png_path): 
                            active_icon_path = png_path
                        else:
                            if hasattr(main_window, 'glob') and hasattr(main_window.glob.env, 'path_sysicon'):
                                active_icon_path = os.path.normpath(os.path.join(main_window.glob.env.path_sysicon, "reset.png")).replace("\\", "/")

                        if base_name not in scanned_model_assets:
                            scanned_model_assets[base_name] = {"path": full_obj_path, "icon": active_icon_path}

        for name, data_pack in scanned_model_assets.items():
            grid_item = QListWidgetItem()
            grid_item.setText(name)
            grid_item.setTextAlignment(Qt.AlignCenter)
            grid_item.setSizeHint(QSize(100, 120))
            if os.path.isfile(data_pack["icon"]):
                grid_item.setIcon(QIcon(QPixmap(data_pack["icon"])))
            local_grid_widget.addItem(grid_item)

        asset_catalog_tabs.addTab(local_grid_widget, "Asset Browser")

        # COLUMN 2 & 3: MOUNT CONTROLLER SIDEBARS
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setMinimumWidth(360) 
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        left_panel_widget = PropManLeftPanel(parent=main_window)
        left_scroll.setWidget(left_panel_widget) 

        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setMinimumWidth(340)
        right_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        right_container = QWidget()
        right_panel_layout = QVBoxLayout(right_container)
        
        prop_manager_widget = PropManagerPanel(parent=main_window)
        right_panel_layout.addWidget(prop_manager_widget)
        right_panel_layout.addStretch(1)

        right_scroll.setWidget(right_container)

        # Map backend inter-panel links using widget name references directly
        prop_manager_widget.setLeftPanel(left_panel_widget)
        left_panel_widget.propman = prop_manager_widget
        left_panel_widget.prop_update = prop_manager_widget.syncedFromLeft

        workspace_splitter.addWidget(asset_catalog_tabs)
        workspace_splitter.addWidget(left_scroll)
        workspace_splitter.addWidget(right_scroll)
        workspace_splitter.setSizes([330, 385, 385])
        
        master_dock_layout.addWidget(workspace_splitter)

        def handle_local_grid_click(item):
            if not item or not prop_manager_widget: 
                return
            asset_name = item.text()
            if asset_name in scanned_model_assets:
                file_target = scanned_model_assets[asset_name]["path"]
                thumb_target = scanned_model_assets[asset_name]["icon"]
                from types import SimpleNamespace
                mock_asset = SimpleNamespace(
                    name=asset_name, path=file_target, filename=file_target, folder="props",
                    subfolder=None, thumbfile=thumb_target, author="User", tag=["user", asset_name]
                )
                print(f"[Prop Studio Core] Deploying scene initialization for: {file_target}")
                prop_manager_widget.add_prop_to_scene(mock_asset)

        try:
            local_grid_widget.itemDoubleClicked.disconnect()
        except (TypeError, RuntimeError):
            pass

        local_grid_widget.itemDoubleClicked.connect(handle_local_grid_click)


        if 'room_layout' in locals() or 'room_layout' in globals():
            studio_room_main.blockSignals(True)
            if hasattr(main_window, 'central_widget') and main_window.central_widget:
                main_window.central_widget.blockSignals(True)

            panel_slider_splitter = QSplitter(Qt.Horizontal)
            panel_slider_splitter.setObjectName("prop_studio_room_adjustable_splitter")
            
            panel_slider_splitter.addWidget(asset_catalog_tabs)
            panel_slider_splitter.addWidget(left_scroll)
            panel_slider_splitter.addWidget(right_scroll)
            panel_slider_splitter.setSizes([400, 400, 200])
            
            room_layout.addWidget(panel_slider_splitter)
            print("[Prop Studio Core] Safely attached adjustable layout panel sliders.")
            
            studio_room_main.blockSignals(False)
            if hasattr(main_window, 'central_widget') and main_window.central_widget:
                main_window.central_widget.blockSignals(False)
        else:
            _standalone_studio_dock_instance.setWidget(studio_room_main)

        if hasattr(glob_reference, 'prop_manager_pipeline') and glob_reference.prop_manager_pipeline:
            print("[Prop Studio Core] Safely hijacked native application multi-prop manager context.")
            manager_instance = glob_reference.prop_manager_pipeline
        else:
            print("[Prop Studio Core] Creating master instance wrapper and binding to global workspace.")
            active_shaders = getattr(glob_reference, 'shaders', None)
            manager_instance = MultiPropManager(active_shaders, glob_reference)
            glob_reference.prop_manager_pipeline = manager_instance

        glob_reference.multi_prop_manager_instance = manager_instance

        if hasattr(manager_instance, 'set_panel_reference'):
            manager_instance.set_panel_reference(prop_manager_widget)

        # Tells the left panel widget to fill its columns with JSON data right now
        if 'left_panel_widget' in locals() and hasattr(left_panel_widget, 'refresh_inventory_list'):
            left_panel_widget.refresh_inventory_list()
            print("[Prop Studio Core] Safely populated local JSON files into table view rows.")
            
        print("[Prop Studio Core] Deferred UI workspace layout assembly sequence completed successfully.")

        from .viewport_hook import perform_background_hardware_link
        QTimer.singleShot(500, lambda: perform_background_hardware_link(glob_reference, main_window, prop_manager_widget))

    QTimer.singleShot(50, deferred_ui_assembly)
    return True


def draw_prop_studio_left_column(main_window, left_box_layout):
    """Natively called during drawLeftPanel execution loops inside MakeHuman 2."""
    main_window.leftColumn.setTitle("Prop Studio & Stage Wing Planner")
    left_panel = PropManLeftPanel(parent=main_window)
    
    if hasattr(left_box_layout, "addLayout"):
        left_box_layout.addLayout(left_panel)
    else:
        left_box_layout.addWidget(left_panel)
        
    right_panel_widget = getattr(main_window, "prop_manager", None)
    if right_panel_widget:
        right_panel_widget.setLeftPanel(left_panel)
        left_panel.propman = right_panel_widget
        left_panel.prop_update = right_panel_widget.syncedFromLeft
        if getattr(right_panel_widget, "current_prop", None): 
            left_panel.setValueFromProp(right_panel_widget.current_prop)
            
    main_window.lastForm = left_panel
    return left_panel

def draw_prop_studio_right_column(main_window, right_box_layout):
    """Natively called during drawRightPanel execution loops inside MakeHuman 2."""
    main_window.rightColumn.setTitle("Prop Inventory Studio Matrix")
    right_panel_widget = getattr(main_window, "prop_manager", None)
    if right_panel_widget:
        right_box_layout.addWidget(right_panel_widget)
        right_panel_widget.show()
        
        from gui.tablewindow import MHQTableView
        prop_table = MHQTableView(main_window, "props")
        prop_table.addModel(right_panel_widget.refreshProps, ["Name", "Status", "Action"])
        right_box_layout.addWidget(prop_table)
        
        def process_matrix_row_click(model_index):
            if not model_index.isValid():
                return
            clicked_row = model_index.row()
            name_cell = prop_table.table.model().index(clicked_row, 0)
            asset_string_name = prop_table.table.model().data(name_cell)
            if asset_string_name and right_panel_widget:
                # Maps clean lowercase identifiers to update active focus states safely
                right_panel_widget.update_selection_focus_by_name(str(asset_string_name).lower().strip())
                
        if hasattr(prop_table, 'table') and prop_table.table:
            prop_table.table.clicked.connect(process_matrix_row_click)
            
    return True


__all__ = [
    "initialize_prop_studio", 
    "PropManagerPanel", 
    "PropManLeftPanel",
    "draw_prop_studio_left_column",
    "draw_prop_studio_right_column"
]

