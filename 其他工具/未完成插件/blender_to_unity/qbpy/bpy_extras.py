import bpy
from bpy_extras.view3d_utils import *
import mathutils


def r2d_to_v3d(event, coord=None) -> mathutils.Vector:
    """Return a direction vector from the viewport at the specific 2D region coordinate.

    coord (2d vector) - 2d coordinates relative to the region: (event.mouse_region_x, event.mouse_region_y) for example.
    return (3d Vector) - normalized 3d vector.
    """
    if coord is None:
        coord = (event.mouse_region_x, event.mouse_region_y)
    return region_2d_to_vector_3d(bpy.context.region, bpy.context.region_data, coord)


def r2d_to_o3d(event, coord=None, clamp=None) -> mathutils.Vector:
    """Return the 3d view origin from the region relative 2d coords.

    coord (2d vector) - 2d coordinates relative to the region; (event.mouse_region_x, event.mouse_region_y) for example.
    clamp (float or None) - Clamp the maximum far-clip value used. (negative value will move the offset away from the view_location).
    return (3d Vector) - The origin of the viewpoint in 3d space.
    """
    if coord is None:
        coord = (event.mouse_region_x, event.mouse_region_y)
    return region_2d_to_origin_3d(bpy.context.region, bpy.context.region_data, coord, clamp)


def r2d_to_l3d(event, coord=None, depth_location=(0, 0, 0)) -> mathutils.Vector:
    """Return a 3d location from the region relative 2d coords, aligned with depth_location.

    coord (2d vector) - 2d coordinates relative to the region; (event.mouse_region_x, event.mouse_region_y) for example.
    depth_location (3d vector) - the returned vectors depth is aligned with this since there is no defined depth with a 2d region input.
    return (3d Vector) - normalized 3d vector.
    """
    if coord is None:
        coord = (event.mouse_region_x, event.mouse_region_y)
    return region_2d_to_location_3d(bpy.context.region, bpy.context.region_data, coord, depth_location)


def l3d_to_r2d(coord=(0, 0, 0)) -> mathutils.Vector:
    """Return the region relative 2d location of a 3d position.

    coord (3d Vector) - 3D worldspace location.
    return (2d Vector) - 2d location.
    """
    return location_3d_to_region_2d(bpy.context.region, bpy.context.region_data, coord, default=None)
