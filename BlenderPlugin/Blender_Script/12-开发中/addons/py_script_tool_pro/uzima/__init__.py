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

"""Uzima UI: a custom-drawn, web-style UI library for Blender 5.

Copy this `uzima` folder into your add-on and import it relatively:

    from . import uzima as ui

    app = ui.App("my_addon")

    def build(surface):
        return ui.Column(
            ui.Heading("Hello", "My first Uzima panel"),
            ui.Button("Create", variant="hero", cost=3, on_click=lambda b: app.toast("Done")),
            ui.Slider("Strength", bind="scene.my_props.strength"),
        )

    app.sidebar("My Tab", build=build)
    app.viewport()

    def register():
        app.register()

    def unregister():
        app.unregister()
"""

__version__ = "2.0.0"

from .theme import Theme, DEFAULT, COLOR_KEYS, hex_color, to_color, to_hex, alpha, mix, lighten, darken
from .core import Widget, Bind, Event, call
from .layout import (Column, Row, Flow, Grid, Card, ScrollView, TabView, TabBar, Tab, Spacer,
                     Separator)
from .widgets import (Label, Heading, Icon, Button, IconButton, Chip, Badge, Checkbox, Switch,
                      RadioGroup, Segmented, Slider, NumberField, TextInput, Dropdown, ProgressBar,
                      Spinner, ImageBox, AssetCard, ListView, ColorSwatches, Avatar, Alert, KeyValue,
                      Rating, PreviewGrid, PreviewDropdown)
from .core import FuncBind
from .overlays import Overlay, Menu, MenuItem, MenuSeparator, Popover, Tooltip, Toast, Window, Dialog
from .host import App, Surface, request_redraw, ui_scale
from .draw import Painter, load_font, font_id
from .actions import Action, Hotkey
from .inputs import (ColorField, ColorPickerPanel, VectorField, RangeSlider, Knob, Stepper, ToggleGroup, TagInput,
                     SearchField, DataPicker, FilePathField, HotkeyField, id_icon, srgb_to_linear, linear_to_srgb)
from .data import (CurveEditor, ColorRampEditor, LineChart, BarChart, Sparkline, StatTile, Table, TableColumn,
                   TreeView, TreeNode, TreeToggle, Steps, RingProgress, Histogram, CURVE_PRESETS)
from .media import ViewportPreview, BeforeAfter, Carousel, FrameScrubber, DropZone, keyframe_frames
from .navigation import Accordion, SideNav, Breadcrumbs, Pagination, SplitPane, Scaffold, ReorderList
from .feedback import (CommandPalette, PieMenu, Drawer, Tour, NotificationBell, Banner, Skeleton, EmptyState,
                       HoldButton)
from .viewport import ObjectLabels, Ruler, HUD, SelectionToolbar, scene_stats
from .forms import Prop, Props, Form, Code, resolve
from .theme import PRESETS as THEME_PRESETS
from . import icons


def run_operator(idname, area_type="VIEW_3D", invoke=False, **props):
    """Run a Blender operator from a widget callback with a valid area context.

        ui.run_operator("mesh.primitive_monkey_add", size=1.5)
        ui.run_operator("object.delete", invoke=True)      # INVOKE_DEFAULT (may show a popup)
    """
    import bpy
    mod, name = idname.split(".", 1)
    op = getattr(getattr(bpy.ops, mod), name)
    if invoke:
        _op = op
        op = lambda **kw: _op("INVOKE_DEFAULT", **kw)
    wm = bpy.context.window_manager
    for win in wm.windows:
        scr = win.screen
        if scr is None:
            continue
        for area in scr.areas:
            if area.type == area_type:
                region = next((r for r in area.regions if r.type == "WINDOW"), None)
                with bpy.context.temp_override(window=win, area=area, region=region):
                    return op(**props)
    return op(**props)
