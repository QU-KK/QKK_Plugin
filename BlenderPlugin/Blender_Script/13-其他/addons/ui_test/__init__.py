# Unity_Fbx/__init__.py  —  generated with Uzima UI Generator (by Raisy Clutch)
import bpy
from . import uzima as ui

app = ui.App("Unity_Fbx", theme=ui.Theme(accent="#b79cf2"))

# ---- actions (become real Blender operators; hotkeys can be added here) ----
@app.action("__", label="创建内容后会显示在这里。", icon="inbox")
def __(context):
    ...  # your code here

# ---- layout ----
def build(surface):
    return ui.Column(
        ui.Stepper(label="变体", value=1),
        ui.Row(ui.Heading("标题", subtitle="简短描述")),
        ui.Row(
            ui.Column(
                ui.TabView(
                    [
                        ui.Tab("第一个", ui.Column(), icon="sparkle"),
                        ui.Tab("第二个", ui.Column(), icon="sliders"),
                        ui.Tab("标签页 3", ui.Column()),
                        ui.Tab("标签页 4", ui.Column()),
                        ui.Tab("标签页 5", ui.Column()),
                        ui.Tab("标签页 6", ui.Column()),
                    ],
                    outlined=True,
                ),
                width=50,
            ),
            ui.Column(
                ui.KeyValue("对象", "12"),
                ui.Button("创建", icon="sparkle"),
                ui.HoldButton("长按删除", icon="trash"),
                ui.Badge("新"),
                ui.Switch("透明胶片"),
                ui.RadioGroup(
                    items=[["草图", "草图", None, "最快，适合粗模"], ["均衡", "均衡", None, "速度与细节的最佳平衡"], ["最佳", "最佳", None, "较慢，细节最高"]],
                    value="均衡",
                ),
                ui.Segmented(["网格", "列表", "墙体"], value="网格"),
                ui.ToggleGroup(items=["选中", "可见", "渲染"], value=["可见"]),
                ui.RadioGroup(
                    items=[["草图", "草图", None, "最快，适合粗模"], ["均衡", "均衡", None, "速度与细节的最佳平衡"], ["最佳", "最佳", None, "较慢，细节最高"]],
                    value="均衡",
                ),
                ui.Checkbox("自动 UV 展开", value=True),
            ),
        ),
        ui.Column(),
        ui.IconButton("layers", variant="ghost", size="md", tooltip="添加"),
        ui.ViewportPreview(),
        ui.Table(
            columns=[ui.TableColumn("名称", lambda r: r["col1"]), ui.TableColumn("类型", lambda r: r["col2"]), ui.TableColumn("顶点数", lambda r: r["col3"])],
            rows=[{"col1": "立方体", "col2": "网格", "col3": "8"}, {"col1": "灯光", "col2": "灯光", "col3": "0"}, {"col1": "相机", "col2": "相机", "col3": "0"}],
        ),
        ui.DataPicker(label="材质", collection="materials"),
        ui.Dropdown(items=["EEVEE", "Cycles", "Workbench"], value="EEVEE"),
        ui.Badge("新"),
        ui.IconButton("plus", variant="ghost", size="md", tooltip="添加"),
        ui.TabView(
            [
                ui.Tab("第一个", ui.Column(), icon="sparkle"),
                ui.Tab("第二个", ui.Column(), icon="sliders"),
            ],
        ),
        ui.FilePathField(label="输出文件夹", filter="*"),
        ui.Steps(
            [["准备场景", "检查对象", "done"], ["渲染", "Cycles，128 采样", "active"], ["导出", "PNG 序列", "todo"]],
        ),
        ui.RadioGroup(
            items=[["草图", "草图", None, "最快，适合粗模"], ["均衡", "均衡", None, "速度与细节的最佳平衡"], ["最佳", "最佳", None, "较慢，细节最高"]],
            value="均衡",
        ),
        ui.Alert("已保存到当前场景。", title="注意"),
        ui.DropZone(
            label="添加参考图片",
            hint="PNG、JPG 或 EXR · 点击浏览",
            filter="*.png;*.jpg;*.jpeg;*.exr;*.tif;*.webp",
            icon="upload",
        ),
        ui.EmptyState("这里还什么都没有", text="创建内容后会显示在这里。", icon="inbox", action="创建"),
        ui.Breadcrumbs(["资源库", "道具", "家具", "椅子"], icon="home"),
        ui.Column(ui.Button("创建", icon="sparkle", variant="success", size="lg", active=True)),
        ui.Card(
            title="Card",
            subtitle="55555557575757",
            icon="sparkle",
            open=False,
            variant="outline",
        ),
        ui.Row(
            ui.Button("渲染", icon="window", flex=4),
            ui.Button("", icon="image"),
            ui.Button("", icon="scene"),
            ui.Dropdown(items=["槽1", "槽2", "槽3", "槽4"], value="槽1", placeholder="Select"),
        ),
        ui.Separator(),
        ui.Column(),
        ui.Card(title="Card"),
        ui.Card(title="Card"),
        ui.Card(title="Card"),
        ui.Card(title="Card"),
        ui.Card(title="Card"),
        ui.Card(title="Card"),
        ui.Card(title="Card"),
        ui.Card(title="Card"),
        ui.Card(title="Card"),
        ui.Card(title="Card"),
        ui.Card(title="卡片"),
        gap=2,
    )

app.sidebar("Unity_Fbx", build=build)
app.viewport()   # windows, dialogs, toasts and the command palette over the 3D view

def register():
    # register your own PropertyGroups first, then:
    app.register()


def unregister():
    app.unregister()
