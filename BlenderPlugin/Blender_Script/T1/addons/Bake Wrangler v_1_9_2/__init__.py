'''
Copyright (C) 2019-2023 Dancing Fortune Software All Rights Reserved

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
'''

bl_info = {
    'name': 'Bake Wrangler',
    'description': 'Bake Wrangler aims to improve all baking tasks with a node based interface and provides additional bake passes',
    'author': 'DFS',
    'version': (1, 9, 2),
    'blender': (4, 4, 0),
    'location': 'Editor Type > Bake Node Editor',
    #"warning": "Beta Version",
    'doc_url': 'https://bake-wrangler.readthedocs.io',
    "tracker_url": "https://blenderartists.org/t/bake-wrangler-node-based-baking-tool-set/",
    "support": "COMMUNITY",
    'category': 'Baking'}


import bpy
from . import nodes
from . import status_bar


# Preferences
class BakeWrangler_Preferences(bpy.types.AddonPreferences):
    bl_idname = __package__
    
    def update_icon(self, context):
        if not self.show_icon:
            status_bar.status_bar_icon.disable_bw_icon()
        else:
            status_bar.status_bar_icon.ensure_bw_icon()
            
    # Message prefs
    show_icon: bpy.props.BoolProperty(name="Show BW Icon in Status Bar", description="Shows an icon that changes color based on baking state and can be clicked on to bring up the log", default=True, update=update_icon)
    text_msgs: bpy.props.BoolProperty(name="Messages to Text editor", description="Write messages to a text block in addition to the console", default=True)
    clear_msgs: bpy.props.BoolProperty(name="Clear Old Messages", description="Clear the text block before each new bake", default=True)
    wind_msgs: bpy.props.BoolProperty(name="Open Text in new Window", description="A new window will be opened displaying the text block each time a new bake is started", default=False)
    wind_close: bpy.props.BoolProperty(name="Auto Close Text Window", description="Close the text window on successful bake completion", default=False)
    
    # Node prefs
    show_node_prefs: bpy.props.BoolProperty(name="Node Defaults", description="Default general node options", default=False)
    def_filter_mesh: bpy.props.BoolProperty(name="Meshes", description="Show mesh type objects", default=True)
    def_filter_curve: bpy.props.BoolProperty(name="Curves", description="Show curve type objects", default=True)
    def_filter_surface: bpy.props.BoolProperty(name="Surfaces", description="Show surface type objects", default=True)
    def_filter_meta: bpy.props.BoolProperty(name="Metas", description="Show meta type objects", default=True)
    def_filter_font: bpy.props.BoolProperty(name="Fonts", description="Show font type objects", default=True)
    def_filter_light: bpy.props.BoolProperty(name="Lights", description="Show light type objects", default=True)
    def_filter_collection: bpy.props.BoolProperty(name="Collections", description="Toggle only collections", default=False)
    def_show_adv: bpy.props.BoolProperty(name="Expand Advanced Settings", description="Expand advanced settings on node creation instead of starting with them collapsed", default=False)
    invert_bakemod: bpy.props.BoolProperty(name="Invert Selected in Bake Modifiers", description="Inverts the selection method used by the Bake Modifiers option from ignoring viewport hidden modifiers to baking them", default=False)

    # Render prefs
    show_render_prefs: bpy.props.BoolProperty(name="Render Defaults", description="Default settings for rendering options", default=False)
    def_samples: bpy.props.IntProperty(name="Default Bake Samples", description="The number of samples per pixel that new Pass nodes will be set to when created", default=1, min=1)
    def_xres: bpy.props.IntProperty(name="Default Bake X Resolution", description="The X resolution new Pass nodes will be set to when created", default=1024, min=1, subtype='PIXEL')
    def_yres: bpy.props.IntProperty(name="Default Bake Y Resolution", description="The Y resolution new Pass nodes will be set to when created", default=1024, min=1, subtype='PIXEL')
    def_device: bpy.props.EnumProperty(name="Default Device", description="The render device new Pass nodes will be set to when created", items=nodes.node_tree.BakeWrangler_PassSettings.cycles_devices, default='CPU')
    def_raydist: bpy.props.FloatProperty(name="Default Ray Distance", description="The ray distance that new Mesh nodes will use when created", default=0.01, step=1, min=0.0, unit='LENGTH')
    def_max_ray_dist: bpy.props.FloatProperty(name="Default Max Ray Dist", description="The max ray distance that new Mesh nodes will use when created", default=0.0, step=1, min=0.0, unit='LENGTH')
    def_margin: bpy.props.IntProperty(name="Default Margin", description="The margin that new Mesh nodes will use when created", default=0, min=0, subtype='PIXEL')
    def_mask_margin: bpy.props.IntProperty(name="Default Mask Margin", description="The mask margin that new Mesh nodes will use when created", default=0, min=0, subtype='PIXEL')
    ignore_vis: bpy.props.BoolProperty(name="Objects Always Visible", description="Enable to ignore the visibility of selected objects when baking, making them visible regardless of settings in blender", default=False)

    # Ouput prefs
    show_output_prefs: bpy.props.BoolProperty(name="Output Defaults", description="Default settings for output options", default=False)
    def_format: bpy.props.EnumProperty(name="Default Output Format", description="The format new Output nodes will use when created", items=nodes.node_tree.BakeWrangler_OutputSettings.img_format, default='PNG')
    def_xout: bpy.props.IntProperty(name="Default Output X Resolution", description="The X resolution new Output nodes will be set to when created", default=1024, min=1, subtype='PIXEL')
    def_yout: bpy.props.IntProperty(name="Default Output Y Resolution", description="The Y resolution new Output nodes will be set to when created", default=1024, min=1, subtype='PIXEL')
    def_outpath: bpy.props.StringProperty(name="Default Output Path", description="The path new Output nodes will use when created", default="", subtype='DIR_PATH')
    def_outname: bpy.props.StringProperty(name="Default Output Name", description="The name new Output nodes will use when created", default="Image", subtype='FILE_NAME')
    make_dirs: bpy.props.BoolProperty(name="Create Paths", description="If selected path doesn't exist, try to create it", default=False)
    auto_open: bpy.props.BoolProperty(name="Auto open bakes", description="Automatically open the baked image in blender if it isn't already open", default=True)
    save_packed: bpy.props.BoolProperty(name="Save packed images", description="Prior to baking, save any packed images with changes or they will not apply during the bake", default=False)
    save_images: bpy.props.BoolProperty(name="Save unpacked images", description="Prior to baking, save any unpacked images with changes or they will not apply during the bake", default=False)
    img_non_color: bpy.props.EnumProperty(name="Non-Color", description="Color space to use as non-color when alternative color spaces are in use", items=nodes.node_tree.BakeWrangler_OutputSettings.img_color_spaces)
    
    # Performance prefs
    fact_start: bpy.props.BoolProperty(name="Disable Add-ons", description="Disable add-ons in the background baking instance (faster load times and some 3rd party add-ons can crash the process)", default=True)
    retry: bpy.props.BoolProperty(name="Retry", description="On bake failure retry so long as progress is made each time", default=False)
    
    # Dev prefs
    debug: bpy.props.BoolProperty(name="Debug", description="Enable additional debugging output", default=False)

    def draw(self, context):
        layout = self.layout
        colprefs = layout.column(align=False)

        coltext = colprefs.column(align=False)
        coltext.prop(self, "show_icon")
        coltext.prop(self, "text_msgs")
        if self.text_msgs:
            box = coltext.box()
            box.prop(self, "clear_msgs")
            box.prop(self, "wind_msgs")
            row = box.row(align=True)
            row.label(icon='THREE_DOTS')
            row.prop(self, "wind_close")
            if self.wind_msgs:
                row.enabled = True
            else:
                row.enabled = False

        # Node prefs
        box = colprefs.box()
        if not self.show_node_prefs:
            box.prop(self, "show_node_prefs", icon="DISCLOSURE_TRI_RIGHT", emboss=False)
        else:
            box.prop(self, "show_node_prefs", icon="DISCLOSURE_TRI_DOWN", emboss=False)
            col = box.column(align=False)
            row = col.row(align=True)
            row.alignment = 'LEFT'
            row.label(text="Filter:")
            row1 = row.row(align=True)
            row1.alignment = 'LEFT'
            row1.prop(self, "def_filter_mesh", text="", icon='MESH_DATA')
            row1.prop(self, "def_filter_curve", text="", icon='CURVE_DATA')
            row1.prop(self, "def_filter_surface", text="", icon='SURFACE_DATA')
            row1.prop(self, "def_filter_meta", text="", icon='META_DATA')
            row1.prop(self, "def_filter_font", text="", icon='FONT_DATA')
            row1.prop(self, "def_filter_light", text="", icon='LIGHT_DATA')
            if self.def_filter_collection:
                row1.enabled = False
            row2 = row.row(align=False)
            row2.alignment = 'LEFT'
            row2.prop(self, "def_filter_collection", text="", icon='GROUP')
            col.prop(self, "def_show_adv")
            col.prop(self, "invert_bakemod")

        # Render prefs
        box = colprefs.box()
        if not self.show_render_prefs:
            box.prop(self, "show_render_prefs", icon="DISCLOSURE_TRI_RIGHT", emboss=False)
        else:
            box.prop(self, "show_render_prefs", icon="DISCLOSURE_TRI_DOWN", emboss=False)
            col = box.column(align=False)
            col.prop(self, "def_samples", text="Samples")
            col1 = col.column(align=True)
            col1.prop(self, "def_xres", text="X")
            col1.prop(self, "def_yres", text="Y")
            col.prop(self, "def_device", text="Device")
            col.prop(self, "def_margin", text="Margin")
            col.prop(self, "def_mask_margin", text="Mask Margin")
            col.prop(self, "def_raydist", text="Ray Distance")
            col.prop(self, "def_max_ray_dist", text="Max Ray Dist")
            col.prop(self, "ignore_vis")

        # Output prefs
        box = colprefs.box()
        if not self.show_output_prefs:
            box.prop(self, "show_output_prefs", icon="DISCLOSURE_TRI_RIGHT", emboss=False)
        else:
            box.prop(self, "show_output_prefs", icon="DISCLOSURE_TRI_DOWN", emboss=False)
            col = box.column(align=False)
            col.prop(self, "def_format", text="Format")
            col1 = col.column(align=True)
            col1.prop(self, "def_xout", text="X")
            col1.prop(self, "def_yout", text="Y")
            col2 = col.column(align=True)
            col2.prop(self, "def_outpath", text="Image Path")
            col2.prop(self, "def_outname", text="Image Name")
            col.prop(self, "make_dirs")
            col.prop(self, "auto_open")

        # Dev prefs
        col = colprefs.column(align=True)
        col.prop(self, "fact_start")
        col.prop(self, "save_packed")
        col.prop(self, "save_images")
        col.prop(self, "retry")
        if 'Non-Color' not in bpy.types.ColorManagedInputColorspaceSettings.bl_rna.properties['name'].enum_items.keys():
            col.prop(self, "img_non_color")
        col.prop(self, "debug")



def register():
    from bpy.utils import register_class
    register_class(BakeWrangler_Preferences)
    # Add status property to the window manager
    bpy.types.WindowManager.bw_status = bpy.props.IntProperty(name="Bake Wrangler Status", default=0)
    bpy.types.WindowManager.bw_lastlog = bpy.props.StringProperty(name="Bake Wangler Log", default="")
    bpy.types.WindowManager.bw_lastfile = bpy.props.StringProperty(name="Bake Wangler Temp Blend", default="")
    nodes.register()
    status_bar.register()


def unregister():
    from bpy.utils import unregister_class
    nodes.unregister()
    status_bar.unregister()
    unregister_class(BakeWrangler_Preferences)
    # Remove status property from window manager
    delattr(bpy.types.WindowManager, 'bw_status')
