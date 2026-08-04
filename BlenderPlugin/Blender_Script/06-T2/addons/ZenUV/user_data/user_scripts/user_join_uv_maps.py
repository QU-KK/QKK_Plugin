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

# Copyright 2024, Alex Zhornyak, alexander.zhornyak@gmail.com

import bpy
import bmesh


class ZUV_OP_UVMapsJoin(bpy.types.Operator):
    bl_idname = 'uv.zenuv_join_uv_maps'
    bl_label = 'Join UV Maps'
    bl_description = 'Join UV maps by replacing 0 coordinantes'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        """ Validate context """
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH'

    def execute(self, context: bpy.types.Context):
        b_modified = False

        p_act_obj = context.active_object
        if p_act_obj and p_act_obj.type == 'MESH':
            me: bpy.types.Mesh = p_act_obj.data
            bm = bmesh.from_edit_mesh(me)
            p_uv_layer = bm.loops.layers.uv.active
            if p_uv_layer:
                for face in bm.faces:
                    for loop in face.loops:
                        if loop[p_uv_layer].uv[:] == (0, 0):
                            for it_uv in bm.loops.layers.uv:
                                if it_uv != p_uv_layer:
                                    if loop[it_uv].uv[:] != (0, 0):
                                        loop[p_uv_layer].uv = loop[it_uv].uv[:]
                                        b_modified = True

                if b_modified:
                    bmesh.update_edit_mesh(me, loop_triangles=False, destructive=False)

        if b_modified:
            return {'FINISHED'}
        else:
            self.report({'INFO'}, 'Nothing was joined! No zero coordinates was found!')
            return {'CANCELLED'}


def zenuv_draw_user_adv_maps(self, context):
    layout = self.layout
    layout.separator()
    layout.operator(ZUV_OP_UVMapsJoin.bl_idname)


def register():
    print('Starting Zen UV user script...')

    bpy.types.ZUV_MT_AdvMapsMenu.append(zenuv_draw_user_adv_maps)

    bpy.utils.register_class(ZUV_OP_UVMapsJoin)


def unregister():
    print('Finishing Zen UV user script...')

    bpy.types.ZUV_MT_AdvMapsMenu.remove(zenuv_draw_user_adv_maps)

    bpy.utils.unregister_class(ZUV_OP_UVMapsJoin)
