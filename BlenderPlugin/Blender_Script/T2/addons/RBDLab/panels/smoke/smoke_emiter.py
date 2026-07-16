from bpy.types import Panel
from ..main.module_panel import ModulePanel

'''
class SMOKE_PT_emiter(Panel, ModulePanel):
    rbdlab_section = 'SMOKE'
    bl_label = "Emiter"
    bl_parent_id = "SMOKE_PT_ui"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return context.scene.rbdlab.has_smoke()
'''


def draw_smoke_flow_ui(self, context, layout):
    # layout = self.layout
    rbdlab = context.scene.rbdlab
    smoke_props = rbdlab.smoke
    smoke_emiter = smoke_props.emiter

    layout.use_property_split = True
    layout.use_property_decorate = False

    ### SETTINGS ###
    section = layout.column(align=True)
    section_header = section
    section_header.box().label(text="%s Settings" % smoke_emiter.flow_type.capitalize(), icon='MOD_FLUID')

    section_content = section.box().column(align=True)

    section_content.prop(smoke_emiter, "flow_type", text="Flow Type")
    section_content.separator()
    section_content.prop(smoke_emiter, "subframes", text="Sampling Substeps")

    if smoke_emiter.flow_type != 'FIRE':
        section_content.prop(smoke_emiter, "smoke_color", text="Smoke Color")

    section_content.separator()
    section_content.prop(smoke_emiter, "temperature", text="Initial Temperature")
    section_content.prop(smoke_props, "density_multiplier", text="Density",
                         icon='OUTLINER_OB_VOLUME', expand=True)
    
    if smoke_emiter.flow_type != 'SMOKE':
        section_content.prop(smoke_props, "fuel_multiplier", text="Fuel", icon='OUTLINER_OB_VOLUME', expand=True)


    # col.prop(smoke_emiter, "density", text="Density") # para futuro parche
    # col.prop(smoke_emiter, "density_vertex_group", text="Vertex Group")
    # col.prop(smoke_emiter, "particle_size", text="Particle Size")

    ### FLOW SOURCE ###
    section = layout.column(align=True)
    section_header = section.box()
    section_header.use_property_split = False
    section_header.label(text="Source", icon='SETTINGS')

    section_content = section.box()
    col = section_content.column(align=True)
    if not context.scene.rbdlab.has_smoke_ps():
        info = col.row()
        # info.alert = True
        info.box().label(
            text="To emit from particles, create Smoke Particles", icon='INFO')
    
    col.separator()
    col.prop(smoke_emiter, "flow_source", text="Emit from")

    if smoke_emiter.flow_source == 'MESH':
        col = section_content.column(align=True)
        col.prop(smoke_emiter, "surface_distance", text="Surface Emission")
        col.prop(smoke_emiter, "volume_density", text="Volume Emission")
    else:
        col = section_content.column()
        col.prop(smoke_emiter, "particle_size", text="Particle Size")

    ### VELOCITY ###
    section = layout.column(align=True)
    section_header = section.box()
    section_header.use_property_split = False
    section_header.scale_y = 1.3
    section_header.prop(smoke_emiter, "use_initial_velocity", icon='NORMALIZE_FCURVES', text="Use Initial Velocity")

    if smoke_emiter.use_initial_velocity:
        section_content = section.box()
        section_content.prop(
            smoke_emiter, "velocity_factor", text="Source")

        if smoke_emiter.flow_source == 'MESH':
            section_content.prop(smoke_emiter, "velocity_normal")
            col = section_content.column()
            col.prop(smoke_emiter, "velocity_coord", text="Initial Coords")

    layout.separator()
    smoke_update = layout.row(align=True)
    smoke_update.scale_y = 1.3
    # TODO: Actualizar el operator idname de aquí cuando se haga el smoke.update_emiter.
    smoke_update.operator("rbdlab.smoke_update_emiter", text="Update", icon='FILE_REFRESH')
