import bpy
from datetime import datetime
from bpy.types import Operator
from ...addon.naming import RBDLabNaming
from bpy.props import StringProperty
from ...Global.functions import remove_collection
# from ...Global.basics import ocultar_post_panel_settings
from ...Global.get_common_vars import get_common_vars


class RM_OT_constraint_group(Operator):
    bl_idname = "rbdlab.rm_constraint_group"
    bl_label = "Remove Constraint Group"
    bl_description = "Permanently deletes the constrinats from active group"
    bl_options = {'REGISTER', 'UNDO'}

    to_rm: StringProperty(default="")

    def mv_unexpected_obs_in_collection(self, context, const_coll, special_coll):

        # Objetos que no sean constraints que puedan estar en la collection de Constraints accidentalmente
        # Los desvinculamos de la collection de Constraints y los llevamos a 'Scene Collection' antes de 
        # borrar la collection de constraints:
        
        if len(const_coll.objects) <= 0:
            return
        
        for ob in const_coll.objects:
            
            if not ob.rigid_body_constraint: 

                # deslinko de donde esten, excepto de RigidBodyWorld
                for coll in ob.users_collection:
                    if coll.name != RBDLabNaming.RBD_WORLD:
                        coll.objects.unlink(ob)
                
                # lo linkamos en 'Scene Collection'
                context.scene.collection.objects.link(ob)

            else:
                
                # las quitamos de la collection especial de rbd constraints:
                bpy.data.collections[special_coll].objects.unlink(ob)


    def execute(self, context):

        start = datetime.now()

        # ocultar_post_panel_settings()

        rbdlab, tcoll_list = get_common_vars(context, get_rbdlab=True, get_tcoll_list=True)

        rbdlab_const= rbdlab.constraints
        active_group = rbdlab_const.get_group_item_by_name(self.to_rm)
        const_coll = active_group.collection

        # para poder eliminar los que tengan animacion del listado constwsitch:
        tcoll = tcoll_list.active
        if not tcoll:
            return {'CANCELLED'}
    
        constswitch_list = tcoll.rbdlab.constswitch_list   

        # 1. Iterar los chunks y quitarles la constraint.
        
        # group_id: str = active_group.idname
        # objects_to_remove = set()

        for chunk in active_group.chunk_list:
        
            if not chunk.object:
                continue
        
            ob = chunk.object

            # Eliminamos solo los constraints correspondientes al grupo que se va a eliminar:
            if RBDLabNaming.CONSTRAINTS in ob:

                constraints = ob[RBDLabNaming.CONSTRAINTS].split()
                
                for const in active_group.collection.objects:
                    const_name = const.name
                    if const_name in constraints:
                        constraints.remove(const_name)
                
                # actualizamos la lista:
                # print(ob.name, len(constraints))

                if len(constraints) < 1:
                    del ob[RBDLabNaming.CONSTRAINTS]
                else:
                    ob[RBDLabNaming.CONSTRAINTS] = " ".join(constraints)


            if RBDLabNaming.CONST_IS_ADJACENT in ob:
                del ob[RBDLabNaming.CONST_IS_ADJACENT]

            if RBDLabNaming.CLUSTER_ID in ob:
                del ob[RBDLabNaming.CLUSTER_ID]
                
            if RBDLabNaming.CONST_MAX_CONNECTIONS in ob:
                del ob[RBDLabNaming.CONST_MAX_CONNECTIONS]
            
            const_objects = ob.children
            if not const_objects:
                continue

        # Borrar los objetos de constraints.            

        # 2. Desactivar la visibilidad.
        # (para que progresivamente se borre el overlay)
        active_group.visible = False

        # si hay objetos q no debería estar en la collection de constraints .ConstraintGroup_Constraints:
        self.mv_unexpected_obs_in_collection(context, const_coll, RBDLabNaming.RBD_CONSTRAINTS)

        # 3. Borrar la collection.
        # print("Remove Colelction: " + const_coll.name)
        # si no eliminamos los objetos de bpy.data.objects es más rápido (aunque se queden en el limbo):
        remove_collection(context, const_coll, False)
        active_group.collection = None

        # eliminamos los items que tengan animacion en el listado constswitch:
        # necesito el item id del susodicho para eliminarlo:
        item_id = constswitch_list.get_item_from_active_group_id(active_group.idname)
        if item_id:
            # Lo quitamos del listado:
            constswitch_list.remove_item(item_id)
        
        # 4. Borrar el grupo desde rbdlab.constraints.
        rbdlab_const.remove_group(active_group)

        # si el main de constraints RBDLab_Constraints esta vacia la borramos:        
        const_main_coll = bpy.data.collections.get(RBDLabNaming.CONST_COLL)
        if const_main_coll:

            # si hay objetos q no debería estar en la collection de RBDLab_Constraints:
            self.mv_unexpected_obs_in_collection(context, const_main_coll, RBDLabNaming.CONST_COLL)

            # RBDLab_Constraints:
            if len(const_main_coll.children_recursive) == 0:
                remove_collection(context, const_main_coll)

        print("Remove Constraints End: " + str(datetime.now() - start))
        return {'FINISHED'}





