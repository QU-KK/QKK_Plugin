import os
from bpy.utils import previews
from .paths import RBDLabPaths

preview_collections = {}


def get_icon(idname: str) -> int:
    if "logos" not in preview_collections:
        return None
    pcoll = preview_collections["logos"]
    if idname not in pcoll:
        return None
    return pcoll[idname].icon_id


def register():
    icons_path = RBDLabPaths.LIBS_ICONS
    pcoll_logo = previews.new()
    # pcoll_logo.load("RBDLab_Logo_256", os.path.join(icons_path, "RBDLab_Logo_256.png"), 'IMAGE')
    # pcoll_logo.load("RBDLab_Logo_256", os.path.join(icons_path, "RBDLab_Logo_2_256.png"), 'IMAGE')
    pcoll_logo.load("RBDLab_Logo_256", os.path.join(icons_path, "RBDLab_Logo_3_256.png"), 'IMAGE')
    pcoll_logo.load("PolyHeaven_Logo_256", os.path.join(icons_path, "PolyHeaven_Logo_256.png"), 'IMAGE')
    preview_collections["logos"] = pcoll_logo


def unregister():
    for pcoll in preview_collections.values():
        previews.remove(pcoll)

    preview_collections.clear()
