from __future__ import annotations

import struct
import zlib
from pathlib import Path

import bpy

_PREVIEW_COLLECTION = None
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_READY_ICON_IDS: set[int] = set()

_ICON_MAP = {
    "active_group": "sidebar/ActiveGroup.png",
    "add_selected_mesh": "ui/AddSelectedMesh.png",
    "bake": "ui/Bake.png",
    # Artwork is intentionally not supplied here. The UI falls back to Blender's
    # cancel glyph until the project-owned Bake_Stop.png asset is added.
    "bake_stop": "ui/Bake_Stop.png",
    "bake_group": "ui/BakeGroup.png",
    "bake_project": "ui/BakeProject.png",
    "fyr_baker": "FyrBaker.png",
    "cage": "sidebar/Cage.png",
    "cage_ui": "ui/Cage.png",
    "cage_on": "ui/Cage_On.png",
    "cage_off": "ui/Cage_Off.png",
    "cage_coverage": "ui/CageCoverage.png",
    "cage_coverage_on": "ui/CageCoverage_On.png",
    "cage_coverage_off": "ui/CageCoverage_Off.png",
    "cage_item": "ui/CageItem.png",
    "cage_ob_mesh": "ui/cage_ob_mesh.png",
    "dashboard": "sidebar/Dashboard.png",
    "maps": "sidebar/Maps.png",
    "output": "sidebar/Output.png",
    "preview": "sidebar/Preview.png",
    "session": "sidebar/Session.png",
    "setup": "sidebar/Setup.png",
    "low_poly": "ui/LowPoly.png",
    "high_poly": "ui/HighPoly.png",
    "hierarchy_low_poly": "ui/Hierarchy_LowPoly.png",
    "hierarchy_high_poly": "ui/Hierarchy_HighPoly.png",
    "open_folder": "ui/OpenFolder.png",
    "merge_groups": "ui/MergeGroups.png",
    "show_on_low": "ui/ShowOnLow.png",
    "send_to_painter": "ui/SendToPainter.png",
    "send_to_marmoset": "ui/SendToMarmosetTB.png",
    "texture_set": "ui/TextureSet.png",
    "texture_set_linked": "ui/TextureSetLinked.png",
    # Auto-build texture-set grouping modes (segmented control in the onboarding).
    "ts_per_group": "ui/PerGroup.png",
    "ts_combined": "ui/Combined.png",
    "ts_per_material": "ui/PerMaterial.png",
    "texture_missing": "ui/TextureMissing.png",
    "paint_offset": "ui/PaintOffset.png",
    "paint_skew": "ui/PaintSkew.png",
    "ray_count": "ui/RayCount.png",
    #: The "everything checks out" mark in the output-template editor's Validation
    #: panel, in place of Blender's generic CHECKMARK.
    "validation_check": "ui/Validation_Check.png",
    "mapstack_duplicate_warning": "ui/mapstack_duplicate_warning.png",
}


def _preview_api():
    """``bpy.utils.previews``, or ``None`` when tests stub ``bpy`` without it.

    The submodule is not imported by ``bpy.utils`` itself. ``getattr`` stays
    ``None`` until some other add-on happens to import it, and icon registration
    then skips every custom icon. Import it explicitly.
    """
    utils = getattr(bpy, "utils", None)
    if utils is None:
        return None
    previews = getattr(utils, "previews", None)
    if previews is not None:
        return previews
    try:
        import importlib
        return importlib.import_module("bpy.utils.previews")
    except Exception:
        return None


def _icon_dir() -> Path:
    return Path(__file__).resolve().parent / "icons"


def _resize_rgba_bilinear(pixels, src_w: int, src_h: int, dst_w: int, dst_h: int) -> list[float]:
    if (src_w, src_h) == (dst_w, dst_h):
        return list(pixels)

    resized = [0.0] * (dst_w * dst_h * 4)
    scale_x = src_w / dst_w
    scale_y = src_h / dst_h
    for dst_y in range(dst_h):
        src_y = max(0.0, min(src_h - 1.0, (dst_y + 0.5) * scale_y - 0.5))
        y0 = int(src_y)
        y1 = min(y0 + 1, src_h - 1)
        fy = src_y - y0
        for dst_x in range(dst_w):
            src_x = max(0.0, min(src_w - 1.0, (dst_x + 0.5) * scale_x - 0.5))
            x0 = int(src_x)
            x1 = min(x0 + 1, src_w - 1)
            fx = src_x - x0
            dst_offset = (dst_y * dst_w + dst_x) * 4
            offsets = (
                ((y0 * src_w + x0) * 4, (1.0 - fx) * (1.0 - fy)),
                ((y0 * src_w + x1) * 4, fx * (1.0 - fy)),
                ((y1 * src_w + x0) * 4, (1.0 - fx) * fy),
                ((y1 * src_w + x1) * 4, fx * fy),
            )
            for channel in range(4):
                resized[dst_offset + channel] = sum(
                    pixels[src_offset + channel] * weight
                    for src_offset, weight in offsets
                )
    return resized


def _decode_png_rgba(icon_path: Path):
    """Decode an 8-bit, non-interlaced RGB/RGBA PNG to bottom-up float RGBA.

    Returns ``(width, height, pixels)`` or ``None`` for any other PNG layout.
    Pure Python, so it works while ``bpy.data`` is restricted (add-ons enabled at
    startup register before data access is allowed). Rows come out bottom-up,
    matching ``Image.pixels``.
    """
    data = icon_path.read_bytes()
    if data[:8] != _PNG_SIGNATURE:
        return None
    pos = 8
    width = height = 0
    bpp = 0
    idat = []
    while pos + 8 <= len(data):
        length, kind = struct.unpack(">I4s", data[pos:pos + 8])
        body = data[pos + 8:pos + 8 + length]
        pos += 12 + length
        if kind == b"IHDR":
            width, height, depth, color_type, _comp, _filt, interlace = struct.unpack(">IIBBBBB", body)
            if depth != 8 or color_type not in (2, 6) or interlace != 0:
                return None
            bpp = 4 if color_type == 6 else 3
        elif kind == b"IDAT":
            idat.append(body)
        elif kind == b"IEND":
            break
    if not bpp or width <= 0 or height <= 0:
        return None
    raw = zlib.decompress(b"".join(idat))
    stride = width * bpp
    if len(raw) < (stride + 1) * height:
        return None
    rows = []
    prev = bytearray(stride)
    src = 0
    for _y in range(height):
        filter_type = raw[src]
        line = bytearray(raw[src + 1:src + 1 + stride])
        src += 1 + stride
        if filter_type == 1:
            for i in range(bpp, stride):
                line[i] = (line[i] + line[i - bpp]) & 255
        elif filter_type == 2:
            line = bytearray((a + b) & 255 for a, b in zip(line, prev))
        elif filter_type == 3:
            for i in range(stride):
                left = line[i - bpp] if i >= bpp else 0
                line[i] = (line[i] + ((left + prev[i]) >> 1)) & 255
        elif filter_type == 4:
            for i in range(stride):
                a = line[i - bpp] if i >= bpp else 0
                b = prev[i]
                c = prev[i - bpp] if i >= bpp else 0
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                line[i] = (line[i] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        elif filter_type != 0:
            return None
        rows.append(line)
        prev = line
    scale = 1.0 / 255.0
    pixels = []
    for line in reversed(rows):
        if bpp == 4:
            pixels.extend(value * scale for value in line)
        else:
            for i in range(0, stride, 3):
                pixels.extend((line[i] * scale, line[i + 1] * scale, line[i + 2] * scale, 1.0))
    return width, height, pixels


def _load_preview_pixels(previews, icon_name, icon_path: Path) -> None:
    """Load a PNG into a preview by writing pixel data directly.

    previews.load(..., "IMAGE") uses an async GPU-upload pipeline that shows
    Blender's spinner placeholder on the first draw.  Decoding the PNG here
    (``bpy.data.images`` only as a fallback) and writing image_pixels_float
    bypasses that pipeline so the icon is ready on the very first frame.

    Blender's preview system expects premultiplied alpha.  PNGs are stored as
    straight alpha, so we premultiply (RGB *= A) before writing.
    """
    w = h = 0
    raw = None
    try:
        decoded = _decode_png_rgba(icon_path)
    except Exception:
        decoded = None
    if decoded is not None:
        w, h, raw = decoded
    else:
        img = None
        try:
            img = bpy.data.images.load(str(icon_path), check_existing=False)
            img.colorspace_settings.name = "Non-Color"
            w, h = img.size
            raw = img.pixels[:]          # flat RGBA float, straight alpha, 0.0-1.0
        except Exception:
            raw = None
        if img is not None:
            try:
                bpy.data.images.remove(img)
            except Exception:
                pass

    if not raw:
        # No deferred ``previews.load`` fallback: its first icon read loads the
        # PNG through Blender's thumbnail cache on the draw thread, and an
        # unreadable cached thumbnail raises an uncaught C++ exception that
        # crashes Blender. Without pixels the UI falls back to a built-in icon.
        return

    # Convert straight -> premultiplied alpha so transparent areas don't bleed.
    premul = list(raw)
    for i in range(0, len(premul), 4):
        a = premul[i + 3]
        premul[i]     *= a
        premul[i + 1] *= a
        premul[i + 2] *= a
    preview = previews.new(icon_name)
    # ``icon_id`` draws from the icon buffer, not the full-size image buffer.
    # Blender used to derive it lazily from ``image_pixels_float``, but that is
    # no longer reliable (notably in Blender 5.1): valid preview IDs can retain
    # an all-zero 32px icon buffer and therefore render as blank UI glyphs.
    # Populate both buffers explicitly so every custom icon is ready on the
    # first draw and after an add-on reload.
    preview.image_size = (w, h)
    preview.image_pixels_float[:] = premul
    icon_w = min(w, 32)
    icon_h = min(h, 32)
    preview.icon_size = (icon_w, icon_h)
    preview.icon_pixels_float[:] = _resize_rgba_bilinear(premul, w, h, icon_w, icon_h)


def _ensure_preview_icon_pixels(preview) -> bool:
    """Repair a preview whose valid ``icon_id`` points at an empty UI buffer.

    Blender 5.1 can retain the full-resolution preview while zeroing the separate
    32px buffer used by ``icon_value`` after preview IDs are recycled on add-on
    reload.  Rebuild from the resident image pixels so UI draws never receive a
    known-blank icon.
    """
    if preview is None:
        return False
    try:
        icon_pixels = list(preview.icon_pixels_float)
        if any(icon_pixels[3::4]):
            return True

        image_pixels = list(preview.image_pixels_float)
        src_w, src_h = (int(value) for value in preview.image_size)
        if src_w <= 0 or src_h <= 0 or not any(image_pixels[3::4]):
            return False
        icon_w = min(src_w, 32)
        icon_h = min(src_h, 32)
        preview.icon_size = (icon_w, icon_h)
        preview.icon_pixels_float[:] = _resize_rgba_bilinear(
            image_pixels,
            src_w,
            src_h,
            icon_w,
            icon_h,
        )
        return any(list(preview.icon_pixels_float)[3::4])
    except Exception:
        return False


def _generate_tree_guide_icons(previews) -> None:
    """Procedurally build the hierarchy tree-guide (pole) glyphs.

    Four 1-cell-wide indentation icons used by the bake-project hierarchy list to
    draw continuous Outliner-style connector lines:
      tree_pipe  -  vertical line, full height (an ancestor whose column continues)
      tree_tee   -  vertical full height + branch to the right (a non-last child)
      tree_elbow -  vertical top->middle + branch to the right (the last child)
      tree_blank -  empty spacer (an ancestor whose column has ended)
    Generated at register time so we don't ship PNG assets for trivial line art.
    Colours are opaque so no alpha premultiply is needed.
    """
    w = h = 32
    cx = w // 2
    my = h // 2
    t = 3
    col = (0.55, 0.55, 0.55, 1.0)

    def blank():
        return [0.0] * (w * h * 4)

    def put(px, x, y):
        if 0 <= x < w and 0 <= y < h:
            i = (y * w + x) * 4
            px[i], px[i + 1], px[i + 2], px[i + 3] = col

    def vline(px, y0, y1):
        for y in range(y0, y1):
            for x in range(cx - t, cx + t):
                put(px, x, y)

    def hline(px, x0, x1):
        for x in range(x0, x1):
            for y in range(my - t, my + t):
                put(px, x, y)

    shapes = {}
    px = blank(); vline(px, 0, h); shapes["tree_pipe"] = px
    px = blank(); vline(px, 0, h); hline(px, cx, w); shapes["tree_tee"] = px
    px = blank(); vline(px, my - t, h); hline(px, cx, w); shapes["tree_elbow"] = px
    shapes["tree_blank"] = blank()

    for name, pixels in shapes.items():
        try:
            preview = previews.new(name)
            preview.image_size = (w, h)
            preview.image_pixels_float[:] = pixels
            preview.icon_size = (w, h)
            preview.icon_pixels_float[:] = pixels
        except Exception:
            pass


def register():
    global _PREVIEW_COLLECTION
    unregister()
    previews_api = _preview_api()
    if previews_api is None:
        return

    previews = previews_api.new()
    icon_dir = _icon_dir()
    for icon_name, filename in _ICON_MAP.items():
        icon_path = icon_dir / filename
        if icon_path.exists():
            _load_preview_pixels(previews, icon_name, icon_path)
    _generate_tree_guide_icons(previews)
    _PREVIEW_COLLECTION = previews


def unregister():
    global _PREVIEW_COLLECTION
    previews_api = _preview_api()
    if _PREVIEW_COLLECTION is not None and previews_api is not None:
        try:
            previews_api.remove(_PREVIEW_COLLECTION)
        except Exception:
            pass
    _PREVIEW_COLLECTION = None
    _READY_ICON_IDS.clear()


def get_icon_value(name: str) -> int:
    if _PREVIEW_COLLECTION is None:
        return 0
    preview = _PREVIEW_COLLECTION.get(name)
    if preview is None:
        return 0
    icon_id = int(preview.icon_id or 0)
    if icon_id and icon_id not in _READY_ICON_IDS:
        if _ensure_preview_icon_pixels(preview):
            _READY_ICON_IDS.add(icon_id)
    return icon_id
