######
## Prop State 
## Part of the MakeHuman 2 Project contributed by Elvaerwyn_MH2 2026 V1.4
######

import numpy as np

class PropState:
    """Base class for prop pipeline state tracking."""
    def __init__(self, machine):
        self.machine = machine

    def enter(self, prop_name): pass
    def update(self, prop_name): pass
    def exit(self, prop_name): pass

class StateIdle(PropState):
    def enter(self, prop_name):
        print(f"[STATE] {prop_name} entered IDLE.")
        prop = self.machine.panel_ref.find_prop_by_name(prop_name)
        if prop:
            prop.visible = True  
            prop.use_parenting = False
            prop.parent_bone = "None"

class StateEquipping(PropState):
    def enter(self, prop_name):
        print(f"[STATE] Synchronizing parenting channels for: {prop_name}")
        manager_panel = self.machine.panel_ref
        prop = manager_panel.find_prop_by_name(prop_name)
        
        if prop:
            if hasattr(manager_panel, 'parent_toggle'):
                manager_panel.parent_toggle.setChecked(True)
            if hasattr(manager_panel, 'bone_selector'):
                manager_panel.bone_selector.setCurrentText("hand_R")
            elif hasattr(manager_panel, 'leftPanel') and manager_panel.leftPanel:
                lp = manager_panel.leftPanel
                if hasattr(lp, 'parent_toggle'): 
                    lp.parent_toggle.setChecked(True)
                if hasattr(lp, 'bone_selector'): 
                    lp.bone_selector.setCurrentText("hand_R")

            prop.use_parenting = True
            prop.parent_bone = "hand_R"
            
            lp_ref = getattr(manager_panel, 'leftPanel', None)
            glob_ref = getattr(manager_panel, 'glob', getattr(lp_ref, 'glob', None))
            base_class = getattr(glob_ref, 'baseClass', None) if glob_ref else None
            
            prop.local_offset_pos = [0.0, 0.0, 0.0]
            
            if base_class and getattr(base_class, 'pose_skeleton', None):
                skel = base_class.pose_skeleton
                if "hand_R" in skel.bones:
                    bone = skel.bones["hand_R"]
                    raw_bone_pos = getattr(bone, 'poseheadPos', getattr(bone, 'headPos', [0.0, 0.0, 0.0]))
                    
                    # Convert to primitive float array index listings to block TypeErrors
                    if hasattr(raw_bone_pos, 'x') and callable(getattr(raw_bone_pos, 'x')):
                        bone_pos = [float(raw_bone_pos.x()), float(raw_bone_pos.y()), float(raw_bone_pos.z())]
                    elif len(raw_bone_pos) >= 3:
                        bone_pos = [float(raw_bone_pos[0]), float(raw_bone_pos[1]), float(raw_bone_pos[2])]
                    else:
                        bone_pos = [0.0, 0.0, 0.0]
                    
                    prop.local_offset_pos = [
                        prop.position[0] - bone_pos[0],
                        prop.position[1] - bone_pos[1],
                        prop.position[2] - bone_pos[2]
                    ]
            
            if prop.local_offset_pos == [0.0, 0.0, 0.0]:
                prop.local_offset_pos = getattr(prop, 'position', [0.0, 0.0, 0.0])

            self.machine.frame_counter = 0

    def update(self, prop_name):
        self.machine.frame_counter += 1
        if self.machine.frame_counter >= 12: 
            self.machine.transition_to(prop_name, "USING")

class StateUsing(PropState):
    def enter(self, prop_name):
        print(f"[STATE] Active action trigger executing on {prop_name}")
        
    def update(self, prop_name):
        pass

class StateUnequipping(PropState):
    """Handles the safe decoupling loop of assets moving back to world space."""
    def enter(self, prop_name):
        print(f"[STATE] Breaking joint links for: {prop_name}")
        manager_panel = self.machine.panel_ref
        prop = manager_panel.find_prop_by_name(prop_name)
        if prop:
            prop.use_parenting = False
            prop.parent_bone = "None"
        self.machine.transition_to(prop_name, "IDLE")

class PropStateMachine:
    def __init__(self, panel_ref):
        self.panel_ref = panel_ref
        self.states = {
            "IDLE": StateIdle(self),
            "EQUIPPING": StateEquipping(self),
            "USING": StateUsing(self),
            "UNEQUIPPING": StateUnequipping(self)
        }
        self.current_state_name = "IDLE"
        self.current_state = self.states["IDLE"]
        self.frame_counter = 0

    def transition_to(self, prop_name, new_state_name):
        if new_state_name in self.states:
            self.current_state.exit(prop_name)
            self.current_state_name = new_state_name
            self.current_state = self.states[new_state_name]
            self.current_state.enter(prop_name)
            
            if hasattr(self.panel_ref, '_trigger_viewport_redraw'):
                self.panel_ref._trigger_viewport_redraw()
            elif hasattr(self.panel_ref, 'leftPanel') and self.panel_ref.leftPanel:
                lp = self.panel_ref.leftPanel
                if hasattr(lp, 'glob') and getattr(lp.glob, 'openGLWindow', None):
                    lp.glob.openGLWindow.update()

    def update_machine(self, prop_name):
        if self.current_state:
            self.current_state.update(prop_name)

    def get_export_matrix(self, prop_name):
        """Returns (parent_bone_name, transformation_matrix) for file writers."""
        prop = self.panel_ref.find_prop_by_name(prop_name)
        if not prop:
            return None, np.eye(4)

        is_attached = self.current_state_name in ["EQUIPPING", "USING", "HYBRID"] and getattr(prop, 'use_parenting', False)
        
        if is_attached:
            bone_name = getattr(prop, 'parent_bone', "hand_R")
            local_m = self._build_matrix(
                getattr(prop, 'local_offset_pos', getattr(prop, 'position', [0.0, 0.0, 0.0])),
                getattr(prop, 'rotation', [0.0, 0.0, 0.0])
            )
            
            lp = getattr(self.panel_ref, 'leftPanel', None)
            glob_ref = getattr(self.panel_ref, 'glob', getattr(lp, 'glob', None))
            base_class = getattr(glob_ref, 'baseClass', None) if glob_ref else None
            
            if base_class and getattr(base_class, 'in_posemode', False) and getattr(base_class, 'pose_skeleton', None):
                skeleton = base_class.pose_skeleton
                if hasattr(skeleton, 'bones') and bone_name in skeleton.bones:
                    target_bone = skeleton.bones[bone_name]
                    if hasattr(target_bone, 'matPoseVerts') and target_bone.matPoseVerts is not None:
                        bone_m = np.eye(4)
                        bone_m[0:3, 0:3] = target_bone.matPoseVerts
                        if hasattr(target_bone, 'poseheadPos'):
                            raw_posehead = target_bone.poseheadPos
                            if hasattr(raw_posehead, 'x') and callable(getattr(raw_posehead, 'x')):
                                bone_m[0:3, 3] = [float(raw_posehead.x()), float(raw_posehead.y()), float(raw_posehead.z())]
                            elif len(raw_posehead) >= 3:
                                bone_m[0:3, 3] = [float(raw_posehead), float(raw_posehead), float(raw_posehead)]
                            
                        return bone_name, bone_m @ local_m

            return bone_name, local_m
        else:
            pos = getattr(prop, 'position', [0.0, 0.0, 0.0])
            rot = getattr(prop, 'rotation', [0.0, 0.0, 0.0])
            return None, self._build_matrix(pos, rot)

    def _build_matrix(self, pos, rot):
        """Computes a structurally clean 4x4 transform layout via NumPy."""
        T = np.eye(4)
        T[0:3, 3] = pos
        rx, ry, rz = np.radians(rot)
        
        Rx = np.array([[1.0, 0.0, 0.0], 
                       [0.0, np.cos(rx), -np.sin(rx)], 
                       [0.0, np.sin(rx), np.cos(rx)]])
                       
        Ry = np.array([[np.cos(ry), 0.0, np.sin(ry)], 
                       [0.0, 1.0, 0.0], 
                       [-np.sin(ry), 0.0, np.cos(ry)]])
                       
        Rz = np.array([[np.cos(rz), -np.sin(rz), 0.0], 
                       [np.sin(rz), np.cos(rz), 0.0], 
                       [0.0, 0.0, 1.0]])
        
        T[0:3, 0:3] = Rz @ Ry @ Rx
        return T
