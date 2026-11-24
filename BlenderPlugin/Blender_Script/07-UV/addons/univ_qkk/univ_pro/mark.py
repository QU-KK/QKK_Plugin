# SPDX-FileCopyrightText: 2026 Oxicid
# SPDX-License-Identifier: GPL-3.0-or-later


import bpy
import typing

from math import radians as to_rad
from math import degrees as to_deg

from bmesh.types import BMLoop

from .. import utypes
from .. import utils

# from ..preferences import prefs, univ_settings

DIAGONAL_CONSTR = 1  # (01)
VERTICAL_CONSTR = 2  # (10)
HORIZONTAL_CONSTR = 3  # (11)


# For example, 0x....101100 means:
#     - the first linked loop has no marking (00)
#     - the second linked loop has a horizontal constraint (11)
#     - the third linked loop has a vertical constraint (10)
# The maximum number of linked loops per edge is 16, but it is strongly recommended to avoid non-manifold geometry.
# This complexity was introduced for optimization purposes - this bit layout allows the necessary coordinates to be read very quickly.
#
# The flag markings for Constraints are stored as bits in the edge attribute.
# The bits must be read from right to left in pairs. The left bit in each pair controls enable/disable,
# and the second bit in the pair controls vertical/horizontal orientation.


class UNIV_OT_ClearConstraints(bpy.types.Operator):
    bl_idname = "uv.univ_clear_constraints"
    bl_label = "Clear Constraints"
    bl_options = {"REGISTER", "UNDO"}
    bl_description = "Clear Constraints"

    # noinspection PyTypeHints
    constraints_type: bpy.props.EnumProperty(
        name="Constraints Type", default="VERTICAL", options={"HIDDEN"}, items=utils.ENUM("VERTICAL", "HORIZONTAL", "DIAGONAL")
    )

    def execute(self, context):
        umeshes = utypes.UMeshes(report=self.report)
        umeshes.update_tag = False

        out = 0
        wire_edge_count = 0
        extra_edge_tags_count = (
            0  # like 0b01, TODO: remove in the future, when add diagonal
        )

        selected, visible = umeshes.filtered_by_selected_and_visible_uv_edges()
        umeshes = selected if selected else visible
        if not umeshes:
            return umeshes.update()

        for umesh in umeshes:
            constraints_attr = umesh.bm.edges.layers.int.get("univ_constraints")
            if not constraints_attr:
                continue

            if selected:
                if umesh.elem_mode in ("FACE", "ISLAND"):
                    corners = utils.calc_selected_uv_edges_from_linked_selected_face(
                        umesh
                    )
                else:
                    corners = utils.calc_selected_uv_edge(umesh)
            else:
                corners = utils.calc_visible_uv_corners(umesh)

            extra_edge_tags_count, wire_edge_count = self.clear_constraints(
                umesh,
                corners,
                self.constraints_type,
                extra_edge_tags_count,
                wire_edge_count,
            )

        self.print_info(self.report, out, wire_edge_count, extra_edge_tags_count)
        return umeshes.update()

    @staticmethod
    def remove_constraints_in_object_mode(report) -> set[str]:
        attr_counter = 0
        for obj in utils.calc_any_unique_obj():
            for attr in reversed(obj.data.attributes):
                if attr.name == "univ_constraints":
                    obj.data.attributes.remove(attr)
                    obj.update_tag()
                    attr_counter += 1
        if attr_counter:
            report({"INFO"}, f"Cleaned constraints from {attr_counter!r} objects.")
            return {"FINISHED"}
        else:
            report({"INFO"}, "All constraints from all selected objects was cleaned.")
            return {"CANCELLED"}

    @classmethod
    def clear_constraints(
        cls,
        umesh,
        corners: list[BMLoop],
        constraints_type: str,
        extra_tags: int,
        wire_edge: int,
    ):
        constraints_attr = umesh.bm.edges.layers.int.get("univ_constraints")
        if constraints_type == "VERTICAL":
            new_bits = VERTICAL_CONSTR
        elif constraints_type == "HORIZONTAL":
            new_bits = HORIZONTAL_CONSTR
        else:
            new_bits = DIAGONAL_CONSTR

        update_tag = False
        for crn in corners:
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
        loc_extra_tags, loc_wire_edge = cls.sanitize_constr(
            umesh, constraints_attr
        )
        extra_tags += loc_extra_tags
        wire_edge += loc_wire_edge

        umesh.update_tag |= update_tag
        return extra_tags, wire_edge

    @staticmethod
    def sanitize_constr(umesh, constraints_attr) -> tuple[int, int]:
        # Sanitize constraints
        # TODO: Add this and check shared vertices for Inspect

        extra_edge_tags = 0
        wire_edge = 0

        has_constr_edge = False  # Tag for remove attr, if constraints missed.
        for e in umesh.bm.edges:
            val: int = e[constraints_attr]
            if not val:
                continue

            if not hasattr(e, "link_loops"):
                e[constraints_attr] = 0
                wire_edge += 1
                umesh.update_tag = True
                continue

            link_corners = e.link_loops
            extra_bits = val >> len(link_corners) * 2

            if extra_bits:
                extra_edge_tags += 1
                new_bits = val & int("1" * (len(link_corners) * 2))  # Clear extra bits.
                if not new_bits:
                    e[constraints_attr] = 0
                    umesh.update_tag = True
                else:
                    e[constraints_attr] = new_bits
                    umesh.update_tag = True
                    has_constr_edge = True
            else:
                has_constr_edge = True
                break

        if not has_constr_edge:
            umesh.bm.edges.layers.int.remove(constraints_attr)
            umesh.update_tag = True

        return extra_edge_tags, wire_edge

    @staticmethod
    def print_info(report, out, wire_edge_count, extra_edge_tags_count):
        if out:
            report(
                {"WARNING"},
                f"Found {out!r} edges that have more than 16 linked faces, for which flags cannot be fully written.",
            )
        if wire_edge_count:
            report(
                {"WARNING"},
                f"Found {wire_edge_count!r} wire edges with no effect tags.",
            )
        if extra_edge_tags_count:
            report(
                {"WARNING"},
                f"Found {extra_edge_tags_count!r} edges with no effect tags "
                f"(possibly caused by geometry changes or manual modification of the attribute.)",
            )


class UNIV_OT_MarkConstraints(UNIV_OT_ClearConstraints):
    bl_idname = "uv.univ_mark_constraints"
    bl_label = "Constraints"
    bl_description = """
Set/clear vertical/horizontal/diagonal constraints for unwrap. 

Modifier keys for constraints mode:
    Default - Toggle
    Shift - Set Constraints
    Ctrl | Alt - Clear Constraints
NOTE: When applying destructive modifiers, collapse, split, and similar operations, constraint data may become invalid.
"""

    # noinspection PyTypeHints
    constraints_type: bpy.props.EnumProperty(
        name="Constraints Type", default="VERTICAL", options={"HIDDEN"}, items=utils.ENUM("VERTICAL", "HORIZONTAL", "DIAGONAL")
    )
    # noinspection PyTypeHints
    mode: bpy.props.EnumProperty(
        name="Mode", items=utils.ENUM("TOGGLE", "SET", "CLEAR"), default="TOGGLE"
    )

    def invoke(self, context, event):
        if event.value == "PRESS":
            return self.execute(context)

        if event.shift:
            self.mode = "SET"
        elif event.ctrl or event.alt:
            self.mode = "CLEAR"
        else:
            self.mode = "TOGGLE"

        return self.execute(context)

    def execute(self, context):
        if context.mode != "EDIT_MESH" or self.mode == "CLEAR":
            return super().execute(context)

        umeshes = utypes.UMeshes(report=self.report)
        umeshes.update_tag = False
        out = 0
        wire_edge_count = 0
        incorrect_edge_tags_count = (
            0  # like 0b01, TODO: remove in the future, when add diagonal
        )

        umeshes, _ = umeshes.filtered_by_selected_and_visible_uv_edges()
        if not umeshes:
            self.report({"WARNING"}, "Not found selected edges")
            return {"CANCELLED"}

        for umesh in umeshes:
            if umesh.elem_mode in ("FACE", "ISLAND"):
                corners = utils.calc_selected_uv_edges_from_linked_selected_face(umesh)
            else:
                corners = utils.calc_selected_uv_edge(umesh)
            umesh.sequence = corners

            out += self.set_constraints(umesh, corners, self.constraints_type)

        if not umeshes.update_tag and (self.mode == "TOGGLE"):
            # Remove constraints
            for umesh in umeshes:
                incorrect_edge_tags_count, wire_edge_count = self.clear_constraints(
                    umesh,
                    umesh.sequence,
                    self.constraints_type,
                    incorrect_edge_tags_count,
                    wire_edge_count,
                )

        self.print_info(self.report, out, wire_edge_count, incorrect_edge_tags_count)
        if self.mode == "TOGGLE":
            return umeshes.update()
        else:
            return umeshes.update(info="No new edge was found for marking.")

    @staticmethod
    def set_constraints(umesh: utypes.UMesh, corners: typing.Iterable[BMLoop], constraints_type: str) -> int:
        out = 0
        if constraints_type == "VERTICAL":
            new_bits = VERTICAL_CONSTR
        elif constraints_type == "HORIZONTAL":
            new_bits = HORIZONTAL_CONSTR
        else:
            new_bits = DIAGONAL_CONSTR

        constraints_attr = umesh.bm.edges.layers.int.get("univ_constraints")
        if not constraints_attr:
            constraints_attr = umesh.bm.edges.layers.int.new("univ_constraints")
            umesh.update_tag = True

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
        return out


# noinspection PyTypeHints
class UNIV_OT_MarkConstraintsByAngle(bpy.types.Operator):
    bl_idname = "uv.univ_mark_constraints_by_angle"
    bl_label = "Constraints by Angle"
    bl_options = {"REGISTER", "UNDO"}
    bl_description = """Set vertical/horizontal constraints by angle for unwrap"""

    angle: bpy.props.FloatProperty(
        name="Angle",
        subtype="ANGLE",
        default=to_rad(25),
        soft_min=to_rad(5),
        min=to_rad(2),
        max=to_rad(40),
    )
    constraints_type: bpy.props.EnumProperty(
        name="Vertical", default="VERTICAL", options={"HIDDEN"}, items=utils.ENUM("VERTICAL", "HORIZONTAL")
    )

    def execute(self, context):
        from ..operators.transform import Align_by_Angle

        umeshes = utypes.UMeshes(report=self.report)
        umeshes.update_tag = False
        out = 0

        has_segments = False
        is_vertical = self.constraints_type == "VERTICAL"
        if context.mode == "EDIT_MESH":
            selected, visible = umeshes.filtered_by_selected_and_visible_uv_edges()
            umeshes = selected if selected else visible
            if not umeshes:
                return umeshes.update()

            for umesh in umeshes:
                for segments in Align_by_Angle.get_segments_by_angle(
                    umesh,
                    self.angle,
                    is_vertical,
                    bool(selected),
                    with_seams=False,
                ):
                    has_segments = True
                    corners = self.get_corners_from_segment_with_pair_with_length_check(segments)
                    out += UNIV_OT_MarkConstraints.set_constraints(umesh, corners, self.constraints_type)

        else:
            umeshes.free()
            self.report({"WARNING"}, "Object mode not implement")
            return {"CANCELLED"}

        if not has_segments:
            self.report(
                {"INFO"}, f"Not found edges with {to_deg(self.angle):.1f} angle"
            )
            return {"FINISHED"}
        elif not umeshes.update_tag:
            self.report({"INFO"}, "All edges marked")

        if out:
            self.report(
                {"WARNING"},
                f"Found {out!r} edges that have more than 16 linked faces, for which flags cannot be fully written.",
            )
        # if incorrect_edge_tags:
        #     self.report({'WARNING'}, f"Found {incorrect_edge_tags!r} edges with incorrect tags with no effect tags "
        #                           f"(possibly caused by geometry changes or manual modification of the attribute.)")
        umeshes.silent_update()
        return {"FINISHED"}

    @staticmethod
    def get_corners_from_segment_with_pair_with_length_check(segments):
        for seg in segments:
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
