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


import gpu
from gpu_extras.batch import batch_for_shader
from .gpu_utils import gpu_state_depth_test_set, gpu_state_line_width_set

from .box import UVPM4_Box
from .utils import in_debug_mode, print_backtrace
from .overlay import OverlayManager
from .spipeline.engine.box_utils import BoxRenderInfo
from .app_iface import *

SHADER_NAME_FLAT_COLOR = 'FLAT_COLOR' if AppInterface.APP_VERSION >= (4, 0, 0) else '3D_FLAT_COLOR'


def disable_box_rendering(self, context):
    prefs = get_prefs()
    prefs.box_rendering = False


class BoxRenderer(OverlayManager):

    def __init__(self, context, box_access):
        self.last_pixel_viewsize = None
        self.__draw_handler = None

        self.prefs = get_prefs()
        self.line_width = self.prefs.box_render_line_width

        self.context = context
        self.box_access =  box_access

        self.box_info_array = None
        self.active_box_info = None

        self.shader = gpu.shader.from_builtin(SHADER_NAME_FLAT_COLOR)
        self.batch = None
        self.line_batch = None

        self.update_coords()

        handler_args = (self, context)
        self.__draw_handler = SpaceImageEditor.draw_handler_add(render_boxes_draw_callback, handler_args, 'WINDOW', 'POST_VIEW')
        super().__init__(context, render_boxes_draw_text_callback)

    def finish(self):
        if self.__draw_handler is not None:
            SpaceImageEditor.draw_handler_remove(self.__draw_handler, 'WINDOW')

        super().finish()

    def update_box_access(self, box_access):
        self.box_access = box_access
        self.update_coords()

    def get_pixel_viewsize(self):
        tmp_coords0 = self.context.region.view2d.region_to_view(0, 0)
        tmp_coords1 = self.context.region.view2d.region_to_view(1, 1)
        return abs(tmp_coords0[0] - tmp_coords1[0])

    def coords_update_needed(self, event):
        pixel_viewsize_changed = self.last_pixel_viewsize is None or (self.last_pixel_viewsize != self.get_pixel_viewsize())
        return pixel_viewsize_changed

    def update_box_info_array(self):
        self.box_info_array = None
        box_info_array, self.active_box_info = self.box_access.box_info_array_impl()

        if box_info_array is None:
            return

        self.box_info_array = box_info_array # sorted(box_info_array, key=lambda box_info: box_info.z_coord)

    def update_coords(self):
        if self.box_access is None:
            return

        self.prefs.boxes_dirty = False
        self.update_box_info_array()

        if self.box_info_array is None:
            return
            
        self.batch = None
        self.line_batch = None

        batch_coords = []
        batch_colors = []

        def append_box_to_batch(box, z_coord, color):
            p1 = (box.p1_x, box.p1_y)
            p2 = (box.p2_x, box.p2_y)

            coords = [
                (p1[0], p1[1], z_coord),
                (p1[0], p2[1], z_coord),
                (p2[0], p2[1], z_coord),

                (p1[0], p1[1], z_coord),
                (p2[0], p1[1], z_coord),
                (p2[0], p2[1], z_coord)
            ]
            
            nonlocal batch_coords
            nonlocal batch_colors

            batch_coords += coords
            batch_colors += [color] * len(coords)

        def append_line_to_batch(p1, p2, fixed_coord, offset, z_coord, color):
            nonlocal append_box_to_batch

            p2 = [p2[0], p2[1]]
            p2[fixed_coord] += offset

            append_box_to_batch(UVPM4_Box.SA(p1[0], p1[1], p2[0], p2[1]), z_coord, color)

        
        self.last_pixel_viewsize = self.get_pixel_viewsize()
        line_width = self.line_width * self.last_pixel_viewsize

        for box_info in self.box_info_array:
            min_coords = box_info.box.min_corner
            max_coords = box_info.box.max_corner
            # max_coords = tuple(max(min_coords[i], max_coords[i]-pixel_viewsize[i]) for i in range(2))

            z_coord = box_info.z_coord
            color = box_info.color

            p1 = (min_coords[0], min_coords[1])
            p2 = (min_coords[0], max_coords[1])
            p3 = (max_coords[0], max_coords[1])
            p4 = (max_coords[0], min_coords[1])

            append_line_to_batch(p1, p2, 0,  line_width, z_coord, color)
            append_line_to_batch(p2, p3, 1, -line_width, z_coord, color)
            append_line_to_batch(p3, p4, 0, -line_width, z_coord, color)
            append_line_to_batch(p4, p1, 1,  line_width, z_coord, color)
            
            
        self.batch = batch_for_shader(self.shader, 'TRIS', {"pos": batch_coords, "color": batch_colors})

        if self.active_box_info is not None:
            min_coords = self.active_box_info.box.min_corner
            max_coords = self.active_box_info.box.max_corner
            z_coord = self.active_box_info.z_coord

            p1 = (min_coords[0], min_coords[1], z_coord)
            p2 = (min_coords[0], max_coords[1], z_coord)
            p3 = (max_coords[0], max_coords[1], z_coord)
            p4 = (max_coords[0], min_coords[1], z_coord)

            line_coords = [
                p1, p2,
                p2, p3,
                p3, p4,
                p4, p1
            ]

            line_colors = [self.active_box_info.outline_color] * len(line_coords)
            self.line_batch = batch_for_shader(self.shader, 'LINES', {"pos": line_coords, "color": line_colors})

        self.context.area.tag_redraw()


def render_boxes_draw_callback(self, context):
    try:
        self.box_access.is_alive()

        self.shader.bind()
        gpu_state_depth_test_set("LESS_EQUAL")

        if self.batch is not None:
            self.batch.draw(self.shader)

        gpu_state_depth_test_set("NONE")

        if self.line_batch is not None:
            gpu_state_line_width_set(1.0)
            self.line_batch.draw(self.shader)

    except Exception as ex:
        if in_debug_mode(debug_lvl=2):
            print_backtrace(ex)


def render_boxes_draw_text_callback(self, context):
    if self.box_access is None:
        return

    try:
        self.box_access.is_alive()
        self.callback_begin()

        if self.box_info_array is None:
            return

        for box_info in self.box_info_array:

            if len(box_info.text) == 0:
                continue

            text_view_coords = box_info.box.min_corner

            COORD_OFFSET = 0.05
            text_view_coords = (text_view_coords[0] + COORD_OFFSET, text_view_coords[1] + COORD_OFFSET)

            text_region_coords = self.context.region.view2d.view_to_region(text_view_coords[0], text_view_coords[1], clip=False)
            text_region_coords = [text_region_coords[0], text_region_coords[1] + self.line_distance * box_info.text_line_num]

            self.print_text(text_region_coords, box_info.text, box_info.color, box_info.z_coord)

        gpu_state_depth_test_set("NONE")

    except Exception as ex:
        if in_debug_mode(debug_lvl=2):
            print_backtrace(ex)


class BoxRenderAccess:

    ACTIVE_COLOR = None
    ACTIVE_COLOR_MULTIPLIER = 1.0
    ACTIVE_Z_COORD = None
    ACTIVE_OUTLINE_COLOR = (1,0.25,0,1)

    NON_ACTIVE_COLOR_MULTIPLIER = 1.0

    def is_alive(self):
        return True


class BoxArrayAccess:

    def __init__(self, box_array, color, active_idx=-1):
        assert(len(box_array) > 0)
        self.box_array = box_array
        self.color = color
        self.active_idx = active_idx

    def active_box_impl(self):
        if self.active_idx < 0:
            return None
        
        return self.box_array[self.active_idx]


class BoxArrayRenderAccess(BoxArrayAccess, BoxRenderAccess):

    def box_info_array_impl(self):
        box_info_array = [BoxRenderInfo(glob_idx, box, self.color) for glob_idx, box in enumerate(self.box_array)]

        active_box_info = None if self.active_idx < 0 else box_info_array[self.active_idx]
        return box_info_array, active_box_info

    def select_box_impl(self, box_info):
        self.active_idx = box_info.glob_idx


class MainBoxArrayRenderAccess(BoxArrayRenderAccess):

    from .spipeline.engine.box_utils import MAIN_TARGET_BOX_COLOR

    def __init__(self, box_array, active_idx=-1):
        super().__init__(box_array, self.MAIN_TARGET_BOX_COLOR, active_idx=active_idx)


class CustomTargetBoxAccess(MainBoxArrayRenderAccess):

    def __init__(self, context, ui_drawing=False):
        super().__init__([get_main_props(context).custom_target_box], active_idx=0)
    

class TileTargetBoxAccess(MainBoxArrayRenderAccess):

    def __init__(self, context):
        self.context = context
        self.main_props = get_main_props(context)
    
    def box_info_array_impl(self):
        app_state = AppState(self.context)
        super().__init__(self.main_props.tile_target_props.get_target_boxes(app_state))
        return super().box_info_array_impl()


class BoxInfoArrayRenderAccess(BoxArrayRenderAccess):

    def __init__(self, box_info_array):
        self.box_info_array = box_info_array
        self.active_idx = -1

    def box_info_array_impl(self):
        active_box_info = None if self.active_idx < 0 else self.box_info_array[self.active_idx]
        return self.box_info_array, active_box_info
