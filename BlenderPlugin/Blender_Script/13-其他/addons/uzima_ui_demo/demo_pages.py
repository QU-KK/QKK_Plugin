# Copyright (C) 2026 Raisy Clutch
# raisycltch@gmail.com
#
# Created by Raisy Clutch
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""Demo pages. Each function returns one page of the sidebar; every element is wired to something real."""

import math
import time

import bpy

from . import uzima as ui
from .demo_core import (ACCENTS, ENV_IMAGES, KINDS, LOOKS, LOOK_IMAGES, PIE_ITEMS, app, asset, demo_curve, demo_ramp,
                        generate, hud_tool, labels_tool, props, ruler_tool, select_object, start_tour, tool_bind,
                        toolbar_tool)


def section(text):
    return ui.Label(text, muted=True, size=11, weight="medium")


def obj():
    return bpy.context.object


def create_button(**kw):
    return ui.Button("Create", variant="hero", icon="sparkles", cost=lambda: 3 * props().variants,
                     on_click=generate, tooltip="Create\nUses 3 credits per variant.", **kw)


# ---------------------------------------------------------------------------
# 1. Create
# ---------------------------------------------------------------------------

def recent_row(img, title, meta, badge, kind="neutral"):
    menu = [ui.MenuItem("Open", icon="external"), ui.MenuItem("Rename", icon="edit", shortcut="F2"),
            ui.MenuItem("Duplicate", icon="copy"), "-",
            ui.MenuItem("Delete", icon="trash", danger=True,
                        on_click=lambda w: app.toast("Deleted", title + " moved to trash.", "danger"))]
    return ui.Row(ui.ImageBox(asset(img), width=46, height=46, radius=9),
                  ui.Column(ui.Label(title, weight="medium"), ui.Label(meta, muted=True, size=10.5), gap=0),
                  ui.Badge(badge, kind), gap=10, context_menu=menu, tooltip="Right-click for actions")


def page_create():
    studio = ui.Card(
        ui.Segmented([(i, n, ic) for i, n, ic in KINDS], bind="scene.uzima_demo.kind"),
        ui.TextInput("Describe what you want to make…", label="Prompt", bind="scene.uzima_demo.prompt",
                     multiline=True, min_lines=3, max_lines=6, clearable=False, key="prompt"),
        ui.Row(section("Look"), ui.Label(lambda: dict((i, d) for i, _n, d, _x in LOOKS).get(props().look, ""),
                                         muted=True, size=10.5, align="right"), gap=6),
        ui.PreviewGrid(bind="scene.uzima_demo.look", images=LOOK_IMAGES, cols=3, key="look"),
        ui.Slider(bind="scene.uzima_demo.detail"),
        ui.Row(ui.Stepper("Variants", bind="scene.uzima_demo.variants"), gap=8),
        ui.Separator(),
        ui.Row(ui.Button("Preview", icon="eye", variant="outline", width="auto",
                         on_click=lambda b: app.toast("Preview", "Previews are simulated in the demo.", "info")),
               create_button(size="lg", key="create_btn"), gap=8),
        title="New creation", subtitle="Describe it, pick a look, create", icon="sparkles", variant="raised", gap=12,
    )
    recent = ui.Card(
        recent_row("landscape", "Dusk dunes", "Image · 2 min ago", "Image", "info"),
        recent_row("car", "Red coupe", "Mesh · 18 min ago", "Mesh", "accent"),
        recent_row("rooftop", "Rooftop at night", "Scene · 1 h ago", "Scene", "warning"),
        title="Recent", icon="refresh", collapsible=True, key="card_recent",
    )
    return ui.Column(studio, recent, gap=12)


# ---------------------------------------------------------------------------
# 2. Controls
# ---------------------------------------------------------------------------

def page_controls():
    buttons = ui.Card(
        section("Variants"),
        ui.Flow(ui.Button("Primary", variant="primary", width="auto", icon="sparkle"),
                ui.Button("Secondary", width="auto"), ui.Button("Outline", variant="outline", width="auto"),
                ui.Button("Ghost", variant="ghost", width="auto"), ui.Button("Soft", variant="soft", width="auto"),
                ui.Button("Danger", variant="danger", width="auto"), ui.Button("Success", variant="success", width="auto"),
                gap=6),
        section("Hero"),
        ui.Button("Create", variant="hero", icon="sparkles", cost=3, on_click=generate),
        section("Run Blender operators directly"),
        ui.Grid(ui.Button("Cube", icon="cube", operator="mesh.primitive_cube_add"),
                ui.Button("Sphere", icon="sphere", operator="mesh.primitive_uv_sphere_add"),
                ui.Button("Light", icon="light", operator="object.light_add", props={"type": "AREA"}),
                ui.Button("Camera", icon="camera", operator="object.camera_add"), cols=2, gap=6),
        section("Icon buttons and states"),
        ui.Flow(*[ui.IconButton(i, variant=v, tooltip=i.capitalize()) for i, v in
                  (("plus", "secondary"), ("edit", "secondary"), ("copy", "ghost"), ("trash", "danger"),
                   ("play", "primary"), ("heart", "soft"))], gap=6),
        ui.Row(ui.Button("Loading", loading=True), ui.Button("Disabled", enabled=False),
               ui.Button("Toggle", toggle=True, icon="eye"), gap=6),
        section("Hold to confirm"),
        ui.HoldButton("Hold to delete selected", duration=1.0,
                      on_confirm=lambda b: (ui.run_operator("object.delete", confirm=False),
                                            app.toast("Deleted", "Selected objects removed.", "danger"))),
        title="Buttons", icon="bolt", collapsible=True, key="card_buttons",
    )
    chips = ui.Card(
        ui.Flow(*[ui.Chip(t, selectable=True, selected=(t == "Props")) for t in ("Characters", "Props", "Vehicles",
                                                                                 "Lights")],
                ui.Chip("Neon", icon="sparkle", removable=True, on_remove=lambda c: app.toast("Tag removed")), gap=6),
        ui.Flow(ui.Badge("New", "accent"), ui.Badge("Beta", "info", dot=True), ui.Badge("Live", "success", dot=True),
                ui.Badge("Pending", "warning"), ui.Badge("Failed", "danger", icon="x"), gap=6),
        title="Pills and chips", icon="tag", collapsible=True, key="card_chips",
    )
    toggles = ui.Card(
        ui.Checkbox(bind="scene.uzima_demo.auto_uv"),
        ui.Checkbox(bind="scene.uzima_demo.pbr", description="Albedo, roughness and normal maps"),
        ui.Switch("Transparent film", bind="scene.render.film_transparent",
                  tooltip="Bound to Blender\nscene.render.film_transparent"),
        ui.Separator("Radio"),
        ui.RadioGroup(bind="scene.uzima_demo.quality"),
        ui.Separator("Segmented"),
        ui.Segmented([("GRID", "Grid", "grid"), ("LIST", "List", "menu"), ("WALL", "Wall", "image")],
                     bind="scene.uzima_demo.view"),
        ui.Separator("Toggle groups"),
        ui.ToggleGroup(bind="scene.uzima_demo.formats", label="Export formats (multi-select enum)"),
        ui.ToggleGroup([("X", "X"), ("Y", "Y"), ("Z", "Z")], label="Mesh symmetry (active mesh)",
                       binds=["object.data.use_mirror_x", "object.data.use_mirror_y", "object.data.use_mirror_z"],
                       visible=lambda: obj() is not None and obj().type == "MESH"),
        ui.Row(ui.Label("Rating", muted=True), ui.Rating(bind="scene.uzima_demo.rating"), gap=8),
        title="Toggles", icon="success", collapsible=True, key="card_toggles",
    )
    dials = ui.Card(
        ui.Row(ui.Knob("Rotate Z", bind=ui.Bind(obj, "rotation_euler", index=2), min=-math.pi, max=math.pi,
                       default=0.0),
               ui.Knob(bind="scene.uzima_demo.strength", default=0.65),
               ui.Knob("Detail", bind="scene.uzima_demo.detail", default=0.5), gap=10, justify="between"),
        ui.Stepper("Samples", bind="scene.uzima_demo.samples", step=8),
        title="Knobs and steppers", subtitle="Drag up or down · double-click resets", icon="target",
        collapsible=True, key="card_dials",
    )
    return ui.Column(buttons, chips, toggles, dials, gap=12)


# ---------------------------------------------------------------------------
# 3. Inputs
# ---------------------------------------------------------------------------

def object_suggestions(q):
    return [(o.name, o.name, ui.id_icon(o, "objects"), o.type.title()) for o in bpy.context.scene.objects
            if q in o.name.lower()]


def page_inputs():
    text = ui.Card(
        ui.SearchField("Find an object…", suggestions=object_suggestions,
                       on_pick=lambda name, f: select_object(bpy.data.objects.get(name))),
        ui.TextInput("Scene name", label="Scene name (bound to Blender)", bind="scene.name", clearable=False),
        ui.TextInput("sk-…", label="API key", password=True, bind="scene.uzima_demo.api_key", icon="lock"),
        ui.TagInput(label="Tags", bind="scene.uzima_demo.tags"),
        ui.TextInput("Notes for this shot…", label="Notes", multiline=True, min_lines=2,
                     bind="scene.uzima_demo.notes"),
        title="Text", icon="edit", collapsible=True, key="card_text",
    )
    sliders = ui.Card(
        ui.Slider(bind="scene.uzima_demo.strength", default=0.65),
        ui.Slider("Resolution", bind="scene.render.resolution_percentage", unit="%", min=1, max=100),
        ui.RangeSlider("Frame range", bind=("scene.frame_start", "scene.frame_end"), min=1, max=250),
        ui.Slider(bind="scene.uzima_demo.samples", style="box"),
        title="Sliders", icon="sliders", collapsible=True, key="card_sliders",
    )
    numbers = ui.Card(
        ui.Row(ui.NumberField("Frame", bind="scene.frame_current"), ui.NumberField(bind="scene.uzima_demo.seed"),
               gap=8),
        ui.VectorField(bind=ui.Bind(obj, "location"), label="Location (active object)"),
        ui.VectorField(bind=ui.Bind(obj, "rotation_euler"), label="Rotation"),
        title="Numbers and vectors", subtitle="Drag, click to type, or use the arrows", icon="target",
        collapsible=True, key="card_numbers",
    )
    pickers = ui.Card(
        ui.Dropdown(bind="scene.render.engine", label="Render engine (bound to Blender)", icon="camera"),
        ui.Dropdown(bind="scene.uzima_demo.model", label="Engine", icon="cube", searchable=True),
        ui.DataPicker(bind="scene.uzima_demo.target", label="Target object (eyedropper: pick in viewport)"),
        ui.DataPicker(bind="scene.camera", label="Scene camera (Blender's own pointer)",
                      filter=lambda o: o.type == "CAMERA"),
        ui.DataPicker(bind="scene.uzima_demo.material", label="Material"),
        title="Dropdowns and data pickers", icon="menu", collapsible=True, key="card_pickers",
    )
    colors = ui.Card(
        ui.ColorField("Object color (viewport display)", bind=ui.Bind(obj, "color"),
                      visible=lambda: obj() is not None),
        ui.ColorField("Material base color", bind=ui.Bind(lambda: obj().active_material if obj() else None,
                                                          "diffuse_color"),
                      visible=lambda: obj() is not None and obj().active_material is not None),
        ui.ColorField("World color", bind=ui.Bind(lambda: bpy.context.scene.world, "color"),
                      visible=lambda: bpy.context.scene.world is not None),
        title="Colors", subtitle="Saturation square, hue, hex, eyedropper", icon="palette", collapsible=True,
        key="card_colors",
    )
    files = ui.Card(
        ui.FilePathField(bind="scene.uzima_demo.reference", filter="*.png;*.jpg;*.jpeg;*.exr"),
        ui.FilePathField("Render output folder", bind="scene.render.filepath", mode="DIR"),
        title="Files and folders", subtitle="Opens Blender's file browser", icon="folder", collapsible=True,
        key="card_files",
    )
    keys = ui.Card(
        ui.HotkeyField("Command palette", action="command_palette"),
        ui.HotkeyField("Pie menu", action="quick_pie"),
        ui.Label("Click a key field, then press a new combination. It updates Blender's keymap right away.",
                 wrap=True, muted=True, size=11),
        title="Hotkeys", icon="keyboard", collapsible=True, key="card_keys",
    )
    previews = ui.Card(
        ui.PreviewDropdown(bind="scene.uzima_demo.look", images=LOOK_IMAGES, label="Look (dropdown)", grid_cols=3),
        section("Environment (grid)"),
        ui.PreviewGrid(bind="scene.uzima_demo.env", images=ENV_IMAGES, cols=2, aspect=1.6),
        title="Preview enums", subtitle="Thumbnail pickers bound to EnumProperty", icon="image", collapsible=True,
        key="card_previews",
    )
    return ui.Column(text, sliders, numbers, pickers, colors, files, keys, previews, gap=12)


# ---------------------------------------------------------------------------
# 4. Data
# ---------------------------------------------------------------------------

_fps = {"hist": [0.0] * 30, "t": 0.0}


def fps_history():
    now = time.perf_counter()
    if now - _fps["t"] > 0.3:
        _fps["hist"] = _fps["hist"][1:] + [app.viewport_fps()]
        _fps["t"] = now
    return _fps["hist"]


def type_counts():
    counts = {}
    for o in bpy.context.scene.objects:
        counts[o.type.title()] = counts.get(o.type.title(), 0) + 1
    return dict(sorted(counts.items(), key=lambda kv: -kv[1])[:6])


def location_series():
    o = obj()
    sc = bpy.context.scene
    n = 24
    frames = [round(sc.frame_start + (sc.frame_end - sc.frame_start) * i / (n - 1)) for i in range(n)]
    if o is None:
        return []
    from .uzima.media import _fcurves
    curves = {(fc.data_path, fc.array_index): fc for fc in _fcurves(o)}
    out = []
    for axis, name, col in ((0, "X", ui.hex_color("#ec6a6a")), (1, "Y", ui.hex_color("#8cc95a")),
                            (2, "Z", ui.hex_color("#6aa8e8"))):
        fc = curves.get(("location", axis))
        vals = [fc.evaluate(f) for f in frames] if fc else [o.location[axis]] * n
        out.append((name, vals, col))
    return out


def location_labels():
    sc = bpy.context.scene
    return [round(sc.frame_start + (sc.frame_end - sc.frame_start) * i / 23) for i in range(24)]


def collection_nodes():
    def obj_node(o):
        return ui.TreeNode(("O", o.name), o.name, ui.id_icon(o, "objects"), data=o)

    def coll_node(c):
        return ui.TreeNode(("C", c.name), c.name, "folder", data=c,
                           children=lambda c=c: [coll_node(ch) for ch in c.children] + [obj_node(o) for o in c.objects])
    root = bpy.context.scene.collection
    return [coll_node(ch) for ch in root.children] + [obj_node(o) for o in root.objects]


def _visible(node):
    d = node.data
    if isinstance(d, bpy.types.Object):
        return not d.hide_get()
    return not d.hide_viewport


def _set_visible(node, v):
    d = node.data
    if isinstance(d, bpy.types.Object):
        d.hide_set(not v)
    else:
        d.hide_viewport = not v


_job = {"step": -1, "t": 0.0}
JOB_STEPS = [("Prepare scene", "Collect objects and textures"), ("Upload", "Send 24 MB to the render farm"),
             ("Render", "120 frames at 1920 × 1080"), ("Download", "Fetch the finished frames")]


def job_steps():
    s = _job["step"]
    return [(t, d, "done" if i < s else ("active" if i == s else "todo")) for i, (t, d) in enumerate(JOB_STEPS)]


def job_progress():
    s = _job["step"]
    if s < 0:
        return 0.0
    return min(1.0, (s + min(1.0, (time.perf_counter() - _job["t"]) / 1.2)) / len(JOB_STEPS))


def run_job(*_):
    _job["step"] = 0
    _job["t"] = time.perf_counter()

    def tick():
        _job["step"] += 1
        _job["t"] = time.perf_counter()
        ui.request_redraw()
        if _job["step"] >= len(JOB_STEPS):
            app.toast("Render job finished", "120 frames downloaded.", "success")
            return None
        return 1.2
    bpy.app.timers.register(tick, first_interval=1.2)


def page_data():
    stats = ui.Grid(
        ui.StatTile("Objects", lambda: len(bpy.context.scene.objects), icon="cube",
                    delta=lambda: "%d selected" % len(bpy.context.selected_objects)),
        ui.StatTile("Vertices", lambda: ui.scene_stats().get("verts", ui.scene_stats().get("vertices", "-")),
                    icon="mesh"),
        ui.StatTile("Viewport", lambda: round(app.viewport_fps()), suffix=" fps", icon="video", spark=fps_history),
        ui.StatTile("Frame", lambda: bpy.context.scene.frame_current, icon="play",
                    delta=lambda: bpy.context.scene.frame_current - bpy.context.scene.frame_start),
        cols=2, gap=8)
    charts = ui.Card(
        section("Objects by type (live)"),
        ui.BarChart(lambda: list(type_counts().values()), labels=lambda: list(type_counts().keys()), height=120),
        section("Active object location over the frame range"),
        ui.LineChart(location_series, labels=location_labels, height=150),
        title="Charts", icon="chart", collapsible=True, key="card_charts",
    )
    table = ui.Card(
        ui.Table([
            ui.TableColumn("Name", lambda o: o.name, icon=lambda o: ui.id_icon(o, "objects")),
            ui.TableColumn("Type", lambda o: o.type.title(), width=62),
            ui.TableColumn("Verts", lambda o: len(o.data.vertices) if o.type == "MESH" else 0, width=50,
                           align="right"),
            ui.TableColumn("", toggle=(lambda o: not o.hide_get(), lambda o, v: o.hide_set(not v)), width=30),
        ], rows=lambda: list(bpy.context.scene.objects), selected=lambda o: o.select_get(), on_select=select_object,
            on_activate=lambda o, t: ui.run_operator("view3d.view_selected"), max_rows=7),
        title="Scene objects", subtitle="Click to select · double-click to frame · sort by header",
        icon="table", collapsible=True, key="card_table",
    )
    tree = ui.Card(
        ui.TreeView(collection_nodes, on_select=lambda n, t, ev: select_object(n.data, t, ev)
                    if isinstance(n.data, bpy.types.Object) else None,
                    selected=lambda n: isinstance(n.data, bpy.types.Object) and n.data.select_get(),
                    toggles=[ui.TreeToggle(_visible, _set_visible)], key="tree"),
        title="Collections", subtitle="Expand, select, hide", icon="tree", collapsible=True, key="card_tree",
    )
    curve = ui.CurveEditor(mapping=demo_curve, height=150)
    curves = ui.Card(
        curve,
        ui.Flow(*[ui.Chip(n.replace("_", " ").capitalize(), on_click=lambda c, n=n: curve.set_points(ui.CURVE_PRESETS[n]))
                  for n in ("linear", "smooth", "ease_in", "ease_out", "bell")], gap=5),
        ui.Label("Edits the Float Curve node in the hidden “.Uzima Demo Nodes” node group. "
                 "Double-click adds a point, right-click deletes.", wrap=True, muted=True, size=10.5),
        title="Curve editor", icon="curve", collapsible=True, key="card_curve",
    )
    ramp = ui.Card(
        ui.ColorRampEditor(ramp=demo_ramp),
        ui.Label("Edits the Color Ramp node in the same group. Double-click the bar to add a stop.", wrap=True,
                 muted=True, size=10.5),
        title="Color ramp", icon="gradient", collapsible=True, key="card_ramp",
    )
    job = ui.Card(
        ui.Row(ui.RingProgress(job_progress, label="Render"), ui.Steps(job_steps), gap=14, valign="top"),
        ui.Button("Run a simulated render job", icon="play", on_click=run_job),
        title="Progress", icon="refresh", collapsible=True, key="card_job",
    )
    hist = ui.Card(ui.Histogram(image=asset("landscape")), title="Histogram", subtitle="landscape.png",
                   icon="chart", collapsible=True, key="card_hist")
    return ui.Column(stats, charts, table, tree, curves, ramp, job, hist, gap=12)


# ---------------------------------------------------------------------------
# 5. Media
# ---------------------------------------------------------------------------

def load_references(paths, zone):
    n = 0
    for p in paths:
        try:
            bpy.data.images.load(p, check_existing=True)
            n += 1
        except Exception:
            pass
    app.toast("Images loaded", "%d image%s added to the blend file." % (n, "" if n == 1 else "s"), "success")


def page_media():
    return ui.Column(
        ui.Card(ui.ViewportPreview(source="camera"),
                ui.Label("Rendered live by Blender's viewport engine through the scene camera.", wrap=True, muted=True,
                         size=10.5),
                title="Live camera preview", icon="camera", collapsible=True, key="card_preview"),
        ui.Card(ui.FrameScrubber(), title="Timeline", subtitle="Keyframes of the active object and markers",
                icon="video", collapsible=True, key="card_scrub"),
        ui.Card(ui.BeforeAfter(asset("character"), asset("car"), labels=("Clay", "Final")),
                title="Before and after", icon="layers", collapsible=True, key="card_ba"),
        ui.Card(ui.Carousel([(asset(n), c) for n, c in (("rooftop", "Rooftop at night"), ("landscape", "Dusk dunes"),
                                                        ("interior", "Cozy loft"), ("abstract", "Dream study"))],
                            autoplay=4, key="carousel"),
                title="Carousel", icon="image", collapsible=True, key="card_carousel"),
        ui.Card(ui.DropZone(on_files=load_references), title="Drop zone", subtitle="Loads images into the file",
                icon="upload", collapsible=True, key="card_drop"),
        ui.Card(ui.Grid(ui.ImageBox(asset("car"), height=80, badge="Mesh"),
                        ui.ImageBox(asset("interior"), height=80, badge="Render"), cols=2, gap=8),
                ui.Row(ui.Avatar("AK", status="online"), ui.Avatar("MW", color="info", status="busy"),
                       ui.Avatar("", image=asset("character"), status="away"), ui.Label("3 collaborators", muted=True),
                       gap=6),
                title="Images and avatars", icon="user", collapsible=True, key="card_images"),
        ui.Alert("Creation runs in the cloud. Your GPU is only used for the viewport and local renders.",
                 title="Cloud", kind="info"),
        ui.Alert("3 assets have missing textures.", kind="warning"),
        gap=12,
    )


# ---------------------------------------------------------------------------
# 6. Layout
# ---------------------------------------------------------------------------

def add_shot(widget):
    q = props().queue
    it = q.add()
    it.name = "Shot %02d" % len(q)
    it.frames = 24 * (len(q) % 5 + 1)
    props().queue_index = len(q) - 1


def page_layout():
    page = {"n": 1}
    return ui.Column(
        ui.Banner("Uzima 2.0 adds 40 new elements. Try the command palette with Ctrl Shift P.", title="What's new",
                  action="Open", on_action=lambda b: app.command_palette()),
        ui.Card(ui.Breadcrumbs(["Library", "Props", "Furniture", "Chairs"],
                               on_click=lambda i, label, w: app.toast("Go to " + label)),
                ui.Pagination(12, page=4, on_change=lambda p, w: app.toast("Page %d" % p), key="pages"),
                title="Navigation", icon="arrow_right", collapsible=True, key="card_nav"),
        ui.Card(ui.ReorderList(collection=lambda: props().queue, label=lambda it: it.name,
                               sublabel=lambda it: "%d frames" % it.frames, icon="video",
                               toggle=(lambda it: it.enabled, lambda it, v: setattr(it, "enabled", v)),
                               active="scene.uzima_demo.queue_index", on_add=add_shot,
                               on_remove=lambda i, w: props().queue.remove(i), add_label="Add shot",
                               empty="No shots yet. Add one below."),
                title="Render queue", subtitle="Drag the handle to reorder (a CollectionProperty)", icon="drag",
                collapsible=True, key="card_queue"),
        ui.Card(ui.Accordion([
            ("Lighting", ui.Label("Three-point setup with a warm key and cool rim.", wrap=True, muted=True), "light"),
            ("Camera", ui.Label("35 mm, f/2.8, slight Dutch angle.", wrap=True, muted=True), "camera"),
            ("Output", ui.Label("1920 × 1080, 24 fps, EXR multilayer.", wrap=True, muted=True), "download"),
        ], key="accordion"), title="Accordion", icon="layers", collapsible=True, key="card_acc"),
        ui.Card(ui.SplitPane(ui.Column(section("Inputs"), ui.Label("Mesh"), ui.Label("Texture"), gap=4),
                             ui.Column(section("Outputs"), ui.Label("GLB"), ui.Label("Preview"), gap=4),
                             ratio=0.5, key="split"),
                title="Split pane", subtitle="Drag the middle handle", icon="drawer", collapsible=True,
                key="card_split"),
        ui.Card(ui.Skeleton(lines=3, avatar=True), ui.Skeleton(lines=2, image=True, image_height=70),
                title="Loading skeletons", icon="refresh", collapsible=True, key="card_skel"),
        ui.Card(ui.EmptyState("No renders yet", "Finished renders show up here. Start one from the Data page.",
                              icon="image", action="Start render", on_action=lambda b: run_job()),
                title="Empty state", icon="inbox", collapsible=True, key="card_empty"),
        gap=12,
    )


# ---------------------------------------------------------------------------
# 7. Overlays
# ---------------------------------------------------------------------------

_bar = {"win": None}


def toggle_quick_bar(button=None):
    view = app.first_viewport()
    w = _bar["win"]
    if w is not None and w in view.overlays:
        w.close()
        _bar["win"] = None
        return
    bar = ui.Card(
        ui.Row(ui.Icon("sparkles", size=17, color="accent"),
               ui.TextInput("Ask Uzima to create…", bind="scene.uzima_demo.prompt", variant="bare",
                            clearable=False, on_submit=lambda text, field: generate()),
               ui.Segmented([(i, "", ic) for i, _n, ic in KINDS], bind="scene.uzima_demo.kind", width=118),
               ui.PreviewDropdown(bind="scene.uzima_demo.look", images=LOOK_IMAGES, thumb=22, width=120,
                                  menu_width=300, grid_cols=3),
               ui.IconButton("arrow_up", variant="primary", on_click=generate, tooltip="Create\nOr press Enter."),
               gap=10),
        variant="raised", padding=9)
    _bar["win"] = view.window(ui.Window(bar, chrome=False, width=620, anchor="top", offset=(0, -14), scroll=False,
                                        transparent=True, padding=0, closable=False))


def open_inspector(button=None):
    body = ui.Column(
        ui.Props("object", ["name", "location", "rotation_euler", "scale"], empty="Select an object"),
        ui.PreviewDropdown(bind="scene.uzima_demo.look", images=LOOK_IMAGES, label="Look", grid_cols=3),
        ui.Row(ui.Button("Close", variant="ghost"), ui.Button("Apply", variant="primary", icon="check",
               on_click=lambda b: app.toast("Changes applied", kind="success")), gap=8),
        gap=10)
    app.window(body, title="Inspector", icon="sliders", width=320, height=470, anchor="right")


def open_drawer(button=None):
    app.drawer(ui.Column(
        ui.Props("scene.render", ["engine", "resolution_x", "resolution_y", "resolution_percentage",
                                  "film_transparent", "filepath"]),
        ui.Button("Render image", icon="camera", variant="primary",
                  on_click=lambda b: ui.run_operator("render.render", invoke=True),
                  tooltip="Render image\nOpens Blender's render window"),
        gap=10), title="Render settings", icon="camera")


CONTEXT_MENU = [
    ui.MenuItem("Add", icon="plus", submenu=[
        ui.MenuItem("Cube", icon="cube", operator="mesh.primitive_cube_add"),
        ui.MenuItem("Sphere", icon="sphere", operator="mesh.primitive_uv_sphere_add"),
        ui.MenuItem("Monkey", icon="mesh", action="add_monkey"),
    ]),
    ui.MenuItem("Shade smooth", icon="sphere", operator="object.shade_smooth", shortcut="Right-click"),
    ui.MenuItem("Object labels", icon="tag", checked=lambda: labels_tool in app.first_viewport().overlays,
                action="toggle_labels"),
    ui.MenuSeparator("Danger zone"),
    ui.MenuItem("Delete selected", icon="trash", danger=True, operator="object.delete", props={"confirm": False}),
]


def page_overlays():
    windows = ui.Card(
        ui.Button("Quick create bar", icon="sparkles", variant="primary", on_click=toggle_quick_bar),
        ui.Grid(ui.Button("Inspector", icon="window", on_click=open_inspector),
                ui.Button("Drawer", icon="drawer", on_click=open_drawer),
                ui.Button("Palette", icon="command", action="command_palette", tooltip="Ctrl Shift P"),
                ui.Button("Pie menu", icon="pie", action="quick_pie", tooltip="Ctrl Shift Q"), cols=2, gap=6),
        ui.Grid(ui.Button("Dialog", icon="info", on_click=lambda b: app.dialog(
                    "Create 4 variants?", "This will use 12 credits.", confirm="Create",
                    on_confirm=lambda d: generate())),
                ui.Button("Form dialog", icon="edit", on_click=lambda b: app.dialog(
                    "Save preset", "Store the current settings as a preset.", confirm="Save",
                    content=ui.Column(ui.TextInput("Preset name", value="Neon night", clearable=False),
                                      ui.Checkbox("Share with team", value=True), gap=8),
                    on_confirm=lambda d: app.toast("Preset saved", kind="success"))), cols=2, gap=6),
        ui.Button("Take the tour", icon="help", variant="soft", on_click=start_tour),
        title="Windows, drawers and dialogs", icon="window", collapsible=True, key="card_windows",
    )
    toasts = ui.Card(
        ui.Grid(ui.Button("Success", variant="success", on_click=lambda b: app.toast(
                    "Render finished", "Frame 120 saved.", "success")),
                ui.Button("Info", on_click=lambda b: app.toast("Syncing", "Uploading 3 assets…", "info")),
                ui.Button("Warning", on_click=lambda b: app.toast("Low credits", "12 credits left.", "warning")),
                ui.Button("Error", variant="danger", on_click=lambda b: app.toast(
                    "Creation failed", "The engine timed out.", "danger", action="Retry",
                    on_action=lambda t: generate())), cols=2, gap=6),
        ui.Label("Every toast is kept in the bell at the top of the panel.", muted=True, size=10.5, wrap=True),
        title="Toasts and notifications", icon="bell", collapsible=True, key="card_toasts",
    )
    menus = ui.Card(
        ui.Card(ui.Label("Right-click anywhere in this box.", align="center", muted=True), ui.Spacer(18),
                variant="outline", context_menu=CONTEXT_MENU, tooltip="Right-click me"),
        title="Context menus", subtitle="Sub-menus, check marks, shortcuts, separators", icon="menu",
        collapsible=True, key="card_menus",
    )
    tools = ui.Card(
        ui.Switch(bind=tool_bind(labels_tool, "Object labels"), description="Name and size above selected objects"),
        ui.Switch(bind=tool_bind(ruler_tool, "Ruler"), description="Active object to the other selected one"),
        ui.Switch(bind=tool_bind(hud_tool, "Stats HUD"), description="Draggable FPS and scene counts"),
        ui.Switch(bind=tool_bind(toolbar_tool, "Selection toolbar"), description="Quick actions above the selection"),
        title="Viewport tools", subtitle="Drawn in the 3D view", icon="globe", collapsible=True, key="card_tools",
    )
    return ui.Column(windows, toasts, menus, tools, gap=12)


# ---------------------------------------------------------------------------
# 8. Blender (auto widgets, forms, operators, code)
# ---------------------------------------------------------------------------

def page_blender():
    return ui.Column(
        ui.Props("object", ["name", "location", "rotation_euler", "scale", "color", "parent", "hide_render"],
                 title="Active object", subtitle="ui.Props(\"object\", [...])", icon="cube", empty="Select an object",
                 key="props_obj"),
        ui.Props("object.data", ["energy", "color", "shadow_soft_size"], title="Light", icon="light",
                 styles={"energy": "slider"}, visible=lambda: obj() is not None and obj().type == "LIGHT"),
        ui.Props("object.data", ["lens", "clip_start", "clip_end"],
                 title="Camera", icon="camera", visible=lambda: obj() is not None and obj().type == "CAMERA"),
        ui.Card(ui.Form(ui.Prop("scene.render.resolution_x"), ui.Prop("scene.render.resolution_y"),
                        ui.Prop("scene.render.fps"), ui.Prop("scene.render.engine"), title="Output",
                        on_apply=lambda f: app.toast("Output updated", "One undo step.", "success")),
                title="Form", subtitle="Changes wait for Apply · one undo step", icon="success",
                collapsible=True, key="card_form"),
        ui.Card(ui.Grid(ui.Button("Monkey", icon="mesh", action="add_monkey"),
                        ui.Button("Smooth", icon="sphere", operator="object.shade_smooth"),
                        ui.Button("Apply scale", icon="maximize", operator="object.transform_apply",
                                  props={"location": False, "rotation": False, "scale": True}),
                        ui.Button("Frame", icon="target", operator="view3d.view_selected"), cols=2, gap=6),
                title="Operators and actions", icon="bolt", collapsible=True, key="card_ops"),
        ui.Card(ui.Code('''from . import uzima as ui

app = ui.App("my_addon")

@app.action("hello", label="Say hello", hotkey="ctrl+H")
def hello(context):
    app.toast("Hello", context.object.name)

def build(surface):
    return ui.Column(
        ui.Prop("object.location"),          # right widget per type
        ui.Prop("scene.render.engine"),
        ui.Button("Hello", action="hello"),
        ui.Button("Cube", operator="mesh.primitive_cube_add"),
    )

app.sidebar("My Tool", build=build)
app.viewport()''', title="your_addon/__init__.py"),
                title="Code", icon="command", collapsible=True, key="card_code"),
        gap=12,
    )


# ---------------------------------------------------------------------------
# 9. Theme
# ---------------------------------------------------------------------------

def page_theme():
    th = app.theme
    return ui.Column(
        ui.Card(ui.Dropdown(list(ui.THEME_PRESETS), value=th.preset, label="Preset", icon="palette",
                            on_change=lambda v, w: (app.theme.load_preset(v), ui.request_redraw())),
                section("Accent"),
                ui.ColorSwatches([ui.hex_color(h) for h in ACCENTS], bind="scene.uzima_demo.accent",
                                 on_change=lambda v, w: app.theme.set(accent=v)),
                ui.ColorField("Custom accent", bind=ui.Bind.fn(lambda: app.theme.accent[:3],
                                                                lambda c: app.theme.set(accent=c), "Accent")),
                title="Colors", icon="palette", collapsible=True, key="card_colors_theme"),
        ui.Card(ui.Switch(bind=ui.Bind.fn(lambda: app.theme.gradients, lambda v: app.theme.set(gradients=v),
                                          "Gradients"), description="Off = every element uses flat colors"),
                ui.Switch(bind=ui.Bind.fn(lambda: app.theme.shadows, lambda v: app.theme.set(shadows=v),
                                          "Shadows and glows")),
                ui.Slider("Animation speed", bind=ui.Bind.fn(lambda: app.theme.speed, lambda v: app.theme.set(speed=v)),
                          min=6, max=40, precision=0),
                section("Per element: theme vs gradient=False vs gradient=True"),
                ui.Row(ui.Button("Theme", variant="hero"), ui.Button("Flat", variant="hero", gradient=False),
                       ui.Button("Always", variant="hero", gradient=True), gap=6),
                ui.Row(ui.Slider("Default", value=0.6), ui.Slider("Flat", value=0.6, gradient=False, shadows=False),
                       gap=8),
                title="Style", subtitle="Gradients and shadows on or off", icon="sliders", collapsible=True,
                key="card_style"),
        ui.Card(ui.Code('''app.theme.set(accent="#9fbd97")
app.theme.set(gradients=False, shadows=False)
app.theme.load_preset("Midnight")
app.theme.save("/path/my_theme.json")
ui.Button("Flat", variant="hero", gradient=False)''', title="Theme in code"),
                title="Code", icon="command", collapsible=True, key="card_theme_code"),
        gap=12,
    )


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

class Logo(ui.Widget):
    def natural_width(self, ctx):
        return ctx.px(34)

    def measure(self, ctx, avail_w):
        return ctx.px(34), ctx.px(34)

    def paint(self, ctx, p):
        th = ctx.theme
        x, y, w, h = self.rect
        p.shadow(x, y, w, h, ctx.px(10), ui.alpha(th.accent, 0.35), ctx.px(10))
        p.rect(x, y, w, h, fill=th.accent_lo, fill2=th.accent_hi, radius=ctx.px(10))
        p.sparkle(x + w / 2, y + h / 2, w * 0.3, th.accent_text, 0.62)


def build_sidebar(surface):
    header = ui.Row(
        Logo(width="auto"),
        ui.Column(ui.Label("Uzima UI", weight="semibold", size=14.5),
                  ui.Label("Component library · v%s" % ui.__version__, muted=True, size=10.5), gap=1, flex=1),
        ui.NotificationBell(key="bell", tooltip="Notifications"),
        ui.IconButton("command", tooltip="Command palette\nCtrl Shift P", action="command_palette"),
        gap=8,
    )
    nav = ui.SideNav([
        ui.Tab("Create", page_create(), icon="sparkles"),
        ui.Tab("Controls", page_controls(), icon="sliders"),
        ui.Tab("Inputs", page_inputs(), icon="edit"),
        ui.Tab("Data", page_data(), icon="chart"),
        ui.Tab("Media", page_media(), icon="image"),
        ui.Tab("Layout", page_layout(), icon="layers"),
        ui.Tab("Overlays", page_overlays(), icon="window"),
        ui.Tab("Blender", page_blender(), icon="cube"),
        ui.Tab("Theme", page_theme(), icon="palette"),
    ], key="nav", rail=40)
    footer = ui.Row(
        ui.Label(lambda: "%d objects · %s" % (len(bpy.context.scene.objects),
                                                  bpy.context.scene.render.engine.replace("BLENDER_", "").title()),
                 muted=True, size=10.5),
        create_button(size="sm", width="auto"),
        gap=8,
    )
    return ui.Scaffold(nav, header=header, footer=footer)
