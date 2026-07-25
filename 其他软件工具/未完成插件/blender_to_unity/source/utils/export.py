import bpy
import os
from ...qbpy.object import Object


class Export:
    def is_lod(self, object):
        """
        Check if object has lod.

        object (bpy.types.Object) - Object to check.
        return (bool) - True if object has lod.
        """
        return any("LOD" in child.name for child in object.children if child.type == "MESH")

    def export(self, name, export_prop, fbx_prop) -> str:
        """
        Export to Unity.

        object (bpy.types.Object) - Name of the unity file.
        export_prop (bpy.types.PropertyGroup) - Export Property Group.
        fbx_prop (bpy.types.PropertyGroup) - FBX Property Group.
        return (str) - File path.
        """
        if export_prop.type == "UNITY":
            unity_folder = export_prop.unity_folders[export_prop.unity_folder_index]
            if unity_folder.path:
                if bpy.app.version >= (3, 6, 0):
                    Object.fbx_export(
                        filepath=os.path.join(
                            unity_folder.path,
                            f"{name.replace(':', '_').replace(' : ', '_')}.fbx",
                        ),
                        properties=fbx_prop,
                    )
                else:
                    Object.export_fbx(
                        filepath=os.path.join(
                            unity_folder.path,
                            f"{name.replace(':', '_').replace(' : ', '_')}.fbx",
                        ),
                        properties=fbx_prop,
                    )
                return unity_folder.path

        elif export_prop.type == "DISK":
            disk_folder = export_prop.disk_folders[export_prop.disk_folder_index]
            if disk_folder.path:
                if bpy.app.version >= (3, 6, 0):
                    Object.fbx_export(
                        filepath=os.path.join(
                            disk_folder.path,
                            f"{name.replace(':', '_').replace(' : ', '_')}.fbx",
                        ),
                        properties=fbx_prop,
                    )
                else:
                    Object.export_fbx(
                        filepath=os.path.join(
                            disk_folder.path,
                            f"{name.replace(':', '_').replace(' : ', '_')}.fbx",
                        ),
                        properties=fbx_prop,
                    )
                return disk_folder.path

        elif export_prop.type == "BOTH":
            unity_folder = export_prop.unity_folders[export_prop.unity_folder_index]
            if unity_folder.path:
                if bpy.app.version >= (3, 6, 0):
                    Object.fbx_export(
                        filepath=os.path.join(
                            unity_folder.path,
                            f"{name.replace(':', '_').replace(' : ', '_')}.fbx",
                        ),
                        properties=fbx_prop,
                    )
                else:
                    Object.export_fbx(
                        filepath=os.path.join(
                            unity_folder.path,
                            f"{name.replace(':', '_').replace(' : ', '_')}.fbx",
                        ),
                        properties=fbx_prop,
                    )

            disk_folder = export_prop.disk_folders[export_prop.disk_folder_index]
            if disk_folder.path:
                if bpy.app.version >= (3, 6, 0):
                    Object.fbx_export(
                        filepath=os.path.join(
                            disk_folder.path,
                            f"{name.replace(':', '_').replace(' : ', '_')}.fbx",
                        ),
                        properties=fbx_prop,
                    )
                else:
                    Object.export_fbx(
                        filepath=os.path.join(
                            disk_folder.path,
                            f"{name.replace(':', '_').replace(' : ', '_')}.fbx",
                        ),
                        properties=fbx_prop,
                    )

            return unity_folder.path
