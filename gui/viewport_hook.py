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
    Decoupled graphics and interface injection engine.
    Safely binds the prop manager pipeline onto the active 3D drawing track.
    """
    center_viewport = getattr(glob_reference, "openGLWindow", None)
    if not center_viewport and hasattr(main_window, 'graph') and main_window.graph:
        center_viewport = getattr(main_window.graph, 'view', None)
    if not center_viewport and hasattr(main_window, 'glWindow'):
        center_viewport = main_window.glWindow

    if center_viewport and hasattr(center_viewport, 'scene') and center_viewport.scene:
        active_scene_instance = center_viewport.scene
        
        if not hasattr(active_scene_instance, "_orig_mh2_scene_draw"):
            active_scene_instance._orig_mh2_scene_draw = active_scene_instance.draw
        
        def decoupled_master_scene_draw(*args, **kwargs):
            active_scene_instance._orig_mh2_scene_draw(*args, **kwargs)
            
            live_glob = getattr(active_scene_instance, 'glob', glob_reference)
            live_pipeline = getattr(live_glob, 'prop_manager_pipeline', None)
            
            if live_pipeline and hasattr(live_glob, 'custom_props_list') and live_glob.custom_props_list:
                try:
                    active_focus_prop = getattr(prop_manager_widget, 'current_prop', None)
                    if active_focus_prop and hasattr(active_focus_prop, 'name') and active_focus_prop.name:
                        if hasattr(prop_manager_widget, 'prop_fsm') and prop_manager_widget.prop_fsm:
                            prop_manager_widget.prop_fsm.update_machine(active_focus_prop.name)

                    proj_view_matrix = args[0] if len(args) > 0 else None
                    campos = args[1] if len(args) > 1 else [0.0, 0.0, 5.0]
                    
                    if hasattr(center_viewport, "shaders") and center_viewport.shaders:
                        live_pipeline.shaders = center_viewport.shaders
                    elif hasattr(center_viewport, "ctx") and hasattr(center_viewport.ctx, "shaders"):
                        live_pipeline.shaders = center_viewport.ctx.shaders

                    active_light_object = None
                    if hasattr(live_glob, 'light') and live_glob.light:
                        active_light_object = live_glob.light
                    elif hasattr(main_window, 'light') and main_window.light:
                        active_light_object = main_window.light
                    elif hasattr(center_viewport, 'light') and center_viewport.light:
                        active_light_object = center_viewport.light
                        
                    if active_light_object is None:
                        from types import SimpleNamespace
                        active_light_object = SimpleNamespace(
                            lightWeight=1.0, 
                            direction=getattr(center_viewport, 'light_direction', [0.0, 1.0, 0.0]),
                            color=[1.0, 1.0, 1.0]
                        )
                    
                    if proj_view_matrix is not None:
                        live_pipeline.drawProps(proj_view_matrix, campos, active_light_object)

                except Exception as render_err:
                    print(f"[Prop Studio Debug] Scene queue execution crash: {render_err}")

        active_scene_instance.draw = decoupled_master_scene_draw
        print("[Prop Studio Core] Successfully bound multi-prop manager onto scene drawing queue!")
        
        if hasattr(center_viewport, "update"): 
            center_viewport.update()
    else:
        print("[Prop Studio Warning] Active 3D Scene object context not found on viewport target.")

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
