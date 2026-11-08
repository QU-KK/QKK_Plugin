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

"""Uzima UI theme.

All sizes are in unscaled pixels ("dp"). The painter multiplies them by the Blender UI
scale, so the UI stays crisp on any monitor.

Every color is a public attribute. Colors can be given as "#rrggbb", "#rrggbbaa", or
(r, g, b[, a]) floats in 0..1 (sRGB, like the colors you see in a color picker).

    theme = ui.Theme(accent="#9fbd97", bg="#121414")    # new theme with overrides
    theme.set(accent="#7c5cff")                          # change live; shades are derived
    theme.set(accent="#7c5cff", accent_text="#ffffff")   # ...or override any of them
    app = ui.App("my_addon", theme=theme)

Changing a theme that is in use repaints the UI on the next frame.
"""


def hex_color(h, a=1.0):
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(ch * 2 for ch in h)
    if len(h) == 8:
        a = int(h[6:8], 16) / 255.0
    return (int(h[0:2], 16) / 255.0, int(h[2:4], 16) / 255.0, int(h[4:6], 16) / 255.0, a)


def to_color(c):
    """Accept "#hex", (r, g, b) or (r, g, b, a) and return an RGBA tuple."""
    if isinstance(c, str):
        return hex_color(c)
    c = tuple(float(v) for v in c)
    if len(c) == 3:
        return c + (1.0,)
    return c[:4]


def to_hex(c):
    return "#%02x%02x%02x" % tuple(int(round(max(0.0, min(1.0, v)) * 255)) for v in c[:3])


def alpha(c, a):
    return (c[0], c[1], c[2], a)


def mix(c1, c2, t):
    t = max(0.0, min(1.0, t))
    return tuple(c1[i] + (c2[i] - c1[i]) * t for i in range(4))


def lighten(c, amt):
    return mix(c, (1.0, 1.0, 1.0, c[3]), amt)


def darken(c, amt):
    return mix(c, (0.0, 0.0, 0.0, c[3]), amt)


def luminance(c):
    def lin(v):
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
    return 0.2126 * lin(c[0]) + 0.7152 * lin(c[1]) + 0.0722 * lin(c[2])


# names of every color slot, for docs, pickers and serialization
COLOR_KEYS = (
    "bg", "surface_0", "surface_1", "surface_2", "surface_3", "surface_4", "selected", "overlay",
    "border", "border_strong", "border_focus",
    "text", "text_dim", "text_muted", "text_disabled",
    "accent", "accent_hi", "accent_lo", "accent_edge", "accent_text", "accent_soft",
    "info", "success", "warning", "danger",
)


class Theme:
    # --- surfaces (darkest -> lightest) ---
    bg = hex_color("#151818")          # region background
    surface_0 = hex_color("#1b1d20")   # sunken areas, tracks, fields
    surface_1 = hex_color("#202125")   # cards, tab bar
    surface_2 = hex_color("#27292d")   # raised cards, popovers, windows
    surface_3 = hex_color("#323438")   # chips, buttons
    surface_4 = hex_color("#3a3c40")   # hover
    selected = hex_color("#36383c")    # active tab / row
    overlay = hex_color("#000000", 0.55)  # dialog backdrop

    # --- borders ---
    border = hex_color("#2c2e32")
    border_strong = hex_color("#3d4045")
    border_focus = hex_color("#9fbd97", 0.75)

    # --- text ---
    text = hex_color("#eef0f1")
    text_dim = hex_color("#b4b7ba")
    text_muted = hex_color("#7a7e83")
    text_disabled = hex_color("#55585c")

    # --- accent (sage green) ---
    accent = hex_color("#9fbd97")
    accent_hi = hex_color("#b6d0af")
    accent_lo = hex_color("#88a87f")
    accent_edge = hex_color("#5e7a57")
    accent_text = hex_color("#16200f")
    accent_soft = hex_color("#9fbd97", 0.14)

    # --- semantic ---
    info = hex_color("#6aa8e8")
    success = hex_color("#5cc98a")
    warning = hex_color("#e8b25a")
    danger = hex_color("#ec6a6a")

    # --- radii ---
    r_xs = 4
    r_sm = 7
    r_md = 10
    r_lg = 14
    r_xl = 18
    r_pill = 999

    # --- spacing ---
    pad = 12
    gap = 8
    gap_sm = 5
    control_h = 30
    control_h_sm = 24
    control_h_lg = 40

    # --- typography (px at UI scale 1.0) ---
    fs_xs = 10.5
    fs_sm = 11.5
    fs_md = 12.5
    fs_lg = 14.5
    fs_xl = 17
    fs_title = 21

    # --- style switches ---
    gradients = True      # False: every element is drawn with flat colors
    shadows = True        # False: no drop shadows or glows

    # --- motion ---
    speed = 18.0          # higher = snappier transitions
    tooltip_delay = 0.55

    # --- sidebar ---
    sidebar_tab_strip = 21  # width Blender uses for category tabs (dp)
    sidebar_bg_alpha = 1.0  # < 1.0 gives a glass look over the viewport

    def __init__(self, **overrides):
        if overrides:
            self.set(**overrides)

    def set(self, **values):
        """Change theme values. Colors take "#hex" or tuples.

        Setting `accent` alone also derives accent_hi, accent_lo, accent_edge, accent_text,
        accent_soft and border_focus from it, unless you pass those too."""
        for k, v in values.items():
            if not hasattr(Theme, k) and k not in COLOR_KEYS:
                raise AttributeError("Theme has no setting %r" % k)
            if k in COLOR_KEYS:
                v = to_color(v)
            setattr(self, k, v)
        if "accent" in values:
            derived = self.accent_shades(self.accent)
            for k, v in derived.items():
                if k not in values:
                    setattr(self, k, v)
        try:
            from .host import request_redraw
            request_redraw()
        except Exception:
            pass
        return self

    @staticmethod
    def accent_shades(accent):
        a = to_color(accent)
        dark_text = luminance(a) > 0.28
        return {
            "accent_hi": lighten(a, 0.18),
            "accent_lo": darken(a, 0.10),
            "accent_edge": darken(a, 0.42),
            "accent_text": mix(a, (0.0, 0.0, 0.0, 1.0), 0.86) if dark_text else (1.0, 1.0, 1.0, 1.0),
            "accent_soft": alpha(a, 0.14),
            "border_focus": alpha(a, 0.75),
        }

    @classmethod
    def from_accent(cls, accent, **overrides):
        return cls(accent=accent, **overrides)

    def color(self, value):
        """Resolve a color given as a theme key ("accent", "text_muted"), hex string or tuple."""
        if value is None:
            return None
        if isinstance(value, str):
            if value.startswith("#"):
                return hex_color(value)
            return getattr(self, value)
        return to_color(value)

    def colors(self):
        """All colors as {name: "#rrggbb"} (alpha dropped), e.g. to save a user preset."""
        return {k: to_hex(getattr(self, k)) for k in COLOR_KEYS}

    def copy(self, **overrides):
        t = type(self)()
        for k in dir(self):
            if not k.startswith("_") and not callable(getattr(self, k)):
                try:
                    setattr(t, k, getattr(self, k))
                except AttributeError:
                    pass
        if overrides:
            t.set(**overrides)
        return t


PRESETS = {
    "Uzima Dark": {},
    "Midnight": dict(
        bg="#0d0f12", surface_0="#12151a", surface_1="#161a20", surface_2="#1c2128", surface_3="#252b33",
        surface_4="#2d343d", selected="#2a313a", border="#232931", border_strong="#323a44",
        text="#e8edf3", text_dim="#a8b1bc", text_muted="#6f7a87", text_disabled="#4a535e",
        accent="#8fb4d9"),
    "Even Darker": dict(
        bg="#0a0b0d", surface_0="#0e1013", surface_1="#121418", surface_2="#161920", surface_3="#1d2027",
        surface_4="#23262e", selected="#20262c", border="#191c22", border_strong="#262a32",
        text="#e6eaef", text_dim="#a4adb8", text_muted="#6a727c", text_disabled="#464d56",
        accent="#7da8d4"),
    "Darkest": dict(
        bg="#050608", surface_0="#080a0c", surface_1="#0b0d10", surface_2="#0f1216", surface_3="#14171c",
        surface_4="#191d22", selected="#161a1f", border="#111418", border_strong="#1c2026",
        text="#e2e6ec", text_dim="#9ba4ae", text_muted="#636b75", text_disabled="#424850",
        accent="#6f9fd6"),
    "Sand": dict(
        bg="#171513", surface_0="#1d1a17", surface_1="#221f1b", surface_2="#2a2622", surface_3="#35302b",
        surface_4="#3e3833", selected="#3a342e", border="#2e2a25", border_strong="#423c35",
        text="#f2eee8", text_dim="#c2bab0", text_muted="#8a8279", text_disabled="#5c554e",
        accent="#e0b77a"),
    "Monokai": dict(
        bg="#272822", surface_0="#2d2e28", surface_1="#33342e", surface_2="#3a3b34", surface_3="#45463e",
        surface_4="#505145", selected="#49483e", border="#3e3f37", border_strong="#555648",
        text="#f8f8f2", text_dim="#c8c5b8", text_muted="#75715e", text_disabled="#5b5a4d",
        accent="#a6e22e", info="#66d9ef", success="#a6e22e", warning="#fd971f", danger="#f92672"),
    "Atom One Dark": dict(
        bg="#282c34", surface_0="#2c313a", surface_1="#333842", surface_2="#3a3f4b", surface_3="#424853",
        surface_4="#4b5160", selected="#3d424d", border="#3a3f49", border_strong="#525866",
        text="#d7dae0", text_dim="#abb2bf", text_muted="#5c6370", text_disabled="#4b5263",
        accent="#61afef", info="#61afef", success="#98c379", warning="#d19a66", danger="#e06c75"),
    "Light": dict(
        bg="#f3f4f2", surface_0="#e8eae6", surface_1="#ffffff", surface_2="#ffffff", surface_3="#eef0ec",
        surface_4="#e2e5e0", selected="#e1e7dd", border="#dde0da", border_strong="#c6cac2",
        text="#1b1e1c", text_dim="#434844", text_muted="#767c77", text_disabled="#a8ada8",
        overlay="#00000059", accent="#6f9466", info="#2f78c4", success="#2f9e5f", warning="#b97a12",
        danger="#cf3f3f"),
}


def _theme_reset(self):
    """Put every color back to the built-in default (style switches are kept)."""
    for k in COLOR_KEYS:
        setattr(self, k, getattr(Theme, k))
    return self


def _theme_load_preset(self, name):
    """Apply a preset from PRESETS ("Uzima Dark", "Midnight", "Even Darker", "Darkest", "Sand",
    "Monokai", "Atom One Dark", "Light")."""
    self.reset()
    self.set(**PRESETS[name]) if PRESETS[name] else self.set(accent=self.accent)
    self.preset = name
    return self


def _theme_to_dict(self):
    d = self.colors()
    d.update(gradients=self.gradients, shadows=self.shadows, speed=self.speed)
    return d


def _theme_from_dict(self, d):
    d = dict(d)
    switches = {k: d.pop(k) for k in ("gradients", "shadows", "speed") if k in d}
    accent_derived = Theme.accent_shades(d["accent"]) if "accent" in d else {}
    for k, v in switches.items():
        setattr(self, k, v)
    self.set(**{k: v for k, v in d.items() if k in COLOR_KEYS})
    return self


def _theme_save(self, path):
    import json
    with open(path, "w", encoding="utf-8") as f:
        json.dump(self.to_dict(), f, indent=2)


def _theme_load(self, path):
    import json
    with open(path, encoding="utf-8") as f:
        return self.from_dict(json.load(f))


Theme.preset = "Uzima Dark"
Theme.reset = _theme_reset
Theme.load_preset = _theme_load_preset
Theme.to_dict = _theme_to_dict
Theme.from_dict = _theme_from_dict
Theme.save = _theme_save
Theme.load = _theme_load

DEFAULT = Theme()
