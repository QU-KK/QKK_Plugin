import bpy
from bpy.types import Operator
# from ....ops_common_functions import ops_multiline_print
# from .....Global.basics import deselect_all_objects, set_active_object, ocultar_post_panel_settings
from .......addon.naming import RBDLabNaming


class RBDLAB_OT_separate_by_selection(Operator):
    bl_idname = "rbdlab.separate_by_selection"
    bl_label = "Separate chunks"
    bl_description = "Separate Selected"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scn = context.scene
        # rbdlab = scn.rbdlab

        scn.frame_set(scn.frame_start)

        active_ob = context.active_object

        if RBDLabNaming.JOINED not in active_ob:
            self.report({'WARNING'}, "This object dont are joined!")
            return {'CANCELLED'}

        if active_ob:

            combined_dict = active_ob[RBDLabNaming.JOIN_SEPARATE_DATA].to_dict()

            bpy.ops.mesh.separate(type='LOOSE')
            # bpy.ops.object.origin_set(type='ORIGIN_CENTER_OF_VOLUME', center='MEDIAN')
            bpy.ops.object.origin_set(type='ORIGIN_CENTER_OF_MASS', center='MEDIAN')

            # primero eliminamos todos los neighbours heredados:
            for ob_sel in context.selected_objects:
                location_id = f"{ob_sel.location.x:.6f},{ob_sel.location.y:.6f},{ob_sel.location.z:.6f}"

                custom_properties = [cp for cp in list(ob_sel.keys()) if cp.lower().startswith("neighbour_")]
                for cp in custom_properties:
                    del ob_sel[cp]
                    # Eliminamos los neighbour del data:
                    ob_sel.neighbor_chunks.chunks.clear()

            # despues restauramos los neighbours que tenemos guardados por coordenadas:
            for ob_sel in context.selected_objects:

                location_id = f"{ob_sel.location.x:.6f},{ob_sel.location.y:.6f},{ob_sel.location.z:.6f}"

                if location_id in combined_dict["neighbours"].keys():
                    for neighbours in combined_dict["neighbours"].values():
                        # los values de neighbours son listas:
                        for neighbour in neighbours:

                            ob_sel[neighbour] = 1.0

                            # y guardamos sus neighbour del data:
                            # neighbour_ob = bpy.data.objects.get(neighbour.replace("neighbour_", ""))
                            # if neighbour_ob:
                            #     ob_sel.neighbor_chunks.add_neighbor(neighbour_ob)

                            # los IDProperty solo soportan 63 chars y algunos neigbours superaban el limite, por 
                            # eso ahora lo busco con startswitch:
                            for neighbour_ob in bpy.data.objects:
                                if neighbour_ob.name.startswith(neighbour):
                                    ob_sel.neighbor_chunks.add_neighbor(neighbour_ob)

                    if ob_sel.rigid_body:
                        ob_sel.rigid_body.collision_shape = 'CONVEX_HULL'

                # restauramos los nombres:
                # al estar usando las coordenadas para volver a vincularlos, si el usuario mueve los chunks luego no podra relacionarlos
                print("loc ids:", location_id, combined_dict["names"].keys())
                if location_id in combined_dict["names"].keys():
                    if location_id in combined_dict["names"].keys():
                        for name in combined_dict["names"][location_id]:
                            # print("***", name, ob_sel.name)
                            ob_sel.name = name

                # restauramos los childrens y lo emparentamos:
                if location_id in combined_dict["childrens"].keys():
                    for child_name in combined_dict["childrens"][location_id]:
                        # print("***", child_name, ob_sel.name)
                        child_ob = bpy.data.objects.get(child_name)
                        if child_ob:
                            child_ob.parent = ob_sel
                            child_ob.matrix_parent_inverse = ob_sel.matrix_world.inverted()

                if RBDLabNaming.JOIN_SEPARATE_DATA in ob_sel:
                    del ob_sel[RBDLabNaming.JOIN_SEPARATE_DATA]

                if RBDLabNaming.JOINED in ob_sel:
                    del ob_sel[RBDLabNaming.JOINED]

            # les recalculamos la masa:
            bpy.ops.rigidbody.mass_calculate(material=active_ob[RBDLabNaming.CURRENT_MASS].title())

        else:
            self.report({'ERROR'}, "No active object!")

        return {'FINISHED'}
