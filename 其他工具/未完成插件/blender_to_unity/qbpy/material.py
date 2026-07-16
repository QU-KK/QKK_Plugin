import bpy


class Material:
    @staticmethod
    def get_material(name: str, use_nodes: bool = True) -> bpy.types.Material:
        """Get material by name.

        name (str) - Name of material.
        return (bpy.types.Material) - Material.
        """
        material = bpy.data.materials.get(name)
        if material is None:
            material = bpy.data.materials.new(name)
        material.use_nodes = use_nodes
        return material

    @staticmethod
    def set_material(obj: bpy.types.Object, material: bpy.types.Material, index: int = 0):
        """Set material to object.

        obj (bpy.types.Object) - Object to set material to.
        material (bpy.types.Material) - Material to set.
        """
        if obj.data.materials:
            obj.data.materials[index] = material
        else:
            obj.data.materials.append(material)

    @staticmethod
    def remove_material(obj: bpy.types.Object, material: bpy.types.Material):
        """
        Remove the material.

        obj (bpy.types.Object) - The object to remove material from.
        material (bpy.types.Material) - Material to remove.
        """
        if obj.type == "MESH" and obj.material_slots:
            for slot in obj.material_slots:
                if slot.material and slot.material == material:
                    slot.material = None

    @staticmethod
    def remove_materials(obj: bpy.types.Object):
        """
        Remove all the materials from material slots.

        obj (bpy.types.Object) - The object to remove materials from.
        """
        if obj.type == "MESH" and obj.material_slots:
            for slot in obj.material_slots:
                if slot.material:
                    slot.material = None

    @staticmethod
    def remove_material_slots(obj: bpy.types.Object):
        """
        Remove all the material slots.

        obj (bpy.types.Object) - The object to remove material slots from.
        """
        if obj.type == "MESH" and obj.material_slots:
            obj.data.materials.clear()
