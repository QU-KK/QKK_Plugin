import bpy
from .blender import preferences, ui_scale, panel, collapse_panels
from .draw.draw_text import DrawText
from .draw.draw_2d import Draw2D
from .draw.draw_3d import Draw3D


class Overlay(DrawText, Draw2D, Draw3D):
    def update_data(self, data):
        self.prefs = preferences()
        if self.pause_modal:
            background = list(bpy.context.preferences.themes["Default"].user_interface.wcol_tool.inner[:])
            background[-1] = 0.5
            self.v3d_item_background = tuple(background)

            background_sel = list(bpy.context.preferences.themes["Default"].user_interface.wcol_tool.inner_sel[:])
            background_sel[-1] = 0.5
            self.v3d_item_background_sel = tuple(background_sel)

            # self.v3d_item_background = bpy.context.preferences.themes['Default'].user_interface.wcol_tool.inner
            # self.v3d_item_background_sel = bpy.context.preferences.themes['Default'].user_interface.wcol_tool.inner_sel
            self.v3d_text_color = bpy.context.preferences.themes["Default"].user_interface.wcol_tool.text
            self.v3d_text_sel = bpy.context.preferences.themes["Default"].user_interface.wcol_tool.text_sel
        else:
            self.v3d_item_background = bpy.context.preferences.themes["Default"].user_interface.wcol_tool.inner
            self.v3d_item_background_sel = bpy.context.preferences.themes["Default"].user_interface.wcol_tool.inner_sel
            self.v3d_text_color = bpy.context.preferences.themes["Default"].user_interface.wcol_tool.text
            self.v3d_text_sel = bpy.context.preferences.themes["Default"].user_interface.wcol_tool.text_sel
        d = [(icon, title, None) for icon, title in data[0:1]]
        for l in data[1:]:
            label, prop = l[0:2]
            value = l[-1]
            active = True if prop == self.modal_action or prop == True else None
            if active and self.input:
                value = self.input
            d.append((label, value, active))
        return d

    def draw_data(self, obj, data):
        text = self.update_data(data)
        x_offset = 0
        gap = 32 * ui_scale()
        p = [10 * ui_scale(), 8 * ui_scale()]
        margin = 30 + (p[1])
        s = " : "
        line_height = round(self.get_text_dims("M")[1])
        for key, value, active in text[0:1]:
            if len(value) == 0:
                max_icon_width = 16 * ui_scale()
            else:
                max_icon_width = self.get_text_dims(s + value)[0] + 16 * ui_scale()
        listToStr = "".join(str(elem[0] + s + elem[1]) for elem in text[1:])
        max_width = self.get_text_dims(listToStr)[0] + max_icon_width
        x = bpy.context.region.width / 2 - (max_width + (gap * len(text) - gap)) / 2
        y = margin
        th = line_height
        for key, value, active in text[0:1]:
            if len(value) != 0:
                max_title_width = self.get_text_dims(value)[0] + 24 * ui_scale() + gap
                tw = self.get_text_dims(value)[0] + 24 * ui_scale()
                if active:
                    self.draw_box((x, y), (tw, th), p, self.v3d_item_background_sel)
                    self.draw_text((x + 24 * ui_scale(), y), value, self.v3d_text_sel)
                else:
                    self.draw_box((x, y), (tw, th), p, self.v3d_item_background)
                    self.draw_text((x + 24 * ui_scale(), y), value, self.v3d_text_color)
            else:
                max_title_width = self.get_text_dims(value)[0] + 16 * ui_scale() + gap
                tw = self.get_text_dims(value)[0] + 16 * ui_scale()
                if active:
                    self.draw_box((x, y), (tw, th), p, self.v3d_item_background_sel)
                    self.draw_text((x + 16 * ui_scale(), y), value, self.v3d_text_sel)
                else:
                    self.draw_box((x, y), (tw, th), p, self.v3d_item_background)
                    self.draw_text((x + 16 * ui_scale(), y), value, self.v3d_text_color)
            self.draw_image((x, y - 4 * ui_scale()), key)
        for key, value, active in text[1:]:
            if len(value) != 0:
                tw = self.get_text_dims(key + s + value)[0]
                if active:
                    self.draw_box(
                        ((x + x_offset) + max_title_width, y),
                        (tw, th),
                        p,
                        self.v3d_item_background_sel,
                    )
                    self.draw_text(
                        ((x + x_offset) + max_title_width, y),
                        key + s + value,
                        self.v3d_text_sel,
                    )
                else:
                    self.draw_box(
                        ((x + x_offset) + max_title_width, y),
                        (tw, th),
                        p,
                        self.v3d_item_background,
                    )
                    self.draw_text(
                        ((x + x_offset) + max_title_width, y),
                        key + s + value,
                        self.v3d_text_color,
                    )
            else:
                tw = self.get_text_dims(key)[0]
                if active:
                    self.draw_box(
                        ((x + x_offset) + max_title_width, y),
                        (tw, th),
                        p,
                        self.v3d_item_background_sel,
                    )
                    self.draw_text(((x + x_offset) + max_title_width, y), key, self.v3d_text_sel)
                else:
                    self.draw_box(
                        ((x + x_offset) + max_title_width, y),
                        (tw, th),
                        p,
                        self.v3d_item_background,
                    )
                    self.draw_text(((x + x_offset) + max_title_width, y), key, self.v3d_text_color)
            x_offset += tw + gap
        bpy.context.window_manager.screencast_offset_center = th + p[1] * 3

    def draw_keymaps(self, obj, keymaps, global_keymaps=None):
        self.prefs = preferences()
        if self.pause_modal:
            background = list(bpy.context.preferences.themes["Default"].user_interface.wcol_tool.inner[:])
            background[-1] = 0.5
            self.v3d_item_background = tuple(background)

            background_sel = list(bpy.context.preferences.themes["Default"].user_interface.wcol_tool.inner_sel[:])
            background_sel[-1] = 0.5
            self.v3d_item_background_sel = tuple(background_sel)

            # self.v3d_item_background = bpy.context.preferences.themes['Default'].user_interface.wcol_tool.inner
            # self.v3d_item_background_sel = bpy.context.preferences.themes['Default'].user_interface.wcol_tool.inner_sel
            self.v3d_text_color = bpy.context.preferences.themes["Default"].user_interface.wcol_tool.text
            self.v3d_text_sel = bpy.context.preferences.themes["Default"].user_interface.wcol_tool.text_sel
        else:
            self.v3d_item_background = bpy.context.preferences.themes["Default"].user_interface.wcol_tool.inner
            self.v3d_item_background_sel = bpy.context.preferences.themes["Default"].user_interface.wcol_tool.inner_sel
            self.v3d_text_color = bpy.context.preferences.themes["Default"].user_interface.wcol_tool.text
            self.v3d_text_sel = bpy.context.preferences.themes["Default"].user_interface.wcol_tool.text_sel
        y_offset = 0
        line_height = round(self.get_text_dims("M")[1])
        p = [10 * ui_scale(), 8 * ui_scale()]
        margin = 30 + (p[1])
        s = "  •  "
        gap_width = self.get_text_dims(s)[0]
        global_keymap_width = self.get_text_dims("SHIFT + H" + s + "Global")[0]

        if global_keymaps is None:
            key_list = []
            key_dict = {}
            value_list = []
            value_dict = {}
            for keymap in keymaps:
                key, prop = keymap[0:2]
                value = keymap[-1]
                if hasattr(obj, prop):
                    if obj.rna_type.properties[prop].type == "BOOLEAN":
                        if len(value) != 0:
                            value = keymap[-1]
                        else:
                            value = obj.rna_type.properties[prop].name
                key_list.append(len(key))
                key_dict[key] = len(key)
                value_list.append(len(s + value))
                value_dict[s + value] = len(s + value)
            for key, value in key_dict.items():
                if value == max(key_list):
                    max_title_width = self.get_text_dims(key)[0]
            for key, value in value_dict.items():
                if value == max(value_list):
                    max_value_width = self.get_text_dims(key)[0]
            max_width = max_title_width + max_value_width + gap_width

        else:
            if self.prefs.overlay.show_global_keymaps:
                key_list = []
                key_dict = {}
                value_list = []
                value_dict = {}
                for keymap in global_keymaps:
                    key, prop = keymap[0:2]
                    value = keymap[-1]
                    if hasattr(obj, prop):
                        if obj.rna_type.properties[prop].type == "BOOLEAN":
                            if len(value) != 0:
                                value = keymap[-1]
                            else:
                                value = obj.rna_type.properties[prop].name
                    key_list.append(len(key))
                    key_dict[key] = len(key)
                    value_list.append(len(s + value))
                    value_dict[s + value] = len(s + value)
                for key, value in key_dict.items():
                    if value == max(key_list):
                        max_title_width = self.get_text_dims(key)[0]
                for key, value in value_dict.items():
                    if value == max(value_list):
                        max_value_width = self.get_text_dims(key)[0]
                max_width = max_title_width + max_value_width + gap_width
            else:
                key_list = []
                key_dict = {}
                value_list = []
                value_dict = {}
                for keymap in keymaps:
                    key, prop = keymap[0:2]
                    value = keymap[-1]
                    if hasattr(obj, prop):
                        if obj.rna_type.properties[prop].type == "BOOLEAN":
                            if len(value) != 0:
                                value = keymap[-1]
                            else:
                                value = obj.rna_type.properties[prop].name
                    key_list.append(len(key))
                    key_dict[key] = len(key)
                    value_list.append(len(s + value))
                    value_dict[s + value] = len(s + value)
                for key, value in key_dict.items():
                    if value == max(key_list):
                        max_title_width = self.get_text_dims(key)[0]
                for key, value in value_dict.items():
                    if value == max(value_list):
                        max_value_width = self.get_text_dims(key)[0]
                max_width = max_title_width + max_value_width + gap_width

        if global_keymap_width > max_width:
            max_width = global_keymap_width

        x = bpy.context.region.width - (max_width + margin + panel("UI")[0])
        y = margin
        if self.prefs.overlay.show_keymaps:
            p = [10 * ui_scale(), 8 * ui_scale()]
            tw = max_width
            if global_keymaps is None:
                th = (line_height * len(keymaps)) + (p[0] * len(keymaps) - p[0])

                # self.draw_box((x, y+th+p[0]*2), (tw, line_height), p, self.v3d_item_background)
                # self.draw_text((x, y+th+p[0]*2), 'H'+s+'Help', self.v3d_text_color)

                self.draw_box((x, y), (tw, th), p, self.v3d_item_background)
                for keymap in reversed(keymaps):
                    key, prop = keymap[0:2]
                    value = keymap[-1]
                    if hasattr(obj, prop):
                        if obj.rna_type.properties[prop].type == "BOOLEAN":
                            self.draw_text((x, (y + y_offset)), key, self.v3d_text_color)
                            self.draw_text(
                                (x + max_title_width, (y + y_offset)),
                                s,
                                self.v3d_text_color,
                            )
                            self.draw_checkbox(
                                (
                                    x + max_title_width + gap_width,
                                    (y + y_offset) - (3 * ui_scale()),
                                ),
                                default=getattr(obj, prop),
                            )
                            if value:
                                self.draw_text(
                                    (
                                        x + max_title_width + gap_width * 2,
                                        (y + y_offset),
                                    ),
                                    value,
                                    self.v3d_text_color,
                                )
                            else:
                                self.draw_text(
                                    (
                                        x + max_title_width + gap_width * 2,
                                        (y + y_offset),
                                    ),
                                    obj.rna_type.properties[prop].name,
                                    self.v3d_text_color,
                                )
                    else:
                        self.draw_text((x, (y + y_offset)), key, self.v3d_text_color)
                        self.draw_text(
                            (x + max_title_width, (y + y_offset)),
                            s,
                            self.v3d_text_color,
                        )
                        self.draw_text(
                            (x + max_title_width + gap_width, (y + y_offset)),
                            value,
                            self.v3d_text_color,
                        )
                    y_offset += line_height + p[0]
                bpy.context.window_manager.screencast_offset_right = th + p[1] * 3
            else:
                if self.prefs.overlay.show_global_keymaps:
                    th = (line_height * len(global_keymaps)) + (p[0] * len(global_keymaps) - p[0])

                    self.draw_box(
                        (x, y + th + p[0] * 2),
                        (tw, line_height),
                        p,
                        self.v3d_item_background,
                    )
                    self.draw_text(
                        (x, y + th + p[0] * 2),
                        "SHIFT + H" + s + "Local",
                        self.v3d_text_color,
                    )

                    self.draw_box((x, y), (tw, th), p, self.v3d_item_background)
                    for keymap in reversed(global_keymaps):
                        key, prop = keymap[0:2]
                        value = keymap[-1]
                        if hasattr(obj, prop):
                            if obj.rna_type.properties[prop].type == "BOOLEAN":
                                self.draw_text((x, (y + y_offset)), key, self.v3d_text_color)
                                self.draw_text(
                                    (x + max_title_width, (y + y_offset)),
                                    s,
                                    self.v3d_text_color,
                                )
                                self.draw_checkbox(
                                    (
                                        x + max_title_width + gap_width,
                                        (y + y_offset) - (3 * ui_scale()),
                                    ),
                                    default=getattr(obj, prop),
                                )
                                if value:
                                    self.draw_text(
                                        (
                                            x + max_title_width + gap_width * 2,
                                            (y + y_offset),
                                        ),
                                        value,
                                        self.v3d_text_color,
                                    )
                                else:
                                    self.draw_text(
                                        (
                                            x + max_title_width + gap_width * 2,
                                            (y + y_offset),
                                        ),
                                        obj.rna_type.properties[prop].name,
                                        self.v3d_text_color,
                                    )
                        else:
                            self.draw_text((x, (y + y_offset)), key, self.v3d_text_color)
                            self.draw_text(
                                (x + max_title_width, (y + y_offset)),
                                s,
                                self.v3d_text_color,
                            )
                            self.draw_text(
                                (x + max_title_width + gap_width, (y + y_offset)),
                                value,
                                self.v3d_text_color,
                            )
                        y_offset += line_height + p[0]
                    bpy.context.window_manager.screencast_offset_right = y + th + (p[1] * 2) * ui_scale()
                else:
                    th = (line_height * len(keymaps)) + (p[0] * len(keymaps) - p[0])

                    self.draw_box(
                        (x, y + th + p[0] * 2),
                        (tw, line_height),
                        p,
                        self.v3d_item_background,
                    )
                    self.draw_text(
                        (x, y + th + p[0] * 2),
                        "SHIFT + H" + s + "Global",
                        self.v3d_text_color,
                    )

                    self.draw_box((x, y), (tw, th), p, self.v3d_item_background)
                    for keymap in reversed(keymaps):
                        key, prop = keymap[0:2]
                        value = keymap[-1]
                        if hasattr(obj, prop):
                            if obj.rna_type.properties[prop].type == "BOOLEAN":
                                self.draw_text((x, (y + y_offset)), key, self.v3d_text_color)
                                self.draw_text(
                                    (x + max_title_width, (y + y_offset)),
                                    s,
                                    self.v3d_text_color,
                                )
                                self.draw_checkbox(
                                    (
                                        x + max_title_width + gap_width,
                                        (y + y_offset) - (3 * ui_scale()),
                                    ),
                                    default=getattr(obj, prop),
                                )
                                if value:
                                    self.draw_text(
                                        (
                                            x + max_title_width + gap_width * 2,
                                            (y + y_offset),
                                        ),
                                        value,
                                        self.v3d_text_color,
                                    )
                                else:
                                    self.draw_text(
                                        (
                                            x + max_title_width + gap_width * 2,
                                            (y + y_offset),
                                        ),
                                        obj.rna_type.properties[prop].name,
                                        self.v3d_text_color,
                                    )
                        else:
                            self.draw_text((x, (y + y_offset)), key, self.v3d_text_color)
                            self.draw_text(
                                (x + max_title_width, (y + y_offset)),
                                s,
                                self.v3d_text_color,
                            )
                            self.draw_text(
                                (x + max_title_width + gap_width, (y + y_offset)),
                                value,
                                self.v3d_text_color,
                            )
                        y_offset += line_height + p[0]
                    bpy.context.window_manager.screencast_offset_right = y + th + (p[1] * 2) * ui_scale()
        else:
            tw = self.get_text_dims("H" + s + "Help")[0]
            x = bpy.context.region.width - (tw + margin + panel("UI")[0])
            self.draw_box((x, y), (tw, line_height), p, self.v3d_item_background)
            self.draw_text((x, y), "H", self.v3d_text_color)
            self.draw_text((x + self.get_text_dims("H")[0], y), s + "Help", self.v3d_text_color)
            bpy.context.window_manager.screencast_offset_right = line_height + (p[1] * 3)

    def draw_modifiers(self):
        y_offset = 0
        line_height = round(self.get_text_dims("M")[1])
        p = (10 * ui_scale(), 8 * ui_scale())
        text = []
        for mod in bpy.context.object.modifiers:
            index = bpy.context.object.modifiers.find(mod.name)
            icon = mod.type
            if mod.type in {
                "MESH_SEQUENCE_CACHE",
                "LAPLACIANDEFORM",
                "MESH_DEFORM",
                "SURFACE_DEFORM",
            }:
                icon = "MESH_CACHE"
            elif mod.type in {"NORMAL_EDIT"}:
                icon = "WEIGHTED_NORMAL"
            elif mod.type in {"UV_WARP"}:
                icon = "UV_PROJECT"
            elif mod.type in {
                "VERTEX_WEIGHT_EDIT",
                "VERTEX_WEIGHT_MIX",
                "VERTEX_WEIGHT_PROXIMITY",
            }:
                icon = "VERTEX_WEIGHT"
            elif mod.type in {"CORRECTIVE_SMOOTH", "LAPLACIANSMOOTH"}:
                icon = "SMOOTH"
            text.append([index, icon, mod.name, mod.is_active, mod.show_viewport])
        margin = 30 + (p[1])
        s = "  :  "
        list = []
        dict = {}
        for line in text:
            index, key, value = line[0:3]
            index = str(index)
            list.append(len(index + s + value))
            dict[index + s + value] = len(index + s + value)
            max_title_width = self.get_text_dims(index)[0]
            max_gap_width = self.get_text_dims(s)[0]
            max_value_width = self.get_text_dims(value)[0]
        for key, value in dict.items():
            if value == max(list):
                max_width = self.get_text_dims(key)[0] + 24 * ui_scale()
        x = margin + panel("TOOLS")[0]
        y = margin
        tw = max_width + 28 * ui_scale()
        if self.prefs.overlay.show_modifiers:
            if len(text) == 1:
                th = line_height
                for index, icon, value, active, viewport in reversed(text):
                    index = str(index)
                    if active:
                        self.draw_box((x, y), (tw, th), p, self.v3d_item_background_sel)
                    else:
                        self.draw_box((x, y), (tw, th), p, self.v3d_item_background)

                    self.draw_text((x, y), index + s, self.v3d_text_sel)
                    self.draw_image((x + max_title_width + max_gap_width, y - 4 * ui_scale()), icon)
                    self.draw_text(
                        (x + max_title_width + max_gap_width + 24 * ui_scale(), y),
                        value,
                        self.v3d_text_sel,
                    )
                    if viewport:
                        self.draw_image(
                            (x + max_width + 12 * ui_scale(), y - 4 * ui_scale()),
                            "RESTRICT_VIEW_ON",
                        )
                    else:
                        self.draw_image(
                            (x + max_width + 12 * ui_scale(), y - 4 * ui_scale()),
                            "RESTRICT_VIEW_OFF",
                        )
                bpy.context.window_manager.screencast_offset_left = th + p[1] * 3
            else:
                th = (line_height * len(text)) + (p[1] * len(text) * 2) - p[1] * 2 + 2
                y = margin - 1
                self.draw_box((x, y), (tw, th), p, self.v3d_item_background)
                for index, icon, value, active, viewport in reversed(text):
                    index = str(index)
                    if active:
                        line_width = bpy.context.preferences.system.ui_line_width
                        if bpy.context.object.modifiers.find(self.act_mod.name) == 0:
                            self.selected(
                                (x + line_width, (margin + y_offset)),
                                (tw - line_width * 2, line_height),
                                p,
                                corner=[False, False, True, True],
                            )
                        elif bpy.context.object.modifiers.find(self.act_mod.name) == len(bpy.context.object.modifiers) - 1:
                            self.selected(
                                (x + line_width, (margin + y_offset)),
                                (tw - line_width * 2, line_height),
                                p,
                                corner=[True, True, False, False],
                            )
                        else:
                            self.selected(
                                (x + line_width, (margin + y_offset)),
                                (tw - line_width * 2, line_height),
                                p,
                                corner=[False, False, False, False],
                            )
                        self.draw_text((x, (y + y_offset)), index, self.v3d_text_sel)
                        self.draw_text((x + max_title_width, (y + y_offset)), s, self.v3d_text_sel)
                        self.draw_text(
                            (
                                x + max_title_width + max_gap_width + 24 * ui_scale(),
                                (y + y_offset),
                            ),
                            value,
                            self.v3d_text_sel,
                        )
                    else:
                        self.draw_text((x, (y + y_offset)), index, self.v3d_text_color)
                        self.draw_text((x + max_title_width, (y + y_offset)), s, self.v3d_text_sel)
                        self.draw_text(
                            (
                                x + max_title_width + max_gap_width + 24 * ui_scale(),
                                (y + y_offset),
                            ),
                            value,
                            self.v3d_text_color,
                        )
                    self.draw_image(
                        (
                            x + max_title_width + max_gap_width,
                            (y + y_offset) - 4 * ui_scale(),
                        ),
                        icon,
                    )
                    if viewport:
                        self.draw_image(
                            (
                                x + max_width + 12 * ui_scale(),
                                (y + y_offset) - 4 * ui_scale(),
                            ),
                            "RESTRICT_VIEW_ON",
                        )
                    else:
                        self.draw_image(
                            (
                                x + max_width + 12 * ui_scale(),
                                (y + y_offset) - 4 * ui_scale(),
                            ),
                            "RESTRICT_VIEW_OFF",
                        )
                    y_offset += line_height + (p[1] * 2)
                bpy.context.window_manager.screencast_offset_left = th + p[1] * 3
        else:
            s = "  •  "
            tw = self.get_text_dims("SHIFT + M" + s + "Modifiers")[0]
            x = margin + panel("TOOLS")[0]
            self.draw_box((x, y), (tw, line_height), p, self.v3d_item_background)
            self.draw_text((x, y), "SHIFT + M", self.v3d_text_color)
            self.draw_text(
                (x + self.get_text_dims("SHIFT + M")[0], y),
                s + "Modifiers",
                self.v3d_text_color,
            )

    def draw_2d(self, context, overlay):
        args = (context,)
        self._2d_handle = bpy.types.SpaceView3D.draw_handler_add(overlay, args, "WINDOW", "POST_PIXEL")
        self.original_t_panel, self.original_n_panel = collapse_panels()

    def draw_3d(self, context, overlay):
        args = (context,)
        self._3d_handle = bpy.types.SpaceView3D.draw_handler_add(overlay, args, "WINDOW", "POST_VIEW")

    def exit(self, context):
        context.window.cursor_modal_restore()
        bpy.types.SpaceView3D.draw_handler_remove(self._2d_handle, "WINDOW")
        bpy.types.SpaceView3D.draw_handler_remove(self._3d_handle, "WINDOW")
        context.object.show_wire = False
        collapse_panels(self.original_t_panel, self.original_n_panel)
        bpy.context.window_manager.screencast_offset_left = 0
        bpy.context.window_manager.screencast_offset_center = 0
        bpy.context.window_manager.screencast_offset_right = 0

    def exit_2d(self, context):
        context.window.cursor_modal_restore()
        bpy.types.SpaceView3D.draw_handler_remove(self._2d_handle, "WINDOW")
        context.object.show_wire = False
        collapse_panels(self.original_t_panel, self.original_n_panel)
        bpy.context.window_manager.screencast_offset_left = 0
        bpy.context.window_manager.screencast_offset_center = 0
        bpy.context.window_manager.screencast_offset_right = 0

    def exit_3d(self, context):
        context.window.cursor_modal_restore()
        bpy.types.SpaceView3D.draw_handler_remove(self._3d_handle, "WINDOW")
        context.object.show_wire = False
        bpy.context.window_manager.screencast_offset_left = 0
        bpy.context.window_manager.screencast_offset_center = 0
        bpy.context.window_manager.screencast_offset_right = 0
