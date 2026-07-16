
import struct
from .utils import rgb_to_rgba, UTIL_COLOR_ARRAY
from .tdensity import TDensityTierValue


class IParamInfo:

    VALUE_PROP_ID = None
    VALUE_PROP_TEXT = None
    
    DEFAULT_VALUE_TEXT = None
    TEXT_SUFFIX = None

    VCOLOR_CHANNEL_NAME_PREFIX_BASE = '__uvpm4'
    VCOLOR_CHANNEL_NAME_PREFIX_VERSION = '_v1_'
    VCOLOR_CHANNEL_NAME_PREFIX = VCOLOR_CHANNEL_NAME_PREFIX_BASE + VCOLOR_CHANNEL_NAME_PREFIX_VERSION

    INDEX = -1
    value_prop_obj = None

    @classmethod
    def value_property_s(cls, context):
        if not cls.VALUE_PROP_ID:
            return None

        from ...utils import PropertyWrapper, get_main_props
        return PropertyWrapper(get_main_props(context), cls.VALUE_PROP_ID)

    @classmethod
    def pre_set_convert(cls, value):
        return value
    
    @classmethod
    def post_get_convert(cls, value):
        return value

    def __init__(self, script_name, label, default_value):
        self.label = label
        self.script_name = script_name
        self.default_value = self.PARAM_TYPE(default_value)

    def value_property(self, context):
        if not self.VALUE_PROP_ID:
            return None
        
        from ...utils import get_main_props, PropertyWrapper
        value_prop_obj = self.value_prop_obj if self.value_prop_obj else get_main_props(context)
        return PropertyWrapper(value_prop_obj, self.VALUE_PROP_ID, text=self.VALUE_PROP_TEXT)
    
    def value_property_get(self, context):
        return self.value_property(context).get()
    
    def get_vcolor_chname(self):
        return self.VCOLOR_CHANNEL_NAME_PREFIX + self.script_name

    def index(self):
        if self.INDEX < 0:
            raise ValueError()

        return self.INDEX

    def param_to_text(self, value):
        if self.DEFAULT_VALUE_TEXT is not None and (value == self.default_value):
            return self.DEFAULT_VALUE_TEXT

        return str(self.TEXT_TYPE(value)) + (self.TEXT_SUFFIX if self.TEXT_SUFFIX is not None else '')

    def param_to_color(self, value):
        return (1,1,1,1)
    
    def get_iparam_value(self, p_context, vcolor_layer, face):
        from ...app_iface import MeshWrapper
        return MeshWrapper.get_vcolor(self, vcolor_layer, face)
    

class MinMaxIParamInfo(IParamInfo):

    def __init__(self, script_name, label, min_value, max_value, default_value=None):
        if default_value is None:
            default_value = self.PARAM_TYPE(min_value)

        super().__init__(script_name, label, default_value)

        self.min_value = self.PARAM_TYPE(min_value)
        self.max_value = self.PARAM_TYPE(max_value)

    def serialize_min_value(self):
        return struct.pack(self.PARAM_TYPE_MARK, self.min_value)
    
    def serialize_max_value(self):
        return struct.pack(self.PARAM_TYPE_MARK, self.max_value)
    
    def serialize_default_value(self):
        return struct.pack(self.PARAM_TYPE_MARK, self.default_value)


class IntIParamInfo(MinMaxIParamInfo):

    PARAM_TYPE = int
    PARAM_TYPE_MARK = 'i'
    TEXT_TYPE = PARAM_TYPE


class StrIParamInfo(IParamInfo):

    PARAM_TYPE = str
    PARAM_TYPE_MARK = 'i'
    TEXT_TYPE = PARAM_TYPE

    ATTR_ENCODING = 'ascii'

    @classmethod
    def pre_set_convert(cls, value : str):
        return value.encode(cls.ATTR_ENCODING)
    
    @classmethod
    def post_get_convert(cls, value : bytes):
        return value.decode(cls.ATTR_ENCODING)

    def serialize_min_value(self):
        return bytes()
    
    def serialize_max_value(self):
        return bytes()
    
    def serialize_default_value(self):
        from ...connection import encode_string
        return encode_string(self.default_value)
    
    def get_iparam_value(self, p_context, vcolor_layer, face):
        from ...app_iface import MeshWrapper
        return p_context.string_id_map.get_id(MeshWrapper.get_vcolor(self, vcolor_layer, face))


class StaticStrIParamInfo(StrIParamInfo):

    def __init__(self):
        super().__init__(
            script_name=self.SCRIPT_NAME,
            label=self.LABEL,
            default_value=self.DEFAULT_VALUE
        )


class StaticIntIParamInfo(IntIParamInfo):

    def __init__(self):
        default_value = self.DEFAULT_VALUE if hasattr(self, 'DEFAULT_VALUE') else None

        super().__init__(
            script_name=self.SCRIPT_NAME,
            label=self.LABEL,
            min_value=self.MIN_VALUE,
            max_value=self.MAX_VALUE,
            default_value=default_value
        )

    @classmethod
    def enabled_property_s(cls, context):
        from ...utils import PropertyWrapper, get_main_props
        return PropertyWrapper(get_main_props(context), cls.ENABLED_PROP_ID)


class RotStepIParamInfo(StaticIntIParamInfo):

    LABEL = 'Rotation Step'
    SCRIPT_NAME = 'rotation_step'

    USE_GLOBAL_VALUE = -1

    MIN_VALUE = USE_GLOBAL_VALUE
    MAX_VALUE = 180

    DEFAULT_VALUE_TEXT = 'G'
    TEXT_SUFFIX = 'd'
    VALUE_PROP_ID = 'island_rot_step'
    ENABLED_PROP_ID = 'island_rot_step_enable'


class TexelDensityIParamInfo(StaticStrIParamInfo):

    DEFAULT_VALUE = ''

    def param_to_text(self, value):
        return TDensityTierValue.from_s(value).to_string()
    
    def param_to_color(self, value):
        return TDensityTierValue.from_s(value).color()
    
    def value_property_get(self, context):
        prop = self.value_property(context).get()
        return prop.to_s_exact()


class TexelDensityPackingIParamInfo(TexelDensityIParamInfo):

    LABEL = 'Is.TD'
    SCRIPT_NAME = 'tdensity_packing'

    DEFAULT_VALUE = ''

    VALUE_PROP_TEXT = 'Is.TD (Packing)' 
    VALUE_PROP_ID = 'island_tdensity_packing'
    ENABLED_PROP_ID = 'island_tdensity_set_before_pack'


class TexelDensityShowIParamInfo(TexelDensityIParamInfo):

    LABEL = 'Texel Density'
    SCRIPT_NAME = 'tdensity_show'


class NormalizeMultiplierIParamInfo(StaticIntIParamInfo):

    LABEL = 'Scale Multiplier'
    SCRIPT_NAME = 'normalize_multiplier'

    MIN_VALUE = 10
    MAX_VALUE = 1000
    DEFAULT_VALUE = 100

    TEXT_SUFFIX = '%'
    VALUE_PROP_ID = 'island_normalize_multiplier'


class GroupIParamInfoGeneric(StaticIntIParamInfo):

    GROUP_COLORS = UTIL_COLOR_ARRAY

    def param_to_color(self, value):
        return rgb_to_rgba(self.GROUP_COLORS[int(value) % len(self.GROUP_COLORS)])


class AlignPriorityIParamInfo(GroupIParamInfoGeneric):

    LABEL = 'Align Priority'
    SCRIPT_NAME = 'align_priority'

    MIN_VALUE = 0
    MAX_VALUE = 100
    DEFAULT_VALUE = MIN_VALUE
    
    VALUE_PROP_ID = 'align_priority'
    ENABLED_PROP_ID = 'align_priority_enable'


class SplitOffsetIParamInfo(StaticIntIParamInfo):

    LABEL = 'Split Offset'

    MAX_VALUE = 10000
    MIN_VALUE = -MAX_VALUE
    DEFAULT_VALUE = MIN_VALUE


class SplitOffsetXIParamInfo(SplitOffsetIParamInfo):

    SCRIPT_NAME = 'split_offset_x'


class SplitOffsetYIParamInfo(SplitOffsetIParamInfo):

    SCRIPT_NAME = 'split_offset_y'
