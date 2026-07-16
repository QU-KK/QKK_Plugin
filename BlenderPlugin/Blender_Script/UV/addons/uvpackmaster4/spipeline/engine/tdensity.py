
from .param import EngineParamTarget, EngineParamUtils
from .types import EnumValue, enum_decorator
from .utils import rgb_to_rgba

class TDensityValue(EngineParamTarget):

    S_PRECISION = 2
    S_FORMAT_STR = '.{}f'.format(S_PRECISION)
    ZERO_STR = '0.0'

    view_val : float
    s_val : str

    @classmethod
    def from_f(cls, f):
        o = cls()
        o.set_f(f)
        return o
    
    @classmethod
    def from_s(cls, s):
        o = cls()
        o.set_s(s)
        return o
    
    @classmethod
    def undefined(cls):
        o = cls()
        o.set_f(0.0)
        return o
    
    def is_defined(self):
        eps = 1.0e-5
        return self.to_f() > eps
    
    def set_s(self, s):
        self.set_f(float(s) if s != '' else 0.0)

    def set_f(self, f):
        self.view_val = f
        self.s_val = format(f, self.S_FORMAT_STR)

    def to_f(self):
        f = float(self.to_s())
        assert f >= 0.0
        return f

    def to_s(self):
        self.sync()
        if self.s_val == '':
            return self.ZERO_STR

        return self.s_val
    
    def to_string(self):
        if not self.is_defined():
            return 'X'
        
        return self.to_s()
    
    def __str__(self):
        self.to_string()

    def sync(self):
        self.set_f(self.view_val)


@enum_decorator
class TDensityTierValueMode:

    DIRECT_VALUE = EnumValue('0', 'Direct Value', 'Specify a TD value directly using the properly below')
    USE_TIER = EnumValue('1', 'Use Tier', 'Value will be determined using a TD tier')


from .id_collection import IdCollectionAccessDescriptor

class TDensityTierValue(EngineParamTarget):

    _TIER_ACCESS = None

    mode : EngineParamUtils.ENUM_PARAM_TYPE
    val : TDensityValue
    tier_access_desc : IdCollectionAccessDescriptor

    error_suffix = ''

    @classmethod
    def init_tier_access(cls, tiers):
        from .id_collection import IdCollectionAccess
        cls._TIER_ACCESS = IdCollectionAccess(None, desc=IdCollectionAccessDescriptor(), coll=tiers)

    @property
    def use_tier(self):
        return self.mode == TDensityTierValueMode.USE_TIER
    
    @use_tier.setter
    def use_tier(self, val):
        self.mode = TDensityTierValueMode.USE_TIER if val else TDensityTierValueMode.DIRECT_VALUE

    @classmethod
    def from_s(cls, s):
        o = cls()

        from .utils import is_uuid_strict
        if is_uuid_strict(s):
            tier = cls._get_tier_access().get_item_by_uuid(s)

            if tier:
                o.use_tier = True
                o.tier_access_desc.active_item_uuid = s

            else:
                o.use_tier = False
                o.val = TDensityValue.undefined()

        else:
            o.use_tier = False
            o.val = TDensityValue.from_s(s)

        return o

    @classmethod
    def _get_tier_access(cls):
        assert cls._TIER_ACCESS is not None
        return cls._TIER_ACCESS
    
    def set_error_suffix(self, suffix):
        self.error_suffix = suffix

    def _get_tier(self):
        try:
            return self._get_tier_access().get_item_by_uuid_safe(self.tier_access_desc.active_item_uuid)
        
        except AttributeError:
            raise RuntimeError('TDensity tier not selected' + (' ({})'.format(self.error_suffix) if self.error_suffix else ''))

    def _get_val(self):
        return self._get_tier().val if self.use_tier else self.val
    
    def color(self):
        return rgb_to_rgba(self._get_tier().color) if self.use_tier else (1, 1, 1, 1)
    
    def to_s(self):
        return self._get_val().to_s()

    def to_f(self):
        return self._get_val().to_f()

    def is_defined(self):
        return self._get_val().is_defined()

    def to_s_exact(self):
        if self.use_tier:
            return self._get_tier().uuid
        
        return self.val.to_s()

    def to_string(self):
        return self._get_val().to_string()
    
    def __str__(self):
        self.to_string()


class TDensityTier(EngineParamTarget):

    val : TDensityValue
    uuid : str


class TDensityTierIdCollection(EngineParamTarget):

    items : list[TDensityTier]
