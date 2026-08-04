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

""" # Zen UV Mark System """
from math import radians, pi
import bpy
import bmesh
from ZenUV.utils.generic import (
    get_mesh_data,
    collect_selected_objects_data,
    resort_by_type_mesh_in_edit_mode_and_sel,
    verify_uv_layer
)
from ZenUV.ui.labels import ZuvLabels
from ZenUV.utils.constants import UiConstants as uc
from ZenUV.utils.mark_utils import (
    MarkStateManager,
    unmark_all_seams_sharp,
    sharp_by_uv_border,
    seams_by_uv_border,
    seams_by_sharp,
    sharp_by_seam,
    seams_by_open_edges,
    MarkFactory
)
from ZenUV.prop.zuv_preferences import get_prefs
from ZenUV.ui.pie import ZsPieFactory


class ZUV_OT_Mark_Seams(bpy.types.Operator):
    """Mark selected edges or face borders as Seams and/or Sharp edges"""
    bl_idname = "uv.zenuv_mark_seams"
    bl_label = "Mark Seam"
    bl_description = "Mark selected edges or face borders as Seams and/or \
Sharp edges"
    bl_options = {'REGISTER', 'UNDO'}

    action: bpy.props.EnumProperty(
        name='Action',
        description='Action',
        items=[
            ("MARK", "Mark", "Mark edges"),
            ("UNMARK", "Unmark", "Unmark edges")
            ],
        default='MARK')

    markSeamEdges: bpy.props.BoolProperty(
        name=ZuvLabels.PREF_MARK_SEAM_EDGES_LABEL,
        description=ZuvLabels.PREF_MARK_SEAM_EDGES_DESC,
        default=True)

    markSharpEdges: bpy.props.BoolProperty(
        name=ZuvLabels.PREF_MARK_SHARP_EDGES_LABEL,
        description=ZuvLabels.PREF_MARK_SHARP_EDGES_DESC,
        default=False)

    clear_inside: bpy.props.BoolProperty(
        name="Clear Inside",
        description="Clear marking inside of selected faces",
        default=True)

    @classmethod
    def description(cls, context, properties):
        if properties:
            return cls.bl_description.replace('Mark', properties.action.title())
        else:
            return cls.bl_description

    def draw(self, context):
        layout = self.layout

        if self.action == 'UNMARK':
            seam_label = 'Unmark Seams'
            sharp_label = 'Unmark Sharp Edges'
        else:
            seam_label = 'Mark Seams'
            sharp_label = 'Mark Sharp Edges'

        addon_prefs = context.preferences.addons[ZuvLabels.ADDON_NAME].preferences
        layout.prop(self, 'clear_inside')
        mark_box = layout.box()
        s_mark_settings = 'Mark Settings'
        s_mark_settings += ' (Global Mode)' if addon_prefs.useGlobalMarkSettings else ' (Local Mode)'
        mark_box.label(text=s_mark_settings)

        row = mark_box.row(align=True)
        if not addon_prefs.useGlobalMarkSettings:
            row.prop(self, 'markSeamEdges', text=seam_label)
            row.prop(self, 'markSharpEdges', text=sharp_label)
        else:
            row.enabled = False
            row.prop(addon_prefs, "markSeamEdges")
            row.prop(addon_prefs, "markSharpEdges")

    @classmethod
    def poll(cls, context):
        """ Validate context """
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH'

    def execute(self, context):

        ZsPieFactory.mark_pie_cancelled()

        # Sync mode only
        if context.space_data and context.space_data.type == 'IMAGE_EDITOR' and not context.scene.tool_settings.use_uv_select_sync:
            from ZenUV.utils.messages import zen_message
            zen_message(context, message="Turn on UV Sync Selection mode",)
            return {'CANCELLED'}

        objs = resort_by_type_mesh_in_edit_mode_and_sel(context)
        if not objs:
            self.report({'WARNING'}, "There are no selected objects")
            return {'CANCELLED'}

        MarkFactory.initialize()
        MarkFactory.b_is_use_popup = True

        b_mSeam, b_mSharp = MarkStateManager(context).get_state_from_generic_operator(self.markSeamEdges, self.markSharpEdges)
        if not b_mSeam and not b_mSharp:
            return {'FINISHED'}

        p_objs = MarkFactory.collect_mark_objects(objs)

        MarkFactory.mark_edges(
            p_objs,
            b_mSeam,
            b_mSharp,
            is_switch=False,
            is_assign=self.action == 'MARK',
            is_remove_inside=self.clear_inside,
            is_silent_mode=False
        )
        if MarkFactory.message != '':
            self.report({'WARNING'}, message=MarkFactory.message)

        if MarkFactory.raise_popup:
            bpy.ops.wm.call_menu(name=MarkFactory.popup_name)

        if context.scene.tool_settings.use_edge_path_live_unwrap:
            from ZenUV.ops.pack_sys.pack import PackObjectsStorage
            from ZenUV.utils.generic import bpy_select_by_context

            Storage = PackObjectsStorage()
            Storage.collect_objects(context)
            Storage.hide_pack_excluded(context)
            bpy_select_by_context(context, action='SELECT')
            bpy.ops.uv.unwrap(
                    method='ANGLE_BASED',
                    fill_holes=True,
                    correct_aspect=True,
                    use_subsurf_data=False,
                    )
            bpy_select_by_context(context, action='DESELECT')
            Storage.unhide_pack_excluded()
            Storage.restore_selection_all_objects(context)

        return {'FINISHED'}


class ZUV_OT_Unmark_All(bpy.types.Operator):
    bl_idname = "uv.zenuv_unmark_all"
    bl_label = "Unmark All"
    bl_description = "Remove all the Seams and/or Sharp edges from the mesh"
    bl_options = {'REGISTER', 'UNDO'}

    clear_pinned: bpy.props.BoolProperty(
        name="Clear Pinned",
        description="Clear Pinned vertices",
        default=False)

    markSeamEdges: bpy.props.BoolProperty(
        name="Mark Seams",
        description="Automatically assign Seams",
        default=True)

    markSharpEdges: bpy.props.BoolProperty(
        name="Mark Sharp Edges",
        description='Automatically assign Sharp edges',
        default=False)

    @classmethod
    def poll(cls, context):
        """ Validate context """
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH'

    def draw(self, context):
        addon_prefs = get_prefs()
        layout = self.layout
        layout.prop(self, "clear_pinned")
        mark_box = layout.box()
        s_mark_settings = 'Mark Settings'
        s_mark_settings += ' (Global Mode)' if addon_prefs.useGlobalMarkSettings else ' (Local Mode)'
        mark_box.label(text=s_mark_settings)

        row = mark_box.row(align=True)
        if not addon_prefs.useGlobalMarkSettings:
            row.prop(self, 'markSeamEdges')
            row.prop(self, 'markSharpEdges')
        else:
            row.enabled = False
            row.prop(addon_prefs, "markSeamEdges")
            row.prop(addon_prefs, "markSharpEdges")

    def execute(self, context):
        ZsPieFactory.mark_pie_cancelled()

        objs = resort_by_type_mesh_in_edit_mode_and_sel(context)
        if not objs:
            self.report({'WARNING'}, "There are no selected objects")
            return {'CANCELLED'}

        mSeam, mSharp = MarkStateManager(context).get_state_from_generic_operator(self.markSeamEdges, self.markSharpEdges)

        if mSeam is False and mSharp is False:
            return {'FINISHED'}

        for obj in objs:
            me, bm = get_mesh_data(obj)

            """ Clear Pinned Data """
            uv_layer = verify_uv_layer(bm)

            edges = [edge for edge in bm.edges if not edge.hide]

            if self.clear_pinned:
                for loop in [loop for face in bm.faces for loop in face.loops]:
                    loop[uv_layer].pin_uv = False

            if mSeam is True and mSharp is False:
                for edge in edges:
                    edge.seam = False
            elif mSeam is False and mSharp is True:
                for edge in edges:
                    edge.smooth = True
            elif mSeam is True and mSharp is True:
                for edge in edges:
                    edge.seam = False
                    edge.smooth = True

            bmesh.update_edit_mesh(me, loop_triangles=False)

        return {'FINISHED'}


class ZUV_OT_UnifiedMark(bpy.types.Operator):
    bl_idname = "uv.zenuv_unified_mark"
    bl_label = ZuvLabels.UNIFIED_MARK_LABEL
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = ZuvLabels.UNIFIED_MARK_DESC

    convert: bpy.props.EnumProperty(
        items=uc.unified_mark_enum,
        default="SEAM_BY_OPEN_EDGES",
        # options={'HIDDEN'}
    )
    unmark_seams: bpy.props.BoolProperty(name="Unmark Seams", default=False)
    unmark_sharp: bpy.props.BoolProperty(name="Unmark Sharp", default=False)

    influence: bpy.props.EnumProperty(
        name='Influence',
        description='For which edges to mark',
        items=[
            ("ISLAND", "Island", "Include only boundary edges belonging to different islands"),
            ("UV", "UV", "Include all boundary edges of the curremt UV Map")
        ],
        default="ISLAND"
    )

    @classmethod
    def poll(cls, context):
        """ Validate context """
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH'

    def invoke(self, context, event):
        self.convert = context.scene.zen_uv.sl_convert
        return self.execute(context)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "convert", text="Operation")
        if self.convert == "SHARP_BY_UV_BORDER":
            layout.prop(self, 'influence')
        box = layout.box()
        if self.convert in {"SEAM_BY_UV_BORDER", "SHARP_BY_UV_BORDER"}:
            box.prop(self, "unmark_seams")
            box.prop(self, "unmark_sharp")
        else:
            box.label(text="No options.")

    def execute(self, context):
        bms = collect_selected_objects_data(context)
        if self.convert == "SHARP_BY_UV_BORDER":
            if self.unmark_seams or self.unmark_sharp:
                unmark_all_seams_sharp(bms, self.unmark_seams, self.unmark_sharp)
            sharp_by_uv_border(context, bms, self.influence)
        if self.convert == "SEAM_BY_UV_BORDER":
            if self.unmark_seams or self.unmark_sharp:
                unmark_all_seams_sharp(bms, self.unmark_seams, self.unmark_sharp)
            seams_by_uv_border(bms)
        elif self.convert == "SEAM_BY_SHARP":
            seams_by_sharp(context)
        elif self.convert == "SHARP_BY_SEAM":
            sharp_by_seam(context)
        elif self.convert == "SEAM_BY_OPEN_EDGES":
            seams_by_open_edges(bms)
        return {'FINISHED'}


class ZUV_OT_Seams_By_UV_Borders(bpy.types.Operator):
    bl_idname = "uv.zenuv_seams_by_uv_islands"
    bl_label = ZuvLabels.MARK_BY_BORDER_LABEL
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = ZuvLabels.MARK_BY_BORDER_DESC

    unmark_seams: bpy.props.BoolProperty(name="Unmark Seams", default=False)
    unmark_sharp: bpy.props.BoolProperty(name="Unmark Sharp", default=False)

    @classmethod
    def poll(cls, context):
        """ Validate context """
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH'

    def execute(self, context):
        bms = collect_selected_objects_data(context)
        if self.unmark_seams or self.unmark_sharp:
            unmark_all_seams_sharp(bms, self.unmark_seams, self.unmark_sharp)
        seams_by_uv_border(bms)
        return {'FINISHED'}


class ZUV_OT_Sharp_By_UV_Borders(bpy.types.Operator):
    bl_idname = "uv.zenuv_sharp_by_uv_islands"
    bl_label = ZuvLabels.MARK_SHARP_BY_BORDER_LABEL
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = ZuvLabels.MARK_SHARP_BY_BORDER_DESC

    unmark_seams: bpy.props.BoolProperty(name="Unmark Seams", default=False)
    unmark_sharp: bpy.props.BoolProperty(name="Unmark Sharp", default=False)
    influence: bpy.props.EnumProperty(
        name='Influence',
        description='For which edges to mark',
        items=[
            ("ISLAND", "Island", "Include only boundary edges belonging to different islands"),
            ("UV", "UV", "Include all boundary edges of the curremt UV Map")
        ],
        default="ISLAND"
    )

    @classmethod
    def poll(cls, context):
        """ Validate context """
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH'

    def execute(self, context):
        bms = collect_selected_objects_data(context)
        if self.unmark_seams or self.unmark_sharp:
            unmark_all_seams_sharp(bms, self.unmark_seams, self.unmark_sharp)
        sharp_by_uv_border(context, bms, self.influence)
        return {'FINISHED'}


class ZUV_OT_Seams_By_Open_Edges(bpy.types.Operator):
    bl_idname = "uv.zenuv_seams_by_open_edges"
    bl_label = ZuvLabels.SEAM_BY_OPEN_EDGES_LABEL
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = ZuvLabels.SEAM_BY_OPEN_EDGES_DESC

    @classmethod
    def poll(cls, context):
        """ Validate context """
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH'

    def execute(self, context):
        bms = collect_selected_objects_data(context)

        seams_by_open_edges(bms)
        return {'FINISHED'}


class ZUV_OT_Seam_By_Sharp(bpy.types.Operator):
    bl_idname = "uv.zenuv_seams_by_sharp"
    bl_label = ZuvLabels.SEAM_BY_SHARP_LABEL
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = ZuvLabels.SEAM_BY_SHARP_DESC

    @classmethod
    def poll(cls, context):
        """ Validate context """
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH'

    def execute(self, context):
        seams_by_sharp(context)
        return {'FINISHED'}


class ZUV_OT_Sharp_By_Seam(bpy.types.Operator):
    bl_idname = "uv.zenuv_sharp_by_seams"
    bl_label = ZuvLabels.SHARP_BY_SEAM_LABEL
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = ZuvLabels.SHARP_BY_SEAM_DESC

    @classmethod
    def poll(cls, context):
        """ Validate context """
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH'

    def execute(self, context):
        sharp_by_seam(context)
        return {'FINISHED'}


class ZUV_OT_Auto_Mark(bpy.types.Operator):
    bl_idname = "uv.zenuv_auto_mark"
    bl_label = ZuvLabels.AUTO_MARK_LABEL
    bl_description = ZuvLabels.AUTO_MARK_DESC
    bl_options = {'REGISTER', 'UNDO'}

    keep_init: bpy.props.BoolProperty(
        name='Keep init marks',
        description="Keep the state of initial seam and sharp",
        default=False
    )

    respect_selection: bpy.props.BoolProperty(
        name='Selection Respect',
        description="Mark only within current selection",
        default=False
    )

    angle: bpy.props.FloatProperty(
        name=ZuvLabels.AUTO_MARK_ANGLE_NAME,
        description=ZuvLabels.AUTO_MARK_ANGLE_DESC,
        min=0.0,
        max=180.0,
        default=30.03
    )

    markSharpEdges: bpy.props.BoolProperty(
        name=ZuvLabels.PREF_MARK_SHARP_EDGES_LABEL,
        description=ZuvLabels.PREF_MARK_SHARP_EDGES_DESC,
        default=False,
    )

    markSeamEdges: bpy.props.BoolProperty(
        name=ZuvLabels.PREF_MARK_SEAM_EDGES_LABEL,
        description=ZuvLabels.PREF_MARK_SEAM_EDGES_DESC,
        default=True,
    )

    @classmethod
    def poll(cls, context):
        """ Validate context """
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH'

    def draw(self, context: bpy.types.Context):
        addon_prefs = context.preferences.addons[ZuvLabels.ADDON_NAME].preferences

        layout = self.layout

        layout.prop(self, 'keep_init')
        layout.prop(self, 'respect_selection')
        layout.prop(self, "angle")

        mark_box = layout.box()
        s_mark_settings = 'Mark Settings'
        s_mark_settings += ' (Global Mode)' if addon_prefs.useGlobalMarkSettings else ' (Local Mode)'
        mark_box.label(text=s_mark_settings)

        row = mark_box.row(align=True)
        if not addon_prefs.useGlobalMarkSettings:
            row.prop(self, 'markSeamEdges')
            row.prop(self, 'markSharpEdges')
        else:
            row.enabled = False
            row.prop(addon_prefs, "markSeamEdges")
            row.prop(addon_prefs, "markSharpEdges")

    def execute(self, context):
        ZsPieFactory.mark_pie_cancelled()

        objs = resort_by_type_mesh_in_edit_mode_and_sel(context)
        if not objs:
            self.report({'WARNING'}, "There are no selected objects")
            return {'CANCELLED'}

        mSeam, mSharp = MarkStateManager(context).get_state_from_generic_operator(self.markSeamEdges, self.markSharpEdges)
        if not mSeam and not mSharp:
            return {'FINISHED'}

        for obj in objs:
            bm = bmesh.from_edit_mesh(obj.data)

            if self.respect_selection:
                edges = [edge for edge in bm.edges if not edge.hide and edge.select]
            else:
                edges = [edge for edge in bm.edges if not edge.hide]

            sharp = [edge for edge in edges if edge.calc_face_angle(pi) > radians(self.angle)]

            if mSeam and mSharp:
                if not self.keep_init:
                    self.mark_both(edges, state=False)
                self.mark_both(sharp, state=True)
            elif mSeam and not mSharp:
                if not self.keep_init:
                    self.mark_seam(edges, state=False)
                self.mark_seam(sharp, state=True)
            elif not mSeam and mSharp:
                if not self.keep_init:
                    self.mark_sharp(edges, state=False)
                self.mark_sharp(sharp, state=True)
            else:
                return {'CANCELLED'}

            bmesh.update_edit_mesh(obj.data, loop_triangles=False)

        return {'FINISHED'}

    def mark_both(self, edges, state=True):
        for edge in edges:
            edge.seam = state
            edge.smooth = not state

    def mark_sharp(self, edges, state=True):
        for edge in edges:
            edge.smooth = not state

    def mark_seam(self, edges, state=True):
        for edge in edges:
            edge.seam = state


mark_sys_classes = (
    ZUV_OT_Unmark_All,
    ZUV_OT_Sharp_By_Seam,
    ZUV_OT_Seams_By_UV_Borders,
    ZUV_OT_Sharp_By_UV_Borders,
    ZUV_OT_Seam_By_Sharp,
    ZUV_OT_Mark_Seams,
    ZUV_OT_Auto_Mark,
    ZUV_OT_Seams_By_Open_Edges,
    ZUV_OT_UnifiedMark
)

if __name__ == '__main__':
    pass
