"""Single bottom-center viewport HUD for setup and active bake progress.

The draw handler stays registered while the add-on is enabled. Setup code can
temporarily provide explicit text through begin/update/end; otherwise the HUD
reads the active background bake and its owning project's progress state.
"""

from __future__ import annotations

import time
import traceback

import blf
import bpy
import gpu
from gpu_extras.batch import batch_for_shader

from . import constants

_ACTIVE: bool = False
_TITLE: str = ""
_DETAIL: str = ""
_FACTOR: float | None = None
_HANDLER = None
_ROUND_SHADER = None

#: monotonic stamp of the last begin()/update(). Explicit mode is torn down when it
#: goes older than _EXPLICIT_MAX_AGE, so a setup path that raises between begin() and
#: end() cannot strand the card on screen for the rest of the session.
_ACTIVE_AT: float = 0.0
_EXPLICIT_MAX_AGE: float = 180.0

#: Identity of the run the user dismissed by hand. The derived (bake-driven) HUD stays
#: hidden while that identity is still the live one; a new job id brings it back, so a
#: dismiss never silently disables progress for the rest of the session.
_SUPPRESSED_KEY: str = ""

#: True while the bake low-impact viewport mode holds the VIEW_3D WINDOW region frozen.
#: That mode is the measured 4.6-6.7x bake-contention win, and it deliberately never tags
#: the WINDOW region for redraw -- but this HUD is a POST_PIXEL handler *on* that region,
#: so it cannot repaint and sits on whatever frame it drew first ("Baking / 0% / 0.0s") for
#: the whole bake. A frozen 0% reads as a hang, which is worse than no HUD, so we hide it
#: and let the sidebar and status bar (both of which ARE tagged) carry progress -- exactly
#: what the preference's own description promises. Set by operators around the bake.
_VIEWPORT_QUIET: bool = False


def set_viewport_quiet(quiet: bool) -> None:
    """Tell the HUD whether the viewport is frozen for the duration of a bake."""
    global _VIEWPORT_QUIET
    _VIEWPORT_QUIET = bool(quiet)


#: First time each bake identity was seen, so the elapsed readout survives the backend
#: process exiting while the Cycles material queue runs on.
_RUN_STARTED_AT: dict[str, float] = {}


def _tag_redraw_all_view3d() -> None:
    try:
        from .overlay_events import tag_redraw_all_view3d

        tag_redraw_all_view3d(all_windows=True)
    except Exception:
        pass


def _live_bake_identity():
    """(job_id, start_time) of whatever bake stage is running now, else None.

    Two stages can own a run. The backend worker publishes a snapshot; the addon-side
    Cycles material queue does not, and it routinely OUTLIVES the backend by minutes
    on a job with material rows. Reading only the snapshot is what made the card
    vanish mid-bake with the elapsed timer frozen — the run was still going, nothing
    was left watching it.
    """
    from . import runtime

    snapshot = runtime.active_bake_snapshot()
    if snapshot is not None and bool(getattr(snapshot, "running", False)):
        job_id = str(getattr(snapshot, "job_id", "") or "").strip()
        return job_id, float(getattr(snapshot, "start_time", 0.0) or 0.0)

    try:
        from . import export

        status = export.active_material_bake_status()
    except Exception:
        status = None
    if status is not None:
        return str(getattr(status, "job_id", "") or "").strip(), 0.0

    try:
        from . import operators

        if operators.cycles_async_bake_active():
            return _cycles_primary_identity(), 0.0
    except Exception:
        pass
    return None


def _cycles_primary_identity() -> str:
    """Job id of an in-flight Cycles-primary run ("" when it cannot be resolved)."""
    try:
        from . import operators

        state = getattr(operators, "_CYCLES_ASYNC_STATE", None)
        prepared = state.get("prepared") if isinstance(state, dict) else None
        return str(getattr(getattr(prepared, "job", None), "job_id", "") or "")
    except Exception:
        return ""


def _project_for_job(job_id: str):
    for scene in getattr(bpy.data, "scenes", []) or []:
        settings = getattr(scene, "fyr_baker_settings", None)
        for candidate in getattr(settings, "projects", []) if settings is not None else []:
            if str(getattr(candidate, "last_job_id", "") or "").strip() == job_id:
                return candidate
    return None


#: Stand-in id for a run that publishes no job id of its own. A Cycles-primary run has
#: none until (and unless) its prepared job resolves, so every keyed lookup has to agree
#: on the same placeholder or the run cannot be matched against itself.
_UNKEYED_RUN = "<unkeyed>"


def _identity_key(job_id: object) -> str:
    """The dictionary key for a run identity, empty job ids included."""
    return str(job_id or "").strip() or _UNKEYED_RUN


def _run_start_time(job_id: str, snapshot_start: float) -> float:
    """Elapsed-time origin for a run, remembered across the backend's exit."""
    key = _identity_key(job_id)
    if snapshot_start > 0.0:
        _RUN_STARTED_AT.setdefault(key, snapshot_start)
        return _RUN_STARTED_AT[key]
    return _RUN_STARTED_AT.setdefault(key, time.monotonic())


def _running_bake_state():
    """Return (title, detail, factor) for the active bake, if any."""
    global _SUPPRESSED_KEY
    try:
        from . import runtime

        # The viewport is frozen for this bake, so anything drawn here would be stale
        # for its whole duration. See _VIEWPORT_QUIET.
        if _VIEWPORT_QUIET:
            return None

        identity = _live_bake_identity()
        if identity is None:
            _RUN_STARTED_AT.clear()
            # Nothing is running, so a manual dismiss has nothing left to hide. Clearing
            # it here is what lets an unkeyed run be dismissed without also hiding the
            # next unkeyed run, which shares the same placeholder key.
            _SUPPRESSED_KEY = ""
            return None
        job_id, snapshot_start = identity
        if _SUPPRESSED_KEY and _identity_key(job_id) == _SUPPRESSED_KEY:
            return None

        project = _project_for_job(job_id)
        if project is None:
            return None
        if _status_hides_hud(getattr(project, "last_status_message", "")):
            return None

        percent = max(
            0.0,
            min(100.0, float(getattr(project, "last_progress_percent", 0.0) or 0.0)),
        )
        title = str(getattr(project, "last_status_message", "") or "Baking").strip()
        active_group = str(getattr(project, "last_active_group", "") or "").strip()
        active_map = str(getattr(project, "last_active_map", "") or "").strip()
        context_text = " / ".join(part for part in (active_group, active_map) if part)
        detail = f"{context_text}  ·  {percent:.0f}%" if context_text else f"{percent:.0f}%"

        start = _run_start_time(job_id, snapshot_start)
        if start > 0.0:
            elapsed = runtime.format_duration(max(0.0, time.monotonic() - start))
            if elapsed:
                detail = f"{detail}  ·  {elapsed}"
        return title or "Baking", detail, percent / 100.0
    except Exception:
        return None


def _hex_rgba(hex_code: str) -> tuple[float, float, float, float]:
    digits = hex_code.strip().lstrip("#")
    return (
        int(digits[0:2], 16) / 255.0,
        int(digits[2:4], 16) / 255.0,
        int(digits[4:6], 16) / 255.0,
        1.0,
    )


#: Fallbacks matching Blender's stock dark theme, used only when a theme entry cannot
#: be read. Real colours come from the user's theme in _theme_hud().
_HUD_FILL = _hex_rgba("181818")
_HUD_STROKE = _hex_rgba("242424")
_HUD_TEXT = _hex_rgba("DDDDDD")
_HUD_TEXT_DIM = _hex_rgba("999999")
_HUD_PROGRESS = _hex_rgba("4772B3")
_HUD_BAR_INNER = _hex_rgba("222222")


def _srgb_to_linear(value: float) -> float:
    """Inverse of the sRGB transfer function, for one channel."""
    v = max(0.0, min(1.0, float(value)))
    if v <= 0.04045:
        return v / 12.92
    return ((v + 0.055) / 1.055) ** 2.4


def _gpu_color(color):
    """Theme colour (sRGB) -> the value to hand a GPU shader in this framebuffer.

    POST_PIXEL draw handlers render into an **sRGB framebuffer**: whatever a fragment
    shader writes is treated as linear and gamma-encoded on the way out. Blender's
    builtin shaders undo that themselves, but a shader built from GPUShaderCreateInfo
    (our round-rect one) does not -- so a theme colour uploaded verbatim landed on
    screen roughly twice as bright as the same value in Blender's own widgets
    (measured: theme 0x3D painted as 0x85). Undo the encode here so the card, its
    outline and the bar match the surrounding UI.

    Only the custom round-rect shader goes through this. ``blf`` and the builtin
    UNIFORM_COLOR fallback both take sRGB directly and would double-convert.
    """
    if color is None:
        return (0.0, 0.0, 0.0, 0.0)
    values = tuple(float(c) for c in color)
    rgb = tuple(_srgb_to_linear(c) for c in values[:3])
    alpha = float(values[3]) if len(values) > 3 else 1.0
    return rgb + (alpha,)


def _theme_rgba(source, attribute, fallback, alpha=None):
    """Read one theme colour as RGBA in sRGB, falling back when it is unavailable."""
    try:
        raw = tuple(float(c) for c in getattr(source, attribute))
    except Exception:
        return tuple(fallback)
    if not raw:
        return tuple(fallback)
    rgb = (raw + raw[-1:] * 3)[:3]
    if alpha is not None:
        return rgb + (float(alpha),)
    return rgb + ((float(raw[3]) if len(raw) > 3 else 1.0),)


def _status_hides_hud(message) -> bool:
    text = str(message or "").strip()
    if not text:
        return False
    if text in {
        constants.STATUS_IDLE,
        constants.STATUS_CANCELLED,
        constants.STATUS_COMPLETE,
        constants.STATUS_FAILED,
        "Bake Ready",
    }:
        return True
    lowered = text.lower()
    return lowered.startswith("bake complete") or lowered.startswith("finished baking")


def _mix_rgba(left, right, factor: float):
    t = max(0.0, min(1.0, float(factor)))
    return tuple(left[i] * (1.0 - t) + right[i] * t for i in range(4))


def _theme_hud(ui_scale: float):
    """HUD palette taken from the user's active Blender theme.

    The card is a floating panel over the viewport, so it borrows the same widget
    colours Blender gives its own popups (``wcol_menu_back``) and its own progress
    bars (``wcol_progress``). Every entry is read independently: a theme that is
    missing one key still gets the rest instead of falling back wholesale.
    """
    widget_unit = 20.0 * ui_scale
    theme = {
        "card_inner": _HUD_FILL,
        "card_outline": _HUD_STROKE,
        "card_roundness": 0.4,
        "title": _HUD_TEXT,
        "detail": _HUD_TEXT_DIM,
        "bar_inner": _HUD_BAR_INNER,
        "bar_fill": _HUD_PROGRESS,
        "bar_outline": _HUD_STROKE,
        "bar_roundness": 0.4,
        "shadow": (0.0, 0.0, 0.0, 0.0),
        "shadow_width": 0.0,
        "stroke_width": 1.0,
        "title_px": int(11.0 * ui_scale),
        "detail_px": int(11.0 * ui_scale),
        "widget_unit": widget_unit,
    }
    try:
        prefs = bpy.context.preferences
        system = prefs.system
        ui = prefs.themes[0].user_interface
        styles = prefs.ui_styles[0]
    except Exception:
        return theme

    menu_back = getattr(ui, "wcol_menu_back", None)
    if menu_back is not None:
        theme["card_inner"] = _theme_rgba(menu_back, "inner", theme["card_inner"])
        theme["card_outline"] = _theme_rgba(menu_back, "outline", theme["card_outline"], alpha=1.0)
        theme["detail"] = _theme_rgba(menu_back, "text", theme["detail"], alpha=1.0)

    menu_item = getattr(ui, "wcol_menu_item", None)
    if menu_item is not None:
        theme["title"] = _theme_rgba(menu_item, "text", theme["title"], alpha=1.0)

    progress = getattr(ui, "wcol_progress", None)
    if progress is not None:
        theme["bar_inner"] = _theme_rgba(progress, "inner", theme["bar_inner"], alpha=1.0)
        theme["bar_fill"] = _theme_rgba(progress, "item", theme["bar_fill"], alpha=1.0)
        theme["bar_outline"] = _theme_rgba(progress, "outline", theme["bar_outline"], alpha=1.0)
        try:
            theme["bar_roundness"] = float(progress.roundness)
        except Exception:
            pass

    # Secondary text that reads as a label rather than a heading. Some themes leave
    # menu_back.text almost as bright as the title, so bias it toward the card.
    theme["detail"] = _mix_rgba(theme["title"], theme["detail"], 0.75)

    # Blender's own drop shadow behind popups, so the card lifts off the viewport the
    # same amount every other floating panel does.
    try:
        shadow_fac = float(getattr(ui, "menu_shadow_fac", 0.0) or 0.0)
        shadow_width = float(getattr(ui, "menu_shadow_width", 0.0) or 0.0)
        if shadow_fac > 0.0 and shadow_width > 0.0:
            theme["shadow"] = (0.0, 0.0, 0.0, max(0.0, min(1.0, shadow_fac)))
            theme["shadow_width"] = shadow_width * ui_scale
    except Exception:
        pass

    try:
        pixel_size = float(getattr(system, "pixel_size", 1.0) or 1.0)
        roundness = getattr(ui, "panel_roundness", None)
        if roundness is None:
            roundness = getattr(menu_back, "roundness", 0.4)
        theme["card_roundness"] = float(roundness)
        theme["stroke_width"] = max(1.0, pixel_size)
        widget_points = float(getattr(styles.widget, "points", 11.0) or 11.0)
        theme["title_px"] = max(1, int(widget_points * ui_scale))
        theme["detail_px"] = theme["title_px"]
    except Exception:
        pass
    return theme


def _pixel_radius(roundness: float, width: float, height: float, widget_unit: float) -> float:
    cap = 0.5 * min(width, height)
    return min(cap, max(0.0, float(roundness)) * widget_unit * 0.5)


def _get_round_rect_shader():
    global _ROUND_SHADER
    if _ROUND_SHADER is not None:
        return _ROUND_SHADER if _ROUND_SHADER is not False else None
    try:
        vert_out = gpu.types.GPUStageInterfaceInfo("fyr_hud_round_rect_iface")
        vert_out.smooth("VEC2", "v_pos")
        info = gpu.types.GPUShaderCreateInfo()
        info.vertex_out(vert_out)
        info.vertex_in(0, "VEC2", "pos")
        info.push_constant("MAT4", "ModelViewProjectionMatrix")
        info.push_constant("VEC4", "rectMinMax")
        info.push_constant("FLOAT", "radius")
        info.push_constant("FLOAT", "strokeWidth")
        info.push_constant("VEC4", "fillColor")
        info.push_constant("VEC4", "strokeColor")
        info.fragment_out(0, "VEC4", "FragColor")
        info.vertex_source(
            """
            void main()
            {
              v_pos = pos;
              gl_Position = ModelViewProjectionMatrix * vec4(pos, 0.0, 1.0);
            }
            """
        )
        info.fragment_source(
            """
            float sdRoundBox(vec2 p, vec2 b, float r)
            {
              r = min(r, min(b.x, b.y));
              vec2 q = abs(p) - b + vec2(r);
              return min(max(q.x, q.y), 0.0) + length(max(q, 0.0)) - r;
            }

            void main()
            {
              vec2 center = 0.5 * (rectMinMax.xy + rectMinMax.zw);
              vec2 halfSize = 0.5 * (rectMinMax.zw - rectMinMax.xy);
              float dist = sdRoundBox(v_pos - center, halfSize, radius);
              float aa = max(fwidth(dist), 1e-5);
              float outer = 1.0 - smoothstep(-aa, aa, dist);
              float inner = 1.0 - smoothstep(-aa, aa, dist + strokeWidth);
              vec4 fill = fillColor;
              fill.a *= inner;
              vec4 stroke = strokeColor;
              stroke.a *= clamp(outer - inner, 0.0, 1.0);
              float outA = stroke.a + fill.a * (1.0 - stroke.a);
              vec3 outRgb = (stroke.rgb * stroke.a + fill.rgb * fill.a * (1.0 - stroke.a))
                            / max(outA, 1e-5);
              FragColor = vec4(outRgb, outA);
            }
            """
        )
        _ROUND_SHADER = gpu.shader.create_from_info(info)
        del info
    except Exception:
        _ROUND_SHADER = False
        return None
    return _ROUND_SHADER


def _draw_rect(shader, x0: float, y0: float, x1: float, y1: float, color) -> None:
    batch = batch_for_shader(
        shader,
        "TRI_FAN",
        {"pos": [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]},
    )
    shader.bind()
    # NOTE: this path uses the builtin UNIFORM_COLOR shader, which applies the sRGB
    # transform itself. Passing the theme colour through _gpu_color() here would
    # double-convert and paint the fallback card far too dark.
    shader.uniform_float("color", color)
    batch.draw(shader)


def _draw_round_rect(shader, mvp, x0, y0, x1, y1, radius, fill, stroke, stroke_width) -> None:
    pad = max(2.0, float(stroke_width) + 1.5)
    batch = batch_for_shader(
        shader,
        "TRI_FAN",
        {
            "pos": [
                (x0 - pad, y0 - pad),
                (x1 + pad, y0 - pad),
                (x1 + pad, y1 + pad),
                (x0 - pad, y1 + pad),
            ]
        },
    )
    shader.bind()
    shader.uniform_float("ModelViewProjectionMatrix", mvp)
    shader.uniform_float("rectMinMax", (x0, y0, x1, y1))
    shader.uniform_float("radius", float(radius))
    shader.uniform_float("strokeWidth", float(stroke_width))
    shader.uniform_float("fillColor", _gpu_color(fill))
    shader.uniform_float("strokeColor", _gpu_color(stroke))
    batch.draw(shader)


def _draw() -> None:
    if _explicit_state_is_stale():
        end()
    state = (_TITLE, _DETAIL, _FACTOR) if _ACTIVE else _running_bake_state()
    if state is None:
        return
    try:
        title, detail, factor = state
        region = bpy.context.region
        if region is None or getattr(bpy.context.area, "type", None) != "VIEW_3D":
            return
        width = float(region.width)
        try:
            ui_scale = float(bpy.context.preferences.system.ui_scale)
        except Exception:
            ui_scale = 1.0

        theme = _theme_hud(ui_scale)
        font_id = 0
        title_px = theme["title_px"]
        detail_px = theme["detail_px"]
        pad = 14.0 * ui_scale
        gap = 6.0 * ui_scale
        bar_h = 6.0 * ui_scale
        stroke = theme["stroke_width"]

        blf.size(font_id, title_px)
        title_w, title_h = blf.dimensions(font_id, title)
        blf.size(font_id, detail_px)
        detail_w, detail_h = blf.dimensions(font_id, detail)

        box_w = max(title_w, detail_w, 280.0 * ui_scale) + pad * 2.0
        box_h = title_h + gap + detail_h + gap + bar_h + pad * 2.0
        x0 = (width - box_w) * 0.5
        y0 = 34.0 * ui_scale
        x1 = x0 + box_w
        y1 = y0 + box_h
        card_radius = _pixel_radius(theme["card_roundness"], box_w, box_h, theme["widget_unit"])

        gpu.state.blend_set("ALPHA")
        round_shader = _get_round_rect_shader()
        mvp = None
        if round_shader is not None:
            mvp = gpu.matrix.get_projection_matrix() @ gpu.matrix.get_model_view_matrix()
            shadow_w = theme["shadow_width"]
            if shadow_w > 0.0 and theme["shadow"][3] > 0.0:
                _draw_round_rect(
                    round_shader,
                    mvp,
                    x0,
                    y0 - shadow_w * 0.35,
                    x1,
                    y1 - shadow_w * 0.15,
                    card_radius + shadow_w * 0.25,
                    theme["shadow"],
                    (0.0, 0.0, 0.0, 0.0),
                    0.0,
                )
            _draw_round_rect(
                round_shader,
                mvp,
                x0,
                y0,
                x1,
                y1,
                card_radius,
                theme["card_inner"],
                theme["card_outline"],
                stroke,
            )
        else:
            fallback = gpu.shader.from_builtin("UNIFORM_COLOR")
            _draw_rect(fallback, x0, y0, x1, y1, theme["card_inner"])

        bar_x = x0 + pad
        bar_y = y0 + pad
        bar_w = box_w - pad * 2.0
        bar_radius = 0.5 * bar_h
        if round_shader is not None and mvp is not None:
            _draw_round_rect(
                round_shader,
                mvp,
                bar_x,
                bar_y,
                bar_x + bar_w,
                bar_y + bar_h,
                bar_radius,
                theme["bar_inner"],
                theme["bar_outline"],
                stroke,
            )
            if factor is None:
                fill_x = bar_x + bar_w * 0.35
                fill_w = bar_w * 0.30
            else:
                fill_x = bar_x
                fill_w = bar_w * max(0.0, min(1.0, float(factor)))
            if fill_w > 0.5:
                fill_w = max(fill_w, bar_h)
                fill_w = min(fill_w, bar_w)
                if fill_x + fill_w > bar_x + bar_w:
                    fill_x = bar_x + bar_w - fill_w
                _draw_round_rect(
                    round_shader,
                    mvp,
                    fill_x,
                    bar_y,
                    fill_x + fill_w,
                    bar_y + bar_h,
                    bar_radius,
                    theme["bar_fill"],
                    (0.0, 0.0, 0.0, 0.0),
                    0.0,
                )
        else:
            fallback = gpu.shader.from_builtin("UNIFORM_COLOR")
            _draw_rect(fallback, bar_x, bar_y, bar_x + bar_w, bar_y + bar_h, theme["bar_inner"])
            if factor is None:
                fill_x = bar_x + bar_w * 0.35
                fill_w = bar_w * 0.30
            else:
                fill_x = bar_x
                fill_w = bar_w * max(0.0, min(1.0, float(factor)))
            if fill_w > 0.0:
                _draw_rect(
                    fallback,
                    fill_x,
                    bar_y,
                    fill_x + fill_w,
                    bar_y + bar_h,
                    theme["bar_fill"],
                )
        gpu.state.blend_set("NONE")

        shadow_enabled = False
        try:
            blf.enable(font_id, blf.SHADOW)
            blf.shadow(font_id, 3, 0.0, 0.0, 0.0, 0.5)
            blf.shadow_offset(font_id, 0, -1)
            shadow_enabled = True
        except Exception:
            shadow_enabled = False

        title_y = y1 - pad - title_h
        blf.size(font_id, title_px)
        blf.color(font_id, *theme["title"])
        blf.position(font_id, x0 + (box_w - title_w) * 0.5, title_y, 0.0)
        blf.draw(font_id, title)

        blf.size(font_id, detail_px)
        blf.color(font_id, *theme["detail"])
        blf.position(font_id, x0 + (box_w - detail_w) * 0.5, title_y - gap - detail_h, 0.0)
        blf.draw(font_id, detail)
        if shadow_enabled:
            blf.disable(font_id, blf.SHADOW)
    except Exception:
        # Draw handlers must never break the viewport.
        pass


def _ensure_handler() -> None:
    global _HANDLER
    if _HANDLER is not None:
        return
    try:
        _HANDLER = bpy.types.SpaceView3D.draw_handler_add(_draw, (), "WINDOW", "POST_PIXEL")
    except Exception:
        _HANDLER = None
        print("[Fyr Baker] progress HUD unavailable:\n" + traceback.format_exc())


def begin(title: str, detail: str = "", factor: float | None = None) -> None:
    global _ACTIVE, _TITLE, _DETAIL, _FACTOR, _ACTIVE_AT, _SUPPRESSED_KEY
    _TITLE = str(title or "Please wait…")
    _DETAIL = str(detail or "")
    _FACTOR = factor
    _ACTIVE = True
    _ACTIVE_AT = time.monotonic()
    # A fresh explicit run clears a stale manual dismiss; otherwise dismissing once
    # would keep hiding progress for every later run that reuses the same job id.
    _SUPPRESSED_KEY = ""
    _ensure_handler()
    _tag_redraw_all_view3d()


def current_title() -> str:
    """Title of the explicit card on screen ("" when none), so a second producer can
    tell it does not own the card."""
    return _TITLE if _ACTIVE else ""


def update(detail: str, factor: float | None = None) -> None:
    global _DETAIL, _FACTOR, _ACTIVE_AT
    if not _ACTIVE:
        return
    _DETAIL = str(detail or "")
    _FACTOR = factor
    _ACTIVE_AT = time.monotonic()
    _tag_redraw_all_view3d()


def end() -> None:
    global _ACTIVE, _TITLE, _DETAIL, _FACTOR, _ACTIVE_AT
    _ACTIVE = False
    _TITLE = ""
    _DETAIL = ""
    _FACTOR = None
    _ACTIVE_AT = 0.0
    _tag_redraw_all_view3d()


def _explicit_state_is_stale() -> bool:
    """Explicit mode left up by a path that never reached its end().

    begin()/end() are not paired through an exception, and a few operators can bail
    between them. Rather than trust every caller, the card expires on its own.
    """
    return bool(_ACTIVE and _ACTIVE_AT > 0.0 and (time.monotonic() - _ACTIVE_AT) > _EXPLICIT_MAX_AGE)


def force_dismiss() -> bool:
    """Hide the HUD now, whichever mode is showing it. True if anything was showing.

    Explicit mode is torn down. The derived (bake-driven) card cannot simply be torn
    down -- it is recomputed on every redraw -- so the identity currently showing is
    remembered and skipped until a different bake comes along. Dismissing never stops
    the bake itself; :class:`MASTER_BAKER_OT_cancel_bake` is what does that.
    """
    global _SUPPRESSED_KEY
    dismissed = False
    if _ACTIVE:
        end()
        dismissed = True
    identity = None
    try:
        identity = _live_bake_identity()
    except Exception:
        identity = None
    if identity is not None:
        _SUPPRESSED_KEY = _identity_key(identity[0])
        dismissed = True
    _tag_redraw_all_view3d()
    return dismissed


def is_showing() -> bool:
    """Whether the HUD is drawing anything right now, in either mode.

    Distinct from :func:`is_active`, which only reports the explicit begin/end mode.
    The dismiss button keys off this one so it also appears for a bake-driven card.
    """
    if _ACTIVE and not _explicit_state_is_stale():
        return True
    try:
        return _running_bake_state() is not None
    except Exception:
        return False


def is_active() -> bool:
    return _ACTIVE


def register() -> None:
    _ensure_handler()


def unregister() -> None:
    global _HANDLER
    end()
    if _HANDLER is not None:
        try:
            bpy.types.SpaceView3D.draw_handler_remove(_HANDLER, "WINDOW")
        except Exception:
            pass
        _HANDLER = None
