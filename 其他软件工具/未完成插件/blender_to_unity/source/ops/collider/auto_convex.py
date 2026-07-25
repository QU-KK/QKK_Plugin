import bpy
import bmesh
from bpy.types import Operator
from ....qbpy.blender import preferences
from ....qbpy.object import Object
from ....qbpy.modifier import Modifier
from ....qbpy.material import Material
from ....qbpy.collection import Collection
from ...utils.collider import Collider
import os
import sys
from subprocess import Popen
from math import radians
from mathutils import Matrix
import time


class UNITY_OT_auto_convex(Operator, Collider):
    bl_label = "Convex"
    bl_idname = "unity.collider_convex_vhacd"
    bl_options = {"REGISTER", "INTERNAL", "PRESET"}

    @classmethod
    def description(cls, context, event):
        return """VHACD Convex Collider.\n\nShift  •  Dafault Convex Collider"""

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        vhacd = preferences().unity.vhacd
        layout.prop(vhacd, "version")
        vhacd.draw(context, layout)

    def invoke(self, context, event):
        self.unity = preferences().unity
        self.vhacd = self.unity.vhacd

        if event.shift:
            bpy.ops.unity.collider_convex("EXEC_DEFAULT")
            self.report({"INFO"}, "Added: Convex Collider")
            return {"FINISHED"}

        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        if self.vhacd.version in {"VHACD4.1", "VHACD4"}:
            self.vhacd_4(context)
            self.report({"INFO"}, "Added: Convex Collider (VHACD 4)")
        else:
            self.vhacd_2(context)
            self.report({"INFO"}, "Added: Convex Collider (VHACD 2)")

        return {"FINISHED"}

    def vhacd_2(self, context):
        # Check executable path
        vhacd_path = bpy.path.abspath(self.vhacd.path)

        selected_objects = [
            object for object in context.selected_objects if object.type == "MESH" and "Collider" not in object.name and "LOD" not in object.name
        ]

        if not selected_objects:
            self.report({"ERROR"}, "Object(s) must be selected first")
            return {"CANCELLED"}

        for object in selected_objects:
            object.select_set(False)

        new_objects = []

        for object in selected_objects:
            for child in object.children:
                if "vhacd" in child:
                    bpy.data.meshes.remove(mesh=child.data)
            if object.type != "MESH":
                continue

            # Base filename is object name with invalid characters removed
            filename = "".join(c for c in object.name if c.isalnum() or c in (" ", ".", "_")).rstrip()

            off_filepath = os.path.join(bpy.app.tempdir, f"{filename}.off")
            out_filepath = os.path.join(bpy.app.tempdir, f"{filename}.wrl")
            log_filepath = os.path.join(bpy.app.tempdir, f"{filename}_log.txt")

            mesh = object.data.copy()

            bm = bmesh.new()
            bm.from_mesh(mesh)
            bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.0001)
            bmesh.ops.triangulate(bm, faces=bm.faces)
            bm.to_mesh(mesh)
            mesh.update()
            bm.free()

            Object.export_off(filepath=off_filepath, mesh=mesh)

            cmd_line = f'"{vhacd_path}" --input "{off_filepath}" --resolution {self.vhacd.resolution} --depth {self.vhacd.depth} --concavity {self.vhacd.concavity} --planeDownsampling {self.vhacd.plane_downsample} --convexhullDownsampling {self.vhacd.hull_downsample} --alpha {self.vhacd.alpha} --beta {self.vhacd.beta} --gamma {self.vhacd.gamma} --pca {"1" if self.vhacd.normalize else "0"} --mode {"1" if self.vhacd.mode == "TETRAHEDRON" else "0"} --maxNumVerticesPerCH {self.vhacd.hull_vertices} --minVolumePerCH {self.vhacd.hull_volume} --output "{out_filepath}" --log "{log_filepath}"'
            print(f"Running V-HACD...\n{cmd_line}\n")
            vhacd_process = Popen(cmd_line, bufsize=-1, close_fds=True, shell=True, cwd=bpy.app.tempdir)

            bpy.data.meshes.remove(mesh)

            vhacd_process.wait()
            if not os.path.exists(out_filepath):
                continue

            bpy.ops.import_scene.x3d(filepath=out_filepath, axis_forward="Y", axis_up="Z")
            imported_objects = bpy.context.selected_objects
            new_objects.extend(imported_objects)

            if self.unity.object_collection:
                collision_object_collection = Collection.get_collection(collection=object.name)
                Collection.link_collection(collection=collision_object_collection)

            material = Material.get_material(name="Convex_Collider", use_nodes=False)
            name_template = "*_Collider"

            for index, hull in enumerate(imported_objects):
                hull.select_set(False)
                name = name_template.replace("*", object.name, 1)
                name = name.replace("#", str(index + 1), 1)
                if name == name_template:
                    name += str(index + 1)
                hull["vhacd"] = ""
                bpy.data.materials.remove(hull.material_slots[0].material)
                Object.rename_object(object=hull, name=name)
                Object.parent_object(parent=object, child=hull, copy_transform=False)
                self.collision_object_color(object=hull, material=material, color=self.unity.collider.convex)

                if self.unity.object_collection:
                    Object.link_object(object=hull, collection=collision_object_collection)
                else:
                    Object.link_object(object=hull, collection=object.users_collection[0])

                if self.vhacd.shrinkwrap:
                    Modifier.add_shrinkwrap_modifier(object=hull, target=object)

            # remove from temp
            os.remove(off_filepath)
            os.remove(out_filepath)
            os.remove(log_filepath)

        if not new_objects:
            for object in selected_objects:
                object.select_set(True)
            self.report({"WARNING"}, "No meshes to process!")
            return {"CANCELLED"}

        for object in selected_objects:
            object.select_set(True)

        return {"FINISHED"}

    def vhacd_4(self, context):
        # Check executable path
        vhacd_path = bpy.path.abspath(self.vhacd.path)

        selected_objects = [
            object for object in context.selected_objects if object.type == "MESH" and "Collider" not in object.name and "LOD" not in object.name
        ]

        if not selected_objects:
            self.report({"ERROR"}, "Object(s) must be selected first")
            return {"CANCELLED"}

        for object in selected_objects:
            object.select_set(False)

        new_objects = []

        for object in selected_objects:
            for child in object.children:
                if "vhacd" in child:
                    bpy.data.meshes.remove(mesh=child.data)

            filename = "".join(c for c in object.name if c.isalnum() or c in (" ", ".", "_")).rstrip()

            filepath = os.path.join(bpy.app.tempdir, f"{filename}.obj")
            obj_filepath = os.path.join(bpy.app.tempdir, "decomp.obj")
            stl_filepath = os.path.join(bpy.app.tempdir, "decomp.stl")

            if self.vhacd.version == "VHACD4.1":
                mtl_filepath = os.path.join(bpy.app.tempdir, "decomp.mtl")

            object.select_set(True)

            if bpy.app.version >= (4, 0, 0):
                bpy.ops.wm.obj_export(filepath=filepath, export_selected_objects=True)
            else:
                bpy.ops.export_scene.obj(filepath=filepath, use_selection=True)

            object.select_set(False)

            # override = bpy.context.copy()
            # override['selected_objects'] = [object]

            # with bpy.context.temp_override(**override):
            #     if bpy.app.version >= (4, 0, 0):
            #         bpy.ops.wm.obj_export(filepath=filepath, export_selected_objects=True)
            #     else:
            #         bpy.ops.export_scene.obj(filepath=filepath, use_selection=True)

            cmd_line = f'"{vhacd_path}" "{filepath}" -r {self.vhacd.voxel_resolution} -d {self.vhacd.recursion_depth} -h {self.vhacd.output_hull} -v {self.vhacd.vertex_count} -f {self.vhacd.fill_mode.lower()} -s {str(self.vhacd.shrinkwrap).lower()} -a {str(self.vhacd.asynchronous).lower()} -l {self.vhacd.edge_length} -p {str(self.vhacd.split_hull).lower()} -e {self.vhacd.volume_error} -g false'
            print(f"Running V-HACD...\n{cmd_line}\n")
            vhacd_process = Popen(cmd_line, bufsize=-1, close_fds=True, shell=True, cwd=bpy.app.tempdir)
            vhacd_process.wait()

            if not os.path.exists(obj_filepath):
                continue

            if bpy.app.version >= (4, 0, 0):
                Object.obj_import(filepath=obj_filepath)
            else:
                Object.import_obj(filepath=obj_filepath)

            imported_objects = bpy.context.selected_objects
            new_objects.extend(imported_objects)

            if self.unity.object_collection:
                collision_object_collection = Collection.get_collection(collection=object.name)
                Collection.link_collection(collection=collision_object_collection)

            material = Material.get_material(name="Convex_Collider", use_nodes=False)
            name_template = "*_Collider"

            matrix = Matrix.Rotation(radians(90), 4, "X")

            for index, hull in enumerate(imported_objects):
                hull.select_set(False)
                name = name_template.replace("*", object.name, 1)
                name = name.replace("#", str(index + 1), 1)
                if name == name_template:
                    name += str(index + 1)
                hull["vhacd"] = ""

                if hull.material_slots:
                    for i, slot in enumerate(hull.material_slots):
                        if slot.material:
                            bpy.data.materials.remove(slot.material)
                        else:
                            hull.active_material_index = i
                            bpy.ops.object.material_slot_remove()

                Object.object_origin(object=hull, origin=object.location)
                Object.rename_object(object=hull, name=name)
                Object.parent_object(parent=object, child=hull)
                self.collision_object_color(object=hull, material=material, color=self.unity.collider.convex)
                Object.unlink_object(object=hull)

                # correct rotation (0)
                hull.rotation_euler.zero()
                hull.data.transform(matrix)

                if self.unity.object_collection:
                    Object.link_object(object=hull, collection=collision_object_collection)
                else:
                    Object.link_object(object=hull, collection=object.users_collection[0])

            # remove from temp
            os.remove(filepath)
            os.remove(obj_filepath)
            os.remove(stl_filepath)
            if self.vhacd.version == "VHACD4.1":
                os.remove(mtl_filepath)

        if not new_objects:
            for object in selected_objects:
                object.select_set(True)
            self.report({"WARNING"}, "No meshes to process!")
            return {"CANCELLED"}

        for object in selected_objects:
            object.select_set(True)

        return {"FINISHED"}


classes = (UNITY_OT_auto_convex,)

register, unregister = bpy.utils.register_classes_factory(classes)
