import bpy


class Scene:
    @staticmethod
    def new_scene(name: str) -> bpy.types.Scene:
        """
        Create a new scene.

        name (str) - The name of the scene.
        returns (bpy.types.Scene) - The new scene.
        """
        return bpy.data.scenes.get(name) or bpy.data.scenes.new(name)
