# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####


import bpy
import bmesh
from math import pi, radians
from mathutils import Vector

from ZenUV.utils import get_uv_islands as island_util
from ZenUV.utils.generic import verify_uv_layer
from ZenUV.utils.bounding_box import BoundingBox2d
from ZenUV.ui.pie import ZsPieFactory
from ZenUV.ops.transform_sys.transform_utils.tr_utils import ActiveUvImage
from ZenUV.ops.transform_sys.transform_utils.transform_loops import TransformLoops
from ZenUV.utils.generic import resort_by_type_mesh_in_edit_mode_and_sel
from ZenUV.utils.get_uv_islands import get_islands, get_island
from collections import defaultdict
from pprint import pprint


class OverlapIslandsFactoryMulti:

    # @classmethod
    # def project_polygon(cls, polygon, axis):
    #     min_proj = float('inf')
    #     max_proj = float('-inf')
    #     for point in polygon:
    #         proj = point.dot(axis)
    #         min_proj = min(min_proj, proj)
    #         max_proj = max(max_proj, proj)
    #     return min_proj, max_proj

    # @classmethod
    # def polygons_intersect(cls, poly1, poly2):
    #     for polygon in (poly1, poly2):
    #         for i1, p1 in enumerate(polygon):
    #             i2 = (i1 + 1) % len(polygon)
    #             p2 = polygon[i2]
    #             edge = p2 - p1
    #             axis = Vector((-edge.y, edge.x))  # Perpendicular axis
    #             min1, max1 = cls.project_polygon(poly1, axis)
    #             min2, max2 = cls.project_polygon(poly2, axis)
    #             if max1 < min2 or max2 < min1:
    #                 return False
    #     return True

    # @classmethod
    # def do_islands_overlap(cls, obj1, polys1, obj2, polys2):

    #     for poly1 in polys1:
    #         for poly2 in polys2:
    #             if cls.polygons_intersect(poly1, poly2):
    #                 return True
    #     return False

    @classmethod
    def project_polygon(cls, polygon, axis):
        # Normalize the axis to avoid scaling issues
        axis = axis.normalized()
        min_proj = float('inf')
        max_proj = float('-inf')
        for point in polygon:
            proj = point.dot(axis)
            min_proj = min(min_proj, proj)
            max_proj = max(max_proj, proj)
        return min_proj, max_proj

    @classmethod
    def polygons_intersect(cls, poly1, poly2):
        # Check if polygons are degenerate (e.g., all points on a line)
        if len(poly1) < 3 or len(poly2) < 3:
            return False

        # Iterate over edges in both polygons
        for polygon in (poly1, poly2):
            for i1, p1 in enumerate(polygon):
                i2 = (i1 + 1) % len(polygon)
                p2 = polygon[i2]
                edge = p2 - p1

                # Handle degenerate edges (very small length)
                if edge.length < 1e-6:
                    continue

                # Use the perpendicular axis (SAT) and normalize it
                axis = Vector((-edge.y, edge.x)).normalized()
                min1, max1 = cls.project_polygon(poly1, axis)
                min2, max2 = cls.project_polygon(poly2, axis)

                # Add a small tolerance to account for floating-point precision
                tolerance = 1e-6
                if max1 < min2 - tolerance or max2 < min1 - tolerance:
                    return False

        # If no separating axis found, polygons intersect
        return True

    @classmethod
    def do_islands_overlap(cls, obj1, polys1, obj2, polys2):
        for poly1 in polys1:
            for poly2 in polys2:
                if cls.polygons_intersect(poly1, poly2):
                    return True
        return False

    @classmethod
    def find_overlapping_groups(cls, context, objects):
        overlaps = defaultdict(set)
        islands_info = []
        uv_polygons_info = []

        # Collect UV islands from all objects
        for obj_index, obj in enumerate(objects):
            print(f'Object {obj_index} processing')

            bm = bmesh.from_edit_mesh(obj.data)
            uv_layer = bm.loops.layers.uv.active

            if not uv_layer:
                print(f"Object '{obj.name}' has no UV layers. Skipping.")
                continue

            islands = get_islands(context, bm)
            print(f'islands total: {len(islands)}')

            for island in islands:
                islands_info.append((obj_index, [f.index for f in island]))
                uv_polygons_info.append((obj_index, [[loop[uv_layer].uv for loop in f.loops] for f in island]))
        print('\n---------------------------------------------------------------------')
        print(f'islands info -> {islands_info}')
        cls.show_uv_info(uv_polygons_info)

        # Check for overlaps between all islands
        for i, (obj_idx1, uv_island1) in enumerate(uv_polygons_info):
            for j, (obj_idx2, uv_island2) in enumerate(uv_polygons_info):
                if i < j:
                    if cls.do_islands_overlap(objects[obj_idx1], uv_island1, objects[obj_idx2], uv_island2):
                        overlaps[i].add(j)
                        overlaps[j].add(i)

        print(f'{overlaps = }')

        visited = set()
        groups = []

        def dfs(island_index, current_group):
            stack = [island_index]
            while stack:
                idx = stack.pop()
                if idx not in visited:
                    visited.add(idx)
                    current_group.add(idx)
                    stack.extend(overlaps[idx] - visited)

        # Group overlapping islands
        for island_index in range(len(islands_info)):
            if island_index not in visited:
                current_group = set()
                dfs(island_index, current_group)
                groups.append(current_group)

        return groups, islands_info

    @classmethod
    def show_uv_info(cls, data):
        for i, (obj_idx, uv_face) in enumerate(data):
            print(f'island {i}, object {obj_idx} faces {len(uv_face)}')


class OverlapIslandsFactory:

    @classmethod
    def example_usage(self, context):
        """ Only example !!! """
        import bmesh
        from ZenUV.utils.generic import resort_by_type_mesh_in_edit_mode_and_sel
        from ZenUV.utils.get_uv_islands import OverlapIslandsFactory

        objs = resort_by_type_mesh_in_edit_mode_and_sel(context)
        if not objs:
            self.report({'WARNING'}, "Zen UV: There are no selected objects.")
            return {"CANCELLED"}

        for obj in objs:
            bm = bmesh.from_edit_mesh(obj.data)
            uv_layer = verify_uv_layer(bm)

            islands = get_islands(context, bm)
            print(f'{len(islands)=}')
            print(islands)

            # res = IslandsFactory.is_islands_overlapped(islands[0], islands[1], uv_layer)
            res = OverlapIslandsFactory.get_overlapped_islands_by_groups(islands, uv_layer)
            print(res)

            for i_set in res:
                if len(i_set) == 1:
                    continue
                for i in i_set:
                    for f in islands[i]:
                        f.select = True
            bmesh.update_edit_mesh(obj.data)

    @classmethod
    def is_islands_overlapped(cls, island1: list, island2: list, uv_layer: bmesh.types.BMLayerItem):

        from mathutils import Vector

        def get_uv_polygons(faces, uv_layer):
            polygons = []
            for face in faces:
                polygon = [loop[uv_layer].uv for loop in face.loops]
                polygons.append(polygon)
            return polygons

        def project_polygon(polygon, axis):
            min_proj = float('inf')
            max_proj = float('-inf')
            for point in polygon:
                proj = point.dot(axis)
                if proj < min_proj:
                    min_proj = proj
                if proj > max_proj:
                    max_proj = proj
            return min_proj, max_proj

        def polygons_intersect(poly1, poly2):
            for polygon in (poly1, poly2):
                for i1, p1 in enumerate(polygon):
                    i2 = (i1 + 1) % len(polygon)
                    p2 = polygon[i2]
                    edge = p2 - p1
                    axis = Vector((-edge.y, edge.x))  # Perpendicular axis
                    min1, max1 = project_polygon(poly1, axis)
                    min2, max2 = project_polygon(poly2, axis)
                    if max1 < min2 or max2 < min1:
                        return False
            return True

        polys1 = get_uv_polygons(island1, uv_layer)
        polys2 = get_uv_polygons(island2, uv_layer)

        for poly1 in polys1:
            for poly2 in polys2:
                if polygons_intersect(poly1, poly2):
                    return True
        return False

    @classmethod
    def get_overlapped_islands_by_groups(cls, islands, uv_layer):
        from collections import defaultdict

        overlaps = defaultdict(set)

        for i, island1 in enumerate(islands):
            for j, island2 in enumerate(islands):
                if i < j:
                    if cls.is_islands_overlapped(island1, island2, uv_layer):
                        overlaps[i].add(j)
                        overlaps[j].add(i)

        visited = set()
        groups = []

        def dfs(island_index, current_group):
            stack = [island_index]
            while stack:
                idx = stack.pop()
                if idx not in visited:
                    visited.add(idx)
                    current_group.add(idx)
                    stack.extend(overlaps[idx] - visited)

        for island_index in range(len(islands)):
            if island_index not in visited:
                current_group = set()
                dfs(island_index, current_group)
                groups.append(current_group)

        return groups

    @classmethod
    def bbox_ovelaps_detection(cls, context, objs: list, unstack_direction: Vector = Vector((1.0, 0.0))):
        """
        Finds overlapping islands and shifts them by the specified amount "unstack_direction"
        Detection method - Bounding Box
        """
        from collections import defaultdict
        from ZenUV.utils.bounding_box import BoundingBox2d

        scope = defaultdict(list)

        for obj in objs:
            bm = bmesh.from_edit_mesh(obj.data)
            uv = verify_uv_layer(bm)
            bm.faces.ensure_lookup_table()

            for island in get_island(context, bm, uv):
                p_i_center = tuple(round(v, 5) for v in BoundingBox2d(islands=[island], uv_layer=uv).center)
                scope[p_i_center].append((obj, [f.index for f in island]))

        for obj_islands_list in scope.values():
            if len(obj_islands_list) == 1:
                obj_islands_list.clear()
                continue
            if len(obj_islands_list) > 1:
                obj_islands_list.pop()

        for obj in objs:
            bm = bmesh.from_edit_mesh(obj.data)
            uv = bm.loops.layers.uv.verify()
            bm.faces.ensure_lookup_table()

            for obj_islands_list in scope.values():
                for obj_in_scope, indices in obj_islands_list:
                    if obj_in_scope == obj:
                        for idx in indices:
                            for loop in bm.faces[idx].loops:
                                loop[uv].uv += unstack_direction

            bmesh.update_edit_mesh(obj.data)


class ZUV_OP_TestOperator(bpy.types.Operator):
    bl_idname = 'zenuv_test.test_operator'
    bl_label = 'Test Operator'
    bl_description = 'Isolate Islands (Toggle) by selected edge/face of the Islands'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        """ Validate context """
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH'

    method: bpy.props.EnumProperty(
        name='Method',
        description='Detection Method',
        items=(
            ('BBOX', 'BBox', 'BBox center detection'),
            ('OVERLAP_FACES', 'Overlapping Faces', 'Detection real faces overlaps'),
            ('MULT_OBJS', 'Multiple Objects', 'Use Multiple objects for detection')
        ),
        default='MULT_OBJS'
    )

    unstack_direction: bpy.props.FloatVectorProperty(
        name="Direction",
        size=2,
        max=1.0,
        min=-1.0,
        default=(1.0, 0.0),
        subtype='XYZ'
    )

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.prop(self, 'method')
        layout.prop(self, 'unstack_direction')

    def execute(self, context):
        from ZenUV.utils.get_uv_islands import OverlapIslandsFactory, OverlapIslandsFactoryMulti
        from ZenUV.utils.generic import bpy_deselect_by_context
        objs = list(resort_by_type_mesh_in_edit_mode_and_sel(context))
        if not objs:
            self.report({'WARNING'}, "Zen UV: There are no selected objects.")
            return {"CANCELLED"}
        print(f'\n{self.method} ------------------------------------------')

        bpy_deselect_by_context(context)

        if self.method == 'BBOX':
            OverlapIslandsFactory.bbox_ovelaps_detection(context, objs, self.unstack_direction)

        elif self.method == 'OVERLAP_FACES':
            for obj in objs:
                bm = bmesh.from_edit_mesh(obj.data)
                uv_layer = verify_uv_layer(bm)

                islands = island_util.get_islands(context, bm)
                print(f'{len(islands) = }')

                # res = IslandsFactory.is_islands_overlapped(islands[0], islands[1], uv_layer)
                overlap_groups = OverlapIslandsFactory.get_overlapped_islands_by_groups(islands, uv_layer)
                print(overlap_groups)

                for i_set in overlap_groups:
                    if len(i_set) == 1:
                        continue
                    for i in list(i_set)[1:]:
                        for f in islands[i]:
                            f.select = True
                            for loop in f.loops:
                                loop[uv_layer].uv += self.unstack_direction

                bmesh.update_edit_mesh(obj.data)

        elif self.method == 'MULT_OBJS':
            groups, islands_info = OverlapIslandsFactoryMulti.find_overlapping_groups(context, objs)

            print(f'{groups = }', '\n')
            print(f'{islands_info = }', '\n')

            # Dictionary to track the selection per object
            object_to_faces = defaultdict(set)

            # Collect face indices for each object based on overlapping groups
            for group in groups:
                if len(group) == 1:
                    continue
                for island_index in list(group):
                    obj_index, island = islands_info[island_index]
                    object_to_faces[objs[obj_index]].update(island)

            # Apply selections to each object
            for obj, face_indices in object_to_faces.items():
                bm = bmesh.from_edit_mesh(obj.data)
                bm.faces.ensure_lookup_table()

                # Select the relevant faces
                for face_idx in face_indices:
                    bm.faces[face_idx].select = True

                bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)

        return {'FINISHED'}