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

"""Uzima UI renderer.

One signed-distance-field shader draws every shape: rounded boxes with
gradients and borders, soft shadows and glows, anti-aliased line segments,
and arcs. Shapes are batched into a single draw call until text or an image
needs to go on top, so a whole panel usually costs only a handful of calls.

Coordinates are Blender region pixels: x to the right, y up from the bottom.
"""

import math
import os
import time

import blf
import gpu

KIND_BOX = 0.0
KIND_SOFT = 1.0
KIND_SEG = 2.0
KIND_ARC = 3.0
KIND_STAR = 4.0

_VERT = """
void main()
{
    v_pos = pos;
    v_rect = rect;
    v_radii = radii;
    v_ca = col_a;
    v_cb = col_b;
    v_bc = bcol;
    v_p = params;
    v_clip = clip;
    gl_Position = vec4(pos / viewport * 2.0 - 1.0, 0.0, 1.0);
}
"""

_FRAG = """
float sd_round_box(vec2 p, vec2 b, vec4 r)
{
    /* r = (top-left, top-right, bottom-right, bottom-left), y up */
    float rr = (p.x > 0.0) ? ((p.y > 0.0) ? r.y : r.z) : ((p.y > 0.0) ? r.x : r.w);
    rr = min(rr, min(b.x, b.y));
    vec2 q = abs(p) - b + rr;
    return min(max(q.x, q.y), 0.0) + length(max(q, 0.0)) - rr;
}

float sd_segment(vec2 p, vec2 a, vec2 b)
{
    vec2 pa = p - a, ba = b - a;
    float h = clamp(dot(pa, ba) / max(dot(ba, ba), 1e-6), 0.0, 1.0);
    return length(pa - ba * h);
}

vec4 shade()
{
    if (v_pos.x < v_clip.x || v_pos.y < v_clip.y || v_pos.x > v_clip.z || v_pos.y > v_clip.w) {
        discard;
    }
    float kind = v_p.w;

    if (kind > 3.5) {
        /* sparkle / superellipse star: rect = (cx, cy, radius, exponent) */
        vec2 sp = (v_pos - v_rect.xy) / v_rect.z;
        float e = v_rect.w;
        float f = pow(pow(abs(sp.x), e) + pow(abs(sp.y), e), 1.0 / e) - 1.0;
        float fw = max(fwidth(f), 1e-4);
        float a = clamp(0.5 - f / fw, 0.0, 1.0);
        return vec4(v_ca.rgb, v_ca.a * a);
    }
    if (kind > 2.5) {
        /* arc: rect = (cx, cy, radius, half_width), col_b.xy = (start, span) */
        vec2 p = v_pos - v_rect.xy;
        float R = v_rect.z;
        float hw = v_rect.w;
        float a0 = v_cb.x;
        float span = v_cb.y;
        float ang = atan(p.y, p.x);
        float rel = mod(ang - a0, 6.28318530718);
        float d;
        if (rel <= span) {
            d = abs(length(p) - R) - hw;
        }
        else {
            vec2 c0 = vec2(cos(a0), sin(a0)) * R;
            vec2 c1 = vec2(cos(a0 + span), sin(a0 + span)) * R;
            d = min(length(p - c0), length(p - c1)) - hw;
        }
        float a = clamp(0.5 - d, 0.0, 1.0);
        return vec4(v_ca.rgb, v_ca.a * a);
    }
    if (kind > 1.5) {
        /* segment: rect = (x0, y0, x1, y1), params.x = half width */
        float d = sd_segment(v_pos, v_rect.xy, v_rect.zw) - v_p.x;
        float a = clamp(0.5 - d, 0.0, 1.0);
        return vec4(v_ca.rgb, v_ca.a * a);
    }

    vec2 b = v_rect.zw * 0.5;
    vec2 p = v_pos - (v_rect.xy + b);
    float d = sd_round_box(p, b, v_radii);

    if (kind > 0.5) {
        /* soft shadow / glow, params.y = blur radius */
        float blur = max(v_p.y, 0.5);
        float a = 1.0 - smoothstep(-blur, blur, d);
        a = a * a * (3.0 - 2.0 * a);
        return vec4(v_ca.rgb, v_ca.a * a);
    }

    /* gradient fill, params.z = angle (0 = top to bottom) */
    float ang = v_p.z;
    vec2 dir = vec2(sin(ang), -cos(ang));
    float ext = abs(dir.x) * b.x + abs(dir.y) * b.y;
    float t = clamp(dot(p, dir) / max(ext, 1e-4) * 0.5 + 0.5, 0.0, 1.0);
    vec4 fill = mix(v_ca, v_cb, t);

    float bw = v_p.x;
    float outer = clamp(0.5 - d, 0.0, 1.0);
    float inner = clamp(0.5 - (d + bw), 0.0, 1.0);
    vec4 res = vec4(fill.rgb * fill.a, fill.a) * outer;
    if (bw > 0.0) {
        float ring = max(outer - inner, 0.0);
        vec4 bp = vec4(v_bc.rgb * v_bc.a, v_bc.a) * ring;
        res = bp + res * (1.0 - bp.a);
    }
    if (res.a <= 0.0) {
        discard;
    }
    return vec4(res.rgb / res.a, res.a);
}

vec3 srgb_to_linear(vec3 c)
{
    vec3 lo = c / 12.92;
    vec3 hi = pow((max(c, vec3(0.0)) + 0.055) / 1.055, vec3(2.4));
    return mix(hi, lo, vec3(lessThanEqual(c, vec3(0.04045))));
}

void main()
{
    vec4 c = shade();
    /* The 3D viewport draws add-on overlays into an sRGB framebuffer that expects linear color */
    if (linear_out > 0.5) {
        c.rgb = srgb_to_linear(c.rgb);
    }
    fragColor = c;
}
"""

_IMG_VERT = """
void main()
{
    v_pos = pos;
    v_uv = uv;
    gl_Position = vec4(pos / viewport * 2.0 - 1.0, 0.0, 1.0);
}
"""

_IMG_FRAG = """
float sd_round_box(vec2 p, vec2 b, vec4 r)
{
    float rr = (p.x > 0.0) ? ((p.y > 0.0) ? r.y : r.z) : ((p.y > 0.0) ? r.x : r.w);
    rr = min(rr, min(b.x, b.y));
    vec2 q = abs(p) - b + rr;
    return min(max(q.x, q.y), 0.0) + length(max(q, 0.0)) - rr;
}
void main()
{
    if (v_pos.x < clip.x || v_pos.y < clip.y || v_pos.x > clip.z || v_pos.y > clip.w) {
        discard;
    }
    vec2 b = rect.zw * 0.5;
    float d = sd_round_box(v_pos - (rect.xy + b), b, radii);
    float a = clamp(0.5 - d, 0.0, 1.0);
    vec4 c = texture(image, v_uv);
    if (to_srgb > 0.5) {
        /* sRGB textures are decoded to linear when sampled: encode back for the UI framebuffer */
        vec3 lo = c.rgb * 12.92;
        vec3 hi = 1.055 * pow(max(c.rgb, vec3(0.0)), vec3(1.0 / 2.4)) - 0.055;
        c.rgb = mix(hi, lo, vec3(lessThanEqual(c.rgb, vec3(0.0031308))));
    }
    c *= tint;
    if (linear_out > 0.5) {
        vec3 lo = c.rgb / 12.92;
        vec3 hi = pow((max(c.rgb, vec3(0.0)) + 0.055) / 1.055, vec3(2.4));
        c.rgb = mix(hi, lo, vec3(lessThanEqual(c.rgb, vec3(0.04045))));
    }
    fragColor = vec4(c.rgb, c.a * a);
}
"""

_shader = None
_img_shader = None
_format = None


def _get_shaders():
    global _shader, _img_shader, _format
    if _shader is not None:
        return _shader, _img_shader, _format

    iface = gpu.types.GPUStageInterfaceInfo("uzima_iface")
    iface.smooth("VEC2", "v_pos")
    for n in ("v_rect", "v_radii", "v_ca", "v_cb", "v_bc", "v_p", "v_clip"):
        iface.flat("VEC4", n)

    info = gpu.types.GPUShaderCreateInfo()
    info.push_constant("VEC2", "viewport")
    info.push_constant("FLOAT", "linear_out")
    info.vertex_in(0, "VEC2", "pos")
    for i, n in enumerate(("rect", "radii", "col_a", "col_b", "bcol", "params", "clip")):
        info.vertex_in(i + 1, "VEC4", n)
    info.vertex_out(iface)
    info.fragment_out(0, "VEC4", "fragColor")
    info.vertex_source(_VERT)
    info.fragment_source(_FRAG)
    _shader = gpu.shader.create_from_info(info)

    fmt = gpu.types.GPUVertFormat()
    fmt.attr_add(id="pos", comp_type="F32", len=2, fetch_mode="FLOAT")
    for n in ("rect", "radii", "col_a", "col_b", "bcol", "params", "clip"):
        fmt.attr_add(id=n, comp_type="F32", len=4, fetch_mode="FLOAT")
    _format = fmt

    iface2 = gpu.types.GPUStageInterfaceInfo("uzima_img_iface")
    iface2.smooth("VEC2", "v_pos")
    iface2.smooth("VEC2", "v_uv")
    info2 = gpu.types.GPUShaderCreateInfo()
    info2.push_constant("VEC2", "viewport")
    info2.push_constant("VEC4", "rect")
    info2.push_constant("VEC4", "radii")
    info2.push_constant("VEC4", "clip")
    info2.push_constant("VEC4", "tint")
    info2.push_constant("FLOAT", "to_srgb")
    info2.push_constant("FLOAT", "linear_out")
    info2.sampler(0, "FLOAT_2D", "image")
    info2.vertex_in(0, "VEC2", "pos")
    info2.vertex_in(1, "VEC2", "uv")
    info2.vertex_out(iface2)
    info2.fragment_out(0, "VEC4", "fragColor")
    info2.vertex_source(_IMG_VERT)
    info2.fragment_source(_IMG_FRAG)
    _img_shader = gpu.shader.create_from_info(info2)
    return _shader, _img_shader, _format


# ---------------------------------------------------------------------------
# Fonts
# ---------------------------------------------------------------------------

_HERE = os.path.dirname(__file__)
FONT_DIR = os.path.join(_HERE, "fonts")
_fonts = {}          # weight name -> blf font id
_font_paths = {}     # weight name -> path (for unloading)

DEFAULT_FONTS = {
    "regular": "Inter-Regular.ttf",
    "medium": "Inter-Medium.ttf",
    "semibold": "Inter-SemiBold.ttf",
    "bold": "Inter-Bold.ttf",
}


def load_font(name, path):
    """Register a custom font under `name` (e.g. "display"). Returns the blf id."""
    if name in _fonts and _font_paths.get(name) == path:
        return _fonts[name]
    fid = blf.load(path)
    if fid == -1:
        print("Uzima UI: could not load font", path)
        fid = 0
    _fonts[name] = fid
    _font_paths[name] = path
    return fid


def font_id(name="regular"):
    if not _fonts:
        for n, f in DEFAULT_FONTS.items():
            p = os.path.join(FONT_DIR, f)
            if os.path.exists(p):
                load_font(n, p)
    if name == "mono" and "mono" not in _fonts:
        try:
            import bpy
            p = os.path.join(bpy.utils.system_resource("DATAFILES"), "fonts", "DejaVuSansMono.woff2")
            load_font("mono", p if os.path.exists(p) else _font_paths.get("regular", ""))
        except Exception:
            _fonts["mono"] = _fonts.get("regular", 0)
    return _fonts.get(name, _fonts.get("regular", 0))


def ensure_fonts():
    """Blender invalidates add-on fonts when a .blend file is opened, created or reverted:
    the id stays the same but draws nothing. Calling blf.load() again on the same file
    revives it. This check is one cheap call per frame, so text can never silently vanish."""
    if not _fonts:
        font_id()
        return True
    fid = _fonts.get("regular", 0)
    blf.size(fid, 12)
    if fid and blf.dimensions(fid, "H")[0] > 0:
        return False
    reload_fonts()
    return True


def reload_fonts():
    for name, path in list(_font_paths.items()):
        fid = blf.load(path)
        if fid == -1:
            fid = 0
        _fonts[name] = fid
    _measure_cache.clear()


def unload_fonts():
    for name, path in list(_font_paths.items()):
        try:
            blf.unload(path)
        except Exception:
            pass
    _fonts.clear()
    _font_paths.clear()


_measure_cache = {}


def text_size(text, size, weight="regular"):
    """Width and height in pixels of `text` at pixel `size`."""
    key = (text, round(size, 2), weight)
    r = _measure_cache.get(key)
    if r is None:
        fid = font_id(weight)
        blf.size(fid, size)
        r = blf.dimensions(fid, text)
        if len(_measure_cache) > 4000:
            _measure_cache.clear()
        _measure_cache[key] = r
    return r


def cap_height(size, weight="regular"):
    return text_size("H", size, weight)[1]


def ellipsize(text, size, max_w, weight="regular"):
    if text_size(text, size, weight)[0] <= max_w:
        return text
    ell = "…"
    lo, hi = 0, len(text)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if text_size(text[:mid] + ell, size, weight)[0] <= max_w:
            lo = mid
        else:
            hi = mid - 1
    return text[:lo].rstrip() + ell if lo > 0 else ell


def wrap_text(text, size, max_w, weight="regular"):
    """Greedy word wrap. Returns list of (line, start_index)."""
    lines = []
    for para_start, para in _paragraphs(text):
        if para == "":
            lines.append(("", para_start))
            continue
        i = 0
        n = len(para)
        while i < n:
            # find the longest prefix that fits
            j = i
            last_space = -1
            while j < n:
                if para[j] == " ":
                    last_space = j
                if text_size(para[i:j + 1], size, weight)[0] > max_w and j > i:
                    break
                j += 1
            if j >= n:
                lines.append((para[i:], para_start + i))
                break
            if last_space > i:
                lines.append((para[i:last_space + 1], para_start + i))
                i = last_space + 1
            else:
                lines.append((para[i:j], para_start + i))
                i = j
    if not lines:
        lines.append(("", 0))
    return lines


def _paragraphs(text):
    start = 0
    for part in text.split("\n"):
        yield start, part
        start += len(part) + 1


# ---------------------------------------------------------------------------
# Images
# ---------------------------------------------------------------------------

_textures = {}


def load_texture(source):
    """Return (GPUTexture, width, height) for a file path or bpy.types.Image."""
    import bpy
    if isinstance(source, gpu.types.GPUTexture):
        return (source, source.width, source.height)
    if hasattr(source, "image_pixels_float"):
        # bpy.types.ImagePreview from bpy.utils.previews
        w, h = source.image_size
        if w == 0 or h == 0:
            raise ValueError("preview not generated yet")
        key = "pv:%d:%dx%d" % (source.as_pointer(), w, h)
        hit = _textures.get(key)
        if hit:
            return hit
        buf = gpu.types.Buffer("FLOAT", w * h * 4, source.image_pixels_float[:])
        tex = gpu.types.GPUTexture((w, h), format="RGBA16F", data=buf)
        r = (tex, w, h)
        _textures[key] = r
        return r
    if isinstance(source, str):
        key = source
        hit = _textures.get(key)
        if hit:
            return hit
        img = bpy.data.images.load(source, check_existing=True)
    else:
        img = source
        key = "img:" + str(img.as_pointer())
        hit = _textures.get(key)
        if hit and hit[1] == img.size[0] and hit[2] == img.size[1]:
            return hit
    try:
        img.colorspace_settings.name = "sRGB"
    except Exception:
        pass
    tex = gpu.texture.from_image(img)
    r = (tex, img.size[0], img.size[1])
    _textures[key] = r
    return r


def clear_textures():
    _textures.clear()


# ---------------------------------------------------------------------------
# Painter
# ---------------------------------------------------------------------------

def _lin(c):
    """sRGB channel -> linear."""
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _radii(r):
    if isinstance(r, (tuple, list)):
        return (float(r[0]), float(r[1]), float(r[2]), float(r[3]))
    r = float(r)
    return (r, r, r, r)


_ZERO4 = (0.0, 0.0, 0.0, 0.0)


class Painter:
    """Immediate-style drawing API used by widgets.

    p = Painter(scale)
    p.rect(x, y, w, h, fill=(1,1,1,1), radius=8)
    p.text("Hello", x, y, size=13)
    p.finish()
    """

    def __init__(self, scale=1.0, theme=None, linear=False):
        """linear=True converts all colors from sRGB to linear when drawing. Needed in the 3D
        viewport, whose overlay framebuffer is sRGB; without it everything looks washed out."""
        from .theme import DEFAULT
        self.scale = scale
        self.theme = theme or DEFAULT
        self.linear = linear
        # theme switches; widgets can override them for themselves (gradient= / shadows=)
        self.gradients = getattr(self.theme, "gradients", True)
        self.shadows = getattr(self.theme, "shadows", True)
        vp = gpu.state.viewport_get()
        self.vw = float(vp[2])
        self.vh = float(vp[3])
        self._clip = [(-1e9, -1e9, 1e9, 1e9)]
        self._prims = []
        self.time = time.perf_counter()
        self.draw_calls = 0

    # ---- helpers -------------------------------------------------------
    def px(self, v):
        return v * self.scale

    @property
    def clip(self):
        return self._clip[-1]

    def push_clip(self, x, y, w, h):
        c = self._clip[-1]
        self._clip.append((max(c[0], x), max(c[1], y), min(c[2], x + w), min(c[3], y + h)))

    def pop_clip(self):
        if len(self._clip) > 1:
            self._clip.pop()

    def clip_visible(self, x, y, w, h):
        c = self._clip[-1]
        return not (x > c[2] or y > c[3] or x + w < c[0] or y + h < c[1])

    def _add(self, x0, y0, x1, y1, rect, radii, ca, cb, bc, params):
        self._prims.append((x0, y0, x1, y1, rect, radii, ca, cb, bc, params, self._clip[-1]))

    # ---- shapes --------------------------------------------------------
    def rect(self, x, y, w, h, fill=None, radius=0.0, border=None, border_w=0.0,
             fill2=None, angle=0.0, flat=None, functional=False):
        """Rounded rectangle. `radius` can be one value or (tl, tr, br, bl).
        `fill2` makes a gradient from `fill` to `fill2` (angle 0 = top to bottom).

        When gradients are switched off the rectangle is drawn with `fill` only, or with `flat`
        if given (use it when `fill` is just the transparent start of a fade). Pass
        functional=True for gradients that carry information (color spectrum, ramp bars)."""
        if w <= 0 or h <= 0:
            return
        if fill is None:
            fill = (0.0, 0.0, 0.0, 0.0)
        if fill2 is not None and not self.gradients and not functional:
            if flat is not None:
                fill = flat
            fill2 = None
            if fill[3] <= 0.0 and border is None:
                return
        if fill2 is None:
            fill2 = fill
        bc = border if border is not None else _ZERO4
        bw = border_w if border is not None else 0.0
        self._add(x - 1, y - 1, x + w + 1, y + h + 1, (x, y, w, h), _radii(radius),
                  fill, fill2, bc, (bw, 0.0, angle, KIND_BOX))

    def shadow(self, x, y, w, h, radius=0.0, color=(0, 0, 0, 0.5), blur=10.0,
               spread=0.0, dx=0.0, dy=0.0, functional=False):
        """Soft drop shadow or glow behind a rounded rectangle. Skipped when shadows are
        switched off, unless functional=True."""
        if not self.shadows and not functional:
            return
        x += dx - spread
        y += dy - spread
        w += spread * 2
        h += spread * 2
        e = blur * 1.2 + 1
        r = _radii(radius)
        r = tuple(v + spread for v in r)
        self._add(x - e, y - e, x + w + e, y + h + e, (x, y, w, h), r,
                  color, color, _ZERO4, (0.0, blur, 0.0, KIND_SOFT))

    def circle(self, cx, cy, r, fill=None, border=None, border_w=0.0, fill2=None):
        self.rect(cx - r, cy - r, r * 2, r * 2, fill=fill, radius=r, border=border,
                  border_w=border_w, fill2=fill2)

    def line(self, x0, y0, x1, y1, width=1.0, color=(1, 1, 1, 1)):
        hw = width * 0.5
        e = hw + 1.5
        self._add(min(x0, x1) - e, min(y0, y1) - e, max(x0, x1) + e, max(y0, y1) + e,
                  (x0, y0, x1, y1), _ZERO4, color, color, _ZERO4, (hw, 0.0, 0.0, KIND_SEG))

    def polyline(self, pts, width=1.0, color=(1, 1, 1, 1), closed=False):
        n = len(pts)
        for i in range(n - 1):
            self.line(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1], width, color)
        if closed and n > 2:
            self.line(pts[-1][0], pts[-1][1], pts[0][0], pts[0][1], width, color)

    def arc(self, cx, cy, r, start, span, width=1.0, color=(1, 1, 1, 1)):
        """Arc from angle `start` (radians, 0 = right, CCW) sweeping `span`."""
        span = max(0.0, min(span, math.tau))
        hw = width * 0.5
        e = r + hw + 1.5
        self._add(cx - e, cy - e, cx + e, cy + e, (cx, cy, r, hw), _ZERO4, color,
                  (start % math.tau, span, 0.0, 0.0), _ZERO4, (0.0, 0.0, 0.0, KIND_ARC))

    def area(self, x0, x1, base, top_fn, color, color2=None, flat=None):
        """Fill under a curve: one pixel-wide column per x from base up to top_fn(x).
        color is the top color, color2 the bottom (gradient), flat used when gradients are off."""
        xi = int(math.floor(x0))
        end = int(math.ceil(x1))
        while xi < end:
            cx = max(x0, xi)
            w = min(x1, xi + 1) - cx
            if w > 0:
                t = top_fn(cx + w / 2)
                if t > base + 0.25:
                    self.rect(cx, base, w, t - base, fill=color, fill2=color2, flat=flat)
            xi += 1

    def sparkle(self, cx, cy, r, color=(1, 1, 1, 1), sharpness=0.6):
        """Filled four-point star (the AI 'spark'). Lower sharpness = thinner points."""
        e = r + 1.5
        self._add(cx - e, cy - e, cx + e, cy + e, (cx, cy, r, sharpness), _ZERO4, color,
                  color, _ZERO4, (0.0, 0.0, 0.0, KIND_STAR))

    # ---- text ----------------------------------------------------------
    def text(self, text, x, y, size=None, color=None, weight="regular", align="left",
             valign="baseline", max_w=None):
        """Draw a single line. `size` is unscaled px. Returns drawn width."""
        if not text:
            return 0.0
        th = self.theme
        size = self.px(size if size is not None else th.fs_md)
        color = color or th.text
        if max_w is not None:
            text = ellipsize(text, size, max_w, weight)
        w, _h = text_size(text, size, weight)
        if align == "center":
            x -= w * 0.5
        elif align == "right":
            x -= w
        if valign == "center":
            y -= cap_height(size, weight) * 0.5
        elif valign == "top":
            y -= cap_height(size, weight)
        c = self._clip[-1]
        if x > c[2] or x + w < c[0] or y - size > c[3] or y + size < c[1]:
            return w
        self.flush()
        fid = font_id(weight)
        blf.size(fid, size)
        if self.linear:
            blf.color(fid, _lin(color[0]), _lin(color[1]), _lin(color[2]), color[3])
        else:
            blf.color(fid, *color)
        if c[0] > -1e8:
            blf.enable(fid, blf.CLIPPING)
            blf.clipping(fid, c[0], c[1], c[2], c[3])
        else:
            blf.disable(fid, blf.CLIPPING)
        blf.position(fid, round(x), round(y), 0)
        blf.draw(fid, text)
        blf.disable(fid, blf.CLIPPING)
        return w

    def measure(self, text, size=None, weight="regular"):
        size = self.px(size if size is not None else self.theme.fs_md)
        return text_size(text, size, weight)

    # ---- images --------------------------------------------------------
    def image(self, source, x, y, w, h, radius=0.0, opacity=1.0, fit="cover", tint=None):
        """Draw an image file path or bpy Image, clipped to a rounded rect."""
        try:
            tex, iw, ih = load_texture(source)
        except Exception as e:  # missing file etc.
            self.rect(x, y, w, h, fill=self.theme.surface_3, radius=radius)
            return
        self.flush()
        _s, shader, _f = _get_shaders()
        u0, v0, u1, v1 = 0.0, 0.0, 1.0, 1.0
        dx, dy, dw, dh = x, y, w, h
        if iw > 0 and ih > 0:
            ar_img = iw / ih
            ar_box = w / h if h > 0 else 1.0
            if fit == "cover":
                if ar_img > ar_box:
                    span = ar_box / ar_img
                    u0, u1 = 0.5 - span / 2, 0.5 + span / 2
                else:
                    span = ar_img / ar_box
                    v0, v1 = 0.5 - span / 2, 0.5 + span / 2
            elif fit == "contain":
                if ar_img > ar_box:
                    dh = w / ar_img
                    dy = y + (h - dh) / 2
                else:
                    dw = h * ar_img
                    dx = x + (w - dw) / 2
        from gpu_extras.batch import batch_for_shader
        pos = ((dx, dy), (dx + dw, dy), (dx + dw, dy + dh), (dx, dy + dh))
        uv = ((u0, v0), (u1, v0), (u1, v1), (u0, v1))
        batch = batch_for_shader(shader, "TRIS", {"pos": pos, "uv": uv},
                                 indices=((0, 1, 2), (0, 2, 3)))
        shader.bind()
        shader.uniform_float("viewport", (self.vw, self.vh))
        shader.uniform_float("rect", (dx, dy, dw, dh))
        shader.uniform_float("radii", _radii(radius))
        c = self._clip[-1]
        shader.uniform_float("clip", (max(c[0], -1e6), max(c[1], -1e6), min(c[2], 1e6), min(c[3], 1e6)))
        t = tint or (1.0, 1.0, 1.0, 1.0)
        shader.uniform_float("tint", (t[0], t[1], t[2], t[3] * opacity))
        shader.uniform_float("to_srgb", 1.0 if tex.format.startswith("SRGB") else 0.0)
        shader.uniform_float("linear_out", 1.0 if self.linear else 0.0)
        shader.uniform_sampler("image", tex)
        gpu.state.blend_set("ALPHA")
        batch.draw(shader)
        self.draw_calls += 1

    # ---- icons ---------------------------------------------------------
    def icon(self, name, x, y, size=16.0, color=None, stroke=1.6):
        """Draw a vector icon centered in the square (x, y, size)."""
        from .icons import draw_icon
        draw_icon(self, name, x, y, size, color or self.theme.text, stroke * self.scale)

    # ---- submit --------------------------------------------------------
    def flush(self):
        prims = self._prims
        if not prims:
            return
        self._prims = []
        shader, _i, fmt = _get_shaders()
        n = len(prims) * 6
        pos = []
        cols = [[], [], [], [], [], [], []]
        for (x0, y0, x1, y1, rect, radii, ca, cb, bc, params, clip) in prims:
            pos += ((x0, y0), (x1, y0), (x1, y1), (x0, y0), (x1, y1), (x0, y1))
            for lst, val in zip(cols, (rect, radii, ca, cb, bc, params, clip)):
                lst += (val,) * 6
        vbo = gpu.types.GPUVertBuf(fmt, n)
        vbo.attr_fill("pos", pos)
        for name, lst in zip(("rect", "radii", "col_a", "col_b", "bcol", "params", "clip"), cols):
            vbo.attr_fill(name, lst)
        batch = gpu.types.GPUBatch(type="TRIS", buf=vbo)
        shader.bind()
        shader.uniform_float("viewport", (self.vw, self.vh))
        shader.uniform_float("linear_out", 1.0 if self.linear else 0.0)
        gpu.state.blend_set("ALPHA")
        batch.draw(shader)
        self.draw_calls += 1

    def finish(self):
        self.flush()
        gpu.state.blend_set("NONE")
