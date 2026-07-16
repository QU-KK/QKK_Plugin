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

# Copyright 2023, Alex Zhornyak, alexander.zhornyak@gmail.com

import bpy

import urllib.error
import urllib.request
import ssl
import os
import shutil
from zipfile import ZipFile
from io import BytesIO
from timeit import default_timer as timer

from ZenUV.utils.blender_zen_utils import ZenPolls, ZuvPresets
from ZenUV.utils.tests.system_operators import ZUV_OT_OpenPresetsFolder
from ZenUV.utils.vlog import Log


class ZuvDemoExample(bpy.types.PropertyGroup):
    url: bpy.props.StringProperty(
        name='URL',
        default=''
    )

    url_details: bpy.props.StringProperty(
        name='URL Details',
        description='Url that is called by pressing "More Info" button',
        default=''
    )

    description: bpy.props.StringProperty(
        name='Description',
        default=''
    )

    category: bpy.props.StringProperty(
        name='Category',
        default=''
    )

    file_path: bpy.props.StringProperty(
        name='File Path',
        default=''
    )

    is_link: bpy.props.BoolProperty(
        name='Link',
        description='Url is the link to external web resource',
        default=False
    )

    def get_url_github_name(self):
        s_res = self.name.lower()
        s_res = s_res.replace(' ', '-')
        return s_res

    def get_preset_folder(self):
        if self.name:
            s_preset_path = ZuvPresets.force_full_preset_path(ZUV_DemoExampleProps.PRESETS_DIR)
            return os.path.join(s_preset_path, self.name)
        return ''

    def update_file_path(self):
        self.file_path = ''
        s_preset_folder = self.get_preset_folder()
        if s_preset_folder and os.path.exists(s_preset_folder):
            for file in os.listdir(s_preset_folder):
                s_file_path = os.path.join(s_preset_folder, file)
                if os.path.isfile(s_file_path):
                    if s_file_path.lower().endswith('.blend'):
                        self.file_path = s_file_path
                        break


class ZUV_UL_DemoExampleList(bpy.types.UIList):
    ''' Zen Trimsheet Groups UIList '''
    def draw_item(self, context, layout: bpy.types.UILayout, data, item: ZuvDemoExample, icon, active_data, active_propname, index):
        ''' @Draw Trimsheet Groups UIList '''
        # act_idx = getattr(active_data, active_propname)
        # b_active = index == act_idx

        row = layout.row()

        s_folder = item.get_preset_folder()
        b_folder_exists = os.path.exists(s_folder)

        row.alert = b_folder_exists and not os.path.exists(item.file_path)

        r1 = row.row(align=True)
        r1.active = b_folder_exists or item.is_link
        r1.prop(item, 'name', text='', emboss=False)
        r1.prop(item, 'category', text='', emboss=False)

        # DEBUG
        # row.prop(item, 'url', text='', emboss=False)

        r2 = row.row(align=True)
        r2.alignment = 'RIGHT'

        if not item.is_link and b_folder_exists:
            op = r2.operator('wm.open_mainfile', text='', icon='FILE_BLEND')
            op.filepath = item.file_path
            op.display_file_selector = False
        else:
            if item.is_link:
                op = r2.operator('wm.url_open', text='', icon='URL')
                op.url = item.url
            else:
                op = r2.operator(
                    'wm.zuv_demo_examples_download', text='',
                    icon='IMPORT')
                op.idx = index


class ZUV_DemoExampleProps(bpy.types.PropertyGroup):

    CONFIG_URL = 'https://raw.githubusercontent.com/zen-masters/Zen-UV/master/examples/README.md'

    DETAILS_URL = 'https://github.com/zen-masters/Zen-UV/tree/master/examples'

    PRESETS_DIR = 'demo_examples'

    examples: bpy.props.CollectionProperty(name='Examples', type=ZuvDemoExample)

    example_index: bpy.props.IntProperty(
        name='Active Example Index',
        description='Active index of the current example',
        default=-1,
        min=-1
    )

    def draw(self, layout: bpy.types.UILayout, context: bpy.types.Context):
        row = layout.row(align=False)
        row_l = row.row(align=False)
        row_l.alignment = 'LEFT'
        row_l.label(text='Examples')
        row_r = row.row(align=False)
        row_r.alignment = 'RIGHT'
        ot = row_r.operator(
            ZUV_OT_OpenPresetsFolder.bl_idname,
            icon=ZUV_OT_OpenPresetsFolder.get_icon_name(),
            text='')
        ot.preset_folder = ZUV_DemoExampleProps.PRESETS_DIR

        if ZenPolls.version_since_4_2_0:
            if not context.preferences.system.use_online_access:
                row = layout.row(align=True)
                row.operator("extensions.userpref_show_online", icon='INTERNET_OFFLINE', text="Online Access Disabled")

        row = layout.row(align=False)
        r1 = row.row(align=False)
        r1.alignment = 'LEFT'
        r1.operator('wm.zuv_demo_examples_update', text='Update', icon='FILE_REFRESH')

        p_example = self.get_active_example()
        if p_example:

            s_folder = p_example.get_preset_folder()
            b_folder_exists = os.path.exists(s_folder)
            if not p_example.is_link and b_folder_exists:
                if os.path.exists(p_example.file_path):
                    op = r1.operator('wm.open_mainfile', icon='FILE_BLEND')
                    op.filepath = p_example.file_path
                    op.display_file_selector = False
            else:
                if p_example.is_link:
                    op = r1.operator('wm.url_open', text='Open Website', icon='URL')
                    op.url = p_example.url
                else:
                    op = r1.operator(
                        'wm.zuv_demo_examples_download',
                        icon='IMPORT')
                    op.idx = self.example_index

            r2 = row.row(align=True)
            r2.alignment = 'RIGHT'
            r2.enabled = b_folder_exists
            op = r2.operator(ZUV_OT_DemoExamplesDelete.bl_idname, text='', icon='TRASH')
            op.idx = self.example_index

        row = layout.row()
        col = row.column()
        col.template_list(
            "ZUV_UL_DemoExampleList",
            "name",
            self,
            "examples",
            self,
            "example_index",
            rows=2
        )

        if p_example:
            t_description = p_example.description.split('\n')
            if t_description:
                box = layout.box()

                col = box.column(align=True)

                for line in t_description:
                    col.label(text=line)

                row = box.row(align=True)
                row.alignment = 'RIGHT'
                op = row.operator('wm.url_open', text='More Info', icon='INFO')

                op.url = p_example.url_details if p_example.url_details else f'{self.DETAILS_URL}#{p_example.get_url_github_name()}'

    def get_example(self, idx: int) -> ZuvDemoExample:
        if idx in range(0, len(self.examples)):
            return self.examples[idx]
        return None

    def get_active_example(self) -> ZuvDemoExample:
        return self.get_example(self.example_index)


class ZUV_OT_DemoExamplesUpdate(bpy.types.Operator):
    bl_idname = "wm.zuv_demo_examples_update"
    bl_label = 'Update Examples'
    bl_description = 'Update list of demo examples'
    bl_options = {'REGISTER', 'UNDO'}

    LITERAL_LAST_UPDATE = 'zenuv_last_examples_update'

    @classmethod
    def poll(cls, context: bpy.types.Context):
        return ZenPolls.internet_enabled()

    def execute(self, context: bpy.types.Context):
        from ZenUV.prop.zuv_preferences import get_prefs
        addon_prefs = get_prefs()

        def plain_description(t_description):
            out = []
            for line in t_description:
                if line.startswith('#### '):
                    break
                out.append(line)
            return out

        try:
            ssl_context = ssl._create_unverified_context()
            with urllib.request.urlopen(addon_prefs.demo.CONFIG_URL, context=ssl_context) as f:
                config = f.read().decode('utf-8')  # type: str

                t_lines = config.split('\n')


                urls = {item.url: item for item in addon_prefs.demo.examples}

                valid_urls = set()

                category = ''
                name = ''
                t_description = []

                url = None

                for line in t_lines:
                    if line.startswith('## '):
                        category = line.replace('## ', '').strip()
                    elif line.startswith('### '):
                        name = line.replace('### ', '').strip()
                        t_description = []
                    elif line.startswith('[//]: # ('):
                        url = line.replace('[//]: # (', '').strip()
                        url = url.replace(')', '')

                        if url not in urls:
                            addon_prefs.demo.examples.add()
                            addon_prefs.demo.example_index = len(addon_prefs.demo.examples) - 1

                            urls[url] = addon_prefs.demo.examples[-1]
                        else:
                            pass

                        urls[url].name = name
                        urls[url].category = category
                        urls[url].url = url
                        urls[url].url_details = ''
                        urls[url].is_link = False
                        urls[url].update_file_path()
                        urls[url].description = '\n'.join(plain_description(t_description))

                        valid_urls.add(url)

                        name = ''
                        t_description = []
                    elif line.startswith('[comment]: # ('):
                        url = line.replace('[comment]: # (', '').strip()
                        url = url.replace(')', '')

                        if url not in urls:
                            addon_prefs.demo.examples.add()
                            addon_prefs.demo.example_index = len(addon_prefs.demo.examples) - 1

                            urls[url] = addon_prefs.demo.examples[-1]
                        else:
                            pass

                        urls[url].name = name
                        urls[url].category = category
                        urls[url].url = url
                        urls[url].url_details = ''
                        urls[url].is_link = True
                        urls[url].description = '\n'.join(plain_description(t_description))

                        valid_urls.add(url)

                        name = ''
                        t_description = []
                    elif line.startswith('[more_info]: # ('):
                        url_details = line.replace('[more_info]: # (', '').strip()
                        url_details = url_details.replace(')', '')

                        if url in urls:
                            urls[url].url_details = url_details
                    else:
                        if name:
                            if line:
                                t_description.append(line)

                for idx in range(len(addon_prefs.demo.examples) - 1, -1, -1):
                    item = addon_prefs.demo.examples[idx]
                    if item.url not in valid_urls:
                        if item.is_link or not os.path.exists(item.get_preset_folder()):
                            addon_prefs.demo.examples.remove(idx)

                context.preferences.is_dirty = True

                context.area.tag_redraw()

                bpy.app.driver_namespace[self.LITERAL_LAST_UPDATE] = timer()

                return {'FINISHED'}
        except urllib.error.URLError as e:
            self.report({'ERROR'}, "Can not update! Check internet connection! Error details: " + str(e))
        except Exception as e:
            self.report({'ERROR'}, str(e))

        bpy.app.driver_namespace[self.LITERAL_LAST_UPDATE] = timer()

        return {'CANCELLED'}


class ZUV_OT_DemoExamplesDownload(bpy.types.Operator):
    bl_idname = "wm.zuv_demo_examples_download"
    bl_label = 'Download Example'
    bl_description = 'Download example by given index'
    bl_options = {'INTERNAL'}

    idx: bpy.props.IntProperty(
        name='Example Index',
        default=-1
    )

    @classmethod
    def poll(cls, context: bpy.types.Context):
        return ZenPolls.internet_enabled()

    def execute(self, context: bpy.types.Context):
        from ZenUV.prop.zuv_preferences import get_prefs
        addon_prefs = get_prefs()

        try:
            p_example = addon_prefs.demo.get_example(self.idx)  # type: ZuvDemoExample
            if p_example is not None:
                s_preset_folder = p_example.get_preset_folder()
                if s_preset_folder:
                    ssl_context = ssl._create_unverified_context()
                    with urllib.request.urlopen(p_example.url, context=ssl_context) as zipresp:
                        with ZipFile(BytesIO(zipresp.read())) as zfile:
                            zfile.extractall(s_preset_folder)

                            p_example.file_path = ''
                            for file in zfile.filelist:
                                if file.filename.lower().endswith('.blend'):
                                    p_example.file_path = os.path.join(s_preset_folder, file.filename)

                            if p_example.file_path:
                                self.report({'INFO'}, f'Successfully loaded example: {p_example.name}')
                            else:
                                self.report({'WARNING'}, f'Loaded example: {p_example.name} but BLEND file is missing!')

                    context.preferences.is_dirty = True

                    return {'FINISHED'}
        except urllib.error.URLError as e:
            self.report({'ERROR'}, "Can not update! Check internet connection! Error details: " + str(e))
        except Exception as e:
            self.report({'ERROR'}, str(e))

        return {'CANCELLED'}


class ZUV_OT_DemoExamplesDelete(bpy.types.Operator):
    bl_idname = "wm.zuv_demo_examples_delete"
    bl_label = 'Delete Example'
    bl_description = 'Delete folder with example by given index'
    bl_options = {'INTERNAL'}

    idx: bpy.props.IntProperty(
        name='Example Index',
        default=-1
    )

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event):
        wm = context.window_manager
        return wm.invoke_confirm(self, event)

    def execute(self, context: bpy.types.Context):
        from ZenUV.prop.zuv_preferences import get_prefs
        addon_prefs = get_prefs()

        try:
            p_example = addon_prefs.demo.get_example(self.idx)  # type: ZuvDemoExample
            if p_example is not None:
                s_preset_folder = p_example.get_preset_folder()
                if s_preset_folder:
                    shutil.rmtree(s_preset_folder)

                    p_example.update_file_path()

                    context.preferences.is_dirty = True

                    return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, str(e))

        return {'CANCELLED'}
