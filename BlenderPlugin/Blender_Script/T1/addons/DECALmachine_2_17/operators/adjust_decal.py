import bpy
from bpy.props import EnumProperty, BoolProperty

import bmesh
from mathutils import Matrix, Vector

from math import radians

from .. utils.decal import set_props_and_node_names_of_decal, set_decalobj_props_from_material, set_decalobj_name, set_defaults, change_panel_width, get_available_panel_decals, ensure_decalobj_versions
from .. utils.material import get_overridegroup, get_parallaxgroup_from_decalmat, get_decalmat, get_decalgroup_from_decalmat, get_decal_texture_nodes, get_panel_material, get_decalgroup_as_dict, has_proper_emission_map, set_decalgroup_from_dict
from .. utils.math import get_loc_matrix, get_rot_matrix, get_sca_matrix
from .. utils.mesh import smooth
from .. utils.modifier import get_displace, get_nrmtransfer
from .. utils.property import set_cycles_visibility, get_cycles_visibility
from .. utils.registration import get_prefs
from .. utils.ui import draw_init, draw_title, draw_prop, init_cursor, popup_message, scroll, scroll_up, wrap_cursor, init_status, finish_status, draw_info, get_keymap_item, update_HUD_location
from .. utils.uv import get_selection_uv_bbox

from .. colors import red
from .. items import adjust_mode_items
from .. import DECALmachineManager as DM

machin3tools = None

class Adjust(bpy.types.Operator):
    bl_idname = "machin3.adjust_decal"
    bl_label = "MACHIN3: Adjust Decal"
    bl_options = {"REGISTER", "UNDO"}
    bl_description = "Adjust Decal Height, Parallax and Various Other Properties"

    mode: EnumProperty(name="Mode", items=adjust_mode_items, default="HEIGHT")
    passthrough: BoolProperty(default=False)
    @classmethod
    def poll(cls, context):
        return any(obj.DM.isdecal for obj in context.selected_objects)

    def draw_HUD(self, context):
        def get_mode_hint_keys(self):
            modehints = []

            if 'HEIGHT' in self.modes:
                modehints.append('Q')

            if 'EMISSION' in self.modes:
                modehints.append('E')

            if 'AO' in self.modes or 'ALPHA' in self.modes:
                modehints.append('A')

            if 'PARALLAX' in self.modes:
                modehints.append('D')

            if 'WIDTH' in self.modes:
                modehints.append('W')

            if 'STRETCH' in self.modes:
                modehints.append('S')

            return modehints

        if context.area == self.area:
            draw_init(self)

            draw_title(self, "Adjust Decals" if len(self.decals) > 1 else "Adjust Decal")

            hint = "switch " + ", ".join(hint_keys) if (hint_keys := get_mode_hint_keys(self)) and len(hint_keys) > 1 else ""
            draw_prop(self, "Mode", self.mode, offset=0, hint=hint, prop_offset=130, hint_offset=280)

            if self.mode == "HEIGHT":
                draw_prop(self, "Δ Height", self.delta_height, decimal=5 if self.is_shift else 3 if self.is_ctrl else 4, offset=18, hint=f"{'ALT ' if get_prefs().adjust_use_alt_height else ''}move LEFT/RIGHT, X to set %0.4f" % (context.scene.DM.height), prop_offset=130, hint_offset=280)

            elif self.mode == "WIDTH":
                draw_prop(self, "Δ Width", self.delta_width + 1, decimal=4 if self.is_shift else 2 if self.is_ctrl else 3, offset=18, hint="move LEFT/RIGHT, X to set 1", prop_offset=130, hint_offset=280)

            elif self.mode == "PARALLAX":
                draw_prop(self, "Δ Amount", self.delta_parallax, decimal=3 if self.is_shift else 1 if self.is_ctrl else 2, offset=18, hint="move LEFT/RIGHT, X to reset", prop_offset=130, hint_offset=280)

            elif self.mode == "AO/ALPHA":
                draw_prop(self, "Δ AO/Alpha", (self.delta_alpha + self.delta_ao) / 2, decimal=3 if self.is_shift else 1 if self.is_ctrl else 2, offset=18, hint="move LEFT/RIGHT, X to set 1, C to set 0/0.5", prop_offset=130, hint_offset=280)

            elif self.mode == "AO":
                draw_prop(self, "Δ AO Strength", self.delta_ao, decimal=3 if self.is_shift else 1 if self.is_ctrl else 2, offset=18, hint="move LEFT/RIGHT, X to set 1, C to set 0", prop_offset=130, hint_offset=280)

            elif self.mode == "ALPHA":
                draw_prop(self, "Δ Alpha", self.delta_alpha, decimal=3 if self.is_shift else 1 if self.is_ctrl else 2, offset=18, hint="move LEFT/RIGHT, X to set 1, C to set 0.5", prop_offset=130, hint_offset=280)

            elif self.mode == "STRETCH":
                draw_prop(self, "Panel UV Stretch", self.delta_stretch + 1, decimal=3 if self.is_shift else 1 if self.is_ctrl else 2, offset=18, hint="move LEFT/RIGHT, X to set 1", prop_offset=130, hint_offset=280)

            elif self.mode == "EMISSION":
                draw_prop(self, "Δ Brightness", self.delta_emit, decimal=2 if self.is_shift else 0 if self.is_ctrl else 1, offset=18, hint="move LEFT/RIGHT, X to set 0, C to set 10", prop_offset=130, hint_offset=280)

            if self.panel_decals:
                self.offset += 18

                if self.cycle_libs:
                    draw_prop(self, "Panel", self.panel_decals[0].active_material.DM.decalname, offset=18, hint="CTRL scroll UP/DOWN", prop_offset=130, hint_offset=280)

                else:
                    draw_info(self, "Found no Panel Decals to cycle through", size=11, HUDcolor=red, HUDalpha=1, offset=18)

            if 'ROTATE' in self.modes:
                self.offset += 18

                draw_prop(self, "Rotate", self.rotate, offset=18, hint="scroll UP/DOWN, SHIFT: 5°, SHIFT + CTRL: 1°", prop_offset=130, hint_offset=280)

            self.offset += 18

            draw_prop(self, "Rotate UVs", self.uvrotate, offset=18, hint="ALT scroll UP/DOWN", prop_offset=130, hint_offset=280)
            draw_prop(self, "Mirror U", self.umirror, offset=18, hint="toggle U", prop_offset=130, hint_offset=280)
            draw_prop(self, "Mirror V", self.vmirror, offset=18, hint="toggle V", prop_offset=130, hint_offset=280)

            self.offset += 18

            if all(get_cycles_visibility(objdata[0], 'glossy') == get_cycles_visibility(self.decals[0][0], 'glossy') for objdata in self.decals):
                state = get_cycles_visibility(self.decals[0][0], 'glossy')
            else:
                state = "Mixed"

            draw_prop(self, "Glossy Rays", state, offset=18, hint="toggle G", prop_offset=130,  hint_offset=280)

            if 'PARALLAX' in self.modes and any(matdata[2] for matdata in self.decaltypemats):
                parallaxmats = [matdata for matdata in self.decaltypemats if matdata[2]]

                if all(matdata[2].mute == parallaxmats[0][2].mute for matdata in parallaxmats):
                    state = not parallaxmats[0][2].mute
                else:
                    state = "Mixed"

                draw_prop(self, "Parallax", state, offset=18, hint="toggle P", prop_offset=130, hint_offset=280)

            if 'INVERT' in self.modes and any(mat[2] is not None for mat in self.decalmats):
                infomats = [matdata for matdata in self.decalmats if matdata[3] is not None]

                if all(matdata[2].inputs['Invert'].default_value == infomats[0][2].inputs['Invert'].default_value for matdata in infomats):
                    state = bool(round(infomats[0][2].inputs['Invert'].default_value))
                else:
                    state = "Mixed"

                draw_prop(self, "Invert", state, offset=18, hint="toggle I", prop_offset=130, hint_offset=280)

            self.offset += 18

            decals = [objdata for objdata in self.decals if objdata[6] is not None]

            if all(objdata[0].data.polygons[0].use_smooth == decals[0][0].data.polygons[0].use_smooth for objdata in decals):
                state = decals[0][0].data.polygons[0].use_smooth
            else:
                state = "Mixed"

            draw_prop(self, "Smooth", state, offset=18, hint="toggle F", prop_offset=130, hint_offset=280)

            if 'NRMTRANSFER' in self.modes:
                if all(objdata[3].show_viewport == self.decals[0][3].show_viewport for objdata in self.decals):
                    state = self.decals[0][3].show_viewport
                else:
                    state = "Mixed"

                draw_prop(self, "Normal Transfer", state, offset=18, hint="toggle N", prop_offset=130, hint_offset=280)

    def modal(self, context, event):
        context.area.tag_redraw()

        self.is_shift = event.shift
        self.is_ctrl = event.ctrl
        self.is_alt = event.alt

        if event.type == "MOUSEMOVE":
            wrap_cursor(self, context, event)
            update_HUD_location(self, event)

        events = ['MOUSEMOVE', 'X', 'C', 'G', 'U', 'V', 'F']

        if 'HEIGHT' in self.modes:
            events.append('Q')

        if 'EMISSION' in self.modes:
            events.append('E')

        if 'AO' in self.modes or 'ALPHA' in self.modes:
            events.append('A')

        if 'PARALLAX' in self.modes:
            events.append('D')
            events.append('P')

        if 'WIDTH' in self.modes:
            events.append('W')

        if 'STRETCH' in self.modes:
            events.append('S')

        if 'INVERT' in self.modes:
            events.append('I')

        if 'NRMTRANSFER' in self.modes:
            events.append('N')

        if event.type in events or scroll(event, key=True):

            if event.type == 'MOUSEMOVE':
                if self.passthrough:
                    self.passthrough = False

                elif not (self.is_alt and event.type in {'LEFTMOUSE', 'RIGHTMOUSE'}):

                    if self.mode == "HEIGHT":
                        divisor = 10000 if self.is_shift else 100 if self.is_ctrl else 1000
                        self.adjust_height(event, divisor)

                    elif self.mode == "WIDTH":
                        divisor = 1000 if self.is_shift else 10 if self.is_ctrl else 100
                        self.adjust_panel_width(event, divisor, context.scene)

                    elif self.mode == "PARALLAX":
                        divisor = 1000 if self.is_shift else 10 if self.is_ctrl else 100
                        self.adjust_parallax(event, divisor)

                    elif self.mode == "AO":
                        divisor = 1000 if self.is_shift else 10 if self.is_ctrl else 100
                        self.adjust_ao(event, divisor)

                    elif self.mode == "ALPHA":
                        divisor = 1000 if self.is_shift else 10 if self.is_ctrl else 100
                        self.adjust_alpha(event, divisor)

                    elif self.mode == "AO/ALPHA":
                        divisor = 1000 if self.is_shift else 10 if self.is_ctrl else 100
                        self.adjust_ao(event, divisor)
                        self.adjust_alpha(event, divisor)

                    elif self.mode == "STRETCH":
                        divisor = 1000 if self.is_shift else 10 if self.is_ctrl else 100
                        self.adjust_panel_uv_stretch(event, divisor)

                    elif self.mode == "EMISSION":
                        divisor = 100 if self.is_shift else 1 if self.is_ctrl else 10
                        self.adjust_emission(event, divisor)

            elif event.type == 'Q' and event.value == "PRESS":
                self.mode = "HEIGHT"

            elif event.type == 'W' and event.value == "PRESS":
                self.mode = "WIDTH"

            elif event.type == 'D' and event.value == "PRESS":
                self.mode = "PARALLAX"

            elif event.type == 'A' and event.value == "PRESS":
                if 'AO' in self.modes and 'ALPHA' in self.modes:
                    self.mode = "AO/ALPHA"

                elif 'AO' in self.modes:
                    self.mode = "AO"

                elif 'ALPHA' in self.modes:
                    self.mode = "ALPHA"

            elif event.type == 'S' and event.value == "PRESS":
                self.mode = "STRETCH"

            elif event.type == 'E' and event.value == "PRESS":
                self.mode = "EMISSION"

            elif event.type == 'X' and event.value == "PRESS":
                if self.mode == "HEIGHT":
                    for obj, displace, init_mid_level, _, _, _, _ in self.decals:
                        if init_mid_level:
                            get_displace(obj).mid_level = context.scene.DM.height
                    self.delta_height = 0

                elif self.mode == "WIDTH":
                    for obj, initbm in self.init_bms:
                        initbm.to_mesh(obj.data)

                    self.delta_width = 0

                elif self.mode == "PARALLAX":
                    for mat, _, pg, _, init_parallax in self.decaltypemats:
                        if init_parallax is not None:
                            pg.inputs[0].default_value = mat.DM.parallaxdefault
                    self.delta_parallax = 0

                elif self.mode == "AO/ALPHA":
                    for mat, _, dg, _, init_alpha, init_ao, _ in self.decalmats:
                        if init_ao is not None:
                            dg.inputs["AO Multiplier"].default_value = 1
                        if init_alpha is not None:
                            dg.inputs["Alpha"].default_value = 1
                    self.delta_ao = 0
                    self.delta_alpha = 0

                elif self.mode == "AO":
                    for mat, _, dg, _, _, init_ao, _ in self.decalmats:
                        if init_ao is not None:
                            dg.inputs["AO Multiplier"].default_value = 1
                    self.delta_ao = 0

                elif self.mode == "ALPHA":
                    for mat, _, dg, _, init_alpha, _, _ in self.decalmats:
                        if init_alpha is not None:
                            dg.inputs["Alpha"].default_value = 1
                    self.delta_alpha = 0

                elif self.mode == "STRETCH":
                    for obj, initbm in self.init_bms:
                        initbm.to_mesh(obj.data)

                    self.delta_stretch = 0

                elif self.mode == "EMISSION":
                    for mat, _, dg, _, _, _, init_emit in self.decalmats:
                        dg.inputs["Emission Multiplier"].default_value = 0
                    self.delta_emit = 0

            elif event.type == 'C' and event.value == "PRESS":
                if self.mode == "AO/ALPHA":
                    for mat, _, dg, _, init_alpha, init_ao, _ in self.decalmats:
                        if init_ao is not None:
                            dg.inputs["AO Multiplier"].default_value = 0
                        if init_alpha is not None:
                            dg.inputs["Alpha"].default_value = 0.5
                    self.delta_ao = 0
                    self.delta_alpha = 0

                if self.mode == "AO":
                    for mat, _, dg, _, _, init_ao, _ in self.decalmats:
                        if init_ao is not None:
                            dg.inputs["AO Multiplier"].default_value = 0
                    self.delta_ao = 0

                elif self.mode == "ALPHA":
                    for mat, _, dg, _, init_alpha, _, _ in self.decalmats:
                        if init_alpha is not None:
                            dg.inputs["Alpha"].default_value = 0.5
                    self.delta_alpha = 0

                elif self.mode == "EMISSION":
                    for mat, _, dg, _, _, _, init_emit in self.decalmats:
                        dg.inputs["Emission Multiplier"].default_value = 10
                    self.delta_emit = 0

            elif event.type in ['U', 'V'] and event.value == "PRESS":
                if event.type == 'U':
                    self.umirror = not self.umirror

                elif event.type == 'V':
                    self.vmirror = not self.vmirror

                self.mirror_uvs()

            elif scroll(event, key=True):

                if scroll_up(event, key=True):

                    if self.is_ctrl and not self.is_alt and not self.is_shift:
                        if self.cycle_libs and self.panel_decals:
                            self.change_panel_decal(context, 1)

                    elif self.is_alt:
                        self.rotate_uvs("CCW")

                    elif 'ROTATE' in self.modes:
                        if self.is_shift and self.is_ctrl:
                            self.rotate += 1
                            rmx = Matrix.Rotation(radians(1), 4, "Z")
                        elif self.is_shift:
                            self.rotate += 5
                            rmx = Matrix.Rotation(radians(5), 4, "Z")
                        else:
                            self.rotate += 45
                            rmx = Matrix.Rotation(radians(45), 4, "Z")

                        for obj, _, _, _, _, _, _ in self.decals:
                            if not obj.DM.issliced and not obj.DM.isprojected:
                                loc, rot, sca = obj.matrix_basis.decompose()
                                obj.matrix_basis = get_loc_matrix(loc) @ get_rot_matrix(rot) @ rmx @ get_sca_matrix(sca)

                else:

                    if self.is_ctrl and not self.is_alt and not self.is_shift:
                        if self.cycle_libs and self.panel_decals:
                            self.change_panel_decal(context, -1)

                    elif self.is_alt:
                        self.rotate_uvs("CW")

                    elif 'ROTATE' in self.modes:
                        if self.is_shift and self.is_ctrl:
                            self.rotate -= 1
                            rmx = Matrix.Rotation(radians(-1), 4, "Z")
                        elif self.is_shift:
                            self.rotate -= 5
                            rmx = Matrix.Rotation(radians(-5), 4, "Z")
                        else:
                            self.rotate -= 45
                            rmx = Matrix.Rotation(radians(-45), 4, "Z")

                        for obj, _, _, _, _, _, _ in self.decals:
                            if not obj.DM.issliced and not obj.DM.isprojected:
                                loc, rot, sca = obj.matrix_basis.decompose()
                                obj.matrix_basis = get_loc_matrix(loc) @ get_rot_matrix(rot) @ rmx @ get_sca_matrix(sca)

            elif event.type == 'G' and event.value == "PRESS":
                state = not get_cycles_visibility(self.decals[0][0], 'glossy')

                for obj, _, _, _, _, _, _ in self.decals:
                    set_cycles_visibility(obj, 'glossy', state)
                    obj.data.update()

            elif event.type == 'P' and event.value == "PRESS":#
                parallaxmats = [matdata for matdata in self.decaltypemats if matdata[2]]
                state = parallaxmats[0][2].mute

                for _, _, pg, _, _ in parallaxmats:
                    pg.mute = not state

            elif event.type == 'I' and event.value == "PRESS":
                infomats = [matdata for matdata in self.decalmats if matdata[3] is not None]
                state = 1 - infomats[0][2].inputs['Invert'].default_value
                for _, _, dg, _, _, _, _ in infomats:
                    dg.inputs["Invert"].default_value = state

            elif event.type == 'F' and event.value == "PRESS":
                self.toggle_shade()

            elif event.type == 'N' and event.value == "PRESS":
                state = not self.decals[0][3].show_viewport

                for obj, _, _, nrmtransfer, init_shownrms, _, _ in self.decals:
                    if init_shownrms is not None:
                        nrmtransfer.show_render = state
                        nrmtransfer.show_viewport = state

        elif event.type in {'MIDDLEMOUSE'} or (self.is_alt_nav and self.is_alt and event.type in {'LEFTMOUSE', 'RIGHTMOUSE'}):
            self.passthrough = True
            return {'PASS_THROUGH'}

        elif event.type in {'LEFTMOUSE', 'SPACE'}:
            self.finish()

            remove_panel_decal_mats = [mat for mat in self.panel_decal_mats.values() if mat.users == 0]
            bpy.data.batch_remove(remove_panel_decal_mats)

            self.report_version_errors()

            return {'FINISHED'}

        elif event.type in {'RIGHTMOUSE', 'ESC'}:
            self.cancel_modal()

            remove_panel_decal_mats = [mat for mat in self.panel_decal_mats.values() if mat.users == 0]
            bpy.data.batch_remove(remove_panel_decal_mats)

            return {'CANCELLED'}

        self.last_mouse_x = event.mouse_x
        self.last_mouse_y = event.mouse_y

        return {"RUNNING_MODAL"}

    def finish(self):
        bpy.types.SpaceView3D.draw_handler_remove(self.HUD, 'WINDOW')

        finish_status(self)

    def cancel_modal(self):
        self.finish()

        for obj, displace, init_mid_level, nrmtransfer, init_shownrms, init_glossy, init_use_smooth in self.decals:
            if init_mid_level:
                displace.mid_level = init_mid_level

            if init_shownrms:
                nrmtransfer.show_render = init_shownrms
                nrmtransfer.show_viewport = init_shownrms

            set_cycles_visibility(obj, 'glossy', init_glossy)

        for mat, init_blend, dg, init_invert, init_alpha, init_ao, init_emit in self.decalmats:
            mat.blend_method = init_blend

            if init_invert:
                dg.inputs["Invert"].default_value = init_invert
            if init_ao:
                dg.inputs["AO Multiplier"].default_value = init_ao
            dg.inputs["Emission Multiplier"].default_value = init_emit

        for mat, dg, pg, init_pmute, init_parallax in self.decaltypemats:

            if init_pmute is not None:
                pg.mute = init_pmute

            if init_parallax:
                pg.inputs[0].default_value = init_parallax

        for obj, initbm in self.init_bms:
            initbm.to_mesh(obj.data)
            initbm.clear()

    def invoke(self, context, event):
        self.dg = context.evaluated_depsgraph_get()

        decals = [obj for obj in context.selected_objects if obj.DM.isdecal]

        current_decals, self.legacy_decals, self.future_decals = ensure_decalobj_versions(decals)

        if current_decals:

            for obj in self.legacy_decals + self.future_decals:
                obj.select_set(False)

            decalmats = {get_decalmat(obj) for obj in current_decals if get_decalmat(obj)}

            decalmatuuids = {mat.DM.uuid for mat in decalmats}

            decaltypemats = {mat for mat in bpy.data.materials if mat.DM.uuid in decalmatuuids}

            self.decals = []

            for obj in current_decals:
                displace = get_displace(obj, create=True)
                midvalue = displace.mid_level

                nrmtransfer = get_nrmtransfer(obj, create=True)
                shownrms = nrmtransfer.show_viewport

                if nrmtransfer.loop_mapping != 'POLYINTERP_LNORPROJ':
                    nrmtransfer.loop_mapping = 'POLYINTERP_LNORPROJ'

                glossy = get_cycles_visibility(obj, 'glossy')

                use_smooth = obj.data.polygons[0].use_smooth if obj.data.polygons else None

                if not use_smooth and nrmtransfer.show_viewport and 'UVTransfer' not in nrmtransfer.name:
                    nrmtransfer.show_viewport = False
                    nrmtransfer.show_render = False

                self.decals.append((obj, displace, midvalue, nrmtransfer, shownrms, glossy, use_smooth))

            self.decalmats = []

            for mat in decalmats:
                blendmethod = mat.blend_method

                decalgroup = get_decalgroup_from_decalmat(mat)

                invert = decalgroup.inputs["Invert"].default_value if mat.DM.decaltype == "INFO" else None
                alpha = decalgroup.inputs["Alpha"].default_value if mat.DM.decaltype == "INFO" else None
                ao = decalgroup.inputs["AO Multiplier"].default_value if mat.DM.decaltype != "INFO" else None
                emit = decalgroup.inputs["Emission Multiplier"].default_value
                self.decalmats.append((mat, blendmethod, decalgroup, invert, alpha, ao, emit))

            self.decaltypemats = []

            for mat in decaltypemats:
                decalgroup = get_decalgroup_from_decalmat(mat)

                parallaxgroup = get_parallaxgroup_from_decalmat(mat) if mat.DM.decaltype in ['SIMPLE', 'SUBSET', 'PANEL'] else None
                parallaxmute = parallaxgroup.mute if parallaxgroup else None
                parallax = parallaxgroup.inputs[0].default_value if parallaxgroup else None
                self.decaltypemats.append((mat, decalgroup, parallaxgroup, parallaxmute, parallax))

            self.init_bms = []

            for obj in current_decals:
                initbm = bmesh.new()
                initbm.from_mesh(obj.data)
                initbm.normal_update()
                initbm.verts.ensure_lookup_table()

                self.init_bms.append((obj, initbm))

            self.panel_decals = [obj for obj in current_decals if obj.DM.decaltype == "PANEL" and get_decalmat(obj)]
            self.panel_decal_mats = {}

            self.cycle_libs = [lib.name for lib in get_prefs().decallibsCOL if (lib.ispanel or lib.istrimsheet) and lib.ispanelcycle]

            self.modes = self.get_adjustment_modes()

            self.delta_height = 0
            self.delta_width = 0
            self.delta_parallax = 0
            self.delta_ao = 0
            self.delta_alpha = 0
            self.delta_stretch = 0
            self.delta_emit = 0
            self.mode = "HEIGHT"
            self.rotate = 0
            self.uvrotate = 0
            self.umirror = False
            self.vmirror = False

            self.is_shift = event.shift
            self.is_ctrl = event.ctrl
            self.is_alt = event.alt

            self.is_alt_nav = get_keymap_item(name="3D View", idname="view3d.rotate", key='LEFTMOUSE', alt=True)

            init_cursor(self, event)

            init_status(self, context, f"Adjust Decal{'s' if len(self.decals) > 1 else ''}")

            self.area = context.area
            self.HUD = bpy.types.SpaceView3D.draw_handler_add(self.draw_HUD, (context, ), "WINDOW", "POST_PIXEL")
            context.window_manager.modal_handler_add(self)
            return {"RUNNING_MODAL"}

        else:
            self.report_version_errors()
            return {'CANCELLED'}

    def report_version_errors(self):
        if self.legacy_decals or self.future_decals:
            msg = ["Adjusting the following decals failed:"]

            if self.legacy_decals:
                for obj in self.legacy_decals:
                    msg.append(f" • {obj.name}")

                msg.append("These are legacy decals, that need to be updated before they can be used!")

            if self.future_decals:
                if self.legacy_decals:
                    msg.append('')

                for obj in self.future_decals:
                    msg.append(f" • {obj.name}")

                msg.append("These are next-gen decals, that can't be used in this Blender version!")

            popup_message(msg)

    def get_adjustment_modes(self):
        modes = set(['HEIGHT'])

        for matdata in self.decalmats:
            mat = matdata[0]

            if has_proper_emission_map(mat):
                modes.add('EMISSION')

            if mat.DM.decaltype in ['SIMPLE', 'SUBSET', 'PANEL']:
                modes.add('AO')

            if mat.DM.decaltype == 'INFO':
                modes.add('ALPHA')
                modes.add('INVERT')

        for matdata in self.decaltypemats:
            if matdata[2]:
                modes.add('PARALLAX')

        for objdata in self.decals:
            decal = objdata[0]

            if decal.DM.decaltype == 'PANEL':
                modes.add('WIDTH')
                modes.add('STRETCH')

            if not decal.DM.isprojected and not decal.DM.issliced:
                modes.add('ROTATE')

            if decal.data.polygons[0].use_smooth:
                modes.add('NRMTRANSFER')

        return modes

    def adjust_height(self, event, divisor):
        if get_prefs().adjust_use_alt_height and not self.is_alt:
            return

        delta_x = event.mouse_x - self.last_mouse_x
        delta_height = delta_x / divisor

        self.delta_height += delta_height

        for obj, displace, init_mid_level, _, _, _, _ in self.decals:
            if init_mid_level is not None:
                displace.mid_level -= delta_height

    def adjust_panel_width(self, event, divisor, scene):
        delta_x = event.mouse_x - self.last_mouse_x
        delta_width = delta_x / divisor

        self.delta_width += delta_width

        for obj, initbm in self.init_bms:
            if obj.DM.issliced:
                bm = initbm.copy()
                bm.verts.ensure_lookup_table()

                change_panel_width(bm, 1 + self.delta_width, panel=obj, scene=scene, set_prop=len(self.panel_decals) == 1)

                bm.to_mesh(obj.data)
                bm.clear()

    def adjust_parallax(self, event, divisor):
        delta_x = event.mouse_x - self.last_mouse_x
        delta_parallax = delta_x / divisor

        self.delta_parallax += delta_parallax

        for mat, _, pg, _, init_parallax in self.decaltypemats:
            if init_parallax is not None:
                amount = pg.inputs[0].default_value
                pg.inputs[0].default_value = max(amount + delta_parallax, 0)
                pg.mute = False

    def adjust_ao(self, event, divisor):
        delta_x = event.mouse_x - self.last_mouse_x
        delta_ao = delta_x / divisor

        self.delta_ao += delta_ao

        for mat, _, dg, _, _, init_ao, _ in self.decalmats:
            if init_ao is not None:
                i = dg.inputs.get('AO Multiplier')

                ao = i.default_value
                newamount = ao + delta_ao

                i.default_value = min(1, max(0, newamount))
    def adjust_alpha(self, event, divisor):
        delta_x = event.mouse_x - self.last_mouse_x
        delta_apha = delta_x / divisor

        self.delta_alpha += delta_apha

        for mat, _, dg, _, init_alpha, _, _ in self.decalmats:
            if init_alpha is not None:
                i = dg.inputs.get('Alpha')

                alpha = i.default_value
                newamount = alpha + delta_apha

                i.default_value = min(1, max(0.01, newamount))
    def adjust_panel_uv_stretch(self, event, divisor):
        delta_x = event.mouse_x - self.last_mouse_x
        delta_stretch = delta_x / divisor

        self.delta_stretch += delta_stretch

        smx = Matrix.Scale(1 + self.delta_stretch, 2, (1, 0)).inverted_safe()

        for obj, initbm in self.init_bms:
            if obj.DM.issliced:
                bm = initbm.copy()
                bm.verts.ensure_lookup_table()

                uvs = bm.loops.layers.uv.active

                for face in bm.faces:
                    for loop in face.loops:
                        loop[uvs].uv = smx @ loop[uvs].uv

                bm.to_mesh(obj.data)
                bm.clear()

    def adjust_emission(self, event, divisor):
        delta_x = event.mouse_x - self.last_mouse_x
        delta_emit = delta_x / divisor

        self.delta_emit += delta_emit

        for mat, _, dg, _, _, _, init_emit in self.decalmats:
                i = get_decalgroup_from_decalmat(mat).inputs["Emission Multiplier"]
                emit = i.default_value
                newamount = emit + delta_emit if emit + delta_emit >= 0 else 0
                i.default_value = newamount

    def toggle_shade(self):
        decals = [objdata for objdata in self.decals if objdata[6] is not None]

        state = not decals[0][0].data.polygons[0].use_smooth

        for objdata in decals:
            obj = objdata[0]
            smooth(obj.data, state)

            if not state and (nrmtransfer := get_nrmtransfer(obj, create=False)) and nrmtransfer.show_viewport and 'UVTransfer' not in nrmtransfer.name:
                nrmtransfer.show_viewport = False
                nrmtransfer.show_render = False

        if state:
            self.modes.add('NRMTRANSFER')
        else:
            self.modes.remove('NRMTRANSFER')

    def rotate_uvs(self, direction):
        self.uvrotate += 90 if direction == "CW" else -90

        rmx = Matrix.Rotation(radians(self.uvrotate), 2, "Z")

        for obj, initbm in self.init_bms:

            if obj.DM.prejoindecals:
                continue

            bm = initbm.copy()
            bm.verts.ensure_lookup_table()

            uvs = bm.loops.layers.uv.active
            loops = [loop for face in bm.faces for loop in face.loops]

            dmid = get_selection_uv_bbox(uvs, loops)[1] if obj.DM.preatlasmats else Vector((0.5, 0.5))

            for loop in loops:
                loop[uvs].uv = dmid + rmx @ (loop[uvs].uv - dmid)

            bm.to_mesh(obj.data)
            bm.clear()

    def mirror_uvs(self):
        for obj, initbm in self.init_bms:

            if obj.DM.prejoindecals and obj.DM.preatlasmats:
                continue

            bm = initbm.copy()
            bm.verts.ensure_lookup_table()

            if any([self.umirror, self.vmirror]):
                uvs = bm.loops.layers.uv.active
                loops = [loop for face in bm.faces for loop in face.loops]

                dmid = get_selection_uv_bbox(uvs, loops)[1] if obj.DM.preatlasmats else Vector((0.5, 0.5))
                mmx = Matrix(((-1 if self.umirror else 1, 0), (0, -1 if self.vmirror else 1)))

                for loop in loops:
                    loop[uvs].uv = dmid + mmx @ (loop[uvs].uv - dmid)

            bm.to_mesh(obj.data)
            bm.clear()

    def change_panel_decal(self, context, direction):
        create_and_connect_bevel_shader_setup = None

        if DM.get_addon('MACHIN3tools'):
            m3 = DM.addons['machin3tools']['module']
            create_and_connect_bevel_shader_setup = m3.utils.material.create_and_connect_bevel_shader_setup

        availablepanels = get_available_panel_decals(cycle_libs=self.cycle_libs)

        currentuuid = self.panel_decals[0].DM.uuid
        currentidx = None

        for idx, panel in enumerate(availablepanels):
            if panel[0] == currentuuid:
                currentidx = idx
                break

        if currentidx is None:
            newidx = 0

        else:
            newidx = currentidx - direction

            if newidx < 0:
                newidx = len(availablepanels) - 1
            elif newidx == len(availablepanels):
                newidx = 0

        newpanel = availablepanels[newidx]

        mat = None
        uuid, name, library = newpanel

        if uuid in self.panel_decal_mats:
            mat = self.panel_decal_mats[uuid]

            for panel in self.panel_decals:
                panel.active_material = mat

                set_decalobj_props_from_material(panel, mat)
                set_decalobj_name(panel, decalname=mat.DM.decalname, uuid=uuid)

            context.window_manager.paneldecals = uuid

        else:
            mat, appended, _, _ = get_panel_material(context, uuid)

            if mat:
                self.panel_decal_mats[uuid] = mat

                if appended:
                    set_props_and_node_names_of_decal(library, name, decalobj=None, decalmat=mat)

                    set_defaults(decalmat=mat)
                for panel in self.panel_decals:
                    old_mat = panel.active_material

                    mat.blend_method = old_mat.blend_method

                    set_decalobj_props_from_material(panel, mat)

                    if mat.DM.decaltype != 'INFO' and old_mat.DM.decaltype != 'INFO':

                        old_dg = get_decalgroup_from_decalmat(old_mat)

                        if old_dg:
                            material, material2, subset = get_decalgroup_as_dict(old_dg)

                            dg = get_decalgroup_from_decalmat(mat)

                            if dg:

                                if mat.DM.decaltype == 'SIMPLE':
                                    material2 = None
                                    subset = None
                                elif mat.DM.decaltype == 'SUBSET':
                                    material2 = None

                                set_decalgroup_from_dict(dg, material, material2, subset)

                                mat.DM.ismatched = old_mat.DM.ismatched
                                mat.DM.matchedmaterialto = old_mat.DM.matchedmaterialto
                                mat.DM.matchedmaterial2to = old_mat.DM.matchedmaterial2to
                                mat.DM.matchedsubsetto = old_mat.DM.matchedsubsetto

                                dm = bpy.context.scene.DM
                                override = dm.material_override

                                if override:
                                    old_og = get_overridegroup(old_mat)

                                    if old_og:
                                        og = get_overridegroup(mat)

                                        if not og:
                                            tree = mat.node_tree

                                            og = tree.nodes.new(type='ShaderNodeGroup')
                                            og.width = 250
                                            og.location.x -= 200
                                            og.location.y += 500
                                            og.node_tree = override
                                            og.name = 'DECALMACHINE_OVERRIDE'

                                            override_decalmat_components = ['Material', 'Material 2']

                                            if dm.material_override_decal_subsets:
                                                override_decalmat_components.append('Subset')

                                            for output in og.outputs:
                                                for inputprefix in override_decalmat_components:
                                                    if inputprefix == 'Subset' and mat.DM.decaltype not in ['SUBSET', 'PANEL']:
                                                        continue

                                                    elif inputprefix == 'Material 2' and mat.DM.decaltype != 'PANEL':
                                                        continue

                                                    i = dg.inputs.get(f"{inputprefix} {output.name}")

                                                    if i:
                                                        tree.links.new(output, i)

                                                if dm.coat == 'UNDER' and not dm.material_override_decal_subsets:
                                                    if mat.DM.decaltype in ['SUBSET', 'PANEL'] and output.name.startswith('Coat '):
                                                        i = dg.inputs.get(f"Subset {output.name}")

                                                        if i:
                                                            tree.links.new(output, i)

                                            if dm.material_override_decal_emission:
                                                decal_texture_nodes = get_decal_texture_nodes(mat)

                                                emission = decal_texture_nodes.get('EMISSION')

                                                if emission:
                                                    emission.mute = True

                                if machin3tools and create_and_connect_bevel_shader_setup:
                                    m3 = context.scene.M3

                                    if m3.use_bevel_shader:

                                        old_tree = old_mat.node_tree
                                        old_bevel = old_tree.nodes.get('MACHIN3tools Bevel')

                                        if old_bevel:
                                            normal_inputs = [dg.inputs[f"{comp} {name}"] for name in ['Normal', 'Coat Normal'] for comp in ['Material', 'Material 2', 'Subset']]

                                            if normal_inputs:
                                                bevel, global_radius = create_and_connect_bevel_shader_setup(mat, dg, normal_inputs, decalmachine=True)

                                                bevel.samples = m3.bevel_shader_samples
                                                bevel.inputs[0].default_value = m3.bevel_shader_radius
                                                global_radius.outputs[0].default_value = m3.bevel_shader_radius

                    panel.active_material = mat

                    set_decalobj_name(panel, decalname=mat.DM.decalname, uuid=uuid)

                context.window_manager.paneldecals = uuid
