# SPDX-FileCopyrightText: 2024 Oxicid
# SPDX-License-Identifier: GPL-3.0-or-later

if 'bpy' in locals():
    from .. import reload
    reload.reload(globals())

import bpy
import math
import bl_math
import numpy as np

from .. import utils
from .. import utypes
from .. import preferences
from ..preferences import prefs

from bpy.props import *
from bpy.types import Operator
from mathutils import Vector, Color, kdtree
from bpy_extras.io_utils import ExportHelper, ImportHelper


import gpu
import typing
from math import inf
from gpu_extras.batch import batch_for_shader

from ..draw import shaders
from ..utypes import BBox


# Trim generator
# sizes = []
# x = 0.5
# for _ in range(8):
#
#     sizes.append(x)
#     x /= 2
#
# sizes.append(x*2)
# sizes.reverse()
#
# starts = []
# acc = 0
# for v in sizes:
#     starts.append(acc)
#     acc += v


MAX_TRIMS_SIZE = 200
MAX_SLOT_SIZE = 64


def get_active_empty_slot_or_create_new():
    slots = prefs().trims_presets_slots

    if not slots:
        prefs().active_trim_slot_index = 0
        return slots.add()

    UNIV_OT_TrimPresetsProcessing.sanitize_slot_index_and_add_if_missed()

    active_idx = prefs().active_trim_slot_index
    active_slot = slots[active_idx]
    if not active_slot.trims_preset:
        return active_slot
    else:
        if len(slots) >= MAX_SLOT_SIZE:
            for i, slot in enumerate(slots):
                if not slot.trims_preset:
                    prefs().active_trim_slot_index = i
                    return slot
            return active_slot  # return active slot for avoid extended logic
        else:
            new_slot = slots.add()
            prefs().active_trim_slot_index = len(slots) - 1
            return new_slot



class UNIV_OT_TrimPresetsProcessing(Operator):
    bl_idname = "scene.univ_trim_presets_processing"
    bl_label = "Presets Processing"
    # noinspection PyTypeHints
    operation_type: EnumProperty(default='ADD',
                                 options={'SKIP_SAVE'},
                                 items=(('ADD', 'Add', ''),
                                        ('REMOVE', 'Remove', ''),
                                        ('REMOVE_ALL', 'Remove All', ''))
                                 )

    def execute(self, _context):
        if self.operation_type == 'ADD':
            self.add(self.report)
        else:
            if not prefs().trims_presets_slots:
                self.report({'WARNING'}, "Not found presets for remove.")
                return {'CANCELLED'}
            else:
                self.sanitize_slot_index_and_add_if_missed()
                slot = prefs().get_active_trim_slot()
                if  self.operation_type == 'REMOVE_ALL':
                    slot.trims_preset.clear()
                    slot.active_trim_index = 0
                    prefs().use_trims = False
                else:
                    self.remove(self.report)

        for a in utils.get_areas_by_type('VIEW_3D'):
            a.tag_redraw()
        for a in utils.get_areas_by_type('IMAGE_EDITOR'):
            a.tag_redraw()

        return {'FINISHED'}

    @classmethod
    def add(cls, report=None, bbox=None, color=None):
        cls.sanitize_slot_index_and_add_if_missed()
        active_slot = prefs().get_active_trim_slot()
        trim_preset = active_slot.trims_preset

        if len(trim_preset) >= MAX_TRIMS_SIZE:
            if report:
                report({'WARNING'}, f"The preset limit of {MAX_TRIMS_SIZE} units has been reached")
            return

        from ..draw import TrimDrawer
        prev_pause = TrimDrawer.pause
        try:
            TrimDrawer.pause = True

            prev_idx = cls.get_sanitized_preset_index()

            if not color:
                hues = [Color(trim.color).h for trim in trim_preset]
                color = Color((0.9,0.0,0.0))
                color.h = utils.largest_gap_midpoint_for_hue(hues)

            my_user = trim_preset.add()
            if bbox:
                my_user.x = bbox.xmin
                my_user.y = bbox.ymin
                my_user.width = bbox.width
                my_user.height = bbox.height
            else:
                my_user.x = 0
                my_user.y = 0
                my_user.width = 1
                my_user.height = 0.25
            my_user.color = color



            # Set unique name
            my_user.name = 'temp'
            all_names = {trim.name for trim in trim_preset}

            if 'Trim' not in all_names:
                my_user.name = 'Trim'
            else:
                for i in range(1, MAX_TRIMS_SIZE):
                    name = f'Trim {i}'
                    if name not in all_names:
                        my_user.name = name
                        break
                else:
                    my_user.name = 'Trim'

            # NOTE: Swap after renaming, otherwise the name will be stored in an invalid object.
            if len(trim_preset) > 1:
                trim_preset.move(len(trim_preset) - 1, prev_idx + 1)  # move(src_index, dst_index)
                active_slot.active_trim_index = prev_idx + 1
            else:
                active_slot.active_trim_index = len(trim_preset) - 1
        finally:
            prefs().use_trims = True
            if not prev_pause:
                TrimDrawer.register()
                TrimDrawer.pause = prev_pause

    @classmethod
    def remove(cls, report):
        slot = prefs().get_active_trim_slot()
        trims_preset = slot.trims_preset
        if not len(trims_preset):
            report({'WARNING'}, 'The preset is empty')
            return
        active_trim_index = cls.get_sanitized_preset_index()
        if len(trims_preset) == active_trim_index - 1:
            trims_preset.active_trim_index = 0
        trims_preset.remove(active_trim_index)
        cls.get_sanitized_preset_index()

        if not trims_preset:
            prefs().use_trims = False

    @staticmethod
    def get_sanitized_preset_index():
        active_slot = prefs().get_active_trim_slot()
        trims_presets = active_slot.trims_preset
        active_trim_index = active_slot.active_trim_index

        # Set the penultimate trim as active after removing the last one.
        if active_trim_index >= len(trims_presets):
            active_trim_index = max(len(trims_presets) - 1, 0)
            active_slot.active_trim_index = active_trim_index

        return active_trim_index

    @staticmethod
    def sanitize_slot_index_and_add_if_missed():
        slots = prefs().trims_presets_slots
        idx = prefs().active_trim_slot_index

        if not slots:
            prefs().active_trim_slot_index = 0
            return

        # Set the penultimate slot as active after removing the last one.
        if idx >= len(slots):
            prefs().active_trim_slot_index = len(slots) - 1


class UNIV_OT_TrimSlotsProcessing(Operator):
    bl_idname = "scene.univ_trim_slots_processing"
    bl_label = "Presets Processing"
    # noinspection PyTypeHints
    operation_type: EnumProperty(default='ADD',
                                 options={'SKIP_SAVE'},
                                 items=(('ADD', 'Add', ''),
                                        # ('DUPLICATE', 'Duplicate', ''),
                                        ('REMOVE', 'Remove', ''),
                                        ('REMOVE_ALL', 'Remove All', ''))
                                 )

    def execute(self, _context):
        if self.operation_type == 'ADD':
            self.add(self.report)
        elif self.operation_type == 'DUPLICATE':
            raise
        else:
            if not prefs().trims_presets_slots:
                self.report({'WARNING'}, "Not found slots for remove.")
                return {'CANCELLED'}


            if self.operation_type == 'REMOVE_ALL':
                prefs().trims_presets_slots.clear()
                prefs().active_trim_index = 0
                prefs().use_trims = False
            else:
                self.remove(self.report)

        for a in utils.get_areas_by_type('VIEW_3D'):
            a.tag_redraw()
        for a in utils.get_areas_by_type('IMAGE_EDITOR'):
            a.tag_redraw()

        return {'FINISHED'}

    @classmethod
    def add(cls, report=None):
        if len(prefs().trims_presets_slots) >= MAX_SLOT_SIZE:
            if report:
                report({'WARNING'}, f"The preset limit of {MAX_SLOT_SIZE} units has been reached")
            return


        from ..draw import TrimDrawer
        prev_pause = TrimDrawer.pause
        try:
            TrimDrawer.pause = True
            UNIV_OT_TrimPresetsProcessing.sanitize_slot_index_and_add_if_missed()
            prev_idx = prefs().active_trim_slot_index
            new_slot = prefs().trims_presets_slots.add()

            # Set unique name
            new_slot.name = 'temp'
            all_names = {slot.name for slot in prefs().trims_presets_slots}
            if 'Trim Preset' not in all_names:
                new_slot.name = 'Trim Preset'
            else:
                for i in range(1, MAX_TRIMS_SIZE):
                    name = f'Trim Preset {i}'
                    if name not in all_names:
                        new_slot.name = name
                        break
                else:
                    new_slot.name = 'Trim Preset'

            # NOTE: Swap after renaming, otherwise the name will be stored in an invalid object.
            slots = prefs().trims_presets_slots
            if len(slots) > 1:
                slots.move(len(slots)-1, prev_idx + 1)
                prefs().active_trim_slot_index = prev_idx + 1
            else:
                prefs().active_trim_slot_index = len(slots) - 1

        finally:
            prefs().use_trims = True
            if not prev_pause:
                TrimDrawer.register()
                TrimDrawer.pause = prev_pause

    @classmethod
    def remove(cls, report):
        if not len(prefs().trims_presets_slots):
            report({'WARNING'}, 'The slot is empty')
            return

        UNIV_OT_TrimPresetsProcessing.sanitize_slot_index_and_add_if_missed()

        slots = prefs().trims_presets_slots
        active_idx = prefs().active_trim_slot_index
        if len(slots) == active_idx - 1:
            prefs().active_trim_slot_index = 0
        slots.remove(active_idx)

        if not slots:
            prefs().active_trim_slot_index = 0
            prefs().use_trims = False
        else:
            UNIV_OT_TrimPresetsProcessing.sanitize_slot_index_and_add_if_missed()


class UNIV_OT_TrimPresetLoad(Operator, ImportHelper):
    bl_idname = "scene.univ_trim_preset_load"
    bl_label = "Load..."
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = "Load trim preset. \n\nNOTE: If the active preset is empty, it overwrites it."

    # noinspection PyTypeHints
    filter_glob: StringProperty(default="*.svg;*.bmp;*.png;*.tga;*.exr;*.hdr;*.tif;", options={'HIDDEN'})

    def execute(self, context):
        import pathlib
        import OpenImageIO as oiio
        from ..draw import TrimDrawer

        if len(prefs().trims_presets_slots) >= MAX_SLOT_SIZE:
            self.report({"WARNING"}, f"The preset limit of {MAX_SLOT_SIZE!r} units has been reached")
            return {'CANCELLED'}

        path = pathlib.Path(self.filepath)
        if path.suffix == '.svg':
            svg_file = utils.SVG.load(self.filepath)
            if svg_file is None:
                self.report({'WARNING'}, f"SVG file is broken: {self.filepath!r}")
                return {'CANCELLED'}

            bboxes_with_colors = svg_file.to_bboxes()

            # Clean created materials
            for mat in svg_file._context['materials'].values():  # noqa # pylint: disable=W0212
                # for mat in materials.value():
                bpy.data.materials.remove(mat)
            # Delete all materials created by svg importer
            for mtl in reversed(bpy.data.materials):
                if mtl.users == 0 and 'SVGMat' in mtl.name:
                    bpy.data.materials.remove(mtl)


            view_box = svg_file.get_view_box(self.filepath)
            remap_scale_x = 1 / view_box.width
            remap_scale_y = 1 / -view_box.height

            for (bb, _) in bboxes_with_colors:
                bb.xmin *= remap_scale_x
                bb.xmax *= remap_scale_x
                bb.ymin *= remap_scale_y
                bb.ymax *= remap_scale_y

                height = abs(bb.height)

                bb.ymin = bb.ymax + 1.0
                bb.ymax = bb.ymin + height
        else:
            inp = oiio.ImageInput.open(filename=self.filepath)
            if not inp:
                self.report({'WARNING'}, f"Image not support {self.filepath!r}")
                return {'CANCELLED'}

            spec = inp.spec()
            x_res = spec.width
            y_res = spec.height


            n_channels = spec.nchannels
            if n_channels == 1:
                self.report({'WARNING'}, 'Not support gray texture')
                return {'CANCELLED'}

            pixels = inp.read_image(0, 0, 0, n_channels, 'uint8')
            pixels = np.array(pixels)


            flat_coords = pixels.reshape(-1, n_channels)
            colors, counts = np.unique(flat_coords, return_counts=True, axis=0)

            bboxes_with_colors = []
            for col, count in zip(colors, counts):
                if n_channels == 4:
                    rgb = col[:3]
                    alpha = col[-1]
                    if alpha < 245:
                        continue

                    if np.all(np.isclose(rgb, 0, atol=15)):
                        continue
                elif n_channels == 3:
                    if np.all(np.isclose(col, 0, atol=25)):
                        continue

                if count <= 8:  # Skip noise
                    continue

                # Find X,Y coordinates of all trim pixels
                trim_y, trim_x = np.where(np.all(pixels==col,axis=2))

                if count < len(trim_x)*0.5:  # Skip small noise bbox
                    continue

                top, bottom = trim_y[0], trim_y[-1]
                left, right = trim_x[0], trim_x[-1]

                xmin = left / x_res
                xmax = (right + 1) / x_res

                ymin = 1.0 - (bottom + 1) / y_res
                ymax = 1.0 - top / y_res

                bb = utypes.BBox(xmin, xmax, ymin, ymax)
                col = (col/255)[:3]
                bboxes_with_colors.append((bb, Color(col)))

            inp.close()
            # NOTE: Sort trims only for images, svg save order.
            bboxes_with_colors.sort(key=lambda bb_and_col: utils.wrap(bb_and_col[1].h - 0.001), reverse=True)



        if not bboxes_with_colors:
            self.report({'WARNING'}, "Failed to get trim preset, possibly the file is broken or has unsupported shape types.")
            return {'FINISHED'}

        if len(bboxes_with_colors) > 200:
            self.report({"WARNING"}, f"The file contains more than 200 figures ({len(bboxes_with_colors)}), the data will not be read completely.")
            bboxes_with_colors = bboxes_with_colors[:200]

        TrimDrawer.unregister()
        prefs().use_trims = False  # Disable for avoid redraw.

        slot = get_active_empty_slot_or_create_new()
        slot.name = path.stem

        for (bb, col) in bboxes_with_colors:
            UNIV_OT_TrimPresetsProcessing.add(self.report, bb, col[:3])

        TrimDrawer.register()

        return {'FINISHED'}


class UNIV_OT_TrimPresetSave(Operator, ExportHelper):
    bl_idname = "scene.univ_trim_preset_save"
    bl_label = "Save..."
    bl_description = "Save active trim preset."

    # noinspection PyTypeHints
    filepath: StringProperty(subtype="FILE_PATH")
    # noinspection PyTypeHints
    filename_ext: EnumProperty(
        name="Format",
        description="Choose the file format to save to",
        items=(('.svg', "SVG", ""),
               None,
               ('.tga', 'TARGA', ""),
               ('.png', 'PNG', ""),
               ('.exr', 'OPEN_EXR', ""),
               ('.tif', 'TIFF', ""),
               ('.bmp', "BMP", ""),
               ('.hdr', 'HDR', ""),
              ),
        default='.svg',
    )

    def invoke(self, context, event):
        pref = prefs()
        if not pref.use_trims:
            self.report({'WARNING'}, "Trim System not enabled")
            return {'CANCELLED'}

        has_trim = False
        if pref.trims_presets_slots:
            UNIV_OT_TrimPresetsProcessing.sanitize_slot_index_and_add_if_missed()
            for trim in pref.get_active_trim_slot().trims_preset:
                if trim.visible:
                    has_trim = True
                    break

        if not has_trim:
            self.report({'WARNING'}, 'Visible trims not found')
            return {'CANCELLED'}

        return super().invoke(context, event)

    def execute(self, context):
        size_x = int(prefs().size_x)
        size_y = int(prefs().size_y)

        if self.filename_ext == '.svg':
            bbox_array_with_hex_color = []
            pref = prefs()
            for trim in pref.get_active_trim_slot().trims_preset:
                if trim.visible:
                    bb = trim.to_bbox()
                    color = Color(trim.color)
                    color = utils.rgb_to_hex(color)
                    bbox_array_with_hex_color.append((bb, color))

            svg = self.svg_from_uv_bboxes(bbox_array_with_hex_color, size_x, size_y)

            file = self.filepath
            with open(file, "w", encoding="utf-8") as f:
                f.write(svg)

            return {'FINISHED'}


        import gpu
        from .. import icons

        tris = []
        colors = []

        for trim in prefs().get_active_trim_slot().trims_preset:
            if trim.visible:
                bb = trim.to_bbox()
                bb.pixel_snap(size_x, size_y)
                tris.extend(bb.draw_data_tris())
                colors.extend([(*trim.color, 1.0)] * 6)

        file = self.filepath
        offscreen = gpu.types.GPUOffScreen(size_x, size_y)
        offscreen.bind()

        try:
            fb = gpu.state.active_framebuffer_get()
            fb.clear(color=(0.0, 0.0, 0.0, 0.0))
            self.draw_image(tris, colors)

            pixel_data = fb.read_color(0, 0, size_x, size_y, 4, 0, 'UBYTE')
            pixel_data.dimensions = size_x * size_y * 4
            icons.IconsCreator.save_pixels(file, pixel_data, size_x, size_y)
        finally:
            offscreen.unbind()
            offscreen.free()

        return {'FINISHED'}


    @staticmethod
    def svg_from_uv_bboxes(bboxes_with_color, width, height):
        parts = [
            f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'width="{width}" height="{height}" '
            f'viewBox="0 0 {width} {height}">'
        ]

        for (bb, hex_color) in bboxes_with_color:
            x = bb.xmin * width
            y = height - (bb.ymin + bb.height) * height
            w = bb.width * width
            h = bb.height * height

            parts.append(
                f'<rect x="{x:.6f}" y="{y:.6f}" '
                f'width="{w:.6f}" height="{h:.6f}" '
                f'fill="{hex_color}"/>'
            )

        parts.append('</svg>')
        return "\n".join(parts)


    @classmethod
    def draw_image(cls, coords, colors):
        import gpu
        from mathutils import Matrix
        from gpu_extras.batch import batch_for_shader

        gpu.state.blend_set('ALPHA')

        with gpu.matrix.push_pop():
            gpu.matrix.load_matrix(cls.get_normalize_uvs_matrix())
            gpu.matrix.load_projection_matrix(Matrix.Identity(4))
            shader = shaders.POLYLINE_FLAT_COLOR_2D
            batch = batch_for_shader(shader, 'TRIS', {"pos": coords, "color": colors})
            batch.draw(shader)

        gpu.state.blend_set('NONE')

    @classmethod
    def get_normalize_uvs_matrix(cls):
        """Matrix maps x and y coordinates from [0, 1] to [-1, 1]"""
        from mathutils import Matrix
        matrix = Matrix.Identity(4)
        matrix.col[3][0] = -1
        matrix.col[3][1] = 1
        matrix[0][0] = 2
        matrix[1][1] = -2
        return matrix




class UNIV_OT_TrimFromMesh(Operator, utils.PaddingHelper):
    bl_idname = "uv.univ_trim_from_mesh"
    bl_label = "Trim From Mesh"
    bl_description = "Trim from mesh or uv"
    bl_options = {'REGISTER', 'UNDO'}
    # noinspection PyTypeHints
    mode: EnumProperty(name='Mode', default='UV', items=utils.ENUM(('UV', 'UV'), 'MESH'))
    # noinspection PyTypeHints
    keep_extend: BoolProperty(name='Keep Extend', default=True, description="No Padding for extended (1.0 length) trims")

    def draw(self, context):
        self.layout.prop(self, 'keep_extend')
        self.draw_padding()
        self.layout.row(align=True).prop(self, 'mode', expand=True)

    def execute(self, context):
        import bmesh
        from ..draw import TrimDrawer
        from ..operators import project

        if len(prefs().trims_presets_slots) >= MAX_SLOT_SIZE:
            self.report({"WARNING"}, f"The preset limit of {MAX_SLOT_SIZE!r} units has been reached")
            return {'CANCELLED'}

        obj = context.active_object
        if not obj:
            self.report({'WARNING'}, 'Active object not found.')
            return {'CANCELLED'}

        if obj.type != 'MESH':
            self.report({'WARNING'}, 'Active object must be a mesh.')
            return {'CANCELLED'}

        if self.mode == 'UV' and not obj.data.uv_layers:
            self.report({'WARNING'}, 'UV layers not found.')
            return {'FINISHED'}

        if not len(obj.data.polygons):
            self.report({'INFO'}, 'Faces not found.')
            return {'FINISHED'}
        elif len(obj.data.polygons) > MAX_TRIMS_SIZE:
            self.report({'INFO'}, f"The limit of {MAX_TRIMS_SIZE} faces has been exceeded.")
            return {'CANCELLED'}


        if bpy.context.mode == 'EDIT_MESH':
            bm = bmesh.from_edit_mesh(obj.data)
            umesh = utypes.UMesh(bm, obj)
        else:
            bm = bmesh.new()
            bm.from_mesh(obj.data)
            umesh = utypes.UMesh(bm, obj, False)
            umesh.ensure()

        if not self.bl_idname.startswith('UV') or not umesh.is_edit_bm:
            umesh.sync = True
            umesh._sync_invalidate = True  # noqa

        if bpy.context.mode == 'EDIT_MESH':
            faces = utils.calc_selected_uv_faces(umesh)
            if not faces:
                faces = utils.calc_visible_uv_faces(umesh)
                if not faces:
                    self.report({'WARNING'}, "Not found visible faces")
                    return {'FINISHED'}
        else:
            faces = umesh.bm.faces

        TrimDrawer.unregister()

        _ = get_active_empty_slot_or_create_new()
        prefs().use_trims = False

        bboxes = []
        if self.mode == 'UV':
            for f in faces:
                isl = utypes.AdvIsland([f], umesh)
                bboxes.append(isl.calc_bbox())
        else:
            vector_nor = Vector()
            for f in faces:
                vector_nor += f.normal * f.calc_area()

            projected_faces = []
            rot_mtx_from_normal = project.UNIV_OT_Normal.calc_rot_mtx_from_normal(vector_nor)
            for f in faces:
                p_face = []
                for v in f.verts:
                    uv_co = (rot_mtx_from_normal @ v.co).to_2d()
                    p_face.append(uv_co)
                projected_faces.append(p_face)

            bb = utypes.BBox.calc_bbox((co for f in projected_faces for co in f))

            aspect = bb.aspect
            if aspect > 16:
                self.report({'WARNING'}, f"Extreme aspect ratio - {aspect!r}, possibly geometry issues")

            scale, delta, pivot = utils.get_transform_from_box(
                bb, utypes.BBox(0.0, 1.0, 0.0, 1.0), axis='XY', pad=0.0, use_crop=False
            )

            diff = pivot - pivot * scale
            diff += delta

            for f in projected_faces:
                for co in f:
                    co *= scale
                    co += diff
                bboxes.append(utypes.BBox.calc_bbox(f))

        pad = int(prefs().padding * self.padding_multiplayer)
        global_pad_x = pad / int(prefs().size_x)
        global_pad_y = pad / int(prefs().size_y)

        for bb in bboxes:
            if self.keep_extend and math.isclose(bb.width, 1.0, abs_tol=1e-5):
                pad_x = 0.0
            else:
                pad_x = utils.attenuate_padding(global_pad_x, bb.width) * 0.5

            if self.keep_extend and math.isclose(bb.height, 1.0, abs_tol=1e-5):
                pad_y = 0.0
            else:
                pad_y = utils.attenuate_padding(global_pad_y, bb.height) * 0.5

            bb.pad((-pad_x, -pad_y))
            UNIV_OT_TrimPresetsProcessing.add(self.report, bb)

        TrimDrawer.register()


        umesh.free()
        return {'FINISHED'}

class TrimEditorHistory:
    def __init__(self):
        self.data = [self.to_compact()]
        self.cur_idx = 0

    def add(self):
        # Delete all 'future' history
        del self.data[self.cur_idx+1:]
        self.data.append(self.to_compact())
        self.cur_idx = len(self.data)-1

    def redo(self):
        if self.cur_idx >= len(self.data)-1:
            return False
        self.cur_idx += 1
        self.from_compact(self.data[self.cur_idx])
        return True

    def undo(self):
        if self.cur_idx == 0:
            return False
        self.cur_idx -= 1
        self.from_compact(self.data[self.cur_idx])
        return True

    @staticmethod
    def to_compact():
        presets = prefs().get_active_trim_slot().trims_preset

        names = np.array([t.name for t in presets])
        colors = np.array([t.color for t in presets], dtype=np.float32)
        visible = np.array([t.visible for t in presets], dtype=bool)
        x = np.array([t.x for t in presets], dtype=np.float32)
        y = np.array([t.y for t in presets], dtype=np.float32)
        width = np.array([t.width for t in presets], dtype=np.float32)
        height = np.array([t.height for t in presets], dtype=np.float32)

        return [names, colors, visible, x, y, width, height]

    @staticmethod
    def from_compact(data):
        presets = prefs().get_active_trim_slot().trims_preset
        presets.clear()

        for name, color, visible, x, y, width, height in zip(*data):
            trim = presets.add()

            trim.name = name
            trim.color = color
            trim.visible = visible
            trim.x = x
            trim.y = y
            trim.width = width
            trim.height = height


class PickedGizmoType:
    NONE = -1
    MIN = 0
    MAX = 1
    LUP = 2
    RBOT = 3

    LEFT = 4
    RIGHT = 5
    TOP = 6
    BOTTOM = 7

    CENTER = 8


class TrimMoveObject:
    def __init__(self,
                 orig_bb: BBox,
                 trim: preferences.UNIV_TrimPreset | None,
                 first_pick_co: Vector,
                 picked_gizmo_type = PickedGizmoType.NONE,
                 is_drag: bool = False,
                 is_draw: bool = False):
        self.orig_bb: BBox = orig_bb
        self.trim = trim
        self.first_pick_co = first_pick_co.copy().freeze()
        self.is_drag = is_drag
        self.is_draw = is_draw
        self.picked_elem_type = picked_gizmo_type

    @classmethod
    def find_nearest_trim(cls, pos: Vector, gizmo_size: float, aspect: float, alt=False, soft_start_pos=Vector((0.0,0.0))):
        picked_trim = None
        min_dist = inf
        picked_gizmo_type = PickedGizmoType.MAX  # Frequency used corner

        if alt:
            trims = [t for t in prefs().get_active_trim_slot().trims_preset if t.visible]
            assert len(trims)

            bboxes = [trim.to_bbox() for trim in trims]
            aspect = 1.0 / aspect

            min_idx = utils.argmin(bboxes, lambda bb_: min(bb_.distance(pos, aspect), bb_.distance_to_center(pos, aspect)))
            return cls(bboxes[min_idx], trims[min_idx], pos, min_idx, is_drag=True)


        aspect_x = min(1.0, 1.0 / aspect)
        aspect_y = min(1.0, aspect)

        size_x = gizmo_size * aspect_x * 2.0
        size_y = gizmo_size * aspect_y * 2.0


        for trim in prefs().get_active_trim_slot().trims_preset:
            if not trim.visible:
                continue

            bb = trim.to_bbox()

            # Draw center cursor
            cross_size_x = size_x
            cross_size_y = size_y

            min_size = min(trim.width, trim.height)
            if min_size < gizmo_size:
                cross_size_x = min_size * aspect_x
                cross_size_y = min_size * aspect_y

            gizmos = UNIV_OT_TrimEditor.calc_gizmo(bb, aspect_x, aspect_y, cross_size_x, cross_size_y, gizmo_size)
            for gizmo_typ, giz_bb in enumerate(gizmos):
                new_dist = (giz_bb.center - pos).length
                if new_dist < min_dist:
                    if pos in giz_bb:
                        min_dist = new_dist
                        picked_trim = trim
                        picked_gizmo_type = gizmo_typ


        if picked_trim is None:
            # Trim Add (Draw)
            trim_presets = prefs().get_active_trim_slot().trims_preset
            if len(trim_presets) >= 200:
                return None

            bb = BBox.calc_bbox([soft_start_pos])
            UNIV_OT_TrimPresetsProcessing.add(bbox=bb)

            created_trim = trim_presets[-1]
            return cls(bb, created_trim, soft_start_pos, picked_gizmo_type, is_draw=True)
        else:
            # Gizmo Move
            return cls(picked_trim.to_bbox(), picked_trim, pos, picked_gizmo_type)

    def move(self, delta, alt):
        bb = self.orig_bb.copy()

        if self.is_drag or self.picked_elem_type == PickedGizmoType.CENTER:
            bb.move(delta)
            delta = utils.wrap_box(bb)
            bb.move(delta)
            self.trim.from_bbox(bb)
            return

        match self.picked_elem_type:
            case PickedGizmoType.MIN:
                bb.min += delta
            case PickedGizmoType.MAX:
                bb.max += delta
            case PickedGizmoType.LUP:
                x, y = bb.left_upper + delta
                bb.xmin = x
                bb.ymax = y
            case PickedGizmoType.RBOT:
                x, y = bb.right_bottom + delta
                bb.xmax = x
                bb.ymin = y
            case PickedGizmoType.LEFT:
                bb.xmin += delta.x
            case PickedGizmoType.RIGHT:
                bb.xmax += delta.x
            case PickedGizmoType.TOP:
                bb.ymax += delta.y
            case PickedGizmoType.BOTTOM:
                bb.ymin += delta.y
            case _:
                print(f"UniV: Trim Editor: Unsupported Gizmo Type {self.picked_elem_type}")
                raise NotImplementedError


        if alt:
            delta = self.orig_bb.center
            match self.picked_elem_type:
                case PickedGizmoType.MIN | PickedGizmoType.LEFT:
                    pt = bb.min
                case PickedGizmoType.MAX | PickedGizmoType.RIGHT:
                    pt = bb.max
                case PickedGizmoType.LUP | PickedGizmoType.TOP:
                    pt = bb.left_upper
                case PickedGizmoType.RBOT | PickedGizmoType.BOTTOM:
                    pt = bb.right_bottom
                case _:
                    pt = bb.min  # noqa # PyCharm Moment...

            other_pt = (pt - delta) * Vector((-1.0, -1.0)) + delta
            bb = BBox.calc_bbox((pt, other_pt))
        bb.sanitize()

        isect_bb = bb.isect(BBox(0.0, 1.0, 0.0, 1.0))
        if isect_bb:
            self.trim.from_bbox(isect_bb)
        else:
            self.trim.from_bbox(bb)

    def set_position(self, to: Vector, _from: Vector, alt):
        x, y = to
        x = bl_math.clamp(x)
        y = bl_math.clamp(y)
        self.move(Vector((x, y)) - _from, alt)

    def get_nearest_pt_to_picked_trim(self):
        if self.is_draw:
            return self.first_pick_co.copy()

        if self.is_drag:
            min_co = Vector((0.0, 0.0))
            min_dist = inf

            bb = self.orig_bb
            all_points = bb.draw_data_verts()
            all_points.append(bb.center)
            all_points.extend((bb.left, bb.right, bb.upper, bb.bottom))

            for co in all_points:
                new_dist = (self.first_pick_co - co).length
                if new_dist < min_dist:
                    min_co = co
                    min_dist = new_dist

            return min_co

        match self.picked_elem_type:
            case PickedGizmoType.MIN:
                return self.orig_bb.min.copy()
            case PickedGizmoType.MAX:
                return self.orig_bb.max.copy()
            case PickedGizmoType.LUP:
                return self.orig_bb.left_upper
            case PickedGizmoType.RBOT:
                return self.orig_bb.right_bottom

            case PickedGizmoType.LEFT:
                y = self.first_pick_co.y
                return Vector((self.orig_bb.xmin, y))
            case PickedGizmoType.RIGHT:
                y = self.first_pick_co.y
                return Vector((self.orig_bb.xmax, y))
            case PickedGizmoType.TOP:
                x = self.first_pick_co.x
                return Vector((x, self.orig_bb.ymax))
            case PickedGizmoType.BOTTOM:
                x = self.first_pick_co.x
                return Vector((x, self.orig_bb.ymin))

            case PickedGizmoType.CENTER:
                return self.orig_bb.center
            case _:
                return self.first_pick_co.copy()

    def __bool__(self):
        return bool(self.trim)


class TrimFlags:
    use_knife = False
    use_knife_x_axis = True
    use_cut_through = True
    use_padding = True
    gizmo_pixel_size: int = 7


class UNIV_OT_TrimEditor(bpy.types.Operator):
    bl_idname = 'uv.univ_trim_editor'
    bl_label = 'Trim Editor'
    bl_options = {'REGISTER', 'UNDO'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.trim_kdtree: kdtree.KDTree | None = None
        self.soft_snap_x_coords = []
        self.soft_snap_y_coords = []

        self.gizmos: list[list[BBox]] = []
        self.pad_x = utils.get_pad()
        self.pad_y = utils.get_pad()

        self.area: bpy.types.Area | None = None
        self.view: bpy.types.View2D | None = None

        self.use_snap: bool = False
        self.use_soft_snap: bool = True
        self.soft_snap_lines: list[float | None] = [None, None]
        self.radius: float = 0.0
        self.soft_radius_mul: float = 0.2

        self.aspect = utils.get_aspect_ratio()

        self.gizmo_size: float = 0.001
        self.gizmo_size_draw_multiplayer: float = 0.65
        self.gizmo_pixel_size: int = TrimFlags.gizmo_pixel_size

        self.first_mouse_pos = Vector((0.0, 0.0))
        self.prev_mouse_pos: Vector = Vector((0.0, 0.0))
        self.mouse_position: Vector = Vector((0.0, 0.0))
        self.nearest_pick_co: Vector = Vector((0.0, 0.0))

        # Used only for avoid update
        self.prev_set_pos_to: Vector = Vector((0.0, 0.0))
        self.prev_set_pos_from: Vector = Vector((0.0, 0.0))

        self.handler: typing.Any = None
        self.batch_lines: gpu.types.GPUBatch | None = None
        self.batch_tris: gpu.types.GPUBatch | None = None
        self.tris_shader: gpu.types.GPUShader = shaders.SMOOTH_COLOR_2D
        self.line_shader: gpu.types.GPUShader = shaders.POLYLINE_FLAT_COLOR_2D

        self.is_edit = False
        self.drag_trim: TrimMoveObject | None = None
        self.icon_idx = -1

        self.history: TrimEditorHistory | None = None

    def invoke(self, context, event):
        self.area = context.area
        if self.area.ui_type != 'UV':
            self.report({'WARNING'}, 'Area must be UV')
            return {'CANCELLED'}

        if context.region.type != 'WINDOW':
            self.report({'WARNING'}, 'Incorrect operator context. Need `INVOKE_REGION_WIN`.')
            return {'CANCELLED'}

        self.view = context.region.view2d

        self.update_padding()

        if self.aspect < 1:
            self.gizmo_pixel_size *= round(1 / self.aspect)

        self.use_snap = context.scene.tool_settings.use_snap_uv

        self.calc_radius_and_mouse_position(event)
        self.prev_mouse_pos = self.mouse_position
        self.first_mouse_pos = self.mouse_position.copy()
        self.gizmo_size = utils.get_max_distance_from_px(self.gizmo_pixel_size, self.view)

        self.history = TrimEditorHistory()

        # Create empty trim kdtree, which will be calculated when the eSnapPointMode flag does not match
        from ..draw import TrimDrawer
        TrimDrawer.unregister()
        TrimDrawer.pause = True
        self.calc_draw_data()

        # Add help info
        info = ('UniV: [Ctrl]-Snap.  [Shift]-Soft Snap.  [Alt]-Proportional.  [P]-Padding.  [+, -]-Gizmo Scale.  '
                '[K]-Knife.  [F]-Flip Cut Axis.  [C]-Cut Through.  [H]-Hide.  [Alt+H]-Unhide All.  [X, Del]-Remove.  '
                '[Ctrl+Z]-Undo.  [Ctrl+Shift+Z]-Redo.  [Esc, Space, Enter]-Exit.')
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


    def modal_ex(self, context, event):
        prev_mouse_pos = self.mouse_position
        self.calc_radius_and_mouse_position(event)

        if not self.is_edit:
            curr_gizmo_size = utils.get_max_distance_from_px(self.gizmo_pixel_size, self.view)
            if self.gizmo_size != curr_gizmo_size:
                self.calc_draw_data()
                self.area.tag_redraw()
                self.update_knife_line()
            self.gizmo_size = curr_gizmo_size

        if event.type == 'MOUSEMOVE':
            if self.drag_trim:
                self.area.tag_redraw()
            elif TrimFlags.use_knife:
                self.update_knife_line()
                self.area.tag_redraw()

        elif event.type in ('INBETWEEN_MOUSEMOVE', 'TIMER_REPORT'):
            return {'RUNNING_MODAL'}

        elif event.type == 'LEFTMOUSE':
            self.area.tag_redraw()
            if event.value == 'PRESS':
                if TrimFlags.use_knife:
                    self.update_knife_line()
                    x, y = self.soft_snap_lines
                    mx, my = self.mouse_position

                    if TrimFlags.use_knife_x_axis:
                        pos = Vector((mx, y))
                    else:
                        pos = Vector((x, my))

                    min_size = 0.002

                    min_dist = float('inf')
                    min_dist_trim = None
                    all_trims = []
                    for trim in prefs().get_active_trim_slot().trims_preset:
                        if not trim.visible:
                            continue
                        bb = trim.to_bbox()

                        if TrimFlags.use_knife_x_axis:
                            offset_to_avoid_small_trim = min_size*0.5 + (self.pad_y * 0.5)
                            bb.ymin += offset_to_avoid_small_trim
                            bb.ymax -= offset_to_avoid_small_trim
                        else:
                            offset_to_avoid_small_trim = min_size*0.5 + (self.pad_x * 0.5)
                            bb.xmin += offset_to_avoid_small_trim
                            bb.xmax -= offset_to_avoid_small_trim

                        if TrimFlags.use_cut_through:
                            if TrimFlags.use_knife_x_axis:
                                if bb.isect_y(y):
                                    all_trims.append(trim)
                            else:
                                if bb.isect_x(x):
                                    all_trims.append(trim)
                        else:
                            if pos not in bb:
                                continue
                            bb = trim.to_bbox()
                            new_dist = min(bb.distance(pos, 1 / self.aspect),
                                           bb.distance_to_center(pos, 1 / self.aspect))
                            if new_dist < min_dist:
                                min_dist = new_dist
                                min_dist_trim = trim

                    if min_dist_trim:
                        all_trims.append(min_dist_trim)

                    # NOTE: Memory can be reallocated, so first modify the existing trims, and then create new ones.
                    new_trims = []
                    for trim in all_trims:
                        bb = trim.to_bbox()
                        if TrimFlags.use_knife_x_axis:
                            new_trims.append(BBox(bb.xmin, bb.xmax, y + (self.pad_y * 0.5), bb.ymax))

                            bb.ymax = y - (self.pad_y * 0.5)
                            trim.height = bb.height
                        else:
                            new_trims.append(BBox(x + (self.pad_x * 0.5), bb.xmax,bb.ymin, bb.ymax))

                            bb.xmax = x - (self.pad_x * 0.5)
                            trim.width = bb.width

                    for new_trim in new_trims:
                        UNIV_OT_TrimPresetsProcessing.add(report=self.report, bbox=new_trim)

                    if all_trims or new_trims:
                        self.history.add()

                    self.update_dynamic_data()
                    return {'RUNNING_MODAL'}

                if event.alt and not prefs().get_active_trim_slot().trims_preset:
                    self.is_edit = False
                    self.drag_trim = None
                    self.report({'WARNING'}, 'Not found trim for drag')
                    return {'RUNNING_MODAL'}

                self.is_edit = True
                if event.shift:
                    soft_start_pos = self.mouse_position.copy()
                else:
                    soft_start_pos = self.get_first_soft_snap_pos()

                self.soft_snap_x_coords = []

                self.drag_trim = TrimMoveObject.find_nearest_trim(
                    self.mouse_position, self.gizmo_size, self.aspect, event.alt, soft_start_pos)

                if not self.drag_trim:
                    self.is_edit = False
                    self.drag_trim = None
                    self.report({'WARNING'}, 'The preset limit of 200 units has been reached')
                    return {'RUNNING_MODAL'}
                self.first_mouse_pos = self.mouse_position.copy()
            else:
                if TrimFlags.use_knife:
                    return {'RUNNING_MODAL'}

                self.is_edit = False
                is_remove = False
                if self.drag_trim:
                    # Remove small trims
                    if self.drag_trim.trim.width <= 0.0025 and self.drag_trim.trim.height <= 0.0025:
                        for idx, trim in enumerate(prefs().get_active_trim_slot().trims_preset):
                            if self.drag_trim.trim == trim:
                                is_remove = True
                                prefs().get_active_trim_slot().trims_preset.remove(idx)
                                break
                if not is_remove:
                    self.history.add()

                self.drag_trim = None
                self.trim_kdtree = None
                self.update_dynamic_data()

        elif event.type in ('LEFT_ALT', 'RIGHT_ALT'):  # Proportional move
            self.change_prev_set_pos_for_call_update()
        elif event.value == 'PRESS':
            if event.type == 'K' and not self.is_edit:
                TrimFlags.use_knife ^= 1
                self.update_dynamic_data()

            elif event.type == 'F' and TrimFlags.use_knife:
                TrimFlags.use_knife_x_axis ^= 1
                self.update_knife_line()
            elif event.type == 'C' and TrimFlags.use_knife:
                TrimFlags.use_cut_through ^= 1
                self.update_knife_line()

            elif event.type == 'P':
                TrimFlags.use_padding ^= 1
                self.update_padding()

                self.change_prev_set_pos_for_call_update()

                self.trim_kdtree = None
                self.update_dynamic_data()

            elif event.type == 'Z' and not self.is_edit and not event.alt and event.ctrl:
                if not event.shift:
                    if self.history.undo():
                        self.update_dynamic_data()
                        return {'RUNNING_MODAL'}
                else:
                    if self.history.redo():
                        self.update_dynamic_data()
                        return {'RUNNING_MODAL'}

            elif event.type == 'H' and not self.is_edit:
                has_hidden = False
                if event.alt:
                    for t in prefs().get_active_trim_slot().trims_preset:
                        if not t.visible:
                            t.visible = True
                            has_hidden = True
                    if has_hidden:
                        self.history.add()
                else:
                    min_dist = float('inf')
                    min_dist_trim = None

                    for t in prefs().get_active_trim_slot().trims_preset:
                        if t.visible:
                            bb = t.to_bbox()
                            new_dist = bb.distance(self.mouse_position, 1/self.aspect, True)
                            if new_dist <= self.radius and new_dist < min_dist:
                                min_dist = new_dist
                                min_dist_trim = t
                    if min_dist_trim:
                        min_dist_trim.visible = False
                        self.history.add()

                self.update_dynamic_data()
                return {'RUNNING_MODAL'}

            elif event.type in ('X', 'DEL') and not self.is_edit:
                min_dist = float('inf')
                min_dist_trim = None

                for t in prefs().get_active_trim_slot().trims_preset:
                    if t.visible:
                        bb = t.to_bbox()
                        new_dist = bb.distance(self.mouse_position, 1/self.aspect, True)
                        if new_dist <= self.radius and new_dist < min_dist:
                            min_dist = new_dist
                            min_dist_trim = t

                if min_dist_trim:
                    prefs().get_active_trim_slot().trims_preset.remove(min_dist_trim.get_index())
                    self.history.add()

                    self.update_dynamic_data()
                return {'RUNNING_MODAL'}

            elif event.type in ('NUMPAD_MINUS', 'MINUS'):  # Resize Gizmo
                TrimFlags.gizmo_pixel_size -= 1
                TrimFlags.gizmo_pixel_size = utils.clamp(TrimFlags.gizmo_pixel_size, 4, 16)
                self.gizmo_pixel_size = TrimFlags.gizmo_pixel_size
                if self.aspect < 1:
                    self.gizmo_pixel_size *= round(1 / self.aspect)
                return {'RUNNING_MODAL'}
            elif event.type == 'NUMPAD_PLUS' or (event.type == 'EQUAL' and event.shift):
                TrimFlags.gizmo_pixel_size += 1
                TrimFlags.gizmo_pixel_size = utils.clamp(TrimFlags.gizmo_pixel_size, 4, 16)
                self.gizmo_pixel_size = TrimFlags.gizmo_pixel_size
                if self.aspect < 1:
                    self.gizmo_pixel_size *= round(1 / self.aspect)
                return {'RUNNING_MODAL'}

            elif event.type in {'WHEELUPMOUSE', 'WHEELDOWNMOUSE', 'MIDDLEMOUSE', 'RIGHTMOUSE'} and not any(
                    (event.alt, event.shift)):
                if event.ctrl and event.type in ('WHEELUPMOUSE', 'WHEELDOWNMOUSE'):
                    return {'RUNNING_MODAL'}
                self.update_dynamic_data()
                return {'PASS_THROUGH'}

            elif event.type in {'ESC', 'SPACE', 'RET', 'NUMPAD_ENTER'}:
                return self.exit()

        self.snap_status_update(event)

        #  --------- Event End ---------

        if TrimFlags.use_knife:
            context.window.cursor_modal_set('KNIFE')
            return {'RUNNING_MODAL'}

        # PICK_AREA - for draw
        if not self.is_edit:
            context.window.cursor_modal_set('PAINT_CROSS')
            return {'RUNNING_MODAL'}

        if self.drag_trim:
            if self.drag_trim.is_draw:
                context.window.cursor_modal_set('PAINT_CROSS')
            elif self.drag_trim.picked_elem_type in (PickedGizmoType.LEFT, PickedGizmoType.RIGHT):
                context.window.cursor_modal_set('MOVE_X')
            elif self.drag_trim.picked_elem_type in (PickedGizmoType.TOP, PickedGizmoType.BOTTOM):
                context.window.cursor_modal_set('MOVE_Y')
            else:
                context.window.cursor_modal_set('SCROLL_XY')



        set_pos_to, set_pos_from = self.proceed_find_nearest_target_pt()

        if self.prev_set_pos_to == set_pos_to and self.prev_set_pos_from == set_pos_from:
            return {'RUNNING_MODAL'}

        self.drag_trim.set_position(set_pos_to, set_pos_from, event.alt)

        self.prev_mouse_pos = prev_mouse_pos
        self.prev_set_pos_to = set_pos_to
        self.prev_set_pos_from = set_pos_from

        self.calc_draw_data()
        self.area.tag_redraw()
        return {'RUNNING_MODAL'}

    def update_dynamic_data(self):
        self.soft_snap_x_coords = []
        self.soft_snap_y_coords = []
        self.soft_snap_lines: list[float | None] = [None, None]
        self.update_knife_line()

        self.calc_draw_data()
        self.area.tag_redraw()

    def update_padding(self):
        if not TrimFlags.use_padding:
            self.pad_x = 0.0
            self.pad_y = 0.0
        else:
            pref = prefs()
            self.pad_x = pref.padding / int(pref.size_x)
            self.pad_y = pref.padding / int(pref.size_y)

    def exit(self):
        bpy.context.area.header_text_set(None)
        from ..draw import TrimDrawer
        TrimDrawer.pause = False
        TrimDrawer.register()
        bpy.context.window.cursor_modal_restore()

        for area in utils.get_areas_by_type('IMAGE_EDITOR'):
            if area.ui_type == 'UV':
                area.tag_redraw()

        if not (self.handler is None):
            bpy.types.SpaceImageEditor.draw_handler_remove(self.handler, 'WINDOW')
        bpy.context.preferences.is_dirty = True
        return {'FINISHED'}

    def snap_status_update(self, event):
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


        if event.shift and event.value == 'PRESS':
            self.use_soft_snap = False
        elif event.type in ('LEFT_SHIFT', 'RIGHT_SHIFT') and event.value == 'RELEASE':
            self.use_soft_snap = True

    def change_prev_set_pos_for_call_update(self):
        # NOTE: Not use inplace add, for avoid potential logic break
        self.prev_set_pos_to = self.prev_set_pos_to + Vector((1, -1))
        self.prev_set_pos_from = self.prev_set_pos_from + Vector((-1, 1))

    def proceed_find_nearest_target_pt(self):
        if self.use_snap:
            if not self.trim_kdtree:
                active_trim = None
                if self.drag_trim:
                    active_trim = self.drag_trim.trim


                tile_bounds = np.linspace(0.0, 1.0, 3)
                coords = [Vector((x, y)) for x in tile_bounds for y in tile_bounds]

                pad_left = Vector((-self.pad_x, 0.0))
                pad_right = Vector((self.pad_x, 0.0))
                pad_top = Vector((0.0, self.pad_y))
                pad_bottom = Vector((0.0, -self.pad_y))
                pad_lt = pad_left + pad_top
                pad_rt = pad_right + pad_top
                pad_lb = pad_left + pad_bottom
                pad_rb = pad_right + pad_bottom

                for t in prefs().get_active_trim_slot().trims_preset:
                    if not t.visible:
                        continue

                    if t == active_trim:
                        bb = self.drag_trim.orig_bb
                    else:
                        bb = t.to_bbox()

                    bb_min = bb.min
                    bb_max = bb.max
                    bb_lt = bb.left_upper
                    bb_rb = bb.right_bottom
                    coords.extend((bb_min, bb_max, bb_lt, bb_rb))
                    coords.extend((bb.left, bb.right, bb.upper, bb.bottom, bb.center))

                    if TrimFlags.use_padding:
                        coords.append(bb_min+pad_left)
                        coords.append(bb_min+pad_bottom)
                        coords.append(bb_min+pad_lb)

                        coords.append(bb_max+pad_right)
                        coords.append(bb_max+pad_top)
                        coords.append(bb_max+pad_rt)

                        coords.append(bb_lt+pad_top)
                        coords.append(bb_lt+pad_left)
                        coords.append(bb_lt+pad_lt)

                        coords.append(bb_rb+pad_right)
                        coords.append(bb_rb+pad_bottom)
                        coords.append(bb_rb+pad_rb)

                kd_tree = kdtree.KDTree(len(coords))

                insert = kd_tree.insert
                for i, co in enumerate(coords):
                    insert(co.to_3d(), i)
                kd_tree.balance()
                self.trim_kdtree = kd_tree

            set_pos_to, _, dist = self.trim_kdtree.find(self.mouse_position.to_3d())
            if dist <= self.radius:
                set_pos_to = set_pos_to.to_2d()
            else:
                set_pos_to = self.mouse_position.copy()
            set_pos_from = self.drag_trim.get_nearest_pt_to_picked_trim()

        elif self.use_soft_snap:

            # TODO: Add soft_radius_x and soft_radius_y
            self.soft_snap_lines = [None, None]
            find_x, find_y = self.find_nearest_soft_snap_pos(self.mouse_position)
            soft_r = self.radius * self.soft_radius_mul

            to_x, to_y = self.mouse_position
            from_x, from_y = self.drag_trim.first_pick_co

            if abs(find_x - to_x) <= soft_r:
                to_x = find_x
                self.soft_snap_lines[0] = to_x
                from_x, _ = self.drag_trim.get_nearest_pt_to_picked_trim()

            if abs(find_y - to_y) <= soft_r:
                to_y = find_y
                self.soft_snap_lines[1] = to_y
                _, from_y = self.drag_trim.get_nearest_pt_to_picked_trim()
            set_pos_to = Vector((to_x, to_y))
            set_pos_from =  Vector((from_x, from_y))

        else:
            set_pos_to = self.mouse_position.copy()
            set_pos_from = self.drag_trim.first_pick_co.copy()
        return set_pos_to, set_pos_from

    def calc_radius_and_mouse_position(self, event):
        mouse_position = Vector(self.view.region_to_view(event.mouse_region_x, event.mouse_region_y))
        dist = prefs().max_pick_distance // 2
        self.radius = utils.get_max_distance_from_px(dist, self.view)
        self.mouse_position = mouse_position

    def find_nearest_soft_snap_pos(self, pos):
        active_trim = None
        if self.drag_trim:
            active_trim = self.drag_trim.trim

        if not len(self.soft_snap_x_coords):
            coords_quadro = []
            for t in prefs().get_active_trim_slot().trims_preset:
                if not t.visible:
                    continue

                if t == active_trim:
                    bb = self.drag_trim.orig_bb
                else:
                    bb = t.to_bbox()

                coords_quadro.extend((bb.xmin, bb.xmax, bb.ymax, bb.ymin))

            coords_quadro = np.array(coords_quadro, dtype=np.float32)

            coords_x_left   = coords_quadro[0::4]
            coords_x_right  = coords_quadro[1::4]
            coords_y_upper  = coords_quadro[2::4]
            coords_y_bottom = coords_quadro[3::4]

            if TrimFlags.use_padding:
                coords_x_left_pad   = coords_x_left - np.float32(self.pad_x)
                coords_x_right_pad  = coords_x_right + np.float32(self.pad_x)
                coords_y_upper_pad  = coords_y_upper + np.float32(self.pad_y)
                coords_y_bottom_pad = coords_y_bottom - np.float32(self.pad_y)
            else:
                coords_x_left_pad = coords_x_right_pad = coords_y_upper_pad = coords_y_bottom_pad = []

            center_x = coords_x_left + coords_x_right
            center_x *= np.float32(0.5)

            center_y = coords_y_bottom + coords_y_upper
            center_y *= np.float32(0.5)

            arr_x = [[0.0], coords_x_left_pad, coords_x_left, center_x, coords_x_right, coords_x_right_pad, [0.5, 1.0]]
            coords_x = np.concatenate(arr_x, dtype=np.float32)
            np.clip(coords_x, a_min=0.0, a_max=1.0, out=coords_x)
            self.soft_snap_x_coords = np.unique(np.sort(coords_x))

            arr_y = [[0.0], coords_y_bottom_pad, coords_y_bottom, center_y, coords_y_upper, coords_y_upper_pad, [0.5, 1.0]]
            coords_y = np.concatenate(arr_y, dtype=np.float32)
            np.clip(coords_y, a_min=0.0, a_max=1.0, out=coords_y)
            self.soft_snap_y_coords = np.unique(np.sort(coords_y))

        find_x = utils.find_nearest(self.soft_snap_x_coords, pos.x)
        find_y = utils.find_nearest(self.soft_snap_y_coords, pos.y)

        return find_x, find_y

    @staticmethod
    def calc_gizmo(bb: BBox, aspect_x, aspect_y, cross_off_x, cross_off_y, gizmo_size):
        size_x = gizmo_size * aspect_x
        size_y = gizmo_size * aspect_y

        crn = bb.min + Vector((size_x, size_y))
        gizmo_min = BBox(crn.x-size_x, crn.x+size_x, crn.y-size_y, crn.y+size_y)

        crn = bb.max - Vector((size_x, size_y))
        gizmo_max = BBox(crn.x-size_x, crn.x+size_x, crn.y-size_y, crn.y+size_y)

        crn = bb.left_upper + Vector((size_x, -size_y))
        gizmo_lu = BBox(crn.x-size_x, crn.x+size_x, crn.y-size_y, crn.y+size_y)

        crn = bb.right_bottom + Vector((-size_x, size_y))
        gizmo_rb = BBox(crn.x-size_x, crn.x+size_x, crn.y-size_y, crn.y+size_y)

        # Sides
        width_off = (bb.half_width - size_x)
        if width_off < size_x * 3.5:
            width_off = size_x
        else:
            width_off = size_x * 3.0
        width_off *= 0.8

        height_off = (bb.half_height - size_y)
        if height_off < size_y * 3.5:
            height_off = size_y
        else:
            height_off = size_y * 3.0
        height_off *= 0.8

        side = bb.left
        side.x += size_x
        gizmo_left = BBox(side.x-size_x, side.x+size_x*0.25, side.y-height_off, side.y+height_off)

        side = bb.right
        side.x -= size_x
        gizmo_right = BBox(side.x-size_x*0.25, side.x+size_x, side.y-height_off, side.y+height_off)

        side = bb.upper
        side.y -= size_y
        gizmo_upper = BBox(side.x-width_off, side.x+width_off, side.y-size_y*0.25, side.y+size_y)

        side = bb.bottom
        side.y += size_y
        gizmo_bottom = BBox(side.x-width_off, side.x+width_off, side.y-size_y, side.y+size_y*0.25)

        center = bb.center
        gizmo_center = BBox(center.x - cross_off_x, center.x + cross_off_x, center.y - cross_off_y, center.y + cross_off_y)

        return [gizmo_min, gizmo_max, gizmo_lu, gizmo_rb, gizmo_left, gizmo_right, gizmo_upper, gizmo_bottom, gizmo_center]

    def get_first_soft_snap_pos(self):
        find_x, find_y = self.find_nearest_soft_snap_pos(self.mouse_position)

        to_x, to_y = self.mouse_position

        if abs(find_x - to_x) <= self.radius:
            to_x = find_x

        if abs(find_y - to_y) <= self.radius:
            to_y = find_y
        return Vector((to_x, to_y))

    def calc_draw_data(self):
        lines = []
        lines_colors = []

        tris = []
        tris_colors = []

        line_opacity = prefs().trim_line_opacity
        tris_opacity = prefs().trim_tris_opacity


        aspect_x = min(1.0, 1.0 / self.aspect)
        aspect_y = min(1.0, self.aspect)

        gizmo_size = self.gizmo_size * self.gizmo_size_draw_multiplayer
        size_x = gizmo_size * aspect_x * 2.0
        size_y = gizmo_size * aspect_y * 2.0


        for trim in prefs().get_active_trim_slot().trims_preset:
            if not trim.visible:
                continue

            bb = trim.to_bbox()

            # Draw center cursor
            cross_size_x = size_x
            cross_size_y = size_y

            min_size = min(trim.width, trim.height)
            if min_size < self.gizmo_size:
                cross_size_x = min_size * aspect_x
                cross_size_y = min_size * aspect_y


            center = bb.center
            lines.append(center - Vector((cross_size_x, 0)))
            lines.append(center + Vector((cross_size_x, 0)))
            lines.append(center - Vector((0, cross_size_y)))
            lines.append(center + Vector((0, cross_size_y)))

            lines.extend(bb.draw_data_lines())
            tris.extend(bb.draw_data_tris())

            lines_colors.extend([[*trim.color, line_opacity + 0.3]] * 12)
            tris_colors.extend([[*trim.color, tris_opacity + 0.15]] * (1 * 2 * 3))

            if not self.is_edit:
                gizmos = self.calc_gizmo(bb, aspect_x, aspect_y, cross_size_x, cross_size_y, gizmo_size)[:8]
                for giz_bb in gizmos:
                    tris.extend(giz_bb.draw_data_tris())
                tris_colors.extend([[*trim.color, 1.0]] * (8 * 2 * 3))  # bbox * two_tris * tree_points

        self.batch_lines = batch_for_shader(self.line_shader, 'LINES', {"pos": lines, 'color': lines_colors})
        self.batch_tris = batch_for_shader(self.tris_shader, 'TRIS', {"pos": tris, 'color': tris_colors})

    def update_knife_line(self):
        """NOTE: Need actual mouse position"""
        if TrimFlags.use_knife:
            if self.use_soft_snap:
                self.soft_snap_lines = [None, None]
                find_x, find_y = self.find_nearest_soft_snap_pos(self.mouse_position)
                soft_r = self.radius * self.soft_radius_mul

                to_x, to_y = self.mouse_position

                if TrimFlags.use_knife_x_axis:
                    if abs(find_y - to_y) <= soft_r:
                        to_y = find_y
                    self.soft_snap_lines[1] = to_y
                else:
                    if abs(find_x - to_x) <= soft_r:
                        to_x = find_x
                    self.soft_snap_lines[0] = to_x
            else:
                if TrimFlags.use_knife_x_axis:
                    self.soft_snap_lines = [None, self.mouse_position.y]
                else:
                    self.soft_snap_lines = [self.mouse_position.x, None]

    def register_draw(self):
        self.handler = bpy.types.SpaceImageEditor.draw_handler_add(
            self.univ_quick_snap_draw_callback, (), 'WINDOW', 'POST_VIEW')
        self.area.tag_redraw()

    def univ_quick_snap_draw_callback(self):
        if bpy.context.area != self.area:
            return

        # shaders.set_line_width(line_width)
        shaders.blend_set_alpha()
        self.line_shader.bind()


        # shaders.set_line_width_vk(TrimDrawer.shader, line_width)
        try:
            self.line_shader.uniform_float("viewportSize", gpu.state.viewport_get()[2:])
            self.line_shader.uniform_float("lineWidth", prefs().trim_line_width)
        except: pass  # noqa

        self.batch_lines.draw(self.line_shader)
        self.batch_tris.draw(self.tris_shader)

        if (not self.use_snap and self.use_soft_snap and self.drag_trim) or TrimFlags.use_knife:
            lines = []
            if self.soft_snap_lines[0] is not None:
                x = self.soft_snap_lines[0]
                lines.append(Vector((x, -100.0)))
                lines.append(Vector((x, 100.0)))

            if self.soft_snap_lines[1] is not None:
                y = self.soft_snap_lines[1]
                lines.append(Vector((-100.0, y)))
                lines.append(Vector((100.0, y)))

            if lines:
                if TrimFlags.use_knife and TrimFlags.use_cut_through:
                    colors = [Vector((1.0,0.1,0.1,0.7))] * len(lines)
                else:
                    colors = [Vector((1,1,1,0.3))] * len(lines)
                soft_line_batch = batch_for_shader(self.line_shader, 'LINES', {"pos": lines, 'color': colors})
                soft_line_batch.draw(self.line_shader)
