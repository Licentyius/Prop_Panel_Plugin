####
## Room Map v2.0 
## Part of the MakeHuman 2 Project contributed by Elvaerwyn_MH2 2026
####

from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter, QPen, QColor, QBrush, QFont
from PySide6.QtCore import Qt, QSize, Signal
import numpy as np

class MHRoomLayoutMap(QWidget):
    coordinatesChanged = Signal(float, float)
    roomResized = Signal(float, float)
    
    # Signal fired ONLY when the user lets go of the mouse button to prevent thread overload cascades
    roomResizeFinalized = Signal(float, float)

    def __init__(self, parent=None, is_boundary_planner=False):
        super().__init__(None)
        self.is_boundary_planner = is_boundary_planner
        self.parent_obj = None # Back-reference to panel for current selection highlight
        
        # Explicitly configure robust back-trace safety pathways to tap into the parent state tree references
        if parent:
            self.glob = getattr(parent, 'glob', None)
            if self.glob is None and hasattr(parent, 'parent') and parent.parent:
                self.glob = getattr(parent.parent, 'glob', None)
        else:
            self.glob = None
            
        # --- ENHANCED REAL ESTATE: Expanded layout footprint sizing boundaries ---
        self.setMinimumSize(QSize(360, 360))
        self.setMaximumSize(QSize(360, 360))
        
        self.prop_x = 0.0
        self.prop_z = 0.0
        self.room_width = 8.0
        self.room_length = 8.0
        self.active_drag_mode = "NONE"
        self.is_dragging = False

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
        """Updates the architectural floor plan wall sizes dynamically."""
        self.room_width = max(1.0, min(30.0, float(w)))
        self.room_length = max(1.0, min(30.0, float(l)))
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        try:
            w = self.width()
            h = self.height()
            center_x = w / 2
            center_y = h / 2
            
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
                    else:
                        painter.drawRect(t_x0, t_z0, int(shape_w), int(shape_h))
                        painter.drawLine(t_x0, t_z0, int(t_x0 + shape_w), int(t_z0 + shape_h))

                    arrow_pen = QPen(QColor("#f97316"), 2, Qt.SolidLine)
                    painter.setPen(arrow_pen)
                    painter.drawLine(0, 0, 0, int(-shape_h * 0.75))
                    painter.drawLine(0, int(-shape_h * 0.75), -4, int(-shape_h * 0.55))
                    painter.drawLine(0, int(-shape_h * 0.75), 4, int(-shape_h * 0.55))
                    painter.restore()

                    # Draw the asset name text label right next to the bounding shape box
                    painter.setPen(QPen(QColor("#64748b"), 1))
                    painter.setFont(QFont("Arial", 7))
                    painter.drawText(int(obj_px_x + (shape_w/2) + 5), int(obj_px_z + 4), prop_name_lower)

            else:
                # MAP WIDGET 2: RESTORED DARK SLATE COORDINATE COORD TRACKER OVERLAY
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
        center_x = w / 2
        center_y = h / 2
        max_staging_limit = 100.0
        
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

        self.room_width = max(1.0, min(max_staging_limit, self.room_width))
        self.room_length = max(1.0, min(max_staging_limit, self.room_length))

        scale_x = (w - 40) / max_staging_limit
        scale_y = (h - 40) / max_staging_limit

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
            self.room_width = max(1.0, min(max_staging_limit, round(computed_w * 2.0) / 2.0))
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
            self.room_length = max(1.0, min(max_staging_limit, round(computed_l * 2.0) / 2.0))
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
            local_scale_x = (w - 40) / self.room_width
            local_scale_y = (h - 40) / self.room_length

            true_world_x = (pos.x() - center_x) / local_scale_x
            true_world_z = (pos.y() - center_y) / local_scale_y

            snapped_prop_x = round(true_world_x * 2.0) / 2.0
            snapped_prop_z = round(true_world_z * 2.0) / 2.0
            
            half_w = self.room_width / 2.0
            half_l = self.room_length / 2.0
            self.prop_x = max(-half_w, min(half_w, snapped_prop_x))
            self.prop_z = max(-half_l, min(half_l, snapped_prop_z))
            
            self.coordinatesChanged.emit(self.prop_x, self.prop_z)
            
        self.update()


