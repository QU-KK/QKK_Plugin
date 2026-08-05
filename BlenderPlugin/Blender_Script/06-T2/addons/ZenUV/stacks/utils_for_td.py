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

""" Zen UV Stack System Utils for Texel Density calculation """


class TmpStack:

    obj_name: str = None
    ids: list = None

    def __init__(self, obj_name: str, ids: list) -> None:
        self.obj_name = obj_name
        self.ids = ids


def get_unique_islands(stacks: dict):
    scope = []
    for v in stacks.values():
        p_ids = list(next(iter(v['objs'].values())).values())[0]
        scope.append(TmpStack(obj_name=list(v['objs'].keys())[0], ids=p_ids))

    storage = dict()
    for p_obj_name in {i.obj_name for i in scope}:
        storage.update({p_obj_name: []})

    for i in scope:
        storage[i.obj_name].extend(i.ids)

    return storage
