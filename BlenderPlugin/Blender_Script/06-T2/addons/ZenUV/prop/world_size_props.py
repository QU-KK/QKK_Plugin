# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####

# Copyright 2023, Alex Zhornyak

import bpy

from ZenUV.ops.transform_sys.transform_utils.tr_utils import TransformSysOpsProps


class ZuvWorldSizeUtils:

    @classmethod
    def getActiveImage(cls, context: bpy.types.Context) -> bpy.types.Image:
        from ZenUV.ops.trimsheets.trimsheet_utils import ZuvTrimsheetUtils
        p_image = ZuvTrimsheetUtils.getSpaceDataImage(context)
        if p_image is not None:
            return p_image

        if hasattr(context, 'area') and context.area is not None and context.area.type != 'IMAGE_EDITOR':
            if context.active_object is not None:
                p_act_mat = context.active_object.active_material
                if p_act_mat is not None:
                    if p_act_mat.zen_uv.world_size_image is not None:
                        return p_act_mat.zen_uv.world_size_image

                    if p_act_mat.use_nodes:
                        # Priority for Base Color Texture
                        try:
                            principled = next(n for n in p_act_mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
                            base_color = principled.inputs['Base Color']
                            link = base_color.links[0]
                            link_node = link.from_node
                            return link_node.image
                        except Exception:
                            pass

        return None

    uv_world_size_prop = bpy.props.FloatProperty(
        name='UV World Size',
        description="Value of UV world size in given units",
        min=0.0,
        default=1.0
    )


class ZUV_WorldSizeImageProps(bpy.types.PropertyGroup):
    size: ZuvWorldSizeUtils.uv_world_size_prop
    units: TransformSysOpsProps.get_units_enum()


class ZUV_WorldSizeItem(ZUV_WorldSizeImageProps):
    regex: bpy.props.StringProperty(
        name="RegEx",
        description="Regular expression that will be used for automatic set of UV world size",
        default=""
    )


class ZUV_WorldSizeAddonProps(bpy.types.PropertyGroup):
    world_size_items: bpy.props.CollectionProperty(type=ZUV_WorldSizeItem)
    world_size_items_index: bpy.props.IntProperty(
        name='Active UV World Size Index',
        description='Active index of the current uv world size item',
        default=-1,
        min=-1
    )
    world_size_presets_expanded: bpy.props.BoolProperty(
        name="UV World Size Presets",
        description="Expand-collapse UV world size presets",
        default=False
    )
