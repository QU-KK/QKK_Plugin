# SPDX-License-Identifier: GPL-2.0-or-later
# Applied-bevel boundary solving was removed in v27.223. Selected quad bevel
# faces now stay fully covered while Face Width extends the decal across both
# neighboring surfaces.

EDGEDECAL_ADDON_VERSION = (1, 2, 1)

import bpy
from bpy.app.handlers import persistent
import bmesh
import random
import json
import heapq
from math import radians, acos, degrees, pi, atan2, cos, sin
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree
from bpy.props import BoolProperty, FloatProperty, FloatVectorProperty, IntProperty, StringProperty, PointerProperty, CollectionProperty, EnumProperty
from bpy.types import AddonPreferences, Operator, Panel, PropertyGroup, UIList

import gpu
import time
import hashlib
from array import array
import blf
from gpu_extras.batch import batch_for_shader
from bpy_extras import view3d_utils

EDGEDECAL_UV_PIN_DRAW_HANDLE = None
EDGEDECAL_ADDON_KEYMAPS = []
EDGEDECAL_INTERACTIVE_RUNNING = False
EDGEDECAL_STANDALONE_GENERATION = False
EDGEDECAL_SETTINGS_SYNCING = False
EDGEDECAL_REGENERATE_TARGET = None


EPSILON = 1.0e-8
MIN_FACE_WIDTH = 0.001
COLLECTION_NAME = "Edge Decals"
DEFAULT_MATERIAL_NAME = "M_Edge_Decal"




# Feature modules are executed into this package namespace in dependency order.
# This conservative architecture keeps the original add-on behavior and global
# references intact while making each feature area independently maintainable.
import os as _os

_FEATURE_FILES = (
    "core_state.py",
    "texture_masks.py",
    "geometry.py",
    "surface_voronoi.py",
    "uv_processing.py",
    "generation.py",
    "intersections.py",
    "bundled_assets.py",
    "presets.py",
    "uv_pins.py",
    "ui_sections.py",
    "interactive.py",
    "unreal_export.py",
    "layers.py",
    "lifecycle.py",
)

def _load_feature_file(_filename):
    _path = _os.path.join(_os.path.dirname(__file__), "features", _filename)
    with open(_path, "r", encoding="utf-8") as _handle:
        _source = _handle.read()
    exec(compile(_source, _path, "exec"), globals(), globals())

for _feature_file in _FEATURE_FILES:
    _load_feature_file(_feature_file)

del _feature_file
del _load_feature_file
del _FEATURE_FILES
del _os
