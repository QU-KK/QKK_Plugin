import bpy
from bpy.types import Operator
from bpy.props import *
from ....qbpy.blender import preferences
from ....qbpy.object import Object
from ....qbpy.material import Material
from ....qbpy.collection import Collection
from ....qbpy.property import Property
from ...utils.export import Export
import os
import subprocess
import threading
import json
import sys
import queue
import time
from math import radians
from contextlib import suppress


class UNITY_OT_export_fbx_test(Operator, Export):
    """Export Test"""

    bl_label = "Export Test"
    bl_idname = "unity.export_fbx_test"
    bl_options = {"REGISTER"}

    properties: StringProperty()
    collections: StringProperty()

    def make_single_user_data(self, object):
        if object.type == "MESH" and object.data.users > 1:
            object.data = object.data.copy()

    def execute(self, context):
        self.prop = preferences().unity.export

        if self.prop.selection_type == "OBJECT":
            selected_objects = [object for object in context.selected_objects if "LOD" not in object.name and "Collider" not in object.name]
        elif self.prop.selection_type == "COLLECTION":
            selected_objects = []
            for collection in Collection.selected_collections():
                selected_objects.extend(object for object in collection.objects if not object.parent)
                if self.prop.use_sub_collection:
                    for collection in collection.children_recursive:
                        selected_objects.extend(object for object in collection.objects if not object.parent)

        self.export_data = {}

        for object in selected_objects:
            self.export_object(context, object)

        return {"FINISHED"}

    def export_object(self, context, object):
        # self.make_single_user_data(object=object)
        # for child in object.children_recursive:
        #     self.make_single_user_data(object=child)

        # # REMOVE COLLIDER MATERIAL
        # for child in object.children_recursive:
        #     if 'Collider' in child.name:
        #         Material.remove_material_slots(obj=child)

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

    def export_empty(self, context, object: bpy.types.Object) -> str:
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
        if self.prop.selection_type == "OBJECT" and self.prop.use_include:
            override["selected_objects"] = [object] + list(object.children_recursive)
        elif self.prop.selection_type == "COLLECTION":
            override["selected_objects"] = [object] + list(object.children_recursive)
        else:
            override["selected_objects"] = [object] + list(object.children)

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

    def export_mesh(self, context, object: bpy.types.Object) -> str:
        object_name = object.name

        # ASSIGN BAKED MATERIAL
        if material := bpy.data.materials.get(f"{object.name}_BAKED"):
            Material.remove_material_slots(obj=object)
            Material.set_material(obj=object, material=material)

            for child in object.children:
                if "LOD" in child.name:
                    Material.remove_material_slots(obj=child)
                    Material.set_material(obj=child, material=material)

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
            if self.prop.selection_type == "OBJECT" and self.prop.use_include:
                override["selected_objects"] = [self.empty] + list(self.empty.children_recursive)
            elif self.prop.selection_type == "COLLECTION":
                override["selected_objects"] = [self.empty] + list(self.empty.children_recursive)
            else:
                override["selected_objects"] = [self.empty] + list(self.empty.children)

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
            if self.prop.selection_type == "OBJECT" and self.prop.use_include:
                override["selected_objects"] = [object] + list(object.children_recursive)
            elif self.prop.selection_type == "COLLECTION":
                override["selected_objects"] = [object] + list(object.children_recursive)
            else:
                override["selected_objects"] = [object] + list(object.children)

            # RESTORE
            override = context.copy()
            override["selected_editable_objects"] = [object] + list(object.children_recursive)
            with context.temp_override(**override):
                bpy.ops.object.transform_apply(location=False, scale=True, rotation=True)

            for object, location in self.export_data["location"].items():
                object.location = location

    def export_armature(self, context, object):
        self.export_data["location"][object] = object.location.copy()
        object.location = (0, 0, 0)

        override = context.copy()
        override["selected_objects"] = [object] + list(object.children)

        for object, location in self.export_data["location"].items():
            object.location = location


classes = (UNITY_OT_export_fbx_test,)


register, unregister = bpy.utils.register_classes_factory(classes)
