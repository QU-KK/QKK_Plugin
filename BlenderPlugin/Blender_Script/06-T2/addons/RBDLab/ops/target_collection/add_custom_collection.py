import bpy
from uuid import uuid4
from bpy.types import Operator, Collection, LayerCollection
from bpy.props import FloatProperty, EnumProperty
from ...addon.naming import RBDLabNaming
from ...Global.functions import set_active_collection_to_master_coll, set_active_collection_to_root_scn_coll, create_originals_coll_if_not_exist
from ..constraints.detect import calcute_chunks_neighbors


class RBDLAB_OT_add_custom_collection(Operator):
    bl_idname = "rbdlab.add_custom_collection"
    bl_label = "Add Custom Collection"
    bl_description = "Add custom collection"
    bl_options = {'REGISTER', 'UNDO'}

    search_method: EnumProperty(
        name="Neighbor Search Method",
        items=(
            # ('VERT', 'Vertices', "Use nearest vertices. (PRECISE in organic patterns, don't use for brick walls)"),
            ('CYTHON', 'Automatic', "Use automatic method powered by Cython. The fastest without losing any precision!"),
            ('VERT_KDTREE', 'Vertices', "Use nearest vertices. Really fast. (PRECISE in organic patterns, don't use for brick walls)"),
            # ('EDGE', 'Edges', "Use nearest edges. (SLOWEST BUT PRECISE IN ALMOST EVERY CASE)"),
            ('BBOX', 'Bounding Box', "Use bounding box intersection between the chunks. (FASTEST, really nice for brick walls or similar)")
        ),
        default='CYTHON'
    )
    virtual_cube_threshold: FloatProperty(
        min=0.0001, max=0.1, default=0.001, precision=4, step=1 / 1000, name="Neighbors Threshold",
        description="Distance threshold to consider a chunk is neighbor of another chunk")

    def recursive_find_and_unlink_coll(self, root_child, input_coll):
        RBDLab = RBDLabNaming._RBDLab_name  # to ignore find in this collection

        if isinstance(root_child, LayerCollection):
            root_target_coll = root_child.collection
            self.recursive_find_and_unlink_coll(root_target_coll, input_coll)

        elif isinstance(root_child, Collection):
            childrens = root_child.children

            for child in childrens:

                if child.name == RBDLab:
                    continue

                if input_coll in child.children_recursive:
                    self.recursive_find_and_unlink_coll(child, input_coll)
                else:
                    if child.name == input_coll.name:
                        root_child.children.unlink(child)

    def execute(self, context):
        scn = context.scene
        rbdlab = scn.rbdlab

        ui = rbdlab.ui
        input_coll = ui.custom_collections

        tcoll_list = rbdlab.lists.target_coll_list

        if input_coll:

            all_colls = tcoll_list.get_all_target_collections

            if input_coll not in all_colls:
                previous_selection = context.selected_objects

                set_active_collection_to_master_coll(context)

                # Si no existe la collection RBDLab_Originals, la creamos:
                originals_coll = create_originals_coll_if_not_exist(context, rbdlab)

                # unlink recursivo:
                scn_collection = scn.view_layers[context.view_layer.name].layer_collection
                self.recursive_find_and_unlink_coll(scn_collection, input_coll)

                # y la linkeamos a RBDLab root:
                if input_coll not in rbdlab.root_collection.children_recursive:
                    rbdlab.root_collection.children.link(input_coll)
                
                if RBDLabNaming.CUSTOM_COLL not in input_coll:
                    input_coll[RBDLabNaming.CUSTOM_COLL] = True
                
                # agregamos el Target collection:
                tcoll_list.add_tcoll(input_coll)

                # devuelvo el foco a la Scene Collection:
                set_active_collection_to_root_scn_coll(context)

                # Calcular neighbors para custom collection.
                valid_objects = [obj for obj in input_coll.objects if obj.type == 'MESH' and obj.visible_get()]

                if valid_objects:

                    collection_id = uuid4().hex
                    input_coll[RBDLabNaming.COLLECTION__COLL_ID] = collection_id

                    bpy.ops.object.select_all(action='DESELECT')

                    # para las partes del addon que se utilice el from:
                    for ob in valid_objects:
                        ob[RBDLabNaming.FROM] = "Custom"
                        ob.select_set(True)
                        ob[RBDLabNaming.OBJECT__COLL_ID] = collection_id

                    # set origin to volume:
                    if context.selected_objects:
                        context.view_layer.objects.active = valid_objects[0]
                        # bpy.ops.object.origin_set(type='ORIGIN_CENTER_OF_VOLUME', center='MEDIAN')
                        bpy.ops.object.origin_set(type='ORIGIN_CENTER_OF_MASS', center='MEDIAN')

                    # restauro la seleccion anterior:
                    if previous_selection:
                        bpy.ops.object.select_all(action='DESELECT')
                        for ob in previous_selection:
                            ob.select_set(True)
                            print(ob.name)

                    # Calculando vecinos:
                    calcute_chunks_neighbors(
                                                context, 
                                                valid_objects, 
                                                search_method=self.search_method,
                                                virtual_cube_threshold=self.virtual_cube_threshold
                                            )
                    # Marcamos como que se computaron los vecinos:
                    input_coll[RBDLabNaming.COMPUTED_NEIGHBORS] = True

            else:
                self.report({'WARNING'}, input_coll.name + "Already in Target Collections!!")
                return {'CANCELLED'}

        else:
            self.report({'WARNING'}, "No collection has been specified!!")
            return {'CANCELLED'}

        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=250)

    def draw(self, context):
        scn = context.scene
        rbdlab = scn.rbdlab
        rbdlab_const = rbdlab.constraints
        ui = rbdlab.ui

        layout = self.layout
        layout.scale_y = 1.2

        layout.prop(ui, "custom_collections", text="Collection")

        col = layout.column(align=True)
        col.row(align=True).prop(self, "search_method", expand=True, text='Method')

        if self.search_method != 'BBOX':
            col.prop(self, "virtual_cube_threshold", slider=True, text="Threshold")
        else:
            col.prop(rbdlab_const, "bbox_offset_unified")

