# SPDX-FileCopyrightText: 2026 Oxicid
# SPDX-License-Identifier: GPL-3.0-or-later

import bpy
import gpu
import blf
import imbuf
import numpy as np

from pathlib import Path
from mathutils import Matrix, Color
from collections import deque
from gpu_extras.batch import batch_for_shader


from .. import utypes
from .. import operators
from .. import utils
from ..utypes import UMask
from ..preferences import prefs

def replace_image_everywhere(old_img, new_img):
    for mtl in bpy.data.materials:
        if getattr(mtl, 'use_nodes', True):
            for node in mtl.node_tree.nodes:
                if node.type == 'TEX_IMAGE' and node.image == old_img:
                    node.image = new_img


    for area in utils.get_areas_by_type('IMAGE_EDITOR'):
        if area.spaces.active.image == old_img:
            area.spaces.active.image = new_img


def recreate_and_replace(img, w, h):
    old_name = img.name
    img.name += 'temp'
    new_img = bpy.data.images.new(old_name, width=w, height=h, alpha=False, float_buffer=False)

    replace_image_everywhere(img, new_img)
    bpy.data.images.remove(img)

    return new_img


class UNIV_OT_Checker(operators.checker.UNIV_OT_Checker):
    def draw(self, context):
        layout = self.layout
        self.draw_checker_layout(layout)

    def invoke(self, context, event):
        self.univ_checker_texture_save()
        return self.execute(context)

    def univ_checker_texture_save(self):
        # saved_textures_name = []
        texture_folder = self.get_texture_folder_path()
        texture_folder.resolve()
        for img in reversed(bpy.data.images):
            if img.name.startswith('UniV_'):
                if img.users == 0:
                    continue

                if img.generated_type == 'BLANK':
                    texture_file = Path(img.filepath_raw).resolve()
                    if not texture_file.exists():
                        if texture_file.parent == texture_folder:
                            img.save()
                            # saved_textures_name.append(img.name)
                            print(f"UniV: Checker: Saved checker texture {img.name!r} to {str(texture_file)!r}.")
        # return saved_textures_name

    @staticmethod
    def draw_checker_layout(layout, is_generator=False):
        pref = prefs()

        match prefs().checker_generated_type:
            case 'SIMPLE_GRID' | 'GRAVITY':
                layout.prop(pref, 'checker_colors')
            case 'ATLUX':
                layout.prop(pref, 'checker_palettes')
                layout.prop(pref, 'checker_offset')
                layout.prop(pref, 'checker_thickness')
                layout.prop(pref, 'checker_frequency')

        col = layout.column(align=True, heading='Texture Type')
        col.prop(pref, 'checker_generated_type', expand=True)

        if not is_generator:
            row = layout.row(align=True, heading='Apply Method')
            row.scale_x = 0.92
            row.prop(pref, 'checker_toggle', expand=True)

        row = layout.row(align=True, heading='Size')
        row.prop(pref, 'size_x', text='')
        row.prop(pref, 'lock_size', text='', icon='LOCKED' if pref.lock_size else 'UNLOCKED')
        row.prop(pref, 'size_y', text='')

    def execute(self, context):
        if bpy.app.timers.is_registered(self.univ_checker_texture_save):
            bpy.app.timers.unregister(self.univ_checker_texture_save)

        self.checker_default(prefs().checker_toggle == 'TOGGLE')

        bpy.app.timers.register(self.univ_checker_texture_save, first_interval=8.0)
        return {'FINISHED'}

    @staticmethod
    def get_texture_folder_path():
        path = Path(__file__).parent.parent / 'textures'
        path.mkdir(parents=False, exist_ok=True)
        assert path.exists(), path
        return path

    def get_path_from_pattern_name(self):
        path = self.get_texture_folder_path()
        return path / (self.full_pattern_name + '.png')

    def get_exist_texture_or_create(self) -> bpy.types.Image:
        img: bpy.types.Image
        for img in reversed(bpy.data.images):
            img_name = img.name
            if img_name.startswith(self.full_pattern_name):
                if tuple(img.size) != prefs().glob_size or self.has_x_after_resolution(img_name):
                    if img.users == 0:
                        bpy.data.images.remove(img)
                        print(f"UniV: Checker Image '{img_name}' was removed")
                    continue

                if img.generated_type == 'BLANK' and not img.is_dirty and img.packed_file is None:
                    # if image not dirty and not have exists path and not packed, that's need regenerate

                    path = Path(img.filepath_raw)
                    if not path.exists():
                        if self.regenerate_texture(img) is None:
                            continue
                        self.report({'INFO'}, f"UniV: Checker: Texture {img_name!r} was not saved and was regenerated.")
                    # TODO: If the texture is saved but the file is not saved, the texture will turn black,
                    #  so it is necessary to reload the texture. To do this, check - any(img).
                    # elif not any(img):
                    #     pass

                return img

        path = self.get_path_from_pattern_name()
        if path.exists():
            # TODO: Add log.
            before = set(bpy.data.images)

            bpy.ops.image.open(filepath=str(path))

            images = tuple(set(bpy.data.images) - before)
            if images:
                return images[0]
            else:
                print(f"UniV: Checker: Texture open error, maybe imported before?")

        return self.generate_checker_texture()

    @classmethod
    def regenerate_texture(cls, img: bpy.types.Image):
        name = img.name.split('.')[0]
        assert name.startswith('UniV')

        attrs = name.split('_')[1:]
        if not attrs:
            print(f"Texture {img.name!r} has not text info.")
            return None


        # Get size
        size = attrs[-1]
        try:
            if 'x' in size:
                sizes = size.split('x')
                if len(sizes) != 2:
                    print(f"UniV: Checker: Texture has changed incorrect rect size {img.name}")
                    return None
                width = utils.resolution_name_to_value[sizes[0]]
                height = utils.resolution_name_to_value[sizes[1]]
            else:
                width = height = utils.resolution_name_to_value[size]
            size = (width, height)
        except KeyError:
            print(f"UniV: Checker: Texture {size=!r} not supported")
            return None

        # Check size
        if tuple(img.size) != (0, 0) and tuple(img.size) != size:
            print(f"UniV: Checker: Expect size {size!r}, got {tuple(img.size)!r}")
            return None

        texture_type = attrs[0]
        match texture_type:
            case 'SimpleGrid':
                color_type = attrs[1].strip('_').lower()
                if not hasattr(utypes.Colors, color_type):
                    print(f"UniV: Checker: Color type {color_type!r} not found")
                    return None

                col = Color(getattr(utypes.Colors, color_type))
                small_line_col = Color(getattr(utypes.ColorsSmallLines, color_type))

                bound_color = (1, 1, 1)
                if color_type == 'white':
                    bound_color = (0, 0, 0)

                full_pattern_name = f"UniV_{texture_type}_{cls.get_color_name(color_type)}_{utils.resolutions_to_name(*size)}"

                # Sanitize name
                if not img.name.startswith(full_pattern_name):
                    print(f"UniV: Checker: Image {img.name!r} renamed to {full_pattern_name!r}.")
                    img.name = full_pattern_name

                path = cls.get_texture_folder_path() / (full_pattern_name + '.png')

                if tuple(img.size) == (0, 0):
                    print(f"UniV: Checker: Got zero size image, maybe texture was unload.")
                    img = recreate_and_replace(img, *size)

                return cls.generate_simple_grid(full_pattern_name, path, size, col, small_line_col, bound_color, img)
            case 'Gravity':
                color_type = attrs[1].strip('_').lower()
                if not hasattr(utypes.Colors, color_type):
                    print(f"UniV: Checker: Color type {color_type!r} not found")
                    return None

                col1 = Color(getattr(utypes.Colors, color_type))
                col2 = utypes.Colors.dark
                invert = True
                if color_type in ('white', 'black', 'dark', 'brown', 'brown_dark'):
                    invert = False
                    col2 = utypes.Colors.white

                full_pattern_name = f"UniV_{texture_type}_{cls.get_color_name(color_type)}_{utils.resolutions_to_name(*size)}"

                # Sanitize name
                if not img.name.startswith(full_pattern_name):
                    print(f"UniV: Checker: Image {img.name!r} renamed to {full_pattern_name!r}.")
                    img.name = full_pattern_name

                path = cls.get_texture_folder_path() / (full_pattern_name + '.png')

                if tuple(img.size) == (0, 0):
                    print(f"UniV: Checker: Got zero size image, maybe texture was unload.")
                    img = recreate_and_replace(img, *size)

                return cls.generate_gravity(full_pattern_name, path, size, col1, col2, img, invert)
            case 'Atlux':
                resolution_name = utils.resolutions_to_name(*size)

                palettes_name = ''
                potential_palettes_name = attrs[1]
                if potential_palettes_name != resolution_name:
                    if len(potential_palettes_name) != 3:
                        from .. import preferences
                        if potential_palettes_name.upper() in preferences.palettes:
                            palettes_name = '_' + potential_palettes_name.capitalize()
                        else:
                            print(f"UniV: Checker: Image {img.name!r} got incorrect palettes {potential_palettes_name.upper()!r}.")


                atlux_settings = ''
                number_settings = [0,0,2]
                atlux_settings_pat = attrs[-2]
                if atlux_settings_pat != texture_type:
                    if len(atlux_settings_pat) != 3:
                        print(f"UniV: Checker: Image {img.name!r} settings incorrect, got {atlux_settings_pat!r}.")
                    else:
                        for i, setting in enumerate(atlux_settings_pat):
                            try:
                                number_settings[i] = int(setting, 16)  # noqa
                            except TypeError:
                                number_settings = [0, 0, 2]
                                print(f"UniV: Checker: Image {img.name!r} got incorrect setting, index = {i!r}, number = {setting!r}.")
                                break
                        else:
                            atlux_settings = '_' + atlux_settings_pat


                full_pattern_name = f"UniV_{texture_type}{palettes_name}{atlux_settings}_{resolution_name}"


                # Sanitize name
                if not img.name.startswith(full_pattern_name):
                    print(f"UniV: Checker: Image {img.name!r} renamed to {full_pattern_name!r}.")
                    img.name = full_pattern_name

                path = cls.get_texture_folder_path() / (full_pattern_name + '.png')

                if tuple(img.size) == (0, 0):
                    print(f"UniV: Checker: Got zero size image, maybe texture was unload.")
                    img = recreate_and_replace(img, *size)

                palette = 'DEFAULT'
                if palettes_name:
                    palette = palettes_name[1:].upper()

                return cls.generate_atlux(full_pattern_name, path, size, *number_settings, palettes=palette, img=img)
            case _:
                print(f"UniV: Checker: Texture with {texture_type!r} name, not support.")
                return None


    def generate_checker_texture(self):
        from mathutils import Color
        pref = prefs()
        self.full_pattern_name = self.get_full_image_name()
        size_x, size_y = pref.glob_size

        match pref.checker_generated_type:
            case 'UV_GRID' | 'COLOR_GRID':
                before = set(bpy.data.images)
                bpy.ops.image.new(
                    name=self.full_pattern_name,
                    width=size_x,
                    height=size_y,
                    alpha=False,
                    generated_type=pref.checker_generated_type)
                return tuple(set(bpy.data.images) - before)[0]
            case 'SIMPLE_GRID':
                path = self.get_path_from_pattern_name()

                tex_name = pref.checker_colors

                col = Color(getattr(utypes.Colors, tex_name))
                small_line_col = Color(getattr(utypes.ColorsSmallLines, tex_name))

                bound_color = (1,1,1)
                if tex_name == 'white':
                    bound_color = (0,0,0)

                return self.generate_simple_grid(self.full_pattern_name, path, (size_x, size_y), col, small_line_col, bound_color)
            case 'GRAVITY':
                path = self.get_path_from_pattern_name()
                color_type = pref.checker_colors

                col1 = Color(getattr(utypes.Colors, color_type))
                col2 = utypes.Colors.dark
                invert = True

                if color_type in ('white', 'black', 'dark', 'brown', 'brown_dark'):
                    invert = False
                    col2 = utypes.Colors.white

                return self.generate_gravity(self.full_pattern_name, path, (size_x, size_y), col1, col2, flip_color=invert)
            case 'ATLUX':
                path = self.get_path_from_pattern_name()
                return self.generate_atlux(self.full_pattern_name, path, (size_x, size_y),
                                           round_offset=prefs().checker_offset,
                                           border_thickness = prefs().checker_thickness,
                                           lines_frequency=prefs().checker_frequency,
                                           palettes=prefs().checker_palettes)
            case _:
                raise NotImplementedError(f'Texture {pref.checker_generated_type} not implement')

    def sanitize_generated_textures(self):
        count = 0

        for obj in bpy.context.selected_objects:
            if not obj.type == 'MESH':
                continue

            for m in obj.modifiers:
                if not isinstance(m, bpy.types.NodesModifier):
                    continue
                if m.name.startswith('UniV Checker'):
                    ng = m.node_group
                    if self.checker_node_group_is_changed(ng):
                        continue

                    gn_mod = utils.GN(m, print_missed_socket=True)
                    if 'Socket_1' in gn_mod:
                        mtl = gn_mod['Socket_1']

                        res = self.sanitize_generated_texture_ex(mtl)
                        if res:
                            count += res
                            obj.update_tag()


            for mtl in getattr(obj.data, 'materials', ()):
                res = self.sanitize_generated_texture_ex(mtl)
                if res:
                    count += res
                    obj.update_tag()

        if count:
            self.update_views()
            bpy.context.view_layer.update()
            self.report({'INFO'}, f"Checker: {count!r} textures was regenerated.")
        return count

    @classmethod
    def sanitize_generated_texture_ex(cls, mtl):
        # if self.material_is_changed(mtl):
        #     continue
        if not isinstance(mtl, bpy.types.Material):
            return 0

        if not getattr(mtl, 'use_nodes', True):
            return 0

        count = 0
        for n in mtl.node_tree.nodes:
            if n.bl_idname == 'ShaderNodeTexImage':
                img = n.image
                if img:
                    if img.name.startswith('UniV_'):
                        # TODO: Check size
                        if img.generated_type == 'BLANK' and not img.is_dirty and img.packed_file is None:
                            # if image not dirty and not have, that's need regenerate
                            path = Path(img.filepath_raw)
                            if not path.exists():
                                if cls.regenerate_texture(img):
                                    print(f"UniV: Checker: Texture {img.name!r} was not saved and was regenerated.")
                                    count += 1
        return count

    @staticmethod
    def generate_simple_grid(name, path, size, col, small_line_col, bound_color, img=None):
        tex = utypes.TexturePatterns.simple_grid(size, col, small_line_col, bound_color)
        if img is None:
            img: bpy.types.Image = bpy.data.images.new(name, width=size[0], height=size[1], alpha=False)

        img.pixels.foreach_set(tex.to_4_channels().data.reshape((-1,)))
        img.filepath_raw = str(path)
        img.update()
        return img

    @staticmethod
    def generate_gravity(name, path, size, color1, color2, img=None, flip_color=True):
        from mathutils import Vector, Matrix, Color
        from ..utypes import TexturePatterns

        from gpu_extras.batch import batch_for_shader
        from .. import draw

        width, height = size

        checker = UMask(width, height)
        checker2_mask = UMask(width, height)

        TexturePatterns.draw_checker(checker, step=128)
        TexturePatterns.draw_checker(checker2_mask, step=64)

        checker1 = checker.mask_to_texture((*color1, 1.0), (*color2, 1.0))

        if flip_color:
            color1 = Color(color1)
            color1.s *= 0.8
            color1.v *= 1.2

            color2 = Color(color2)
            color2.v *= 0.65
        else:
            color1 = Color(color1)
            color1.v *= 0.65

            color2 = Color(color2)
            color2.s *= 0.8
            color2.v *= 1.2


        checker2 = checker.mask_to_texture((*color1, 1.0), (*color2, 1.0))
        colored_texture = checker1.apply_mask(checker2, checker2_mask)

        # Draw Arrows
        arrow_coords_3d = [Vector(co).to_3d() for co in utils.arrow]

        scale_x = 2 / (width // 128)
        scale_y = 2 / (height // 128)
        scale = Vector((scale_x, scale_y))

        arrow_tris_pre = []
        for tris in utils.polyfill_beautify(arrow_coords_3d):
            for idx in tris:
                arrow_tris_pre.append(tuple(arrow_coords_3d[idx].xy*scale))
        arrow_tris_pre = np.array(arrow_tris_pre, np.float32)

        arrow_tris = []
        arrow_tris_color = []

        prev_x_pos = float('-inf')
        for delta in utils.grid_points_ndc(width, height, center=True):
            arrow_tris.append(arrow_tris_pre+np.array(delta, np.float32))

            flip_color = not flip_color
            if delta[0]<prev_x_pos:
                flip_color = not flip_color

            prev_x_pos = delta[0]
            if flip_color:
                arrow_tris_color.extend( [(1, 1, 1, 1)] * len(arrow_tris_pre))
            else:
                arrow_tris_color.extend( [(0, 0, 0, 1)] * len(arrow_tris_pre))

        arrow_tris = np.concatenate(arrow_tris, axis=0)

        tris_color_shader = draw.shaders.SMOOTH_COLOR_2D
        batch_tris = batch_for_shader(tris_color_shader, 'TRIS', {"pos": arrow_tris, 'color': arrow_tris_color})


        offscreen = gpu.types.GPUOffScreen(width * 2, height * 2)

        with offscreen.bind():
            fb = gpu.state.active_framebuffer_get()
            fb.clear(color=(0.0, 0.0, 0.0, 0.0))
            with gpu.matrix.push_pop():
                draw.shaders.blend_set_alpha()
                gpu.matrix.load_matrix(Matrix.Identity(4))
                gpu.matrix.load_projection_matrix(Matrix.Identity(4))

                tris_color_shader.bind()
                batch_tris.draw(tris_color_shader)

        if img is None:
            img: bpy.types.Image = bpy.data.images.new(name, width=size[0], height=size[1], alpha=False)

        arrow_texture = utypes.UTexture.from_frame_buf(width*2, height*2, fb, downscaled=True)
        buf = colored_texture.alpha_over(arrow_texture)

        img.pixels.foreach_set(buf.data.reshape((-1,)))
        img.filepath_raw = str(path)
        img.update()
        return img

    @classmethod
    def generate_atlux(cls, name, path, size, round_offset: int, border_thickness: int, lines_frequency: int, palettes: str, img=None):
        """The idea for this pattern was taken from the following website: https://uvchecker.atlux.one/"""
        from .. import draw
        from ..utypes import Colors

        round_offset = utils.remap(round_offset, 0, 15, 0, 0.5)
        border_thickness = utils.remap(border_thickness, 0, 15, 0, 0.2)

        if round_offset:
            round_offset = max(round_offset, border_thickness)

        batch_texture, shader_texture = UNIV_OT_CheckerGenerator.get_texture_shader()
        draw.shaders.blend_set_alpha()

        # Get checkers data
        width, height = size
        x_blocks = (width // 128)
        y_blocks = (height // 128)
        scale_x = 2 / x_blocks
        scale_y = 2 / y_blocks
        scale = np.array((scale_x, scale_y), dtype=np.float32)

        repeats, unfilled = divmod(x_blocks, 5)
        if not repeats:
            repeats = 1
            unfilled = 0

        if palettes == 'GAMBIT':
            checker_colors = [(*Colors.gray_dark, 1.0), (*Colors.white, 1.0)] * (x_blocks // 2)
        elif palettes == 'RAINBOW':
            first = Color([0.992, 0.357, 0.706])
            second = Color([0.412, 0.69, 1.0])
            checker_colors = [(*col, 1.0) for col in utils.rainbow_between(first, second, x_blocks)]
        else: # palettes in ('DEFAULT', 'GOLDEN'):
            if palettes == 'GOLDEN':
                repeats_colors = [(0.29, 0.22, 0.118, 1.0),
                                  (0.608, 0.42, 0.122, 1.0),
                                  (1.0, 0.945, 0.639, 1.0),
                                  (0.953, 0.78, 0.294, 1.0),
                                  (0.82, 0.612, 0.149, 1.0) ]
            else:
                repeats_colors = [(0.043, 0.365, 0.475, 1.0),
                                  (0.369, 0.839, 0.761, 1.0),
                                  (0.996, 0.929, 0.667, 1.0),
                                  (0.988, 0.561, 0.455, 1.0),
                                  (0.812, 0.173, 0.396, 1.0) ]
                if palettes != 'DEFAULT':
                    print(f"UniV: Checker: Image {img.name!r} got unknown palettes {palettes}, used default.")

            unfilled_colors = [(*Colors.black, 1.0), (*Colors.dark, 1.0), (*Colors.gray, 1.0), (*Colors.white, 1.0)]
            checker_colors = repeats_colors * repeats
            checker_colors += unfilled_colors[:unfilled]

        checker_colors = checker_colors[:x_blocks]
        checker_colors = deque(checker_colors)

        contrast_bw_colors = []
        for col in checker_colors:

            col = Color(col[:3]).from_srgb_to_scene_linear()
            if utils.luminance(col) > 0.5:
                contrast_bw_colors.append((0.05,0.05,0.05,1))
            else:
                contrast_bw_colors.append((0.95,0.95,0.95,1))
        contrast_bw_colors = deque(contrast_bw_colors)
        contrast_bw_colors.rotate(-1)


        # Draw texts
        ibuf = imbuf.new((width, height))
        if hasattr(blf, 'bind_imbuf'):
            with blf.bind_imbuf(0, ibuf, display_name="sRGB"):
                cls.checker_board_atlux(width, height, contrast_bw_colors)
        text = utypes.UTexture.from_ibuf(ibuf).to_gpu_texture()


        # Draw Rounds
        round_rect_tris_pre = utils.round_rect(offset=round_offset, segments=12) * scale
        round_rect_tris = []
        round_rect_tris_color = []

        for i, delta in enumerate(utils.grid_points_ndc(width, height, center=True)):
            round_rect_tris.append(round_rect_tris_pre + np.array(delta, np.float32))
            i = i % x_blocks
            if i == 0:
                checker_colors.rotate(-1)

            color = checker_colors[i]
            round_rect_tris_color.extend( [color] * len(round_rect_tris_pre))
        round_rect_tris = np.concatenate(round_rect_tris, axis=0)

        tris_color_shader = draw.shaders.SMOOTH_COLOR_2D
        batch_round_rect = batch_for_shader(tris_color_shader, 'TRIS', {"pos": round_rect_tris, 'color': round_rect_tris_color})


        # Draw border
        round_rect_border_tris = []
        if border_thickness:
            round_rect_border_pre = utils.round_rect(offset=round_offset, thickness=border_thickness, segments=12) * scale
            for delta in utils.grid_points_ndc(width, height, center=True, is_bottom_top=False):
                round_rect_border_tris.append(round_rect_border_pre + np.array(delta, np.float32))
            round_rect_border_tris = np.concatenate(round_rect_border_tris, axis=0)

        uniform_color_shader = draw.shaders.UNIFORM_COLOR_2D
        round_rect_border_batch = batch_for_shader(uniform_color_shader, 'TRIS', {"pos": round_rect_border_tris})

        # Draw Lines
        lines = utypes.UMask(width, height)
        step = 128
        for i in range(min(4, lines_frequency)):
            step //= 2

        if step != 128:
            utypes.TexturePatterns.draw_lines(lines, step=step)
        lines = lines.mask_to_texture((1,1,1,0.35), (0,0,0,0))
        lines = lines.to_gpu_texture()


        # Shape  ==========
        draw.shaders.blend_set_alpha()
        if not round_offset:
            offscreen = gpu.types.GPUOffScreen(width, height)
            with offscreen.bind():
                fb = gpu.state.active_framebuffer_get()
                fb.clear(color=(0.05, 0.05, 0.05, 1.0))
                with gpu.matrix.push_pop():
                    gpu.matrix.load_matrix(Matrix.Identity(4))
                    gpu.matrix.load_projection_matrix(Matrix.Identity(4))

                    tris_color_shader.bind()
                    batch_round_rect.draw(tris_color_shader)


                    uniform_color_shader.bind()
                    uniform_color_shader.uniform_float("color", (1,1,1,0.3))
                    round_rect_border_batch.draw(uniform_color_shader)

                    # Draw images
                    # Reset matrices -> use normalized device coordinates [-1, 1].
                    shader_texture.uniform_float("viewProjectionMatrix", UNIV_OT_CheckerGenerator.get_normalize_uvs_matrix())
                    shader_texture.uniform_sampler("image", lines)
                    batch_texture.draw(shader_texture)
                    shader_texture.uniform_sampler("image", text)
                    batch_texture.draw(shader_texture)
            buf = utypes.UTexture.from_frame_buf(width, height, fb)

        else:
            # Draw Anti-Aliasing round rects
            offscreen = gpu.types.GPUOffScreen(width*2, height*2)
            with offscreen.bind():
                fb = gpu.state.active_framebuffer_get()
                fb.clear(color=(0.05, 0.05, 0.05, 1.0))
                with gpu.matrix.push_pop():
                    gpu.matrix.load_matrix(Matrix.Identity(4))
                    gpu.matrix.load_projection_matrix(Matrix.Identity(4))

                    tris_color_shader.bind()
                    batch_round_rect.draw(tris_color_shader)

                    uniform_color_shader.bind()
                    uniform_color_shader.uniform_float("color", (1, 1, 1, 0.3))
                    round_rect_border_batch.draw(uniform_color_shader)

                buf = utypes.UTexture.from_frame_buf(width * 2, height * 2, fb, downscaled=True)
            checker_board_texture = buf.to_gpu_texture()

            # Draw contrast lines
            offscreen = gpu.types.GPUOffScreen(width, height)
            with offscreen.bind():
                fb = gpu.state.active_framebuffer_get()
                with gpu.matrix.push_pop():
                    shader_texture.uniform_float("viewProjectionMatrix",
                                                 UNIV_OT_CheckerGenerator.get_normalize_uvs_matrix())
                    shader_texture.uniform_sampler("image", checker_board_texture)
                    batch_texture.draw(shader_texture)

                    shader_texture.uniform_sampler("image", lines)
                    batch_texture.draw(shader_texture)

                    shader_texture.uniform_sampler("image", text)
                    batch_texture.draw(shader_texture)

                buf = utypes.UTexture.from_frame_buf(width, height, fb)

        if img is None:
            img: bpy.types.Image = bpy.data.images.new(name, width=size[0], height=size[1], alpha=False)

        img.pixels.foreach_set(buf.data.reshape((-1,)))
        img.filepath_raw = str(path)
        img.update()
        return img

    @staticmethod
    def checker_board_atlux(width: int, height: int, text_colors, step: int = 128):
        import blf
        mono: int = 0 #  blf_mono_font_render;
        text_size = 32  # hard coded size!

        # Using nullptr will assume the byte buffer has sRGB colorspace, which currently
        # matches the default colorspace of new images.

        utils.blf_size(mono, text_size+5)
        arrow_size_x, arrow_size_y = blf.dimensions(mono, '↑')

        import string
        letters = string.ascii_uppercase
        digits = string.digits[1:] + 'ABCDEF'

        first_char_index: int = 0
        for y in range(0, height, step):
            first_char = letters[first_char_index]

            second_char_index: int = 0
            for i, x in enumerate(range(0, width, step)):
                text_color = text_colors[0]
                text_colors.rotate(-1)

                blf.color(mono, *text_color)
                utils.blf_size(mono, text_size)

                text = first_char + str(i)
                size_x, size_y = blf.dimensions(mono, text)

                # hard coded offset
                pen_x: int = x + ((step // 2) - (size_x // 2))
                pen_y: int = y + ((step // 2) - (size_y // 2))

                blf.position(mono, pen_x, pen_y+25, 0.0)
                blf.draw_buffer(mono, text)

                # hard coded offset
                pen_x: int = x + ((step // 2) - (arrow_size_x // 2))
                pen_y: int = y + ((step // 2) - (arrow_size_y // 2))

                blf.position(mono, pen_x, pen_y - 23, 0.0)
                utils.blf_size(mono, text_size+5)
                blf.draw_buffer(mono, '↑')

                second_char_index = (second_char_index + 1) % len(digits)

            text_colors.rotate(-1)
            first_char_index = (first_char_index + 1) % len(letters)

    def compile_shader(self):
        import gpu
        from gpu_extras.batch import batch_for_shader
        # Drawing the generated texture in 3D space
        #############################################
        vert_out = gpu.types.GPUStageInterfaceInfo("my_interface")
        vert_out.smooth('VEC2', "uvInterp")
        shader_info = gpu.types.GPUShaderCreateInfo()
        shader_info.push_constant('MAT4', "viewProjectionMatrix")
        # shader_info.push_constant('MAT4', "modelMatrix")
        shader_info.sampler(0, 'FLOAT_2D', "image")
        shader_info.vertex_in(0, 'VEC2', "position")
        shader_info.vertex_in(1, 'VEC2', "uv")
        shader_info.vertex_out(vert_out)
        shader_info.fragment_out(0, 'VEC4', "FragColor")
        shader_info.vertex_source(
            "void main()"
            "{"
            "  uvInterp = uv;"
            "  gl_Position = viewProjectionMatrix * vec4(position, 0.0, 1.0);"
            "}"
        )
        shader_info.fragment_source(
            "void main()"
            "{"
            "  FragColor = texture(image, uvInterp);"
            "}"
        )
        self.shader = gpu.shader.create_from_info(shader_info)

        self.batch = batch_for_shader(
            self.shader, 'TRI_FAN',
            {
                "position": (
                    (0.0, 0.0),
                    (1.0, 0.0),
                    (1.0, 1.0),
                    (0.0, 1.0),
                ),
                "uv": ((0, 0), (1, 0), (1, 1), (0, 1)),
            },
        )


class UNIV_OT_CheckerSave(bpy.types.Operator):
    bl_idname = 'wm.univ_checker_save'
    bl_label = 'Checker Save'
    bl_options = {'REGISTER', 'UNDO'}

    # noinspection PyTypeHints
    session_uid: bpy.props.IntProperty(default=-1, options={'HIDDEN'})

    def execute(self, context):
        texture_folder = UNIV_OT_Checker.get_texture_folder_path()
        texture_folder.resolve()

        for img in bpy.data.images:
            if img.session_uid == self.session_uid:
                if img.name.startswith(('UniV_Grid_', 'UniV_ColorGrid_')):
                    self.report({'INFO'}, f"Get blender procedural texture.")
                    return {'CANCELLED'}

                texture_file = Path(img.filepath_raw).resolve()
                if texture_file.parent == texture_folder:
                    img.save()
                    return {'FINISHED'}
                else:
                    self.report({'WARNING'}, f"Incorrect texture path {str(texture_file)}.")
                    return {'CANCELLED'}

        self.report({'WARNING'}, f"Not found texture.")
        return {'FINISHED'}


class UNIV_OT_CheckerUpdate(bpy.types.Operator):
    bl_idname = 'wm.univ_checker_update'
    bl_label = 'Checker Update'
    bl_options = {'REGISTER', 'UNDO'}

    # noinspection PyTypeHints
    session_uid: bpy.props.IntProperty(default=-1, options={'HIDDEN'})

    def execute(self, context):
        texture_folder = UNIV_OT_Checker.get_texture_folder_path()
        texture_folder.resolve()

        for img in bpy.data.images:
            if img.session_uid == self.session_uid:
                if img.name.startswith(('UniV_Grid_', 'UniV_ColorGrid_')):
                    self.report({'INFO'}, f"Get blender procedural texture.")
                    return {'CANCELLED'}

                if UNIV_OT_Checker.regenerate_texture(img):
                    return {'FINISHED'}
                # TODO: Make more information report? instead print

        self.report({'WARNING'}, f"Not found texture.")
        return {'FINISHED'}

from bpy.props import *
class UNIV_OT_CheckerShowFolder(bpy.types.Operator):
    bl_idname = "scene.univ_checker_show_folder"
    bl_label = "Show Folder..."
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        import os
        import platform
        import subprocess
        path = UNIV_OT_Checker.get_texture_folder_path()
        path.resolve()
        if path.exists():
            if platform.system() == 'Windows':
                os.startfile(str(path))
            elif platform.system() == 'Linux':
                subprocess.Popen(["xdg-open", str(path)])
            else:
                subprocess.Popen(["open", str(path)])
        else:
            self.report({'WARNING'}, f"Path {str(path)} not found.")
        return {'FINISHED'}


class UNIV_OT_CheckerGenerator(bpy.types.Operator):
    bl_idname = 'wm.univ_checker_generator'
    bl_label = 'Generate'
    bl_options = {'REGISTER', 'UNDO'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.area: bpy.types.Area | None = None
        self.handler = None
        self.batch: gpu.types.GPUBatch | None = None
        self.shader: gpu.types.GPUShader | None = None

    @staticmethod
    def checker_board_text_v2(width: int, height: int, text_colors, step: int = 128):
        import blf
        mono: int = 0 #  blf_mono_font_render;
        text_size = 32  # hard coded size!

        # Using nullptr will assume the byte buffer has sRGB colorspace, which currently
        # matches the default colorspace of new images.

        utils.blf_size(mono, text_size+5)
        arrow_size_x, arrow_size_y = blf.dimensions(mono, '↑')

        import string
        letters = string.ascii_uppercase
        digits = string.digits[1:] + 'ABCDEF'

        first_char_index: int = 0
        for y in range(0, height, step):
            first_char = letters[first_char_index]

            second_char_index: int = 0
            for i, x in enumerate(range(0, width, step)):
                text_color = text_colors[0]
                text_colors.rotate(-1)

                blf.color(mono, *text_color)
                utils.blf_size(mono, text_size)

                text = first_char + str(i)
                size_x, size_y = blf.dimensions(mono, text)

                # hard coded offset
                pen_x: int = x + ((step // 2) - (size_x // 2))
                pen_y: int = y + ((step // 2) - (size_y // 2))

                blf.position(mono, pen_x, pen_y+25, 0.0)
                blf.draw_buffer(mono, text)

                # hard coded offset
                pen_x: int = x + ((step // 2) - (arrow_size_x // 2))
                pen_y: int = y + ((step // 2) - (arrow_size_y // 2))

                blf.position(mono, pen_x, pen_y - 25, 0.0)
                utils.blf_size(mono, text_size+5)
                blf.draw_buffer(mono, '↑')

                second_char_index = (second_char_index + 1) % len(digits)

            text_colors.rotate(-1)
            first_char_index = (first_char_index + 1) % len(letters)

    def execute(self, context):
        """
        self.area = context.area

        from mathutils import Vector
        from ..utypes import TexturePatterns as pat
        from ..utypes import Colors

        from ..univ_pro import trim
        from .. import draw

        width, height = int(prefs().size_x), int(prefs().size_y)
        self.batch, self.shader = self.get_texture_shader()

        draw.shaders.blend_set_alpha()

        # Create and fill offscreen
        ##########################################

        # Draw checkers
        offscreen = gpu.types.GPUOffScreen(width, height)

        x_blocks = (width // 128)
        y_blocks = (height // 128)
        scale_x = 2 / x_blocks
        scale_y = 2 / y_blocks
        scale = np.array((scale_x, scale_y), dtype=np.float32)

        repeats, unfilled = divmod(x_blocks, 5)
        if not repeats:
            repeats = 1
            unfilled = 0

        repeats_colors = [(0.043, 0.365, 0.475, 1.0),
                          (0.369, 0.839, 0.761, 1.0),
                          (0.996, 0.929, 0.667, 1.0),
                          (0.988, 0.561, 0.455, 1.0),
                          (0.812, 0.173, 0.396, 1.0) ]

        unfilled_colors = [(*Colors.black, 1.0), (*Colors.dark, 1.0), (*Colors.gray, 1.0), (*Colors.white, 1.0)]
        checker_colors = repeats_colors * repeats

        checker_colors += unfilled_colors[:unfilled]
        checker_colors = checker_colors[:x_blocks]

        from collections import deque
        checker_colors = deque(checker_colors)

        contrast_bw_colors = []
        for col in checker_colors:
            if utils.luminance(col[:3]) > 0.7:
                contrast_bw_colors.append((0,0,0,1))
            else:
                contrast_bw_colors.append((1,1,1,1))
        contrast_bw_colors = deque(contrast_bw_colors)



        ibuf = imbuf.new((width, height))

        # font_id = blf.load("/path/to/font.ttf")
        font_id = 0
        with blf.bind_imbuf(font_id, ibuf, display_name="sRGB"):
            self.checker_board_text_v2(width, height, contrast_bw_colors)
        text = utypes.UTexture.from_ibuf(ibuf).to_gpu_texture()

        # Draw Arrows
        round_offset = 0.#2
        round_rect_tris_pre = utils.round_rect(offset=round_offset, segments=12) * scale

        round_rect_tris = []
        round_rect_tris_color = []

        for i, delta in enumerate(utils.grid_points_ndc(width, height, center=True)):
            round_rect_tris.append(round_rect_tris_pre + np.array(delta, np.float32))
            i = i % x_blocks
            if i == 0:
                checker_colors.rotate(-1)

            color = checker_colors[i]
            round_rect_tris_color.extend( [color] * len(round_rect_tris_pre))
        round_rect_tris = np.concatenate(round_rect_tris, axis=0)

        tris_color_shader = gpu.shader.from_builtin('SMOOTH_COLOR')
        batch_round_rect = batch_for_shader(tris_color_shader, 'TRIS', {"pos": round_rect_tris, 'color': round_rect_tris_color})


        # Draw border
        round_rect_border_tris = []
        round_rect_border_pre = utils.round_rect(offset=round_offset, thickness=0.02, segments=12) * scale
        for delta in utils.grid_points_ndc(width, height, center=True, is_bottom_top=False):
            round_rect_border_tris.append(round_rect_border_pre + np.array(delta, np.float32))
        round_rect_border_tris = np.concatenate(round_rect_border_tris, axis=0)

        uniform_color_shader = draw.shaders.UNIFORM_COLOR
        round_rect_border_batch = batch_for_shader(uniform_color_shader, 'TRIS', {"pos": round_rect_border_tris})

        lines = utypes.UMask(width, height)
        pat.draw_lines(lines, step=16)
        lines = lines.mask_to_texture((1,1,1,0.4), (0,0,0,0))
        lines = lines.to_gpu_texture()


        # Shape  ==========
        draw.shaders.blend_set_alpha()
        with offscreen.bind():
            fb = gpu.state.active_framebuffer_get()
            fb.clear(color=(0.05, 0.05, 0.05, 1.0))
            with gpu.matrix.push_pop():
                gpu.matrix.load_matrix(Matrix.Identity(4))
                gpu.matrix.load_projection_matrix(Matrix.Identity(4))

                # Reset matrices -> use normalized device coordinates [-1, 1].
                tris_color_shader.bind()
                batch_round_rect.draw(tris_color_shader)


                uniform_color_shader.bind()
                uniform_color_shader.uniform_float("color", (1,1,1,0.5))
                round_rect_border_batch.draw(uniform_color_shader)


                self.shader.uniform_float("viewProjectionMatrix", self.get_normalize_uvs_matrix())
                self.shader.uniform_sampler("image", lines)
                self.batch.draw(self.shader)
                self.shader.uniform_sampler("image", text)
                self.batch.draw(self.shader)


        
        resolution_name: str = utils.glob_resolutions_to_name()

        buf = UNIV_OT_Checker.generate_atlux(width, height, round_offset=0., lines_frequency=3)

        img = bpy.data.images.new(
            f"UniV_TestGenerate_{resolution_name}",
            width=buf.width,
            height=buf.height,
            alpha=False,
            float_buffer=False,
            # is_data=True
        )

        img.pixels.foreach_set(buf.data.reshape((-1,)))
        img.update()

        area = bpy.context.area
        if area and area.type == 'IMAGE_EDITOR':
            space_data = area.spaces.active
            if space_data:
                space_data.image = img

        bpy.data.materials["Material"].node_tree.nodes["Image Texture"].image = img

        context.area.tag_redraw()
        """
        return {'FINISHED'}

    @staticmethod
    def get_texture_shader() -> tuple[gpu.types.GPUBatch, gpu.types.GPUShader]:
        import gpu
        from gpu_extras.batch import batch_for_shader
        # Drawing the generated texture in 3D space
        #############################################
        vert_out = gpu.types.GPUStageInterfaceInfo("my_interface")
        vert_out.smooth('VEC2', "uvInterp")
        shader_info = gpu.types.GPUShaderCreateInfo()
        shader_info.push_constant('MAT4', "viewProjectionMatrix")
        # shader_info.push_constant('MAT4', "modelMatrix")
        shader_info.sampler(0, 'FLOAT_2D', "image")
        shader_info.vertex_in(0, 'VEC2', "position")
        shader_info.vertex_in(1, 'VEC2', "uv")
        shader_info.vertex_out(vert_out)
        shader_info.fragment_out(0, 'VEC4', "FragColor")
        shader_info.vertex_source(
            "void main()"
            "{"
            "  uvInterp = uv;"
            "  gl_Position = viewProjectionMatrix * vec4(position, 0.0, 1.0);"
            "}"
        )
        shader_info.fragment_source(
            "void main()"
            "{"
            "  FragColor = texture(image, uvInterp);"
            "}"
        )
        shader = gpu.shader.create_from_info(shader_info)

        batch = batch_for_shader(
            shader, 'TRI_FAN',
            {
                "position": (
                    (0.0, 0.0),
                    (1.0, 0.0),
                    (1.0, 1.0),
                    (0.0, 1.0),
                ),
                "uv": ((0, 0), (1, 0), (1, 1), (0, 1)),
            },
        )
        return batch, shader


    @staticmethod
    def get_normalize_uvs_matrix():
        """matrix maps x and y coordinates from [0, 1] to [-1, 1]"""
        from mathutils import Matrix
        matrix = Matrix.Identity(4)
        matrix.col[3][0] = -1
        matrix.col[3][1] = -1
        matrix[0][0] = 2
        matrix[1][1] = 2
        return matrix