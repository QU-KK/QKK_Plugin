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

# Copyright 2022, Alex Zhornyak

import gpu
from gpu_extras.batch import batch_for_shader
import blf
import math

from dataclasses import dataclass


@dataclass
class Rectangle:
    left: float = 0.0
    top: float = 0.0
    right: float = 0.0
    bottom: float = 0.0
    auto_normalize: bool = True

    @property
    def width(self):
        return self.right - self.left

    @width.setter
    def width(self, val):
        self.right = self.left + val

    @property
    def height(self):
        return self.top - self.bottom

    @height.setter
    def height(self, val):
        self.top = self.bottom + val

    def __post_init__(self):
        if self.auto_normalize:
            self.normalize()

    def normalize(self):
        p_left = min(self.left, self.right)
        p_right = max(self.left, self.right)
        p_bottom = min(self.top, self.bottom)
        p_top = max(self.top, self.bottom)

        self.left = p_left
        self.top = p_top
        self.right = p_right
        self.bottom = p_bottom

    def center(self):
        return (self.left + self.width / 2, self.bottom + self.height / 2)

    def intersects(self, other):
        if self.left > other.right or self.right < other.left:
            return False

        if self.top < other.bottom or self.bottom > other.top:
            return False

        return True

    def __hash__(self):
        return hash((self.left, self.top, self.right, self.bottom))


@dataclass
class TextRect(Rectangle):
    name: str = ''
    color: tuple = (0, 0, 0, 0)

    def __hash__(self):
        return hash((super().__hash__(), self.name, self.color))

    def draw_text(self):
        blf.position(0, self.left, self.bottom, 0)

        blf.color(0, *self.color)

        blf.enable(0, blf.SHADOW)
        blf.shadow(0, 3, 0.0, 0.0, 0.0, 1.0)
        blf.shadow_offset(0, 1, -1)

        blf.draw(0, self.name)

        blf.disable(0, blf.SHADOW)


def draw_circle_2d_filled(mx, my, radius, color=(1.0, 1.0, 1.0, 0.7)):
    from ZenUV.utils.blender_zen_utils import ZenCompat

    radius = radius * 1.0
    sides = 12
    vertices = [
        (
            radius * math.cos(i * 2 * math.pi / sides) + mx,
            radius * math.sin(i * 2 * math.pi / sides) + my)
        for i in range(sides + 1)
    ]

    shader = gpu.shader.from_builtin(ZenCompat.get_2d_uniform_color())
    shader.uniform_float("color", color)
    batch = batch_for_shader(shader, 'TRI_FAN', {"pos": vertices})
    batch.draw(shader)


def draw_rounded_rect(rect: Rectangle, view_width, view_height, shader, color, scale, line_width, tl=5, tr=5, bl=5, br=5, outline=False):
    """
    Originally taken from:
    https://projects.blender.org/extensions/object_collection_manager/src/branch/main/source/qcd_move_widget.py

    Author:
    2011 Ryan Inch
    """
    sides = 32

    tl = round(tl * scale)
    tr = round(tr * scale)
    bl = round(bl * scale)
    br = round(br * scale)

    draw_type = 'TRI_FAN' if not outline else 'LINE_STRIP'

    # top left corner
    vert_x = rect.left + tl
    vert_y = rect.top - tl
    tl_vert = (vert_x, vert_y)
    vertices = [(vert_x, vert_y)] if not outline else []

    for side in range(sides+1):
        if (8 <= side <= 16):
            cosine = tl * math.cos(side * 2 * math.pi / sides) + vert_x
            sine = tl * math.sin(side * 2 * math.pi / sides) + vert_y
            vertices.append((cosine, sine))

    if not outline:
        batch = batch_for_shader(shader, draw_type, {"pos": vertices})
        shader.bind()
        shader.uniform_float("color", color)
        batch.draw(shader)
    else:
        batch = batch_for_shader(shader, draw_type, {"pos": [(v[0], v[1], 0) for v in vertices], "color": [color for v in vertices]})
        shader.bind()
        shader.uniform_float("viewportSize", (view_width, view_height))
        shader.uniform_float("lineWidth", line_width)

        batch.draw(shader)

    # top right corner
    vert_x = rect.right - tr
    vert_y = rect.top - tr
    tr_vert = (vert_x, vert_y)
    vertices = [(vert_x, vert_y)] if not outline else []

    for side in range(sides+1):
        if (0 <= side <= 8):
            cosine = tr * math.cos(side * 2 * math.pi / sides) + vert_x
            sine = tr * math.sin(side * 2 * math.pi / sides) + vert_y
            vertices.append((cosine, sine))

    if not outline:
        batch = batch_for_shader(shader, draw_type, {"pos": vertices})
        shader.bind()
        shader.uniform_float("color", color)
        batch.draw(shader)
    else:
        batch = batch_for_shader(shader, draw_type, {"pos": [(v[0], v[1], 0) for v in vertices], "color": [color for v in vertices]})
        shader.bind()
        batch.draw(shader)

    # bottom left corner
    vert_x = rect.left + bl
    vert_y = rect.bottom + bl
    bl_vert = (vert_x, vert_y)
    vertices = [(vert_x, vert_y)] if not outline else []

    for side in range(sides+1):
        if (16 <= side <= 24):
            cosine = bl * math.cos(side * 2 * math.pi / sides) + vert_x
            sine = bl * math.sin(side * 2 * math.pi / sides) + vert_y
            vertices.append((cosine, sine))

    if not outline:
        batch = batch_for_shader(shader, draw_type, {"pos": vertices})
        shader.bind()
        shader.uniform_float("color", color)
        batch.draw(shader)
    else:
        batch = batch_for_shader(shader, draw_type, {"pos": [(v[0], v[1], 0) for v in vertices], "color": [color for v in vertices]})
        shader.bind()
        batch.draw(shader)

    # bottom right corner
    vert_x = rect.right - br
    vert_y = rect.bottom + br
    br_vert = (vert_x, vert_y)
    vertices = [(vert_x, vert_y)] if not outline else []

    for side in range(sides+1):
        if (24 <= side <= 32):
            cosine = br * math.cos(side * 2 * math.pi / sides) + vert_x
            sine = br * math.sin(side * 2 * math.pi / sides) + vert_y
            vertices.append((cosine, sine))

    if not outline:
        batch = batch_for_shader(shader, draw_type, {"pos": vertices})
        shader.bind()
        shader.uniform_float("color", color)
        batch.draw(shader)
    else:
        batch = batch_for_shader(shader, draw_type, {"pos": [(v[0], v[1], 0) for v in vertices], "color": [color for v in vertices]})
        shader.bind()
        batch.draw(shader)

    if not outline:
        vertices = []
        indices = []
        base_ind = 0

        # left edge
        width = max(tl, bl)
        le_x = tl_vert[0]-tl
        vertices.extend([
            (le_x, tl_vert[1]),
            (le_x+width, tl_vert[1]),
            (le_x, bl_vert[1]),
            (le_x+width, bl_vert[1])
            ])
        indices.extend([
            (base_ind, base_ind + 1, base_ind + 2),
            (base_ind + 2, base_ind + 3, base_ind + 1)
            ])
        base_ind += 4

        # right edge
        width = max(tr, br)
        re_x = tr_vert[0]+tr
        vertices.extend([
            (re_x, tr_vert[1]),
            (re_x-width, tr_vert[1]),
            (re_x, br_vert[1]),
            (re_x-width, br_vert[1])
            ])
        indices.extend([
            (base_ind, base_ind + 1, base_ind+2),
            (base_ind + 2, base_ind + 3, base_ind+1)
            ])
        base_ind += 4

        # top edge
        width = max(tl, tr)
        te_y = tl_vert[1]+tl
        vertices.extend([
            (tl_vert[0], te_y),
            (tl_vert[0], te_y-width),
            (tr_vert[0], te_y),
            (tr_vert[0], te_y-width)
            ])
        indices.extend([
            (base_ind, base_ind + 1, base_ind + 2),
            (base_ind + 2, base_ind + 3, base_ind + 1)
            ])
        base_ind += 4

        # bottom edge
        width = max(bl, br)
        be_y = bl_vert[1]-bl
        vertices.extend([
            (bl_vert[0], be_y),
            (bl_vert[0], be_y+width),
            (br_vert[0], be_y),
            (br_vert[0], be_y+width)
            ])
        indices.extend([
            (base_ind, base_ind + 1, base_ind + 2),
            (base_ind + 2, base_ind + 3, base_ind + 1)
            ])
        base_ind += 4

        # middle
        vertices.extend([
            tl_vert,
            tr_vert,
            bl_vert,
            br_vert
            ])
        indices.extend([
            (base_ind, base_ind + 1, base_ind+2),
            (base_ind + 2, base_ind + 3, base_ind+1)
            ])

        batch = batch_for_shader(shader, 'TRIS', {"pos": vertices}, indices=indices)
        shader.bind()

        shader.uniform_float("color", color)
        batch.draw(shader)

    else:
        overlap = round(line_width / 2 - scale / 2)

        # left edge
        le_x = tl_vert[0]-tl
        vertices = [
            (le_x, tl_vert[1] + (overlap if tl == 0 else 0)),
            (le_x, bl_vert[1] - (overlap if bl == 0 else 0))
            ]

        batch = batch_for_shader(shader, 'LINE_STRIP', {"pos": [(v[0], v[1], 0) for v in vertices], "color": [color for v in vertices]})
        shader.bind()
        batch.draw(shader)

        # right edge
        re_x = tr_vert[0]+tr
        vertices = [
            (re_x, tr_vert[1] + (overlap if tr == 0 else 0)),
            (re_x, br_vert[1] - (overlap if br == 0 else 0))
            ]

        batch = batch_for_shader(shader, 'LINE_STRIP', {"pos": [(v[0], v[1], 0) for v in vertices], "color": [color for v in vertices]})
        shader.bind()
        batch.draw(shader)

        # top edge
        te_y = tl_vert[1]+tl
        vertices = [
            (tl_vert[0] - (overlap if tl == 0 else 0), te_y),
            (tr_vert[0] + (overlap if tr == 0 else 0), te_y)
            ]

        batch = batch_for_shader(shader, 'LINE_STRIP', {"pos": [(v[0], v[1], 0) for v in vertices], "color": [color for v in vertices]})
        shader.bind()
        batch.draw(shader)

        # bottom edge
        be_y = bl_vert[1]-bl
        vertices = [
            (bl_vert[0] - (overlap if bl == 0 else 0), be_y),
            (br_vert[0] + (overlap if br == 0 else 0), be_y)
            ]

        batch = batch_for_shader(shader, 'LINE_STRIP', {"pos": [(v[0], v[1], 0) for v in vertices], "color": [color for v in vertices]})
        shader.bind()
        batch.draw(shader)
