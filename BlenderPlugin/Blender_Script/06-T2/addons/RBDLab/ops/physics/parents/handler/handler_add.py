import bpy
from bpy.types import Operator
from .....Global.functions import generate_bounding_box
from .....Global.basics import set_active_object, context_override, rm_ob
from .....addon.naming import RBDLabNaming


class RBDLAB_OT_physics_parents_add_handler(Operator):
    bl_idname = "rbdlab.rigidbody_add_handler"
    bl_label = "Add handler"
    bl_description = "Add Handler"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scn = context.scene
        rbdlab = scn.rbdlab

        tcoll = rbdlab.filtered_target_collection
        coll_name = tcoll.name

        if tcoll is not None:
            tcoll_objs = tcoll.objects

            # Si tuviera previo handler lo eliminamos:
            active_item = rbdlab.lists.target_coll_list.active_item
            if active_item.handler in bpy.data.objects[:]:
                rm_ob(active_item.handler)
                active_item.handler = None

            bbox_name = coll_name + RBDLabNaming.SUFIX_BBOX
            if tcoll_objs:

                # sobreescribir el contexto:
                def callback(context) -> None:
                    area = context.area  # Accedemos al área desde el contexto
                    for space in area.spaces:
                        if space.type == 'VIEW_3D':
                            rbdlab.eth_icons_t = space.show_gizmo_object_translate
                            rbdlab.eth_icons_r = space.show_gizmo_object_rotate
                            rbdlab.eth_icons_s = space.show_gizmo_object_scale
                    area.tag_redraw()
                context_override(context=context, area_type='VIEW_3D', callback=callback)
                
                handler = generate_bounding_box(self, context, tcoll_objs, "Empty", True, 0.2, 0.2, 0.2, bbox_name)
                
                # Guardamos el objeto handler en el listado de target collctions:
                active_item.handler = handler

        active_item.handler.select_set(True)
        set_active_object(context, handler)

        # bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        return {'FINISHED'}


class RBDLAB_OT_physics_parents_rm_handler(Operator):
    bl_idname = "rbdlab.rigidbody_rm_handler"
    bl_label = "Remove handler"
    bl_description = "Remove Handler"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scn = context.scene
        rbdlab = scn.rbdlab
        tcoll = rbdlab.filtered_target_collection

        if tcoll is not None:
            tcoll_objs = tcoll.objects

            if tcoll_objs:
                
                active_item = rbdlab.lists.target_coll_list.active_item
                # Quitamos los parents:
                for ob in tcoll_objs:
                    if ob.name != active_item.handler.name:
                        ob.parent = None
                
                # Si tuviera previo handler lo eliminamos:
                active_item = rbdlab.lists.target_coll_list.active_item
                if active_item.handler in bpy.data.objects[:]:
                    rm_ob(active_item.handler)
                    active_item.handler = None

        return {'FINISHED'}