import bpy
from bpy.props import  BoolProperty, FloatProperty, IntProperty
import os
from time import time
from . import bl_info
from . utils.registration import get_path, get_name, get_addon
from . utils.draw import draw_split_row, draw_fading_label
from . utils.ui import get_keymap_item, draw_keymap_items, get_icon
from . registration import keys as keysdict
from . colors import green, yellow

decalmachine = None
meshmachine = None
machin3tools = None
punchit = None
hypercursor = None

thankyou_time = None

class CURVEmachinePreferences(bpy.types.AddonPreferences):
    path = get_path()
    bl_idname = get_name()

    registration_debug: BoolProperty(name="Addon Terminal Registration Output", default=True)

    blendulate_segment_count: IntProperty(name="Blendulate default Segment Count", description="Use this many Segments, when invoking Blendulate with a single Point selection", default=6, min=0)

    show_sidebar_panel: BoolProperty(name="Show Sidebar Panel", default=True)

    show_curve_split: BoolProperty(name="Show Curve Split tool", default=True)
    show_delete: BoolProperty(name="Show Delete Menu", default=True)
    show_in_curve_context_menu: BoolProperty(name="Show in Edit Curve Context Menu", default=False)

    modal_hud_scale: FloatProperty(name="HUD Scale", default=1, min=0.5, max=10)
    modal_hud_timeout: FloatProperty(name="HUD Timeout", description="Modulate duration of fading HUD elements", default=1, min=0.1, max=10)

    update_available: BoolProperty()

    def draw(self, context):
        layout = self.layout

        self.draw_thank_you(layout)

        global decalmachine, meshmachine, machin3tools, punchit, hypercursor

        if decalmachine is None:
            decalmachine = get_addon('DECALmachine')[0]

        if meshmachine is None:
            meshmachine = get_addon('MESHmachine')[0]

        if machin3tools is None:
            machin3tools = get_addon('MACHIN3tools')[0]

        if punchit is None:
            punchit = get_addon('PUNCHit')[0]

        if hypercursor is None:
            hypercursor = get_addon('HyperCursor')[0]

        menu_keymap = get_keymap_item('Curve', 'wm.call_menu', properties=[('name', 'MACHIN3_MT_curve_machine')], iterate=True)

        column = layout.column(align=True)
        box = column.box()

        split = box.split()

        b = split.box()

        bb = b.box()
        bb.label(text="Addon")

        column = bb.column()
        draw_split_row(self, column, prop='registration_debug', label='Print Addon Registration Output in System Console')

        bb = b.box()
        bb.label(text="General")

        column = bb.column(align=True)

        draw_split_row(self, column, prop='blendulate_segment_count', label='Blendulate Default Segment Count')

        bb = b.box()
        bb.label(text="Menu")

        column = bb.column()

        draw_split_row(self, column, prop='show_in_curve_context_menu', label="Show CURVEmachine in Blender's Edit Curve Context Menu")

        if menu_keymap.type in ['Y', 'X']:
            if menu_keymap.type == 'Y':
                draw_split_row(self, column, prop='show_curve_split', label='Show Curve Split Tool', info='Because the Y key is used for the Menu')

            else:
                draw_split_row(self, column, prop='show_delete', label='Show Delete Tool', info='Because the X key is used for the Menu')

        bb = b.box()
        bb.label(text="HUD")

        column = bb.column()

        draw_split_row(self, column, prop='modal_hud_scale', label='Modal HUD SCale Sidebar Panel')
        draw_split_row(self, column, prop='modal_hud_timeout', label='Timeout', info='Modulate Duration of Fading HUDs')

        bb = b.box()
        bb.label(text="3D View")

        column = bb.column(align=True)

        draw_split_row(self, column, prop='show_sidebar_panel', label='Show Sidebar Panel')

        b = split.box()

        b.label(text="Keymaps")

        wm = bpy.context.window_manager
        kc = wm.keyconfigs.user

        draw_keymap_items(kc, 'Curve', keysdict['MENU'], b)
        draw_keymap_items(kc, 'Curve', keysdict['BLEND'], b)
        draw_keymap_items(kc, 'Curve', keysdict['MERGE'], b, skip_box_label=True)

        column = layout.column(align=True)
        box = column.box()
        box.label(text="Support")

        column = box.column()
        row = column.row()
        row.scale_y = 1.5
        row.operator('machin3.get_curvemachine_support', text='Get Support', icon='GREASEPENCIL')

        column = layout.column(align=True)
        box = column.box()
        box.label(text="About")

        column = box.column(align=True)
        row = column.row(align=True)

        row.scale_y = 1.5
        row.operator("wm.url_open", text='CURVEmachine', icon='CURVE_DATA').url = 'https://machin3.io/CURVEmachine/'
        row.operator("wm.url_open", text='Documentation', icon='INFO').url = 'https://machin3.io/CURVEmachine/docs'
        row.operator("wm.url_open", text='MACHINƎ.io', icon='WORLD').url = 'https://machin3.io'
        row.operator("wm.url_open", text='blenderartists', icon_value=get_icon('blenderartists')).url = 'https://blenderartists.org/t/curvemachine/1467375'

        row = column.row(align=True)
        row.scale_y = 1.5
        row.operator("wm.url_open", text='Patreon', icon_value=get_icon('patreon')).url = 'https://patreon.com/machin3'
        row.operator("wm.url_open", text='Twitter', icon_value=get_icon('twitter')).url = 'https://twitter.com/machin3io'
        row.operator("wm.url_open", text='Youtube', icon_value=get_icon('youtube')).url = 'https://www.youtube.com/c/MACHIN3/'
        row.operator("wm.url_open", text='Artstation', icon_value=get_icon('artstation')).url = 'https://www.artstation.com/machin3'

        column.separator()

        row = column.row(align=True)
        row.scale_y = 1.5
        row.operator("wm.url_open", text='DECALmachine', icon_value=get_icon('save' if decalmachine else 'cancel_grey')).url = 'https://decal.machin3.io'
        row.operator("wm.url_open", text='MESHmachine', icon_value=get_icon('save' if meshmachine else 'cancel_grey')).url = 'https://mesh.machin3.io'
        row.operator("wm.url_open", text='MACHIN3tools', icon_value=get_icon('save' if machin3tools else 'cancel_grey')).url = 'https://machin3.io/MACHIN3tools'
        row.operator("wm.url_open", text='PUNCHit', icon_value=get_icon('save' if punchit else 'cancel_grey')).url = 'https://machin3.io/PUNCHit'
        row.operator("wm.url_open", text='HyperCursor', icon_value=get_icon('save' if hypercursor else 'cancel_grey')).url = 'https://www.youtube.com/playlist?list=PLcEiZ9GDvSdWs1w4ZrkbMvCT2R4F3O9yD'

    def draw_thank_you(self, layout):
        global thankyou_time

        message = [f"Thank you for purchasing {bl_info['name']}!",
                   "",
                   "Your support allows me to keep developing this addon and future ones, keeps updates free for everyone, and most importantly enables me to provide for my family.",
                   f"If you haven't purchased {bl_info['name']}, please consider doing so."]

        if thankyou_time is None:
            thankypou_path = os.path.join(get_path(), 'thank_you')

            if not os.path.exists(thankypou_path):
                thankyou_time = time()
                msg = message + ['', str(thankyou_time)]

                with open(thankypou_path, mode='w') as f:
                    f.write('\n'.join(m for m in msg))

            else:
                with open(thankypou_path) as f:
                    lines = [l[:-1] for l in f.readlines()]

                try:
                    thankyou_time = float(lines[-1])
                except:
                    os.unlink(thankypou_path)

        if thankyou_time:
            draw_message = False
            message_lifetime = 5

            if isinstance(thankyou_time, float):
                deltatime = (time() - thankyou_time) / 60
                draw_message = deltatime < message_lifetime

            else:
                draw_message = True
                deltatime = 'X'

            if draw_message:

                b = layout.box()
                b.label(text="Thank You!", icon='INFO')

                col = b.column()

                for i in range(2):
                    col.separator()

                for line in message:
                    if line:
                        col.label(text=line)
                    else:
                        col.separator()

                for i in range(3):
                    col.separator()

                col.label(text=f"This message will self-destruct in {message_lifetime - deltatime:.1f} minutes.", icon='SORTTIME')

                for i in range(3):
                    col.separator()

                col.label(text=f"If you have purchased {bl_info['name']} and find this nag-screen annoying, I appologize.")
                col.label(text=f"If you have haven't purchased {bl_info['name']} and find this nag-screen annoying, go fuck yourself.")
