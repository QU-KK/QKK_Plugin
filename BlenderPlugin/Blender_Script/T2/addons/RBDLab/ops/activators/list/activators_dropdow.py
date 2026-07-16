import bpy
from bpy.types import Operator
from bpy.props import StringProperty
# from ....addon.naming import RBDLabNaming


class ACTIVATORS_OT_dropdown(Operator):
    bl_idname = "rbdlab.act_dropdown"
    bl_label = "DropDown"
    bl_description = "DropDown"
    bl_options = {'REGISTER', 'UNDO'}

    action: StringProperty(default="")

    def execute(self, context):

        scn = context.scene
        rbdlab = scn.rbdlab

        tcoll_list = rbdlab.lists.target_coll_list
        tcoll = tcoll_list.active
        
        if not tcoll:
            return {'CANCELLED'}

        ac_layers_list = rbdlab.lists.ac_layers_list
        layers_item = ac_layers_list.active

        if not layers_item:
            return {'CANCELLED'}

        activators_list = layers_item.activators_list
        
        if activators_list.is_void:
            return {'CANCELLED'}
        
        action = self.action
        sel = {
                "select_all": True,  
                "deselect_all": False
        }
        mark = {
                "mark_all": True,
                "unmark_all": False
        }
        hides = {
                "hide_all": True,
                "unhide_all": False
        }


        if action in sel.keys():
            # solo los computables:
            activators = activators_list.get_all_computable_activators
            if not activators:
                return {'CANCELLED'}

            for ob in activators:
                ob.select_set(sel[action])
        
        elif action == "delete_all":
            all_ids = activators_list.get_all_computable_ids
            [bpy.ops.rbdlab.act_rm_item(id_to_rm=id_name) for id_name in all_ids]

        elif action in mark.keys():
            # todos los activators:
            activators = activators_list.get_all_activators
            if not activators:
                return {'CANCELLED'}
            
            all_items = activators_list.get_all_items
            for item in all_items:
                item.compute = mark[action]

        elif action in hides.keys():
            # solo los computables:
            activators = activators_list.get_all_computable_activators
            if not activators:
                return {'CANCELLED'}

            # for ob in activators:
            #     ob.hide_set(hides[action])
            
            all_items = activators_list.get_all_items
            for item in all_items:
                item.visible = not hides[action]
        
        
        return {'FINISHED'}
