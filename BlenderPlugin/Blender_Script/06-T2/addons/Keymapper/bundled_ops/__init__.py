"""
bundled_ops — operators bundled directly into Keymapper.

These are small, self-contained operators that ship as part of Keymapper so the
user doesn't have to install them separately. They register alongside Keymapper
and appear in Browse Operators like any other operator, ready to bind shortcuts
to.

Each operator lives in its own module here. To add another bundled operator:
  1. Create a new module exposing `classes` (a tuple of bpy classes).
  2. Import it below and add it to _MODULES.
  3. Add its operator id + display name to operator_discovery.MANUAL_ADDON_OPS
     so it's categorized nicely in Browse Operators.

Note: these operators are registered unconditionally. Per project decision,
we don't guard against the user also having the equivalent standalone addons
installed — that scenario isn't expected.
"""

from . import asset_browser_window
from . import pivot_transform
from . import marking_menu
from . import quick_view
from . import select_tool_pie

_MODULES = (
    asset_browser_window,
    pivot_transform,
    marking_menu,
    quick_view,
    select_tool_pie,
)


def register():
    for mod in _MODULES:
        try:
            mod.register()
        except Exception as e:
            print(f"[Keymapper] bundled_ops: failed to register {mod.__name__}: {e}")


def unregister():
    for mod in reversed(_MODULES):
        try:
            mod.unregister()
        except Exception as e:
            print(f"[Keymapper] bundled_ops: failed to unregister {mod.__name__}: {e}")
