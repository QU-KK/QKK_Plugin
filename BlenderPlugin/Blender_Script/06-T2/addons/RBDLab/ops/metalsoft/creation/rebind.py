import bpy
from bpy.types import Operator
from ....addon.naming import RBDLabNaming
from ....Global.get_common_vars import get_common_vars
from ....Global.functions import set_active_object, create_modifier
from ..common.reorder_modifiers import reorder_modifiers

class RBDLAB_OT_metal_rebind(Operator):
    bl_idname = "rbdlab.metalsoft_creation_rebind"
    bl_label = "Metal Rebind"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def description(cls, _context, properties):
        return "Metal Rebind"

    def execute(self, context):

        scn, tcoll_list = get_common_vars(context, get_scn=True, get_tcoll_list=True)

        tcoll_item = tcoll_list.active_item
        if not tcoll_item:
            self.report({'ERROR'}, "Not valid Target Collections!")
            return {'CANCELLED'}
    
        metal_list = tcoll_item.metal_list

        all_originals = metal_list.get_current_originals
        # org_ob = rbdlab.ui.ob_original_selector

        if not all_originals:
            self.report({'ERROR'}, "No original object selected!")
            return {'CANCELLED'}
        
        previous_selection = context.selected_objects
        previous_active = context.active_object

        current_frame = scn.frame_current
        scn.frame_set(scn.frame_start)

        for org_ob in all_originals:

            dummy_ob_name = org_ob.name + RBDLabNaming.SUFIX_DUMMY_METAL_OB
            dummy_ob = bpy.data.objects.get(dummy_ob_name)
            if not dummy_ob:
                self.report({'ERROR'}, "No GN object detected!")
                return {'CANCELLED'}
            
            # Guardo el active modifier que tenga:
            previous_active_mod = org_ob.modifiers.active
            set_active_object(context, org_ob)
            
            # borramos el modifier previo:
            surface_deform_mod = org_ob.modifiers.get(RBDLabNaming.SURFACE_DEFORM)
            if surface_deform_mod:
                org_ob.modifiers.remove(surface_deform_mod)
            
            # creamos el mismo pero nuevo:
            surface_deform_mod = create_modifier(org_ob, RBDLabNaming.SURFACE_DEFORM, 'SURFACE_DEFORM')
            surface_deform_mod.target = dummy_ob

            reorder_modifiers(org_ob)

            # Bindeo:
            bpy.ops.object.surfacedeform_bind(modifier=RBDLabNaming.SURFACE_DEFORM)
            
            # Restauro el active modifier que fuera:
            if previous_active_mod:
                pm = org_ob.modifiers.get(previous_active_mod.name)
                if pm:
                    org_ob.modifiers.active = pm

        if current_frame != scn.frame_current:
            scn.frame_set(current_frame)
        
        if previous_selection:
            bpy.ops.object.select_all(action='DESELECT')
            for ob in previous_selection:
                ob.select_set(True)
    
        if previous_active:
            set_active_object(context, previous_active)

        return {'FINISHED'}
