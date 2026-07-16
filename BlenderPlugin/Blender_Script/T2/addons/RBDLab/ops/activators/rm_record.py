
import bpy
from datetime import datetime
from bpy.types import Operator, Object
from bpy.props import EnumProperty
from ...Global.functions import get_array_data_from_obj
from ...addon.naming import RBDLabNaming
from ...Global.get_common_vars import get_common_vars


class ACTIVATORS_OT_rm_record(Operator):
    bl_idname = "rbdlab.act_rm_record"
    bl_label = "Remove Activators"
    bl_description = "Restore color and remove keyframes and properties in all chunks in current target collection"
    bl_options = {'REGISTER', 'UNDO'}

    mode: EnumProperty(
        name="Activators record mode",
        items=(('NORMAL', "Normal", "", 0), ('FORCE_PREVIEW', "Preview", "", 1)),
        default='NORMAL',
    )
    
    
    def remove_kf_in_rm_types(self, ob: Object, remove_types: list) -> None:
        if hasattr(ob.animation_data, "action"):
            action = ob.animation_data.action
            if action:
                [action.fcurves.remove(fc) for fc in action.fcurves if fc.data_path in remove_types]  
    

    def remove_kf_dpath_and_csprop(self, ob: Object, dpath: str, csprop:str) -> None:
        
        if hasattr(ob.animation_data, "action"):
            action = ob.animation_data.action
            if hasattr(action, "fcurves"): # en el codigo viejo ponía fcurve en singular :S ¿quizas lo renombraro en blender?
                [action.fcurves.remove(fc) for fc in action.fcurves if fc.data_path == dpath]
            del ob[csprop]

    
    def remove_anim_color(self, work_with:str, ob_input:Object) -> None:
        
        if work_with == 'CONSTRAINTS':
            objects = [ob_input.rigid_body_constraint.object1, ob_input.rigid_body_constraint.object2]
        else:
            objects = [ob_input]
        
        for ob in objects:
            
            if not ob.animation_data:
                continue
            
            if not ob.animation_data.action:
                continue

            fcurves_to_remove = [fc for fc in ob.animation_data.action.fcurves if fc.data_path.startswith("color")]
            for fc in fcurves_to_remove:
                ob.animation_data.action.fcurves.remove(fc)


    def remove_activators_work_with_and_animation(self, rbdlab, tocll, ob: Object, work_with:str) -> None:

        # para reutilizar:
        def append_by_type(data_types:dict, work_with:str, ob:Object) -> None:
            if data_types[work_with]['custom_prop'] in ob:
                if data_types[work_with]['dpath'] not in remove_types:
                    remove_types.append(data_types[work_with]['dpath'])
        

        def del_custom_property(data_types:dict, work_with:str, ob:Object) -> None:
            if data_types[work_with]['custom_prop'] in ob:
                del ob[data_types[work_with]['custom_prop']]
        

        remove_types = []

        data_types = {
                'DEACTIVATION':{
                                'custom_prop': "rbdlab_acetonized_deactivation",
                                'dpath': "rigid_body.use_deactivation"
                },
                'KINEMATIC':{
                                'custom_prop': "rbdlab_acetonized_kineatic",
                                'dpath': "rigid_body.kinematic"
                },
                'DYNAMIC':{
                                'custom_prop': "rbdlab_acetonized_dynamic",
                                'dpath': "rigid_body.enabled"
                },
                'CONSTRAINTS':{
                                'custom_prop': "rbdlab_acetonized_constraints",
                                'dpath': "rigid_body_constraint.enabled"
                },
        }

        visible = ob.visible_get()
        if not visible:  # si esta oculto lo desoculto
            ob.hide_set(False)

        # solo borrar animaciones si se que fueron acetonizeds:
        if ob.type == 'MESH':
            
            if self.mode == 'NORMAL':
                
                append_by_type(data_types, work_with, ob)

            # tanto para preview como para normal:
            if RBDLabNaming.ACTIVATORS_EXPLODED_DEST in ob and RBDLabNaming.ACTIVATORS_INITIAL_EXPLODE in ob:
                remove_types.append("location")

        elif ob.type == RBDLabNaming.CONST_TYPE: 
            if self.mode == 'NORMAL':

                append_by_type(data_types, work_with, ob)


        # remove keyframes de los remove_types:
        # print("remove_types", remove_types)
        if remove_types:
            # tanto para preview como para normal:
            self.remove_kf_in_rm_types(ob, remove_types)
            
        if self.mode == 'NORMAL':

            if ob.type == 'MESH':

                del_custom_property(data_types, work_with, ob)

            if ob.type == RBDLabNaming.CONST_TYPE:

                if data_types[work_with]['custom_prop'] in ob:
                    del ob[data_types[work_with]['custom_prop']]

        # if make clear onrmal or preview restore centroid visibility:
        if RBDLabNaming.ACTIVATORS_EXPLODE_DONE in tocll:
            rbdlab.activators.explode_centroid_visibility = True

        if self.mode == 'NORMAL':
            if visible:  # restauro si estaba oculto
                if not ob.visible_get():
                    ob.hide_set(False)
            else:
                ob.hide_set(False)

            # if make clear in normal mode remove done:
            # if RBDLabNaming.ACTIVATORS_EXPLODE_DONE in tocll:
            #     del tocll[RBDLabNaming.ACTIVATORS_EXPLODE_DONE]

        # remove locations if use forces and flag rbdlab_acetonized_with_loc_force:
        if "rbdlab_acetonized_with_loc_force" in ob:
            self.remove_kf_dpath_and_csprop(ob, "location", "rbdlab_acetonized_with_loc_force")

        # remove locations if use explode forces and flag rbdlab_acetonized_with_explode_force:
        if "rbdlab_acetonized_with_explode_force" in ob:
            self.remove_kf_dpath_and_csprop(ob, "location", "rbdlab_acetonized_with_explode_force")

        # remove rotations if use forces and flag rbdlab_acetonized_with_rot_force:
        if "rbdlab_acetonized_with_rot_force" in ob:
            self.remove_kf_dpath_and_csprop(ob, "rotation_euler", "rbdlab_acetonized_with_rot_force")

        # if have kinematic from rbd panel previously, restore it:
        if RBDLabNaming.RBD_KINEMATIC in ob or RBDLabNaming.RBD_SEL_KINEMATIC in ob:
            if ob.rigid_body:
                ob.rigid_body.kinematic = True
        else:
            if ob.rigid_body:
                ob.rigid_body.kinematic = False
        
        # eliminamos la animación del color:
        self.remove_anim_color(work_with, ob)


    @staticmethod
    def get_valid_chunks(context, rbdlab) -> list:
        valid_objects = []

        scn, ac_layers_list = get_common_vars(context, get_scn=True, get_ac_layers_list=True)

        if rbdlab.activators.type_selection == "Collection":
            valid_objects = ac_layers_list.get_all_computable_includes
            
            # Borrar solo los de su active layer:
            # valid_objects = ac_layers_list.get_all_computable_includes_from_active

        elif rbdlab.activators.type_selection == "Scene":
            valid_objects = [ob for ob in scn.objects if ob.type == 'MESH' and RBDLabNaming.ACTIVATORS_OBJECTS not in ob]

        return valid_objects


    def clear_glue_constraints(self, context, rbdlab, tcoll, valid_objects, work_with):

        procesed_constraints = []

        for obj in valid_objects:
            constrainsts = get_array_data_from_obj(context, RBDLabNaming.CONSTRAINTS, obj)
            if constrainsts:
                for const in constrainsts:

                    if const in procesed_constraints:
                        continue

                    if const not in bpy.data.objects:
                        continue

                    const_obj = bpy.data.objects.get(const)

                    if const_obj.type != RBDLabNaming.CONST_TYPE:
                        continue

                    self.remove_activators_work_with_and_animation(rbdlab, tcoll, const_obj, work_with)

                    if "rbdlab_const_status" in const_obj:
                        const_obj.rigid_body_constraint.enabled = const_obj["rbdlab_const_status"]
                        del const_obj["rbdlab_const_status"]
                    else:
                        const_obj.rigid_body_constraint.enabled = True

                    procesed_constraints.append(const)


    def execute(self, context):
        ''' rbdlab.act_rm_record '''

        start = datetime.now()

        scn, rbdlab, tcoll_list, ac_layers_list = get_common_vars(context, get_scn=True, get_rbdlab=True, get_tcoll_list=True, get_ac_layers_list=True)

        tcoll = tcoll_list.active

        # remove all keyframes to chunks in collection

        if not tcoll:
            self.report({'WARNING'}, "Target Collection is Empty!")
            return {'CANCELLED'}

        if ac_layers_list.is_void:
            self.report({'ERROR'}, "First you must create some activator!")
            return {'CANCELLED'}
        
        # layer_active = ac_layers_list.active

        all_computable_includes = ac_layers_list.get_all_computable_includes
        if not all_computable_includes:
            self.report({'ERROR'}, "First you must include chunks!")
            return {'CANCELLED'}

        scn.frame_set(scn.frame_start)
        # work_with = rbdlab.activators.work_with
        # los multiples tipos 
        # work_with_types = ac_layers_list.get_all_computable_types
        all_computed_items = ac_layers_list.get_all_computable_items

        valid_objects = self.get_valid_chunks(context, rbdlab)
        
        if len(valid_objects) == 0:
            self.report({'ERROR'}, "Cant get chunks!")
            return {'CANCELLED'}


        for item in all_computed_items:
            work_with = item.type
            
            if work_with in ['DEACTIVATION', 'KINEMATIC', 'DYNAMIC']:

                for ob in valid_objects:

                    # only remove kf in includeds chunks:
                    if ob not in all_computable_includes:
                        continue

                    if RBDLabNaming.CHUNK_ACTIVATORS in ob:
                        del ob[RBDLabNaming.CHUNK_ACTIVATORS]

                    # only remove kf in RBDLabNaming.ACETONABLE azetonizeds chunks:
                    # if RBDLabNaming.ACETONABLE not in ob:
                    #     continue

                    self.remove_activators_work_with_and_animation(rbdlab, tcoll, ob, work_with)

                    # lo dejamos reseteado en lo que tenga el usuario en su ui:
                    if work_with == 'DYNAMIC':    
                        if ob.rigid_body:
                            ob.rigid_body.enabled = True if 'ON' == item.start_on_off_toggle else False

            elif 'CONSTRAINTS' == work_with:
                self.clear_glue_constraints(context, rbdlab, tcoll, valid_objects, work_with)

        if self.mode == 'NORMAL':
            if "activators_recorded" in rbdlab.filtered_target_collection:
                del rbdlab.filtered_target_collection["activators_recorded"]

        elif self.mode == 'FORCE_PREVIEW':
            if "activators_force_preview_recorded" in rbdlab.filtered_target_collection:
                del rbdlab.filtered_target_collection["activators_force_preview_recorded"]

        #------------------------------------------------------------------------------------------------------------------------
        # restauramos las transformaciones y el color, por si acaso da la casualidad de q en el primer frame ya era color activo:
        #------------------------------------------------------------------------------------------------------------------------
        def restaurar_transformacion(obj, transformaciones):
            for propiedad, valor in transformaciones.items():
                if getattr(obj, propiedad) != valor:
                    setattr(obj, propiedad, valor)

        for ob in valid_objects:
            
            if RBDLabNaming.ORG_DATA not in ob:
                continue

            org_transforms = ob[RBDLabNaming.ORG_DATA]
            restaurar_transformacion(ob, org_transforms)

            # borramos el custom property del diccionario:
            del ob[RBDLabNaming.ORG_DATA]
        #------------------------------------------------------------------------------------------------------------------------

        # Ponemos todos los computables, como no grabados:
        ac_layers_list.set_all_computable_recorded(False)
        
        # Pongo el layer borrado como no grabado:
        # layer_active.recorded = False

        info_string = "Activators" if self.mode == 'NORMAL' else "Preview"  
        self.report({'INFO'}, info_string + " Clean Finished in " + str(datetime.now() - start) + " seconds!")
        return {'FINISHED'}