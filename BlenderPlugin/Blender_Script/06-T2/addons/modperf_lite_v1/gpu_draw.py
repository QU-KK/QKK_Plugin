# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Supra3D
"""Low-level GPU drawing: shapes, the icon atlas, logo and title font."""

import json
import math
import os
import zlib

import blf
import bpy
import gpu
import numpy as np
from gpu_extras.batch import batch_for_shader

from .constants import FONT
from .utils import _col, _scale


# =============================================================================
# Low level drawing
# =============================================================================

_SHADERS = {}


def _shader(name):
    sh = _SHADERS.get(name)
    if sh is None:
        sh = _SHADERS[name] = gpu.shader.from_builtin(name)
    return sh


def _rrect_points(x0, y0, x1, y1, r, seg=None):
    r = max(0.0, min(r, (x1 - x0) / 2, (y1 - y0) / 2))
    if seg is None:
        seg = max(4, min(16, int(r / 1.5)))        # smooth curve for big radii
    if r < 1.0:
        return [(x1, y1), (x0, y1), (x0, y0), (x1, y0)]
    pts = []
    for cx, cy, a0 in ((x1 - r, y1 - r, 0), (x0 + r, y1 - r, 90),
                       (x0 + r, y0 + r, 180), (x1 - r, y0 + r, 270)):
        for i in range(seg + 1):
            a = math.radians(a0 + 90 * i / seg)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def _draw_tris(pts, color):
    sh = _shader('UNIFORM_COLOR')
    batch = batch_for_shader(sh, 'TRIS', {"pos": pts})
    sh.uniform_float("color", color)
    batch.draw(sh)


def _draw_rect(x0, y0, x1, y1, color, r=0.0):
    pts = _rrect_points(x0, y0, x1, y1, r)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    tris = []
    n = len(pts)
    for i in range(n):
        tris += [(cx, cy), pts[i], pts[(i + 1) % n]]
    _draw_tris(tris, color)


def _draw_polyline(pts, color, width, region, prim='LINES'):
    sh = _shader('POLYLINE_UNIFORM_COLOR')
    batch = batch_for_shader(sh, prim, {"pos": pts})
    sh.uniform_float("viewportSize", (region.width, region.height))
    sh.uniform_float("lineWidth", width)
    sh.uniform_float("color", color)
    batch.draw(sh)


# ---- Blender's own icons (rasterised from Blender's icon SVGs, see icons/) ----

_ATLAS = {'meta_tried': False, 'icons': {}, 'w': 0, 'h': 0, 'raw': None, 'tex': None}


def _atlas_dir():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "icons")


def _atlas_meta():
    """Load the icon index once. Returns True when Blender icons are available."""
    if not _ATLAS['meta_tried']:
        _ATLAS['meta_tried'] = True
        try:
            d = _atlas_dir()
            with open(os.path.join(d, "blender_icons.json")) as f:
                meta = json.load(f)
            with open(os.path.join(d, "blender_icons.bin"), "rb") as f:
                raw = zlib.decompress(f.read())
            _ATLAS.update(icons=meta['icons'], w=meta['width'], h=meta['height'], raw=raw)
        except (OSError, ValueError, KeyError, zlib.error):
            _ATLAS['icons'] = {}                     # fall back to drawn icons
    return bool(_ATLAS['icons'])


def _atlas_texture():
    if _ATLAS['tex'] is None and _atlas_meta():
        W, H = _ATLAS['w'], _ATLAS['h']
        alpha = np.frombuffer(_ATLAS['raw'], dtype=np.uint8).reshape(H, W)[::-1]
        rgba = np.ones((H, W, 4), dtype=np.float32)
        rgba[..., 3] = alpha / 255.0
        buf = gpu.types.Buffer('FLOAT', W * H * 4, rgba.ravel())
        _ATLAS['tex'] = gpu.types.GPUTexture((W, H), format='RGBA8', data=buf)
    return _ATLAS['tex']


def _bicon(b, name, cx, cy, S, col, scale=1.0):
    """Queue Blender icon `name` centred at (cx, cy), tinted `col`.
    Returns False when the icon isn't available (caller draws a fallback)."""
    if not _atlas_meta():
        return False
    ic = _ATLAS['icons'].get(name)
    if ic is None:
        return False
    w, h = ic['wu'] * S * scale, ic['hu'] * S * scale
    x0, y0 = round(cx - w / 2), round(cy - h / 2)
    b.add('icon', x0, y0, x0 + round(w), y0 + round(h), col, name)
    if name + '__dark' in _ATLAS['icons']:
        # dark details of the icon (e.g. the collection box's outline and handle),
        # drawn black over the tinted shape like Blender does
        b.add('icon', x0, y0, x0 + round(w), y0 + round(h),
              (0.0, 0.0, 0.0, col[3] if len(col) > 3 else 1.0), name + '__dark')
    return True


_ICON_THEME = {'modifier': 'icon_modifier', 'object': 'icon_object',
               'object_data': 'icon_object_data', 'collection': 'icon_collection',
               'scene': 'icon_scene', 'shading': 'icon_shading', 'folder': 'icon_folder'}


def _red_alert(text):
    """BUT_REDALERT text/icon colour: TH_REDALERT lightened (HSL x1.5) and
    mixed 50/50 with the text colour (interface_widgets.cc)."""
    import colorsys
    red = (1.0, 0.0, 0.0)
    try:
        red = tuple(bpy.context.preferences.themes[0].user_interface.wcol_state.error)[:3]
    except (AttributeError, IndexError):
        pass
    h, l, s_ = colorsys.rgb_to_hls(*red)
    r = colorsys.hls_to_rgb(h, min(1.0, l * 1.5), min(1.0, s_ * 1.5))
    t = tuple(text)[:3]
    return tuple((a + b) / 2 for a, b in zip(r, t)) + (1.0,)


def _icon_cat_color(ui, name):
    """Theme colour for a Blender icon of a coloured category (UI_icons.hh:
    DEF_ICON_MODIFIER, DEF_ICON_OBJECT, ...), or None for plain icons."""
    if not _atlas_meta():
        return None
    ic = _ATLAS['icons'].get(name)
    attr = _ICON_THEME.get(ic.get('cat', '')) if ic else None
    return _col(getattr(ui, attr)) if attr else None


# Header toggle -> Blender icon for its current value (RNA icon + value offset).
_TOGGLE_ICON = {
    'cage': lambda on: 'mesh_data',
    'edit': lambda on: 'editmode_hlt',
    'viewport': lambda on: 'restrict_view_off' if on else 'restrict_view_on',
    'render': lambda on: 'restrict_render_off' if on else 'restrict_render_on',
}


def _draw_icon(x0, y0, x1, y1, color, name):
    tex = _atlas_texture()
    ic = _ATLAS['icons'].get(name)
    if tex is None or ic is None:
        return
    W, H = _ATLAS['w'], _ATLAS['h']
    u0, u1 = ic['x'] / W, (ic['x'] + ic['w']) / W
    v1, v0 = 1.0 - ic['y'] / H, 1.0 - (ic['y'] + ic['h']) / H
    sh = _shader('IMAGE_COLOR')
    batch = batch_for_shader(sh, 'TRIS', {
        "pos": [(x0, y0), (x1, y0), (x1, y1), (x0, y0), (x1, y1), (x0, y1)],
        "texCoord": [(u0, v0), (u1, v0), (u1, v1), (u0, v0), (u1, v1), (u0, v1)]})
    sh.bind()
    sh.uniform_sampler("image", tex)
    sh.uniform_float("color", color)
    batch.draw(sh)


# ---- ModPerf branding: logo texture + bundled title font ---------------------

_BRAND = {'logo': None, 'logo_tried': False, 'font': None, 'font_tried': False}
LOGO_SIZE = 64
TITLE_FONT_FILE = "Poppins-Bold.ttf"     # SIL Open Font License 1.1 (see fonts/OFL.txt)


def _font_path():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts", TITLE_FONT_FILE)


def _logo_texture():
    """Original ModPerf logo (stacked modifier layers), stored as raw RGBA."""
    if not _BRAND['logo_tried']:
        _BRAND['logo_tried'] = True
        try:
            with open(os.path.join(_atlas_dir(), "modperf_logo.bin"), "rb") as f:
                raw = zlib.decompress(f.read())
            px = np.frombuffer(raw, dtype=np.uint8).reshape(LOGO_SIZE, LOGO_SIZE, 4)[::-1]
            buf = gpu.types.Buffer('FLOAT', LOGO_SIZE * LOGO_SIZE * 4,
                                   (px.astype(np.float32) / 255.0).ravel())
            _BRAND['logo'] = gpu.types.GPUTexture((LOGO_SIZE, LOGO_SIZE), format='RGBA8', data=buf)
        except (OSError, ValueError, zlib.error):
            _BRAND['logo'] = None
    return _BRAND['logo']


def _draw_logo(x0, y0, x1, y1):
    tex = _logo_texture()
    if tex is None:
        return
    sh = _shader('IMAGE_COLOR')
    batch = batch_for_shader(sh, 'TRIS', {
        "pos": [(x0, y0), (x1, y0), (x1, y1), (x0, y0), (x1, y1), (x0, y1)],
        "texCoord": [(0, 0), (1, 0), (1, 1), (0, 0), (1, 1), (0, 1)]})
    sh.bind()
    sh.uniform_sampler("image", tex)
    sh.uniform_float("color", (1.0, 1.0, 1.0, 1.0))
    batch.draw(sh)


def _title_font():
    """blf font id of the bundled bold title font, or None (falls back to UI font)."""
    fid = _BRAND.get('font')
    if fid is not None:
        # Changing the theme / interface font / UI scale makes Blender reload its
        # fonts, which drops fonts loaded with blf.load: reload it when that happens.
        blf.size(fid, 12)
        if blf.dimensions(fid, "M")[0] <= 0:
            _BRAND['font'] = None
            _BRAND['font_tried'] = False
    if not _BRAND['font_tried']:
        _BRAND['font_tried'] = True
        fid = -1
        try:
            if os.path.isfile(_font_path()):
                fid = blf.load(_font_path())
        except Exception:
            fid = -1
        _BRAND['font'] = fid if fid is not None and fid >= 0 else None
    return _BRAND['font']


def _unload_brand():
    if _BRAND.get('font') is not None:
        try:
            blf.unload(_font_path())
        except Exception:
            pass
    _BRAND.update(logo=None, logo_tried=False, font=None, font_tried=False)


def _draw_items(items, region):
    S = _scale()
    lw = max(1.0, 1.2 * S)
    gpu.state.blend_set('ALPHA')
    for it in items:
        kind = it[0]
        if kind == 'rect':
            _draw_rect(it[1], it[2], it[3], it[4], it[5], it[6])
        elif kind == 'outline':
            pts = _rrect_points(it[1], it[2], it[3], it[4], it[6])
            _draw_polyline(pts + [pts[0]], it[5], lw, region, 'LINE_STRIP')
        elif kind == 'tris':
            _draw_tris(it[1], it[2])
        elif kind == 'lines':
            _draw_polyline(it[1], it[2], it[3] if len(it) > 3 else lw * 1.2, region)
        elif kind == 'icon':
            _draw_icon(it[1], it[2], it[3], it[4], it[5], it[6])
        elif kind == 'logo':
            _draw_logo(it[1], it[2], it[3], it[4])
        elif kind == 'text':
            fid = it[5] if len(it) > 5 else FONT
            if len(it) > 6:
                blf.size(fid, it[6])
            blf.position(fid, it[1], it[2], 0)
            blf.color(fid, *it[4])
            blf.draw(fid, it[3])
            # blf resets the blend state; restore it so transparency keeps working
            gpu.state.blend_set('ALPHA')
    gpu.state.blend_set('NONE')


def _shift(it, dx, dy):
    k = it[0]
    if k in ('rect', 'outline', 'icon', 'logo'):
        return (k, it[1] + dx, it[2] + dy, it[3] + dx, it[4] + dy) + tuple(it[5:])
    if k == 'text':
        return (k, it[1] + dx, it[2] + dy) + tuple(it[3:])
    if k in ('tris', 'lines'):
        return (k, [(x + dx, y + dy) for x, y in it[1]]) + tuple(it[2:])
    return it
