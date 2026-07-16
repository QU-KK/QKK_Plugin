import bpy
from bpy.types import Operator, Object
from .......Global.basics import deselect_all_objects, set_active_object #, ocultar_post_panel_settings
from .......addon.naming import RBDLabNaming


class RBDLAB_OT_join_by_selection(Operator):
    bl_idname = "rbdlab.join_by_selection"
    bl_label = "Join chunks"
    bl_description = "Join Selected chunks"
    bl_options = {'REGISTER', 'UNDO'}

    def store_neighbours_and_childrens(self, context, active_ob: Object, selected_chunks: list[Object]) -> None:

        # Creamos un diccionario vacío que servirá como nuestro objeto JSON final:
        combined_dict = {}

        # Creamos una clave "neighbours" y otra "childrens" en el diccionario combinado:
        for key in ["names", "neighbours", "childrens"]:
            combined_dict[key] = {}

        for ob_sel in selected_chunks:
            location_id = f"{ob_sel.location.x:.6f},{ob_sel.location.y:.6f},{ob_sel.location.z:.6f}"

            combined_dict["names"].setdefault(location_id, [ob_sel.name])

            # Guardamos las custom propertiesde cada chunk:
            custom_properties = [cp for cp in list(ob_sel.keys()) if cp.lower().startswith("neighbour_")]
            for cp in custom_properties:
                combined_dict["neighbours"].setdefault(location_id, [cp])

            # Guardamos los hijos de cada objeto:
            combined_dict["childrens"].setdefault(location_id, [child.name for child in ob_sel.children])

            # Emparentamos el objeto a al nuevo unido:
            for child_ob in ob_sel.children:
                child_ob.parent = active_ob
                child_ob.matrix_parent_inverse = active_ob.matrix_world.inverted()

        # Actualizamos el campo correspondiente en el objeto activo (active_ob) con el JSON combinado:
        active_ob[RBDLabNaming.JOIN_SEPARATE_DATA] = combined_dict

        return combined_dict

    def execute(self, context):
        scn = context.scene
        rbdlab = scn.rbdlab

        scn.frame_set(scn.frame_start)

        rbd_props = rbdlab.physics.rigidbodies

        tcoll_list = rbdlab.lists.target_coll_list
        chunks = tcoll_list.get_current_active_tcoll_valild_objects(context)

        if chunks:

            joineds = [ob for ob in chunks if ob.select_get() and RBDLabNaming.JOINED in ob]
            if joineds:
                self.report({'WARNING'}, "Any object are already joinde!")
                return {'CANCELLED'}

            selected_chunks = [ob for ob in chunks if ob.select_get()]

            if selected_chunks:
                # ocultar_post_panel_settings()
                deselect_all_objects(context)
                [ob.select_set(True) for ob in selected_chunks]
                active_ob = selected_chunks[0]
                set_active_object(context, active_ob)

                combined_dict = self.store_neighbours_and_childrens(context, active_ob, selected_chunks)

                bpy.ops.object.join()
                # bpy.ops.object.origin_set(type='ORIGIN_CENTER_OF_VOLUME', center='MEDIAN')
                bpy.ops.object.origin_set(type='ORIGIN_CENTER_OF_MASS', center='MEDIAN')

                for neighbours in combined_dict["neighbours"].values():
                    # los values de neighbours son listas:
                    for neighbour in neighbours:

                        if neighbour not in active_ob:
                            active_ob[neighbour] = 1.0

                            # agregamos los neighbours en el data:
                            # por ejemplo neighbour  tiene dentro "neighbour_Cube_cell.001" y así, por eso le quito con replace:
                            # neighbour_ob = bpy.data.objects.get(neighbour.replace("neighbour_", ""))
                            # if neighbour_ob:
                            #     active_ob.neighbor_chunks.add_neighbor(neighbour_ob)

                            # los IDProperty solo soportan 63 chars y algunos neigbours superaban el limite, por 
                            # eso ahora lo busco con startswitch:
                            for neighbour_ob in bpy.data.objects:
                                if neighbour_ob.name.startswith(neighbour):
                                    active_ob.neighbor_chunks.add_neighbor(neighbour_ob)


                if active_ob.rigid_body:
                    bpy.ops.rigidbody.mass_calculate(material=rbd_props.avalidable_mass)
                    active_ob.rigid_body.collision_shape = 'MESH'
                    active_ob[RBDLabNaming.JOINED] = True

                # les recalculamos la masa:
                if RBDLabNaming.CURRENT_MASS in active_ob:
                    material_type = active_ob[RBDLabNaming.CURRENT_MASS].title()

                    if material_type == "Custom":
                        bpy.ops.rigidbody.mass_calculate(material="Custom", density=rbd_props.custom_mass)
                    else:
                        bpy.ops.rigidbody.mass_calculate(material=material_type)

            else:
                self.report({'ERROR'}, "Not valid selected objects!")

        return {'FINISHED'}
