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

"""
    Zen UV Stack System
"""

import bpy
import bmesh
from bpy.props import BoolProperty
from mathutils import Vector
from ZenUV.utils.generic import (
    get_mesh_data,
    update_indexes,
    get_dir_vector,
    ZenKeyEventSolver
)
from ZenUV.prop.zuv_preferences import get_prefs
from ZenUV.utils.transform import bound_box
from ZenUV.stacks.utils import (
    StacksSystem,
    get_master_parameters,
    STATISTIC
)
from ZenUV.utils.generic import resort_by_type_mesh_in_edit_mode_and_sel, verify_uv_layer

from ZenUV.ui.labels import ZuvLabels
from ZenUV.utils.clib.lib_init import StackSolver
from ZenUV.ui.pie import ZsPieFactory
from ZenUV.utils.progress import ProgressBar, ProgressCancelException
from ZenUV.utils.vlog import Log


def unstack(context, data, offset: Vector, progress: ProgressBar, use_iterative_unstack: bool = False, in_uv_area_only: bool = True):

    from ZenUV.utils.bounding_box import BoundingBox2d
    from ZenUV.ops.transform_sys.transform_utils.transform_loops import TransformLoops

    for obj_name, islands in data["objs"].items():
        obj = context.scene.objects[obj_name]
        bm = bmesh.from_edit_mesh(obj.data)
        uv_layer = verify_uv_layer(bm)

        p_offset = offset.copy()
        for island_name, indices in islands.items():
            if island_name == "master_island":
                continue

            island = [bm.faces[index] for index in indices]

            if in_uv_area_only:
                island_bbox = BoundingBox2d(islands=[island, ], uv_layer=uv_layer)
                if island_bbox.inside_of_uv_area():
                    TransformLoops.move_loops([lp for f in island for lp in f.loops], uv_layer, delta=p_offset)
            else:
                TransformLoops.move_loops([lp for f in island for lp in f.loops], uv_layer, delta=p_offset)

            if use_iterative_unstack:
                p_offset += offset

        bmesh.update_edit_mesh(obj.data, loop_triangles=False)


def find_master_in_data(context, objs_data):
    """
        Find master island in data and return list master_name, master, position
        If master not found in DATA - try to find master by paramethers and return.
    """
    master_name = "master_island"
    for obj_name, islands in objs_data['objs'].items():
        if master_name in islands:
            indices = islands[master_name]
            master_loop_indices, position, master_td, master_face_indices = get_master_parameters(context, obj_name, indices)
            return master_name, master_loop_indices, position, master_td, master_face_indices
    for obj_name, islands in objs_data['objs'].items():
        island_name = list(islands.keys())[0]
        master_loop_indices, position, master_td, master_face_indices = get_master_parameters(context, obj_name, islands[island_name])
    return master_name, master_loop_indices, position, master_td, master_face_indices


def calc_position_distortion(island, uv_layer):
    """ Return conditional distortion by mean island position """
    pos_distortion = bound_box(islands=[island], uv_layer=uv_layer)["cen"]
    return pos_distortion


def calc_distortion_fac(bm, island_ind, uv_layer):
    """ Returns the distortion factor for a given set of polygons """
    distortion = 0
    bm.faces.ensure_lookup_table()
    island = [bm.faces[index] for index in island_ind]
    loops = [loop for face in island for loop in face.loops]
    # for face in island:
    for loop in loops:
        mesh_angle = loop.calc_angle()
        vec_0 = get_dir_vector(loop[uv_layer].uv, loop.link_loop_next[uv_layer].uv)
        vec_1 = get_dir_vector(loop[uv_layer].uv, loop.link_loop_prev[uv_layer].uv)
        uv_angle = vec_0.angle(vec_1, 0.00001)
        distortion += abs(mesh_angle - uv_angle)
    pos_distortion = calc_position_distortion(island, uv_layer)
    if max(pos_distortion) >= 1 \
            or min(pos_distortion) <= 0:
        distortion += 1
    return distortion


def find_by_condition(context, stack, selected_only):
    if selected_only:
        master_name = stack["select"]
        for obj_name, islands in stack['objs'].items():
            if master_name in islands:
                indices = islands[master_name]
                master_obj_name = obj_name
                master_island_data = {"master_island": indices}
                island_name = master_name
    else:
        distortion_dict = dict()
        # Create Distortion DICT for every island in every object
        for obj_name, islands in stack["objs"].items():
            obj = context.scene.objects[obj_name]
            me, bm = get_mesh_data(obj)
            uv_layer = verify_uv_layer(bm)
            for island, indices in islands.items():
                if obj_name not in distortion_dict.keys():
                    distortion_dict[obj_name] = dict()
                obj = distortion_dict[obj_name]
                obj[island] = dict()
                obj[island]["indices"] = indices
                obj[island]["distortion"] = calc_distortion_fac(bm, indices, uv_layer)
        # Find island with minimal distortion
        min_distortion = float('inf')
        master_island = None
        for obj, islands in distortion_dict.items():
            for island, i_data in islands.items():
                if i_data["distortion"] < min_distortion:
                    master_island = dict()
                    master_island[obj] = dict()
                    master_island[obj][island] = i_data["indices"]
                    min_distortion = i_data["distortion"]

        # Store Master Island Data
        master_obj_name = list(master_island.keys())[0]
        island_name = list(master_island[master_obj_name])[0]
        indices = master_island[master_obj_name][island_name]
        master_island_data = {"master_island": indices}

    return master_obj_name, island_name, master_island_data


def detect_masters(context, sim_data, selected_only):
    stacks_count = 0
    master_obj_name = None

    for sim_index, stack in sim_data.items():
        if selected_only:
            if stack["count"] > 1 and stack["select"]:
                stacks_count += 1
                master_obj_name, island_name, master_island_data = find_by_condition(context, stack, selected_only)
            else:
                stacks_count += 1
                master_obj_name = None
        else:
            if stack["count"] > 1:
                stacks_count += 1
                master_obj_name, island_name, master_island_data = find_by_condition(context, stack, selected_only)
            else:
                stacks_count += 1
                master_obj_name = None

        if master_obj_name:
            # Implement Master Island in Sym Data
            stack["objs"][master_obj_name].pop(island_name)
            stack["objs"][master_obj_name].update(master_island_data)

    return sim_data


def get_master_position(context, data):
    """ Return position of the selected island """
    sync_uv = context.scene.tool_settings.use_uv_select_sync
    position = None
    for obj_name, islands in data["objs"].items():
        if position:
            return position
        else:
            obj = context.scene.objects[obj_name]
            me, bm = get_mesh_data(obj)
            uv_layer = verify_uv_layer(bm)
            for island, indices in islands.items():
                m_island = [bm.faces[index] for index in indices]
                if sync_uv:
                    if True in [f.select for f in m_island]:
                        position = bound_box(islands=[m_island], uv_layer=uv_layer)["cen"]
                else:
                    if True in [loop[uv_layer].select for face in m_island for loop in face.loops]:
                        position = bound_box(islands=[m_island], uv_layer=uv_layer)["cen"]
    return position


class ZUV_OT_Unstack(bpy.types.Operator):
    bl_idname = "uv.zenuv_unstack"
    bl_label = 'Unstack'
    bl_description = 'Shift Islands from stacks in the given direction'
    bl_options = {'REGISTER', 'UNDO'}

    def update_break(self, context):
        if self.breakStack:
            self.increment = 1.0

    use_iterative_unstack: bpy.props.BoolProperty(
        name='Iterative Unstack',
        default=False,
        description='Unstack Islands iteratively with moving in given direction'
    )
    UnstackMode: bpy.props.EnumProperty(
        name='Mode',
        description='Mode to Unstack Islands',
        items=[
            ("GLOBAL", 'Global', 'Unstack all Similar Islands'),
            ("STACKED", 'Stacked', 'Unstack Stacked Islands'),
            ("OVERLAPPED", 'Overlapped', 'Unstack Overlapped Islands'),
            ("SELECTED", 'Selected', 'Unstack Selected Islands'),
        ],
        default="STACKED"
    )

    breakStack: bpy.props.BoolProperty(
        name=ZuvLabels.PREF_UNSTACK_BREAK_LABEL,
        default=False,
        description=ZuvLabels.PREF_UNSTACK_BREAK_DESC,
        update=update_break
    )
    increment: bpy.props.FloatProperty(
        name='Unstack Increment',
        description='Unstack Increment',
        default=1.0
    )
    use_seams_as_separator: bpy.props.BoolProperty(
        name='Use Seams',
        default=True,
        description='Use seams as an island separator to prevent stacked islands from self-welding'
    )
    in_uv_area_only: bpy.props.BoolProperty(
        name='Only UV Area',
        default=True,
        description='Unstack islands located in the UV Area only'
    )

    @classmethod
    def description(cls, context, properties):
        if properties:
            if properties.UnstackMode == 'GLOBAL':
                return 'Unstack all Similar Islands'
            elif properties.UnstackMode == 'STACKED':
                return 'Unstack Stacked Islands'
            elif properties.UnstackMode == 'OVERLAPPED':
                return 'Unstack Overlapped Islands'
            elif properties.UnstackMode == 'SELECTED':
                return 'Unstack Selected Islands'
            else:
                return cls.bl_description
        return cls.bl_description

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "UnstackMode")
        layout.prop(self, 'in_uv_area_only')
        layout.prop(self, "use_iterative_unstack")
        layout.prop(self, 'use_seams_as_separator')
        layout.prop(get_prefs(), 'unstack_direction')
        box = layout.box()
        box.prop(self, "breakStack")
        row = box.row()
        row.enabled = self.breakStack
        row.prop(self, "increment")

    def execute(self, context):
        objs = resort_by_type_mesh_in_edit_mode_and_sel(context)
        if not objs:
            self.report({'WARNING'}, "Zen UV: There are no selected objects.")
            return {'CANCELLED'}

        update_indexes(objs)

        if not self.breakStack:
            self.increment = 1.0

        p_direction = get_prefs().unstack_direction

        p_increment = p_direction.normalized() * self.increment
        stacks = StacksSystem(context)

        if self.UnstackMode == 'SELECTED':
            sim_data = stacks.forecast_selected(use_seams_as_separator=self.use_seams_as_separator)
        elif self.UnstackMode == "STACKED":
            sim_data = stacks.get_stacked(use_seams_as_separator=self.use_seams_as_separator)
        elif self.UnstackMode == "GLOBAL":
            sim_data = stacks.forecast_stacks(use_seams_as_separator=self.use_seams_as_separator)
        elif self.UnstackMode == "OVERLAPPED":
            sim_data = stacks.get_overlapped(use_seams_as_separator=self.use_seams_as_separator)

        sim_data = detect_masters(context, sim_data, False)

        # stacks.show_sim_data(sim_data)

        if len(sim_data) > 200:
            progress = ProgressBar(context, 100, text_only=False)
            progress.set_text(prefix="Unstacking:", preposition=" of")
            progress.iterations = len(sim_data)
        else:
            progress = None

        try:
            for data in sim_data.values():
                unstack(context, data, p_increment, progress, self.use_iterative_unstack, self.in_uv_area_only)
                if progress is not None and not progress.update():
                    break
        except Exception as e:
            if progress is not None:
                progress.finish()
            Log.debug(e)
        if progress is not None:
            progress.finish()
        return {'FINISHED'}


class ZUV_OT_Stack_Similar(bpy.types.Operator):
    bl_idname = "uv.zenuv_stack_similar"
    bl_label = 'Stack'
    bl_description = 'Collect all similar islands on stacks'
    bl_options = {'REGISTER', 'UNDO'}

    silent: BoolProperty(
        default=True,
        description="Show stacking report",
        options={'HIDDEN'}
    )
    selected: BoolProperty(
        name='Selected Only',
        default=False,
        description="Stack selected only"
    )

    @classmethod
    def description(cls, context, properties):
        if properties:
            if properties.selected:
                return 'Collect all islands similar to the selected island and stack them at the location of the selected island'
            return cls.bl_description
        return cls.bl_description

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "selected")

    def invoke(self, context, event):
        self.silent = not self.selected
        return self.execute(context)

    @classmethod
    def poll(cls, context):
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH'

    def execute(self, context):
        answer = True, "Finished"
        addon_prefs = get_prefs()
        objs = context.objects_in_mode
        if not objs:
            return {"CANCELLED"}
        update_indexes(objs)
        move_only = addon_prefs.stackMoveOnly
        # Checking that LIB is present or activated
        if not move_only:
            if not StackSolver():
                self.report(
                    {'WARNING'},
                    "Zen UV Library is not installed! Install library or switch on 'Stack Move only' in 'Stack preferences'"
                )
                return {"CANCELLED"}
        stacks = StacksSystem(context)

        progress = ProgressBar(context, 100, text_only=False)
        progress.set_text(prefix="Stacking:", preposition=" of")
        progress.current_step = 0

        if self.selected:
            input_data = stacks.clustered_selected_stacks_with_masters
        else:
            input_data = stacks.clustered_stacks_with_masters

        for master, stack in input_data(progress, self.selected):
            if not progress.update():
                break
            STATISTIC["types"][master.type] += 1
            for cl in stack:
                STATISTIC["types"][cl.type] += 1
                answer = cl.remap(master, move_only=move_only)
                cl.update_mesh()
        part_report = {True: {'INFO'}, False: {'WARNING'}}

        if not self.silent:
            self.report(part_report[answer[0]], answer[1])
        else:
            self.report(part_report[True], "Finished.")

        progress.finish()

        return {'FINISHED'}


class ZUV_OT_Select_Similar(bpy.types.Operator):
    bl_idname = "uv.zenuv_select_similar"
    bl_label = 'Select Similar Islands'
    bl_zen_short_name = 'Similar'
    bl_description = 'Select Islands similar to selected'
    bl_options = {'REGISTER', 'UNDO'}

    area_match: BoolProperty(
        name="Area Matching",
        default=True,
        description="Set strict requirements to Islands Area Matching when Stacking. Disable this option if the Islands have a slightly different Area")

    select_primary: BoolProperty(
        name="Select Primary",
        default=True,
        description="Select Primary Island")

    select_similar: BoolProperty(
        name="Select Similar",
        default=True,
        description="Select Similar")

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "area_match")
        layout.prop(self, "select_primary")
        layout.prop(self, "select_similar")

    @classmethod
    def poll(cls, context):
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH'

    def execute(self, context):
        from ZenUV.utils.generic import resort_by_type_mesh_in_edit_mode_and_sel

        ZsPieFactory.mark_pie_cancelled()

        objs = resort_by_type_mesh_in_edit_mode_and_sel(context)
        if not objs:
            self.report({'WARNING'}, "There are no selected objects")
            return {'CANCELLED'}

        if context.tool_settings.mesh_select_mode[:] != (False, False, True):
            self.report({'WARNING'}, "Switch to the Face selection mode. Otherwise, the result may not be correct.")
        if not self.area_match:
            self.report({'WARNING'}, "Area Match is disabled. The result may not be precise.")
        stacks = StacksSystem(context)

        progress = ProgressBar(context, 100, text_only=False)
        progress.set_text(prefix="Selecting:", preposition=" of")
        progress.current_step = 0

        try:
            for master, stack in stacks.clustered_selected_stacks_with_masters(progress, selected=True, area_match=self.area_match):
                master.select(self.select_primary)
                for cl in stack:
                    if not progress.update():
                        raise ProgressCancelException()
                    cl.select(self.select_similar)
        except ProgressCancelException:
            pass
        progress.finish()
        return {'FINISHED'}


class ZUV_OT_Select_Stacked(bpy.types.Operator):
    bl_idname = "uv.zenuv_select_stacked"
    bl_label = ZuvLabels.OT_SELECT_STACKED_LABEL
    bl_description = ZuvLabels.OT_SELECT_STACKED_DESC
    bl_options = {'REGISTER', 'UNDO'}

    desc: bpy.props.StringProperty(
        name="Description",
        default=ZuvLabels.OT_SYNC_UV_MAPS_DESC,
        options={'HIDDEN'}
    )

    @classmethod
    def description(cls, context, properties):
        if properties:
            addon_prefs = get_prefs()
            zk_mod = addon_prefs.bl_rna.properties['zen_key_modifier'].enum_items
            zk_mod = zk_mod.get(addon_prefs.zen_key_modifier)
            cls.desc = ZuvLabels.OT_SELECT_STACKED_DESC.replace("*", zk_mod.name)
            return cls.desc
        else:
            return cls.bl_description

    def invoke(self, context, event):
        is_modifier_right = ZenKeyEventSolver(context, event, get_prefs()).solve()
        self.clear = not is_modifier_right
        return self.execute(context)

    @classmethod
    def poll(cls, context):
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH'

    def execute(self, context):
        from ZenUV.utils.generic import select_by_context, bpy_deselect_by_context

        StackedSolver = StacksSystem(context)
        stacked = StackedSolver.get_stacked()
        for_select = StackedSolver.get_stacked_faces_ids(stacked)

        if self.clear:
            bpy_deselect_by_context(context)

        for obj_name, faces_ids in for_select.items():
            obj = context.scene.objects[obj_name]
            me = obj.data
            bm = bmesh.from_edit_mesh(me)
            select_by_context(context, bm, [[bm.faces[i] for i in faces_ids], ], state=True)

            bmesh.update_edit_mesh(me, loop_triangles=False)

        return {'FINISHED'}


class ZUV_OT_Select_Stack(bpy.types.Operator):
    bl_idname = "uv.zenuv_select_stack"
    bl_label = 'Select Stack Parts'
    bl_description = 'Select Stack Parts'
    bl_options = {'REGISTER', 'UNDO'}

    clear_selection: bpy.props.BoolProperty(
        name='Clear Selection',
        description='Clears the initial selection before applying the operation',
        default=True)

    mode: bpy.props.EnumProperty(
        name='Mode',
        items=[
            ('PRIMARIES', 'Select Primaries', 'Selects the primary islands as the base instances for stacking'),
            ('REPLICAS', 'Select Replicas', 'Selects the replica islands with the same topology as the primaries'),
            ('SINGLES', 'Select Singles', 'Selects unique islands that do not have any similar copies')
        ],
        default='PRIMARIES',
    )

    def invoke(self, context, event):
        self.objs = context.objects_in_mode
        if not self.objs:
            return {"CANCELLED"}

        is_modifier_right = ZenKeyEventSolver(context, event, get_prefs()).solve()

        if not is_modifier_right:
            self.clear_selection = True
        else:
            self.clear_selection = False
        return self.execute(context)

    @classmethod
    def description(cls, context, properties):
        if properties:
            addon_prefs = get_prefs()
            return f'Select {properties.mode.title()}. Use {addon_prefs.zen_key_modifier.title()} - Append to existing selection'
        else:
            return cls.bl_description

    @classmethod
    def poll(cls, context):
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH'

    def execute(self, context):
        from .utils import Cluster
        from ZenUV.utils.generic import bpy_deselect_by_context

        cl: Cluster = None
        master: Cluster = None

        if self.clear_selection:
            bpy_deselect_by_context(context)

        stacks = StacksSystem(context)

        progress = ProgressBar(context, 100, text_only=False)
        progress.set_text(prefix="Search:", preposition=" of")
        progress.update()
        progress.current_step = 0

        if self.mode == 'SINGLES':
            for singleton in stacks.clustered_singletons(progress):
                singleton.select(True)
        else:
            for master, stack in stacks.clustered_stacks_with_masters(progress, selected=False):
                if not progress.update():
                    break
                if self.mode == 'PRIMARIES':
                    master.select(True)
                if self.mode == 'REPLICAS':
                    for cl in stack:
                        cl.select(True)

        if progress.pb is not None:
            progress.finish()

        return {'FINISHED'}


if __name__ == '__main__':
    pass
