from __future__ import annotations

from collections.abc import Callable


def matching_error_overlay_passes_from_debug_result(
    cache: dict[int, tuple[object, list[object]]],
    debug_result,
    theme,
    *,
    include_inside: bool,
    build_lit_batch_from_positions_fn: Callable[..., object],
    make_lit_heatmap_overlay_pass_fn: Callable[..., object],
    max_cache_entries: int = 8,
) -> list[object]:
    cache_key = (
        id(debug_result),
        bool(include_inside),
        tuple(float(component) for component in theme.heatmap_low_fill),
        tuple(float(component) for component in theme.heatmap_medium_fill),
        tuple(float(component) for component in theme.heatmap_high_fill),
    )
    cached_entry = cache.get(cache_key)
    cached_passes = None
    if cached_entry is not None and cached_entry[0] is debug_result:
        cached_passes = cached_entry[1]
    if cached_passes is not None:
        return cached_passes

    passes: list[object] = []
    if include_inside:
        low_fill_batch = build_lit_batch_from_positions_fn(
            getattr(debug_result, "heatmap_low_fill_positions", []),
            theme.heatmap_low_fill,
            normals=getattr(debug_result, "heatmap_low_fill_normals", []),
        )
        if low_fill_batch is not None:
            passes.append(
                make_lit_heatmap_overlay_pass_fn(
                    low_fill_batch,
                    theme.heatmap_low_fill,
                    blend_mode=None,
                    face_culling_mode="BACK",
                )
            )
        medium_fill_batch = build_lit_batch_from_positions_fn(
            getattr(debug_result, "heatmap_medium_fill_positions", []),
            theme.heatmap_medium_fill,
            normals=getattr(debug_result, "heatmap_medium_fill_normals", []),
        )
        if medium_fill_batch is not None:
            passes.append(
                make_lit_heatmap_overlay_pass_fn(
                    medium_fill_batch,
                    theme.heatmap_medium_fill,
                    blend_mode="ALPHA",
                    face_culling_mode="BACK",
                )
            )
    high_fill_batch = build_lit_batch_from_positions_fn(
        getattr(debug_result, "heatmap_high_fill_positions", []),
        theme.heatmap_high_fill,
        normals=getattr(debug_result, "heatmap_high_fill_normals", []),
    )
    if high_fill_batch is not None:
        passes.append(
            make_lit_heatmap_overlay_pass_fn(
                high_fill_batch,
                theme.heatmap_high_fill,
                blend_mode=None,
                face_culling_mode="BACK",
            )
        )
    if len(cache) >= max_cache_entries:
        cache.clear()
    cache[cache_key] = (debug_result, passes)
    return passes


def heatmap_overlay_passes_from_debug_result(
    cache: dict[int, tuple[object, list[object]]],
    debug_result,
    theme,
    *,
    include_inside: bool,
    build_lit_batch_from_positions_fn: Callable[..., object],
    make_lit_heatmap_overlay_pass_fn: Callable[..., object],
    max_cache_entries: int = 8,
) -> list[object]:
    return matching_error_overlay_passes_from_debug_result(
        cache,
        debug_result,
        theme,
        include_inside=include_inside,
        build_lit_batch_from_positions_fn=build_lit_batch_from_positions_fn,
        make_lit_heatmap_overlay_pass_fn=make_lit_heatmap_overlay_pass_fn,
        max_cache_entries=max_cache_entries,
    )


def debug_result_view_matches_context(
    context,
    debug_result,
    *,
    current_debug_view_fn: Callable[[object], object],
) -> bool:
    if debug_result is None:
        return False
    current_view = current_debug_view_fn(context)
    if current_view is None:
        return False
    current_signature = str(getattr(current_view, "view_signature", "") or "")
    result_signature = str(getattr(debug_result, "view_signature", "") or "")
    return bool(current_signature and result_signature and current_signature == result_signature)
