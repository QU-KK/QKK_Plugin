# SPDX-FileCopyrightText: 2024 Oxicid
# SPDX-License-Identifier: GPL-3.0-or-later

if 'bpy' in locals():
    from .. import reload
    reload.reload(globals())

import bpy
import gpu
import random
import typing
from math import inf
from itertools import chain
from mathutils import Vector
from gpu_extras.batch import batch_for_shader

from .. import utils
from .. import utypes
from ..draw import shaders
from ..preferences import prefs
from ..operators import quick_snap
from ..utypes import BBox, Islands, UMeshes, KDMeshes, TrimKDTree, KDMesh, KDData


class DragMoveObject:
    def __init__(self, pick_isl: utypes.IslandHit):
        self.pick_isl: utypes.IslandHit = pick_isl

        self.coords_pointers: list[Vector] = []  # Flat pointers to coords, for fast transform
        self.original_co: Vector = Vector()  # Use if only move
        self.original_coords: list[Vector] = []
        self.original_bbox: BBox | None = None  # For restore proportions

        # Used for trim system
        self.is_box_transform: bool = False

        # Copy elem coords, used for snap (with switching snap elem mode)
        self.picked_face_vertex_points: list[Vector] = []
        self.picked_face_edge_center_points: list[Vector] = []
        self.picked_face_center_point: Vector = Vector((0.0, 0.0))

        self.calc_coords()

    def calc_coords(self):
        uv = self.pick_isl.island.umesh.uv
        self.coords_pointers = [crn[uv].uv for f in self.pick_isl.island for crn in f.loops]
        self.original_co = self.coords_pointers[0].copy()

        face_inv_div = 1 / len(self.pick_isl.face.loops)
        for crn in self.pick_isl.face.loops:
            crn_uv_co = crn[uv].uv.copy()
            self.picked_face_center_point += crn_uv_co * face_inv_div
            self.picked_face_vertex_points.append(crn_uv_co)
            self.picked_face_edge_center_points.append((crn_uv_co + crn.link_loop_next[uv].uv)/2.0)

    def nearest_transform_to_box(self, tar_bb: BBox, global_delta: Vector, axis: str, pad: float, use_crop: bool):
        if not self.is_box_transform:
            self.store_original_coords_if_not_exist()
            self.original_bbox = utypes.BBox.calc_bbox(self.original_coords)
            self.is_box_transform = True

        src_bb = self.original_bbox.copy()
        src_bb.move(global_delta)

        # Transform
        scale, delta, pivot = utils.get_transform_from_box(src_bb, tar_bb, axis, pad, use_crop)

        diff = pivot - pivot * scale
        diff += delta
        diff += global_delta * scale

        for pointer_co, orig_co in zip(self.coords_pointers, self.original_coords):
            co = orig_co * scale
            co += diff
            pointer_co[:] = co

    def move(self, delta):
        new_delta = (self.original_co + delta) - self.coords_pointers[0]
        for uv_co in self.coords_pointers:
            uv_co += new_delta

    def set_position(self, to: Vector, _from: Vector):
        self.move(to - _from)

    def restore(self):
        if self.is_box_transform:
            self.is_box_transform = False

            assert self.coords_pointers
            assert self.original_coords

            for co_pointer, orig_co in zip(self.coords_pointers, self.original_coords):
                co_pointer[:] = orig_co
        else:
            delta = self.original_co - self.coords_pointers[0]
            for uv_co in self.coords_pointers:
                uv_co += delta

    def store_original_coords_if_not_exist(self):
        if not self.original_coords:
            delta = self.original_co - self.coords_pointers[0]
            self.original_coords = [uv_co + delta for uv_co in self.coords_pointers]


    def find_nearest_pt_to_picked_face(self, first_mouse_pos, snap_points_mode: quick_snap.eSnapPointMode):
        min_co = None
        min_length = float('inf')

        if snap_points_mode & quick_snap.eSnapPointMode.VERTEX:
            for crn_uv_co in self.picked_face_vertex_points:
                new_length = (first_mouse_pos - crn_uv_co).length
                if new_length < min_length:
                    min_co = crn_uv_co
                    min_length = new_length

        if snap_points_mode & quick_snap.eSnapPointMode.EDGE:
            for edge_center in self.picked_face_edge_center_points:
                new_length = (first_mouse_pos - edge_center).length
                if new_length < min_length:
                    min_co = edge_center
                    min_length = new_length

        if snap_points_mode & quick_snap.eSnapPointMode.FACE:
            if (first_mouse_pos - self.picked_face_center_point).length < min_length:
                min_co = self.picked_face_center_point

        # TODO: It may be that snapping to elements will be disabled and Island BBox points will be used for snapping.
        # if min_co is None:
        #     min_co = pt.copy()
        return min_co

class DragFlags:
    use_padding = False
    use_crop = True
    use_persistent_crop_fill = False
    axis: str = 'XY'
    # use_axis_for_crop = True  # TODO: Implement

class UNIV_OT_Drag(bpy.types.Operator, quick_snap.SnapMode, quick_snap.QuickSnap_KDMeshes):
    bl_idname = 'uv.univ_drag'
    bl_label = 'Drag'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.umeshes: UMeshes | None = None
        self.kdmeshes: KDMeshes | None = None

        self.use_trim_cropping = False
        self.trim_bboxes: list[BBox] = []
        self.trim_kdtree: TrimKDTree | None = None
        self.pad = utils.get_pad()

        self.area: bpy.types.Area | None = None
        self.view: bpy.types.View2D | None = None

        self.use_snap: bool = False
        self.radius: float = 0.0
        self.snap_exclude_island_faces = set()  # Need for exclude from snapping
        self.kd_data: KDData | None = None

        self.first_mouse_pos = Vector((0.0, 0.0))
        self.prev_mouse_pos: Vector = Vector((0.0, 0.0))
        self.mouse_position: Vector = Vector((0.0, 0.0))
        self.nearest_pick_co: Vector = Vector((0.0, 0.0))

        # Used only for avoid update
        # TODO: Implement update avoidance for trim system
        self.prev_set_pos_to: Vector = Vector((0.0, 0.0))
        self.prev_set_pos_from: Vector = Vector((0.0, 0.0))

        self.handler: typing.Any = None
        self.shader: gpu.types.GPUShader | None = None
        self.nearest_point: list[Vector] = [Vector((inf, inf))]

        self._cancel: bool = False
        self.pick_isl: utypes.IslandHit | None = None
        self.drag_isl: DragMoveObject | None = None
        self.islands_of_mesh: list[Islands] | None = None

    def invoke(self, context, event):
        self.area = context.area
        if self.area.ui_type != 'UV':
            self.report({'INFO'}, 'Area must be UV')
            return {'CANCELLED'}

        self.view = context.region.view2d
        self.sync = utils.sync()
        self.shader = shaders.POINT_UNIFORM_COLOR_3D
        self.snap_mode_init()
        self.umeshes = UMeshes()

        if not DragFlags.use_padding:
            self.pad = 0.0

        self.calc_radius_and_mouse_position(event)
        self.prev_mouse_pos = self.mouse_position
        self.first_mouse_pos = self.mouse_position.copy()

        # -------- Preprocessing --------
        if not self.preprocessing():
            self.report({'WARNING'}, 'Islands not found')
            return {'CANCELLED'}

        bpy.ops.uv.select_all(action='DESELECT')

        # TODO: Implement optimizing method to draw 3D data
        from .. import draw
        draw.Drawer3D.draw_objects.clear()  # Clean 3d overlays for avoid use update handler

        # Fast deselect after `bpy.ops.uv.select_all` for Blender 5.0
        if utils.USE_GENERIC_UV_SYNC and self.umeshes.sync:
            if self.umeshes.elem_mode in ('VERT', 'EDGE'):
                utils.fast_deselect(self.pick_isl.island.umesh)

        self.pick_isl.island.select = True
        self.drag_isl = DragMoveObject(self.pick_isl)

        # Create empty trim kdtree, which will be calculated when the eSnapPointMode flag does not match
        self.trim_kdtree = TrimKDTree()
        self.use_trim_cropping = DragFlags.use_persistent_crop_fill

        # Immediately calculate the data for snapping if snapping is enabled by default.
        if context.scene.tool_settings.use_snap_uv:
            self.use_snap = True
            self.kd_data = self.find_nearest_target_pt()
            self.nearest_pick_co = self.drag_isl.find_nearest_pt_to_picked_face(self.first_mouse_pos, self.snap_points_mode)

            # Find the closest point for the snap, and the point from which the snap will be made.
            if self.kd_data:
                target_pos = self.kd_data.pt.to_2d()
            else:
                target_pos = self.mouse_position

            self.prev_set_pos_to = target_pos
            self.prev_set_pos_from = self.nearest_pick_co

            if not self.crop_transform_if_access(self.prev_set_pos_to - self.prev_set_pos_from):
                self.drag_isl.set_position(target_pos, self.nearest_pick_co)

            self.pick_isl.island.umesh.update()
            self.area.tag_redraw()
        else:
            if self.use_trim_cropping:
                self.crop_transform_if_access(self.prev_set_pos_to - self.prev_set_pos_from)

        # Add help info
        info = ('UniV: [Ctrl]-Snap. [G]-Grid Snap.  [1-4]-Snap to elem. [X,Y]-Lock or Trim Wrap by Axis.  '
                '[Shift]-Crop by Trim.  [C]-Crop.  [F]-Fill.  [P]-Trim Padding.  [Esc]-Cancel.')
        context.area.header_text_set(info)
        self.register_draw()

        wm = context.window_manager
        wm.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        try:
            return self.modal_ex(context, event)
        except Exception as e:  # noqa
            import traceback
            traceback.print_exc()
            self.report({'ERROR'}, str(e))
            self.exit()
            return {'FINISHED'}

    def modal_ex(self, _context, event):
        if event.type in {'WHEELUPMOUSE', 'WHEELDOWNMOUSE', 'MIDDLEMOUSE'} and not any((event.alt, event.ctrl, event.shift)):
            return {'PASS_THROUGH'}

        elif event.type == 'INBETWEEN_MOUSEMOVE':  # fix over move
            return {'RUNNING_MODAL'}

        elif event.type == 'ESC':
            self._cancel = True
            return self.exit()

        elif event.type == 'LEFTMOUSE' and event.value == 'RELEASE':
            return self.exit()

        elif event.value == 'PRESS':
            if event.type == 'G':
                quick_snap.GlobalSnapFlags.grid_snap ^= 1
            elif event.type in {'ONE', 'TWO', 'THREE', 'FOUR'}:
                self.snap_mode_update(event)
            elif event.type in ('X', 'Y'):
                if event.type == 'X':
                    DragFlags.axis = 'XY' if DragFlags.axis == 'X' else 'X'
                else:
                    DragFlags.axis = 'XY' if DragFlags.axis == 'Y' else 'Y'
            elif event.type == 'P':
                DragFlags.use_padding ^= 1
                self.pad = 0.0
                if DragFlags.use_padding:
                    self.pad = utils.get_pad()

                if self.use_trim_cropping:
                    self.change_prev_set_pos_for_call_update()
            elif event.type in ('C', 'F'):
                # Detect whether a key that is considered "secondary" is pressed
                # The logic is inverted depending on the current use_crop.
                is_secondary_key = (
                        (event.type == 'C' and DragFlags.use_crop) or
                        (event.type == 'F' and not DragFlags.use_crop)
                )

                if is_secondary_key:
                    DragFlags.use_persistent_crop_fill ^= 1
                else:
                    DragFlags.use_persistent_crop_fill = True
                    DragFlags.use_crop ^= True

                if DragFlags.use_persistent_crop_fill != self.use_trim_cropping:
                    self.use_trim_cropping = DragFlags.use_persistent_crop_fill
                    self.change_prev_set_pos_for_call_update()


        prev_mouse_pos = self.mouse_position
        self.calc_radius_and_mouse_position(event)

        self.trim_cropping_status_update(event)
        if self.snap_status_update(event) != self.use_snap:
            if self.use_snap:
                self.nearest_pick_co = self.drag_isl.find_nearest_pt_to_picked_face(
                    self.first_mouse_pos, self.snap_points_mode)

        self.nearest_point = [Vector((inf, inf))]
        if self.use_snap:
            self.kd_data = self.find_nearest_target_pt()
            if self.kd_data:
                target_pos = self.kd_data.pt.to_2d()
                self.nearest_point = [self.kd_data.pt.to_2d()]
            else:
                target_pos = self.mouse_position

            set_pos_to = target_pos
            set_pos_from = self.nearest_pick_co
        else:
            set_pos_to = self.mouse_position
            set_pos_from = self.first_mouse_pos

        if not self.use_trim_cropping:
            self.lock_axis_if_needed(set_pos_from, set_pos_to)

        if self.prev_set_pos_to == set_pos_to and self.prev_set_pos_from == set_pos_from and not self.use_trim_cropping:
            return {'RUNNING_MODAL'}

        if not self.crop_transform_if_access(set_pos_to - set_pos_from):
            # NOTE: Restore should only be performed here, as mouse pos may be outside the trim.
            if self.drag_isl.is_box_transform:
                self.drag_isl.restore()

            if self.use_trim_cropping:
                self.lock_axis_if_needed(set_pos_from, set_pos_to)

            self.drag_isl.set_position(set_pos_to, set_pos_from)

        self.pick_isl.island.umesh.update()

        self.prev_mouse_pos = prev_mouse_pos
        self.prev_set_pos_to = set_pos_to
        self.prev_set_pos_from = set_pos_from

        self.area.tag_redraw()
        return {'RUNNING_MODAL'}

    def crop_transform_if_access(self, delta):
        if self.use_trim_cropping:
            trim_idx = utils.get_nearest_contained_bbox_idx(self.trim_bboxes, self.mouse_position)
            if trim_idx != -1:

                # Set active trim by nearest visible trim.
                filtered_idx = 0
                trim_slot = prefs().get_active_trim_slot()
                for i, trim in enumerate(trim_slot.trims_preset):
                    if trim.visible:
                        if filtered_idx == trim_idx:
                            if trim_slot.active_trim_index != i:
                                trim_slot.active_trim_index = i
                            break
                        filtered_idx += 1

                self.drag_isl.nearest_transform_to_box(self.trim_bboxes[trim_idx], delta, DragFlags.axis, self.pad, DragFlags.use_crop)
                return True
        return False

    def exit(self):
        bpy.context.area.header_text_set(None)
        if self._cancel:
            self.drag_isl.restore()
            self.pick_isl.island.umesh.update()

        for area in utils.get_areas_by_type('IMAGE_EDITOR'):
            if area.ui_type == 'UV':
                area.tag_redraw()

        if not (self.handler is None):
            bpy.types.SpaceImageEditor.draw_handler_remove(self.handler, 'WINDOW')
        return {'FINISHED'}

    def preprocessing(self):
        # Shuffle the order to select random overlapping islands.
        random.shuffle(self.umeshes.umeshes)

        edge_hit = utypes.CrnEdgeHit(self.mouse_position)
        for umesh in reversed(self.umeshes):
            umesh.sequence = utils.calc_visible_uv_faces(umesh)
            if not umesh.sequence:
                self.umeshes.umeshes.remove(umesh)
                continue
            edge_hit.find_nearest_crn_by_visible_faces(umesh, True)

        if not edge_hit:
            return False

        isl, faces = edge_hit.calc_island_with_seam()
        assert len(isl) == len(faces)
        self.snap_exclude_island_faces = faces
        if isl.has_flip_with_noflip():
            self.report({'WARNING'}, "Found flipped faces mixed with non-flipped ones in the island")

            # Set tags for picked island
            isl.umesh.set_face_tag(False)
            noflip, flipped = isl.calc_islands_by_flip_with_mark_seam()

            assert sum(len(i) for i in chain(noflip, flipped)) == len(isl), "Invisible faces affected"

            isl_hit = utypes.IslandHit(self.mouse_position, edge_hit.min_dist * 1.01)
            for sub_isl in chain(noflip, flipped):
                isl_hit.find_nearest_island_with_face(sub_isl)

            self.snap_exclude_island_faces = isl_hit.island.faces
        else:
            isl_hit = utypes.IslandHit(self.mouse_position, edge_hit.min_dist)
            isl_hit.island = isl
            isl_hit.crn = edge_hit.crn
            isl_hit.face = edge_hit.crn.face

        self.pick_isl = isl_hit
        return True

    def register_draw(self):
        self.handler = bpy.types.SpaceImageEditor.draw_handler_add(
            self.univ_quick_snap_draw_callback, (), 'WINDOW', 'POST_VIEW')
        self.area.tag_redraw()

    def univ_quick_snap_draw_callback(self):
        if bpy.context.area.ui_type != 'UV':
            return

        shaders.set_point_size(4)
        shaders.blend_set_alpha()

        self.shader.bind()
        self.nearest_point[0] = self.nearest_point[0].to_3d()

        batch_nearest = batch_for_shader(self.shader, 'POINTS', {"pos": self.nearest_point})
        self.shader.uniform_float("color", (1, 0.2, 0, 1))
        batch_nearest.draw(self.shader)

        self.area.tag_redraw()

        shaders.set_point_size(1)
        shaders.blend_set_none()

    def snap_status_update(self, event):
        prev_status = self.use_snap
        if bpy.context.scene.tool_settings.use_snap_uv:
            if event.ctrl and event.value == 'PRESS':
                self.use_snap = False
            elif event.type in ('LEFT_CTRL', 'RIGHT_CTRL') and event.value == 'RELEASE':
                self.use_snap = True
        else:
            if event.ctrl and event.value == 'PRESS':
                self.use_snap = True
            elif event.type in ('LEFT_CTRL', 'RIGHT_CTRL') and event.value == 'RELEASE':
                self.use_snap = False
        return prev_status

    def trim_cropping_status_update(self, event):
        prev_status = self.use_trim_cropping
        # Sanitize
        if not prefs().use_trims:
            if prev_status:
                self.use_trim_cropping = False
            return prev_status


        if DragFlags.use_persistent_crop_fill:
            if event.shift and event.value == 'PRESS':
                self.use_trim_cropping = False
            elif event.type in ('LEFT_SHIFT', 'RIGHT_SHIFT') and event.value == 'RELEASE':
                self.use_trim_cropping = True
        else:
            if event.shift and event.value == 'PRESS':
                self.use_trim_cropping = True
            elif event.type in ('LEFT_SHIFT', 'RIGHT_SHIFT') and event.value == 'RELEASE':
                self.use_trim_cropping = False

        if not self.trim_bboxes:
            if self.use_trim_cropping:
                self.trim_bboxes = utils.get_trim_bboxes()
                if not self.trim_bboxes:
                    self.use_trim_cropping = False
                    self.report({'INFO'}, 'Visible trim boxes not found')
        if not self.use_trim_cropping:
            self.change_prev_set_pos_for_call_update()
        return prev_status

    def change_prev_set_pos_for_call_update(self):
        # NOTE: Not use inplace add, for avoid potential logic break
        self.prev_set_pos_to = self.prev_set_pos_to + Vector((1, -1))
        self.prev_set_pos_from = self.prev_set_pos_from + Vector((-1, 1))

    def find_nearest_target_pt(self):
        if self.kdmeshes is None:
            self.calc_kdmeshes()
        return super().find_nearest_target_pt()

    @staticmethod
    def lock_axis_if_needed(set_pos_from, set_pos_to):
        if DragFlags.axis == 'X':
            set_pos_to.y = set_pos_from.y
        elif DragFlags.axis == 'Y':
            set_pos_to.x = set_pos_from.x

    def calc_radius_and_mouse_position(self, event):
        mouse_position = Vector(self.view.region_to_view(event.mouse_region_x, event.mouse_region_y))
        dist = prefs().max_pick_distance // 2
        self.radius = utils.get_max_distance_from_px(dist, self.view)
        self.mouse_position = mouse_position

    def calc_kdmeshes(self):
        if type(self.snap_exclude_island_faces) != set:
            self.snap_exclude_island_faces = set(self.snap_exclude_island_faces)
        exclude_faces = self.snap_exclude_island_faces

        kdmeshes = []
        for u in self.umeshes:
            if u == self.pick_isl.island.umesh:
                if len(u.sequence) == len(exclude_faces):
                    u.sequence = []
                    continue
                u.sequence = [f for f in u.sequence if f not in exclude_faces]
            isl = utypes.FaceIsland(u.sequence, u)
            u.sequence = []
            islands = utypes.Islands([isl], u)
            kdmesh = KDMesh(u, islands)
            kdmesh.calc_all_trees()
            kdmeshes.append(kdmesh)
        self.kdmeshes = KDMeshes(kdmeshes)
