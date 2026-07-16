from bpy.types import AddonPreferences
from bpy.props import BoolProperty, EnumProperty, IntProperty, StringProperty, FloatVectorProperty, FloatProperty
from ..Global.functions import get_folder_addon_name
from ..props.when_updating_property import rbdlab_cf_fast_exact_prefs_update, stats_on


class RBDLabAddonPreferences(AddonPreferences):
    bl_idname = get_folder_addon_name()

    switcher_preferences: EnumProperty(
        items=[
            ('FLIPBOOKS',   "Flipbooks",    "", 0),
            ('VIEWPORT',    "ViewPort",     "", 1),
            ('FRACTURE',    "Fracture",     "", 2),
            ('PHYSICS',     "Physics",      "", 3),
            ('MISC',        "Misc",         "", 4),
        ],
        default='MISC'
    )

    i_love_colors: BoolProperty(
        name="I love colors",
        default=True,
    )

    ground_in_wiremode: BoolProperty(
        name="Ground Viewport Display",
        default=False,
    )

    rbdlab_cf_fast_exact_prefs: EnumProperty(
        items=(
            ('FAST', "Fast", " "),
            ('EXACT', "Exact", ""),
        ),
        description="Fast or Exact methor for Booleans",
        default='FAST',
        update=rbdlab_cf_fast_exact_prefs_update

    )

    clear_single_output_collection_name_after_fracture: BoolProperty(
        name="Clear Single Output Collection Name after Fracture",
        default=True,
    )

    auto_add_sun_on_smoke_creation: BoolProperty(
        name="Create Automatic Sun whe create the Smoke",
        default=True,
    )
    move_originals: BoolProperty(
        default=True
    )
    substeps_per_frame: IntProperty(
        # default=8
        default=4
    )
    solver_iterations: IntProperty(
        default=10 # lo dejamos en 10 como estaban.
        # default=100 # cuando se usa constraints van mejor los constraints con 100
    )
    show_statistics: BoolProperty(
        default=True,
        update=stats_on
    )
    flipbooks_path: StringProperty(
        name="Flipbooks Output",
        default="",
        subtype='DIR_PATH'
    )
    flipbook_without_overlays: BoolProperty(
        default=True
    )
    use_flipbooks_in_subfolders: BoolProperty(
        default=True
    )
    use_flipbooks_in_subfolders_only_videos: BoolProperty(
        default=True
    )
    col_passives: FloatVectorProperty(
        name="Passive Color",
        size=4,
        precision=3,
        subtype='COLOR',
        min=0.0,
        max=1.0,
        default=[0.200000, 1.000000, 0.952000, 1.000000]
    )
    col_kinematics: FloatVectorProperty(
        name="Kinematic Color",
        size=4,
        precision=3,
        subtype='COLOR',
        min=0.0,
        max=1.0,
        default=[0.052939, 0.545719, 0.339969, 1.000000]
    )
    # col_activators: FloatVectorProperty(
    #     name="Activators Color",
    #     size=4,
    #     precision=3,
    #     subtype='COLOR',
    #     min=0.0,
    #     max=1.0,
    #     default=[1.000000, 0.716270, 0.100758, 1.000000]
    # )
    color_p_emiter_broken: FloatVectorProperty(
        name="Particle Emiter Inner Color",
        size=4,
        precision=3,
        subtype='COLOR',
        min=0.0,
        max=1.0,
        default=[0.900000, 0.255808, 0.188692, 1.000000]
    )
    color_p_emiter: FloatVectorProperty(
        name="Particle Emiter Color",
        size=4,
        precision=3,
        subtype='COLOR',
        min=0.0,
        max=1.0,
        default=[0.900000, 0.135315, 0.072000, 1.000000]
    )
    col_p_mute: FloatVectorProperty(
        name="Particle Mute Color",
        size=4,
        precision=3,
        subtype='COLOR',
        min=0.0,
        max=1.0,
        default=[0.650403, 0.251997, 0.848361, 1.000000]
    )
    col_p_collision: FloatVectorProperty(
        name="Particle Collision Color",
        size=4,
        precision=3,
        subtype='COLOR',
        min=0.0,
        max=1.0,
        default=[0.373370, 0.145184, 0.745902, 1.000000]
    )
    col_smoke: FloatVectorProperty(
        name="Smoke Color",
        size=4,
        precision=3,
        subtype='COLOR',
        min=0.0,
        max=1.0,
        default=[0.763283, 0.297028, 0.079419, 1.000000]
    )
    col_ground: FloatVectorProperty(
        name="Ground Color",
        size=4,
        precision=3,
        subtype='COLOR',
        min=0.0,
        max=1.0,
        default=[0.350000, 0.350000, 0.350000, 1.000000]
    )
    col_activator_actived: FloatVectorProperty(
        name="Activated Color",
        size=4,
        precision=3,
        subtype='COLOR',
        min=0.0,
        max=1.0,
        default=[1.000000, 0.018743, 0.017411, 1.000000]
    )
    rand_color_between_from: FloatProperty(
        name="Color random from",
        default=0.3,
        min=0,
        max=1.0
    )
    rand_color_between_to: FloatProperty(
        name="Color random to",
        default=0.6,
        min=0,
        max=1.0
    )
    autto_apply_preset: BoolProperty(
        default=True,
        description="Auto apply preset after choosing (only for RBDLab presets)"
    )
    materials_path: StringProperty(
        name="Materials Folder",
        default="",
        subtype='DIR_PATH'
    )

    def simplified_main_modules_update(self, context):
        scn = context.scene
        rbdlab = scn.rbdlab
        rbdlab.ui.collapse_module_selector = self.simplified_main_modules

    simplified_main_modules: BoolProperty(
        default=False,
        description="Simplified Main Modules by default",
        update=simplified_main_modules_update
    )
    cache_path: StringProperty(
        name="Cache Path",
        default="",
        subtype='DIR_PATH'
    )

    def draw(self, context):
        layout = self.layout

        layout.use_property_split = True
        layout.use_property_decorate = False
        # flow = layout.grid_flow(align=True)

        main_col = layout.column(align=True)

        switcher_props = main_col.row(align=True)
        switcher_props.use_property_split = False
        switcher_props.scale_y = 1.3
        switcher_props.prop(self, "switcher_preferences", expand=True)
        main_col.separator()

        if self.switcher_preferences == 'FLIPBOOKS':
            box0 = main_col.box()
            header = box0.column(align=True)
            header.label(text="Flipbooks:", icon='SEQ_PREVIEW')
            box1 = main_col.box()
            cont_col = box1.column(align=True)
            # content:
            row1 = cont_col.row(align=True)
            row1.prop(self, "flipbooks_path")
            cont_col.prop(self, "flipbook_without_overlays", text="Overlays Off when Flipbook Start")
            cont_col.prop(self, "use_flipbooks_in_subfolders", text="Use subfolders")

            if self.use_flipbooks_in_subfolders:
                cont_col.prop(self, "use_flipbooks_in_subfolders_only_videos", text="Only for img sequences")

        elif self.switcher_preferences == 'VIEWPORT':

            main_col = main_col.column(align=True)
            box0 = main_col.box()
            header = box0.column(align=True)
            header.label(text="ViewPort:", icon='VIEW3D')
            box1 = main_col.box()
            cont_col = box1.column(align=True)
            # content:
            # col.prop(self, "i_love_colors", text="I love colors")
            cont_col.prop(self, "show_statistics", text="Show Statistics in Viewport")
            cont_col.prop(self, "ground_in_wiremode", text="Ground Display in Wireframe Mode")

        elif self.switcher_preferences == 'FRACTURE':

            main_col = main_col.column(align=True)
            box0 = main_col.box()
            header = box0.column(align=True)
            header.label(text="Fracture:", icon='MOD_PHYSICS')
            box1 = main_col.box()
            cont_col = box1.column(align=True)
            # content:
            cont_col.prop(self, "clear_single_output_collection_name_after_fracture",
                          text="Clear Auto Name after Fracture")
            cont_col.prop(self, "move_originals", text="Move original objects to RBDLab_Originals collection")
            row = cont_col.row()
            row.prop(self, "rbdlab_cf_fast_exact_prefs", text="Boolean by Default", expand=True)

        elif self.switcher_preferences == 'PHYSICS':

            main_col = main_col.column(align=True)
            box0 = main_col.box()
            header = box0.column(align=True)
            header.label(text="Physics:", icon='PHYSICS')
            box1 = main_col.box()
            cont_col = box1.column(align=True)
            # content:
            cont_col.prop(self, "substeps_per_frame", text="Substeps by default")
            cont_col.prop(self, "solver_iterations", text="Solver Iterations by default")


            domain = main_col.box()
            domain.prop(self, "cache_path", text="Smoke Cache Path")

        elif self.switcher_preferences == 'MISC':

            main_col = main_col.column(align=True)
            box0 = main_col.box()
            header = box0.column(align=True)
            header.label(text="Misc:", icon='MATSHADERBALL')
            box1 = main_col.box()
            cont_col = box1.column(align=True)
            # content:

            # cont_col.prop(self, "materials_path", text="Materials Folder")
            # cont_col.separator()

            cont_col.prop(self, "simplified_main_modules", text="Display Main Modules Simplified")
            cont_col.prop(self, "autto_apply_preset", text="Auto apply preset")
            cont_col.prop(self, "auto_add_sun_on_smoke_creation", text="Create Automatic Sun whe create the Smoke")

            cont_row = cont_col.row(align=True)
            cont_row.prop(self, "rand_color_between_from", text="Random Color Between")
            cont_row.prop(self, "rand_color_between_to", text="")
            cont_col.prop(self, "col_passives", text="Passive Color")
            cont_col.prop(self, "col_kinematics", text="Kinematic Color")
            # cont_col.prop(self, "col_activators", text="Activators Includeds Color")

            # ahora se usa unos colores animados para la emision de particulas
            cont_col.prop(self, "color_p_emiter_broken", text="Particle Emitters Broken Color")
            cont_col.prop(self, "color_p_emiter", text="Particle Emitters Color")

            # cont_col.prop(self, "col_p_mute", text="Particle Mute Color")
            # cont_col.prop(self, "col_p_collision", text="Particle Collision Color")
            # cont_col.prop(self, "col_smoke", text="Smoke Emitters Color")
            cont_col.prop(self, "col_ground", text="Ground Color")

            # Activators -> Activation Color:
            cont_col.prop(self, "col_activator_actived", text="Activation Color")
