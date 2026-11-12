# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""Py script launcher rebuilt with Uzima UI.

The layout mirrors the original "按钮小工具pro" panel:

    header (refresh / open folder / debug toggle)
    category selector (top level folders, 4 per row)
    contents of the selected category:
        * a folder whose name encodes the layout, e.g. "03-行-2-框-对齐",
          becomes a container: 列 -> column, 行-N -> N per row, 框 -> framed,
          对齐 -> aligned spacing
        * a script file whose name is "index-label-icon-scale.py" becomes a
          button with that label, icon and height
        * a file containing "-题头" becomes a section header
"""

import os
import subprocess
import sys
import traceback

import bpy

from . import uzima as ui

APP_ID = "py_script_tool_pro"
TAB = "Python_test"
SCRIPTS_FOLDER = "Python脚本"
MAX_DEPTH = 3

ADDON_DIR = os.path.dirname(os.path.abspath(__file__))

app = ui.App(APP_ID, theme=ui.Theme(accent="#7aa7e0"))

# Blender tells "eye open" (HIDE_OFF) and "eye crossed" (HIDE_ON) apart with two
# icons; Uzima only ships the open eye, so add the crossed one here.
ui.icons.register("eye_off", [
    ("q", (3, 12), (12, 3), (21, 12)),
    ("q", (3, 12), (12, 21), (21, 12)),
    ("c", 12, 12, 3),
    ("l", 4, 20, 20, 4),
])

STATE = {
    "root": None,       # absolute path of the Python脚本 folder
    "tree": None,       # ["dir", name, [children]] or None when not scanned yet
    "selected": None,   # name of the selected top level folder
    "error": "",
}

PANEL = None            # the sidebar surface, assigned at the bottom


# ---------------------------------------------------------------------------
# Blender icons -> Uzima vector icons
# ---------------------------------------------------------------------------

ICONS = {
    "AREA_SWAP": "window",
    "DESKTOP": "window",
    "EXPORT": "upload",
    "FILE": "file",
    "FILE_FOLDER": "folder",
    "FILE_REFRESH": "refresh",
    "HIDE_OFF": "eye",
    "HIDE_ON": "eye_off",
    "IMAGE_DATA": "image",
    "LOCKVIEW_ON": "lock",
    "MATERIAL": "palette",
    "MENU_PANEL": "menu",
    "NODE_SOCKET_SHADER": "sphere",
    "OUTLINER_COLLECTION": "layers",
    "QUESTION_LARGE": "help",
    "RESTRICT_INSTANCED_OFF": "eye",
    "RESTRICT_INSTANCED_ON": "eye_off",
    "SEQ_STRIP_MODIFIER": "sliders",
    "SHADING_TEXTURE": "image",
    "TRASH": "trash",
    "UV": "grid",
    "WORKSPACE": "grid",
    "X": "x",
    "ZOOM_IN": "plus",
    "ZOOM_OUT": "minus",
}

# ordered heuristics for icon names that are not in the table above
ICON_HINTS = (
    ("REFRESH", "refresh"),
    ("FOLDER", "folder"),
    ("TRASH", "trash"),
    ("DELETE", "trash"),
    ("ZOOM_IN", "plus"),
    ("ZOOM_OUT", "minus"),
    ("EXPORT", "upload"),
    ("IMPORT", "download"),
    ("COLLECTION", "layers"),
    ("OUTLINER", "layers"),
    ("SHADER", "sphere"),
    ("MATERIAL", "palette"),
    ("NODE", "sphere"),
    ("TEXTURE", "image"),
    ("IMAGE", "image"),
    ("MESH", "mesh"),
    ("CAMERA", "camera"),
    ("LIGHT", "light"),
    ("SCENE", "scene"),
    ("WORLD", "globe"),
    ("HIDE", "eye"),
    ("VISIB", "eye"),
    ("LOCK", "lock"),
    ("FILE", "file"),
    ("PLAY", "play"),
    ("RENDER", "camera"),
    ("PREF", "settings"),
    ("SETTING", "settings"),
    ("MODIFIER", "sliders"),
    ("TOOL", "sliders"),
    ("UV", "grid"),
    ("QUESTION", "help"),
    ("WARNING", "warning"),
    ("ERROR", "error"),
    ("INFO", "info"),
    ("CHECK", "check"),
    ("ADD", "plus"),
    ("REMOVE", "minus"),
    ("WINDOW", "window"),
    ("PANEL", "window"),
)


def icon_for(name):
    """Map a Blender icon name to a Uzima icon name (None = no icon)."""
    if not name:
        return None
    key = str(name).strip().upper()
    if not key or key in ("NONE", "0"):
        return None
    if key in ICONS:
        return ICONS[key]
    for token, icon in ICON_HINTS:
        if token in key:
            return icon
    return None


# ---------------------------------------------------------------------------
# Scanning the Python脚本 folder
# ---------------------------------------------------------------------------

def scripts_root():
    return os.path.join(ADDON_DIR, SCRIPTS_FOLDER)


def scan_dir(path, depth=0):
    """Nested ["dir", name, [...]] / ["file", path] list, sorted like the original."""
    out = []
    try:
        entries = sorted(os.listdir(path))
    except OSError:
        return out
    for name in entries:
        if name.startswith(".") or name == "__pycache__":
            continue
        full = os.path.join(path, name)
        try:
            is_dir = os.path.isdir(full)
        except OSError:
            continue
        if is_dir:
            children = scan_dir(full, depth + 1) if depth + 1 < MAX_DEPTH else []
            out.append(["dir", name, children])
        elif name.lower().endswith(".py"):
            out.append(["file", full])
    return out


def count_files(node):
    if not node:
        return 0
    if node[0] == "file":
        return 1
    return sum(count_files(child) for child in node[2])


def folder_spec(name):
    """Decode the layout DSL stored in a folder name.

    "02-列"          -> column
    "03-行-2-框-对齐" -> 2 per row, framed, aligned
    """
    parts = name.split("-")
    kind = "col"
    cols = 1
    boxed = "框" in parts
    aligned = "对齐" in parts
    if len(parts) > 1 and parts[1] in ("列", "行"):
        kind = "row" if parts[1] == "行" else "col"
        if kind == "row":
            cols = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 2
            cols = max(1, min(cols, 8))
    return kind, cols, boxed, aligned


def category_label(name):
    """Strip the leading "01-" index the same way the original panel does."""
    return name.split("-", 1)[1] if "-" in name else name


def parse_script_name(path):
    """Return (label, icon, scale_y) from "index-label-icon-scale.py"."""
    stem = os.path.splitext(os.path.basename(path))[0]
    parts = stem.split("-")
    label = parts[1] if len(parts) > 1 else stem
    icon = icon_for(parts[2]) if len(parts) > 2 else None
    scale = 1.0
    if len(parts) > 3:
        try:
            scale = float(parts[3])
        except ValueError:
            scale = 1.0
    return label, icon, scale


def is_header(path):
    return "-题头" in os.path.splitext(os.path.basename(path))[0]


def relative(path):
    root = STATE["root"]
    if root:
        try:
            return os.path.relpath(path, root).replace(os.sep, " / ")
        except ValueError:
            pass
    return os.path.basename(path)


# ---------------------------------------------------------------------------
# State changes
# ---------------------------------------------------------------------------

def rebuild_view():
    if PANEL is not None:
        PANEL.rebuild()
    app.tag_redraw(force=True)


def refresh(notify_user=True):
    """Rescan the scripts folder and rebuild the panel."""
    root = scripts_root()
    STATE["root"] = root
    if not os.path.isdir(root):
        STATE["tree"] = None
        STATE["selected"] = None
        STATE["error"] = "找不到文件夹：%s" % root
        if notify_user:
            app.toast("找不到脚本文件夹", root, kind="error", duration=5)
    else:
        tree = ["dir", os.path.basename(root), scan_dir(root, 0)]
        STATE["tree"] = tree
        STATE["error"] = ""
        names = [entry[1] for entry in tree[2] if entry[0] == "dir"]
        if STATE["selected"] not in names:
            STATE["selected"] = names[0] if names else None
        if notify_user:
            app.toast("已刷新", "%d 个分类 · %d 个脚本" % (len(names), count_files(tree)),
                      kind="success")
    rebuild_view()
    return STATE["tree"]


def select(name):
    if STATE["selected"] == name:
        return
    STATE["selected"] = name
    rebuild_view()


def debug_enabled():
    try:
        return bool(bpy.context.scene.py_script_tool_debug)
    except Exception:
        return False


def open_folder():
    root = STATE["root"] or scripts_root()
    if not os.path.isdir(root):
        refresh()
        root = scripts_root()
    try:
        if os.name == "nt":
            os.startfile(root)  # noqa: S606 (desktop only)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", root])
        else:
            subprocess.Popen(["xdg-open", root])
    except Exception as exc:
        app.toast("打开文件夹失败", str(exc), kind="error", duration=5)


def reveal(path):
    try:
        if os.name == "nt":
            subprocess.Popen('explorer /select,"%s"' % os.path.normpath(path))
        elif sys.platform == "darwin":
            subprocess.Popen(["open", "-R", path])
        else:
            subprocess.Popen(["xdg-open", os.path.dirname(path)])
    except Exception as exc:
        app.toast("定位失败", str(exc), kind="error", duration=5)


def launch(path):
    """Run a script, or reveal it in the file manager when debug mode is on."""
    if debug_enabled():
        reveal(path)
        app.toast("已定位", os.path.basename(path), kind="info")
        return

    # Keep the 3D view context: scripts often call view3d operators, and a timer
    # callback would otherwise run with no area / region.
    win = getattr(bpy.context, "window", None)
    screen = getattr(bpy.context, "screen", None)
    area = getattr(bpy.context, "area", None)
    region = getattr(bpy.context, "region", None)
    if area is not None and area.type == "VIEW_3D":
        region = next((r for r in area.regions if r.type == "WINDOW"), region)
    context_override = {}
    for key, value in (("window", win), ("screen", screen), ("area", area), ("region", region)):
        if value is not None:
            context_override[key] = value

    # Run one tick later so we are outside the UI event pump.
    def _later():
        _execute(path, context_override)
        return None
    bpy.app.timers.register(_later, first_interval=0.01)


def _execute(path, context_override=None):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            source = handle.read()
        namespace = {"__name__": "__main__", "__file__": path, "__builtins__": __builtins__}
        code = compile(source, path, "exec")
        if context_override:
            with bpy.context.temp_override(**context_override):
                exec(code, namespace)
        else:
            exec(code, namespace)
    except Exception:
        traceback.print_exc()
        error = traceback.format_exc().strip().splitlines()[-1]
        app.toast("运行失败", "%s — %s" % (os.path.basename(path), error),
                  kind="error", duration=6)
    else:
        app.toast("运行完成", relative(path), kind="success")


# ---------------------------------------------------------------------------
# Widgets
# ---------------------------------------------------------------------------

def build_script(path):
    label, icon, scale = parse_script_name(path)
    height = max(26.0, min(56.0, 30.0 * (scale or 1.0)))
    return ui.Button(
        label,
        icon=icon,
        height=height,
        size="sm" if height < 36 else "md",
        variant="secondary",
        tooltip=relative(path),
        on_click=lambda button, p=path: launch(p),
    )


def build_header(path):
    stem = os.path.splitext(os.path.basename(path))[0]
    parts = stem.split("-")
    label = parts[1] if len(parts) > 1 else stem
    icon = icon_for(parts[2]) if len(parts) > 2 else None
    return ui.Label(label, icon=icon, weight="semibold", size=12, color="text_dim")


def _build_children(children):
    """Build a mixed list of (is_header, widget) for one container."""
    out = []
    for child in children:
        if child[0] == "dir":
            widget = build_group(child[1], child[2])
            out.append((False, widget))
        elif is_header(child[1]):
            out.append((True, build_header(child[1])))
        else:
            out.append((False, build_script(child[1])))
    return [(head, widget) for head, widget in out if widget is not None]


def build_group(name, children):
    """Render one folder of scripts according to the layout DSL in its name."""
    kind, cols, boxed, aligned = folder_spec(name)
    items = _build_children(children)
    if not items:
        return None
    gap = 3 if aligned else 4

    if kind == "row" and any(head for head, _widget in items):
        # Section headers span the whole width; the buttons below them
        # are packed into rows of `cols`.
        blocks = []
        row = []

        def flush():
            if row:
                blocks.append(ui.Grid(*row, cols=cols, gap=gap))
                del row[:]

        for head, widget in items:
            if head:
                flush()
                blocks.append(widget)
            else:
                row.append(widget)
        flush()
        body = ui.Column(*blocks, gap=6)
    elif kind == "row":
        body = ui.Grid(*[widget for _head, widget in items], cols=cols, gap=gap)
    else:
        body = ui.Column(*[widget for _head, widget in items], gap=gap)

    if boxed:
        return ui.Card(body, variant="outline", padding=7)
    return body


def build_category(entry):
    items = []
    for child in entry[2]:
        if child[0] == "dir":
            widget = build_group(child[1], child[2])
        elif is_header(child[1]):
            widget = build_header(child[1])
        else:
            widget = build_script(child[1])
        if widget is not None:
            items.append(widget)
    if not items:
        return ui.EmptyState("这里还没有脚本", "把 .py 文件放进这个分类文件夹即可。", icon="inbox")
    return ui.Column(*items, gap=8)


def build_selector(folders):
    buttons = []
    for entry in folders:
        name = entry[1]
        label = category_label(name)
        count = count_files(entry)
        buttons.append(ui.Button(
            label,
            size="xs",
            height=30,
            variant="primary" if name == STATE["selected"] else "secondary",
            tooltip="%s · %d 个脚本" % (label, count),
            on_click=lambda button, n=name: select(n),
        ))
    return ui.Grid(*buttons, cols=4, gap=4)


def build(surface):
    tree = STATE["tree"]
    folders = [entry for entry in tree[2] if entry[0] == "dir"] if tree else []
    total = count_files(tree)

    if tree:
        subtitle = "%d 个分类 · %d 个脚本" % (len(folders), total)
    else:
        subtitle = "扫描插件内的 %s 文件夹" % SCRIPTS_FOLDER

    body = [
        ui.Row(
            ui.Column(
                ui.Heading("Py脚本工具", subtitle=subtitle),
                width=None,
            ),
            ui.IconButton(
                "refresh", variant="soft", size="md",
                tooltip="刷新脚本列表",
                on_click=lambda button: refresh(),
            ),
            ui.IconButton(
                "folder", variant="soft", size="md",
                tooltip="打开脚本文件夹",
                on_click=lambda button: open_folder(),
            ),
            gap=6,
        ),
        ui.Switch(
            "调试模式（只定位，不执行）",
            bind="scene.py_script_tool_debug",
            tooltip="开启后点击脚本会在文件管理器中定位它，而不是运行它",
        ),
        ui.Separator(),
    ]

    if tree is None:
        if STATE["error"]:
            body.append(ui.Alert(STATE["error"], title="找不到脚本文件夹", kind="warning"))
        body.append(ui.EmptyState(
            "还没有脚本列表",
            "点击下面的按钮，扫描 %s 文件夹。" % SCRIPTS_FOLDER,
            icon="folder",
        ))
        body.append(ui.Button(
            "刷新Py脚本", icon="refresh", variant="hero", height=56,
            on_click=lambda button: refresh(),
        ))
        return ui.Column(*body, gap=8)

    if not folders:
        body.append(ui.Alert(
            "%s 里没有子文件夹，请先建立分类文件夹。" % SCRIPTS_FOLDER,
            title="没有分类", kind="info",
        ))
        return ui.Column(*body, gap=8)

    body.append(build_selector(folders))
    selected = next((entry for entry in folders if entry[1] == STATE["selected"]), folders[0])
    body.append(ui.Separator())
    body.append(build_category(selected))
    return ui.Column(*body, gap=10)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

def register():
    if not hasattr(bpy.types.Scene, "py_script_tool_debug"):
        bpy.types.Scene.py_script_tool_debug = bpy.props.BoolProperty(
            name="Py脚本调试定位",
            description="为真时点击脚本只在文件管理器中定位，不执行脚本",
            default=False,
        )
    app.register()
    refresh(notify_user=False)


def unregister():
    app.unregister()
    if hasattr(bpy.types.Scene, "py_script_tool_debug"):
        del bpy.types.Scene.py_script_tool_debug


PANEL = app.sidebar(TAB, build=build, padding=10)
app.viewport()
