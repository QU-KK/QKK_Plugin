import bpy
from bpy.types import Operator, Object
from .....Global.basics import deselect_all_objects, set_active_object
from .....addon.naming import RBDLabNaming
from ...common_rigidbodies_functs import my_settings_copy, update_values, my_settings_copy
from .....Global.get_common_vars import get_common_vars


class RBDLAB_OT_physics_dynamic_switch(Operator):
    bl_idname = "rbdlab.phyisics_dswitch_dynamic_parent"
    bl_label = "Switch"
    bl_description = "Switch"
    bl_options = {'REGISTER', 'UNDO'}

    def creamos_constraint_animado(self, ob: Object, target: Object, frame: int) -> None:
        prev_const = ob.constraints.get(RBDLabNaming.CHILD_OF)
        if not prev_const:
            # bpy.ops.object.constraint_add(type='CHILD_OF')
            child_of = ob.constraints.new('CHILD_OF')
            child_of = ob.constraints[-1]
            child_of.name = RBDLabNaming.CHILD_OF
            child_of.target = target

            dpath = "constraints[\"" + RBDLabNaming.CHILD_OF + "\"].enabled"
            child_of.enabled = True
            ob.keyframe_insert(
                data_path=dpath,
                frame=frame
            )
            child_of.enabled = False
            ob.keyframe_insert(
                data_path=dpath,
                frame=frame+1
            )

    def animamos_los_kinematic(self, ob: Object, frame: int) -> None:
        if ob.rigid_body is None:
            return
        ob.rigid_body.kinematic = True
        ob.keyframe_insert(
            data_path="rigid_body.kinematic",
            frame=frame
        )
        ob.rigid_body.kinematic = False
        ob.keyframe_insert(
            data_path="rigid_body.kinematic",
            frame=frame+1
        )

    def execute(self, context):

        scn, rbdlab, tcoll_list = get_common_vars(context, get_scn=True, get_rbdlab=True, get_tcoll_list=True)
        
        org_ob = rbdlab.physics.dswitch.dynamic_parent.select_original

        if org_ob is None:
            self.report({'ERROR'}, "Invalid Original Object!")
            return {'CANCELLED'}

        active_item = tcoll_list.active_item
        tcoll = tcoll_list.active
        chunks = tcoll_list.get_current_active_tcoll_valild_objects(context)
        rbd_props = rbdlab.physics.rigidbodies

        first_chunk = chunks[0]

        deselect_all_objects(context)
        set_active_object(context, first_chunk)

        # si no tuviera rigidbodies:
        if first_chunk.rigid_body is None:
            [ob.select_set(True) for ob in chunks]

            # agrego los rigidbody:
            bpy.ops.rigidbody.objects_add(type='ACTIVE')
            # no solo lo les agrego rigidbodies sino que:
            update_values(first_chunk, rbdlab)  # seteo su rigidbody con la info de las propiedades de ui
            my_settings_copy(context, chunks, rbdlab)  # le copiamos desde el activo al resto de chunks
            # y marcamos la collection:
            tcoll[RBDLabNaming.COLL_WITH_RBD] = RBDLabNaming.COLL_WITH_RBD
            # bpy.ops.rbdlab.rigidbody_add()

        # lo ponemos como kinematic:
        first_chunk.rigid_body.kinematic = True
        # se lo copiamos al resto de chunks:
        my_settings_copy(context, chunks, rbdlab)

        # calculamos la masa:
        bpy.ops.rigidbody.mass_calculate(material=rbd_props.avalidable_mass, density=2320)

        current_frame = scn.frame_current
        scn.frame_set(scn.frame_start)

        # Forzar la actualización del depsgraph
        # bpy.ops.wm.redraw_timer(type='DRAW', iterations=1)

        # si tiene los rbd activos los desactivamos temporalmente:
        if active_item.enable_disable_rbd:
            active_item.enable_disable_rbd = False

        # se lo hacemsos a todos:
        for ob in chunks:
            # creamos y animamos los
            self.creamos_constraint_animado(ob, org_ob, current_frame)

            # animamos los kinematic:
            self.animamos_los_kinematic(ob, current_frame)

            # si tienen un handler se lo quitamos:
            parent = ob.parent
            if parent is not None:
                if parent.type == 'EMPTY' and parent.name.endswith(RBDLabNaming.SUFIX_BBOX):
                    ob[RBDLabNaming.HANDLER] = ob.parent
                    ob.parent = None
                    # rm_ob(parent)
        
        active_item.dswitch_at_frame = current_frame

        # marcamos la collection como que si que tiene rbd:
        tcoll = active_item.coll
        if RBDLabNaming.COLL_WITH_RBD not in tcoll:
            tcoll[RBDLabNaming.COLL_WITH_RBD] = True

        # volvemos a reactivas los rbd:
        if active_item.enable_disable_rbd == False:
            active_item.enable_disable_rbd = True

        deselect_all_objects(context)
        return {'FINISHED'}
