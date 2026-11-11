from __future__ import annotations

from . import constants


def clamp_mip_level(level: int) -> int:
    return max(0, min(int(level), int(constants.IMAGE_EDITOR_MAX_MIP_LEVEL)))


def zoom_percentage_for_mip(level: int) -> float:
    return 100.0 / float(2 ** clamp_mip_level(level))


def pixel_coordinates_from_cursor(cursor_location, width: int, height: int) -> tuple[int, int]:
    cursor_x = float(cursor_location[0]) if len(cursor_location) > 0 else 0.0
    cursor_y = float(cursor_location[1]) if len(cursor_location) > 1 else 0.0
    pixel_x = min(max(int(cursor_x * int(width)), 0), max(int(width) - 1, 0))
    pixel_y = min(max(int(cursor_y * int(height)), 0), max(int(height) - 1, 0))
    return pixel_x, pixel_y


def _normalized_rgba_from_channels(raw_channels: list[float], channel_count: int) -> tuple[float, float, float, float]:
    if channel_count <= 0:
        return 0.0, 0.0, 0.0, 1.0
    if channel_count == 1:
        value = raw_channels[0]
        return value, value, value, 1.0
    if channel_count == 2:
        value, alpha = raw_channels
        return value, value, value, alpha
    if channel_count == 3:
        return raw_channels[0], raw_channels[1], raw_channels[2], 1.0
    return raw_channels[0], raw_channels[1], raw_channels[2], raw_channels[3]


def sample_image_at_cursor(image, cursor_location):
    if image is None:
        return None
    size = tuple(getattr(image, "size", ()) or ())
    if len(size) < 2:
        return None
    width = int(size[0])
    height = int(size[1])
    if width <= 0 or height <= 0:
        return None

    pixels = getattr(image, "pixels", None)
    if pixels is None:
        return None

    channel_count = max(1, int(getattr(image, "channels", 4) or 4))
    pixel_x, pixel_y = pixel_coordinates_from_cursor(cursor_location, width, height)
    base_index = (pixel_y * width + pixel_x) * channel_count
    try:
        raw_channels = [float(pixels[base_index + offset]) for offset in range(channel_count)]
    except (IndexError, TypeError, ValueError):
        return None

    rgba = _normalized_rgba_from_channels(raw_channels, channel_count)
    return {
        "pixel": (pixel_x, pixel_y),
        "size": (width, height),
        "uv": (
            float(cursor_location[0]) if len(cursor_location) > 0 else 0.0,
            float(cursor_location[1]) if len(cursor_location) > 1 else 0.0,
        ),
        "rgba": rgba,
    }


def channel_value_for_mode(rgba: tuple[float, float, float, float], channel_mode: str):
    if channel_mode == constants.IMAGE_CHANNEL_ALPHA:
        return float(rgba[3])
    if channel_mode == constants.IMAGE_CHANNEL_RED:
        return float(rgba[0])
    if channel_mode == constants.IMAGE_CHANNEL_GREEN:
        return float(rgba[1])
    if channel_mode == constants.IMAGE_CHANNEL_BLUE:
        return float(rgba[2])
    if channel_mode == constants.IMAGE_CHANNEL_COLOR:
        return float(rgba[0]), float(rgba[1]), float(rgba[2])
    return float(rgba[0]), float(rgba[1]), float(rgba[2]), float(rgba[3])
