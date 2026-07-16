# from bpy.types import Panel
# from ..main.main_panel import MainPanel
from .resolution import resolution_section
from .collision import collision_section
from .gas import gas_section
from .fire import fire_section
from .collection import collection_section
from .cache import cache_section
from .weights import weights_section
from .display import display_section

'''
class SMOKE_PT_domain(Panel, ModulePanel):
    rbdlab_section = 'SMOKE'
    bl_label = "Domain"
    bl_parent_id = "SMOKE_PT_ui"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return context.scene.rbdlab.has_smoke()
'''


def draw_smoke_domain_ui(self, context, layout):
    # layout = self.layout
    rbdlab = context.scene.rbdlab
    # domain = rbdlab.get_smoke_domain(context)
    domain_mod = rbdlab.get_smoke_domain_mod(context)

    ui = rbdlab.ui

    # switcher categories domain
    bloque_switcher = layout.column(align=True)
    header = bloque_switcher.box().row(align=True)
    header.scale_y = 0.5
    header.prop(ui, "domain_subcategory_collapsable", text="Domain", emboss=False, icon='BLANK1')
    header2 = header.row(align=True)
    header2.alignment = 'RIGHT'
    header2.prop(ui, "domain_subcategory_collapsable", text="", emboss=False, icon='REMOVE'
                 if ui.domain_subcategory_collapsable else 'ADD')

    if ui.domain_subcategory_collapsable:
        switcher = bloque_switcher.grid_flow(row_major=True, columns=4, even_columns=True, even_rows=False, align=True)
        switcher.scale_y = 1.3
        switcher.prop(ui, "domain_sections", expand=True)
    else:
        switcher = bloque_switcher.grid_flow(row_major=True, columns=0, even_columns=True, even_rows=False, align=True)
        switcher.scale_y = 1.3
        switcher.prop(ui, "domain_sections", expand=True, text="")

    # end switcher categories domain
    layout.separator()

    if not domain_mod:
        layout.box().label(text="No domain modifier detected!", icon='ERROR')
        return

    # layout.label(text="Working with:" + domain.name)

    if ui.domain_sections == 'RESOLUTION':
        resolution_section(layout, ui, domain_mod)

    elif ui.domain_sections == 'COLLISION':
        collision_section(layout, ui, domain_mod)

    elif ui.domain_sections == 'GAS':
        gas_section(layout, ui, domain_mod)

    elif ui.domain_sections == 'FIRE':
        fire_section(layout, ui, domain_mod)

    elif ui.domain_sections == 'COLLECTION':
        collection_section(layout, ui, domain_mod)

    elif ui.domain_sections == 'CACHE':
        cache_section(rbdlab, layout, ui, domain_mod)

    elif ui.domain_sections == 'WEIGHTS':
        weights_section(layout, ui, domain_mod)

    elif ui.domain_sections == 'DISPLAY':
        display_section(layout, ui, domain_mod)

    # old ui:
    # layout.use_property_split = True
    # layout.use_property_decorate = False

    # is_baking_any = domain.is_cache_baking_any
    # has_baked_data = domain.has_cache_baked_data
    # has_baked_any = domain.has_cache_baked_any

    # ### GENERAL SETTINGS ###
    # section = layout.column(align=True)
    # section_header = section.box()
    # section_header.use_property_split = False
    # section_header.label(text="Settings", icon='SETTINGS')

    # section_content = section.box().column()
    # section_content.prop(domain, "resolution_max")
    # section_content.prop(domain, "time_scale")
    # section_content.prop(domain, "use_noise")
    # if domain.use_noise:
    #     section_content.prop(domain, "noise_scale")
    #     section_content.prop(domain, "noise_strength")

    # ### Dissolve ###
    # section_content = section.box().column()
    # section_content.prop(domain, "use_dissolve_smoke")
    # section_content.prop(domain, "use_dissolve_smoke_log", text="Slow")
    # section_content.prop(domain, "dissolve_speed")

    # ### BORDER COLLISION ###
    # section = layout.column(align=True)
    # section_header = section.box()
    # section_header.label(text="Border Collisions", icon='MOD_SOLIDIFY')
    # section_content = section.box()

    # flow = section_content.grid_flow(
    #     row_major=True, columns=0, even_columns=True, even_rows=False, align=False)
    # flow.enabled = not is_baking_any and not has_baked_data

    # col = flow.column()
    # col.prop(domain, "use_collision_border_front", text="Front")
    # col = flow.column()
    # col.prop(domain, "use_collision_border_back", text="Back")
    # col = flow.column()
    # col.prop(domain, "use_collision_border_right", text="Right")
    # col = flow.column()
    # col.prop(domain, "use_collision_border_left", text="Left")
    # col = flow.column()
    # col.prop(domain, "use_collision_border_top", text="Top")
    # col = flow.column()
    # col.prop(domain, "use_collision_border_bottom", text="Bottom")

    # ### ADAPTIVE DOMAIN ###
    # section = layout.column(align=True)
    # section.enabled = not is_baking_any and not has_baked_any
    # section_header = section.box()
    # section_header.use_property_split = False
    # section_header.prop(domain, "use_adaptive_domain",text="Adaptive Domain", icon='FULLSCREEN_ENTER')

    # if domain.use_adaptive_domain:
    #     section_content = section.box().column(align=True)
    #     section_content.prop(domain, "additional_res")
    #     section_content.prop(domain, "adapt_margin")
    #     section_content.prop(domain, "adapt_threshold")

    # ### VIEWPORT DISPLAY ###
    # section = layout.column(align=True)
    # section_header = section.box()
    # section_header.use_property_split = False
    # section_header.label(text="Viewport Display", icon='MESH_GRID')

    # section_content = section.box().column()
    # section_content.prop(domain, "display_thickness")
