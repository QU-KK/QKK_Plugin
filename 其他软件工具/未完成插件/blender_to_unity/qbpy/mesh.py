import bpy
import bmesh


class Mesh:
    @staticmethod
    def add_vertex_group(context, name: str):
        vgroup = context.object.vertex_groups.new(name=name)

    @staticmethod
    def update_vertex_group(context, name):
        if context.object.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        vgroup = context.object.vertex_groups.get(name)
        if not vgroup:
            vgroup = context.object.vertex_groups.new(name=name)
        verts = [v.index for v in context.object.data.vertices if v.select]
        vgroup.add(verts, 1.0, "REPLACE")
        bpy.ops.object.mode_set(mode="EDIT")

        return vgroup

    @staticmethod
    def create_vgroup(object: bpy.types.Object, modifier: bpy.types.Modifier):
        cloth_vgroup = object.vertex_groups.get("Cloth")
        if not cloth_vgroup:
            cloth_vgroup = object.vertex_groups.new(name="Cloth")

        bm = bmesh.new()
        bm.from_mesh(object.data)

        verts = [v.index for v in bm.verts if v.is_boundary]
        cloth_vgroup.add(index=verts, weight=1.0, type="REPLACE")
        verts1 = [e.verts[0].index for e in bm.edges if e.seam]
        verts2 = [e.verts[0].index for e in bm.edges if e.seam]
        verts = verts1 + verts2
        cloth_vgroup.add(index=verts, weight=1.0, type="REPLACE")

        modifier.settings.vertex_group_mass = cloth_vgroup.name
        bm.free()

    @staticmethod
    def symmetrize(context, direction: str):
        """Symmetrize the object.

        direction (enum in ['POSITIVE_X', 'POSITIVE_Y', 'POSITIVE_Z', 'NEGATIVE_X', 'NEGATIVE_Y', 'NEGATIVE_Z']) - The direction to symmetrize the object in.
        """
        if context.mode == "OBJECT":
            for obj in context.selected_objects:
                context.view_layer.objects.active = obj
                bpy.ops.object.mode_set(mode="EDIT")
                bpy.ops.mesh.select_all(action="SELECT")
                bpy.ops.mesh.symmetrize(direction=direction)
                bpy.ops.mesh.select_all(action="DESELECT")
                bpy.ops.object.mode_set(mode="OBJECT")
            context.view_layer.objects.active = context.object
        elif context.mode == "EDIT_MESH":
            bpy.ops.mesh.symmetrize(direction=direction)
        elif context.mode == "SCULPT":
            context.scene.tool_settings.sculpt.symmetrize_direction = direction
            bpy.ops.sculpt.symmetrize()

    @staticmethod
    def dupticate(object, name="Object"):
        if object.mode == "EDIT":
            bm = bmesh.from_edit_mesh(object.data).copy()
            bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.select])
        else:
            bm = bmesh.new()
            bm.from_mesh(object.data)

        mesh = bpy.data.meshes.new(name)
        bm.to_mesh(mesh)
        mesh.update()
        bm.free()

        return bpy.data.objects.new(name, mesh)

    @staticmethod
    def edge_decal(object, name, amount, offset, clamp_overlap) -> bpy.types.Object:
        """Create edge decal from the selected edges.

        object (bpy.types.Object) - The object to create the decal from.
        name (str) - The name of the decal.
        amount (float) - The amount of the decal.
        clamp_overlap (bool) - Clamp the width to avoid overlap.
        offset (float) - The offset of the decal.
        return (bpy.types.Object) - The decal object.
        """
        bm = bmesh.from_edit_mesh(object.data).copy()
        decal = bmesh.ops.bevel(
            bm,
            geom=[e for e in bm.edges if e.select],
            offset=amount,
            profile=1.0,
            segments=2,
            affect="EDGES",
            clamp_overlap=clamp_overlap,
        )
        bmesh.ops.delete(bm, geom=[f for f in bm.faces if f not in decal["faces"]], context="FACES")
        bmesh.ops.scale(bm, vec=(offset, offset, offset), verts=bm.verts)
        return Mesh.bmesh_to_object(bm, name)

    @staticmethod
    def bmesh_to_object(bm, name) -> bpy.types.Object:
        """Create an object from a bmesh.

        bm (bmesh) - The bmesh to create the object from.
        name (str) - The name of the object.
        return (bpy.types.Object) - The created object.
        """
        mesh = bpy.data.meshes.new(name)
        bm.to_mesh(mesh)
        mesh.update()
        bm.free()
        return bpy.data.objects.new(name, mesh)
