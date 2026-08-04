import bpy
from bpy.types import Operator, Area
# from .....addon.naming import RBDLabNaming
from .....Global.get_common_vars import get_common_vars
from .....Global.basics import context_override


class RBDLAB_OT_metal_displace_new_textue(Operator):
    bl_idname = "rbdlab.metalsoft_creation_displace_new_texture"
    bl_label = "New Texture"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def description(cls, _context, properties):
        return "New Texture"


    def execute(self, context):
        rbdlab = get_common_vars(context, get_rbdlab=True)
        tcoll_item = rbdlab.lists.target_coll_list.active_item
        metal_item = tcoll_item.metal_list.active
        modifier_list = metal_item.modifiers

        ob = context.active_object

        if not ob:
            self.report({'ERROR'}, "Invalid Active Object!")
            return {'CANCELLED'}

        if ob.type != 'MESH':
            self.report({'ERROR'}, "Invalid Type of Active Object!")
            return {'CANCELLED'}

        active_mod = modifier_list.active
        displace_mod = ob.modifiers.get(active_mod.mod_name)
        if displace_mod:
            bpy.ops.texture.new()
            my_new_texture = bpy.data.textures[-1]
            my_new_texture.type = 'CLOUDS'
            displace_mod.texture = my_new_texture

            # Cambio al tab en properties a texture:
            # sobreescribir el contexto:
            def callback(context) -> None:
                area = context.area  # Accedemos al área desde el contexto
                area.spaces[0].context = 'TEXTURE'
                area.tag_redraw()
            context_override(context=context, area_type='PROPERTIES', callback=callback)


        return {'FINISHED'}