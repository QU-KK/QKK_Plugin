from __future__ import annotations


class OverlayTheme:
    __slots__ = (
        "low_fill",
        "low_line",
        "high_fill",
        "high_line",
        "cage_fill",
        "cage_line",
        "heatmap_low_fill",
        "heatmap_medium_fill",
        "heatmap_high_fill",
        "skew_fill",
        "skew_line",
        "miss_line",
        "low_line_width",
        "high_line_width",
        "cage_line_width",
        "skew_line_width",
        "miss_line_width",
    )

    def __init__(
        self,
        *,
        low_fill: tuple[float, float, float, float],
        low_line: tuple[float, float, float, float],
        high_fill: tuple[float, float, float, float],
        high_line: tuple[float, float, float, float],
        cage_fill: tuple[float, float, float, float],
        cage_line: tuple[float, float, float, float],
        heatmap_low_fill: tuple[float, float, float, float],
        heatmap_medium_fill: tuple[float, float, float, float],
        heatmap_high_fill: tuple[float, float, float, float],
        skew_fill: tuple[float, float, float, float],
        skew_line: tuple[float, float, float, float],
        miss_line: tuple[float, float, float, float],
        low_line_width: float = 1.0,
        high_line_width: float = 1.25,
        cage_line_width: float = 2.0,
        skew_line_width: float = 0.0,
        miss_line_width: float = 1.6,
    ) -> None:
        self.low_fill = low_fill
        self.low_line = low_line
        self.high_fill = high_fill
        self.high_line = high_line
        self.cage_fill = cage_fill
        self.cage_line = cage_line
        self.heatmap_low_fill = heatmap_low_fill
        self.heatmap_medium_fill = heatmap_medium_fill
        self.heatmap_high_fill = heatmap_high_fill
        self.skew_fill = skew_fill
        self.skew_line = skew_line
        self.miss_line = miss_line
        self.low_line_width = low_line_width
        self.high_line_width = high_line_width
        self.cage_line_width = cage_line_width
        self.skew_line_width = skew_line_width
        self.miss_line_width = miss_line_width


def build_overlay_theme(
    *,
    cage_opacity: float = 1.0,
    cage_surface_opacity: float | None = None,
    cage_wireframe_opacity: float | None = None,
    low_reference_color: tuple[float, float, float] | None = None,
    cage_surface_color: tuple[float, float, float] | None = None,
    cage_wireframe_color: tuple[float, float, float] | None = None,
    heatmap_inside_color: tuple[float, float, float] | None = None,
    heatmap_outside_color: tuple[float, float, float] | None = None,
) -> OverlayTheme:
    def _rgb(color_value, fallback):
        if color_value is None:
            return fallback
        return (
            max(0.0, min(1.0, float(color_value[0]))),
            max(0.0, min(1.0, float(color_value[1]))),
            max(0.0, min(1.0, float(color_value[2]))),
        )

    opacity = max(0.0, min(1.0, float(cage_opacity)))
    surface_opacity = 0.42 if cage_surface_opacity is None else max(0.0, min(1.0, float(cage_surface_opacity)))
    wireframe_opacity = 0.38 if cage_wireframe_opacity is None else max(0.0, min(1.0, float(cage_wireframe_opacity)))
    low_rgb = _rgb(low_reference_color, (0.72, 0.80, 0.88))
    cage_surface_rgb = _rgb(cage_surface_color, (0.18, 0.88, 0.46))
    cage_wireframe_rgb = _rgb(cage_wireframe_color, (0.32, 1.0, 0.62))
    heatmap_inside_rgb = _rgb(heatmap_inside_color, (0.12, 0.46, 1.0))
    heatmap_outside_rgb = _rgb(heatmap_outside_color, (1.0, 0.08, 0.08))
    if low_rgb == (0.72, 0.80, 0.88):
        low_fill = (0.32, 0.37, 0.42, 0.06)
    else:
        low_fill = (low_rgb[0] * 0.4444444444, low_rgb[1] * 0.4625, low_rgb[2] * 0.4772727273, 0.06)
    return OverlayTheme(
        low_fill=low_fill,
        low_line=(low_rgb[0], low_rgb[1], low_rgb[2], 0.20),
        high_fill=(1.0, 0.48, 0.12, 0.08),
        high_line=(1.0, 0.60, 0.22, 0.0),
        cage_fill=(cage_surface_rgb[0], cage_surface_rgb[1], cage_surface_rgb[2], surface_opacity * opacity),
        cage_line=(cage_wireframe_rgb[0], cage_wireframe_rgb[1], cage_wireframe_rgb[2], wireframe_opacity * opacity),
        heatmap_low_fill=(heatmap_inside_rgb[0], heatmap_inside_rgb[1], heatmap_inside_rgb[2], 1.0),
        heatmap_medium_fill=(1.0, 0.74, 0.18, 0.85),
        heatmap_high_fill=(heatmap_outside_rgb[0], heatmap_outside_rgb[1], heatmap_outside_rgb[2], 1.0),
        skew_fill=(1.0, 0.48, 0.08, 0.0),
        skew_line=(1.0, 0.72, 0.24, 0.92),
        miss_line=(1.0, 0.10, 0.10, 0.96),
        skew_line_width=1.25,
        cage_line_width=1.1,
    )
