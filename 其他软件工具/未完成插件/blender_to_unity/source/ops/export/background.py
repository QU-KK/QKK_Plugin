import bpy
from bpy.types import Operator
from bpy.props import StringProperty
from ....qbpy.object import Object
from ....qbpy.material import Material
from ....qbpy.property import Property
from ...utils.export import Export
import json
import sys
from math import radians


class UNITY_OT_background_export_fbx(Operator, Export):
    """Background Export FBX"""

    bl_label = "Background Export"
    bl_idname = "unity.background_export_fbx"
    bl_options = {"REGISTER", "INTERNAL"}

    properties: StringProperty()
    collections: StringProperty()

    def make_single_user_data(self, object):
        if object.type == "MESH" and object.data.users > 1:
            object.data = object.data.copy()

    def get_selected_objects(self, context):
        self.fbx_prop = context.scene.unity.fbx
        self.export_prop = context.scene.unity.export
        Property.apply_data_to_item(self.fbx_prop, json.loads(self.properties.replace("\\", "\\\\")))

        if self.export_prop.selection_type == "OBJECT":
            return [object for object in context.selected_objects if "LOD" not in object.name and "Collider" not in object.name]
        elif self.export_prop.selection_type == "COLLECTION":
            return self.get_selected_objects_from_collections()

    def get_selected_objects_from_collections(self):
        selected_objects = []
        for name in json.loads(self.collections):
            selected_objects.extend(object for object in bpy.data.collections[name].objects if not object.parent)
            if self.export_prop.use_sub_collection:
                for collection in bpy.data.collections[name].children_recursive:
                    selected_objects.extend(object for object in collection.objects if not object.parent)
        return selected_objects

    def execute(self, context):
        selected_objects = self.get_selected_objects(context)
        self.export_data = {}

        for obj in selected_objects:
            if obj.type not in {"EMPTY", "MESH", "ARMATURE"}:
                continue

            result = self.export_object(context, object=obj)
            print(f"UNITY:REPORT:INFO:Exported to: {result}")
            print("UNITY: Exported")
            sys.stdout.flush()

        return {"FINISHED"}

    def export_object(self, context, object):
        self.make_single_user_data(object=object)

        for child in object.children_recursive:
            self.make_single_user_data(object=child)

        # REMOVE COLLIDER MATERIAL
        for child in object.children_recursive:
            if "Collider" in child.name:
                Material.remove_material_slots(obj=child)

        self.export_data["name"] = {}
        self.export_data["location"] = {}
        self.export_data["parent"] = {}

        override = context.copy()
        override["selected_editable_objects"] = [object] + list(object.children_recursive)

        with context.temp_override(**override):
            bpy.ops.object.transform_apply(location=False, scale=True, rotation=True)

        if object.type == "EMPTY":
            self.export_empty(context, object)
        elif object.type == "MESH":
            self.export_mesh(context, object)
        elif object.type == "ARMATURE":
            self.export_armature(context, object)

        return self.path

    def assign_texture_to_principled_node(self, material):
        principled_node = next(
            (node for node in material.node_tree.nodes if node.type == "BSDF_PRINCIPLED"),
            None,
        )
        for node in material.node_tree.nodes:
            if node.type == "TEX_IMAGE" and node.image:
                if "Metallic" in node.name:
                    material.node_tree.links.new(principled_node.inputs["Metallic"], node.outputs["Color"])
                elif "Height" in node.name:
                    material.node_tree.links.new(principled_node.inputs["Alpha"], node.outputs["Color"])
                elif "Occlusion" in node.name:
                    material.node_tree.links.new(
                        principled_node.inputs["Emission Strength"],
                        node.outputs["Color"],
                    )
                elif "Specular" in node.name:
                    material.node_tree.links.new(
                        principled_node.inputs["Specular IOR Level"],
                        node.outputs["Color"],
                    )
                elif "Mask" in node.name:
                    material.node_tree.links.new(principled_node.inputs["Metallic"], node.outputs["Color"])
                elif "Coat" in node.name:
                    material.node_tree.links.new(
                        principled_node.inputs["Emission Strength"],
                        node.outputs["Color"],
                    )

    def assign_texture_to_principled_node_v3(self, material):
        principled_node = next(
            (node for node in material.node_tree.nodes if node.type == "BSDF_PRINCIPLED"),
            None,
        )
        for node in material.node_tree.nodes:
            if node.type == "TEX_IMAGE" and node.image:
                if "Metallic" in node.name:
                    material.node_tree.links.new(principled_node.inputs["Metallic"], node.outputs["Color"])
                elif "Height" in node.name:
                    material.node_tree.links.new(principled_node.inputs["Alpha"], node.outputs["Color"])
                elif "Occlusion" in node.name:
                    material.node_tree.links.new(
                        principled_node.inputs["Emission Strength"],
                        node.outputs["Color"],
                    )
                elif "Specular" in node.name:
                    material.node_tree.links.new(principled_node.inputs["Specular"], node.outputs["Color"])
                elif "Mask" in node.name:
                    material.node_tree.links.new(principled_node.inputs["Metallic"], node.outputs["Color"])
                elif "Coat" in node.name:
                    material.node_tree.links.new(
                        principled_node.inputs["Emission Strength"],
                        node.outputs["Color"],
                    )

    def assign_baked_material(self, object):
        for material in bpy.data.materials:
            if material.get("mat_type") == f"{object.name}_BAKED":
                material.name = material.name.replace("_BAKED", "")
                Material.remove_material_slots(obj=object)
                Material.set_material(obj=object, material=material)

                for child in object.children:
                    if "LOD" in child.name:
                        Material.remove_material_slots(obj=child)
                        Material.set_material(obj=child, material=material)

                # ASSIGN TEXTURE TO PRINCIPLED NODE
                if bpy.app.version >= (4, 0, 0):
                    self.assign_texture_to_principled_node(material=material)
                else:
                    self.assign_texture_to_principled_node_v3(material=material)

    ## EXPORT EMPTY
    def export_empty(self, context, object: bpy.types.Object) -> str:
        object["shader_type"] = self.export_prop.shader_type
        if self.export_prop.use_materials and self.export_prop.use_baked_material:
            for obj in object.children:
                if obj.type == "MESH":
                    self.assign_baked_material(object=obj)
        elif not self.export_prop.use_materials:
            Material.remove_material_slots(obj=object)
            for obj in object.children:
                Material.remove_material_slots(obj=obj)

        # RENAME OBJECT IF LOD EXISTS
        for child in object.children:
            if self.is_lod(object=child):
                self.export_data["name"][child] = child.name
                Object.rename_object(object=child, name=f"{child.name}_LOD0")

        # CORRECT TRANSFORM
        self.export_data["location"][object] = object.location.copy()
        object.location = (0, 0, 0)

        # PREPARE LODS
        for child in object.children:
            for lod in child.children:
                if "LOD" in lod.name:
                    self.export_data["parent"][lod.parent] = lod
                    Object.parent_object(parent=object, child=lod)

        # APPLY TRANSFORM
        object.rotation_euler.x = radians(-90)
        override = context.copy()
        override["selected_editable_objects"] = [object] + list(object.children_recursive)

        with context.temp_override(**override):
            bpy.ops.object.transform_apply(location=False, scale=True, rotation=True)

        object.rotation_euler.x = radians(90)

        # EXPORT TODO
        override = context.copy()
        if self.export_prop.selection_type == "OBJECT" and self.export_prop.use_include:
            override["selected_objects"] = [object] + list(object.children_recursive)
        elif self.export_prop.selection_type == "COLLECTION":
            override["selected_objects"] = [object] + list(object.children_recursive)
        else:
            colliders = []
            for child in object.children:
                colliders.extend(obj for obj in child.children if "Collider" in obj.name)

            override["selected_objects"] = [object] + list(object.children) + colliders

        with context.temp_override(**override):
            self.path = self.export(name=object.name, export_prop=self.export_prop, fbx_prop=self.fbx_prop)

        # RESTORE
        override = context.copy()
        override["selected_editable_objects"] = [object] + list(object.children_recursive)

        with context.temp_override(**override):
            bpy.ops.object.transform_apply(location=False, scale=True, rotation=True)

        for parent, child in self.export_data["parent"].items():
            if parent is None:
                continue
            Object.parent_object(parent, child)
        for object, location in self.export_data["location"].items():
            object.location = location
        for object, name in self.export_data["name"].items():
            Object.rename_object(object, name)

    ## EXPORT MESH
    def export_mesh(self, context, object: bpy.types.Object) -> str:
        object_name = object.name

        object["shader_type"] = self.export_prop.shader_type
        if self.export_prop.use_materials and self.export_prop.use_baked_material:
            self.assign_baked_material(object)
        elif not self.export_prop.use_materials:
            Material.remove_material_slots(obj=object)
            for obj in object.children:
                Material.remove_material_slots(obj=obj)

        if self.is_lod(object=object):
            self.export_data["name"][object] = object.name
            Object.rename_object(object=object, name=f"{object.name}_LOD0")

            self.empty = bpy.data.objects.new(object_name, None)
            Object.link_object(object=self.empty, collection=object.users_collection[0])

            self.export_data["location"][object] = object.matrix_world.copy()
            object.location = (0, 0, 0)

            self.export_data["parent"][object.parent] = object
            object.parent = self.empty

            for lod in object.children:
                if "LOD" in lod.name:
                    self.export_data["location"][lod] = lod.matrix_world.copy()
                    lod.location = self.empty.location
                    self.export_data["parent"][lod.parent] = lod
                    lod.parent = self.empty

            # APPLY TRANSFORM
            self.empty.rotation_euler.x = radians(-90)
            override = context.copy()
            override["selected_editable_objects"] = [self.empty] + list(self.empty.children_recursive)
            with context.temp_override(**override):
                bpy.ops.object.transform_apply(location=False, scale=True, rotation=True)

            self.empty.rotation_euler.x = radians(90)

            # EXPORT
            override = context.copy()
            if self.export_prop.selection_type == "OBJECT" and self.export_prop.use_include:
                override["selected_objects"] = [self.empty] + list(self.empty.children_recursive)
            elif self.export_prop.selection_type == "COLLECTION":
                override["selected_objects"] = [self.empty] + list(self.empty.children_recursive)
            else:
                colliders = []
                for child in self.empty.children:
                    colliders.extend(obj for obj in child.children if "Collider" in obj.name)

                override["selected_objects"] = [self.empty] + list(self.empty.children) + colliders

            with context.temp_override(**override):
                self.path = self.export(
                    name=object_name,
                    export_prop=self.export_prop,
                    fbx_prop=self.fbx_prop,
                )

            # RESTORE
            override = context.copy()
            override["selected_editable_objects"] = [self.empty] + list(self.empty.children_recursive)

            with context.temp_override(**override):
                bpy.ops.object.transform_apply(location=False, scale=True, rotation=True)

            for parent, child in self.export_data["parent"].items():
                if parent is None:
                    continue
                Object.parent_object(parent, child)
            for object, matrix_world in self.export_data["location"].items():
                object.matrix_world = matrix_world
            for object, name in self.export_data["name"].items():
                Object.rename_object(object, name)

            bpy.data.objects.remove(self.empty)

        else:
            self.export_data["location"][object] = object.location.copy()
            object.location = (0, 0, 0)

            # APPLY TRANSFORM
            object.rotation_euler.x = radians(-90)
            override = context.copy()
            override["selected_editable_objects"] = [object] + list(object.children_recursive)

            with context.temp_override(**override):
                bpy.ops.object.transform_apply(location=False, scale=True, rotation=True)
            object.rotation_euler.x = radians(90)

            # EXPORT
            override = context.copy()
            if self.export_prop.selection_type == "OBJECT" and self.export_prop.use_include:
                override["selected_objects"] = [object] + list(object.children_recursive)
            elif self.export_prop.selection_type == "COLLECTION":
                override["selected_objects"] = [object] + list(object.children_recursive)
            else:
                override["selected_objects"] = [object] + [child for child in object.children if "Collider" in child.name]

            with context.temp_override(**override):
                self.path = self.export(
                    name=object_name,
                    export_prop=self.export_prop,
                    fbx_prop=self.fbx_prop,
                )

            # RESTORE
            override = context.copy()
            override["selected_editable_objects"] = [object] + list(object.children_recursive)

            with context.temp_override(**override):
                bpy.ops.object.transform_apply(location=False, scale=True, rotation=True)

            for object, location in self.export_data["location"].items():
                object.location = location

    ## EXPORT ARMATURE
    def export_armature(self, context, object):
        object["shader_type"] = self.export_prop.shader_type
        # ASSIGN BAKED MATERIAL
        if self.export_prop.use_materials and self.export_prop.use_baked_material:
            for obj in object.children:
                if obj.type == "MESH":
                    for material in bpy.data.materials:
                        if material.get("mat_type") == f"{obj.name}_BAKED":
                            material.name = material.name.replace("_BAKED", "")
                            Material.remove_material_slots(obj=obj)
                            Material.set_material(obj=obj, material=material)

                            # ASSIGN TEXTURE TO PRINCIPLED NODE
                            if bpy.app.version >= (4, 0, 0):
                                self.assign_texture_to_principled_node(material=material)
                            else:
                                self.assign_texture_to_principled_node_v3(material=material)

        elif not self.export_prop.use_materials:
            for obj in object.children:
                Material.remove_material_slots(obj=obj)

        self.export_data["location"][object] = object.location.copy()
        object.location = (0, 0, 0)

        override = context.copy()
        override["selected_objects"] = [object] + list(object.children)

        with context.temp_override(**override):
            self.path = self.export(name=object.name, export_prop=self.export_prop, fbx_prop=self.fbx_prop)

        for object, location in self.export_data["location"].items():
            object.location = location


classes = (UNITY_OT_background_export_fbx,)


register, unregister = bpy.utils.register_classes_factory(classes)
