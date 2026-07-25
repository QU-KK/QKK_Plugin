import bpy


class Lattice:
    @staticmethod
    def bounds(local_coords, orientation=None):
        if orientation:

            def apply_orientation(p):
                return orientation @ Vector(p[:])

            coords = [apply_orientation(p).to_tuple() for p in local_coords]
        else:
            coords = [p[:] for p in local_coords]
        rotated = zip(*coords[::-1])
        push_axis = []
        for axis, _list in zip("xyz", rotated):

            def info():
                return None

            info.max = max(_list)
            info.min = min(_list)
            info.distance = info.max - info.min
            push_axis.append(info)
        originals = dict(zip(["x", "y", "z"], push_axis))
        o_details = collections.namedtuple("object_details", "x y z")
        return o_details(**originals)

    @staticmethod
    def create_lattice(context):
        lattice_data = bpy.data.lattices.new("Lattice")
        lattice_obj = bpy.data.objects.new("Lattice", lattice_data)
        for col in context.object.users_collection:
            col.objects.link(lattice_obj)
        return lattice_obj

    @staticmethod
    def set_selection(context, lattice):
        bpy.ops.object.mode_set(mode="OBJECT")
        bpy.ops.object.select_all(action="DESELECT")
        lattice.select_set(True)
        context.view_layer.objects.active = lattice

    @staticmethod
    def get_coords_from_verts(objects):
        worldspace_verts = []
        vert_mapping = {}

        for obj in objects:
            bpy.ops.object.editmode_toggle()
            vert_indices = []
            vertices = obj.data.vertices
            for vert in vertices:
                if vert.select == True:
                    index = vert.index
                    vert_indices.append(index)
                    worldspace_verts.append(obj.matrix_world @ vert.co)
            vert_mapping[obj.name] = vert_indices
        return worldspace_verts, vert_mapping

    @staticmethod
    def get_coords_from_objects(objects):
        bbox_world_coords = []
        for obj in objects:
            coords = obj.bound_box[:]
            coords = [(obj.matrix_world @ Vector(p[:])).to_tuple() for p in coords]
            bbox_world_coords.extend(coords)
        return bbox_world_coords

    @staticmethod
    def get_coords_from_object(obj):
        bbox_local_coords = []
        coords = obj.bound_box[:]
        coords = [(obj.matrix_world @ Vector(p[:])).to_tuple() for p in coords]
        bbox_local_coords.extend(coords)
        return bbox_local_coords

    @staticmethod
    def update_lattice(context, lattice, coords, matrix, orientation):
        prefs = preferences()
        if orientation == "GLOBAL":
            rotation = Matrix.Identity(4)
            bbox = Lattice.bounds(coords)

        elif orientation == "LOCAL":
            rotation = matrix.to_quaternion().to_matrix().to_4x4()
            bbox = Lattice.bounds(coords, rotation.inverted())

        bound_min = Vector((bbox.x.min, bbox.y.min, bbox.z.min))
        bound_max = Vector((bbox.x.max, bbox.y.max, bbox.z.max))
        offset = (bound_min + bound_max) * 0.5

        # finally gather position/rotation/scaling for the lattice
        location = rotation @ offset
        scale = Vector(
            (
                abs(bound_max.x - bound_min.x),
                abs(bound_max.y - bound_min.y),
                abs(bound_max.z - bound_min.z),
            )
        )

        lattice.data.points_u = prefs.lattice.points_u
        lattice.data.points_v = prefs.lattice.points_v
        lattice.data.points_w = prefs.lattice.points_w

        lattice.data.interpolation_type_u = prefs.lattice.interpolation
        lattice.data.interpolation_type_v = prefs.lattice.interpolation
        lattice.data.interpolation_type_w = prefs.lattice.interpolation

        lattice.location = location
        lattice.rotation_euler = rotation.to_euler()
        lattice.scale = Vector(
            (
                scale.x * prefs.lattice.scale,
                scale.y * prefs.lattice.scale,
                scale.z * prefs.lattice.scale,
            )
        )

    @staticmethod
    def add_lattice_modifiers(objects, lattice, group_mapping):
        for obj in objects:
            lattice_mod = obj.modifiers.new("Lattice", "LATTICE")
            lattice_mod.object = lattice
            if group_mapping != None:
                vertex_group_name = group_mapping[obj.name]
                lattice_mod.name = vertex_group_name
                lattice_mod.vertex_group = vertex_group_name

            obj.update_tag()

    @staticmethod
    def cleanup(objects):
        for obj in objects:
            used_vertex_groups = set()
            obsolete_modifiers = []
            for modifier in obj.modifiers:
                if modifier.type == "LATTICE" and "Lattice" in modifier.name:
                    if modifier.vertex_group != "":
                        used_vertex_groups.add(modifier.vertex_group)
                    elif modifier.object == None or (modifier.vertex_group == "" and modifier.vertex_group not in obj.vertex_groups):
                        # a,b,c = modifier.object == None, modifier.vertex_group == '', modifier.vertex_group not in obj.vertex_groups
                        # print(f'obj:{a} - vertexgrp empty: {b} - not in groups: {c}' )
                        obsolete_modifiers.append(modifier)
            obsolete_groups = []
            for grp in obj.vertex_groups:
                if "SimpleLattice" in grp.name:
                    if grp.name not in used_vertex_groups:
                        obsolete_groups.append(grp)

            for group in obsolete_groups:
                print(f"Removed vertex_group: {group.name}")
                obj.vertex_groups.remove(group)
            for modifier in obsolete_modifiers:
                print(f"Removed modifier: {modifier.name}")
                obj.modifiers.remove(modifier)

    @staticmethod
    def set_vertex_groups(objects, vert_mapping):
        group_mapping = {}
        for obj in objects:
            mode = obj.mode
            if obj.mode == "EDIT":
                bpy.ops.object.editmode_toggle()
            group = obj.vertex_groups.new(name=f"Lattice")
            group.add(vert_mapping[obj.name], 1.0, "REPLACE")
            group_mapping[obj.name] = group.name
            if mode != obj.mode:
                bpy.ops.object.editmode_toggle()
        return group_mapping

    @staticmethod
    def for_edit_mode(context):
        try:
            bpy.ops.transform.create_orientation(name="Lattice_Orientation", use=False, overwrite=True)
        except:
            bpy.ops.object.mode_set(mode="OBJECT")
            bpy.ops.transform.create_orientation(name="Lattice_Orientation", use=False, overwrite=True)

        active_object = context.view_layer.objects.active
        if active_object.mode == "EDIT":
            objects_originals = context.selected_objects

            bpy.ops.object.mode_set(mode="OBJECT")
            bpy.ops.object.empty_add()

            objects_created = context.selected_objects

            # removing objects with its data
            for obj in objects_created:
                purge_data = [o.data for o in context.selected_objects if o.data]
                bpy.data.batch_remove(context.selected_objects)
                bpy.data.batch_remove([o for o in purge_data if not o.users])

            # selecting original objects with active
            for obj in objects_originals:
                obj.select_set(True)
                context.view_layer.objects.active = active_object

            bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.ed.undo_push()

    @staticmethod
    def set_active(context, object):
        context.view_layer.objects.active = object

    @staticmethod
    def kill_lattice_modifer(context, modifier, target):
        vertex_group = ""

        if modifier.type != "LATTICE" or modifier.object != target:
            return vertex_group

        if context.active_object != modifier.id_data:
            Lattice.set_active(context, modifier.id_data)

        if modifier.vertex_group != None:
            vertex_group = modifier.vertex_group

        if modifier.show_viewport:
            if modifier.id_data.mode != "OBJECT":
                bpy.ops.object.editmode_toggle()

            bpy.ops.object.modifier_remove(modifier=modifier.name)

        # else:
        # bpy.ops.object.modifier_remove(
        # modifier=modifier.name)

        return vertex_group

    @staticmethod
    def kill_vertex_groups(obj, vertex_groups):
        if len(vertex_groups) == 0:
            return

        modifiers = filter(
            lambda modifier: hasattr(modifier, "vertex_group") and modifier.vertex_group,
            obj.modifiers,
        )
        used_vertex_groups = set(map(lambda modifier: modifier.vertex_group, modifiers))

        obsolete = filter(lambda group: group not in used_vertex_groups, vertex_groups)

        for group in obsolete:
            print(f"removed vertex_group: {group}")
            vg = obj.vertex_groups.get(group)
            obj.vertex_groups.remove(vg)
