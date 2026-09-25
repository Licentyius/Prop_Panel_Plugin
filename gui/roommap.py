####
## Room Map v2.2a (Decoupled Drag & Drop Enabled Edition)
## Part of the MakeHuman 2 Project contributed by Elvaerwyn_MH2 2026
####

from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter, QPen, QColor, QBrush, QFont
from PySide6.QtCore import Qt, QSize, Signal
import numpy as np

class MHRoomLayoutMap(QWidget):
    coordinatesChanged = Signal(float, float)
    roomResized = Signal(float, float)
    roomResizeFinalized = Signal(float, float)

    def __init__(self, parent=None, is_boundary_planner=False):
        super().__init__(None)
        self.is_boundary_planner = is_boundary_planner
        self.parent_obj = None # Back-reference to panel for current selection highlight
        
        # Enable dropping capabilities on this widget window surface
        self.setAcceptDrops(True)
        
        if parent:
            self.parent_panel_widget = parent
            self.glob = getattr(parent, 'glob', None)
            if self.glob is None and hasattr(parent, 'parent') and parent.parent:
                self.glob = getattr(parent.parent, 'glob', None)
        else:
            self.glob = None
            self.parent_panel_widget = None
            
        self.setMinimumSize(QSize(360, 360))
        self.setMaximumSize(QSize(360, 360))
        
        self.prop_x = 0.0
        self.prop_z = 0.0
        self.room_width = 8.0
        self.room_length = 8.0
        self.active_drag_mode = "NONE"
        self.is_dragging = False
    # ==============================
    # DRAG ENTER HOVER INTERCEPTORS
    # ==============================
    def dragEnterEvent(self, event):
        """May Go Away Forces the map canvas to welcome the incoming payload, instantly changing the red line circle into a drop cursor!"""
        event.acceptProposedAction()

    def dragMoveEvent(self, event):
        """Maintains active acceptance as the mouse slides over the grid coordinates."""
        event.acceptProposedAction()
    # ========================================
    # DYNAMIC DROP POSITION CALCULATION(Mock)
    # ========================================
    def dropEvent(self, event):
        """Builds a complete physical asset mock payload on drop, automatically routing to add_prop_to_scene natively!"""
        event.acceptProposedAction()
        
        raw_text_payload = ""
        mime = event.mimeData()
        if mime.hasText():
            raw_text_payload = mime.text().strip()
        else:
            raw_text_payload = event.source().currentItem().text().strip()

        if not raw_text_payload:
            return

        if "| State:" in raw_text_payload:
            prop_id_key = raw_text_payload.split("|")[0].replace("[O]", "").strip().lower()
        else:
            prop_id_key = raw_text_payload.replace("[O]", "").strip().lower()

        # If it's a raw file path string, isolate the base name
        import os
        if "/" in prop_id_key or "\\" in prop_id_key:
            base_filename = prop_id_key.replace("\\", "/").split("/")[-1]
            prop_id_key, _ = os.path.splitext(base_filename)
            prop_id_key = prop_id_key.strip().lower()

        # THE TRANSLATION MATRIX VALVE: Map pixel hits back to 3D center meters!
        w = self.width()
        h = self.height()
        center_x = w / 2.0
        center_y = h / 2.0

        mouse_pixel_pos = event.position()
        pixel_x = mouse_pixel_pos.x()
        pixel_y = mouse_pixel_pos.y()

        scale_limit = 100.0 if self.is_boundary_planner else max(1.0, self.room_width)
        z_scale_limit = 100.0 if self.is_boundary_planner else max(1.0, self.room_length)

        scale_x = (w - 40) / scale_limit
        scale_y = (h - 40) / z_scale_limit

        world_x = (pixel_x - center_x) / scale_x
        world_z = (pixel_y - center_y) / scale_y

        final_world_x = round(world_x * 2.0) / 2.0
        final_world_z = round(world_z * 2.0) / 2.0

        half_w = self.room_width / 2.0
        half_l = self.room_length / 2.0
        final_world_x = max(-half_w, min(half_w, final_world_x))
        final_world_z = max(-half_l, min(half_l, final_world_z))

        print(f"[Grid Drop Zone] Deploying asset '{prop_id_key}' natively onto grid pos: X={final_world_x:.2f}, Z={final_world_z:.2f}")

        # THE DIRECT SYSTEM MANAGER FETCH:
        import sys
        target_panel = getattr(sys, 'active_prop_studio_panel_address', None)
        
        # Fallback to verify cross-links if the left panel container was stored
        manager_panel = None
        if target_panel:
            if target_panel.__class__.__name__ == "PropManagerPanel":
                manager_panel = target_panel
            else:
                manager_panel = getattr(target_panel, 'propman', None)

        if manager_panel and hasattr(manager_panel, 'add_prop_to_scene'):
            # Discover file pathways dynamically matching the asset browser's exact scanner
            if hasattr(self, 'glob') and self.glob:
                env = self.glob.env
            else:
                from core.globenv import glob as mh2_glob
                env = mh2_glob.env

            addon_props_dir = os.path.join(env.stdSysPath(), "props").replace("\\", "/")
            user_props_dir = os.path.normpath(os.path.join(env.stdUserPath(), "props")).replace("\\", "/")
            
            file_target = ""
            thumb_target = ""
            for folder in [addon_props_dir, user_props_dir]:
                if os.path.isdir(folder):
                    for filename in os.listdir(folder):
                        base, ext = os.path.splitext(filename)
                        if base.lower() == prop_id_key and ext.lower() in ['.obj', '.glb']:
                            file_target = os.path.join(folder, filename).replace("\\", "/")
                            thumb_target = os.path.join(folder, f"{base}.thumb").replace("\\", "/")
                            break
                if file_target:
                    break

            if not file_target:
                # Absolute fallback route layout if loose file isn't matching folder lists
                file_target = os.path.normpath(os.path.join(user_props_dir, f"{prop_id_key}.obj")).replace("\\", "/")
                thumb_target = os.path.normpath(os.path.join(user_props_dir, f"{prop_id_key}.thumb")).replace("\\", "/")

            # Assemble the identical data layout block structure required by add_prop_to_scene
            from types import SimpleNamespace
            mock_asset = SimpleNamespace(
                name=prop_id_key.replace("_", " ").title(),
                path=file_target,
                filename=file_target,
                folder="props",
                uuid=prop_id_key,
                subfolder=None,
                thumbfile=thumb_target,
                author="User",
                tag=["user", prop_id_key]
            )

            # Fire the active pipeline spawner!
            manager_panel.add_prop_to_scene(mock_asset)
            
            # Stamp coordinate positions and repaint the canvas fields instantly
            active_prop = getattr(manager_panel, 'current_prop', None)
            if active_prop:
                active_prop.position = np.array([final_world_x, 0.814, final_world_z], dtype=np.float64)
                if hasattr(manager_panel, 'update_prop'):
                    manager_panel.update_prop()
                if hasattr(manager_panel, 'setValueFromProp'):
                    manager_panel.setValueFromProp(active_prop)

            event.acceptProposedAction()
        else:
            print("[Grid Drop Error] Core application interface pipeline spawner could not be tracked.")
            event.ignore()

        self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            if self.is_boundary_planner and self.active_drag_mode in ["WALL_WIDTH", "WALL_LENGTH"]:
                print(f"[UI MOUSE RELEASE] Finalizing room limits to: {self.room_width:.2f}m x {self.room_length:.2f}m")
                self.roomResizeFinalized.emit(self.room_width, self.room_length)
                
            self.is_dragging = False
            self.active_drag_mode = "NONE"

    def set_prop_coordinates(self, x, z):
        """Updates the visual prop indicator dot marker coordinate maps."""
        try:
            self.prop_x = float(x)
            self.prop_z = float(z)
            self.update()
        except (TypeError, ValueError):
            pass

    def set_room_dimensions(self, w, l):
        """Attention Needed. Updates the architectural floor plan wall sizes dynamically."""
        self.room_width = max(1.0, min(30.0, float(w)))
        self.room_length = max(1.0, min(30.0, float(l)))
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        try:
            w = self.width()
            h = self.height()
            center_x = w / 2.0
            center_y = h / 2.0
            
            if hasattr(self, 'glob') and self.glob:
                bc = getattr(self.glob, 'baseClass', None)
                if bc and hasattr(bc, 'scene') and bc.scene and hasattr(bc.scene, 'floorsize'):
                    f_size = bc.scene.floorsize
                    if isinstance(f_size, (list, tuple, np.ndarray)) and len(f_size) >= 3:
                        self.room_width = float(f_size[0])
                        self.room_length = float(f_size[2])
                    elif isinstance(f_size, (int, float)):
                        self.room_width = float(f_size)
                        self.room_length = float(f_size)

            self.room_width = max(1.0, min(100.0, self.room_width))
            self.room_length = max(1.0, min(100.0, self.room_length))

            # DYNAMIC FOOTPRINT CALCULATIONS:
            scale_x = (w - 40) / self.room_width
            scale_y = (h - 40) / self.room_length

            if self.is_boundary_planner:
                painter.setBrush(QBrush(QColor("#0b1d3a"))) 
                painter.setPen(QPen(QColor("#1e3a8a"), 2))
                painter.drawRect(0, 0, w - 1, h - 1)

                grid_pen = QPen(QColor("#172554"), 1, Qt.SolidLine)
                painter.setPen(grid_pen)
                for i in range(1, 20):
                    painter.drawLine(int((w / 20) * i), 0, int((w / 20) * i), h)
                    painter.drawLine(0, int((h / 20) * i), w, int((h / 20) * i))

                box_pixel_w = self.room_width * scale_x
                box_pixel_h = self.room_length * scale_y

                x0 = int(center_x - (box_pixel_w / 2.0))
                y0 = int(center_y - (box_pixel_h / 2.0))
                x1 = int(center_x + (box_pixel_w / 2.0))
                y1 = int(center_y + (box_pixel_h / 2.0))

                wall_thick = 6
                painter.setBrush(QBrush(QColor("#0f284f")))
                painter.setPen(QPen(QColor("#38bdf8"), 1.5, Qt.SolidLine))
                painter.drawRect(x0, y0, int(box_pixel_w), int(box_pixel_h))
                painter.drawRect(x0 + wall_thick, y0 + wall_thick, int(box_pixel_w) - (wall_thick * 2), int(box_pixel_h) - (wall_thick * 2))

                painter.setPen(QPen(QColor("#f97316"), 3, Qt.SolidLine))
                painter.drawLine(x1, y0, x1, y1) 
                painter.drawLine(x0, y1, x1, y1) 

                painter.setPen(QPen(QColor("#7dd3fc"), 1))
                painter.setFont(QFont("Consolas", 8))
                painter.drawText(int(center_x) - 20, y1 + 23, f"W: {self.room_width:.2f}m")
                painter.drawText(x1 + 15, int(center_y) + 4, f"L: {self.room_length:.2f}m")

                custom_props = getattr(self.glob, 'custom_props_list', [])
                selected_prop = getattr(self.parent_obj, 'current_prop', None) if self.parent_obj else None

                for prop in custom_props:
                    if not prop or getattr(prop, 'visible', True) is False:
                        continue

                    p_pos = prop.position
                    px = float(p_pos[0]) if hasattr(p_pos, '__getitem__') and len(p_pos) > 0 else 0.0
                    pz = float(p_pos[2]) if hasattr(p_pos, '__getitem__') and len(p_pos) > 2 else 0.0

                    obj_px_x = center_x + (px * scale_x)
                    obj_px_z = center_y + (pz * scale_y)

                    p_scl = getattr(prop, 'scale', [1.0, 1.0, 1.0])
                    s_x = float(p_scl[0]) if hasattr(p_scl, '__getitem__') and len(p_scl) > 0 else 1.0
                    s_z = float(p_scl[2]) if hasattr(p_scl, '__getitem__') and len(p_scl) > 2 else 1.0

                    shape_w = max(16.0, s_x * scale_x)
                    shape_h = max(16.0, s_z * scale_y)

                    if prop == selected_prop:
                        shape_pen = QPen(QColor("#f97316"), 2, Qt.SolidLine)
                        shape_brush = QBrush(QColor(249, 115, 22, 60))
                    else:
                        shape_pen = QPen(QColor("#38bdf8"), 1.2, Qt.SolidLine)
                        shape_brush = QBrush(QColor(56, 189, 248, 20))

                    painter.setPen(shape_pen)
                    painter.setBrush(shape_brush)

                    prop_name_lower = prop.name.lower() if hasattr(prop, 'name') else "prop"
                    painter.save()
                    painter.translate(obj_px_x, obj_px_z)
                    
                    p_rot = getattr(prop, 'rotation', [0.0, 0.0, 0.0])
                    ry = float(p_rot[1]) if hasattr(p_rot, '__getitem__') and len(p_rot) > 1 else 0.0
                    painter.rotate(-ry) 

                    t_x0 = int(-shape_w / 2.0)
                    t_z0 = int(-shape_h / 2.0)

                    # THE GEOMETRIC FOOTPRINT ENGINE: Evaluates name strings to map footprint blueprints!
                    if "chair" in prop_name_lower or "seat" in prop_name_lower or "stool" in prop_name_lower:
                        painter.drawEllipse(t_x0, t_z0, int(shape_w), int(shape_h))
                        painter.setBrush(Qt.NoBrush)
                        painter.drawEllipse(int(t_x0 + shape_w*0.12), int(t_z0 + shape_h*0.12), int(shape_w * 0.76), int(shape_h * 0.76))
                    elif "bed" in prop_name_lower:
                        painter.drawRect(t_x0, t_z0, int(shape_w), int(shape_h))
                        painter.drawRect(t_x0, t_z0, int(shape_w), max(4, int(shape_h * 0.15)))
                    elif "sofa" in prop_name_lower or "couch" in prop_name_lower:
                        painter.drawRect(t_x0, t_z0, int(shape_w), int(shape_h))
                        painter.drawLine(t_x0, int(t_z0 + shape_h*0.22), int(t_x0 + shape_w), int(t_z0 + shape_h*0.22))
                    elif "ball" in prop_name_lower or "sphere" in prop_name_lower or "bubble" in prop_name_lower:
                        painter.drawEllipse(t_x0, t_z0, int(shape_w), int(shape_h))
                    elif "cone" in prop_name_lower or "triangle" in prop_name_lower:
                        from PySide6.QtGui import QPolygonF
                        from PySide6.QtCore import QPointF
                        tri_points = QPolygonF([
                            QPointF(0.0, t_z0),
                            QPointF(t_x0 + shape_w, t_z0 + shape_h),
                            QPointF(t_x0, t_z0 + shape_h)
                        ])
                        painter.drawPolygon(tri_points)
                    else:
                        # Baseline fallback bounding rectangle blueprint for boxes or general assets
                        painter.drawRect(t_x0, t_z0, int(shape_w), int(shape_h))
                        painter.drawLine(t_x0, t_z0, int(t_x0 + shape_w), int(t_z0 + shape_h))

                    arrow_pen = QPen(QColor("#f97316"), 2, Qt.SolidLine)
                    painter.setPen(arrow_pen)
                    painter.drawLine(0, 0, 0, int(-shape_h * 0.75))
                    painter.drawLine(0, int(-shape_h * 0.75), -4, int(-shape_h * 0.55))
                    painter.drawLine(0, int(-shape_h * 0.75), 4, int(-shape_h * 0.55))
                    painter.restore()

                    painter.setPen(QPen(QColor("#64748b"), 1))
                    painter.setFont(QFont("Arial", 7))
                    painter.drawText(int(obj_px_x + (shape_w/2) + 5), int(obj_px_z + 4), prop_name_lower)

            else:
                # MAP WIDGET 2: NORMAL SELECTION COORDINATE RE-SCALE PATH
                painter.setBrush(QBrush(QColor("#18181b"))) 
                painter.setPen(QPen(QColor("#3f3f46"), 2))
                painter.drawRect(0, 0, w - 1, h - 1)

                grid_pen = QPen(QColor("#27272a"), 1)
                painter.setPen(grid_pen)
                for i in range(1, 10):
                    painter.drawLine(int((w / 10) * i), 0, int((w / 10) * i), h)
                    painter.drawLine(0, int((h / 10) * i), w, int((h / 10) * i))

                axis_pen = QPen(QColor("#52525b"), 1, Qt.DashLine)
                painter.setPen(axis_pen)
                painter.drawLine(int(center_x), 0, int(center_x), h)
                painter.drawLine(0, int(center_y), w, int(center_y))

                painter.setBrush(Qt.NoBrush)
                painter.setPen(QPen(QColor("#a1a1aa"), 1, Qt.DotLine))
                painter.drawEllipse(int(center_x - w/2 + 20), int(center_y - h/2 + 20), w - 40, h - 40)

                painter.setBrush(QBrush(QColor("#3b82f6")))
                painter.setPen(QPen(QColor("#ffffff"), 1.5))
                painter.drawEllipse(int(center_x) - 5, int(center_y) - 5, 10, 10)
                painter.setPen(QPen(QColor("#ffffff"), 2))
                painter.drawLine(int(center_x), int(center_y) - 5, int(center_x), int(center_y) - 12)

                dot_x = center_x + (self.prop_x * scale_x)
                dot_z = center_y + (self.prop_z * scale_y)
                painter.setBrush(QBrush(QColor("#f97316"))) 
                painter.setPen(QPen(QColor("#ffffff"), 2))
                painter.drawEllipse(int(dot_x) - 8, int(dot_z) - 8, 16, 16)

                painter.setPen(QColor("#a1a1aa"))
                painter.setFont(QFont("Arial", 8))
                painter.drawText(12, h - 12, f"X: {self.prop_x:.2f} | Z: {self.prop_z:.2f}")

        except Exception as e:
            print(f"[MAP ENGINE EXCEPTION] Draw error loop: {e}")
        finally:
            painter.end()

    def mousePressEvent(self, event):
        if event.button() != Qt.LeftButton:
            return
            
        self.is_dragging = True
        pos = event.position()
        
        if not self.is_boundary_planner:
            self.active_drag_mode = "PROP"
            self.process_unified_drag(pos)
            return

        w = self.width()
        h = self.height()
        center_x = w / 2
        center_y = h / 2
        
        max_floor_dimension = 10.0
        if self.glob and getattr(self.glob, 'baseClass', None):
            bc = self.glob.baseClass
            if hasattr(bc, 'scene') and bc.scene and hasattr(bc.scene, 'floorsize'):
                floor_list = bc.scene.floorsize
                if isinstance(floor_list, (list, tuple, np.ndarray)) and len(floor_list) > 0:
                    max_floor_dimension = float(floor_list[0])
        max_floor_dimension = max(1.0, max_floor_dimension)

        scale_x = (w - 40) / max_floor_dimension
        scale_y = (h - 40) / max_floor_dimension

        x1_pixel = center_x + (self.room_width * scale_x / 2.0)
        y1_pixel = center_y + (self.room_length * scale_y / 2.0)

        if abs(pos.x() - x1_pixel) < 15:
            self.active_drag_mode = "WALL_WIDTH"
        elif abs(pos.y() - y1_pixel) < 15:
            self.active_drag_mode = "WALL_LENGTH"
        else:
            self.active_drag_mode = "PROP"
            
        self.process_unified_drag(pos)

    def mouseMoveEvent(self, event):
        if self.is_dragging:
            self.process_unified_drag(event.position())

    def process_unified_drag(self, pos):
        w = self.width()
        h = self.height()
        center_x = w / 2.0
        center_y = h / 2.0
        
        # Pull live structural dimensions from the core character canvas scene setup
        if self.glob:
            bc = getattr(self.glob, 'baseClass', None)
            if bc and hasattr(bc, 'scene') and bc.scene and hasattr(bc.scene, 'floorsize'):
                f_size = bc.scene.floorsize
                if isinstance(f_size, (list, tuple, np.ndarray)) and len(f_size) >= 3:
                    self.room_width = float(f_size[0])
                    self.room_length = float(f_size[2])
                elif isinstance(f_size, (int, float)):
                    self.room_width = float(f_size)
                    self.room_length = float(f_size)

        self.room_width = max(1.0, min(50.0, self.room_width))
        self.room_length = max(1.0, min(50.0, self.room_length))

        # RE-LINK THE BOUNDARY MATRIX: Use the real room dimensions to scale map selections!
        scale_limit = 50.0 if self.is_boundary_planner else self.room_width
        z_scale_limit = 50.0 if self.is_boundary_planner else self.room_length

        scale_x = (w - 40) / scale_limit
        scale_y = (h - 40) / z_scale_limit

        world_x = (pos.x() - center_x) / scale_x
        world_z = (pos.y() - center_y) / scale_y

        if self.is_boundary_planner:
            x1_pixel = center_x + (self.room_width * scale_x / 2.0)
            y1_pixel = center_y + (self.room_length * scale_y / 2.0)
            
            if abs(pos.x() - x1_pixel) < 15 and self.active_drag_mode == "NONE": 
                self.active_drag_mode = "WALL_WIDTH"
            elif abs(pos.y() - y1_pixel) < 15 and self.active_drag_mode == "NONE": 
                self.active_drag_mode = "WALL_LENGTH"
            elif self.active_drag_mode == "NONE": 
                self.active_drag_mode = "PROP"
        else:
            self.active_drag_mode = "PROP"

        if self.active_drag_mode == "WALL_WIDTH":
            computed_w = abs(world_x) * 2.0
            self.room_width = max(1.0, min(50.0, round(computed_w * 2.0) / 2.0))
            self.roomResized.emit(self.room_width, self.room_length)
            
            if self.glob and getattr(self.glob, 'baseClass', None):
                bc = self.glob.baseClass
                if bc and hasattr(bc, 'scene') and bc.scene and hasattr(bc.scene, 'floorsize'):
                    if isinstance(bc.scene.floorsize, list):
                        bc.scene.floorsize[0] = self.room_width  
                        bc.scene.floorsize[2] = self.room_length 
                    else:
                        bc.scene.floorsize = [self.room_width, 0.2, self.room_length]
                        
                    self.glob.last_cached_room_w = self.room_width
                    
                    if "floorcuboid" in bc.scene.prims and hasattr(bc.scene.prims["floorcuboid"], 'newSize'):
                        bc.scene.prims["floorcuboid"].newSize(bc.scene.floorsize)
                        if hasattr(bc.scene.prims["floorcuboid"], 'build'): 
                            bc.scene.prims["floorcuboid"].build()
                    bc.scene.update()
            
        elif self.active_drag_mode == "WALL_LENGTH":
            computed_l = abs(world_z) * 2.0
            self.room_length = max(1.0, min(50.0, round(computed_l * 2.0) / 2.0))
            self.roomResized.emit(self.room_width, self.room_length)
            
            if self.glob and getattr(self.glob, 'baseClass', None):
                bc = self.glob.baseClass
                if bc and hasattr(bc, 'scene') and bc.scene and hasattr(bc.scene, 'floorsize'):
                    if isinstance(bc.scene.floorsize, list):
                        bc.scene.floorsize[0] = self.room_width
                        bc.scene.floorsize[2] = self.room_length  
                    else:
                        bc.scene.floorsize = [self.room_width, 0.2, self.room_length]
                        
                    self.glob.last_cached_room_l = self.room_length
                    
                    if "floorcuboid" in bc.scene.prims and hasattr(bc.scene.prims["floorcuboid"], 'newSize'):
                        bc.scene.prims["floorcuboid"].newSize(bc.scene.floorsize)
                        if hasattr(bc.scene.prims["floorcuboid"], 'build'): 
                            bc.scene.prims["floorcuboid"].build()
                    bc.scene.update()
            
        elif self.active_drag_mode == "PROP":
            snapped_prop_x = round(world_x * 2.0) / 2.0
            snapped_prop_z = round(world_z * 2.0) / 2.0
            
            half_w = self.room_width / 2.0
            half_l = self.room_length / 2.0
            self.prop_x = max(-half_w, min(half_w, snapped_prop_x))
            self.prop_z = max(-half_l, min(half_l, snapped_prop_z))
            
            self.coordinatesChanged.emit(self.prop_x, self.prop_z)
            
        self.update()

    def contextMenuEvent(self, event):
        """Spawns a native right-click pop-up menu under the cursor to delete props on the fly!"""
        from PySide6.QtWidgets import QMenu
        from PySide6.QtGui import QAction
        
        # 1. Fetch the active scene props list array out of the engine globals
        custom_props = getattr(self.glob, 'custom_props_list', []) if self.glob else []
        if not custom_props:
            return

        w = self.width()
        h = self.height()
        center_x = w / 2.0
        center_y = h / 2.0
        scale_x = (w - 40) / max(1.0, self.room_width)
        scale_y = (h - 40) / max(1.0, self.room_length)

        # Translate the cursor pixel click point back into absolute world meters
        click_pos = event.pos()
        click_world_x = (click_pos.x() - center_x) / scale_x
        click_world_z = (click_pos.y() - center_y) / scale_y

        clicked_prop = None
        # Attention Needed Here. Find which prop is closest to the mouse cursor (within a 1.2 meter radius threshold)
        for prop in custom_props:
            if not prop: continue
            p_pos = prop.position
            px = float(p_pos[0]) if hasattr(p_pos, '__getitem__') and len(p_pos) > 0 else 0.0
            pz = float(p_pos[2]) if hasattr(p_pos, '__getitem__') and len(p_pos) > 2 else 0.0
            
            distance = np.sqrt((click_world_x - px)**2 + (click_world_z - pz)**2)
            if distance < 1.2:
                clicked_prop = prop
                break

        if clicked_prop:
            # 2. Build the visual popup context menu framework
            menu = QMenu(self)
            menu.setStyleSheet("""
                QMenu { background-color: #27272a; color: white; border: 1px solid #3f3f46; padding: 4px; }
                QMenu::item:selected { background-color: #a13d3d; color: white; }
            """)
            
            remove_action = QAction(f"❌ Remove '{clicked_prop.name}' From Scene", self)
            
            def trigger_destruction():
                print(f"[Context Menu] Purging asset from room buffers: {clicked_prop.name}")
                import sys
                manager_panel = getattr(sys, 'active_prop_studio_panel_address', None)
                if manager_panel:
                    manager_ref = manager_panel if manager_panel.__class__.__name__ == "PropManagerPanel" else getattr(manager_panel, 'propman', None)
                    
                    if manager_ref:
                        # Set selection focus to the targeted item and execute the working remover pipeline!
                        manager_ref.current_prop = clicked_prop
                        manager_ref.remove_current_prop()
                        self.update()

            remove_action.triggered.connect(trigger_destruction)
            menu.addAction(remove_action)
            menu.exec(event.globalPos())
