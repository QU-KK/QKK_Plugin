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


import bmesh

import struct
from .pack_context import PackContext


def get_bmesh(obj):
    if obj.mode == 'OBJECT':
        bm = bmesh.new()
        bm.from_mesh(obj.data)

    elif obj.mode == 'EDIT':
        bm = bmesh.from_edit_mesh(obj.data)

    else:
        assert False

    return bm


def commit_bmesh(obj, bm):
    if obj.mode == 'OBJECT':
        bm.to_mesh(obj.data)

    elif obj.mode == 'EDIT':
        bmesh.update_edit_mesh(obj.data)

    else:
        assert False


class UvMapView:

    def __init__(self, context, obj, uv_name):
        self.obj = obj
        self.bm = get_bmesh(obj)
        self.uv_layer = self.bm.loops.layers.uv.get(uv_name)
        self.uv_select_sync = context.tool_settings.use_uv_select_sync

    def commit(self):
        commit_bmesh(self.obj, self.bm)

    def select_all(self, select):
        has_hidden_faces = False

        for face in self.bm.faces[:]:
            if not PackContext.face_is_visible(face, self.uv_select_sync):
                has_hidden_faces = True
                continue

            PackContext.select_face(self.uv_layer, face, self.uv_select_sync, select)

        return has_hidden_faces

    def serialize(self, visible_state=False):
        b = bytes()

        if visible_state:
            visible_array = []

        for face in self.bm.faces:
            if visible_state:
                visible_array.append(PackContext.face_is_visible(face, self.uv_select_sync))

            for loop in face.loops:
                uv = loop[self.uv_layer].uv
                b += struct.pack('ff', *(uv[0], uv[1]))

        if visible_state:
            b += struct.pack('{}B'.format(len(visible_array)), *visible_array)

        return b
