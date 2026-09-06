######
#
# Emitter Widget  V1.0 by Elvaerwyn MH_2 2026
# For use in the prop panel plugin for Makehuman 2
#
######

import time
from PyQt5 import QtWidgets, QtCore
from core import app_instance  # Assuming this is your MH2 instance global
from .emitter_logic import MH2EmitterObject # Isolated engine math file

class MH2EmitterWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.active_emitter = None
        self.last_tick = time.time()
        
        # Build independent UI panel controls
        self.setup_ui()
        
        # High-frequency timer for processing particle physics loops (~60fps)
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.update_emitter_frame)
        self.timer.start(16)

    def setup_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        
        # Unique Emitter Header
        self.header = QtWidgets.QLabel("<b>MH2 Emitter Prop Controls</b>")
        layout.addWidget(self.header)
        
        # State control combo box - isolated from normal prop states
        self.state_menu = QtWidgets.QComboBox()
        self.state_menu.addItems(["holding", "placed", "arranged(locked)", "used"])
        self.state_menu.currentTextChanged.connect(self.on_state_changed)
        layout.addWidget(self.state_menu)
        
        # Spawning button specifically targeting procedural systems
        self.spawn_btn = QtWidgets.QPushButton("Spawn Emitter Type Prop")
        self.spawn_btn.clicked.connect(self.instantiate_emitter)
        layout.addWidget(self.spawn_btn)

    def instantiate_emitter(self):
        # Spawns a dedicated emitter object instead of calling your normal prop spawning logic
        self.active_emitter = MH2EmitterObject(name="FX_Flame_Prop", bone="hand_R")
        self.state_menu.setCurrentText("holding")

    def on_state_changed(self, text):
        if self.active_emitter:
            # Strip formatting to send pure state string matching your workflow tracker
            clean_state = text.split("(")[0].strip()
            self.active_emitter.set_state(clean_state)

    def update_emitter_frame(self):
        if not self.active_emitter:
            return
            
        current_time = time.time()
        dt = current_time - self.last_tick
        self.last_tick = current_time
        
        # Fetch underlying skeletal bones context from your core module
        skeleton = app_instance.get_viewport_skeleton() 
        
        # Process the computational step loops
        self.active_emitter.process_ticks(dt, skeleton)
        
        # Command the OpenGL viewport pipeline to redraw calculations
        app_instance.viewport.refresh()

            
        current_time = time.time()
        dt = current_time - self.last_tick
        self.last_tick = current_time
        
        # Fetch underlying skeletal bones context from your core module
        skeleton = app_instance.get_viewport_skeleton() 
        
        # Process the computational step loops
        self.active_emitter.process_ticks(dt, skeleton)
        
        # Command the OpenGL viewport pipeline to redraw calculations
        app_instance.viewport.refresh()
