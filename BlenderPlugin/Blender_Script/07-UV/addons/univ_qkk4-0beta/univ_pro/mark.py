# SPDX-FileCopyrightText: 2026 Oxicid
# SPDX-License-Identifier: GPL-3.0-or-later

if 'bpy' in locals():
    from .. import reload
    reload.reload(globals())

import bpy

from math import radians as to_rad
from math import degrees as to_deg

from .. import utypes
from .. import utils
# from ..preferences import prefs, univ_settings


class UNIV_OT_Constraint(bpy.types.Operator):
    bl_idname = 'uv.univ_constraint'
    bl_label = 'Constraint'
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = """
Set/clear vertical/horizontal constraints for unwrap. 

The flag markings for Constraints are stored as bits in the edge attribute.
The bits must be read from right to left in pairs. The left bit in each pair controls enable/disable, 
and the second bit in the pair controls vertical/horizontal orientation.

For example, 0x....101100 means:
    - the first linked loop has no marking (00)
    - the second linked loop has a horizontal constraint (11)
    - the third linked loop has a vertical constraint (10)
The maximum number of linked loops per edge is 16, but it is strongly recommended to avoid non-manifold geometry. 
This complexity was introduced for optimization purposes - this bit layout allows the necessary coordinates to be read very quickly.

NOTE: When applying destructive modifiers, collapse, split, and similar operations, constraint data may become invalid.
"""
    # noinspection PyTypeHints
    vertical: bpy.props.BoolProperty(name='Vertical', default=True, options={'HIDDEN'})


    def execute(self, context):
        if context.mode != 'EDIT_MESH':
            self.report({'WARNING'}, 'Object mode not implement')
            return {'CANCELLED'}

        umeshes = utypes.UMeshes(report=self.report)
        umeshes.update_tag = False
        out = 0
        wire_edge = 0
        incorrect_edge_tags = 0  # like 0b01


        vertical = 2  # (10)
        horizontal = 3  # (11)
        new_bits = vertical if self.vertical else horizontal


        selected, visible = umeshes.filtered_by_selected_and_visible_uv_edges()
        umeshes = selected if selected else visible
        if not selected:
            self.report({'WARNING'}, 'Not found selected edges')
            return {'CANCELLED'}


        for umesh in umeshes:
            constraints_attr = umesh.bm.edges.layers.int.get('univ_constraints')
            if not constraints_attr:
                constraints_attr = umesh.bm.edges.layers.int.new('univ_constraints')
                umesh.update_tag = True

            if umesh.elem_mode in ('FACE', 'ISLAND'):
                corners = utils.calc_selected_uv_edges_from_linked_selected_face(umesh)
            else:
                corners = utils.calc_selected_uv_edge(umesh)
            umesh.sequence = corners

            update_tag = False
            for crn in corners:
                e = crn.edge
                for i, crn_l in enumerate(e.link_loops):
                    if crn == crn_l:
                        if i >= 16:
                            out += 1
                            break

                        val: int = e[constraints_attr]
                        shift = i * 2  # Shift to right.

                        old_bits = (val >> shift) & 3  # Isolate two right bits.
                        if old_bits == new_bits:
                            break

                        val &= ~(3 << shift)  # Clear old bits.
                        val |= new_bits << shift  # Set new bits.

                        e[constraints_attr] = val
                        update_tag = True
                        break

            umesh.update_tag |= update_tag

        if not umeshes.update_tag:
            # Remove constraints
            for umesh in umeshes:
                constraints_attr = umesh.bm.edges.layers.int.get('univ_constraints')

                update_tag = False
                for crn in umesh.sequence:
                    e = crn.edge
                    for i, crn_l in enumerate(e.link_loops):
                        if crn == crn_l:
                            if i >= 16:
                                break

                            shift = i * 2

                            val: int = e[constraints_attr]
                            old_bits = (val >> shift) & 3  # Isolate bits.
                            if old_bits == new_bits:
                                val &= ~(3 << shift)  # clear old bits
                                e[constraints_attr] = val
                                update_tag = True
                            break

                # Sanitize
                loc_incorrect_edge_tags, loc_wire_edge = self.sanitize_constr(umesh, constraints_attr)
                incorrect_edge_tags += loc_incorrect_edge_tags
                wire_edge += loc_wire_edge

                umesh.update_tag |= update_tag


        if out:
            self.report({'WARNING'}, f"Found {out!r} edges that have more than 16 linked faces, for which flags cannot be fully written.")
        if wire_edge:
            self.report({'WARNING'}, f"Found {wire_edge!r} wire edges with no effect tags.")
        if incorrect_edge_tags:
            self.report({'WARNING'}, f"Found {incorrect_edge_tags!r} edges with incorrect tags with no effect tags "
                                  f"(possibly caused by geometry changes or manual modification of the attribute.)")

        return umeshes.update()

    @staticmethod
    def sanitize_constr(umesh, constraints_attr) -> tuple[int, int]:
        # Sanitize constraints
        # TODO: Add this and check shared vertices for Inspect

        incorrect_edge_tags = 0
        wire_edge = 0

        has_constr_edge = False
        for e in umesh.bm.edges:
            val: int = e[constraints_attr]
            if not val:
                continue

            if not hasattr(e, 'link_loops'):
                e[constraints_attr] = 0
                wire_edge += 1
                umesh.update_tag = True
                continue

            link_corners = e.link_loops
            all_possible_enabled_constr_bits = int('10' * len(link_corners), 2)

            if not (val & all_possible_enabled_constr_bits):
                e[constraints_attr] = 0
                incorrect_edge_tags += 1
                umesh.update_tag = True
            else:
                has_constr_edge = True
                break
        if not has_constr_edge:
            umesh.bm.edges.layers.int.remove(constraints_attr)
            umesh.update_tag = True

        return incorrect_edge_tags, wire_edge


# noinspection PyTypeHints
class UNIV_OT_ConstraintByAngle(bpy.types.Operator):
    bl_idname = 'uv.univ_constraint_by_angle'
    bl_label = 'Constraint by Angle'
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = """Set vertical/horizontal constraints by angle for unwrap"""

    angle: bpy.props.FloatProperty(name='Angle', subtype='ANGLE',
                                   default=to_rad(25), soft_min=to_rad(5), min=to_rad(2), max=to_rad(40))
    vertical: bpy.props.BoolProperty(name='Vertical', default=True, options={'HIDDEN'})


    def execute(self, context):
        from ..operators.transform import Align_by_Angle
        umeshes = utypes.UMeshes(report=self.report)
        umeshes.update_tag = False
        out = 0
        # incorrect_edge_tags = 0  # like 0b01


        vertical = 2  # (10)
        horizontal = 3  # (11)
        new_bits = vertical if self.vertical else horizontal
        is_x_axis = self.vertical
        has_segments = False

        if context.mode == 'EDIT_MESH':
            selected, visible = umeshes.filtered_by_selected_and_visible_uv_edges()
            umeshes = selected if selected else visible

            if not umeshes:
                return umeshes.update()


            for umesh in umeshes:
                for segments in Align_by_Angle.get_segments_by_angle(umesh, self.angle, is_x_axis, bool(selected)):
                    has_segments = True

                    constraints_attr = umesh.bm.edges.layers.int.get('univ_constraints')
                    if not constraints_attr:
                        constraints_attr = umesh.bm.edges.layers.int.new('univ_constraints')
                        umesh.update_tag = True

                    def get_corners(segments_):
                        for seg in segments_:
                            if seg.is_end_lock:
                                seg.lengths_seq.pop()
                            if not seg.lengths_seq:
                                continue


                            if seg.is_start_lock:
                                del seg.lengths_seq[0]
                            if not seg.lengths_seq:
                                continue


                            for adv_crn in seg:
                                if adv_crn.invert:
                                    yield adv_crn.crn.link_loop_prev
                                else:
                                    yield adv_crn.crn

                                if adv_crn.is_pair:
                                    yield adv_crn.crn.link_loop_radial_prev

                    update_tag = False
                    for crn in get_corners(segments):
                        e = crn.edge
                        for i, crn_l in enumerate(e.link_loops):
                            if crn == crn_l:
                                if i >= 16:
                                    out += 1
                                    break

                                val: int = e[constraints_attr]
                                shift = i * 2

                                old_bits = (val >> shift) & 3
                                if old_bits == new_bits:
                                    break

                                val &= ~(3 << shift)  # clear old bits
                                val |= new_bits << shift

                                e[constraints_attr] = val
                                update_tag = True
                                break

                    umesh.update_tag |= update_tag

        else:
            umeshes.free()
            self.report({'WARNING'}, 'Object mode not implement')
            return {'CANCELLED'}
            # for umesh in self.umeshes:
            #     umesh.sequence = [crn for f in umesh.bm.faces for crn in f.loops]
            #     umesh.update_tag = bool(umesh.sequence)

        if not has_segments:
            self.report({'INFO'}, f'Not found edges with {to_deg(self.angle):.1f} angle')
            return {'FINISHED'}
        elif not umeshes.update_tag:
            self.report({'INFO'}, 'All edges marked')

        if out:
            self.report({'WARNING'}, f"Found {out!r} edges that have more than 16 linked faces, for which flags cannot be fully written.")
        # if incorrect_edge_tags:
        #     self.report({'WARNING'}, f"Found {incorrect_edge_tags!r} edges with incorrect tags with no effect tags "
        #                           f"(possibly caused by geometry changes or manual modification of the attribute.)")
        umeshes.silent_update()
        return {'FINISHED'}