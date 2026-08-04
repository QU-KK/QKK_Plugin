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

# Copyright 2023, Valeriy Yatsenko


import bpy
import bmesh

from dataclasses import dataclass

from .panel import ZUV_PT_3DV_TextureCheckerSetup
from ZenUV.utils.generic import ZUV_PANEL_CATEGORY, ZUV_REGION_TYPE, ZUV_SPACE_TYPE
from ZenUV.utils.generic import resort_by_type_mesh_in_edit_mode_and_sel, get_mesh_data
from ZenUV.utils.messages import zen_message
from ZenUV.utils.register_util import RegisterUtils


class ZUV_OT_SetViewportDisplayMode(bpy.types.Operator):

    bl_idname = "uv.zenuv_set_viewport_display_mode"
    bl_label = 'Set Viewport Display Mode'
    bl_description = 'Set viewport display mode for all selected objects'
    bl_options = {'REGISTER'}

    display_type: bpy.props.EnumProperty(
        name='Display as',
        items=(
            ('BOUNDS', 'Bounds', 'Display the bounds of the object'),
            ('WIRE', 'Wire', 'Display the object as a wireframe'),
            ('SOLID', 'Solid', 'Display the object as a solid (if solid drawing is enabled in the viewport)'),
            ('TEXTURED', 'Textured', 'Display the object with textures (if textures are enabled in the viewport)')
        ),
        default='TEXTURED'
    )

    @classmethod
    def poll(cls, context):
        """ Validate context """
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH'

    def invoke(self, context, event):
        wm = context.window_manager
        return wm.invoke_props_dialog(self)

    def execute(self, context):

        if context.mode == 'EDIT_MESH':
            objs = [
                obj for obj in context.selected_objects
                if obj.type == 'MESH'
                and obj.data.is_editmode is True
                and len(obj.data.polygons) != 0
                and obj.hide_get() is False
                and obj.hide_viewport is False
            ]
        else:
            objs = [
                obj for obj in context.selected_objects
                if obj.type == 'MESH'
                and len(obj.data.polygons) != 0
                and obj.hide_get() is False
                and obj.hide_viewport is False
            ]

        if not objs:
            self.report({'WARNING'}, "Zen UV: There are no selected objects.")
            return {'CANCELLED'}

        obj: bpy.types.Object = None

        for obj in objs:
            if obj.type == 'MESH':
                obj.display_type = self.display_type

        self.report({'INFO'}, 'Zen UV: Finished.')

        return {'FINISHED'}


class ZUV_OT_ClearMeshAttributes(bpy.types.Operator):

    bl_idname = "uv.zenuv_clear_mesh_attrs"
    bl_label = 'Clear Attributes'
    bl_description = 'Clear mesh attributes used in the Zen UV. Finished and Excluded'
    bl_options = {'REGISTER'}

    clear_finished: bpy.props.BoolProperty(name='Finished', description='Clear Finished tag', default=True)
    clear_excluded: bpy.props.BoolProperty(name='Pack Excluded', description='Clear Pack Excluded tag', default=True)
    clear_td_vc: bpy.props.BoolProperty(name='Texel Density', description='Clear texel density baked to vertex color', default=True)

    @classmethod
    def poll(cls, context):
        """ Validate context """
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH'

    def invoke(self, context, event):
        wm = context.window_manager
        return wm.invoke_props_dialog(self)

    def execute(self, context):
        objs = resort_by_type_mesh_in_edit_mode_and_sel(context)
        if not objs:
            self.report({'WARNING'}, "Zen UV: There are no selected objects.")
            return {'CANCELLED'}

        from ZenUV.ops.pack_sys.pack_exclusion import PackExcludedFactory as PF
        from ZenUV.utils.constants import PACK_EXCLUDED_FACEMAP_NAME
        from ZenUV.ops.zen_unwrap.finishing import FINISHED_FACEMAP_NAME

        p_layer_names = []
        if self.clear_finished:
            p_layer_names.append(FINISHED_FACEMAP_NAME)
        if self.clear_excluded:
            p_layer_names.append(PACK_EXCLUDED_FACEMAP_NAME)

        if self.clear_td_vc:
            from ZenUV.utils import vc_processor as vc
            for obj in objs:
                vc.disable_zen_vc_map(obj, vc.Z_TD_PRESETS_V_MAP_NAME)
                vc.disable_zen_vc_map(obj, vc.Z_TD_BALANCED_V_MAP_NAME)

        for obj in objs:
            me, bm, _ = PF._get_obj_bm_data(obj)

            for p_name in p_layer_names:
                p_fmap = bm.faces.layers.int.get(p_name, None)
                if p_fmap is None:
                    continue
                bm.faces.layers.int.remove(p_fmap)
                bmesh.update_edit_mesh(me)

        bpy.ops.ed.undo_push(message='Clear Attributes')

        self.report({'INFO'}, 'Zen UV: Finished.')

        return {'FINISHED'}


@dataclass
class iCounterUnit:

    obj_name: str = ''
    total: int = 0
    selected: int = 0
    hidden: int = 0
    visible: int = 0

    def upd_visible(self):
        self.visible = self.total - self.hidden


class ZUV_OT_IslandCounter(bpy.types.Operator):
    bl_idname = "uv.zenuv_island_counter"
    bl_label = 'UV Island Counter'
    bl_options = {'REGISTER'}
    bl_description = 'Count UV islands in selected objects and display the result'

    show_selected_only: bpy.props.BoolProperty(
        name='Show Selected Only',
        description='Show only the number of selected islands instead of full statistics',
        default=False
    )

    @classmethod
    def description(cls, context: bpy.types.Context, properties: bpy.types.OperatorProperties):
        if properties.show_selected_only:
            return 'Count selected UV islands in selected objects and display the result'
        return cls.bl_description

    @classmethod
    def poll(cls, context):
        """ Validate context """
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH'

    def execute(self, context):
        from ZenUV.utils import get_uv_islands as island_util

        objs = resort_by_type_mesh_in_edit_mode_and_sel(context)
        if not objs:
            self.report({'WARNING'}, "Zen UV: There are no selected objects.")
            return {"CANCELLED"}
        print('\nZen UV Island Counter:')
        storage = list()
        for obj in objs:
            _, bm = get_mesh_data(obj)
            uv_active = bm.loops.layers.uv.active
            i_count_total = len(island_util.get_islands(context, bm, is_include_hidden=True))
            storage.append(iCounterUnit(
                obj_name=obj.name,
                total=len(island_util.get_islands(context, bm, is_include_hidden=True)),
                hidden=i_count_total - len(island_util.get_islands(context, bm, is_include_hidden=False))
                ))
            storage[-1].upd_visible()
            if uv_active is not None:
                storage[-1].selected = len(island_util.get_island(context, bm, uv_active))

        print(''.join([f'\n{o.obj_name}\t\ttotal {o.total}\tvisible {o.visible}\tselected {o.selected}\thidden {o.hidden}' for o in storage]) + '\n')

        p_selected_count = sum([i.selected for i in storage])
        short_message = f'Selected {p_selected_count} islands'
        full_message = f'Total: selected: {p_selected_count} hidden: {sum([i.hidden for i in storage])} in {len(storage)} objects from {sum([o.total for o in storage])} islands'

        print(full_message)

        if self.show_selected_only:
            zen_message(context, short_message)
            self.report({'INFO'}, f'{short_message}. Extended info in the system console.')
        else:
            zen_message(context, full_message)
            self.report({'INFO'}, f'{full_message}. Extended info in the system console.')

        return {'FINISHED'}


class ZUV_OT_ShowIslandArea(bpy.types.Operator):
    bl_idname = "uv.zenuv_show_island_area"
    bl_label = 'Show Mesh Island Area'
    bl_options = {'REGISTER'}
    bl_description = 'Calculates and show selected islands mesh area and UV Area'

    @classmethod
    def poll(cls, context):
        """ Validate context """
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH'

    def execute(self, context):
        from ZenUV.utils import get_uv_islands as island_util
        from ZenUV.utils.messages import zen_message
        objs = resort_by_type_mesh_in_edit_mode_and_sel(context)
        if not objs:
            self.report({'WARNING'}, "Zen UV: There are no selected objects.")
            return {"CANCELLED"}

        for obj in objs:
            _, bm = get_mesh_data(obj)
            uv_layer = bm.loops.layers.uv.active
            p_islands = island_util.get_island(context, bm, uv_layer)
            for i, island in enumerate(p_islands):
                p_island_area = round(sum([f.calc_area() for f in island]), 4)
                if len(p_islands) == 1:
                    zen_message(context, message=f'mesh area {p_island_area}')
                    print(f'island: {i}, mesh area {p_island_area}')
                else:
                    print(f'island: {i}, mesh area {p_island_area}')

        return {'FINISHED'}


class ZUV_OT_SelectEmptyObjects(bpy.types.Operator):
    bl_idname = "uv.zenuv_select_empty_objects"
    bl_label = 'Select Empty Objects'
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = 'Selects objects that do not contain faces'

    @classmethod
    def poll(cls, context):
        """ Validate context """
        is_uv_editor = context.space_data.type == 'IMAGE_EDITOR'
        return not is_uv_editor

    def execute(self, context):
        objs = self.filter_instances(
            [obj for obj in context.scene.objects if obj.type == 'MESH' and len(obj.data.polygons) == 0])
        if not objs:
            self.report({'INFO'}, "Zen UV: No objects with missing faces were found.")
            return {"FINISHED"}
        print('\nZen UV Empty Islands report:\n')
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')

        for obj in context.scene.objects:
            obj.select_set(False)

        for obj in objs:
            print(obj.name)
            obj.select_set(True)

        context.view_layer.objects.active = objs[0]

        self.report({'INFO'}, f'Zen UV: Total {len(objs)} empty objects were found.')

        return {'FINISHED'}

    def filter_instances(self, objs):
        if len(objs) == 1:
            return objs
        res = []
        for p_obj in objs:
            if True not in [p_obj.data == t_obj.data for t_obj in res]:
                res.append(p_obj)
        return res


class ZUV_OT_SelectEdgesByIndex(bpy.types.Operator):
    bl_description = "Select elements by their indices"
    bl_idname = "object.zenuv_select_elements_by_index"
    bl_label = "Select Elements By Index"
    bl_options = {'REGISTER', 'UNDO'}

    # Test List [96969, 97796, 88516, 97816, 88381, 88362, 88447]

    selection_type: bpy.props.EnumProperty(
        name='Selection Type',
        items=[
            ("VERTEX", "Vertex", "Select vertices"),
            ("EDGE", "Edge", "Select edges"),
            ("FACE", "Face", "Select faces")
        ],
        default="VERTEX"
    )
    indices: bpy.props.StringProperty(name="Indices", description="Comma-separated list of indices to select")

    @classmethod
    def description(cls, context, properties):
        if context.scene.tool_settings.use_uv_select_sync:
            return cls.bl_description
        else:
            return f'{cls.bl_description}. Only in UV Sync Selection mode'

    @classmethod
    def poll(cls, context):
        """ Validate context """
        active_object = context.active_object
        is_not_sync = context.space_data.type == 'IMAGE_EDITOR' and not context.scene.tool_settings.use_uv_select_sync
        return not is_not_sync and active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH'

    def execute(self, context):
        indices = [int(idx) for idx in ''.join(self.indices.split()).split(',') if idx.isdigit()]

        if not indices:
            self.report({'ERROR'}, "Invalid edge indices")
            return {'CANCELLED'}

        obj = context.object
        if obj.type != 'MESH':
            self.report({'WARNING'}, 'Active object type is not a Mesh')
            return {'CANCELLED'}
        bpy.ops.mesh.select_all(action='DESELECT')

        bm = bmesh.from_edit_mesh(obj.data)
        if self.selection_type == "VERTEX":
            bpy.ops.mesh.select_mode(use_extend=False, use_expand=False, type='VERT')
            bm.verts.ensure_lookup_table()
            for i in {k.index for k in bm.verts}.intersection(set(indices)):
                bm.verts[i].select = True
        elif self.selection_type == "EDGE":
            bpy.ops.mesh.select_mode(use_extend=False, use_expand=False, type='EDGE')
            bm.edges.ensure_lookup_table()
            for i in {k.index for k in bm.edges}.intersection(set(indices)):
                bm.edges[i].select = True
        elif self.selection_type == "FACE":
            bpy.ops.mesh.select_mode(use_extend=False, use_expand=False, type='FACE')
            bm.faces.ensure_lookup_table()
            for i in {k.index for k in bm.faces}.intersection(set(indices)):
                bm.faces[i].select = True

        bm.select_flush_mode()

        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)


class ZUV_OT_SelectEdgesWithoutFaces(bpy.types.Operator):
    bl_description = "Select edges without faces"
    bl_idname = "object.zenuv_select_edges_without_faces"
    bl_label = "Select Edges Without Faces"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def description(cls, context, properties):
        if context.scene.tool_settings.use_uv_select_sync:
            return cls.bl_description
        else:
            return f'{cls.bl_description}. Only in UV Sync Selection mode'

    @classmethod
    def poll(cls, context):
        """ Validate context """
        active_object = context.active_object
        is_not_sync = context.space_data.type == 'IMAGE_EDITOR' and not context.scene.tool_settings.use_uv_select_sync
        return not is_not_sync and active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH'

    def execute(self, context):
        objs = resort_by_type_mesh_in_edit_mode_and_sel(context)
        if not objs:
            self.report({'INFO'}, "There are no selected objects.")
            return {'CANCELLED'}
        bpy.ops.mesh.select_all(action='DESELECT')
        bpy.ops.mesh.select_mode(use_extend=False, use_expand=False, type='EDGE')

        for obj in objs:
            bm = bmesh.from_edit_mesh(obj.data)
            edges = [e for e in bm.edges if not e.link_faces]
            for e in edges:
                e.select = True
            bmesh.update_edit_mesh(obj.data)
        e_count = len(edges)
        if e_count:
            self.report({'WARNING'}, f'There are {e_count} edges without faces.')
        else:
            self.report({'INFO'}, 'There are no edges without faces.')
        return {'FINISHED'}


class ZUV_OT_SelectEdgesWithMultipleLoops(bpy.types.Operator):
    bl_description = "Select edges with Multiple Loops"
    bl_idname = "object.zenuv_select_edges_with_multiple_loops"
    bl_label = "Select Edges with multiple loops"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def description(cls, context, properties):
        if context.scene.tool_settings.use_uv_select_sync:
            return cls.bl_description
        else:
            return f'{cls.bl_description}. Only in UV Sync Selection mode'

    @classmethod
    def poll(cls, context):
        """ Validate context """
        active_object = context.active_object
        is_not_sync = context.space_data.type == 'IMAGE_EDITOR' and not context.scene.tool_settings.use_uv_select_sync
        return not is_not_sync and active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH'

    def execute(self, context):
        objs = resort_by_type_mesh_in_edit_mode_and_sel(context)
        if not objs:
            self.report({'INFO'}, "There are no selected objects.")
            return {'CANCELLED'}
        bpy.ops.mesh.select_all(action='DESELECT')
        bpy.ops.mesh.select_mode(use_extend=False, use_expand=False, type='EDGE')

        for obj in objs:
            bm = bmesh.from_edit_mesh(obj.data)
            edge_idxs = [edge.index for edge in bm.edges if len(edge.link_loops) > 2]
            for i in edge_idxs:
                bm.edges[i].select = True
            bmesh.update_edit_mesh(obj.data)
        e_count = len(edge_idxs)
        if e_count:
            self.report({'WARNING'}, f'There are {e_count} edges with Multiple Loops.')
        else:
            self.report({'INFO'}, 'There are no edges with Multiple Loops.')
        return {'FINISHED'}


class ZUV_OT_CalcUvEdgesLengths(bpy.types.Operator):
    bl_description = "Calculates the lengths of the selected edges"
    bl_idname = "object.zenuv_calc_uv_edges_length"
    bl_label = "Calc UV Edges Length"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        """ Validate context """
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH'

    def execute(self, context):
        from ZenUV.ops.transform_sys.transform_utils.tr_utils import ActiveUvImage
        from math import isclose

        objs = resort_by_type_mesh_in_edit_mode_and_sel(context)
        if not objs:
            self.report({'INFO'}, "There are no selected objects.")
            return {'CANCELLED'}

        round_value = 5
        is_no_sync = context.area.type == 'IMAGE_EDITOR' and not context.scene.tool_settings.use_uv_select_sync

        p_active_image = ActiveUvImage(context)
        if p_active_image.image is not None:
            p_pixel_size = 1 / p_active_image.len_x
        else:
            p_pixel_size = None

        p_total_len = 0
        scope = dict()

        for obj in objs:
            bm = bmesh.from_edit_mesh(obj.data)
            uv_layer = bm.loops.layers.uv.active

            if uv_layer is None:
                continue

            scope.update({obj.name: []})

            if is_no_sync:
                p_edges = [e.index for e in bm.edges if any(lp[uv_layer].select_edge for lp in e.link_loops)]
            else:
                p_edges = [e.index for e in bm.edges if e.select]

            if not p_edges:
                zen_message(context, message='Select one or more edges')
                return {'CANCELLED'}

            for i in p_edges:
                edge = bm.edges[i]

                if len(edge.link_loops) > 2:
                    scope[obj.name].append([edge.index, None])
                    continue

                if is_no_sync:
                    p_loops = [loop for loop in edge.link_loops if loop[uv_layer].select_edge and loop.face.select]
                else:
                    p_loops = [loop for loop in edge.link_loops]

                if not p_loops:
                    continue

                loop = p_loops[0]

                v_01 = loop[uv_layer].uv
                v_02 = loop.link_loop_next[uv_layer].uv
                v_03 = loop.link_loop_radial_next[uv_layer].uv
                v_04 = loop.link_loop_radial_next.link_loop_next[uv_layer].uv

                if v_01 == v_04 and v_02 == v_03:
                    p_len = (v_01 - v_02).magnitude
                    scope[obj.name].append([edge.index, p_len])
                else:
                    if is_no_sync:
                        p_len = (v_01 - v_02).magnitude
                        if loop.link_loop_radial_next[uv_layer].select_edge:
                            p_len += (v_03 - v_04).magnitude
                    else:
                        p_len = (v_01 - v_02).magnitude + (v_03 - v_04).magnitude
                    scope[obj.name].append([edge.index, p_len])

                if loop.index == loop.link_loop_radial_next.index:
                    p_len *= 0.5

                p_total_len += p_len

        if p_total_len == 0:
            zen_message(context, message='Select one or more edges')
            return {'CANCELLED'}

        print('\n------ ZenUV: Calculating the length of edges -----')

        p_warning = False
        for obj_name, data in scope.items():
            print(obj_name)
            if data:
                local_counter = 0
                for i, length in data:
                    if length is not None:
                        print(f'\t{i}    {round(length, round_value)}')
                        local_counter += length
                    else:
                        print(f'\t{i}           Warning! Multiple loops')
                        p_warning = True
                print(f'\tTotal: {round(local_counter, round_value)}')
            else:
                print('\t-')

        if p_pixel_size is not None:
            print(f'\nPixel Size: {round(p_pixel_size, round_value)}')
            if isclose(p_pixel_size - p_total_len, 0.0):
                print('Length is the same as pixel size')
            elif p_pixel_size < p_total_len:
                print('The total length is greater than the pixel size')
            elif p_pixel_size > p_total_len:
                print('The total length is less than the pixel size')
            info_message = f'Total length: {round(p_total_len, round_value)}. About {round(p_total_len / p_pixel_size, round_value)} pixels'
        else:
            print('Pixel size undefined')
            info_message = f'Total length: {round(p_total_len, round_value)}. Pixel info undefined'

        zen_message(context, message=info_message)
        if p_warning:
            self.report({'WARNING'}, 'Edges with multiple loops detected. Additional info in system console')
        else:
            self.report({'INFO'}, f'{info_message}. Additional info in system console')

        return {'FINISHED'}


class ZUV_OT_SelectDoubledVertices(bpy.types.Operator):

    bl_idname = "object.zenuv_select_doubled_vertices"
    bl_label = "Select Doubled Vertices"
    bl_description = "Selects vertices that have the same coordinates"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        """ Validate context """
        active_object = context.active_object
        is_uv_editor = context.space_data.type == 'IMAGE_EDITOR'
        return not is_uv_editor and active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH'

    def execute(self, context):
        objs = resort_by_type_mesh_in_edit_mode_and_sel(context)
        if not objs:
            self.report({'INFO'}, "There are no selected objects.")
            return {'CANCELLED'}
        bpy.ops.mesh.select_all(action='DESELECT')
        bpy.ops.mesh.select_mode(use_extend=False, use_expand=False, type='VERT')

        p_total_doubles: int = 0

        for obj in objs:
            bm = bmesh.from_edit_mesh(obj.data)
            p_verts: list = []
            doubles: list = []

            for v in bm.verts:
                v_co = v.co.to_tuple(4)
                if v_co in p_verts:
                    doubles.append(v.index)
                p_verts.append(v_co)

            for i in doubles:
                bm.verts[i].select = True

            bm.select_flush_mode()

            p_total_doubles += len(doubles)

        if p_total_doubles > 0:
            self.report({'WARNING'}, f'Found {p_total_doubles} doubled vertices.')
        else:
            self.report({'INFO'}, 'There are no doubled vertices.')
        return {'FINISHED'}


class ZUV_OT_SelectFreeVertices(bpy.types.Operator):

    bl_idname = "object.zenuv_select_free_vertices"
    bl_label = "Select Free Vertices"
    bl_description = "Selects vertices that have no connected faces or edges"
    bl_options = {'REGISTER', 'UNDO'}

    detection_method: bpy.props.EnumProperty(
        name='Method',
        items=(
            ('EDGES', 'Edges', 'Select a vertex if it has no adjacent edges'),
            ('FACES', 'Faces', 'Select a vertex if it has no adjacent faces'),
        ),
        default='FACES'
    )

    @classmethod
    def poll(cls, context):
        """ Validate context """
        active_object = context.active_object
        is_uv_editor = context.space_data.type == 'IMAGE_EDITOR'
        return not is_uv_editor and active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH'

    def execute(self, context):
        objs = resort_by_type_mesh_in_edit_mode_and_sel(context)
        if not objs:
            self.report({'INFO'}, "There are no selected objects.")
            return {'CANCELLED'}
        bpy.ops.mesh.select_all(action='DESELECT')
        bpy.ops.mesh.select_mode(use_extend=False, use_expand=False, type='VERT')

        p_total_count: int = 0

        for obj in objs:
            bm = bmesh.from_edit_mesh(obj.data)
            bm.verts.ensure_lookup_table()
            free_verts: list = []

            if self.detection_method == 'EDGES':
                free_verts = [v.index for v in bm.verts if len(v.link_edges) == 0]
            if self.detection_method == 'FACES':
                free_verts = [v.index for v in bm.verts if len(v.link_faces) == 0]

            for i in free_verts:
                bm.verts[i].select = True

            bm.select_flush_mode()

            p_total_count += len(free_verts)

        if p_total_count > 0:
            self.report({'WARNING'}, f'Found {p_total_count} free vertices.')
        else:
            self.report({'INFO'}, 'There are no free vertices.')
        return {'FINISHED'}


class ZUV_OT_CalculateUVPixelSize(bpy.types.Operator):
    bl_description = 'Calculates the size of a specified number of pixels in UV units and as a percentage'
    bl_idname = "uv.zenuv_calculate_uv_pixel_size"
    bl_label = "Calculate UV Pixel Size"
    bl_options = {'REGISTER', 'UNDO'}

    pixel_count: bpy.props.IntProperty(
        name="Pixel Count",
        description="Number of pixels for the calculation",
        default=1,
        min=1
    )

    image_source: bpy.props.EnumProperty(
        name="Image Source",
        description="Choose the source for image dimensions",
        items=[
            ('CUSTOM', "Custom Image Size", "Use custom width and height"),
            ('ACTIVE_UV', "Active Image in UV Editor", "Use active image in the UV Editor")
        ],
        default='CUSTOM'
    )

    custom_width: bpy.props.IntProperty(
        name="Custom Width",
        description="Width of the custom image in pixels",
        default=1024,
        min=1
    )
    custom_height: bpy.props.IntProperty(
        name="Custom Height",
        description="Height of the custom image in pixels",
        default=1024,
        min=1
    )

    uv_pixel_width: bpy.props.FloatProperty(
        name="UV Pixel Width (Units)",
        description="Width of the specified pixels in UV space",
        default=0.0,
        precision=6
    )
    uv_pixel_height: bpy.props.FloatProperty(
        name="UV Pixel Height (Units)",
        description="Height of the specified pixels in UV space",
        default=0.0,
        precision=6
    )
    uv_pixel_width_percent: bpy.props.FloatProperty(
        name="UV Pixel Width (%)",
        description="Width of the specified pixels as a percentage of the UV space",
        default=0.0,
        precision=6
    )
    uv_pixel_height_percent: bpy.props.FloatProperty(
        name="UV Pixel Height (%)",
        description="Height of the specified pixels as a percentage of the UV space",
        default=0.0,
        precision=6
    )

    @classmethod
    def poll(cls, context):
        return context.space_data.type == 'IMAGE_EDITOR'

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "pixel_count")
        layout.prop(self, "image_source")

        is_error = False

        box = layout.box()

        if self.image_source == 'CUSTOM':
            box.enabled = self.image_source == 'CUSTOM'
            col = box.column(align=True)
            col.label(text="Custom Image Size:")
            col = box.column(align=True)
            col.prop(self, "custom_width")
            col.prop(self, "custom_height")
        else:
            from ZenUV.ops.trimsheets.trimsheet_utils import ZuvTrimsheetUtils
            p_image = ZuvTrimsheetUtils.getActiveImage(context)
            if p_image:
                col = box.column(align=True)
                col.label(text="Image Size:")
                col = box.column(align=True)
                col.enabled = False
                col.prop(p_image, "size", index=0, text='Width')
                col.prop(p_image, "size", index=1, text='Height')
            else:
                is_error = True
                col = box.column(align=True)
                col.alert = True
                col.label(text="Image Size: Not Defined")
                col = box.column(align=True)
                col.alert = True
                col.label(text='Width: 0')
                col.label(text='Height: 0')

        box = layout.box()
        box.enabled = not is_error
        box.alert = is_error
        box.label(text="Pixel Size:")
        col = box.column(align=True)
        col.prop(self, "uv_pixel_width")
        col.prop(self, "uv_pixel_height")
        col = box.column(align=True)
        col.prop(self, "uv_pixel_width_percent")
        col.prop(self, "uv_pixel_height_percent")

    def execute(self, context):
        if self.image_source == 'ACTIVE_UV':
            from ZenUV.ops.trimsheets.trimsheet_utils import ZuvTrimsheetUtils
            p_image = ZuvTrimsheetUtils.getSpaceDataImage(context)
            if p_image is None:
                self.report({'ERROR'}, "No image selected in the UV Editor.")
                return {'CANCELLED'}

            if p_image.size[0] == 0 or p_image.size[1] == 0:
                self.report({'ERROR'}, "The active image in the UV Editor is incorrect.")
                return {'CANCELLED'}

            width, height = p_image.size[0], p_image.size[1]
        else:
            width, height = self.custom_width, self.custom_height

        self.uv_pixel_width = self.pixel_count / width
        self.uv_pixel_height = self.pixel_count / height

        self.uv_pixel_width_percent = self.uv_pixel_width * 100
        self.uv_pixel_height_percent = self.uv_pixel_height * 100

        return {'FINISHED'}


class ZUV_OT_CalculateRecommendedMargin(bpy.types.Operator):
    bl_description = 'Calculates suggested margin based on the image size'
    bl_idname = "uv.zenuv_calculate_recommended_margin"
    bl_label = "Calculate Recommended Margin"
    bl_options = {'REGISTER', 'UNDO'}

    image_source: bpy.props.EnumProperty(
        name="Image Source",
        description="Choose the source for image dimensions",
        items=[
            ('CUSTOM', "Custom Image Size", "Use custom width and height"),
            ('ACTIVE_UV', "Active Image in UV Editor", "Use active image in the UV Editor")
        ],
        default='CUSTOM'
    )
    custom_width: bpy.props.IntProperty(
        name="Custom Width",
        description="Width of the custom image in pixels",
        default=1024,
        min=1
    )
    custom_height: bpy.props.IntProperty(
        name="Custom Height",
        description="Height of the custom image in pixels",
        default=1024,
        min=1
    )
    recommended_margin: bpy.props.FloatProperty(
        name="Recommended Margin (Pixels)",
        description="Suggested UV margin based on the image size",
        default=0.0,
        precision=2
    )
    recommended_margin_units: bpy.props.FloatProperty(
        name="Recommended Margin (Units)",
        description="Suggested UV margin in UV units based on the image size",
        default=0.0,
        precision=4
    )

    @classmethod
    def poll(cls, context):
        return context.space_data.type == 'IMAGE_EDITOR'

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "image_source")

        is_error = False

        box = layout.box()

        if self.image_source == 'CUSTOM':
            box.enabled = self.image_source == 'CUSTOM'
            col = box.column(align=True)
            col.label(text="Custom Image Size:")
            col = box.column(align=True)
            col.prop(self, "custom_width")
            col.prop(self, "custom_height")
        else:
            from ZenUV.ops.trimsheets.trimsheet_utils import ZuvTrimsheetUtils
            p_image = ZuvTrimsheetUtils.getActiveImage(context)
            if p_image:
                col = box.column(align=True)
                col.label(text="Image Size:")
                col = box.column(align=True)
                col.enabled = False
                col.prop(p_image, "size", index=0, text='Width')
                col.prop(p_image, "size", index=1, text='Height')
            else:
                is_error = True
                col = box.column(align=True)
                col.alert = True
                col.label(text="Image Size: Not Defined")
                col = box.column(align=True)
                col.alert = True
                col.label(text='Width: 0')
                col.label(text='Height: 0')

        box = layout.box()
        box.enabled = not is_error
        box.alert = is_error
        box.label(text="Recommended Margin:")
        box.prop(self, "recommended_margin", text="Margin (Pixels)")
        box.prop(self, "recommended_margin_units", text="Margin (Units)")

    def execute(self, context):
        if self.image_source == 'ACTIVE_UV':
            from ZenUV.ops.trimsheets.trimsheet_utils import ZuvTrimsheetUtils
            p_image = ZuvTrimsheetUtils.getSpaceDataImage(context)
            if p_image is None:
                self.report({'ERROR'}, "No image selected in the UV Editor.")
                return {'CANCELLED'}

            if p_image.size[0] == 0 or p_image.size[1] == 0:
                self.report({'ERROR'}, "The active image in the UV Editor is incorrect.")
                return {'CANCELLED'}

            min_value = min(p_image.size[0], p_image.size[1])
        else:
            min_value = min(self.custom_width, self.custom_height)

        self.recommended_margin = self.calculate_recommended_margin(min_value)
        self.recommended_margin_units = round(self.recommended_margin / min_value, 4)

        self.report({'INFO'}, f'Recommended margin is {self.recommended_margin} px or {round(self.recommended_margin_units, 4)} units')

        return {'FINISHED'}

    def calculate_recommended_margin(self, im_size):
        if im_size <= 256:
            return 2.0
        elif im_size <= 512:
            return 4.0
        elif im_size <= 1024:
            return 8.0
        elif im_size <= 2048:
            return 16.0
        elif im_size <= 4096:
            return 32.0
        elif im_size <= 8192:
            return 64.0
        else:
            return 128.0


def draw_check_operators(context: bpy.types.Context, layout: bpy.types.UILayout):
    ''' @Draw Check Sys operators '''
    from ZenUV.ops.operators import ZUV_OT_CorrectSelfIntersecting

    col = layout.column(align=True)
    col.label(text="Select:")
    col.operator(ZUV_OT_SelectEdgesByIndex.bl_idname, text=ZUV_OT_SelectEdgesByIndex.bl_label.replace('Select', ''))
    # Zero Area
    ot = col.operator('uv.zenuv_select_by_uv_area', text='Zero Area Faces')
    ot.mode = 'FACE'
    ot.clear_selection = True
    ot.condition = 'ZERO'
    ot.treshold = 0.0
    # --
    col.operator(ZUV_OT_SelectEdgesWithoutFaces.bl_idname, text=ZUV_OT_SelectEdgesWithoutFaces.bl_label.replace('Select', ''))
    col.operator(ZUV_OT_SelectEdgesWithMultipleLoops.bl_idname, text=ZUV_OT_SelectEdgesWithMultipleLoops.bl_label.replace('Select', ''))

    if context.space_data.type == 'VIEW_3D':
        col.operator(ZUV_OT_SelectEmptyObjects.bl_idname, text=ZUV_OT_SelectEmptyObjects.bl_label.replace('Select', ''))
        col.operator(ZUV_OT_SelectDoubledVertices.bl_idname, text=ZUV_OT_SelectDoubledVertices.bl_label.replace('Select', ''))
        col.operator(ZUV_OT_SelectFreeVertices.bl_idname, text=ZUV_OT_SelectFreeVertices.bl_label.replace('Select', ''))

    col.label(text="Info:")
    col.operator(ZUV_OT_IslandCounter.bl_idname).show_selected_only = False
    col.operator(ZUV_OT_CalcUvEdgesLengths.bl_idname)
    if context.space_data.type == 'IMAGE_EDITOR':
        col.operator(ZUV_OT_CalculateUVPixelSize.bl_idname)

    col.label(text='Misc:')
    col.operator(ZUV_OT_ClearMeshAttributes.bl_idname)
    col.operator(ZUV_OT_SetViewportDisplayMode.bl_idname)
    col.operator(ZUV_OT_CorrectSelfIntersecting.bl_idname)


class ZUV_PT_3DV_CheckPanel(bpy.types.Panel):
    """  Check tool 3D panel """
    bl_label = "Tools"
    bl_space_type = ZUV_SPACE_TYPE
    bl_region_type = ZUV_REGION_TYPE
    bl_category = ZUV_PANEL_CATEGORY
    bl_options = {'DEFAULT_CLOSED'}
    bl_parent_id = "ZUV_PT_Checker"

    def draw(self, context):
        draw_check_operators(context, self.layout)


class ZUV_PT_UVL_CheckPanel(bpy.types.Panel):
    """  Check tool UV panel """
    bl_label = ZUV_PT_3DV_CheckPanel.bl_label
    bl_space_type = 'IMAGE_EDITOR'
    bl_region_type = ZUV_REGION_TYPE
    bl_category = ZUV_PANEL_CATEGORY
    bl_options = {'DEFAULT_CLOSED'}
    bl_parent_id = "ZUV_PT_Checker_UVL"

    draw = ZUV_PT_3DV_CheckPanel.draw


@dataclass
class DisplayItem:
    modes: set = set(),
    spaces: set = set(),
    select_op_id: str = '',
    display_text: str = ''


# ''' @Draw Display Items '''
t_draw_modes = {
    'FINISHED': DisplayItem({'EDIT_MESH'}, {'UV', '3D'}, 'uv.zenuv_select_finished'),
    'FLIPPED': DisplayItem({'EDIT_MESH'}, {'UV', '3D'}, 'uv.zenuv_select_flipped'),
    'STRETCHED': DisplayItem({'EDIT_MESH'}, {'UV', '3D'}, 'uv.zenuv_select_stretched_faces'),
    'EXCLUDED': DisplayItem({'EDIT_MESH'}, {'UV', '3D'}, 'uv.zenuv_select_pack_excluded'),
    'OVERLAPPED': DisplayItem({'EDIT_MESH'}, {'UV', '3D'}, 'uv.select_overlap'),
    'SELF_INTERSECTING': DisplayItem({'EDIT_MESH'}, {'UV'}, 'uv.zenuv_select_self_intersecting'),
    'UV_BORDERS': DisplayItem({'EDIT_MESH'}, {'UV', '3D'}, 'uv.zenuv_select_uv_borders'),
    'UV_NO_SYNC': DisplayItem({'EDIT_MESH'}, {'3D'}, ''),
    'SEAMS': DisplayItem({'EDIT_MESH'}, {'UV'}, ''),
    'TEXEL_DENSITY': DisplayItem({'EDIT_MESH'}, {'UV', '3D'}, ''),
    'UV_OBJECT': DisplayItem({'OBJECT'}, {'UV'}, ''),
    'TRIM_COLORS': DisplayItem({'EDIT_MESH'}, {'3D'}, ''),
}

t_draw_system_modes = {
    'TAGGED': DisplayItem({'EDIT_MESH'}, {'3D'}, ''),
}

t_draw_stack_modes = {
    'SIMILAR_STATIC': DisplayItem({'EDIT_MESH'}, {'UV', '3D'}, ''),
    'SIMILAR_SELECTED': DisplayItem({'EDIT_MESH'}, {'UV', '3D'}, 'uv.zenuv_select_similar'),
    'STACKED': DisplayItem({'EDIT_MESH'}, {'UV', '3D'}, 'uv.zenuv_select_stacked'),
    'OVERLAPPED': DisplayItem({'EDIT_MESH'}, {'UV', '3D'}, 'uv.select_overlap'),
}

t_draw_stack_manual_modes = {
    'STACKED_MANUAL': DisplayItem({'EDIT_MESH'}, {'UV', '3D'}, ''),
}


def is_draw_active_in_ui(context: bpy.types.Context):
    p_scene = context.scene

    b_active = (hasattr(context.space_data, 'overlay') and context.space_data.overlay.show_overlays) or not p_scene.zen_uv.ui.use_draw_overlay_sync
    if bpy.app.version >= (3, 3, 0):
        b_active = b_active and (hasattr(context.space_data, 'show_gizmo') and context.space_data.show_gizmo)

    return b_active


def is_draw_mode_active(context: bpy.types.Context, s_mode: str):
    b_active = is_draw_active_in_ui(context)
    if b_active:
        p_scene = context.scene
        _, p_mode = p_scene.zen_uv.ui.get_draw_mode_pair_by_context(context)
        b_active = p_mode == s_mode
    return b_active


def draw_checker_display_items(layout: bpy.types.UILayout, context: bpy.types.Context, t_modes: dict):
    ''' @Draw Checker Sys Display Items '''
    p_scene = context.scene

    b_active = is_draw_active_in_ui(context)

    attr_name, p_mode = p_scene.zen_uv.ui.get_draw_mode_pair_by_context(context)
    s_space = attr_name.replace('draw_mode_', '')

    s_context_mode = context.mode

    col = layout.column(align=True)
    col.active = b_active

    b_is_uv = s_space == 'UV'

    v: DisplayItem
    for k, v in t_modes.items():
        if s_context_mode in v.modes and s_space in v.spaces:
            row = col.row(align=True)

            if b_is_uv:
                # NOTE: Special case for stretched
                if k == 'STRETCHED':
                    op = row.operator(
                        "wm.context_set_boolean",
                        text="Stretched",
                        icon='HIDE_OFF',
                        depress=context.space_data.uv_editor.show_stretch)
                    op.data_path = "space_data.uv_editor.show_stretch"
                    op.value = not context.space_data.uv_editor.show_stretch

                    row.operator(v.select_op_id, text='', icon="RESTRICT_SELECT_OFF")
                    continue

            b_is_enabled = p_mode == k

            if v.display_text is None:
                s_display_text = ''
            else:
                s_display_text = v.display_text if v.display_text else layout.enum_item_name(p_scene.zen_uv.ui, attr_name, k)

            op = row.operator('wm.context_set_enum', text=s_display_text, depress=b_is_enabled, icon='HIDE_OFF')
            op.data_path = 'scene.zen_uv.ui.' + attr_name
            op.value = 'NONE' if b_is_enabled else k
            if v.select_op_id:
                row.operator(v.select_op_id, text='', icon="RESTRICT_SELECT_OFF")


class ZUV_PT_3DV_CheckDisplayPanel(bpy.types.Panel):
    bl_label = "Display"
    bl_space_type = ZUV_SPACE_TYPE
    bl_region_type = ZUV_REGION_TYPE
    bl_category = ZUV_PANEL_CATEGORY
    # bl_options = {'DEFAULT_CLOSED'}
    bl_parent_id = "ZUV_PT_Checker"

    t_AVAILABLE_MODES = {'EDIT_MESH'}
    s_AVAILABLE_MODES = 'Edit Mesh mode'

    @classmethod
    def do_poll(cls, context: bpy.types.Context, t_modes):
        if context.active_object is None:
            return False
        if context.mode not in t_modes:
            return False

        return is_draw_active_in_ui(context)

    @classmethod
    def poll(cls, context: bpy.types.Context):
        return cls.do_poll(context, cls.t_AVAILABLE_MODES)

    def draw_header(self, context: bpy.types.Context):
        layout = self.layout

        layout.popover(panel='ZUV_PT_GizmoDrawProperties', text='', icon='PREFERENCES')

    @classmethod
    def do_poll_reason(cls, context: bpy.types.Context, t_modes, s_modes) -> str:
        if context.active_object is None:
            return 'No Active Object!'
        if context.mode not in t_modes:
            return 'Available in ' + s_modes

        p_scene = context.scene
        if not hasattr(context.space_data, "overlay"):
            return "Available in View3D or UV"

        if not context.space_data.overlay.show_overlays and p_scene.zen_uv.ui.use_draw_overlay_sync:
            return """Turn Overlay On or
Enable Overlay Sync"""

        if bpy.app.version >= (3, 3, 0):
            if not (hasattr(context.space_data, "show_gizmo") and context.space_data.show_gizmo):
                return 'Turn Show Gizmo On'

        return ""

    @classmethod
    def poll_reason(cls, context: bpy.types.Context) -> str:
        return cls.do_poll_reason(context, cls.t_AVAILABLE_MODES, cls.s_AVAILABLE_MODES)

    def draw(self, context: bpy.types.Context):
        ''' @Draw Check Display Panel '''
        layout = self.layout

        t_blender_draws = {
            'show_edge_crease': 'Crease',
            'show_edge_sharp': 'Sharp',
            'show_edge_bevel_weight': 'Bevel',
            'show_edge_seams': 'Seams',
        }

        row = layout.row(align=True)
        for k, v in t_blender_draws.items():
            p_value = getattr(context.space_data.overlay, k)
            op = row.operator('wm.context_set_boolean', text=v, depress=p_value)
            op.data_path = f'space_data.overlay.{k}'
            op.value = not p_value

        draw_checker_display_items(layout, context, t_draw_modes)


class ZUV_PT_UVL_CheckDisplayPanel(bpy.types.Panel):
    bl_label = ZUV_PT_3DV_CheckDisplayPanel.bl_label
    bl_space_type = 'IMAGE_EDITOR'
    bl_region_type = ZUV_REGION_TYPE
    bl_category = ZUV_PANEL_CATEGORY
    # bl_options = {'DEFAULT_CLOSED'}
    bl_parent_id = "ZUV_PT_Checker_UVL"

    t_AVAILABLE_MODES = {'EDIT_MESH', 'OBJECT'}
    s_AVAILABLE_MODES = 'Edit Mesh | Object modes'

    @classmethod
    def poll(cls, context: bpy.types.Context):
        return ZUV_PT_3DV_CheckDisplayPanel.do_poll(context, cls.t_AVAILABLE_MODES)

    @classmethod
    def poll_reason(cls, context: bpy.types.Context) -> str:
        return ZUV_PT_3DV_CheckDisplayPanel.do_poll_reason(context, cls.t_AVAILABLE_MODES, cls.s_AVAILABLE_MODES)

    draw_header = ZUV_PT_3DV_CheckDisplayPanel.draw_header

    def draw(self, context: bpy.types.Context):
        layout = self.layout

        from ZenUV.ops.trimsheets.trimsheet_utils import ZuvTrimsheetUtils
        from ZenUV.ops.trimsheets.darken_image import ZUV_OT_DarkenImage

        p_image = ZuvTrimsheetUtils.getActiveImage(context)
        row = layout.row(align=True)
        row.enabled = p_image is not None
        row.operator('uv.zuv_darken_image', depress=ZUV_OT_DarkenImage.is_mode_on(context))

        draw_checker_display_items(layout, context, t_draw_modes)


class ZUV_PT_3DV_SubStackPanel(bpy.types.Panel):
    bl_label = "Stacks"
    bl_space_type = ZUV_SPACE_TYPE
    bl_region_type = ZUV_REGION_TYPE
    bl_category = ZUV_PANEL_CATEGORY
    bl_options = {'DEFAULT_CLOSED'}
    bl_parent_id = "ZUV_PT_3DV_CheckDisplayPanel"

    @classmethod
    def poll(cls, context: bpy.types.Context):
        return context.mode in {'EDIT_MESH'}

    @classmethod
    def poll_reason(cls, context: bpy.types.Context) -> str:
        if context.mode not in {'EDIT_MESH'}:
            return 'Available in Edit Mesh'
        return ''

    def draw_header(self, context: bpy.types.Context):
        layout = self.layout

        layout.popover(panel='STACK_PT_DrawProperties', text='', icon='PREFERENCES')

    def draw(self, context):
        draw_checker_display_items(self.layout, context, {**t_draw_stack_modes, **t_draw_stack_manual_modes})


class ZUV_PT_UVL_SubStackPanel(bpy.types.Panel):
    bl_label = "Stacks"
    bl_space_type = 'IMAGE_EDITOR'
    bl_region_type = ZUV_REGION_TYPE
    bl_category = ZUV_PANEL_CATEGORY
    bl_options = {'DEFAULT_CLOSED'}
    bl_parent_id = "ZUV_PT_UVL_CheckDisplayPanel"

    draw_header = ZUV_PT_3DV_SubStackPanel.draw_header

    draw = ZUV_PT_3DV_SubStackPanel.draw

    poll = ZUV_PT_3DV_SubStackPanel.poll

    poll_reason = ZUV_PT_3DV_SubStackPanel.poll_reason


classes = (
    ZUV_OT_SelectEdgesByIndex,
    ZUV_OT_SelectEdgesWithoutFaces,
    ZUV_OT_SelectEdgesWithMultipleLoops,
    ZUV_OT_IslandCounter,
    ZUV_OT_SelectEmptyObjects,
    ZUV_OT_ClearMeshAttributes,
    ZUV_OT_SelectDoubledVertices,
    ZUV_OT_SetViewportDisplayMode,
    ZUV_OT_SelectFreeVertices,
    ZUV_OT_ShowIslandArea,
    ZUV_OT_CalcUvEdgesLengths,
    ZUV_OT_CalculateUVPixelSize,
    ZUV_OT_CalculateRecommendedMargin
)

checker_parented_panels = (
    ZUV_PT_3DV_TextureCheckerSetup,

    ZUV_PT_3DV_CheckDisplayPanel,
    ZUV_PT_UVL_CheckDisplayPanel,

    ZUV_PT_3DV_SubStackPanel,
    ZUV_PT_UVL_SubStackPanel,

    ZUV_PT_3DV_CheckPanel,
    ZUV_PT_UVL_CheckPanel
)


def register():
    RegisterUtils.register(classes)


def unregister():
    RegisterUtils.unregister(classes)
