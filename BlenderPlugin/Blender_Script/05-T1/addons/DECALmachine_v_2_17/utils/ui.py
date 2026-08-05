import bpy
from bpy_extras.view3d_utils import location_3d_to_region_2d
import blf
import rna_keymap_ui
from bl_ui.space_statusbar import STATUSBAR_HT_header as statusbar
from . registration import get_prefs
from .. colors import yellow

from time import time

def get_icon(name):
    from .. import DECALmachineManager as MM

    if icon := MM.icons.get(name, None):
        return icon.icon_id
    else:
        return 45 if bpy.app.version >= (4, 5, 0) else 42

def init_cursor(self, event, offsetx=0, offsety=20):
    self.last_mouse_x = event.mouse_x
    self.last_mouse_y = event.mouse_y

    self.region_offset_x = event.mouse_x - event.mouse_region_x
    self.region_offset_y = event.mouse_y - event.mouse_region_y

    self.HUD_x = event.mouse_x - self.region_offset_x + offsetx
    self.HUD_y = event.mouse_y - self.region_offset_y + offsety

def wrap_cursor(self, context, event):

    if event.mouse_region_x <= 0:
        context.window.cursor_warp(context.region.width + self.region_offset_x - 10, event.mouse_y)

    if event.mouse_region_x >= context.region.width - 1:  # the -1 is required for full screen, where the max region width is never passed
        context.window.cursor_warp(self.region_offset_x + 10, event.mouse_y)

    if event.mouse_region_y <= 0:
        context.window.cursor_warp(event.mouse_x, context.region.height + self.region_offset_y - 10)

    if event.mouse_region_y >= context.region.height - 1:
        context.window.cursor_warp(event.mouse_x, self.region_offset_y + 100)

def warp_cursor_to_object_origin(context, event, obj):
    region_offset_x = event.mouse_x - event.mouse_region_x
    region_offset_y = event.mouse_y - event.mouse_region_y

    loc, _, _ = obj.matrix_world.decompose()
    co = location_3d_to_region_2d(context.region, context.space_data.region_3d, loc, default=None)
    context.window.cursor_warp(round(co.x + region_offset_x), round(co.y + region_offset_y))

def update_HUD_location(self, event, offsetx=0, offsety=20):
    self.HUD_x = event.mouse_x - self.region_offset_x + offsetx
    self.HUD_y = event.mouse_y - self.region_offset_y + offsety

def draw_init(self):
    self.font_id = 1
    self.offset = 0

def draw_title(self, title, subtitle=None, subtitleoffset=125, HUDcolor=None, HUDalpha=0.5, shadow=True):
    if not HUDcolor:
        HUDcolor = get_prefs().modal_hud_color
    shadow = (0, 0, 0)

    scale = bpy.context.preferences.system.ui_scale * get_prefs().modal_hud_scale

    if shadow:
        blf.color(self.font_id, *shadow, HUDalpha * 0.7)
        blf.position(self.font_id, self.HUD_x - 7 + 1, self.HUD_y - 1, 0)
        blf.size(self.font_id, int(20 * scale))
        blf.draw(self.font_id, "• " + title)

    blf.color(self.font_id, *HUDcolor, HUDalpha)
    blf.position(self.font_id, self.HUD_x - 7, self.HUD_y, 0)
    blf.size(self.font_id, int(20 * scale))
    blf.draw(self.font_id, "» " + title)

    if subtitle:
        if shadow:
            blf.color(self.font_id, *shadow, HUDalpha / 2 * 0.7)
            blf.position(self.font_id, self.HUD_x - 7 + int(subtitleoffset * scale), self.HUD_y, 0)
            blf.size(self.font_id, int(15 * scale))
            blf.draw(self.font_id, subtitle)

        blf.color(self.font_id, *HUDcolor, HUDalpha / 2)
        blf.position(self.font_id, self.HUD_x - 7 + int(subtitleoffset * scale), self.HUD_y, 0)
        blf.size(self.font_id, int(15 * scale))
        blf.draw(self.font_id, subtitle)

def draw_prop(self, name, value, offset=0, decimal=2, active=True, HUDcolor=None, prop_offset=120, hint="", hint_offset=200, shadow=True):
    if not HUDcolor:
        HUDcolor = get_prefs().modal_hud_color
    shadow = (0, 0, 0)

    if active:
        alpha = 1
    else:
        alpha = 0.4

    scale = bpy.context.preferences.system.ui_scale * get_prefs().modal_hud_scale

    offset = self.offset + int(offset * scale)
    self.offset = offset

    if shadow:
        blf.color(self.font_id, *shadow, alpha * 0.7)
        blf.position(self.font_id, self.HUD_x + int(20 * scale) + 1, self.HUD_y - int(20 * scale) - offset - 1, 0)
        blf.size(self.font_id, int(11 * scale))
        blf.draw(self.font_id, name)

    blf.color(self.font_id, *HUDcolor, alpha)
    blf.position(self.font_id, self.HUD_x + int(20 * scale), self.HUD_y - int(20 * scale) - offset, 0)
    blf.size(self.font_id, int(11 * scale))
    blf.draw(self.font_id, name)

    if type(value) is str:
        if shadow:
            blf.color(self.font_id, *shadow, alpha * 0.7)
            blf.position(self.font_id, self.HUD_x + int(prop_offset * scale) + 1, self.HUD_y - int(20 * scale) - offset - 1, 0)
            blf.size(self.font_id, int(14 * scale))
            blf.draw(self.font_id, value)

        color = yellow if value == 'Mixed' else HUDcolor

        blf.color(self.font_id, *color, alpha)
        blf.position(self.font_id, self.HUD_x + int(prop_offset * scale), self.HUD_y - int(20 * scale) - offset, 0)
        blf.size(self.font_id, int(14 * scale))
        blf.draw(self.font_id, value)

    elif type(value) is bool:
        if shadow:
            blf.color(self.font_id, *shadow, alpha * 0.7)
            blf.position(self.font_id, self.HUD_x + int(prop_offset * scale) + 1, self.HUD_y - int(20 * scale) - offset - 1, 0)
            blf.size(self.font_id, int(14 * scale))
            blf.draw(self.font_id, str(value))

        if value:
            blf.color(self.font_id, 0.5, 1, 0.5, alpha)
        else:
            blf.color(self.font_id, 1, 0.3, 0.3, alpha)

        blf.position(self.font_id, self.HUD_x + int(prop_offset * scale), self.HUD_y - int(20 * scale) - offset, 0)
        blf.size(self.font_id, int(14 * scale))
        blf.draw(self.font_id, str(value))

    elif type(value) is int:
        if shadow:
            blf.color(self.font_id, *shadow, alpha * 0.7)
            blf.position(self.font_id, self.HUD_x + int(prop_offset * scale) + 1, self.HUD_y - int(20 * scale) - offset - 1, 0)
            blf.size(self.font_id, int(20 * scale))
            blf.draw(self.font_id, "%d" % (value))

        blf.color(self.font_id, *HUDcolor, alpha)
        blf.position(self.font_id, self.HUD_x + int(prop_offset * scale), self.HUD_y - int(20 * scale) - offset, 0)
        blf.size(self.font_id, int(20 * scale))
        blf.draw(self.font_id, "%d" % (value))

    elif type(value) is float:
        if shadow:
            blf.color(self.font_id, *shadow, alpha * 0.7)
            blf.position(self.font_id, self.HUD_x + int(prop_offset * scale) + 1, self.HUD_y - int(20 * scale) - offset - 1, 0)
            blf.size(self.font_id, int(16 * scale))
            blf.draw(self.font_id, "%.*f" % (decimal, value))

        blf.color(self.font_id, *HUDcolor, alpha)
        blf.position(self.font_id, self.HUD_x + int(prop_offset * scale), self.HUD_y - int(20 * scale) - offset, 0)
        blf.size(self.font_id, int(16 * scale))
        blf.draw(self.font_id, "%.*f" % (decimal, value))

    if get_prefs().modal_hud_hints and hint:
        if shadow:
            blf.color(self.font_id, *shadow, 0.6 * 0.7)
            blf.position(self.font_id, self.HUD_x + int(hint_offset * scale) + 1, self.HUD_y - int(20 * scale) - offset - 1, 0)
            blf.size(self.font_id, int(11 * scale))
            blf.draw(self.font_id, "%s" % (hint))

        blf.color(self.font_id, *HUDcolor, 0.6)
        blf.position(self.font_id, self.HUD_x + int(hint_offset * scale), self.HUD_y - int(20 * scale) - offset, 0)
        blf.size(self.font_id, int(11 * scale))
        blf.draw(self.font_id, "%s" % (hint))

def draw_info(self, text, size, offset=0, HUDcolor=None, HUDalpha=0.5, shadow=True):
    if not HUDcolor:
        HUDcolor = get_prefs().modal_hud_color
    shadow = (0, 0, 0)

    scale = bpy.context.preferences.system.ui_scale * get_prefs().modal_hud_scale

    offset = self.offset + int(offset * scale)
    self.offset = offset

    if shadow:
        blf.color(self.font_id, *shadow, HUDalpha * 0.7)
        blf.position(self.font_id, self.HUD_x + int(20 * scale) + 1, self.HUD_y - int(20 * scale) - offset - 1, 0)
        blf.size(self.font_id, int(size * scale))
        blf.draw(self.font_id, text)

    blf.color(self.font_id, *HUDcolor, HUDalpha)
    blf.position(self.font_id, self.HUD_x + int(20 * scale), self.HUD_y - int(20 * scale) - offset, 0)
    blf.size(self.font_id, int(size * scale))
    blf.draw(self.font_id, text)

def draw_text(self, text, x, y, size=11, offsetx=0, offsety=0, HUDcolor=None, HUDalpha=0.5, shadow=True):
    if not HUDcolor:
        HUDcolor = get_prefs().modal_hud_color
    shadow = (0, 0, 0)

    scale = bpy.context.preferences.system.ui_scale * get_prefs().modal_hud_scale

    if shadow:
        blf.color(self.font_id, *shadow, HUDalpha * 0.7)
        blf.position(self.font_id, x - offsetx * size * scale, y - 1 - offsety * size * scale, 0)
        blf.size(self.font_id, int(size * scale))
        blf.draw(self.font_id, text)

    blf.color(self.font_id, *HUDcolor, HUDalpha)
    blf.position(self.font_id, x - offsetx * size * scale, y - offsety * size * scale, 0)
    blf.size(self.font_id, int(size * scale))
    blf.draw(self.font_id, text)

def popup_message(message, title="Info", icon="INFO", terminal=True):
    def draw_message(self, context):
        if isinstance(message, list):
            for m in message:
                self.layout.label(text=m)
        else:
            self.layout.label(text=message)

    bpy.context.window_manager.popup_menu(draw_message, title=title, icon=icon)

    if terminal:
        if icon == "FILE_TICK":
            icon = "ENABLE"
        elif icon == "CANCEL":
            icon = "DISABLE"
        print(icon, title)

        if isinstance(message, list):
            print(" •", ", ".join(message))
        else:
            print(" •", message)

def draw_pil_warning(layout, needed="for decal creation"):
    if get_prefs().pil:
        pass

    elif get_prefs().pilrestart:
        box = layout.box()
        column = box.column()

        row = column.row(align=True)
        row.alignment = 'CENTER'
        row.label(text="PIL has been installed.", icon='INFO')

        row = column.row(align=True)
        row.alignment = 'CENTER'
        row.label(text="Restart Blender now.")

    else:
        box = layout.box()
        column = box.column()

        row = column.row(align=True)
        row.alignment = 'CENTER'
        row.label(text=f"PIL is needed {needed}.", icon_value=get_icon('error'))

        row = column.row(align=True)
        row.alignment = 'CENTER'
        row.label(text="Internet connection required.")

        column.operator("machin3.install_pil", text="Install PIL", icon="PREFERENCES")

def get_panel_fold(layout, idname, text='', icon='NONE', custom_icon=None, align=True, default_closed=True):
    header, panel = layout.panel(idname=idname, default_closed=default_closed)
    header.active = bool(panel)

    if custom_icon:
        header.label(text=text, icon_value=get_icon(custom_icon))
    else:
        header.label(text=text, icon=icon)

    return panel.column(align=align) if panel else None

def init_status(self, context, title='', func=None):
    self.bar_orig = statusbar.draw

    if func:
        statusbar.draw = func
    else:
        statusbar.draw = draw_basic_status(self, context, title)

def draw_basic_status(self, context, title):
    def draw(self, context):
        layout = self.layout

        row = layout.row(align=True)
        row.label(text=title)

        row.label(text="", icon='MOUSE_LMB')
        row.label(text="Finish")

        if context.window_manager.keyconfigs.active.name.startswith('blender'):
            row.label(text="", icon='MOUSE_MMB')
            row.label(text="Viewport")

        row.label(text="", icon='MOUSE_RMB')
        row.label(text="Cancel")

    return draw

def finish_status(self):
    statusbar.draw = self.bar_orig

def get_keymap_item(name, idname, key, alt=False, ctrl=False, shift=False, properties=[]):
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.user

    km = kc.keymaps.get(name)

    alt = int(alt)
    ctrl = int(ctrl)
    shift = int(shift)

    if km:
        kmi = km.keymap_items.get(idname)

        if kmi:
            if all([kmi.type == key and kmi.alt is alt and kmi.ctrl is ctrl and kmi.shift is shift]):

                if properties:
                    if all([getattr(kmi.properties, name, False) == prop for name, prop in properties]):
                        return kmi
                else:
                    return kmi
    return False

def draw_keymap_items(kc, name, keylist, layout):
    drawn = []

    idx = 0

    for item in keylist:
        keymap = item.get("keymap")
        isdrawn = False

        if keymap:
            km = kc.keymaps.get(keymap)

            kmi = None
            if km:
                idname = item.get("idname")

                for kmitem in km.keymap_items:
                    if kmitem.idname == idname:
                        properties = item.get("properties")

                        if properties:
                            if all([getattr(kmitem.properties, name, None) == value for name, value in properties]):
                                kmi = kmitem
                                break

                        else:
                            kmi = kmitem
                            break

            if kmi:
                if idx == 0:
                    box = layout.box()

                if len(keylist) == 1:
                    label = name.title().replace("_", " ")

                else:
                    if idx == 0:
                        box.label(text=name.title().replace("_", " "))

                    label = item.get("label")

                row = box.split(factor=0.15)
                row.label(text=label)

                rna_keymap_ui.draw_kmi(["ADDON", "USER", "DEFAULT"], kc, km, kmi, row, 0)

                infos = item.get("info", [])
                for text in infos:
                    row = box.split(factor=0.15)
                    row.separator()
                    row.label(text=text, icon="INFO")

                isdrawn = True
                idx += 1

        drawn.append(isdrawn)
    return drawn

def init_prefs(context):
    if context.preferences.edit.use_enter_edit_mode:
        context.preferences.edit.use_enter_edit_mode = False

def draw_version_warning(layout, version):
    if bpy.app.version < version:
        from .. import bl_info

        b3d_version = '.'.join([str(i) for i in version])
        addon_version = '.'.join([str(i) for i in bl_info['version']])

        layout.separator(factor=10)
        row = layout.row()
        row.alignment = 'CENTER'
        row.label(text=f"Official Support for Blender versions older than {str(b3d_version)} LTS has ended. Please update Blender to ensure DECALmachine {addon_version} works reliably.", icon_value=get_icon('error'))
        layout.separator(factor=10)

def init_timer_modal(self, debug=False):
    self.start = time()

    self.countdown = self.time * get_prefs().modal_hud_timeout

    if debug:
        print(f"initiating timer with a countdown of {self.time}s ({self.time * get_prefs().modal_hud_timeout}s)")

def set_countdown(self, debug=False):
    self.countdown = self.time * get_prefs().modal_hud_timeout - (time() - self.start)

    if debug:
        print("countdown:", self.countdown)

def get_timer_progress(self, debug=False):
    progress =  self.countdown / (self.time * get_prefs().modal_hud_timeout)

    if debug:
        print("progress:", progress)

    return progress

def scroll(event, wheel=True, pad=True, key=False):
    return scroll_up(event, wheel=wheel, pad=pad, key=key) or scroll_down(event, wheel=wheel, pad=pad, key=key)

def scroll_up(event, wheel=True, pad=True, key=False):

    if pad and event.type == 'TRACKPADPAN' and event.mouse_y > event.mouse_prev_y and event.mouse_y - event.mouse_prev_y >= 5:
        return True

    elif event.value == 'PRESS':

        if wheel and event.type == 'WHEELUPMOUSE':
            return True

        if key and event.type in ['ONE', 'UP_ARROW', 'PLUS', 'NUMPAD_PLUS']:
            return True

    return False

def scroll_down(event, wheel=True, pad=True, key=False):

    if pad and event.type == 'TRACKPADPAN' and event.mouse_y < event.mouse_prev_y and event.mouse_prev_y - event.mouse_y >= 5:
        return True

    elif event.value == 'PRESS':

        if wheel and event.type == 'WHEELDOWNMOUSE':
            return True

        if key and event.type in ['TWO', 'DOWN_ARROW', 'MINUS', 'NUMPAD_MINUS']:
            return True

    return False
