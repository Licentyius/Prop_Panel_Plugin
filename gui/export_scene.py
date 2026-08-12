"""
Multi-Format Prop Scene Exporter v1.4.
Part of the MakeHuman 2 Project contributed by Elvaerwyn_MH2 2026.
"""

import numpy as np
import os
import sys
import mh2_official_tools.prop_panel.gui.propstate as propstate

def export_props_scene(filepath, format_type, custom_props_list, skeleton_ref=None):
    """
    Queries live state engine properties to pipe prop spatial layouts
    cleanly into your Collada, glTF, or OBJ output writers.
    """
    export_payload = []

    for prop in custom_props_list:
        if not prop:
            continue
            
        mesh_data = getattr(prop, 'obj', prop)
        vertices_array = getattr(mesh_data, 'gl_coord', [])
        normals_array = getattr(mesh_data, 'gl_norm', [])
        uvs_array = getattr(mesh_data, 'gl_uvcoord', [])       

        raw_path = getattr(prop, 'path', '') or getattr(prop, 'name', 'unknown_asset')
        raw_path = str(raw_path).replace("props_", "", 1)
        
        base_file = os.path.basename(os.path.normpath(raw_path))
        prop_name = os.path.splitext(base_file)[0]
        
        internal_disk_path = f"f:/mh2_assets/plugin_tests/makehuman2/data/props/{prop_name}.obj"
        export_mesh_path = f"data/props/{prop_name}.obj"
        
        prop.path = export_mesh_path
        mesh_path = export_mesh_path

        panel = getattr(prop, 'panel_ref', None)
        if panel and hasattr(panel, 'prop_fsm'):
            bone_parent, matrix = panel.prop_fsm.get_export_matrix(prop_name)
        else:
            bone_parent = prop.parent_bone if getattr(prop, 'use_parenting', False) else "None"
            bone_parent = None if bone_parent == "None" else bone_parent
            
            T = np.eye(4, dtype=np.float64)
            T[0:3, 3] = getattr(prop, 'position', [0.0, 0.0, 0.0])
            
            rot = getattr(prop, 'rotation', [0.0, 0.0, 0.0])
            rx, ry, rz = np.radians(rot)
            
            Rx = np.array([[1.0, 0.0, 0.0], 
                           [0.0, np.cos(rx), -np.sin(rx)], 
                           [0.0, np.sin(rx), np.cos(rx)]], dtype=np.float64)
                           
            Ry = np.array([[np.cos(ry), 0.0, np.sin(ry)],
                           [0.0, 1.0, 0.0], 
                           [-np.sin(ry), 0.0, np.cos(ry)]], dtype=np.float64)
                           
            Rz = np.array([[np.cos(rz), -np.sin(rz), 0.0], 
                           [np.sin(rz), np.cos(rz), 0.0],
                           [0.0, 0.0, 1.0]], dtype=np.float64)
                           
            T[0:3, 0:3] = Rz @ Ry @ Rx
            matrix = T

        payload_entry = {
            "name": prop_name,
            "matrix_transform": matrix,
            "source_mesh_path": export_mesh_path,
            "is_socketed": True if bone_parent else False,
            "parent_bone_node": bone_parent,
            "vertices": vertices_array,
            "normals": normals_array,
            "uvs": uvs_array
        }
        
        export_payload.append(payload_entry)

    ftype = format_type.lower().strip()
    if ftype == "dae":
        return _write_collada_scene_graph(filepath, export_payload)
    elif ftype == "gltf" or ftype == "glb":
        return _write_gltf_scene_graph(filepath, export_payload)
    elif ftype == "obj":
        return _write_obj_flattened_mesh(filepath, export_payload, skeleton_ref)
        
    return False, "Unsupported exporter format specified."

def _write_collada_scene_graph(filepath, payload):
    """Generates a hierarchical XML COLLADA tree with rigid prop scene elements."""
    xml_out = [
        '<?xml version="1.0" encoding="utf-8"?>',
        '<COLLADA xmlns="http://collada.org" version="1.4.1">',
        '  <asset><up_axis>Y_UP</up_axis></asset>',
        '  <library_geometries>'
    ]
    
    for entry in payload:
        xml_out.append(f'    <geometry id="{entry["name"]}-mesh" name="{entry["name"]}">')
        xml_out.append('      <mesh>')
        xml_out.append(f'        <extra><technique profile="MH2"><source_ref>{entry["source_mesh_path"]}</source_ref></technique></extra>')
        xml_out.append('      </mesh>')
        xml_out.append('    </geometry>')
    xml_out.append('  </library_geometries>')

    xml_out.append('  <library_visual_scenes>')
    xml_out.append('    <visual_scene id="Scene" name="Scene">')
    
    for entry in payload:
        flat_matrix_str = " ".join(map(str, entry["matrix_transform"].flatten()))
        if entry["is_socketed"]:
            xml_out.append(f'      <node id="Prop_{entry["name"]}" name="{entry["name"]}" type="NODE" sid="socket_{entry["parent_bone_node"]}">')
        else:
            xml_out.append(f'      <node id="Prop_{entry["name"]}" name="{entry["name"]}" type="NODE">')
            
        xml_out.append(f'        <matrix sid="transform">{flat_matrix_str}</matrix>')
        xml_out.append(f'        <instance_geometry url="#{entry["name"]}-mesh"/>')
        xml_out.append('      </node>')
        
    xml_out.append('    </visual_scene>')
    xml_out.append('  </library_visual_scenes>')
    
    xml_out.append('  <scene><instance_visual_scene url="#Scene"/></scene>')
    xml_out.append('%_COLLADA_%')
    
    # Quick string correction to swap out template token placeholder markers safely
    cleaned_xml_string = '\n'.join(xml_out).replace('%_COLLADA_%', '</COLLADA>')

    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(cleaned_xml_string)
        return True, f"COLLADA export successfully resolved to {os.path.basename(filepath)}"
    except Exception as e:
        return False, f"COLLADA write error loop: {str(e)}"

def _write_gltf_scene_graph(filepath, payload):
    """Generates column-major glTF node references appended to joint arrays."""
    import json
    gltf_root = {
        "asset": {"version": "2.0", "generator": "MakeHuman 2 Prop Engine"},
        "scenes": [{"nodes": []}],
        "nodes": [],
        "meshes": []
    }
    
    for idx, entry in enumerate(payload):
        gltf_matrix = entry["matrix_transform"].T.flatten().tolist()
        node_entry = {
            "name": entry["name"],
            "matrix": gltf_matrix,
            "extras": {"source_mesh": entry["source_mesh_path"]}
        }
        if entry["is_socketed"]:
            node_entry["extras"]["parent_bone"] = entry["parent_bone_node"]
            
        gltf_root["nodes"].append(node_entry)
        gltf_root["scenes"][0]["nodes"].append(idx)

    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(gltf_root, f, indent=4)
        return True, "glTF PBR asset metadata export resolved successfully."
    except Exception as e:
        return False, f"glTF write error: {str(e)}"

def _write_obj_flattened_mesh(filepath, payload, skeleton):
    """
    Parses loose .obj geometric asset strings on disk, bakes your 3D transformation matrices 
    and skeletal bone channels directly into the vertex data coordinates, and merges them 
    safely alongside the main character mesh file!
    """
    import os
    
    obj_lines = []
    if os.path.isfile(filepath):
        with open(filepath, 'r', encoding='utf-8') as main_f:
            obj_lines = main_f.read().splitlines()
    else:
        obj_lines.append("# Wavefront OBJ Combined Scene File generated via MakeHuman 2 Prop Engine")

    v_offset = 0
    vn_offset = 0
    vt_offset = 0

    for line in obj_lines:
        if line.startswith("v "): 
            v_offset += 1
        elif line.startswith("vn "): 
            vn_offset += 1
        elif line.startswith("vt "): 
            vt_offset += 1

    for entry in payload:
        mesh_src = entry["source_mesh_path"]
        if not mesh_src:
            continue
            
        # =====================================================================
        # >>> FIXED: DYNAMIC PATH RECONSTRUCTION PREVENTS SKIPPED FILES >>>
        # =====================================================================
        if not os.path.isabs(mesh_src):
            plugin_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
            base_filename = os.path.basename(mesh_src)
            disk_mesh_path = os.path.normpath(os.path.join(plugin_root, "data", "props", base_filename)).replace("\\", "/")
        else:
            disk_mesh_path = mesh_src

        if not os.path.isfile(disk_mesh_path):
            print(f"[Prop Exporter Warning] Skipped asset mesh data path lookup failure: {disk_mesh_path}")
            continue

        print(f"[Prop Exporter] Baking geometric transformations onto mesh file: {os.path.basename(disk_mesh_path)}")
        obj_lines.append(f"\n# PROP SCENE ELEMENT OBJECT NODE: {entry['name']}")
        obj_lines.append(f"o Prop_{entry['name']}")

        final_transform = entry["matrix_transform"]
        
        if entry["is_socketed"] and skeleton:
            bone_name = entry["parent_bone_node"]
            bone_obj = None
            if hasattr(skeleton, 'bones') and bone_name in skeleton.bones:
                bone_obj = skeleton.bones[bone_name]
            elif hasattr(skeleton, 'getBone'):
                bone_obj = skeleton.getBone(bone_name)

            if bone_obj:
                b_rot = getattr(bone_obj, 'matRestGlobal', getattr(bone_obj, 'matPoseVerts', None))
                b_pos = getattr(bone_obj, 'headPos', getattr(bone_obj, 'poseheadPos', None))
                
                if b_rot is not None and b_pos is not None:
                    comp_m = np.eye(4, dtype=np.float64)
                    
                    if hasattr(b_rot, 'shape'):
                        if b_rot.shape == (3, 3): 
                            comp_m[0:3, 0:3] = b_rot
                        elif b_rot.shape == (4, 4): 
                            comp_m[0:3, 0:3] = b_rot[0:3, 0:3]
                    else:
                        try:
                            arr_rot = np.array(b_rot, dtype=np.float64)
                            if arr_rot.shape == (3, 3): 
                                comp_m[0:3, 0:3] = arr_rot
                            elif arr_rot.shape == (4, 4): 
                                comp_m[0:3, 0:3] = arr_rot[0:3, 0:3]
                        except Exception:
                            pass
                    
                    try:
                        if hasattr(b_pos, 'x') and callable(getattr(b_pos, 'x')):
                            comp_m[0:3, 3] = [float(b_pos.x()), float(b_pos.y()), float(b_pos.z())]
                        elif len(b_pos) >= 3:
                            comp_m[0:3, 3] = [float(b_pos[0]), float(b_pos[1]), float(b_pos[2])]
                    except Exception:
                        try:
                            comp_m[0:3, 3] = [float(getattr(b_pos, 'x', 0)), float(getattr(b_pos, 'y', 0)), float(getattr(b_pos, 'z', 0))]
                        except Exception:
                            pass
                            
                    final_transform = comp_m @ final_transform

        with open(disk_mesh_path, 'r', encoding='utf-8') as p_file:
            prop_lines = p_file.read().splitlines()

        local_v_count = 0
        local_vn_count = 0
        local_vt_count = 0

        for pline in prop_lines:
            tokens = pline.strip().split()
            if not tokens:
                continue

            if tokens[0] == "v":
                local_v_count += 1
                v_coords = np.array([float(tokens[1]), float(tokens[2]), float(tokens[3]), 1.0])
                baked_v = final_transform @ v_coords
                obj_lines.append(f"v {baked_v[0]:.6f} {baked_v[1]:.6f} {baked_v[2]:.6f}")

            elif tokens[0] == "vn":
                local_vn_count += 1
                n_coords = np.array([float(tokens[1]), float(tokens[2]), float(tokens[3])])
                rot_only_matrix = final_transform[0:3, 0:3]
                baked_n = rot_only_matrix @ n_coords
                n_len = np.linalg.norm(baked_n)
                if n_len > 0: 
                    baked_n = baked_n / n_len
                obj_lines.append(f"vn {baked_n[0]:.6f} {baked_n[1]:.6f} {baked_n[2]:.6f}")

            elif tokens[0] == "vt":
                local_vt_count += 1
                obj_lines.append(pline)

            elif tokens[0] == "f":
                face_vertices = []
                for vert_token in tokens[1:]:
                    indices = vert_token.split('/')
                    new_indices = []
                    
                    if len(indices) > 0 and indices[0]:
                        new_indices.append(str(int(indices[0]) + v_offset))
                    
                    if len(indices) > 1 and indices[1]:
                        new_indices.append(str(int(indices[1]) + vt_offset))
                    elif len(indices) > 1:
                        new_indices.append("")
                        
                    if len(indices) > 2 and indices[2]:
                        new_indices.append(str(int(indices[2]) + vn_offset))
                        
                    face_vertices.append("/".join(new_indices))
                    
                obj_lines.append(f"f {' '.join(face_vertices)}")

        v_offset += local_v_count
        vn_offset += local_vn_count
        vt_offset += local_vt_count

    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write('\n'.join(obj_lines))
        return True, f"Combined Wavefront OBJ scene successfully baked to {os.path.basename(filepath)}"
    except Exception as e:
        return False, f"OBJ scene serialization error: {str(e)}"



