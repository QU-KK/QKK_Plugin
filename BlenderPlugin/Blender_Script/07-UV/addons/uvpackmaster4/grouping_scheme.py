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

import uuid

from .group_map import GROUPING_METHOD_METADATA

from .box import Box, mark_boxes_dirty
from .box_utils import disable_box_rendering
from .utils import unique_name, PropertyWrapper
from .spipeline.engine.types import GroupLayoutMode
from .spipeline.engine.g_scheme import GroupingScheme
from .island_params import IParamSerializer, VColorIParamSerializer
from .spipeline.engine.island_params import IntIParamInfo
from .grouping import UVPM4_GroupingOptions, GroupingOptionsMixin
from .group import UVPM4_GroupInfo
from .grouping_scheme_access import GroupingSchemeAccess, GSAccessDescIdAttrMixin
from .spipeline.engine.labels import Labels
from .pgroup import standalone_property_group
from .operator_generic import UVPM4_OT_GenericHandler
from .app_iface import *


class GroupMapSerializer(IParamSerializer):
    def __init__(self, g_scheme):
        super().__init__(g_scheme.get_iparam_info())
        assert (g_scheme.group_map is not None)
        self.group_map = g_scheme.group_map

    def get_iparam_value(self, p_obj_idx, p_obj, face):
        return self.group_map.get_map(p_obj, face.index)


class GroupingSchemeSerializer(VColorIParamSerializer):

    def __init__(self, g_scheme):
        super().__init__(g_scheme.get_iparam_info())
        assert (g_scheme.group_map is None)
        self.g_scheme = g_scheme
    
    def get_iparam_value(self, p_obj_idx, p_obj, face):
        return self.g_scheme.get_iparam_value(self.vcolor_layers[p_obj_idx], face)
    

def _update_g_scheme_name(self, context):
    gs_access = GroupingSchemeAccess(context, desc_id='editor')
    g_schemes = gs_access.get_g_schemes()

    orig_name = self.name

    from .utils import format_name
    name = format_name(self.name)

    if name == '':
        name = UVPM4_GroupingScheme.DEFAULT_GROUPING_SCHEME_NAME

    name = unique_name(name, g_schemes, self)
    if orig_name != name:
        self.name = name


@standalone_property_group
class UVPM4_GroupingSchemeAccessDescriptor:

    active_g_scheme_uuid : StringProperty(default='', update=disable_box_rendering)

@standalone_property_group
class UVPM4_GroupingSchemeAccessDescriptorContainer:

    packing : PointerProperty(type=UVPM4_GroupingSchemeAccessDescriptor)
    editor : PointerProperty(type=UVPM4_GroupingSchemeAccessDescriptor)
    lock_group : PointerProperty(type=UVPM4_GroupingSchemeAccessDescriptor)
    stack_group : PointerProperty(type=UVPM4_GroupingSchemeAccessDescriptor)
    track_group : PointerProperty(type=UVPM4_GroupingSchemeAccessDescriptor)
    norm_group : PointerProperty(type=UVPM4_GroupingSchemeAccessDescriptor)


@standalone_property_group
class UVPM4_GroupingScheme(GroupingScheme):

    DEFAULT_GROUPING_SCHEME_NAME = 'Scheme'

    name : StringProperty(name="name", default="", update=_update_g_scheme_name)
    uuid : StringProperty(name="uuid", default="")
    groups : CollectionProperty(type=UVPM4_GroupInfo)
    active_group_idx : IntProperty(name="", default=0, update=mark_boxes_dirty)
    options : PointerProperty(type=UVPM4_GroupingOptions)
        
    def __init__(self):
        super(type(self), self).__init__()
        self.init_defaults()

    def copy_from(self, other):
        super(type(self), self).copy_from(other)
        self.init_defaults()

    @staticmethod
    def uuid_is_valid(uuid_to_test):
        try:
            uuid_obj = uuid.UUID(uuid_to_test, version=4)
        except ValueError:
            return False
        return uuid_obj.hex == uuid_to_test

    @staticmethod
    def uuid_generate():
        return uuid.uuid4().hex

    def init_defaults(self):
        if self.name == '':
            self.name = self.DEFAULT_GROUPING_SCHEME_NAME

        if self.uuid == '':
            self.uuid = self.uuid_generate()

        self.group_by_num = dict()
        self.group_map = None
        self.iparam_info = None
        self.next_group_num = UVPM4_GroupInfo.DEFAULT_GROUP_NUM

        for group in self.groups:
            self.__add_group_to_dictionaries(group)

    def regenerate_uuid(self):
        self.uuid = self.uuid_generate()

    def copy(self):
        out = UVPM4_GroupingScheme.SA()
        out.copy_from(self)
        return out

    def group_count(self):
        return len(self.groups)
    
    def dynamic_tiles_validate_fail_msg(self, group):
        if self.dynamic_tiles_enabled(group) and not GroupLayoutMode.supports_dynamic_tiles(self.options.group_layout_mode):
            return "'{}' is not supported with '{}' set to '{}'".format(
                PropertyWrapper(group, 'dynamic_tiles').get_name(),
                PropertyWrapper(self.options, 'group_layout_mode').get_name(),
                GroupLayoutMode.item_by_value(self.options.group_layout_mode).name)
        
        return None
    
    def group_validate_groups_to_tiles(self, group):
        def raise_error(msg):
            raise RuntimeError("Group '{}': {}".format(group.name, msg))
        
        msg = self.dynamic_tiles_validate_fail_msg(group)
        if msg is not None:
            raise_error(msg)
    
    def validate_groups_to_tiles(self, pack_op_type):
        self.options.validate_groups_to_tiles(pack_op_type)

        for group in self.groups:
            self.group_validate_groups_to_tiles(group)

        msg = self.complementary_group_validate_fail_msg()
        if msg is not None:
            GroupingOptionsMixin.raise_grouping_error(msg)
    
    def complementary_group_validate_fail_msg(self):
        if not self.options.base.last_group_complementary:
            return None

        valid_policies = None

        if valid_policies and self.options.tdensity_policy not in valid_policies:
            return "'{}' requires '{}' set to {}".format(
                Labels.LAST_GROUP_COMPLEMENTARY_NAME,
                PropertyWrapper(self.options, 'tdensity_policy').get_name(),
                ' or '.join("'" + policy.name + "'" for policy in valid_policies)
            )

        if len(self.groups) <= 1:
            return "'{}' requires at least two groups in the scheme".format(
                Labels.LAST_GROUP_COMPLEMENTARY_NAME
                )

        if self.options.base.dynamic_tiles_all:
            return "'{}' is not supported with '{}' enabled".format(
                Labels.LAST_GROUP_COMPLEMENTARY_NAME,
                PropertyWrapper(self.options.base, 'dynamic_tiles_all').get_name()
                )
        
        return None

    def complementary_group_is_active(self):
        active_group = self.get_active_group()
        if active_group is None:
            return False
        return self.is_complementary_group(active_group)
    
    def groups_to_tiles_target_boxes_not_editable_msg(self, group):
        if self.dynamic_tiles_enabled(group):
            return "'Dynamic Tiles' enabled"
        
        if self.is_complementary_group(group):
            return 'Group is complementary'
        
        return None

    def get_group_by_num(self, g_num):
        group = self.group_by_num.get(g_num)
        return group
    
    def get_iparam_value(self, vcolor_layer, face):
        group_num = MeshWrapper.get_vcolor(self.get_iparam_info(), vcolor_layer, face)
        group = self.get_group_by_num(group_num)
        if group is None:
            group_num = UVPM4_GroupInfo.DEFAULT_GROUP_NUM

        return group_num

    def get_default_group(self):
        default_group = self.get_group_by_num(UVPM4_GroupInfo.DEFAULT_GROUP_NUM)

        if default_group is None:
            default_group = self.add_group_with_target_box(g_num=UVPM4_GroupInfo.DEFAULT_GROUP_NUM)

        return default_group

    def __add_group_to_dictionaries(self, group):
        if self.next_group_num <= group.num:
            self.next_group_num = group.num + 1

        self.group_by_num[group.num] = group

    def add_group(self, name=UVPM4_GroupInfo.DEFAULT_GROUP_NAME, g_num=None):
        if g_num is None:
            g_num = self.next_group_num

        if name == UVPM4_GroupInfo.DEFAULT_GROUP_NAME:
            name = UVPM4_GroupInfo.get_default_group_name(g_num)

        new_group = UVPM4_GroupInfo.SA(name, g_num)
        return self.add_group_internal(new_group)

    def add_group_with_target_box(self, name=UVPM4_GroupInfo.DEFAULT_GROUP_NAME, g_num=None, **kwargs):
        new_group = self.add_group(name, g_num)

        for key, value in kwargs.items():
            setattr(new_group, key, value)

        self.add_target_box(new_group)

        return new_group

    def add_group_internal(self, new_group):
        assert new_group.num >= UVPM4_GroupInfo.MIN_GROUP_NUM
        if new_group.num > UVPM4_GroupInfo.MAX_GROUP_NUM:
            raise RuntimeError('Max group limit reached')

        added_group = self.groups.add()
        added_group.copy_from(new_group)
        
        self.__add_group_to_dictionaries(added_group)
        self.active_group_idx = len(self.groups)-1
        return added_group

    def group_to_text(self, g_num):
        group = self.get_group_by_num(g_num)

        if group is None:
            raise RuntimeError('Group not found')

        return group.name

    def group_to_color(self, g_num):
        group = self.get_group_by_num(g_num)

        if group is None:
            raise RuntimeError('Group not found')

        return group.color

    def remove_group(self, group_idx):
        group_to_remove = self.groups[group_idx]

        if group_to_remove.is_default():
            raise RuntimeError("Cannot remove the default group")

        del self.group_by_num[group_to_remove.num]

        self.groups.remove(group_idx)
        self.active_group_idx = min(self.active_group_idx, len(self.groups)-1)

    def box_intersects_group_boxes(self, box_to_check):
        for group in self.groups:
            if self.is_complementary_group(group):
                continue
            
            for box in group.target_boxes:
                if box.intersects(box_to_check):
                    return True

        return False

    def add_target_box(self, target_group):
        tile_num_x = 0
        tile_num_y = 0

        if len(target_group.target_boxes) > 0:
            min_corner = target_group.target_boxes[-1].min_corner
            tile_num_x = int(min_corner[0]) + 1
            tile_num_y = int(min_corner[1])

        while True:
            new_box = Box.unit_box().tile(tile_num_x, tile_num_y)

            if not self.box_intersects_group_boxes(new_box):
                target_group.add_target_box(new_box)
                break

            tile_num_x += 1


    def init_group_map(self, p_context, g_method, skip_default_group=False):
        map_type = GROUPING_METHOD_METADATA.get(g_method).group_map_t
        if map_type is None:
            raise RuntimeError('Unexpected grouping method encountered')
        
        if skip_default_group:
            def_group = self.add_group_with_target_box()
            assert def_group.num == UVPM4_GroupInfo.DEFAULT_GROUP_NUM

        self.group_map = map_type(self, p_context)
        return self.group_map

    def get_iparam_info(self):
        if self.iparam_info is not None:
            return self.iparam_info
        
        self.iparam_info = IntIParamInfo(
            script_name='g_scheme_{}'.format(self.uuid),
            label=self.group_map.iparam_label() if self.group_map is not None else self.name,
            min_value=UVPM4_GroupInfo.MIN_GROUP_NUM,
            max_value=UVPM4_GroupInfo.MAX_GROUP_NUM
        )

        return self.iparam_info
    
    def get_iparam_serializer(self):
        if self.group_map is not None:
            return GroupMapSerializer(self)
        
        return GroupingSchemeSerializer(self)

    def get_active_group(self):
        try:
            return self.groups[self.active_group_idx]
        except IndexError:
            return None
    
    def to_engine_param(self):
        param = super(type(self), self).to_engine_param()
        param['iparam_name'] = self.get_iparam_info().script_name

        return param

    def is_valid(self):
        if self.name.strip() == '':
            return False

        if not self.uuid_is_valid(self.uuid):
            return False

        if len(self.groups) == 0:
            return False

        if self.active_group_idx not in range(len(self.groups)):
            return False

        def_group_found = False
        g_number_set = set()

        for group in self.groups:
            if group.name.strip() == '':
                return False

            if group.is_default():
                if def_group_found:
                    return False
                def_group_found = True

            if len(group.target_boxes) == 0:
                return False

            if group.active_target_box_idx not in range(len(group.target_boxes)):
                return False

            g_number_set.add(group.num)

        if not def_group_found:
            return False

        if len(g_number_set) != len(self.groups):
            return False

        return True


class TargetGroupingSchemeMixin:

    target_scheme_action : EnumProperty(name="Action", items=[("NEW", "Create A New Scheme", "Create A New Scheme", 0),
                                                      ("EXTEND", "Apply To An Existing Scheme", "Apply To An Existing Scheme", 1)])
    target_scheme_name : StringProperty(name="Name", default=UVPM4_GroupingScheme.DEFAULT_GROUPING_SCHEME_NAME)
    target_scheme_uuid : EnumProperty(name="Grouping Schemes", items=GroupingSchemeAccess.get_g_schemes_enum_items_callback)

    def create_new_g_scheme(self):
        return self.target_scheme_action == "NEW"

    def get_target_g_scheme(self):
        create_new_g_scheme = self.create_new_g_scheme()

        if not create_new_g_scheme and len(self.gs_access.get_g_schemes()) == 0:
            raise RuntimeError('No grouping scheme in the blend file found')

        if create_new_g_scheme:
            self.gs_access.create_g_scheme()
            self.gs_access.active_g_scheme.name = self.target_scheme_name
        else:
            self.gs_access.set_active_g_scheme_uuid(self.target_scheme_uuid)

        return self.gs_access.active_g_scheme
    
    def invoke(self, context, event):
        self.target_scheme_name = self.target_scheme_name_impl(context)
        return super().invoke(context, event)
    
    def props_dialog_width(self):
        return 400

    def draw(self, context):
        self.gs_access = GroupingSchemeAccess(context, ui_drawing=True, desc_id=GroupingSchemeAccess.get_desc_id_from_obj(self))
        create_new_g_scheme = self.create_new_g_scheme()

        layout = self.layout
        col = layout.column(align=True)
        col.prop(self, "target_scheme_action", text="")

        box = col.box()
        row = box.row(align=True)

        if create_new_g_scheme:
            split = row.split(factor=0.4, align=True)
            split.label(text="New Scheme Name:")
            row = split.row(align=True)
            row.prop(self, "target_scheme_name", text="")
        else:
            if len(self.gs_access.get_g_schemes()) == 0:
                row.label(text='WARNING: no grouping scheme in the blend file found.')
            else:
                split = row.split(factor=0.4, align=True)
                split.label(text="Apply To Scheme:")
                row = split.row(align=True)
                row.prop(self, "target_scheme_uuid", text="")

        self.draw_impl(context, col)

    def draw_impl(self, context):
        pass


class UVPM4_OT_GroupingSchemeOperatorGeneric(UVPM4_OT_GenericHandler):

    bl_options = {'INTERNAL', 'UNDO'}

    def execute(self, context):
        self.gs_access = GroupingSchemeAccess(context, desc_id=GroupingSchemeAccess.get_desc_id_from_obj(self), desc=GroupingSchemeAccess.get_desc_from_context(context))
        return super().execute(context)
            


class UVPM4_OT_NewGroupingScheme(UVPM4_OT_GroupingSchemeOperatorGeneric, GSAccessDescIdAttrMixin):

    bl_idname = "uvpackmaster4.new_grouping_scheme"
    bl_label = "New Grouping Scheme"
    bl_description = "Add a new grouping scheme"

    def execute_impl(self, context):
        self.gs_access.create_g_scheme()
        return {'FINISHED'}


class UVPM4_OT_RemoveGroupingScheme(UVPM4_OT_GroupingSchemeOperatorGeneric, GSAccessDescIdAttrMixin):

    bl_idname = "uvpackmaster4.remove_grouping_scheme"
    bl_label = "Remove"
    bl_description = "Remove the active grouping scheme"

    def execute_impl(self, context):
        g_schemes = self.gs_access.get_g_schemes()
        active_idx = self.gs_access.get_active_g_scheme_idx()

        if active_idx < 0:
            return {'CANCELLED'}

        g_schemes.remove(active_idx)
        new_idx = min(active_idx, len(g_schemes)-1)
        self.gs_access.set_active_g_scheme_uuid(g_schemes[new_idx].uuid if new_idx >=0 else '')

        return {'FINISHED'}


class UVPM4_OT_NewGroupInfo(UVPM4_OT_GroupingSchemeOperatorGeneric, GSAccessDescIdAttrMixin):

    bl_idname = "uvpackmaster4.new_group_info"
    bl_label = "New Item"
    bl_description = 'Add a group to the active grouping scheme'

    def execute_impl(self, context):
        if self.gs_access.active_g_scheme is None:
            return {'CANCELLED'}

        new_group = self.gs_access.active_g_scheme.add_group_with_target_box()
        mark_boxes_dirty(self, context)
        return {'FINISHED'}


class UVPM4_OT_RemoveGroupInfo(UVPM4_OT_GroupingSchemeOperatorGeneric, GSAccessDescIdAttrMixin):

    bl_idname = "uvpackmaster4.remove_group_info"
    bl_label = "Remove"
    bl_description = 'Remove the active group from the scheme'

    def execute_impl(self, context):
        if self.gs_access.active_g_scheme is None:
            return {'CANCELLED'}

        self.gs_access.active_g_scheme.remove_group(self.gs_access.active_g_scheme.active_group_idx)
        mark_boxes_dirty(self, context)
        return {'FINISHED'}


class UVPM4_OT_MoveGroupInfo(UVPM4_OT_GroupingSchemeOperatorGeneric, GSAccessDescIdAttrMixin):
    bl_idname = "uvpackmaster4.move_group_info"
    bl_label = "Move"
    bl_description = "Move the active group up/down in the list"

    direction : EnumProperty(items=[("UP", "Up", "", 0), ("DOWN", "Down", "", 1)])

    def execute_impl(self, context):
        if self.gs_access.active_g_scheme is None:
            return {'CANCELLED'}

        old_idx = self.gs_access.active_g_scheme.active_group_idx
        new_idx = old_idx
        if self.direction == "UP":
            if old_idx > 0:
                new_idx = old_idx - 1
        else:
            if old_idx < len(self.gs_access.active_g_scheme.groups) - 1:
                new_idx = old_idx + 1
        self.gs_access.active_g_scheme.groups.move(old_idx, new_idx)
        self.gs_access.active_g_scheme.active_group_idx = new_idx
        return {'FINISHED'}


class UVPM4_OT_NewTargetBox(UVPM4_OT_GroupingSchemeOperatorGeneric, GSAccessDescIdAttrMixin):

    bl_idname = "uvpackmaster4.new_target_box"
    bl_label = "New Item"
    bl_description = 'Add a new target box to the active group'

    def execute_impl(self, context):
        if self.gs_access.active_g_scheme is None:
            return {'CANCELLED'}
        if self.gs_access.active_group is None:
            return {'CANCELLED'}

        self.gs_access.active_g_scheme.add_target_box(self.gs_access.active_group)

        mark_boxes_dirty(self, context)
        return {'FINISHED'}


class UVPM4_OT_RemoveTargetBox(UVPM4_OT_GroupingSchemeOperatorGeneric, GSAccessDescIdAttrMixin):

    bl_idname = "uvpackmaster4.remove_target_box"
    bl_label = "Remove"
    bl_description = 'Remove the active target box'

    def execute_impl(self, context):
        if self.gs_access.active_group is None:
            return {'CANCELLED'}

        self.gs_access.active_group.remove_target_box(self.gs_access.active_group.active_target_box_idx)

        mark_boxes_dirty(self, context)
        return {'FINISHED'}


class UVPM4_OT_MoveTargetBox(UVPM4_OT_GroupingSchemeOperatorGeneric, GSAccessDescIdAttrMixin):
    bl_idname = "uvpackmaster4.move_target_box"
    bl_label = "Move"
    bl_description = "Move the active box up/down in the list"

    direction : EnumProperty(items=[("UP", "Up", "", 0), ("DOWN", "Down", "", 1)])

    def execute_impl(self, context):
        if self.gs_access.active_group is None:
            return {'CANCELLED'}

        old_idx = self.gs_access.active_group.active_target_box_idx
        new_idx = old_idx
        if self.direction == "UP":
            if old_idx > 0:
                new_idx = old_idx - 1
        else:
            if old_idx < len(self.gs_access.active_group.target_boxes) - 1:
                new_idx = old_idx + 1
        self.gs_access.active_group.target_boxes.move(old_idx, new_idx)
        self.gs_access.active_group.active_target_box_idx = new_idx
        return {'FINISHED'}
