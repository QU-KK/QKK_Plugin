# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####

# <pep8 compliant>

# Sticky UV Editor
# Original idea Oleg Stepanov (DotBow)
# https://github.com/DotBow/Blender-Sticky-UV-Editor-Add-on


import bpy

from bpy.props import (BoolProperty, EnumProperty, FloatProperty,
                       IntVectorProperty)
from bpy.types import PropertyGroup


SPACE_UV_EDITOR_ATTRS = [
    "show_stretch",
    "display_stretch_type",
    "uv_opacity",
    "edge_display_type",
    "show_modified_edges",
    "show_faces",
    "show_metadata",
    "tile_grid_shape"
]

SPACE_IMAGE_ATTRS = [
    "show_region_toolbar",
    "show_region_ui",
    "show_region_tool_header",
    # "show_region_hud",
    "pivot_point",
    "cursor_location",
    # "use_uv_select_sync"
    # "use_snap",
    # "use_proportional_edit"
    ]


def _set_attributes(p_source, p_target, p_attrs):
    for attr in p_attrs:
        try:
            p_new_attr = getattr(p_source, attr)
            p_was_attr = getattr(p_target, attr)
            if p_new_attr != p_was_attr:
                setattr(p_target, attr, p_new_attr)
        except Exception as e:
            print(f"Sticky UV Editor: Can not set - {attr}. Reason:", e)


class UVEditorSettings(PropertyGroup):
    initialized: BoolProperty(
        default=False)

    show_stretch: BoolProperty(
        name="Display Stretch",
        description="Display faces colored according to the difference in shape between UVs and their 3D coordinates (blue for low distortion, red for high distortion)",
        default=False)
    display_stretch_type: EnumProperty(
        name="Display Stretch Type",
        description="Type of stretch to draw",
        items={('ANGLE', "Angle",
                "Angle distortion between UV and 3D angles", 0),
               ('AREA', "Area",
                "Area distortion between UV and 3D faces", 1)},
        default='ANGLE')
    uv_opacity: FloatProperty(
        name="UV Opacity",
        description="Opacity of UV overlays",
        default=1.0,
        min=0.0, max=1.0)
    edge_display_type: EnumProperty(
        name="Display style for UV edges",
        description="Type of stretch to draw",
        items={('OUTLINE', "Outline",
                "Display white edges with black outline", 0),
               ('DASH', "Dash",
                "Display dashed black-white edges", 1),
               ('BLACK', "Black",
                "Display black edges", 2),
               ('WHITE', "White",
                "Display white edges", 3)},
        default='OUTLINE')
    show_modified_edges: BoolProperty(
        name="Modified Edges",
        description="Display edges after modifiers are applied",
        default=False)
    show_faces: BoolProperty(
        name="Faces",
        description="Display faces over the image",
        default=True)
    show_metadata: BoolProperty(
        name="Show Metadata",
        description="Display metadata properties of the image",
        default=False)

    tile_grid_shape: IntVectorProperty(
        name="Tile Grid Shape",
        description="How many tiles will be shown in the background",
        size=2,
        default=(0, 0))

    show_region_toolbar: BoolProperty(
        name="Show Toolbar",
        description="",
        default=True)
    show_region_ui: BoolProperty(
        name="Show Sidebar",
        description="",
        default=True)
    show_region_tool_header: BoolProperty(
        name="Show Tool Settings",
        description="",
        default=True)
    # show_region_hud: BoolProperty(
    #     name="Show Adjust Last Operation",
    #     description="",
    #     default=False)
    pivot_point: EnumProperty(
        items={
            ('CENTER', "Center", "", 0),
            ('MEDIAN', "Median", "", 1),
            ('CURSOR', "Cursor", "", 2),
            ('INDIVIDUAL_ORIGINS', "Individual Origins", "", 3),
        },
        name="Pivot",
        default='CENTER'
    )

    cursor_location: bpy.props.FloatVectorProperty(
        name='Cursor 2D',
        description="2D cursor location for UV editor",
        subtype='COORDINATES',
        size=2
    )
    # use_uv_select_sync: BoolProperty(
    #     name="UV Sync Selection",
    #     description="Keep UV an edit mode mesh selection in sync",
    #     default=False)

    def set(self, scene, area):
        space = area.spaces.active
        if space is None:
            return

        _set_attributes(scene.StkUvEdProps, space.uv_editor, SPACE_UV_EDITOR_ATTRS)

        _set_attributes(scene.StkUvEdProps, space, SPACE_IMAGE_ATTRS)

    def save_from_area(self, scene: bpy.types.Scene, area: bpy.types.Area):
        space = area.spaces.active
        if space is None:
            return

        _set_attributes(space.uv_editor, scene.StkUvEdProps, SPACE_UV_EDITOR_ATTRS)

        _set_attributes(space, scene.StkUvEdProps, SPACE_IMAGE_ATTRS)

    def save_from_property(self, scene: bpy.types.Scene, prop):
        _set_attributes(prop, scene.StkUvEdProps, SPACE_UV_EDITOR_ATTRS)

        _set_attributes(prop, scene.StkUvEdProps, SPACE_IMAGE_ATTRS)


def draw_sticky_editor_settings(self, context: bpy.types.Context):
    ''' @Draw Sticky UV Editor Settings '''
    layout: bpy.types.UILayout = self.layout
    stk_props = self.StkUvEdProps

    box = layout.box()
    row = box.row()
    row.prop(self, "stk_tabs", expand=True)

    # Draw preferences
    if self.stk_tabs == 'GENERAL':
        box = box.box()
        box.use_property_split = True

        col = box.column(align=True)
        col.prop(self, 'uv_editor_side')

        col = box.column(align=True)
        col.active = self.show_ui_button
        col.prop(self, "show_ui_button")
        r = col.row(align=True)
        r.prop(self, 'stk_ed_button_position_mode', expand=True)
        if self.stk_ed_button_position_mode == 'PERCENTAGE':
            col.prop(self, "stk_ed_button_v_position")
            col.prop(self, "stk_ed_button_h_position")

    if self.stk_tabs == 'SAVE_RESTORE':
        row = box.row(align=True)
        row.prop(self, "remember_uv_editor_settings")

        row = box.split()
        row.active = not self.remember_uv_editor_settings
        col1 = row.column(align=True)
        col2 = row.column(align=True)

        box = col1.box()
        box.label(text="UV Editing Overlay:", icon='OVERLAY')
        # box.use_property_split = True
        row = box.row()
        row.prop(stk_props, "show_stretch")
        row.prop(stk_props, "display_stretch_type", text="")
        box.separator()
        box.label(text="Geometry")
        box.prop(stk_props, "uv_opacity")
        box.prop(stk_props, "edge_display_type", text="")
        box.prop(stk_props, "show_modified_edges")
        box.prop(stk_props, "show_faces")
        box.separator()
        box.label(text="Image")
        box.prop(stk_props, "show_metadata")

        box = col2.box()
        # box.use_property_split = True
        col = box.column()
        col.label(text="UV Editor View Settings:")
        col.separator()

        col.prop(stk_props, "pivot_point")
        col.prop(self, "view_mode", text="Auto Frame")
        col.prop(stk_props, "show_region_toolbar")
        col.prop(stk_props, "show_region_ui")
        col.prop(stk_props, "show_region_tool_header")
        # col.prop(stk_props, "show_region_hud")
        col.prop(stk_props, 'cursor_location')

    if self.stk_tabs == 'ABOUT':
        box = box.box()
        col = box.column()
        col.label(text="Sticky UV Editor")
        col.label(text="Original idea and development - Oleg Stepanov (DotBow)")
        col.label(text="https://github.com/DotBow/Blender-Sticky-UV-Editor-Add-on")
        col.operator(
            "wm.url_open",
            text="Blender Sticky UV Editor",
        ).url = "https://github.com/DotBow/Blender-Sticky-UV-Editor-Add-on"
