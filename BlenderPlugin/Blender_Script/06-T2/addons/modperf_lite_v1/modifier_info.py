# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Supra3D
"""Modifier facts mirrored from Blender's source (flags, disabled state, cage)."""

from .constants import HEADER_TOGGLES, MODIFIER_FLAGS, NO_TOGGLE_TYPES


def _mod_flags(mod):
    return MODIFIER_FLAGS.get(mod.bl_rna.identifier, (1, 0))


def _ob_is(ob, *types):
    return ob is not None and ob.type in types


def _mod_is_disabled(scene, mod):
    """Python port of each modifier's ModifierTypeInfo::is_disabled()."""
    t = mod.type
    g = lambda a, d=None: getattr(mod, a, d)
    try:
        if t == 'ARMATURE':
            return not _ob_is(g('object'), 'ARMATURE')
        if t == 'ARRAY':
            return ((g('curve') is not None and g('curve').type != 'CURVE')
                    or (g('start_cap') is not None and g('start_cap').type != 'MESH')
                    or (g('end_cap') is not None and g('end_cap').type != 'MESH'))
        if t == 'BEVEL':
            return g('width', 1.0) == 0.0
        if t == 'BOOLEAN':
            if g('operand_type') == 'OBJECT':
                return not _ob_is(g('object'), 'MESH')
            if g('operand_type') == 'COLLECTION':
                return g('collection') is None and g('solver') != 'EXACT'
            return False
        if t in {'CAST', 'SMOOTH'}:
            axes = g('use_x') or g('use_y') or g('use_z')
            return g('factor', 1.0) == 0.0 or not axes
        if t == 'CURVE':
            return not _ob_is(g('object'), 'CURVE')
        if t == 'DATA_TRANSFER':
            return not _ob_is(g('object'), 'MESH')
        if t == 'DISPLACE':
            return ((g('texture') is None and g('direction') == 'RGB_TO_XYZ')
                    or g('strength', 1.0) == 0.0)
        if t == 'HOOK':
            return g('object') is None
        if t == 'LAPLACIANDEFORM':
            return not g('vertex_group')
        if t == 'LAPLACIANSMOOTH':
            return not (g('use_x') or g('use_y') or g('use_z'))
        if t == 'LATTICE':
            return not _ob_is(g('object'), 'LATTICE')
        if t == 'MASK':
            return g('armature') is not None and g('armature').type != 'ARMATURE'
        if t == 'MESH_CACHE':
            return g('factor', 1.0) <= 0.0 or not g('filepath')
        if t == 'MESH_DEFORM':
            return not _ob_is(g('object'), 'MESH')
        if t == 'MESH_SEQUENCE_CACHE':
            return g('cache_file') is None or not g('object_path')
        if t == 'NODES':
            return g('node_group') is None
        if t == 'SHRINKWRAP':
            aux = g('auxiliary_target')
            return not _ob_is(g('target'), 'MESH') or (aux is not None and aux.type != 'MESH')
        if t == 'SUBSURF':
            levels = g('levels', 1)
            if scene is not None and scene.render.use_simplify:
                levels = min(levels, scene.render.simplify_subdivision)
            return levels == 0
        if t == 'SURFACE_DEFORM':
            return not _ob_is(g('target'), 'MESH') and not g('is_bound')
        if t == 'WARP':
            return g('object_from') is None or g('object_to') is None
        if t == 'VERTEX_WEIGHT_EDIT':
            return not g('vertex_group')
        if t == 'VERTEX_WEIGHT_MIX':
            return not g('vertex_group_a')
        if t == 'VERTEX_WEIGHT_PROXIMITY':
            return not g('vertex_group') or g('target') is None
    except (AttributeError, ReferenceError):
        pass
    return False


def _cage_info(scene, ob):
    """BKE_modifiers_get_cage_index(): (cage_index, last_possible_cage_index)."""
    cage, last = -1, -1
    for i, md in enumerate(ob.modifiers):
        editmode, mapping = _mod_flags(md)
        if _mod_is_disabled(scene, md) or not editmode:
            continue
        if mapping:
            last = i
        if not md.show_viewport or not md.show_in_editmode:
            continue
        if not mapping:
            break
        if md.show_on_cage:
            cage = i
    return cage, last


def _header_toggles(scene, ob, mod, index):
    """Toggles Blender draws in this modifier's header, left -> right:
    list of (flag, icon, tooltip, active)."""
    out = []
    editmode, mapping = _mod_flags(mod)
    disabled = _mod_is_disabled(scene, mod)
    if ob.type == 'MESH':
        cage, last = _cage_info(scene, ob)
        if not disabled and editmode and mapping and index <= last:
            could = mod.show_viewport and mod.show_in_editmode and not disabled and mapping
            out.append(HEADER_TOGGLES[0] + (not (index < cage or not could),))
    if mod.type not in NO_TOGGLE_TYPES:
        if ob.type != 'EMPTY' and editmode:
            out.append(HEADER_TOGGLES[1] + (mod.show_viewport,))
        out.append(HEADER_TOGGLES[2] + (True,))
        out.append(HEADER_TOGGLES[3] + (True,))
    return out
