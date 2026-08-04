import bpy
import bmesh
from mathutils import Vector, Matrix
from .. utils.decal import apply_decal, set_defaults, get_target, ensure_decalobj_versions
from .. utils.modifier import add_displace, add_nrmtransfer, get_displace, add_subd, add_shrinkwrap, get_nrmtransfer, get_subd, get_shrinkwrap, get_uvtransfer, move_mod
from .. utils.raycast import get_origin_from_object_boundingbox
from .. utils.mesh import get_eval_mesh, hide, unhide, blast, smooth, init_uvs, reset_material_indices
from .. utils.object import intersect, flatten, parent, update_local_view, lock, unshrinkwrap
from .. utils.math import remap, create_bbox, flatten_matrix
from .. utils.raycast import get_bvh_ray_distance_from_verts
from .. utils.ui import popup_message, init_cursor, init_status, finish_status
from .. utils.uv import get_uv_transfer_layer, get_active_uv_layer
from .. utils.collection import unlink_object_from_all_collections
from .. utils.property import set_cycles_visibility
from .. utils.draw import draw_lines, draw_tris

class Project(bpy.types.Operator):
    bl_idname = "machin3.project_decal"
    bl_label = "MACHIN3: Project Decal"
    bl_description = "Project Selected Decals on Surface\nALT: Manually Adjust Projection Depth\nCTRL: Use UV Project instead of UV Transfer\nSHIFT: Shrinkwrap"
    bl_options = {'REGISTER', 'UNDO'}

    passthrough = False

    @classmethod
    def poll(cls, context):
        sel = context.selected_objects

        if any(obj.DM.isdecal and not obj.DM.preatlasmats and not obj.DM.prejoindecals for obj in sel):

            if any(not obj.DM.isprojected and not obj.DM.issliced for obj in sel):
                return True

            elif all(obj.DM.issliced for obj in sel):

                return any(get_shrinkwrap(obj) is None and get_subd(obj) is None and (target := get_target(None, None, None, obj)) and target.type == 'MESH' for obj in sel)

    def draw_VIEW3D(self, context):
        for decal, target, projected, (front, back), bbox in self.projections:
            coords, edge_indices, tri_indices = bbox

            mxcoords = []
            for idx, co in enumerate(coords):
                if idx > 3:
                    mxt = Matrix.Translation((0, 0, (back + abs(self.offset)) / decal.scale.z))
                    mxco = decal.matrix_world @ mxt @ Vector(co)
                else:
                    mxt = Matrix.Translation((0, 0, (-front - abs(self.offset)) / decal.scale.z))
                    mxco = decal.matrix_world @ mxt @ Vector(co)

                mxcoords.append(mxco)

            draw_lines(mxcoords, indices=edge_indices[:8], width=2, alpha=0.3, xray=False)

            draw_lines(mxcoords, indices=edge_indices[8:], width=1, alpha=0.2, xray=False)

            draw_tris(mxcoords, indices=tri_indices[:4], alpha=0.1, xray=False)

    def modal(self, context, event):
        context.area.tag_redraw()

        events = ['MOUSEMOVE']

        if event.type in events:

            if event.type == 'MOUSEMOVE':
                if self.passthrough:
                    self.passthrough = False

                elif not event.alt:
                    divisor = 1000 if event.shift else 10 if event.ctrl else 100

                    delta_x = event.mouse_x - self.last_mouse_x
                    delta_offset = delta_x / divisor

                    self.offset += delta_offset

        elif event.type in {'MIDDLEMOUSE'} or (event.alt and event.type in {'LEFTMOUSE', 'RIGHTMOUSE'}):
            self.passthrough = True
            return {'PASS_THROUGH'}

        elif event.type in {'LEFTMOUSE', 'SPACE'}:
            self.finish()

            for decal, target, projected, (front, back), bbox in self.projections:
                projected.hide_set(False)
                projected = self.project(context, event, decal, target, projected=projected, depth=(front + abs(self.offset), back + abs(self.offset)))

                if not projected:
                    self.failed.append((decal, "TRY_REAPPLY"))

            if self.failed or self.legacy_decals or self.future_decals:
                self.report_errors(self.failed)

            return {'FINISHED'}

        elif event.type in {'RIGHTMOUSE', 'ESC'}:
            self.finish()

            for decal, target, projected, (front, back), bbox in self.projections:
                bpy.data.meshes.remove(projected.data, do_unlink=True)

            return {'CANCELLED'}

        self.last_mouse_x = event.mouse_x

        return {'RUNNING_MODAL'}

    def finish(self):
        bpy.types.SpaceView3D.draw_handler_remove(self.VIEW3D, 'WINDOW')

        finish_status(self)

    def invoke(self, context, event):
        self.dg = context.evaluated_depsgraph_get()

        self.active = context.active_object
        self.sel = context.selected_objects.copy()

        selected_decals = [obj for obj in self.sel if obj.DM.isdecal and not obj.DM.preatlasmats and not obj.DM.prejoindecals]

        if all(obj.DM.issliced for obj in selected_decals):
            decals = selected_decals

        else:
            decals = [obj for obj in selected_decals if not obj.DM.isprojected and not obj.DM.issliced]

        current_decals, self.legacy_decals, self.future_decals = ensure_decalobj_versions(decals)

        for obj in self.sel:
            if obj not in current_decals:
                obj.select_set(False)

        if event.alt:
            if self.invoke_modal(context, event, current_decals):
                return {'RUNNING_MODAL'}

            if self.failed or self.legacy_decals or self.future_decals:
                self.report_errors(self.failed)

        else:
            self.invoke_simple(context, event, current_decals)

        return {'FINISHED'}

    def invoke_modal(self, context, event, decals):
        self.projections = []
        self.failed = []

        for obj in decals:
            target = get_target(self.dg, self.active, self.sel, obj)

            if target:
                if target != obj.parent:
                    apply_decal(self.dg, obj, target=target)

                projected = self.create_projected_base_object(obj, target)

                front, back = get_bvh_ray_distance_from_verts(projected, obj, (0, 0, -1), 0.1)

                if front + back < 0.001 * obj.scale.z:
                    front = back = 0.001 * obj.scale.z

                bbox = create_bbox(obj)

                self.projections.append((obj, target, projected, (front, back), bbox))

            else:
                self.failed.append((obj, "FORCE_PROJECT"))

        if self.projections:

            self.offset = 0

            init_cursor(self, event)

            init_status(self, context, 'Project')

            self.area = context.area
            self.VIEW3D = bpy.types.SpaceView3D.draw_handler_add(self.draw_VIEW3D, (context, ), 'WINDOW', 'POST_VIEW')

            context.window_manager.modal_handler_add(self)
            return True

    def invoke_simple(self, context, event, decals):
        failed = []

        for decal in decals:
            target = get_target(self.dg, self.active, self.sel, decal)

            if target:

                if target != decal.parent:
                    apply_decal(self.dg, decal, target=target)

                if event.shift or all(obj.DM.issliced for obj in decals):
                    if target.type == 'MESH':
                        self.shrinkwrap(context, decal, target)
                    else:
                        failed.append((decal, "NON_MESH_SHRINKWRAP"))

                else:
                    projected = self.project(context, event, decal, target)

                    if not projected:
                        mindim = min([d for d in decal.dimensions if d])
                        projected = self.project(context, event, decal, target, depth=(mindim, mindim))

                        if not projected:
                            failed.append((decal, "TRY_REAPPLY"))

            else:
                failed.append((decal, "FORCE_PROJECT"))

        if failed or self.legacy_decals or self.future_decals:
            self.report_errors(failed)

    def report_errors(self, failed):
        if all(obj.DM.issliced for obj, _ in failed):
            msg = ["Shrinkwraping the following decals failed:"]

        elif any(obj.DM.issliced for obj, _ in failed):
            msg = ["Projecting/Shrinkwraping the following decals failed:"]

        else:
            msg = ["Projecting the following decals failed:"]

        if failed:
            for obj, _ in failed:
                msg.append(" • " + obj.name)

            messages = set(msg for _, msg in failed)
            targets = set(obj.parent for obj, _ in failed if obj.parent)

            if 'TRY_REAPPLY' in messages:
                msg.append(f"Try Re-Applying the decal{'s' if len(failed) > 1 else ''} first!")

                if targets and any(mod.type == 'BOOLEAN' for tobj in targets for mod in tobj.modifiers):
                    msg.append("If the target object carries complex booleans, you can also try adding a Weld mod at the end.")

            if 'FORCE_PROJECT' in messages:
                msg.append("You can force-project on a non-decal object by selecting it last.")

            if 'NON_MESH_SHRINKWRAP' in messages:
                msg.append("You can only Shrinkwrap on MESH objects")

        if self.legacy_decals:
            if failed:
                msg.append('')

            for obj in self.legacy_decals:
                msg.append(f" • {obj.name}")

            msg.append("These are legacy decals, that need to be updated before they can be used!")

        if self.future_decals:
            if failed or self.legacy_decals:
                msg.append('')

            for obj in self.future_decals:
                msg.append(f" • {obj.name}")

            msg.append("These are next-gen decals, that can't be used in this Blender version!")

        popup_message(msg)

    def align_uvempty(self, uvempty, decal):
        loc = get_origin_from_object_boundingbox(self.dg, decal)

        _, rot, _ = decal.matrix_world.decompose()

        sca = Matrix()
        sca[0][0] = decal.dimensions.x / 2
        sca[1][1] = decal.dimensions.y / 2
        sca[2][2] = 1

        uvempty.matrix_world = Matrix.Translation(loc) @ rot.to_matrix().to_4x4() @ sca

    def validate_projected(self, projected, decal):
        if not projected.data.polygons:
            return False

        dmxw = decal.matrix_world
        origin, _, _ = dmxw.decompose()
        direction = dmxw @ Vector((0, 0, -1)) - origin

        pmxw = projected.matrix_world
        pmxi = pmxw.inverted_safe()
        direction_local = pmxi.to_3x3() @ direction

        bm = bmesh.new()
        bm.from_mesh(projected.data)
        bm.normal_update()
        bm.verts.ensure_lookup_table()

        backfaces = [f for f in bm.faces if f.normal.dot(direction_local) > 0]

        bmesh.ops.delete(bm, geom=backfaces, context="FACES")

        if bm.faces:
            bm.to_mesh(projected.data)
            bm.clear()
            return True

        else:
            return False

    def shrinkwrap(self, context, decal, target):
        smooth(decal.data)

        subd = add_subd(decal)
        shrinkwrap = add_shrinkwrap(decal, target)

        if decal.DM.decaltype == 'PANEL':
            subd.subdivision_type = 'CATMULL_CLARK'
            subd.boundary_smooth = 'PRESERVE_CORNERS'

        move_mod(subd, 0)
        move_mod(shrinkwrap, 1)

        set_defaults(decalobj=decal)
    def setup_uv_transfer(self, context, decal, projected, mod):
        context.view_layer.objects.active = projected

        transfer_uvs = get_uv_transfer_layer(projected, create=True)
        source_uvs = get_active_uv_layer(decal.parent)

        mod.name = 'NormalUVTransfer'
        mod.data_types_loops = {'CUSTOM_NORMAL', 'UV'}

        mod.layers_uv_select_src = source_uvs.name
        mod.layers_uv_select_dst = transfer_uvs.name

    def project(self, context, event, decal, target, projected=None, depth=None):
        mirrors = [mod for mod in decal.modifiers if mod.type == "MIRROR" and mod.show_render and mod.show_viewport]

        orig_nrm_transfer = get_nrmtransfer(decal, create=False)
        is_uv_transfer = orig_nrm_transfer and 'UV' in orig_nrm_transfer.data_types_loops

        for mod in mirrors:
            mod.show_viewport = False

        unshrinkwrap(decal)

        if event.ctrl:
            uvempty = bpy.data.objects.new("uvempty", None)
            context.collection.objects.link(uvempty)

            self.align_uvempty(uvempty, decal)

        if not projected:
            projected = self.create_projected_base_object(decal, target)

        projected.hide_set(False)

        unhide(projected.data)
        hide(decal.data)

        if not depth:
            front, back = get_bvh_ray_distance_from_verts(projected, decal, (0, 0, -1), 0.1)

            if front + back < 0.001 * decal.scale.z:
                front = back = 0.001 * decal.scale.z

            factor = 1.2

        else:
            front, back = depth

            factor = 1.01

        thickness = (front + back) / decal.scale.z

        solidify = decal.modifiers.new(name="Solidify", type="SOLIDIFY")
        solidify.thickness = thickness * factor
        solidify.offset = remap(0, -back, front, -1 / factor, 1 / factor)

        if bpy.app.version >= (4, 5, 0):
            move_mod(solidify, 0)

        displace = get_displace(decal)

        if displace:
            displace.show_viewport = False

        intersect(projected, decal)
        flatten(projected)

        blast(projected.data, "hidden", "FACES")

        parent(projected, target)

        projected.DM.isdecal = True
        projected.DM.isprojected = True
        projected.DM.projectedon = target
        projected.DM.decalbackup = decal
        projected.DM.uuid = decal.DM.uuid
        projected.DM.version = decal.DM.version
        projected.DM.decaltype = decal.DM.decaltype
        projected.DM.decallibrary = decal.DM.decallibrary
        projected.DM.decalname = decal.DM.decalname
        projected.DM.decalmatname = decal.DM.decalmatname
        projected.DM.creator = decal.DM.creator

        projected.DM.istrimdecal = decal.DM.istrimdecal

        if projected.DM.istrimdecal:
            projected.DM.trimsheetuuid = decal.DM.trimsheetuuid

        set_cycles_visibility(projected, 'shadow', False)
        set_cycles_visibility(projected, 'diffuse', False)

        decal.modifiers.remove(solidify)
        unhide(decal.data)

        if displace:
            displace.show_viewport=True

        if not self.validate_projected(projected, decal):
            bpy.data.meshes.remove(projected.data, do_unlink=True)
            for mod in mirrors:
                mod.show_viewport = True

            return False

        init_uvs(projected.data)

        reset_material_indices(projected.data)

        if event.ctrl:
            uvproject = projected.modifiers.new(name="UVProject", type="UV_PROJECT")
            uvproject.projectors[0].object = uvempty
            flatten(projected)
            bpy.data.objects.remove(uvempty, do_unlink=True)

        else:
            uvtransfer = projected.modifiers.new(name="UVTransfer", type="DATA_TRANSFER")
            uvtransfer.object = decal
            uvtransfer.use_loop_data = True
            uvtransfer.loop_mapping = 'POLYINTERP_NEAREST'
            uvtransfer.data_types_loops = {'UV'}
            uvtransfer.layers_uv_select_dst = 'INDEX'
            flatten(projected)

        if decal.active_material:
            projected.data.materials.append(decal.active_material)

        add_displace(projected)

        for mod in mirrors:
            mirror = projected.modifiers.new(name=mod.name, type="MIRROR")
            mirror.use_axis = mod.use_axis
            mirror.use_mirror_u = mod.use_mirror_u
            mirror.use_mirror_v = mod.use_mirror_v
            mirror.mirror_object = mod.mirror_object

        nrmtransfer = add_nrmtransfer(projected, target)

        if is_uv_transfer:
            from . texture_coordinates import UVTransfer
            mod = UVTransfer.setup_transfer_mod(self, projected)

            source_uvs, transfer_uvs = UVTransfer.setup_uv_transfer(self, context, projected, mod)

        elif not projected.data.polygons[0].use_smooth:
            nrmtransfer.show_viewport = False
            nrmtransfer.show_render = False

        set_defaults(decalobj=projected, ignore_normal_transfer_visibility=True)
        lock(projected)

        projected.select_set(True)

        if context.active_object == decal:
            context.view_layer.objects.active = projected

        decal.use_fake_user = True
        decal.DM.isbackup = True

        unlink_object_from_all_collections(decal)

        decal.DM.backupmx = flatten_matrix(target.matrix_world.inverted_safe() @ decal.matrix_world)

        update_local_view(context.space_data, [(projected, True)])

        if projected.data.has_custom_normals:
            with context.temp_override(object=projected):
                bpy.ops.mesh.customdata_custom_splitnormals_clear()

        if get_uv_transfer_layer(decal, create=False) and get_uvtransfer(decal):
            self.setup_uv_transfer(context, decal, projected, nrmtransfer)

        return True

    def create_projected_base_object(self, decal, target):
        mesh = get_eval_mesh(self.dg, target, data_block=True)

        mesh.materials.clear()

        attribute_names = [attr.name for attr in mesh.attributes]

        for name in attribute_names:
            if name.startswith('.') or name in ['position', 'sharp_face', 'material_index']:
                continue

            mesh.attributes.remove(mesh.attributes[name])

        projected = bpy.data.objects.new(f"{decal.name}_projected", object_data=mesh)

        projected.vertex_groups.clear()

        projected.shape_key_clear()

        projected.matrix_world = target.matrix_world

        for col in decal.users_collection:
            col.objects.link(projected)

        projected.hide_set(True)

        return projected

class UnShrinkwrap(bpy.types.Operator):
    bl_idname = "machin3.unshrinkwrap_decal"
    bl_label = "MACHIN3: Unshrinkwrap"
    bl_description = "Un-Shrinkwrap, turn shrinkwrapped decal back into flat one."
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        decals = [obj for obj in context.selected_objects if obj.DM.isdecal]
        return decals and any(get_shrinkwrap(obj) or get_subd(obj) for obj in decals)

    def execute(self, context):
        decals = [obj for obj in context.selected_objects if obj.DM.isdecal]

        for obj in decals:
            unshrinkwrap(obj)

        return {'FINISHED'}
