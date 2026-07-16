'''
Copyright (C) 2019-2023 Dancing Fortune Software All Rights Reserved

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
'''

bl_info = {
    'name': '🧇 烘焙神器 (Bake Wrangler)',
    'description': '旨在通道基于节点的界面改进所有烘焙任务,并渲染额外的烘焙过程',
    'author': 'DFS  汉化：GJJ',
    'version': (1, 6, 1),
    'blender': (3, 4, 0),
    'location': '【编辑器类型】>【烘焙神器 (Bake Wrangler)】',
    #"warning": "Beta Version",
    'doc_url': 'https://bake-wrangler.readthedocs.io',
    "tracker_url": "https://blenderartists.org/t/bake-wrangler-node-based-baking-tool-set/",
    "support": "COMMUNITY",
    'category': 'Baking'}


import bpy
from . import nodes
from . import status_bar


# Preferences
class BakeWrangler_Preferences(bpy.types.AddonPreferences):
    bl_idname = __package__
    
    def update_icon(self, context):
        if not self.show_icon:
            status_bar.status_bar_icon.disable_bw_icon()
        else:
            status_bar.status_bar_icon.ensure_bw_icon()
            
    # Message prefs
    show_icon: bpy.props.BoolProperty(name="在状态栏中显示BW图标", description="显示一个根据烘焙状态更改颜色的图标,可以单击该图标以调出日志", default=True, update=update_icon)
    text_msgs: bpy.props.BoolProperty(name="消息到文本编辑器", description="将消息写入控制台之外的文本块", default=True)
    clear_msgs: bpy.props.BoolProperty(name="清除旧消息", description="每次烘焙前清除文本块", default=True)
    wind_msgs: bpy.props.BoolProperty(name="在新窗口中打开文本", description="每次开始新烘焙时,都会打开一个新窗口,显示文本块", default=False)
    wind_close: bpy.props.BoolProperty(name="自动关闭文本窗口", description="烘焙成功后关闭文本窗口", default=False)
    
    # Node prefs
    show_node_prefs: bpy.props.BoolProperty(name="节点默认值", description="默认常规节点选项", default=False)
    def_filter_mesh: bpy.props.BoolProperty(name="栅格", description="显示栅格类型对象", default=True)
    def_filter_curve: bpy.props.BoolProperty(name="曲线", description="显示曲线类型对象", default=True)
    def_filter_surface: bpy.props.BoolProperty(name="表面", description="显示表面类型对象", default=True)
    def_filter_meta: bpy.props.BoolProperty(name="转移", description="显示元类型对象", default=True)
    def_filter_font: bpy.props.BoolProperty(name="字体", description="显示字体类型对象", default=True)
    def_filter_light: bpy.props.BoolProperty(name="灯光", description="显示灯光类型对象", default=True)
    def_filter_collection: bpy.props.BoolProperty(name="收藏", description="仅切换集合", default=False)
    def_show_adv: bpy.props.BoolProperty(name="展开高级设置", description="在节点创建时展开高级设置,而不是从折叠的设置开始", default=False)
    invert_bakemod: bpy.props.BoolProperty(name="反转烘焙修改器中的选定对象", description="反转“烘焙修改器”选项的选择方法,从忽略视口隐藏的修改器到烘焙它们", default=False)

    # Render prefs
    show_render_prefs: bpy.props.BoolProperty(name="渲染默认值", description="渲染选项的默认设置", default=False)
    def_samples: bpy.props.IntProperty(name="默认烘焙采样数", description="创建新“过程”节点时将设置为的每个像素的采样数", default=1, min=1)
    def_xres: bpy.props.IntProperty(name="默认烘焙X分辨率", description="X分辨率的新Pass节点将在创建时设置为", default=1024, min=1, subtype='PIXEL')
    def_yres: bpy.props.IntProperty(name="默认烘焙Y分辨率", description="Y分辨率的新过程节点将在创建时设置为", default=1024, min=1, subtype='PIXEL')
    def_device: bpy.props.EnumProperty(name="默认设备", description="渲染设备的新“过程”节点将在创建时设置为", items=nodes.node_tree.BakeWrangler_PassSettings.cycles_devices, default='CPU')
    def_raydist: bpy.props.FloatProperty(name="默认光线距离", description="创建新栅格节点时将的光线距离", default=0.01, step=1, min=0.0, unit='LENGTH')
    def_max_ray_dist: bpy.props.FloatProperty(name="默认最大光线距离", description="创建新栅格节点时将的最大光线距离", default=0.0, step=1, min=0.0, unit='LENGTH')
    def_margin: bpy.props.IntProperty(name="默认边缘", description="创建新栅格节点时将的边距", default=0, min=0, subtype='PIXEL')
    def_mask_margin: bpy.props.IntProperty(name="默认遮罩边距", description="创建新栅格节点时将的遮罩边距", default=0, min=0, subtype='PIXEL')
    ignore_vis: bpy.props.BoolProperty(name="对象始终可见", description="启用该选项可以在烘焙时忽略选定对象的可见性,使其无论在blender中的设置如何都可见", default=False)

    # Ouput prefs
    show_output_prefs: bpy.props.BoolProperty(name="输出默认值", description="输出选项的默认设置", default=False)
    def_format: bpy.props.EnumProperty(name="默认输出格式", description="创建新输出节点时将的格式", items=nodes.node_tree.BakeWrangler_OutputSettings.img_format, default='PNG')
    def_xout: bpy.props.IntProperty(name="默认输出X分辨率", description="X分辨率的新输出节点将在创建时设置为", default=1024, min=1, subtype='PIXEL')
    def_yout: bpy.props.IntProperty(name="默认输出Y分辨率", description="Y分辨率的新输出节点将在创建时设置为", default=1024, min=1, subtype='PIXEL')
    def_outpath: bpy.props.StringProperty(name="默认输出路径", description="新输出节点在创建时将的路径", default="", subtype='DIR_PATH')
    def_outname: bpy.props.StringProperty(name="默认输出名称", description="创建新输出节点时将的名称", default="Image", subtype='FILE_NAME')
    make_dirs: bpy.props.BoolProperty(name="创建路径", description="如果所选路径不存在,请尝试创建它", default=False)
    auto_open: bpy.props.BoolProperty(name="自动打开烘焙", description="如果烘焙图像尚未打开,则自动打开blender中的烘焙图像", default=True)
    save_packed: bpy.props.BoolProperty(name="保存压缩的图像", description="烘焙之前,请保存任何已打包的图像,否则它们将不会在烘焙过程中应用", default=False)
    save_images: bpy.props.BoolProperty(name="保存解压缩的图像", description="烘焙之前,请保存任何已更改的未打包图像,否则它们将不会在烘焙过程中应用", default=False)
    img_non_color: bpy.props.EnumProperty(name="非色彩", description="替代颜色空间时用作非颜色的颜色空间", items=nodes.node_tree.BakeWrangler_OutputSettings.img_color_spaces)
    
    # Performance prefs
    fact_start: bpy.props.BoolProperty(name="禁用插件", description="禁用后台烘焙实例中的插件(加载时间更快,某些第三方插件可能会使进程塌陷)", default=True)
    retrys: bpy.props.IntProperty(name="重试次数", description="烘焙失败时,多次重试", default=0)
    
    # Dev prefs
    debug: bpy.props.BoolProperty(name="调试", description="启用附加调试输出", default=False)

    def draw(self, context):
        layout = self.layout
        row=layout.row();row.operator("wm.url_open", text="插件视频",icon="FILE_MOVIE").url = "https://www.bilibili.com/video/BV1ED421p7tL/";row.operator("wm.url_open", text="更多插件",icon="COLORSET_09_VEC").url = "https://space.bilibili.com/454791153/video"
        if bpy.app.version < (3,4,0) :row=layout.row();row.alert=True;row.operator("wm.url_open",text="只支持blender3.4-4.2",icon="KEYTYPE_KEYFRAME_VEC").url = "https://www.bilibili.com/video/BV1Qv411F7ia/"
        colprefs = layout.column(align=False)

        coltext = colprefs.column(align=False)
        coltext.prop(self, "show_icon")
        coltext.prop(self, "text_msgs")
        if self.text_msgs:
            box = coltext.box()
            box.prop(self, "clear_msgs")
            box.prop(self, "wind_msgs")
            row = box.row(align=True)
            row.label(icon='THREE_DOTS')
            row.prop(self, "wind_close")
            if self.wind_msgs:
                row.enabled = True
            else:
                row.enabled = False

        # Node prefs
        box = colprefs.box()
        if not self.show_node_prefs:
            box.prop(self, "show_node_prefs", icon="DISCLOSURE_TRI_RIGHT", emboss=False)
        else:
            box.prop(self, "show_node_prefs", icon="DISCLOSURE_TRI_DOWN", emboss=False)
            col = box.column(align=False)
            row = col.row(align=True)
            row.alignment = 'LEFT'
            row.label(text="滤器")
            row1 = row.row(align=True)
            row1.alignment = 'LEFT'
            row1.prop(self, "def_filter_mesh", text="", icon='MESH_DATA')
            row1.prop(self, "def_filter_curve", text="", icon='CURVE_DATA')
            row1.prop(self, "def_filter_surface", text="", icon='SURFACE_DATA')
            row1.prop(self, "def_filter_meta", text="", icon='META_DATA')
            row1.prop(self, "def_filter_font", text="", icon='FONT_DATA')
            row1.prop(self, "def_filter_light", text="", icon='LIGHT_DATA')
            if self.def_filter_collection:
                row1.enabled = False
            row2 = row.row(align=False)
            row2.alignment = 'LEFT'
            row2.prop(self, "def_filter_collection", text="", icon='GROUP')
            col.prop(self, "def_show_adv")
            col.prop(self, "invert_bakemod")

        # Render prefs
        box = colprefs.box()
        if not self.show_render_prefs:
            box.prop(self, "show_render_prefs", icon="DISCLOSURE_TRI_RIGHT", emboss=False)
        else:
            box.prop(self, "show_render_prefs", icon="DISCLOSURE_TRI_DOWN", emboss=False)
            col = box.column(align=False)
            col.prop(self, "def_samples", text="采样")
            col1 = col.column(align=True)
            col1.prop(self, "def_xres", text="X")
            col1.prop(self, "def_yres", text="Y")
            col.prop(self, "def_device", text="装置")
            col.prop(self, "def_margin", text="边缘")
            col.prop(self, "def_mask_margin", text="遮罩边距")
            col.prop(self, "def_raydist", text="射线距离")
            col.prop(self, "def_max_ray_dist", text="最大光线距离")
            col.prop(self, "ignore_vis")

        # Output prefs
        box = colprefs.box()
        if not self.show_output_prefs:
            box.prop(self, "show_output_prefs", icon="DISCLOSURE_TRI_RIGHT", emboss=False)
        else:
            box.prop(self, "show_output_prefs", icon="DISCLOSURE_TRI_DOWN", emboss=False)
            col = box.column(align=False)
            col.prop(self, "def_format", text="总体安排")
            col1 = col.column(align=True)
            col1.prop(self, "def_xout", text="X")
            col1.prop(self, "def_yout", text="Y")
            col2 = col.column(align=True)
            col2.prop(self, "def_outpath", text="图像路径")
            col2.prop(self, "def_outname", text="图像名称")
            col.prop(self, "make_dirs")
            col.prop(self, "auto_open")

        # Dev prefs
        col = colprefs.column(align=True)
        col.prop(self, "fact_start")
        col.prop(self, "save_packed")
        col.prop(self, "save_images")
        col.prop(self, "retrys")
        if 'Non-Color' not in bpy.types.ColorManagedInputColorspaceSettings.bl_rna.properties['name'].enum_items.keys():
            col.prop(self, "img_non_color")
        col.prop(self, "debug")



def register():
    from bpy.utils import register_class
    register_class(BakeWrangler_Preferences)
    # Add status property to the window manager
    bpy.types.WindowManager.bw_status = bpy.props.IntProperty(name="烘焙牧马人状态", default=0)
    bpy.types.WindowManager.bw_lastlog = bpy.props.StringProperty(name="Bake Wangler日志", default="")
    bpy.types.WindowManager.bw_lastfile = bpy.props.StringProperty(name="Bake Wangler Temp Blend", default="")
    nodes.register()
    status_bar.register()


def unregister():
    from bpy.utils import unregister_class
    nodes.unregister()
    status_bar.unregister()
    unregister_class(BakeWrangler_Preferences)
    # Remove status property from window manager
    delattr(bpy.types.WindowManager, 'bw_status')
