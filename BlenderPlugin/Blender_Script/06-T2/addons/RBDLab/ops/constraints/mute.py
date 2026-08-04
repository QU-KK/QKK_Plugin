from typing import List, Set
from bpy.types import Operator, Object
from bpy.props import BoolProperty
# from ...addon.naming import RBDLabNaming
from .base import BaseConstraintOperator
# from ...Global.basics import ocultar_post_panel_settings
from ...Global.functions import deselect_all_objects


class CONST_OT_mute(Operator, BaseConstraintOperator):
    bl_idname = "rbdlab.const_mute"
    bl_label = "Mute Constraints"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = "Mute selected chunks/constraints"

    state: BoolProperty(default=False, options={'SKIP_SAVE'})

    # Property interna.
    # True porque necesitamos obtenerlos a partir de los chunks
    base__get_const_objects_from_chunks: bool = True

    def get_filtered_chunks(self, context) -> Set[Object]:
        return context.selected_objects

    def action(self, context, rbdlab_const, active_group, collection, selected_chunks: List[Object], const_objects: List[Object]):
        state = self.state

        # ocultar_post_panel_settings()
        
        # # HACK: Para obtener los constraint objects de los selected.
        # # ya que "const_objects" incluye solo los const_ob de los selected chunks, pero no si seleccionaste los GP directamente.
        # const_objects_select = [const_ob for const_ob in context.selected_objects
        #                         if const_ob.rigid_body_constraint and 
        #                         const_ob.type == RBDLabNaming.CONST_TYPE and 
        #                         RBDLabNaming.GROUP_ID in const_ob and
        #                         const_ob[RBDLabNaming.GROUP_ID] == group.idname]

        # se agregan si fueran por seleccion directa de los grease pencil, de paso aprovecho para quitar repetidos:
        # all_const = list(set(const_objects+const_objects_select))

        # descarto usar los const_objects porque no se bien como se estan eligiendo:
        all_constraints = active_group.collection.objects 
        # filtramos los objetos por seleccion (solo los constraints que si alguno de sus object forman parte de la selecion actual):
        valid_constratins = [const for const in all_constraints if const.rigid_body_constraint.object1 in context.selected_objects or const.rigid_body_constraint.object2 in context.selected_objects]
        
        # # filtramos los objetos por seleccion (solo los constraints que sus object, ambos, formen parte de la selecion actual):
        # valid_constratins = [const for const in all_const if const.rigid_body_constraint.object1 in context.selected_objects and const.rigid_body_constraint.object2 in context.selected_objects]

        print(valid_constratins)
        for const_ob in (valid_constratins):
            # print(const_ob.name)
            const_ob.rigid_body_constraint.enabled = not state
            const_ob["rbdlab_const_muted"] = state

        wm = context.window_manager
        state_str = "Muted " if state else "Unmuted "
        feedback_text = state_str + str(len(valid_constratins)) + " Constraints."

        if state:
            wm["Constraints_MuteUnmute_str"] = feedback_text
        else:
            if "Constraints_MuteUnmute_str" in wm:
                del wm["Constraints_MuteUnmute_str"]

        self.report({'INFO'}, feedback_text)

        # print("Muted Constraint Objects:", const_objects)


class CONST_OT_select_muted(Operator, BaseConstraintOperator):
    bl_idname = "rbdlab.const_select_muted"
    bl_label = "Select muted Constraints"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = "Select muted constraints"

    def action(self, context, rbdlab_const, group, collection, chunks: List[Object], const_objects: List[Object]):
        deselect_all_objects(context)
        for const_ob in const_objects:
            if "rbdlab_const_muted" in const_ob:
                if const_ob["rbdlab_const_muted"]:
                    const_ob.rigid_body_constraint.object1.select_set(True)
                    const_ob.rigid_body_constraint.object2.select_set(True)
