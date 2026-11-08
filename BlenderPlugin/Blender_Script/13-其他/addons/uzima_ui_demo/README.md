# Uzima UI 2.0

A custom-drawn, web-style UI library for Blender 5 (works from 4.2). Every pixel is drawn with
Blender's `gpu` module: rounded cards, optional gradients and glows, animated controls, custom fonts.
It lives in the **N panel** (its own sidebar tab) and **over the 3D viewport** (windows, drawers,
dialogs, menus, a command palette, a pie menu, toasts, and tools drawn in 3D space).

It is not just looks: every value widget binds to real Blender properties with undo, buttons and menus
run operators, actions get real keymap entries, pickers select real objects and materials, and the
curve and ramp editors edit real node data.

This package contains:

- `uzima/`: the library. Copy this folder into any add-on.
- `__init__.py`, `demo_core.py`, `demo_pages.py`: the demo add-on (every element, wired to Blender).
- `assets/`: sample images for the demo. `tools/`: headless preview renderer and interaction tests.

## Install the demo

Blender 5: **Edit > Preferences > Get Extensions > ⌄ (top right) > Install from Disk** and pick the zip
(or drag the zip into Blender). Open the 3D viewport sidebar (**N**), click the **Uzima** tab and use the
icon rail on the left to switch pages: Create, Controls, Inputs, Data, Media, Layout, Overlays, Blender,
Theme. **Ctrl Shift P** opens the command palette and **Ctrl Shift Q** the pie menu (change both on the
Inputs page). The **Overlays** page has a guided tour.

## Use it in your own add-on

```python
import bpy
from . import uzima as ui

app = ui.App("my_addon")            # unique id: keeps your panel / operator / keymap names separate

@app.action("add_lamp", label="Add lamp", icon="light", hotkey="ctrl+shift+L")
def add_lamp(context):
    bpy.ops.object.light_add(type="POINT")

def build(surface):
    return ui.Column(
        ui.Prop("object.location"),                     # the right widget for any property
        ui.Prop("scene.render.engine"),
        ui.Slider(bind="scene.my_props.strength"),
        ui.Button("Add lamp", action="add_lamp"),
        ui.Button("Cube", operator="mesh.primitive_cube_add", props={"size": 2}),
    )

app.sidebar("My Tool", build=build)    # an N-panel tab
app.viewport()                         # windows / dialogs / palette / viewport tools over the 3D view

def register():
    # register your PropertyGroups first, then:
    app.register()

def unregister():
    app.unregister()
```

`build(surface)` runs the first time the tab is drawn; `surface.rebuild()` builds it again. For a panel with
a fixed header and footer, return `ui.Scaffold(body, header=..., footer=...)`.

## Working with Blender

| What | How |
|---|---|
| Bind any widget to a property | `bind="scene.render.resolution_x"` (path from `bpy.context`) or `ui.Bind(lambda: obj, "location", index=2)` |
| Bind to anything else | `ui.Bind.fn(getter, setter, "Label")` |
| Automatic widget for a property | `ui.Prop("object.color")`, `ui.Prop(ui.Bind(...), style="knob")` |
| A panel of properties | `ui.Props("scene.render", ["engine", "resolution_x"])`, `ui.Props("scene.my_group")` (all of them) |
| Apply-together edits, one undo step | `ui.Form(ui.Prop(...), ui.Prop(...), title="Output", on_apply=...)` |
| Run an operator | `ui.Button(..., operator="object.shade_smooth")`, `ui.MenuItem(..., operator=...)`, `ui.run_operator(idname, invoke=True, **props)` |
| Named actions with hotkeys | `@app.action(name, label, icon, hotkey="ctrl+shift+L")`, `app.run_action(name)`, `app.set_hotkey(name, "alt+L")` |
| File browser | `ui.FilePathField(bind=..., mode="FILE" or "DIR")`, `app.browse(callback, mode, filter)` |
| Pick in the viewport | `app.pick_object(callback)` (ray cast), `app.pick_color(callback)` (samples the rendered view) |
| Pick data-blocks | `ui.DataPicker(bind=...)` for PointerProperties, or `collection="materials"`, `filter=...` |
| Live text and visibility | `ui.Label(lambda: ...)`, `visible=lambda: bpy.context.object is not None`, `enabled=lambda: ...` |
| Saved UI state | any widget with `key=` (tabs, cards, side nav, tree...) restores its state from the .blend |

`Prop` picks: Switch for booleans, ToggleGroup for boolean arrays and flag enums, Dropdown for enums,
VectorField for vectors (rotation in degrees), ColorField for colors (scene-linear handled), Slider or
NumberField for numbers, FilePathField for paths, DataPicker for data-block pointers. When the owner
changes (a different active object), it rebinds by itself.

## Elements

**Layout and navigation:** `Column`, `Row`, `Flow`, `Grid`, `Card` (collapsible, `variant=` default /
raised / outline / ghost / composer), `ScrollView`, `TabView` / `TabBar`, `SideNav` (icon rail), `Accordion`,
`Breadcrumbs`, `Pagination`, `SplitPane` (draggable), `Scaffold` (pinned header / footer), `Spacer`, `Separator`.

**Buttons and toggles:** `Button` (variants `hero`, `primary`, `secondary`, `outline`, `ghost`, `soft`,
`danger`, `success`; `operator=`, `action=`, `cost=`, `loading=`, `toggle=`), `IconButton`, `HoldButton`
(press and hold to confirm), `Chip`, `Badge`, `Checkbox`, `Switch`, `RadioGroup`, `Segmented`, `ToggleGroup`
(multi-select), `Rating`.

**Inputs:** `TextInput` (multiline, password), `SearchField` (suggestions), `TagInput`, `NumberField`,
`Slider`, `RangeSlider`, `Knob`, `Stepper`, `VectorField`, `Dropdown` (searchable enum popover),
`PreviewGrid` / `PreviewDropdown` (preview enums; file paths, bpy images or `bpy.utils.previews`),
`ColorField` + `ColorPickerPanel` (saturation square, hue, alpha, hex, eyedropper, recent colors),
`ColorSwatches`, `DataPicker`, `FilePathField`, `HotkeyField`.

**Data:** `CurveEditor` (Blender CurveMapping or a point list, presets), `ColorRampEditor` (Blender ColorRamp
or stops), `LineChart`, `BarChart`, `Sparkline`, `StatTile`, `Table` (sortable, selectable, toggle columns),
`TreeView` (expand, select, toggles), `Steps`, `RingProgress`, `ProgressBar`, `Spinner`, `Histogram`,
`KeyValue`, `ListView`.

**Media:** `ImageBox`, `AssetCard`, `Avatar`, `ViewportPreview` (live render through the camera or view),
`BeforeAfter`, `Carousel`, `FrameScrubber` (frame range, keyframes, markers, play), `DropZone`.

**Feedback:** `Alert`, `Banner`, `Skeleton`, `EmptyState`, `NotificationBell`, toasts, tooltips.

**Overlays:** `app.window(...)` (draggable, resizable), `app.dialog(...)`, `app.drawer(...)`,
`app.command_palette()` (your actions + every Blender operator), `app.pie(items)`, `app.tour(steps)`,
`surface.open_popover(...)`, `ui.Menu` with `ui.MenuItem` (icons, shortcuts, check marks, sub-menus,
separators, danger items) and right-click menus on any widget with `context_menu=[...]`.

**Viewport tools:** `ui.ObjectLabels()`, `ui.Ruler()`, `ui.HUD()`, `ui.SelectionToolbar()`; show them with
`app.viewport_tool(tool, True)`.

## Theme, gradients and shadows

```python
app = ui.App("my_addon", theme=ui.Theme(accent="#7c5cff"))
app.theme.set(accent="#e8b25a")              # hover / glow / focus shades are derived
app.theme.set(gradients=False)               # every element flat
app.theme.set(shadows=False)                 # no shadows or glows
app.theme.load_preset("Midnight")            # "Uzima Dark", "Midnight", "Even Darker", "Darkest", "Sand", "Monokai", "Atom One Dark", "Light"
app.theme.save(path); app.theme.load(path)   # JSON
ui.Button("Flat", variant="hero", gradient=False)   # per element: None = theme, True / False = forced
ui.Label("Note", color="accent")             # theme color names follow theme changes
```

Color slots (`ui.COLOR_KEYS`): `bg`, `surface_0`–`surface_4`, `selected`, `overlay`, `border`, `border_strong`,
`border_focus`, `text`, `text_dim`, `text_muted`, `text_disabled`, `accent`, `accent_hi`, `accent_lo`,
`accent_edge`, `accent_text`, `accent_soft`, `info`, `success`, `warning`, `danger`.

## Keyboard

Hover the panel and press **Tab** to move between controls (Shift Tab back), **Enter** or **Space** to press,
**arrow keys** to change sliders, knobs, choices and pages, **Esc** to leave. Blender's own shortcuts keep
working everywhere else.

## Custom widgets

Subclass `ui.Widget`, return a size from `measure(ctx, avail_w)` and draw in `paint(ctx, p)` with the painter:
`rect` (rounded, per-corner radii, gradients, borders), `shadow`, `circle`, `line`, `polyline`, `arc`, `area`,
`sparkle`, `text`, `image`, `icon`, `push_clip` / `pop_clip`. Events: `on_enter`, `on_leave`, `on_hover`,
`on_press` (return True to capture), `on_drag`, `on_release`, `on_click`, `on_double_click`, `on_right_click`,
`on_wheel`, `on_key`, `on_nav`, `on_focus`, `on_blur`. Use `self.anim("name", target)` for smooth changes and
`get_state` / `set_state` to save state in the .blend.

## Notes

- The 3D viewport composites add-on drawing in linear color; Uzima converts automatically so colors match
  the sidebar. Override with `surface.linear_output`.
- Fonts are reloaded after every file load, so text never disappears.
- The cursor stays Blender's arrow (`ui.App(..., cursors=True)` enables hand / text cursors). The eyedropper
  shows Blender's eyedropper cursor while picking.
- Panels can't receive files dragged from outside Blender, so `DropZone` opens the file browser instead.
- No IME (Chinese, Japanese, Korean composition) in text fields.
- Inter font: SIL Open Font License (`uzima/fonts/OFL.txt`).
