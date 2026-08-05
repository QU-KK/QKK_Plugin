import bpy
import bmesh
from bpy.types import Operator
from ....addon.naming import RBDLabNaming
from ....Global.get_common_vars import get_common_vars
from ....Global.functions import (
                                    create_modifier, 
                                    set_active_object, 
                                    deselect_all_objects, 
                                    copy_modifier_by_name_from_active_to_selected, 
                                    enter_edit_mode, 
                                    enter_object_mode
                                )


class RBDLAB_OT_metal_clean_fractures(Operator):
    bl_idname = "rbdlab.metalsoft_creation_clean_fractures"
    bl_label = "Metal Clean Fractures"
    bl_options = {'REGISTER', 'UNDO'}


    @classmethod
    def description(cls, _context, properties):
        return "Clean Fractures"
    
    
    def get_count_selected_vert(self, context) -> int:
        
        """ Obtiene la cantidad de todos los vertices seleccionados, en la selección actual de objetos """
        
        selected_vertices = 0
        for ob in context.selected_objects:
            bm = bmesh.from_edit_mesh(ob.data)
            selected_vertices += sum(1 for v in bm.verts if v.select)
            bm.free()
        
        return selected_vertices


    def prepare_to_edit_mode(self, context) -> None:
        enter_edit_mode(context, mode='VERT')
        bpy.ops.mesh.select_all(action='SELECT')

    
    def select_and_delete(self, context, use_boundary, use_multi_face, use_non_contiguous, total_verts) -> None:

        self.prepare_to_edit_mode(context)

        bpy.ops.mesh.select_non_manifold(
            extend=False, 
            use_wire=False, 
            use_boundary=use_boundary, 
            use_multi_face=use_multi_face, 
            use_non_contiguous=use_non_contiguous, 
            use_verts=False
        )

        selected_vertices = self.get_count_selected_vert(context)
                
        # Prevenimos borrar todos los vertices:
        if 0 < selected_vertices < total_verts:
            # print("Remove", selected_vertices, "vertices")
            bpy.ops.mesh.delete(type='VERT')

        bpy.ops.mesh.select_all(action='SELECT')
        enter_object_mode(context)


    def execute(self, context):

        tcoll_list = get_common_vars(context, get_tcoll_list=True)
        tcoll_item = tcoll_list.active_item
        
        if not tcoll_item:
            self.report({'ERROR'}, "No valid Target Collection!")
            return {'CANCELLED'}

        metal_list = tcoll_item.metal_list
        metal_props = tcoll_item.metal_props

        # item = tcoll_list.active_item
        # me aseguro de que esten visibles los chunks para el clean:
        # current_mode = item.metal_or_fractures
        # if 'FRACTURES' not in current_mode:
        #     if 'METAL' in current_mode:
        #         item.metal_or_fractures = {'METAL', 'FRACTURES'}

        current_metal = metal_list.active
        if current_metal:
            metal_previous_state = current_metal.metal_or_fractures
            if 'FRACTURES' not in metal_previous_state:
                current_metal.metal_or_fractures = {'FRACTURES'}

        chunks = tcoll_list.get_current_active_tcoll_valild_objects(context)
        
        if not chunks:
            self.report({'ERROR'}, "No valid chunks in this Target Collection!")
            return {'CANCELLED'}

        deselect_all_objects(context)

        first_chunk = chunks[0]
        [ob.select_set(True) for ob in chunks]
        set_active_object(context, first_chunk)

        modifiers_to_copy = []

        if metal_props.metal_decimate_planar:
            
            decimate_planar_mod = first_chunk.modifiers.get(RBDLabNaming.DECIMATE_PLANAR)
            if not decimate_planar_mod:
                decimate_planar_mod = create_modifier(first_chunk, RBDLabNaming.DECIMATE_PLANAR, 'DECIMATE')
                decimate_planar_mod.decimate_type = 'DISSOLVE'
                modifiers_to_copy.append(RBDLabNaming.DECIMATE_PLANAR)

        if metal_props.metal_triangulate:

            triangualte_mod = first_chunk.modifiers.get(RBDLabNaming.TRIANGULATE)
            if not triangualte_mod:
                triangualte_mod = create_modifier(first_chunk, RBDLabNaming.TRIANGULATE, 'TRIANGULATE')        
                modifiers_to_copy.append(RBDLabNaming.TRIANGULATE)

        # Transferimos los modifiers al resto de la seleccion:
        copy_modifier_by_name_from_active_to_selected(context, modifiers_to_copy)
    
        # aplicar los modifiers si tuviera alguno:
        if metal_props.metal_decimate_planar or metal_props.metal_triangulate:

            # Esto se estaba cepillando las particulas (si las hubiera), por lo tanto deselecciono los iners emisores:
            [ob.select_set(False) for ob in context.selected_objects if RBDLabNaming.INNER_EMISOR in ob]
            
            bpy.ops.object.convert(target='MESH')
    

        if metal_props.use_multi_face or metal_props.use_boundary or metal_props.use_non_contiguous:

            total_verts = sum([len(ob.data.vertices) for ob in context.selected_objects])
            
            self.select_and_delete(
                                    context, 
                                    metal_props.use_boundary, 
                                    metal_props.use_multi_face, 
                                    metal_props.use_non_contiguous, 
                                    total_verts
                                )

        if metal_props.metal_remove_doulbes:

            self.prepare_to_edit_mode(context)

            selected_vertices = self.get_count_selected_vert(context)

            if selected_vertices > 0:
                bpy.ops.mesh.remove_doubles()
    
            bpy.ops.mesh.select_all(action='SELECT')
            enter_object_mode(context)
        
        # restauro como estuviea la visilidad:
        # rbdlab.ui.visibility_metal_or_ob = current_mode
        if current_metal and metal_previous_state:
            current_metal.metal_or_fractures = metal_previous_state

        deselect_all_objects(context)
        return {'FINISHED'}
