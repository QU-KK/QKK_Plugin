from bpy.types import Panel
from ..main.module_panel import ModulePanel
from ...addon.icons import get_icon
from ...addon.naming import RBDLabNaming
import os


class MATERIALS_PT_ui(Panel, ModulePanel):
    rbdlab_section = 'MATERIALS'
    bl_label = "Poly Haven Materials"
    bl_idname = "MATERIALS_PT_ui"

    def draw_header(self, context):
        self.layout.label(text="", icon_value=get_icon("PolyHeaven_Logo_256"))

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        rbdlab = scene.rbdlab

        col_preview = layout.column(align=True)
        col_preview.use_property_split = True
        col_preview.use_property_decorate = False

        # if len(rbdlab.thumbnails.categories) > 0 and len(rbdlab.thumbnails.active) > 0:
        if len(rbdlab.thumbnails.categories) > 0:
            # categories:
            col_preview.use_property_split = False

            prev_cont = col_preview.column(align=True)
            row = prev_cont.row(align=True).box()
            row.scale_y = 1.1
            row.prop(rbdlab.thumbnails, "categories", text="Category")

            # title preview:
            file = rbdlab.thumbnails.active
            filename = os.path.splitext(os.path.basename(file))[0].replace("_", " ").title()
            if filename:
                row = prev_cont.row(align=True).box()
                # row.alert = True
                row.label(text=filename, icon='MATERIAL')

            # material preview:
            row = prev_cont.row(align=True).box()
            row.template_icon_view(rbdlab.thumbnails, "active")
            col = row.column(align=True)
            col.scale_y = 1.2
            col.prop(context.space_data.shading, "studiolight_rotate_z")

            col_preview.separator()

            # by selection/collection:
            col = prev_cont.box().column(align=True)
            row = col.row(align=True)
            row.scale_y = 1.3
            row.prop(rbdlab.thumbnails, "by_selection", text="By selection", expand=True)

            # Collection List:
            if rbdlab.thumbnails.by_selection == 'COLLECTION':

                rbdlab_materials = rbdlab.materials

                col = prev_cont.column(align=True)
                row = col.row(align=True)

                section = col.column(align=True)
                section.use_property_split = False
                header = section.box().row(align=True)
                header.label(text="Source Collections", icon='GROUP')

                if not rbdlab_materials.list:
                    content = section.box().column(align=True)
                    content.scale_y = 2
                    content.operator("rbdlab.materials_init_collections", text="Load Collections", icon='FILE_REFRESH')
                    # content.label(text="hola1")
                else:
                    header.operator("rbdlab.materials_init_collections", text="", icon='FILE_REFRESH')
                    section.template_list(
                        "MAT_UL_work_group",
                        "",
                        rbdlab_materials,
                        "coll_list",
                        rbdlab_materials,
                        "list_index",
                        rows=4
                    )
                    # section.label(text="hola2")

                # para los outer/Inner:
                row = col.box().row(align=True)
            else:
                # para los outer/Inner:
                row = col.row(align=True)

            row.scale_y = 1.3
            row.prop(rbdlab.thumbnails, "inner_or_outer", text="Assign to", expand=True)

            # assign operator
            col_buttons = prev_cont.box().column(align=True)
            # col_buttons = col_preview.column(align=True)
            col_buttons.operator("rbdlab.assign_materials", text="Assing Material")
            col_buttons.scale_y = 1.5

        else:
            # feedback bad path
            col = col_preview.column(align=True)
            col.alert = True
            col.label(text="Set a valid path for materials in preferences")

        if context.active_object:
            layout.template_list("MAT_UL_dynamic_materials", "", context.active_object,
                                 "material_slots", context.active_object, "active_material_index", rows=3)


class MaterialButtonsPanel:
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "material"
    # COMPAT_ENGINES must be defined in each subclass, external engines can add themselves here

    @classmethod
    def poll(cls, context):
        mat = context.material
        return mat and (context.engine in cls.COMPAT_ENGINES) and not mat.grease_pencil


class RBDLAB_PT_materials_properties(MaterialButtonsPanel, Panel):
    bl_label = RBDLabNaming._RBDLab_name
    bl_context = "material"
    bl_options = {'DEFAULT_CLOSED'}
    COMPAT_ENGINES = {'BLENDER_EEVEE', 'CYCLES'}

    @classmethod
    def poll(cls, context):
        engine = context.engine
        mat = context.material
        return mat and mat.use_nodes and (engine in cls.COMPAT_ENGINES) and not mat.grease_pencil

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True

        obj = context.active_object
        if obj.type == 'MESH':
            mat = obj.material_slots[obj.active_material_index]
            current_inner_mat = None

            for m in obj.material_slots:
                if RBDLabNaming.INNER_MAT_TAG in m.material:
                    current_inner_mat = m.name

            box = layout.column(align=True).box()
            msg = box.row(align=True)

            label1 = "Active mat: "
            msg.label(text=label1)
            msg2 = msg.row(align=True)
            msg2.alert = True
            msg2.label(text="[ " + mat.name + " ]")
            ancho_panel = context.region.width
            result = abs((ancho_panel+len(label1))/100)
            # print(result)
            msg2.scale_x = result

            if current_inner_mat:
                box.label(text="Current Inner Material is: " + current_inner_mat)

            msg3 = box.row(align=True)
            msg3.label(text="Only one material at a time can be declared as inner material.", icon='INFO')

            button = box.row(align=True)
            button.scale_y = 1.3
            button.operator("rbdlab.set_current_material_to_rbdlab_inner_mat",
                            text="Set Active material in to RBDLAB Inner Material")
