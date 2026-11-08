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

"""Demo: Blender properties, the Uzima app, actions (with hotkeys) and helpers.
Pages live in demo_pages.py; registration in __init__.py."""

import os
import random

import bpy
from bpy.props import (BoolProperty, CollectionProperty, EnumProperty, FloatProperty, FloatVectorProperty,
                       IntProperty, PointerProperty, StringProperty)

from . import uzima as ui

HERE = os.path.dirname(__file__)


def asset(name):
    return os.path.join(HERE, "assets", name + ".png")


# ---------------------------------------------------------------------------
# Properties the demo binds to
# ---------------------------------------------------------------------------

KINDS = [("MESH", "Mesh", "cube"), ("SCENE", "Scene", "layers"), ("IMAGE", "Image", "image")]
LOOKS = [
    ("NEON", "Neon", "Wet streets, glowing signs", "rooftop"),
    ("STUDIO", "Studio", "Clean product lighting", "car"),
    ("CLAY", "Clay", "Matte grey blockout", "character"),
    ("DUSK", "Dusk", "Warm low sun, long shadows", "landscape"),
    ("COZY", "Cozy", "Soft interior daylight", "interior"),
    ("DREAM", "Dream", "Abstract light and haze", "abstract"),
]
ENVS = [("CITY", "City night", "rooftop"), ("DESERT", "Desert", "landscape"), ("LOFT", "Loft", "interior"),
        ("VOID", "Void", "abstract")]
ACCENTS = ("#9fbd97", "#8fb4d9", "#b9a3e3", "#e3a3c4", "#e8b25a", "#e88a6a", "#6cc4b0", "#d9d2c3")
LOOK_IMAGES = {i: asset(img) for i, _n, _d, img in LOOKS}
ENV_IMAGES = {i: asset(img) for i, _n, img in ENVS}


class UzimaQueueItem(bpy.types.PropertyGroup):
    name: StringProperty(name="Name", default="Shot")
    enabled: BoolProperty(name="Enabled", default=True)
    frames: IntProperty(name="Frames", default=120, min=1)


class UzimaDemoProps(bpy.types.PropertyGroup):
    prompt: StringProperty(name="Prompt", default="A small lighthouse on a rocky island at dusk")
    kind: EnumProperty(name="Type", items=[(i, n, "") for i, n, _ in KINDS], default="MESH")
    look: EnumProperty(name="Look", default="DUSK", items=[(i, n, d) for i, n, d, _ in LOOKS])
    env: EnumProperty(name="Environment", default="CITY", items=[(i, n, "") for i, n, _ in ENVS])
    model: EnumProperty(name="Engine", default="UZ_MESH", items=[
        ("UZ_MESH", "Uzima Mesh v2", "Clean quads, UVs and PBR textures"),
        ("UZ_SCULPT", "Uzima Sculpt", "Dense, high-detail surfaces"),
        ("UZ_DRAFT", "Uzima Draft", "Fast low-poly drafts for blockouts"),
        ("UZ_SCENE", "Uzima Scene", "Lays out whole scenes with lights"),
        ("LOCAL", "Local (offline)", "Runs on your own GPU"),
    ])
    mode: EnumProperty(name="Mode", default="FULL", items=[
        ("FULL", "Full", "Mesh, UVs and textures"), ("PREVIEW", "Preview", "Fast untextured mesh"),
        ("REFINE", "Refine", "Improve the selected mesh")])
    quality: EnumProperty(name="Quality", default="BALANCED", items=[
        ("DRAFT", "Draft", "Fastest, good for blockouts"),
        ("BALANCED", "Balanced", "Best mix of speed and detail"),
        ("BEST", "Best", "Slow, highest detail")])
    view: EnumProperty(name="View", default="GRID", items=[("GRID", "Grid", ""), ("LIST", "List", ""),
                                                           ("WALL", "Wall", "")])
    formats: EnumProperty(name="Export formats", options={"ENUM_FLAG"}, default={"GLB", "USD"}, items=[
        ("GLB", "glTF", "", 1), ("FBX", "FBX", "", 2), ("USD", "USD", "", 4), ("OBJ", "OBJ", "", 8)])
    strength: FloatProperty(name="Prompt strength", default=0.65, min=0, max=1, subtype="FACTOR")
    detail: FloatProperty(name="Detail", default=0.5, min=0, max=1, subtype="FACTOR")
    samples: IntProperty(name="Samples", default=64, min=1, max=256)
    variants: IntProperty(name="Variants", default=1, min=1, max=4)
    seed: IntProperty(name="Seed", default=1337, min=0, max=99999)
    auto_uv: BoolProperty(name="Auto UV unwrap", default=True)
    pbr: BoolProperty(name="PBR textures", default=True)
    notify: BoolProperty(name="Notify when done", default=True)
    rating: IntProperty(name="Rating", default=4, min=0, max=5)
    api_key: StringProperty(name="API key", default="", subtype="PASSWORD")
    notes: StringProperty(name="Notes", default="")
    tags: StringProperty(name="Tags", default="lighthouse, dusk, rocks")
    reference: StringProperty(name="Reference image", default="", subtype="FILE_PATH")
    target: PointerProperty(name="Target object", type=bpy.types.Object)
    material: PointerProperty(name="Material", type=bpy.types.Material)
    accent: FloatVectorProperty(name="Accent", subtype="COLOR_GAMMA", size=3, min=0, max=1,
                                default=(0.624, 0.741, 0.592))
    queue: CollectionProperty(type=UzimaQueueItem)
    queue_index: IntProperty(name="Active shot", default=0)


CLASSES = (UzimaQueueItem, UzimaDemoProps)


def props():
    return bpy.context.scene.uzima_demo


# ---------------------------------------------------------------------------
# The app
# ---------------------------------------------------------------------------

app = ui.App("uzima_demo")


def generate(button=None):
    """Simulated creation: spin the button, then add real objects to the scene."""
    p = props()
    btns = [button] if isinstance(button, ui.Button) else []
    for b in btns:
        b.loading = True
    kind = p.kind
    prompt = p.prompt.strip() or "Untitled"
    seed = p.seed

    def finish():
        for b in btns:
            b.loading = False
        if kind == "SCENE":
            ui.run_operator("mesh.primitive_plane_add", size=12, location=(0, 0, 0))
            rnd = random.Random(seed)
            for _i in range(6):
                ui.run_operator("mesh.primitive_cube_add", size=rnd.uniform(0.6, 2.2),
                                location=(rnd.uniform(-4, 4), rnd.uniform(-4, 4), 1.0))
            app.toast("Scene ready", "Added a ground plane and 6 blocks.", "success")
        elif kind == "MESH":
            ui.run_operator("mesh.primitive_monkey_add", size=1.6, location=bpy.context.scene.cursor.location)
            ob = bpy.context.view_layer.objects.active
            if ob:
                ob.name = prompt[:24]
                if ob.type == "MESH":
                    ui.run_operator("object.shade_smooth")
            app.toast("Mesh created", "“%s” added at the 3D cursor." % prompt[:40], "success")
        else:
            app.toast("Image queued", "Image creation is only simulated in this demo.", "info")
        ui.request_redraw()
        return None

    bpy.app.timers.register(finish, first_interval=1.3)


def select_object(obj, *_args):
    ev = _args[1] if len(_args) > 1 else None
    if obj is None:
        return
    if not (ev is not None and getattr(ev, "shift", False)):
        for o in bpy.context.view_layer.objects:
            o.select_set(False)
    try:
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
    except RuntimeError:
        app.toast("Can't select", "%s isn't in the current view layer." % obj.name, "warning")


# ---------------------------------------------------------------------------
# Demo node group: real CurveMapping and ColorRamp for the curve / ramp editors
# ---------------------------------------------------------------------------

NODE_GROUP = ".Uzima Demo Nodes"


def ensure_demo_nodes():
    """Create a hidden node group holding a Float Curve and a Color Ramp node (outside of drawing)."""
    try:
        ng = bpy.data.node_groups.get(NODE_GROUP)
        if ng is None:
            ng = bpy.data.node_groups.new(NODE_GROUP, "ShaderNodeTree")
            ng.use_fake_user = True
            c = ng.nodes.new("ShaderNodeFloatCurve")
            c.name = "Curve"
            pts = c.mapping.curves[0].points
            pts[0].location = (0.0, 0.0)
            pts[1].location = (1.0, 1.0)
            pts.new(0.3, 0.12)
            pts.new(0.7, 0.9)
            c.mapping.update()
            r = ng.nodes.new("ShaderNodeValToRGB")
            r.name = "Ramp"
            el = r.color_ramp.elements
            el[0].color = (0.008, 0.009, 0.012, 1)
            el[1].color = (0.9, 0.92, 0.88, 1)
            mid = el.new(0.55)
            mid.color = (0.35, 0.5, 0.31, 1)
    except Exception as e:
        print("Uzima demo: could not create demo nodes", e)
    return None


def demo_curve():
    ng = bpy.data.node_groups.get(NODE_GROUP)
    n = ng.nodes.get("Curve") if ng else None
    return n.mapping if n else None


def demo_ramp():
    ng = bpy.data.node_groups.get(NODE_GROUP)
    n = ng.nodes.get("Ramp") if ng else None
    return n.color_ramp if n else None


# ---------------------------------------------------------------------------
# Viewport tools (toggled from the Overlays page and from actions)
# ---------------------------------------------------------------------------

labels_tool = ui.ObjectLabels(text=lambda o: "%.2f × %.2f × %.2f m" % tuple(o.dimensions))
ruler_tool = ui.Ruler()
hud_tool = ui.HUD()
toolbar_tool = ui.SelectionToolbar()


def tool_bind(tool, label):
    view = app.first_viewport()
    return ui.Bind.fn(lambda: tool in view.overlays, lambda v: app.viewport_tool(tool, v), label)


# ---------------------------------------------------------------------------
# Actions: run from buttons, menus, the command palette and Blender's keymap
# ---------------------------------------------------------------------------

PIE_ITEMS = [
    ui.MenuItem("Add cube", icon="cube", operator="mesh.primitive_cube_add"),
    ui.MenuItem("Add sphere", icon="sphere", operator="mesh.primitive_uv_sphere_add"),
    ui.MenuItem("Add camera", icon="camera", operator="object.camera_add"),
    ui.MenuItem("Add light", icon="light", operator="object.light_add", props={"type": "POINT"}),
    ui.MenuItem("Shade smooth", icon="sphere", operator="object.shade_smooth"),
    ui.MenuItem("Frame selected", icon="target", operator="view3d.view_selected"),
    ui.MenuItem("Create", icon="sparkles", on_click=lambda *_: generate()),
    ui.MenuItem("Palette", icon="command", action="command_palette"),
]


@app.action("command_palette", label="Command palette", icon="command", hotkey="ctrl+shift+P",
            description="Search Uzima actions and every Blender operator")
def _palette(context, info):
    app.command_palette(info)


@app.action("quick_pie", label="Quick pie menu", icon="pie", hotkey="ctrl+shift+Q",
            description="Radial menu at the mouse")
def _pie(context, info):
    app.pie(PIE_ITEMS, info, title="Uzima")


@app.action("create", label="Create from prompt", icon="sparkles", description="Run the Create page with its prompt")
def _create(context):
    generate()


@app.action("toggle_hud", label="Toggle stats HUD", icon="chart", description="FPS, vertices and triangles")
def _hud(context):
    app.viewport_tool(hud_tool, hud_tool not in app.first_viewport().overlays)


@app.action("toggle_labels", label="Toggle object labels", icon="tag", description="Name tags above objects")
def _labels(context):
    app.viewport_tool(labels_tool, labels_tool not in app.first_viewport().overlays)


@app.action("toggle_ruler", label="Toggle ruler", icon="ruler", description="Distance between selected objects")
def _ruler(context):
    app.viewport_tool(ruler_tool, ruler_tool not in app.first_viewport().overlays)


@app.action("add_monkey", label="Add Suzanne", icon="mesh", description="Adds a monkey at the 3D cursor")
def _monkey(context):
    ui.run_operator("mesh.primitive_monkey_add")


@app.action("start_tour", label="Take the tour", icon="help", description="Walk through the sidebar")
def _tour(context):
    start_tour()


def start_tour(*_):
    side = app.surfaces[0]
    nav = side.root.find("nav") if side.root else None
    if nav is not None:
        nav.select(0)
    app.tour([
        ("nav", "Pages", "Every Uzima element lives on one of these pages. Hover an icon to see its name."),
        ("prompt", "Prompt", "Type what you want to make. It is a real Blender property, saved with the file."),
        ("look", "Preview enum", "Pick a look from thumbnails. It is bound to an EnumProperty."),
        ("create_btn", "Create", "Adds real objects to your scene. Try Ctrl Shift P for the command palette."),
        ("bell", "Notifications", "Every toast is kept here so nothing gets lost."),
    ], surface=side)
