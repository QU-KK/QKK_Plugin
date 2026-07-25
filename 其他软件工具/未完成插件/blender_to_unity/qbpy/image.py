import bpy
import os
from .scene import Scene


class Image:
    @staticmethod
    def new_image(
        name: str = "Untitled",
        width: int = 1024,
        height: int = 1024,
        color: tuple = (0.0, 0.0, 0.0, 1.0),
        non_color: bool = False,
        alpha: bool = False,
        generated_type: str = "BLANK",
        tiled: bool = False,
        check: bool = True,
    ) -> bpy.types.Image:
        """
        Create a new image.

        name (str, optional) - The name of the image.
        width (int, optional) - Width of the image
        height (int, optional) - Height of the image
        color (tuple, optional) - The color of the image.
        non_color (bool, optional) - Create image with non-color data color space
        alpha (bool, optional) - Create an image with an alpha channel
        generated_type (enum in ['BLANK', 'UV_GRID', 'COLOR_GRID'], default 'BLANK') - Fill the image with a grid for UV map testing
        tiles (bool, optional) - Create a tiled image
        check (bool, optional) - Check if the image exists
        returns (bpy.types.Image) - The newly created image
        """
        if check:
            image = bpy.data.images.get(name)
            if not image:
                image = bpy.data.images.new(
                    name=name,
                    width=width,
                    height=height,
                    is_data=non_color,
                    alpha=alpha,
                    tiled=tiled,
                    float_buffer=True,
                )
            image.generated_width = width
            image.generated_height = height
        else:
            image = bpy.data.images.new(
                name=name,
                width=width,
                height=height,
                is_data=non_color,
                alpha=alpha,
                tiled=tiled,
                float_buffer=True,
            )
        image.generated_color = color
        image.generated_type = generated_type

        return image

    @staticmethod
    def save_image(image: bpy.types.Image, path: str = bpy.app.tempdir, name: str = ""):
        """
        Save the image to the filepath.
        image (bpy.types.Image) - The image to save.
        path (str) - The path to save the image to.
        name (str) - The name of the image.
        """
        if not name:
            name = image.name

        if image.file_format == "OPEN_EXR":
            image.filepath_raw = os.path.join(path, f"{name}.exr")
        else:
            image.filepath_raw = os.path.join(path, f"{name}.{image.file_format.lower()}")
        image.save()
        return image.filepath_raw

    @staticmethod
    def save_image_as(
        image: bpy.types.Image,
        path: str = bpy.app.tempdir,
        name: str = "",
        file_format: str = "PNG",
        color_mode: str = "RGB",
        color_depth: str = "8",
        compression: int = 15,
        quality: int = 100,
        exr_codec="ZIP",
        tiff_codec="DEFLATE",
        view_transform: str = "Standard",
    ):
        """
        Save the image to the filepath.

        image (bpy.types.Image) - The image to save.
        path (str) - The path to save the image to.
        name (str, optional) - The name of the image.
        file_format (enum in ['BMP', 'IRIS', 'PNG', 'JPEG', 'JPEG2000', 'TARGA', 'TARGA_RAW', 'CINEON', 'DPX', 'OPEN_EXR_MULTILAYER', 'OPEN_EXR', 'HDR', 'TIFF', 'WEBP', 'AVI_JPEG', 'AVI_RAW', 'FFMPEG'], default 'PNG') - The file format to save the image as.
        color_mode (enum in ['BW', 'RGB', 'RGBA'], default 'RGBA') - The color mode of the image.
        color_depth (enum in ['8', '16'], default '8') - The color depth of the image.
        compression (int in [0, 100], default 15) - The compression level of the image.
        quality (int in [0, 100], default 100) - The quality of the image.
        """
        scene = Scene.new_scene(name="save_image")
        image_name = image.name

        if not name:
            name = image.name

        settings = scene.render.image_settings
        settings.file_format = file_format
        settings.color_mode = "RGB" if file_format == "JPEG" else color_mode
        settings.color_depth = color_depth
        settings.compression = compression
        settings.quality = quality
        settings.exr_codec = exr_codec
        settings.tiff_codec = tiff_codec
        scene.view_settings.view_transform = view_transform
        filepath = os.path.join(path, f"{name}{scene.render.file_extension}")
        image.save_render(filepath=bpy.path.abspath(filepath), scene=scene)
        bpy.data.scenes.remove(scene)
        image.name = image_name

    @staticmethod
    def get_image(name: str) -> bpy.types.Image:
        """
        Get image by name.

        name (str) - The name of the image to get.
        return (bpy.types.Image) - The image.
        """
        return bpy.data.images.get(name)

    @staticmethod
    def load_image(filepath: str = bpy.app.tempdir, check_existing: bool = True) -> bpy.types.Image:
        """
        Load the image.

        filepath (str, optional) - The path to the image.
        check (bool, optional) - If True, check if the image exists.
        return (bpy.types.Image) - The image.
        """
        return bpy.data.images.load(filepath=bpy.path.abspath(filepath), check_existing=check_existing)
