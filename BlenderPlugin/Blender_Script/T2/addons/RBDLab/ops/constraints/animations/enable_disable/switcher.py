import bpy
from uuid import uuid4
from typing import List
from bpy.types import Operator, Object
from ...base import BaseConstraintOperator
from bpy.props import IntProperty, EnumProperty
# from .....Global.basics import ocultar_post_panel_settings
from ..check_previous_keyframes import check_keyframes
from .....Global.get_common_vars import get_common_vars


class GLUE_OT_anim_enable_disable_switcher(Operator, BaseConstraintOperator):
    bl_idname = "rbdlab.const_anim_enable_disable_switcher"
    bl_label = "Switcher Between Groups"
    bl_description = "Switcher for Enable and Disable Constrinats"
    bl_options = {'REGISTER', 'UNDO'}

    modos = [
            ('ENABLE_TO_DISABLE', "Enable to Disable", ""),
            ('DISABLE_TO_ENABLE', "Disable to Enable", ""),
        ]

    mode1 : EnumProperty(
        items=modos, 
        default='ENABLE_TO_DISABLE'
    )
    mode2 : EnumProperty(
        items=modos, 
        default='DISABLE_TO_ENABLE'
    )

    frame: IntProperty(name="Frame", default=0)

    def action(self, context, rbdlab_const, active_group, collection, chunks: List[Object], const_objects: List[Object]):

        # ocultar_post_panel_settings()

        rbdlab, ui, tcoll_list = get_common_vars(context, get_rbdlab=True, get_ui=True, get_tcoll_list=True)

        tcoll = tcoll_list.active
        constswitch_list = tcoll.rbdlab.constswitch_list
        
        # chekeamos si es por by selection:
        selected_meshes = [ob for ob in context.selected_objects if ob.type == 'MESH' and ob.select_get()]
        if constswitch_list.by_selection and len(selected_meshes) < 1:
            self.report({'ERROR'}, "No selected Objects!")
            return {'CANCELLED'}

        check = check_keyframes(self, active_group, constswitch_list, self.frame, chunks)
        if check:
            if 'CANCELLED' in check:
                return {'CANCELLED'}

        rbdlab_const = rbdlab.constraints
        previous_index = rbdlab_const.active_group_index

        if ui.const_switcher_from_collections == ui.const_switcher_to_collections:
            self.report({'ERROR'}, "Switching between the same collection is not supported!")
            return {'CANCELLED'}
        else:
            from_coll_name = ui.const_switcher_from_collections.name
            to_coll_name = ui.const_switcher_to_collections.name

            all_groups = rbdlab_const.get_all_constraints_groups

            short_id = str(uuid4())[:6]
            # cp_sid = "rbdlab_switcher_" + short_id

            all_constraints = set()
            for i, item in enumerate(all_groups):
                current_coll = item.collection.name

                # Para guardar en el item todos los objetos constraints de ambas collections:
                for const in item.collection.objects:
                    all_constraints.add(const)

                if current_coll == from_coll_name:
                    rbdlab_const.active_group_index = i
                    mode = self.mode1

                    try:
                        bpy.ops.rbdlab.const_constswitch_add(id_name=short_id, mode=mode, frame=self.frame, single_item=False)
                    except:
                        self.report({'ERROR'}, "Already exist keyframes in frame: "+ str(self.frame) + "!")
                        rbdlab_const.active_group_index = previous_index
                        return {'CANCELLED'}
                
                if current_coll == to_coll_name:
                    rbdlab_const.active_group_index = i
                    mode = self.mode2

                    try:
                        bpy.ops.rbdlab.const_constswitch_add(id_name=short_id, mode=mode, frame=self.frame, single_item=False)
                    except:
                        self.report({'ERROR'}, "Already exist keyframes in frame: "+ str(self.frame) + "!")
                        rbdlab_const.active_group_index = previous_index
                        return {'CANCELLED'}
            
            # Soft To Hard In Frame: xxx
            name1 = "Soft" if "soft" in from_coll_name.lower() else "hard"
            name2 = "Hard" if "hard" in to_coll_name.lower() else "soft"

            # Agrego un único item al listado para los dos:
            constswitch_list.add_item(
                id_name = short_id,
                mode='None', 
                from_active_group = active_group.idname, 
                label_txt = " " + name1 + " To " + name2 + " In Frame: " + str(self.frame), 
                keyframes = [self.frame, self.frame+1], 
                chunks = chunks,
                constraints = list(all_constraints),
                switcher_btween = True
            )

        rbdlab_const.active_group_index = previous_index
        return {'FINISHED'}

    def invoke(self, context, event):
        scn = context.scene
        self.frame = scn.frame_current
        return context.window_manager.invoke_props_dialog(self, width=300)

    def draw(self, context):
        
        scn = context.scene
        rbdalb = scn.rbdlab
        ui = rbdalb.ui

        layout = self.layout

        col = layout.column(align=True)
        
        collections = col.box().column(align=True)
        collections.prop(ui, "const_switcher_from_collections", text="") # from
        mode = collections.row(align=True)
        mode.prop(self, "mode1", expand=True)

        collections = col.box().column(align=True)
        collections.prop(ui, "const_switcher_to_collections", text="") # to
        mode = collections.row(align=True)
        mode.prop(self, "mode2", expand=True)

        col.separator()
        col.prop(self, "frame")

