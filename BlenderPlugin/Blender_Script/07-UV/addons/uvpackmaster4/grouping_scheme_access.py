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


from .app_iface import *


class GroupingSchemeDescriptorMetadata:

    def __init__(self, panel_name):
        self.panel_name = panel_name


class GroupingSchemeAccess:

    __DESC_METADATA = None
    
    @classmethod
    def DESC_METADATA(cls):
        if cls.__DESC_METADATA is None:
            from .spipeline.panels.pack_panels import UVPM4_PT_GroupingPack, UVPM4_PT_LockGroups, UVPM4_PT_StackGroups, UVPM4_PT_TrackGroups, UVPM4_PT_NormalizeScale
            from .spipeline.panels.grouping_editor_panels import UVPM4_PT_GroupingEditor

            cls.__DESC_METADATA = {
                        'packing' : GroupingSchemeDescriptorMetadata(panel_name=UVPM4_PT_GroupingPack.bl_label),
                        'editor' : GroupingSchemeDescriptorMetadata(panel_name=UVPM4_PT_GroupingEditor.bl_label),
                        'lock_group' : GroupingSchemeDescriptorMetadata(panel_name=UVPM4_PT_LockGroups.bl_label),
                        'stack_group' : GroupingSchemeDescriptorMetadata(panel_name=UVPM4_PT_StackGroups.bl_label),
                        'track_group' : GroupingSchemeDescriptorMetadata(panel_name=UVPM4_PT_TrackGroups.bl_label),
                        'norm_group' : GroupingSchemeDescriptorMetadata(panel_name=UVPM4_PT_NormalizeScale.bl_label)
                    }

        return cls.__DESC_METADATA

    def __init__(self, context, desc_id=None, desc=None, ui_drawing=False):
        self.context = context
        self.ui_drawing = ui_drawing
        self.g_schemes = get_scene_props(self.context).grouping_schemes

        if desc:
            self.desc_id = None
            self.desc = desc
        else:
            if not desc_id:
                raise RuntimeError('GroupingSchemeAccess: desc id not set')

            self.desc_id = desc_id
            self.desc = getattr(get_main_props(context).grouping_scheme_access_descriptors, desc_id)

        self.init_active_members()

    def init_active_members(self):
        self.active_g_scheme = self.init_active_g_scheme()

        if not self.ui_drawing and self.active_g_scheme is not None:
            self.active_g_scheme.init_defaults()

        self.active_group = self.init_active_group()
        self.active_target_box = self.init_active_target_box()

    def get_g_schemes_enum_items(self):
        items = []
        enumerated_g_schemes = list(enumerate(self.g_schemes))
        enumerated_g_schemes.sort(key=lambda i: i[1].name)

        for idx, g_scheme in enumerated_g_schemes:
            items.append((str(g_scheme.uuid), g_scheme.name, "", idx))
        return items

    @staticmethod
    def get_g_schemes_enum_items_callback(property_self, context):
        gs_access = GroupingSchemeAccess(context, ui_drawing=True, desc_id='editor')
        return gs_access.get_g_schemes_enum_items()

    def create_g_scheme(self, set_active=True):
        new_g_scheme = self.g_schemes.add()
        new_g_scheme.init_defaults()
        new_g_scheme.add_group_with_target_box()
        if set_active:
            self.set_active_g_scheme_uuid(new_g_scheme.uuid)

        return new_g_scheme
    
    def get_active_g_scheme_uuid(self):
        return  self.desc.active_g_scheme_uuid

    def get_active_g_scheme_idx(self):
        active_g_scheme_uuid = self.get_active_g_scheme_uuid()

        for idx, g_scheme in enumerate(self.g_schemes):
            if active_g_scheme_uuid == g_scheme.uuid:
                return idx

        return -1

    def init_active_g_scheme(self):
        active_g_scheme_idx = self.get_active_g_scheme_idx()
        active_g_scheme = None

        if active_g_scheme_idx >= 0:
            active_g_scheme = self.g_schemes[active_g_scheme_idx]

        return active_g_scheme
    
    def get_g_schemes(self):
        return self.g_schemes
    
    def get_active_g_scheme_safe(self):
        if self.active_g_scheme is None:
            desc_metadata = self.DESC_METADATA()[self.desc_id]
            raise RuntimeError("Grouping scheme requested but it was not found - select a scheme in the '{}' panel".format(desc_metadata.panel_name))
        
        return self.active_g_scheme

    def init_active_group(self):
        if self.active_g_scheme is None:
            return None

        return self.active_g_scheme.get_active_group()

    def init_active_target_box(self):
        if self.active_group is None:
            return None

        return self.active_group.get_active_target_box()

    def set_active_g_scheme_uuid(self, uuid):
        self.desc.active_g_scheme_uuid = uuid
        self.init_active_members()

    def layout_init_desc(self, layout):
        layout.context_pointer_set('uvpm4_gs_access_desc', self.desc)
    
    @staticmethod
    def get_desc_id_from_obj(obj):
        if hasattr(obj, 'GS_ACCESS_DESC_ID') and obj.GS_ACCESS_DESC_ID:
            return str(obj.GS_ACCESS_DESC_ID)
        
        if hasattr(obj, 'gs_access_desc_id') and obj.gs_access_desc_id:
            return str(obj.gs_access_desc_id)
        
        if hasattr(obj, 'grouping_config') and obj.grouping_config:
            return obj.grouping_config.g_scheme_access_desc_id
        
        if hasattr(obj, 'get_mode'):
            mode = obj.get_mode()
            if mode:
                return mode.grouping_config.g_scheme_access_desc_id

        return None
    
    @staticmethod
    def get_desc_from_context(context):
        if hasattr(context, 'uvpm4_gs_access_desc'):
            return context.uvpm4_gs_access_desc
        
        return None
    
    @classmethod
    def get_desc_kwargs(cls, obj, context):
        return {'desc_id': cls.get_desc_id_from_obj(obj), 'desc': cls.get_desc_from_context(context)}


import mathutils  

class GroupByPropAccess:

    def __init__(self, g_scheme, prop_id):
        self.g_scheme = g_scheme
        self.prop_id = prop_id
        self.group_by_prop = dict()

        for group in self.g_scheme.groups:
            prop_val = self.__value_preprocess(getattr(group, self.prop_id))

            if prop_val in self.group_by_prop:
                self.group_by_prop[prop_val].append(group)
            else:
                self.group_by_prop[prop_val] = [group]

    @staticmethod
    def __value_preprocess(value):
        if type(value) in {mathutils.Color, mathutils.Vector}:
            return tuple(value[0:3])
        
        return value

    def get(self, prop_val):
        groups, new = self.get_all(prop_val)
        return groups[-1], new

    def get_all(self, prop_val):
        prop_val = self.__value_preprocess(prop_val)
        groups = self.group_by_prop.get(prop_val)
        new = False

        if groups is None:
            kwargs = { self.prop_id: prop_val }
            groups = [self.g_scheme.add_group_with_target_box(**kwargs)]

            self.group_by_prop[prop_val] = groups
            new = True

        return groups, new


class GroupByNameAccess(GroupByPropAccess):

    def __init__(self, g_scheme):
        super().__init__(g_scheme, prop_id='name')


class GroupByColorAccess(GroupByPropAccess):

    def __init__(self, g_scheme):
        super().__init__(g_scheme, prop_id='color')


class GSAccessDescIdAttrMixin:

    gs_access_desc_id : StringProperty(name='', description='', default='')
