"""
Viewport_hook for Prop module.
Part of the MakeHuman 2 Project contributed by Elvaerwyn_MH2 2026.
"""

import os
import numpy as np
from PySide6.QtCore import Qt, QSize, QTimer
from PySide6.QtWidgets import QWidget, QMessageBox

def perform_background_hardware_link(glob_reference, main_window, prop_manager_widget):
    """
    Bind the own draw function to  MakeHuman2 openGL draw queue using library function
    registerDrawFunction
    """

    def propDraw(parent, proj_view_matrix, campos):
            
        propman_pipeline = getattr(glob_reference, 'prop_manager_pipeline', None)

        if propman_pipeline:
            propman_pipeline.shaders = parent.mh_shaders
            try:
                active_focus_prop = getattr(prop_manager_widget, 'current_prop', None)
                if active_focus_prop and hasattr(active_focus_prop, 'name') and active_focus_prop.name:
                    if hasattr(prop_manager_widget, 'prop_fsm') and prop_manager_widget.prop_fsm:
                        prop_manager_widget.prop_fsm.update_machine(active_focus_prop.name)

                # called in propmanager
                propman_pipeline.drawProps(proj_view_matrix, campos, parent.light)
                propman_pipeline.drawProps(proj_view_matrix, campos, parent.light)  # TODO should not be called twice later

            except Exception as render_err:
                print(f"[Prop Studio Debug] Scene queue execution crash: {render_err}")

    glob_reference.registerDrawFunction("prop_panel", propDraw, 2)

    print("[Prop Studio Core] draw function registered to MakeHuman2 openGL draw queue (PostDraw)!")

    # =========================================================================
    # DYNAMIC EXPORTER BAR INTERFACE INJECTION
    # =========================================================================
    try:
        export_view = None
        if hasattr(main_window, 'views') and "export" in main_window.views:
            export_view = main_window.views["export"]
        elif hasattr(main_window, 'category_views') and "export" in main_window.category_views:
            export_view = main_window.category_views["export"]

        if export_view:
            right_panel = None
            if hasattr(export_view, 'rightPanel'):
                right_panel = export_view.rightPanel
            else:
                for child in export_view.findChildren(QWidget):
                    if child.__class__.__name__ == "ExportRightPanel" or hasattr(child, "exportimages"):
                        right_panel = child
                        break

            if right_panel and not hasattr(right_panel, "_prop_studio_button_injected"):
                from gui.common import IconButton
                
                sys_icon_dir = getattr(glob_reference.env, 'path_sysicon', '') if glob_reference.env else ''
                if sys_icon_dir:
                    icon_path = os.path.normpath(os.path.join(sys_icon_dir, "wavefront_sym.png")).replace("\\", "/")
                else:
                    icon_path = ""
                    
                tip_text = "<b>Export Custom Prop Scene Layout</b><br>Bakes all loaded studio shapes and bone offsets into a combined file layout."
                
                scene_export_btn = IconButton(
                    num=len(right_panel.exportimages), 
                    icon=icon_path, 
                    tip=tip_text, 
                    func=None, 
                    width=130, 
                    checkable=True
                )
                
                def execute_addon_scene_export_pipeline():
                    for item in right_panel.exportimages:
                        if item["button"]: 
                            item["button"].setChecked(False)
                    scene_export_btn.setChecked(True)
                    
                    try:
                        from . import export_scene
                        print("[Prop Studio Exporter] Root path discovery success: export_scene loaded.")

                        export_dir = None
                        if glob_reference.env and hasattr(glob_reference.env, 'stdUserPath'):
                            try:
                                export_dir = glob_reference.env.stdUserPath("exports")
                            except Exception:
                                export_dir = None
                                
                        if not export_dir:
                            export_dir = os.path.abspath(os.path.join(os.getcwd(), "saved_scenes"))
                            
                        if not os.path.exists(export_dir):
                            os.makedirs(export_dir, exist_ok=True)
                            
                        target_file = os.path.normpath(os.path.join(export_dir, "studio_combined_scene.obj")).replace("\\", "/")
                        
                        bc_instance = getattr(glob_reference, 'baseClass', None)
                        skel_ref = getattr(bc_instance, 'skeleton', getattr(bc_instance, 'pose_skeleton', None)) if bc_instance else None
                        active_props = getattr(glob_reference, 'custom_props_list', [])
                        
                        print(f"[Prop Studio Exporter] Dispatching master scene graph to format channel: OBJ...")
                        success, msg = export_scene.export_props_scene(target_file, "obj", active_props, skel_ref)
                        
                        if success:
                            QMessageBox.information(right_panel.parent(), "Export Complete!", f"Successfully exported scene:\n{msg}")
                        else:
                            print(f"[Prop Studio Exporter Error] {msg}")
                            
                    except Exception as export_err:
                        print(f"[Prop Studio Exporter Crash] Failed to run file generations: {export_err}")

                scene_export_btn.clicked.connect(execute_addon_scene_export_pipeline)
                
                new_entry = {
                    "button": scene_export_btn, 
                    "icon": "wavefront_sym.png", 
                    "tip": tip_text, 
                    "func": execute_addon_scene_export_pipeline
                }
                right_panel.exportimages.append(new_entry)
                
                if hasattr(right_panel.layout(), "insertWidget"):
                    right_panel.layout().insertWidget(right_panel.layout().count() - 1, scene_export_btn)
                else:
                    right_panel.layout().addWidget(scene_export_btn)
                    
                right_panel._prop_studio_button_injected = True
                print("[Prop Studio Core] Dynamic 'Export Scene' button successfully injected onto the main Export screen!")

    except Exception as inject_err:
        print(f"[Prop Studio Warning] Dynamic exporter bar injection bypassed: {inject_err}")
