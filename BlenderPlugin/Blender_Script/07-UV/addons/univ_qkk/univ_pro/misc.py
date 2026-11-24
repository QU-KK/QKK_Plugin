# SPDX-FileCopyrightText: 2026 Oxicid
# SPDX-License-Identifier: GPL-3.0-or-later


import re
import bpy
import json
from pathlib import Path

from .. import utils
from ..preferences import univ_settings


POLIIGON_PHYSICAL_SIZES: dict[int, tuple[float, float] | None] | None = None


class UNIV_OT_TexelDensityFromTexture(bpy.types.Operator):
    bl_idname = "uv.univ_texel_density_from_texture"
    bl_label = 'TD From Texture'
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = "Extracts dimensions from texture name or metadata.\n\n" \
        "Name_30cm_Albedo → 0.3m\n" \
        "Name_2.5Mx2.5M_Albedo → 2.5 x 2.5 m\n" \
        "Supported units: mm, cm, m, km, in, ft, yd, mi\n\n" \
        "Quixel Megascans textures are supported if the original \n" \
        "filenames are intact and the texture path contains the corresponding JSON file. \n\n" \
        "Poliigon textures are supported if the naming convention with the texture ID is preserved." \


    def execute(self, context):
        area = bpy.context.area
        if not area or area.type != 'IMAGE_EDITOR':
            self.report({'WARNING'}, 'Active area must be UV type')
            return {'CANCELLED'}

        space_data = area.spaces.active
        if not (space_data and space_data.image):
            self.report({'WARNING'}, 'Not found active image')
            return {'CANCELLED'}

        img = space_data.image
        image_width, image_height = img.size
        if not image_height:
            self.report({'WARNING'}, 'Active image not valid')
            return {'CANCELLED'}

        if int(univ_settings().size_x) != image_width or int(univ_settings().size_y) != image_height:
            self.report({'INFO'}, 'Resolution of active texture and resolution of texture in '
                                  'Texel Density do not match. The resolution from Texel Density is used.')

        size = self.get_physical_size_from_name(img.name)
        if size:
            self.update_texel_from_size(size)
            return {'FINISHED'}

        if img.name.startswith('Poliigon_'):
            size = self.get_physical_size_poligon(img.name)
            if size:
                self.update_texel_from_size(size)
            return {'FINISHED'}

        if not img.packed_file:
            path = Path(img.filepath)
            size = self.get_physical_size_quixel(path)
            if size:
                self.update_texel_from_size(size)
                return {'FINISHED'}
        self.report({'WARNING'}, 'Physical size not found in name or metadata')

        return {'FINISHED'}

    @staticmethod
    def update_texel_from_size(size):
        x, y = size
        x_td = int(univ_settings().size_x) / x
        y_td = int(univ_settings().size_y) / y
        univ_settings().texel_density = (x_td + y_td) * 0.5
        utils.update_univ_panels()

    @staticmethod
    def get_physical_size_from_name(name: str):
        pattern = rf'_(\d+(?:\.\d+)?){utils.UNITS}(?:\s*[xх×]\s*(\d+(?:\.\d+)?){utils.UNITS}?)?'
        matches = re.finditer(pattern, name, flags=re.IGNORECASE)
        for m in matches:
            g = m.groups()
            if g[2]:
                unit2 = g[3] if g[3] else g[1]
                x_size = utils.unit_conversion(float(g[0]), g[1], 'm')
                y_size = utils.unit_conversion(float(g[2]), unit2, 'm')
            else:
                x_size = y_size = utils.unit_conversion(float(g[0]), g[1], 'm')
            return x_size, y_size
        return None

    @staticmethod
    def get_physical_size_quixel(image_path: Path):
        if not image_path.exists():
            return None

        prefix = image_path.stem.split('_')[0]
        if not prefix:
            return None

        quixel_json = image_path.parent / f'{prefix}.json'
        if not quixel_json.exists():
            quixel_json = image_path.parent / f'{prefix}0.json'
            if not quixel_json.exists():
                return None

        with open(quixel_json) as f:
            js = json.load(f)
            for key in js:
                if key != 'physicalSize':
                    continue
                size_info = js[key]

                if size_info is None:
                    return False

                if 'x' in size_info:
                    splitted = size_info.split('x')
                    if len(splitted) != 2:
                        break

                    try:
                        return float(splitted[0]), float(splitted[1])
                    except:  # noqa
                        return False
                break
        return False

    def get_physical_size_poligon(self, name: str):
        import requests  # type: ignore[import-untyped]
        match_poliigon_id = re.search(r'_(\d{4,})_', name)
        if not match_poliigon_id:
            self.report({'WARNING'}, 'Not found id from poliigon texture')
            return None

        try:
            poliigon_id: int = int(match_poliigon_id.group(1))

            if POLIIGON_PHYSICAL_SIZES is None:
                self.load_poliigon_physical_size_cache()

            if poliigon_id in POLIIGON_PHYSICAL_SIZES:
                ret = POLIIGON_PHYSICAL_SIZES[poliigon_id]
                if not ret:
                    self.report({'WARNING'}, "Sizes not found")
                return ret

            # TODO: Fix toolbox.get_context
            # p = __import__("poliigon-addon-blender")
            # self = p.toolbox.cTB
            # asset_data = self._asset_index.get_asset(7787)
            # asset_data.specifications.get("physical_size_cm", {})
            # TODO: Implement cache system (and save them in txt)
            url = f"https://www.poliigon.com/texture/.../{poliigon_id}"
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
            response = requests.get(url, headers, timeout=(3, 10), stream=True)

            if response.status_code == 404:
                self.report({'WARNING'}, f'Not found url {url!r} for get texel density from poliigon metadata')
                return None

            # Example: <p data-v-8f651ff6="">2.50 m  x 2.50 m</p>
            pattern = rf'>(\d+(?:\.\d+)?)\s*{utils.UNITS}\s*x\s*(\d+(?:\.\d+)?)\s*{utils.UNITS}<'
            match = re.search(pattern, response.text)
            if match:
                width = match.group(1)
                width_unit = match.group(2)
                height = match.group(3)
                height_unit = match.group(4)
                x_size = utils.unit_conversion(float(width), width_unit, 'm')
                y_size = utils.unit_conversion(float(height), height_unit, 'm')
                size = x_size, y_size
                POLIIGON_PHYSICAL_SIZES[poliigon_id] = size
                return size
            else:
                POLIIGON_PHYSICAL_SIZES[poliigon_id] = None
                self.report({'WARNING'}, "Sizes not found")
        except requests.exceptions.ConnectionError:
            self.report({'WARNING'}, 'Not found internet connection for get texel density from id')
        except requests.exceptions.Timeout:
            self.report({'WARNING'}, 'Server response timeout, try again')

    @staticmethod
    def load_poliigon_physical_size_cache():
        json_path = Path(__file__).parent / 'poliigon_physical_size_cache.json'
        global POLIIGON_PHYSICAL_SIZES
        if json_path.exists():
            with open(json_path, 'r', encoding='utf-8') as f:
                try:
                    POLIIGON_PHYSICAL_SIZES = {int(k): v for k, v in json.load(f).items()}
                except (ValueError, json.JSONDecodeError):
                    POLIIGON_PHYSICAL_SIZES = {}
        else:
            POLIIGON_PHYSICAL_SIZES = {}

    @staticmethod
    def store_poliigon_physical_size_cache():
        json_path = Path(__file__).parent / 'poliigon_physical_size_cache.json'
        global POLIIGON_PHYSICAL_SIZES
        if POLIIGON_PHYSICAL_SIZES:
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(POLIIGON_PHYSICAL_SIZES, f, sort_keys=True, indent=4, separators=(',', ': '))  # noqa


class TexelDensity_NameExtract_Test:
    @staticmethod
    def extract_meters_from_name_test():
        texts = ('wood_2mx4m_albedo.png',
                 'brick_1m_diffuse.jpg',
                 'tile_100cmx200cm_normal.png',
                 'metal_0.5mx1m_roughness.tga',
                 'fabric_50kmx50m_albedo.tif',
                 'ground_5.5cmx6.2_albedo.tif',
                 'marble_ric_5in_albedo.tif',
                 'bronze_rich_5ft_albedo.tif',
                 'gold_6ftx6ft_albedo.tif',
                 'paper_dd__8_6mix6mi_albedo.tif')

        for name in texts:
            UNIV_OT_TexelDensityFromTexture.get_physical_size_from_name(name)
