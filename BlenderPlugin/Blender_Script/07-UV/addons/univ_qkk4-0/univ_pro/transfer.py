# SPDX-FileCopyrightText: 2024 Oxicid
# SPDX-License-Identifier: GPL-3.0-or-later

if 'bpy' in locals():
    from .. import reload
    reload.reload(globals())

import bpy

from .. import utils
from ..utypes import UMeshes, UMesh
from ..operators import checker


class TransferObj:
    def __init__(self, umesh):
        self.umesh: UMesh = umesh
        self.transfer_mod = None
        self.set_border_seam = False
        self.had_checker_modifier = False
        self.first_display_type = self.umesh.obj.display_type
        self.had_uv_layer = bool(umesh.obj.data.uv_layers)
        self._had_checker_modifier()

    def _had_checker_modifier(self):
        for m in self.umesh.obj.modifiers:
            if m.name.startswith('UniV Checker'):
                self.had_checker_modifier = True
                break

    def remove_added_checker(self):
        if not self.had_checker_modifier:
            for m in reversed(self.umesh.obj.modifiers):
                if m.name.startswith('UniV Checker'):
                    self.umesh.obj.modifiers.remove(m)
                    break

    def remove_added_uv_layer(self):
        if not self.had_uv_layer:
            self.umesh.obj.data.uv_layers.remove(self.umesh.obj.data.uv_layers[0])

    def set_bound_display_type(self):
        if self.umesh.obj.display_type != 'BOUNDS':
            self.umesh.obj.display_type = 'BOUNDS'

    def set_textured_display_type(self):
        if self.umesh.obj.display_type != 'TEXTURED':
            self.umesh.obj.display_type = 'TEXTURED'

    def restore_display_type(self):
        if self.umesh.obj.display_type != self.first_display_type:
            self.umesh.obj.display_type = self.first_display_type

    def move_mod_to_first(self):
        assert self.transfer_mod
        mod_idx = 0
        for i, m in enumerate(self.umesh.obj.modifiers):
            if m == self.transfer_mod:
                if i == 0:
                    return
                mod_idx = i
                break

        for i in range(mod_idx):
            try:
                self.umesh.obj.modifiers.move(i, mod_idx)
                return
            except RuntimeError:
                pass

    def add_mod(self, source_obj: UMesh, loop_mapping):
        mod = self.umesh.obj.modifiers.new(name='UniV DataTransfer', type='DATA_TRANSFER')
        mod.object = source_obj.obj
        mod.use_loop_data = True
        mod.data_types_loops = {'UV'}
        mod.loop_mapping = loop_mapping
        self.transfer_mod = mod
        self.umesh.obj.update_tag()

    def remove_mod(self):
        for m in reversed(self.umesh.obj.modifiers):
            if m.name.startswith('UniV DataTransfer'):
                self.umesh.obj.modifiers.remove(m)
        self.transfer_mod = None

    def border_seam(self):
        if self.set_border_seam:
            return

        self.umesh.ensure(face=True)
        if not self.umesh.uv:
            self.umesh.uv = self.umesh.bm.loops.layers.uv.verify()

        uv = self.umesh.uv
        is_pair = utils.is_pair
        for f in self.umesh.bm.faces:
            for crn in f.loops:
                pair = crn.link_loop_radial_prev
                if crn != pair and not is_pair(crn, pair, uv):
                    crn.edge.seam = True
        self.set_border_seam = True
        if not self.umesh.is_edit_bm:
            self.umesh.update()


class UNIV_OT_Transfer(bpy.types.Operator):
    bl_idname = 'mesh.univ_transfer'
    bl_label = 'Transfer'
    bl_options = {'REGISTER', 'UNDO'}

    # noinspection PyTypeHints
    mapping_type: bpy.props.EnumProperty(name='Mapping Type', default='POLYINTERP_NEAREST',
                                         items=(
                                             #  Data Transfer: source mesh data is not ready - dependency cycle?
                                             # ('NEAREST_NORMAL', 'Nearest Normal', ''),  # TODO: Check new in versions
                                             ('POLYINTERP_NEAREST', 'Nearest', ''),
                                             ('POLYINTERP_LNORPROJ', 'Project', ''))
                                         )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.umeshes: UMeshes = UMeshes([])
        self.active_obj = None
        self.source_obj: TransferObj | None = None
        self.transfer_objs: list[TransferObj] = []
        self.distance: float = 0.0
        self.invertible = True
        self._cancel: bool = False

    def invoke(self, context, event):
        self.umeshes = UMeshes.calc(verify_uv=False)
        self.umeshes.active_to_first()
        self.active_obj = context.active_object

        if not self.preprocessing():
            self.umeshes.free()
            return {'CANCELLED'}

        for u in self.umeshes:
            if not u.obj.data.uv_layers:
                u.obj.data.uv_layers.new(do_init=False)

        # Temporary apply checker texture.
        if not self.source_obj.had_checker_modifier or not all(t.had_checker_modifier for t in self.transfer_objs):
            from .. import preferences

            checker.UNIV_OT_Checker.update_views()
            prev_toggle = preferences.prefs().checker_toggle
            preferences.prefs().checker_toggle = 'TOGGLE'
            bpy.ops.mesh.univ_checker()  # noqa
            preferences.prefs().checker_toggle = prev_toggle

        context.area.header_text_set('UniV: 1 - Nearest. 2 - Project. I - Invert. Esc - cancel.')
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
        if event.type not in {'ESC', 'I', 'ONE', 'TWO', 'LEFTMOUSE', 'RIGHTMOUSE', 'ENTER', 'WHEELUPMOUSE', 'WHEELDOWNMOUSE', 'MIDDLEMOUSE'}:
            return {'RUNNING_MODAL'}

        if event.value == 'PRESS':
            match event.type:
                case 'I':
                    if self.invertible:
                        self.source_obj, self.transfer_objs = self.transfer_objs[0], [self.source_obj]
                        self.sourcing()
                        self.transferring()
                    else:
                        self.report({'WARNING'}, f'Unable to invert transfer operation, '
                                                 f'{"no UV-Map" if len(self.umeshes) == 2 else "more than 2 objects selected"}')
                # case 'ONE':
                #     self.mapping_type = 'NEAREST_NORMAL'
                #     for t in self.transfer_objs:
                #         if t.transfer_mod.loop_mapping != self.mapping_type:
                #             t.transfer_mod.loop_mapping = self.mapping_type
                case 'ONE':
                    self.mapping_type = 'POLYINTERP_NEAREST'
                    for t in self.transfer_objs:
                        if t.transfer_mod.loop_mapping != self.mapping_type:
                            t.transfer_mod.loop_mapping = self.mapping_type
                case 'TWO':
                    self.mapping_type = 'POLYINTERP_LNORPROJ'
                    for t in self.transfer_objs:
                        if t.transfer_mod.loop_mapping != self.mapping_type:
                            t.transfer_mod.loop_mapping = self.mapping_type
        match event.type:
            case 'ESC' | 'RIGHTMOUSE':
                self._cancel = True
                return self.exit()
            case 'LEFTMOUSE' | 'ENTER':
                self.apply_transfer_modifier()
                return self.exit()
            case 'WHEELUPMOUSE' | 'WHEELDOWNMOUSE' | 'MIDDLEMOUSE':
                if event.type == 'MIDDLEMOUSE':
                    return {'PASS_THROUGH'}
                elif not any((event.alt, event.ctrl, event.shift)):
                    return {'PASS_THROUGH'}

        context.area.tag_redraw()
        return {'RUNNING_MODAL'}

    def preprocessing(self):
        if not self.umeshes:
            self.report({'WARNING'}, 'Objects not found')
            return False
        elif len(self.umeshes) == 1:
            self.report({'WARNING'}, 'More than 1 mesh object must be selected')
            return False
        elif len(self.umeshes) == 2:
            if not self.umeshes[0].obj.data.uv_layers:
                self.invertible = False
                if not self.umeshes[1].obj.data.uv_layers:
                    self.report({'WARNING'}, 'UV layers not found')
                    return False
                self.umeshes.umeshes.reverse()
            self.source_obj = TransferObj(self.umeshes[0])
            self.transfer_objs = [TransferObj(self.umeshes[1])]
        else:
            self.invertible = False
            if not self.umeshes[0].obj.data.uv_layers:
                self.report({'WARNING'}, 'Active object has not uv')
                return False

            self.source_obj = TransferObj(self.umeshes[0])
            self.transfer_objs = [TransferObj(u) for u in self.umeshes.umeshes[1:]]

        self.sourcing()
        self.transferring()
        return True

    def sourcing(self):
        self.source_obj.remove_mod()
        self.source_obj.set_bound_display_type()
        self.source_obj.border_seam()

    def transferring(self):
        for t in self.transfer_objs:
            t.add_mod(self.source_obj.umesh, self.mapping_type)
            t.move_mod_to_first()
            t.set_textured_display_type()

    def apply_transfer_modifier(self):
        is_edit_mode = bpy.context.mode == 'EDIT_MESH'
        if is_edit_mode:
            bpy.ops.object.editmode_toggle()

        for t in self.transfer_objs:
            bpy.context.view_layer.objects.active = t.umesh.obj
            bpy.ops.object.modifier_apply(modifier=t.transfer_mod.name)

        if is_edit_mode:
            bpy.ops.object.editmode_toggle()
        bpy.context.view_layer.objects.active = self.active_obj

    def exit(self):
        bpy.context.area.header_text_set(None)
        for t in self.transfer_objs:
            if self._cancel:
                t.remove_mod()
                t.remove_added_uv_layer()
            t.remove_added_checker()
        self.source_obj.restore_display_type()
        self.source_obj.remove_added_checker()
        self.umeshes.free()

        for area in utils.get_areas_by_type('VIEW_3D'):
            area.tag_redraw()

        return {'FINISHED'}
