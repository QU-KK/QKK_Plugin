import bpy
from ...Global.functions import (
    deselect_all_objects,
    select_object,
    create_new_collection,
)
from bpy.types import Operator
from bpy.props import StringProperty
from ...addon.naming import RBDLabNaming
from ...Global.get_common_vars import get_common_vars


class RBDLAB_OT_particles_emitters_to_coll_for_compositor(Operator):
    bl_idname = "rbdlab.particles_emitters_to_coll_for_compositor"
    bl_label = "Particle emitters to collection for compositor"

    collection_custom_name_emitter_for_compo: StringProperty(
        name="Collection name",
        default=""
    )

    @classmethod
    def poll(cls, context):
        return context.scene.rbdlab.filtered_target_collection is not None

    @classmethod
    def description(cls, _context, properties):
        return "Link particle emitters to new collection for use in compositing"

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        col = layout.column()
        col.label(text="Name for compositor collection:")
        col.prop(self, "collection_custom_name_emitter_for_compo", text="Name")

    def execute(self, context):

        tcoll_list = get_common_vars(context, get_tcoll_list=True)
        tcoll = tcoll_list.active

        if tcoll:
            coll_name = tcoll.name
            if coll_name:

                # si estamos visualizando metal, lo cambio a chunks para poder trabajar:
                tcoll_item = tcoll_list.active_item
                metal_list = tcoll_item.metal_list
                current_metal = metal_list.active

                if current_metal:
                    metal_previous_state = current_metal.metal_or_fractures
                    if 'FRACTURES' not in metal_previous_state:
                        current_metal.metal_or_fractures = {'FRACTURES'}

                deselect_all_objects(context)

                for obj in bpy.data.collections[coll_name].objects:
                    if RBDLabNaming.INNER_EMISOR in obj:
                        select_object(context, obj)

                if context.selected_objects:
                    coll_name_for_compositor = self.collection_custom_name_emitter_for_compo
                    if coll_name_for_compositor not in bpy.data.collections:
                        create_new_collection(context, coll_name_for_compositor)

                    if coll_name_for_compositor in bpy.data.collections:
                        for ob in context.selected_objects:
                            bpy.data.collections[coll_name_for_compositor].objects.link(ob)

                deselect_all_objects(context)

                # restauro la visibilidad del metal:
                if current_metal and metal_previous_state:
                    current_metal.metal_or_fractures = metal_previous_state

                return {'FINISHED'}
            else:
                self.report({'WARNING'}, "Target Collection is Empty!")
                return {'CANCELLED'}
        else:
            self.report({'WARNING'}, "Target Collection is Empty!")
            return {'CANCELLED'}
