import bpy
import bmesh

from .. utils.decal import sort_panel_geometry, create_panel_uvs
from .. utils.mesh import get_eval_mesh
from .. utils.modifier import get_nrmtransfer
from .. utils.object import is_obj_smooth
from .. utils.raycast import shrinkwrap

class Unwrap(bpy.types.Operator):
    bl_idname = "machin3.panel_decal_unwrap"
    bl_label = "MACHIN3: Panel Decal Unwrap"
    bl_description = "Re-Unwraps panel decals\nALT: Shrinkwraps in addtion to Unwrap"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        decals = [obj for obj in context.selected_objects if obj.DM.isdecal]
        return decals and all(obj.DM.decaltype == "PANEL" and obj.DM.issliced for obj in decals)

    def invoke(self, context, event):
        for obj in context.selected_objects:
            bm = bmesh.new()
            bm.from_mesh(obj.data)
            bm.normal_update()
            bm.verts.ensure_lookup_table()

            target = obj.DM.slicedon if obj.DM.slicedon else obj.parent if obj.parent else None

            if event.alt and target:
                    dg = context.evaluated_depsgraph_get()

                    bmt = bmesh.new()
                    bmt.from_mesh(get_eval_mesh(dg, target, data_block=False))

                    deltamx = target.matrix_world.inverted_safe() @ obj.matrix_world
                    shrinkwrap(bm, bmt, deltamx)

            use_smooth = is_obj_smooth(target)

            geo = sort_panel_geometry(bm, smooth=use_smooth)

            if not use_smooth or target.type != 'MESH':
                nrmtransfer = get_nrmtransfer(obj, create=False)

                if nrmtransfer and 'UVTransfer' not in nrmtransfer.name:
                    nrmtransfer.show_viewport = False
                    nrmtransfer.show_render = False

            create_panel_uvs(bm, geo, obj)

            obj.data.update()

        return {'FINISHED'}
