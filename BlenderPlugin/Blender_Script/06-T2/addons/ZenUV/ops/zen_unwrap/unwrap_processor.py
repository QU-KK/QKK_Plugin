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
from dataclasses import dataclass, asdict
from math import pi
from ...utils.register_util import RegisterUtils

from ...utils.bounding_box import BoundingBox2d
from ...utils.generic import (
    ResortObjects,
    bpy_select_by_context,
    verify_uv_layer
)
from ...ops.world_orient import oCluster

from ...utils.loops_factory import LoopsFactory
from ...utils.uv_factory import UvIslandUtils, SelectionUtils
from ...utils.blender_zen_utils import is_loop_domain, get_selection_mode, ZenPolls
from ...utils.iter_utils import IterUtils

from ...utils.constants import ALL_AXES_SCOPE
from ...ops.transform_sys.transform_utils.transform_loops import TransformLoops
from ...ops.zen_unwrap.props import ZenUnwrapProps

from ...utils.vlog import Log


class UC_Lables:

    ENUM_UWRP_CONSTR_INFLUENCE_MODE_L = 'Mode'
    ENUM_UWRP_CONSTR_INFLUENCE_MODE_D = 'Affect Islands or selected Faces'

    ENUM_UWRP_CONSTR_INFLUENCE_MODE_ISL_L = 'Islands'
    ENUM_UWRP_CONSTR_INFLUENCE_MODE_FACE_L = 'Faces'

    PREF_UWRP_CONSTR_URP_METHOD_L = 'Method'
    PREF_UWRP_CONSTR_URP_METHOD_D = 'Unwrapping method'

    LAB_UWRP_CONSTR_ADV = 'Unwrap Options:'

    # Enums prop METHOD
    ENUM_UWRP_CONSTR_URP_METHOD_ANGL_BAS_L = 'Angle Based'
    ENUM_UWRP_CONSTR_URP_METHOD_ANGL_BAS_D = 'Angle Based'
    ENUM_UWRP_CONSTR_URP_METHOD_CONFORM_L = 'Conformal'
    ENUM_UWRP_CONSTR_URP_METHOD_CONFORM_D = 'Conformal'

    PREF_UWRP_CONSTR_FULL_URP_L = 'Full Unwrap'
    PREF_UWRP_CONSTR_FULL_URP_D = 'Unwrap Island, but keep in init bounding box limits'

    PREF_UWRP_CONSTR_FILL_H_L = 'Fill Holes'
    PREF_UWRP_CONSTR_FILL_H_D = 'Virtual fill holes in meshes before unwrapping'

    PREF_UWRP_CONSTR_CORR_ASP_L = 'Correct Aspect'
    PREF_UWRP_CONSTR_CORR_ASP_D = 'Map UVs taking image aspect ratio into account'

    PREF_UWRP_CONSTR_USE_SUBS_L = 'Use Subsurf Modifier'
    PREF_UWRP_CONSTR_USE_SUBS_D = 'Map UVs taking vertex position after subsurf into account'


class UC_IslandState:

    def __init__(
        self,
        bm: bmesh.types.BMesh,
        island: list,
        uv_layer: bmesh.types.BMLayerItem,
        ignore_pins: bool = False
    ) -> None:

        """
        :prop bm: bmesh.types.BMesh
        :prop island: [BMFace, BMFace, ... BMFace]
        :prop uv_layer: uv_layer: bmesh.types.BMLayerItem
        :prop ignore_pins: bool
        """

        self.uv_layer = uv_layer
        self.bbox = BoundingBox2d(islands=[island, ], uv_layer=uv_layer)

        self.reserved_pins = self._collect_reserved_pins(island) if ignore_pins else []
        self.uv_storage = self._store_uvs(island)
        self.orientation = self._get_orientation(bm, uv_layer)

    def _get_orientation(self, bm, uv_layer):
        m_face_index = list(self.uv_storage.keys())[0]
        orient_vector = (bm.faces[m_face_index].loops[0][uv_layer].uv - bm.faces[m_face_index].loops[0].link_loop_next[uv_layer].uv) * 0.5
        directions = {orient_vector.angle(axe, pi * 2): axe for axe in ALL_AXES_SCOPE}
        return directions[min(directions.keys())]

    def _get_restoration_angle(self, bm, uv_layer):
        cur_orientation = self._get_orientation(bm, uv_layer)
        return self.orientation.angle_signed(cur_orientation)

    def _collect_reserved_pins(self, island):
        loops = [lp[self.uv_layer] for f in island for lp in f.loops]
        pins_state = [lp.pin_uv for lp in loops]
        for lp in loops:
            lp.pin_uv = False
        return pins_state

    def _restore_reserved_pins(self, loops, uv_layer):
        if any(set(self.reserved_pins)):
            for loop, state in zip(loops, self.reserved_pins):
                loop[uv_layer].pin_uv = state

    def _store_uvs(self, island):
        return {f.index: [lp[self.uv_layer].uv.copy() for lp in f.loops] for f in island}

    def restore_state(self, bm, uv_layer, restore_location=False, restore_orientation=False, restore_size=False, ignore_pins=False, image_aspect: float = 1.0):
        island = [bm.faces[i] for i in self.uv_storage.keys()]
        loops = [lp for f in island for lp in f.loops]
        angle = self._get_restoration_angle(bm, uv_layer) if restore_orientation else 0.0

        TransformLoops.fit_loops(
            loops,
            uv_layer,
            self.bbox,
            fit_axis_name='MAX_FIT',
            angle=angle,
            image_aspect=image_aspect,
            move=restore_location,
            rotate=restore_orientation,
            scale=restore_size,
        )

        if ignore_pins:
            self._restore_reserved_pins(loops, uv_layer)

    def _pin_edges_set(self, bm, uv_layer, island_loops_idxs, action):
        s_isl_loops_idxs = set(island_loops_idxs)
        for lp in [lp for lp in bm.edges[self.p_edge].link_loops if lp.index in s_isl_loops_idxs]:
            lp[uv_layer].pin_uv = action
            lp.link_loop_next[uv_layer].pin_uv = action


class UC_ObjState:

    def __init__(
        self,
        context: bpy.types.Context,
        bm: bmesh.types.BMesh,
        obj: bpy.types.Object,
        uv_layer: bmesh.types.BMLayerItem,
        islands: list,
        ignore_pins: bool = False
    ) -> None:

        self.obj = obj
        self.islands = self._collect_islands(bm, islands, uv_layer, ignore_pins)
        self.selection = self._store_selection(context, bm, uv_layer)
        self._select_islands(context, bm, islands, uv_layer)

    def _store_selection(self, context, bm, uv_layer):
        if is_loop_domain(context):
            selection_mode = get_selection_mode(context)
            selected_loops = LoopsFactory.get_loops_by_sel_mode(context, bm, uv_layer, only_uv_edges=selection_mode == 'EDGE')
            return [lp.index for lp in selected_loops]
        else:
            return [f.index for f in bm.faces if f.select]

    def _select_islands(self, context, bm, islands, uv_layer):
        for island in islands:
            SelectionUtils.select_faces_any_context(context, island, state=True, bm=bm, uv_layer=uv_layer)

    def _collect_islands(self, bm, islands, uv_layer, ignore_pins):
        return [UC_IslandState(bm, i, uv_layer, ignore_pins=ignore_pins) for i in islands]

    def restore_selection(self, context, bm, uv_layer):
        if is_loop_domain(context):
            loops = [lp for f in bm.faces for lp in f.loops]
            looplist = [loops[i] for i in self.selection]
            LoopsFactory.select_loops(context, bm, looplist, uv_layer, state=True)
        else:
            facelist = [bm.faces[i] for i in self.selection]
            SelectionUtils.select_faces_any_context(context, facelist, state=True, bm=bm, uv_layer=uv_layer)
        bm.select_flush_mode()


@dataclass
class UnwrapProcessorProps():

    influence_mode: str = "SELECTION"
    unwrap_allowed: bool = True
    restore_location: bool = False
    restore_orientation: bool = False
    restore_size: bool = False
    ignore_pins: bool = False
    orient_to_world: bool = False

    # Blender Unwrap operator properties

    urp_method: str = 'ANGLE_BASED'
    fill_holes: bool = True
    correct_aspect: bool = True
    use_subsurf_data: bool = False


class UnwrapProcessor:

    message = ''

    def __init__(self, context: bpy.types.Context, PROPS: UnwrapProcessorProps) -> None:
        self.uc_objs_collector = []
        self.PROPS = PROPS

    def _gathering_input_data(self, context: bpy.types.Context, PROPS: UnwrapProcessorProps):
        objs = ResortObjects.resort_by_type_mesh_in_edit_mode_and_sel(context)
        if not objs:
            UnwrapProcessor.message = "No objects selected."
            return False

        for obj, bm, uv_layer in IterUtils.iter_objs_with_bmesh_uv(objs, context, skip_obj_if_no_uv=False):

            if not uv_layer:
                uv_layer = verify_uv_layer(bm)

            if PROPS.influence_mode == 'ISLAND':
                islands = UvIslandUtils.get_selected_uv_islands(context, bm, uv_layer)
            elif PROPS.influence_mode == 'SELECTION':
                loops = LoopsFactory.get_loops_by_sel_mode(context, bm, uv_layer, groupped=True)
                islands = [{lp.face for lp in cluster} for cluster in loops]

            elif PROPS.influence_mode == 'FACES':
                loops = LoopsFactory.get_loops_by_sel_mode(context, bm, uv_layer, groupped=True, per_face=True)
                islands = [{lp.face for lp in cluster} for cluster in loops]
            self.uc_objs_collector.append(
                UC_ObjState(context, bm, obj, uv_layer=uv_layer,  islands=islands, ignore_pins=PROPS.ignore_pins)
            )

    def _select_faces_in_sync_mode_on(self, context):
        if not is_loop_domain(context):
            bpy.ops.uv.select_all(action='DESELECT')

            for uc_obj in self.uc_objs_collector:
                me = uc_obj.obj.data
                bm = bmesh.from_edit_mesh(me)
                uv_layer = verify_uv_layer(bm)

                islands = uc_obj.islands
                for i_state in islands:
                    facelist = [bm.faces[i] for i in i_state.uv_storage.keys()]
                    SelectionUtils.select_faces_any_context(context, facelist, state=True, bm=bm, uv_layer=uv_layer)

                bmesh.update_edit_mesh(uc_obj.obj.data, loop_triangles=False, destructive=False)

    def _unwrap_island_one_by_one(self, context, PROPS):
        for uc_obj in self.uc_objs_collector:
            bm = bmesh.from_edit_mesh(uc_obj.obj.data)
            uv_layer = verify_uv_layer(bm)

            islands = uc_obj.islands
            for i_state in islands:
                bpy_select_by_context(context, action='DESELECT')
                facelist = [bm.faces[i] for i in i_state.uv_storage.keys()]
                SelectionUtils.select_faces_any_context(context, facelist, state=True, bm=bm, uv_layer=uv_layer)
                self._unwrap(PROPS)

            bmesh.update_edit_mesh(uc_obj.obj.data, loop_triangles=False, destructive=False)

    def _unwrap(self, PROPS: UnwrapProcessorProps):
        if PROPS.unwrap_allowed:
            bpy.ops.uv.unwrap(
                method=PROPS.urp_method,
                fill_holes=PROPS.fill_holes,
                correct_aspect=PROPS.correct_aspect,
                use_subsurf_data=PROPS.use_subsurf_data,
                )

    def _is_restoration_allowed(self, PROPS: UnwrapProcessorProps):
        return PROPS.restore_location or PROPS.restore_orientation or PROPS.restore_size

    def _restore_unwrapped_transform(self, context: bpy.types.Context, PROPS: UnwrapProcessorProps):
        from ...ops.transform_sys.transform_utils.tr_utils import ActiveUvImage
        if self._is_restoration_allowed(PROPS):
            island: UC_IslandState = None
            for uc_obj in self.uc_objs_collector:
                me = uc_obj.obj.data
                bm = bmesh.from_edit_mesh(me)
                uv_layer = verify_uv_layer(bm)

                for island in uc_obj.islands:
                    island.restore_state(
                        bm,
                        uv_layer,
                        PROPS.restore_location,
                        PROPS.restore_orientation,
                        PROPS.restore_size,
                        PROPS.ignore_pins,
                        image_aspect=ActiveUvImage(context).aspect
                    )

        bpy_select_by_context(context, action='DESELECT')

    def _restore_selection(self, context: bpy.types.Context):
        uc_obj: UC_ObjState = None
        for uc_obj in self.uc_objs_collector:

            bm = bmesh.from_edit_mesh(uc_obj.obj.data)
            uv_layer = verify_uv_layer(bm)
            uc_obj.restore_selection(context, bm, uv_layer)
            bmesh.update_edit_mesh(uc_obj.obj.data, loop_triangles=False, destructive=False)

    def _orient_to_world(self, context: bpy.types.Context):
        for uc_obj in self.uc_objs_collector:
            bm = bmesh.from_edit_mesh(uc_obj.obj.data)

            islands = uc_obj.islands
            for i_state in islands:
                cluster = oCluster(context, uc_obj.obj, [bm.faces[i] for i in i_state.uv_storage.keys()], bm)
                cluster.f_orient = True
                cluster.type = "HARD"
                cluster.do_orient_to_world()

            bmesh.update_edit_mesh(uc_obj.obj.data, loop_triangles=False, destructive=False)

    # Unwrapping PRESETS

    def preset_unwrap_automatic(self, context: bpy.types.Context):
        self._gathering_input_data(context, self.PROPS)
        if self.PROPS.influence_mode == 'FACES':
            self._unwrap_island_one_by_one(context, self.PROPS)
        else:
            self._select_faces_in_sync_mode_on(context)
            self._unwrap(self.PROPS)

        self._restore_unwrapped_transform(context, self.PROPS)
        self._restore_selection(context)

        UnwrapProcessor.message = 'Finished'
        return True

    def preset_unwrap_in_place(self, context):
        self.PROPS.ignore_pins = True
        self.PROPS.restore_location = True
        self.PROPS.restore_orientation = True
        self.PROPS.restore_size = True
        self.preset_unwrap_automatic(context)

    def preset_unwrap_and_orient_to_world(self, context: bpy.types.Context):
        self._gathering_input_data(context, self.PROPS)
        self.PROPS.unwrap_allowed = True
        self.PROPS.ignore_pins = True
        if self.PROPS.influence_mode == 'FACES':
            self._unwrap_island_one_by_one(context, self.PROPS)
        else:
            self._select_faces_in_sync_mode_on(context)
            self._unwrap(self.PROPS)
        self._orient_to_world(context)
        self._restore_selection(context)

    def preset_unwrap_by_operator_props(self, context: bpy.types.Context):
        self._gathering_input_data(context, self.PROPS)

        if self.PROPS.influence_mode == 'FACES':
            self._unwrap_island_one_by_one(context, self.PROPS)
        else:
            self._select_faces_in_sync_mode_on(context)
            self._unwrap(self.PROPS)
        if self.PROPS.orient_to_world:
            self._orient_to_world(context)
        self._restore_unwrapped_transform(context, self.PROPS)
        self._restore_selection(context)


class ZuvUnwrapTemplate():

    bl_idname = ""
    bl_label = 'Template UWRP Processor'
    bl_description = 'Template UWRP Processor'

    def get_unwrap_allowed(p_default):
        return bpy.props.BoolProperty(
            name='Unwrap',
            description='',
            default=p_default
        )

    def get_influence_mode(p_default):
        return bpy.props.EnumProperty(
            name=UC_Lables.ENUM_UWRP_CONSTR_INFLUENCE_MODE_L,
            description=UC_Lables.ENUM_UWRP_CONSTR_INFLUENCE_MODE_D,
            items=[
                ("ISLAND", 'Island', ""),
                ("SELECTION", 'Selection', ""),
                ("FACES", "Faces", ""),
            ],
            default=p_default
        )

    def get_restore_location(p_default):
        return bpy.props.BoolProperty(
            name='Restore Location',
            description='Restore Location and Isalnd gabarit',
            default=p_default
        )

    def get_restore_orientation(p_default):
        return bpy.props.BoolProperty(
            name='Restore Orientation',
            description='Restore Orientation',
            default=p_default
        )

    def get_restore_size(p_default):
        return bpy.props.BoolProperty(
            name='Restore Size',
            description='Restore Size',
            default=p_default
        )

    def get_ignore_pins(p_default):
        return bpy.props.BoolProperty(
            name='Ignore Pins',
            description='Ignore Pins',
            default=p_default
        )

    # Blender Unwrap Properties
    def get_urp_method(p_default):
        return bpy.props.EnumProperty(
            name=UC_Lables.PREF_UWRP_CONSTR_URP_METHOD_L,
            description=UC_Lables.PREF_UWRP_CONSTR_URP_METHOD_D,
            items=ZenUnwrapProps.UNWRAP_METHOD_ITEMS,
            default=p_default
        )

    def get_fill_holes(p_default):
        return bpy.props.BoolProperty(
            name=UC_Lables.PREF_UWRP_CONSTR_FILL_H_L,
            description=UC_Lables.PREF_UWRP_CONSTR_FILL_H_D,
            default=p_default
        )

    def get_correct_aspect(p_default):
        return bpy.props.BoolProperty(
            name=UC_Lables.PREF_UWRP_CONSTR_CORR_ASP_L,
            description=UC_Lables.PREF_UWRP_CONSTR_CORR_ASP_D,
            default=p_default
        )

    def get_use_subsurf_data(p_default):
        return bpy.props.BoolProperty(
            name=UC_Lables.PREF_UWRP_CONSTR_USE_SUBS_L,
            description=UC_Lables.PREF_UWRP_CONSTR_USE_SUBS_D,
            default=p_default
        )

    """ NOTE: we are using function-style properties for multiple inheritance approach

        influence_mode: ZuvUnwrapTemplate.get_influence_mode("ISLAND")

        unwrap_allowed: ZuvUnwrapTemplate.get_unwrap_allowed(True)

        restore_location: ZuvUnwrapTemplate.get_restore_location(True)

        restore_orientation: ZuvUnwrapTemplate.get_restore_orientation(True)

        restore_size: ZuvUnwrapTemplate.get_restore_size(True)

        ignore_pins: ZuvUnwrapTemplate.get_ignore_pins(False)

        urp_method: ZuvUnwrapTemplate.get_urp_method('ANGLE_BASED')

        fill_holes: ZuvUnwrapTemplate.get_fill_holes(True)

        correct_aspect: ZuvUnwrapTemplate.get_correct_aspect(True)

        use_subsurf_data: ZuvUnwrapTemplate.get_use_subsurf_data(False)

    """

    @classmethod
    def poll(cls, context: bpy.types.Context):
        return context.mode == "EDIT_MESH"

    @classmethod
    def poll_reason(cls, context: bpy.types.Context):
        if context.mode != 'EDIT_MESH':
            return 'Available in Edit Mesh!'
        return ''

    def draw(self, context: bpy.types.Context):
        layout: bpy.types.UILayout = self.layout
        row = layout.row()
        row.prop(self, "influence_mode")

        self.draw_uwrp_processor_props(layout)

        self.draw_bl_uwrp_props(layout)

    def draw_uwrp_processor_props(self, layout: bpy.types.UILayout):
        layout.prop(self, 'unwrap_allowed')
        layout.prop(self, 'restore_location')
        layout.prop(self, 'restore_size')
        layout.prop(self, 'restore_orientation')
        layout.prop(self, 'ignore_pins')

    def draw_bl_uwrp_props(self, layout: bpy.types.UILayout):
        box = layout.box()
        box.use_property_split = True
        box.label(text=UC_Lables.LAB_UWRP_CONSTR_ADV)
        box.prop(self, "urp_method")
        box.prop(self, "fill_holes")
        box.prop(self, "correct_aspect")
        box.prop(self, "use_subsurf_data")

    def execute(self, context):

        # Sample usage 01 =====================================
        # """
        # Manual delegate Operator properties to the UnwrapProcessorProps
        # """
        # props = UnwrapProcessorProps()

        # props.unwrap_allowed = self.unwrap_allowed
        # props.influence_mode = self.influence_mode
        # props.restore_location = self.restore_location
        # props.restore_orientation = self.restore_orientation
        # props.restore_size = self.restore_size
        # props.ignore_pins = self.ignore_pins

        # UP = UnwrapProcessor(context, props)

        # UP.unwrap_selection(context)
        # ======================================================

        # Sample usage 02 =====================================
        # """
        # Automatic delegate Operator properties to the UnwrapProcessorProps
        # """
        # UP = UnwrapProcessor(context, self.delegate_properties())

        # UP.unwrap_selection(context)
        # ======================================================

        return {'FINISHED'}

    def delegate_properties(self, PROPS: UnwrapProcessorProps):
        """ Automatic delegate Operator properties to the UnwrapProcessorProps """
        PROPS = PROPS()
        prop_class_dict = asdict(PROPS)

        for prp in prop_class_dict:
            attr = getattr(self.properties, prp, None)
            # print(prp, attr)
            if attr is None:
                Log.debug('From class ZuvUnwrapTemplate: ', f'Propertie "{prp}" not present in the {self.bl_idname} Class')
                continue
            setattr(PROPS, prp, attr)
        return PROPS


class ZUV_OT_UnwrapProcessor(bpy.types.Operator, ZuvUnwrapTemplate):

    bl_idname = "uv.zenuv_unwrap_processor"
    bl_label = 'UWRP Processor'
    bl_description = 'UWRP Processor'
    bl_options = {'REGISTER', 'UNDO'}

    influence_mode: ZuvUnwrapTemplate.get_influence_mode("ISLAND")

    unwrap_allowed: ZuvUnwrapTemplate.get_unwrap_allowed(True)

    restore_location: ZuvUnwrapTemplate.get_restore_location(True)

    restore_orientation: ZuvUnwrapTemplate.get_restore_orientation(True)

    restore_size: ZuvUnwrapTemplate.get_restore_size(True)

    ignore_pins: ZuvUnwrapTemplate.get_ignore_pins(False)

    urp_method: ZuvUnwrapTemplate.get_urp_method('ANGLE_BASED')

    fill_holes: ZuvUnwrapTemplate.get_fill_holes(True)

    correct_aspect: ZuvUnwrapTemplate.get_correct_aspect(True)

    use_subsurf_data: ZuvUnwrapTemplate.get_use_subsurf_data(False)

    def execute(self, context):
        UP = UnwrapProcessor(context, self.delegate_properties(UnwrapProcessorProps))

        # UP.preset_unwrap_automatic(context)
        UP.preset_unwrap_by_operator_props(context)

        return {'FINISHED'}


class ZUV_OT_UnwrapInPlace(bpy.types.Operator, ZuvUnwrapTemplate):

    bl_idname = "uv.zenuv_unwrap_inplace"
    bl_label = 'Unwrap Inplace'
    bl_description = 'Performs a UV unwrapping of selected polygons or a selected island while preserving their dimensions and orienting them to match their world orientation'
    bl_options = {'REGISTER', 'UNDO'}

    influence_mode: ZuvUnwrapTemplate.get_influence_mode(
        ZenPolls.get_operator_defaults("UV_OT_zenuv_unwrap_inplace", "influence_mode", 'ISLAND'))

    unwrap_allowed: ZuvUnwrapTemplate.get_unwrap_allowed(
        ZenPolls.get_operator_defaults("UV_OT_zenuv_unwrap_inplace", "unwrap_allowed", True))

    restore_location: ZuvUnwrapTemplate.get_restore_location(
        ZenPolls.get_operator_defaults("UV_OT_zenuv_unwrap_inplace", "restore_location", True))

    restore_orientation: ZuvUnwrapTemplate.get_restore_orientation(
        ZenPolls.get_operator_defaults("UV_OT_zenuv_unwrap_inplace", "restore_orientation", True))

    restore_size: ZuvUnwrapTemplate.get_restore_size(
        ZenPolls.get_operator_defaults("UV_OT_zenuv_unwrap_inplace", "restore_size", True))

    ignore_pins: ZuvUnwrapTemplate.get_ignore_pins(
        ZenPolls.get_operator_defaults("UV_OT_zenuv_unwrap_inplace", "ignore_pins", False))

    urp_method: ZuvUnwrapTemplate.get_urp_method(
        ZenPolls.get_operator_defaults("UV_OT_zenuv_unwrap_inplace", "urp_method", 'ANGLE_BASED'))

    fill_holes: ZuvUnwrapTemplate.get_fill_holes(
        ZenPolls.get_operator_defaults("UV_OT_zenuv_unwrap_inplace", "fill_holes", True))

    correct_aspect: ZuvUnwrapTemplate.get_correct_aspect(
        ZenPolls.get_operator_defaults("UV_OT_zenuv_unwrap_inplace", "correct_aspect", True))

    use_subsurf_data: ZuvUnwrapTemplate.get_use_subsurf_data(
        ZenPolls.get_operator_defaults("UV_OT_zenuv_unwrap_inplace", "use_subsurf_data", False))

    orient: bpy.props.EnumProperty(
        name='Orientation',
        description='Orientation Mode',
        items=(
            ('KEEP', "Keep", "Preserve initial orientation"),
            ('W_ORIENT', "World Orient", "Aligns UV to match their world orientation"),
            ('SKIP', "Skip", "Leaves the orientation of UV unchanged, without any adjustment after Unwrap"),
        ),
        default=ZenPolls.get_operator_defaults("UV_OT_zenuv_unwrap_inplace", "orient", 'W_ORIENT')
    )

    size: bpy.props.EnumProperty(
        name='Size',
        description='Size Mode',
        items=(
            ('KEEP', "Keep", "Preserve initial size"),
            ("GLOBAL_PRESET", "Global Preset", "Set value described in the Texel Density panel as Global TD Preset"),
            ('SKIP', "Skip", "Leaves the size of UV unchanged, without any adjustment after Unwrap"),
        ),
        default=ZenPolls.get_operator_defaults("UV_OT_zenuv_unwrap_inplace", "size", 'KEEP')
    )

    def draw(self, context: bpy.types.Context):
        layout = self.layout
        layout.use_property_split = True
        row = layout.row()
        row.prop(self, "influence_mode")

        box = layout.box()
        box.use_property_split = True
        box.label(text='Keep:')
        self.draw_uwrp_processor_props(box)

        self.draw_bl_uwrp_props(layout)

    def draw_uwrp_processor_props(self, layout: bpy.types.UILayout):
        # layout.prop(self, 'unwrap_allowed')
        layout.prop(self, 'restore_location', text='Location')
        layout.prop(self, 'orient')
        layout.prop(self, 'size')
        # layout.prop(self, 'restore_orientation')
        layout.prop(self, 'ignore_pins')

    def execute(self, context: bpy.types.Context):
        UP = UnwrapProcessor(context, self.delegate_properties(UnwrapProcessorProps))
        UP.PROPS.unwrap_allowed = True

        if self.size == 'KEEP':
            UP.PROPS.restore_size = True
        elif self.size == 'SKIP':
            UP.PROPS.restore_size = False
        else:
            UP.PROPS.restore_size = False

        if self.orient == 'KEEP':
            UP.PROPS.restore_orientation = True
            UP.PROPS.orient_to_world = False
        elif self.orient == 'W_ORIENT':
            UP.PROPS.restore_orientation = False
            UP.PROPS.orient_to_world = True
        else:
            UP.PROPS.restore_orientation = False
            UP.PROPS.orient_to_world = False

        UP.preset_unwrap_by_operator_props(context)

        if self.size == 'GLOBAL_PRESET':
            p_td = round(context.scene.zen_uv.td_props.td_global_preset, 2)
            bpy.ops.uv.zenuv_set_texel_density(
                td_value=p_td,
                island_pivot='cen',
                set_mode='ISLAND')

        return {'FINISHED'}


system_classes = (
    # ZUV_OT_UnwrapProcessor,
    ZUV_OT_UnwrapInPlace,
)


def register():
    RegisterUtils.register(system_classes)


def unregister():
    RegisterUtils.unregister(system_classes)


if __name__ == "__main__":
    pass
