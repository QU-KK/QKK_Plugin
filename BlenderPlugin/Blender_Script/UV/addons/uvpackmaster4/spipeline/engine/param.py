
import typing
from collections.abc import Iterable

from .utils import eprint, ShadowedCollectionProperty


class EngineParamUtils:

    ENUM_PARAM_TYPE = str

    @classmethod
    def from_param(cls, annotation, param):
        origin = typing.get_origin(annotation)
        val = None

        if origin == list:
            elem_type = typing.get_args(annotation)[0]

            val = list()
            for elem in param:
                val.append(cls.from_param(elem_type, elem))

        elif origin == tuple:
            val = tuple(cls.from_param(t, param[idx]) for idx, t in enumerate(typing.get_args(annotation)))

        elif origin == ShadowedCollectionProperty:
            elem_type = typing.get_args(annotation)[0]

            val = ShadowedCollectionProperty(elem_type=elem_type)
            for elem in param:
                val.append(cls.from_param(elem_type, elem))

        else:
            if hasattr(annotation, 'from_engine_param'):
                val = annotation.from_engine_param(param)
            else:
                val = annotation(param)

        assert val != None
        return val
    
    @classmethod
    def init_attr(cls, annotation):
        origin = typing.get_origin(annotation)

        if origin == list:
            return list()

        elif origin == tuple:
            return tuple(t() for t in typing.get_args(annotation))
        
        elif origin == ShadowedCollectionProperty:
            elem_type = typing.get_args(annotation)[0]
            return ShadowedCollectionProperty(elem_type=elem_type)

        else:
            return annotation()
        
        assert False
    
    @classmethod
    def copy_attr(cls, annotation, attr):
        origin = typing.get_origin(annotation)
        val = None

        if origin == list:
            elem_type = typing.get_args(annotation)[0]

            val = list()
            for elem in attr:
                val.append(cls.copy_attr(elem_type, elem))

        elif origin == tuple:
            val = tuple(cls.copy_attr(t, attr[idx]) for idx, t in enumerate(typing.get_args(annotation)))

        else:
            if hasattr(annotation, 'copy_from'):
                val = annotation()
                val.copy_from(attr)
            else:
                val = annotation(attr)

        assert val != None
        return val

    @classmethod
    def to_param(cls, obj):
        t = type(obj)

        if t in {bool, int, float, str}:
            return obj

        if isinstance(obj, Iterable):
            return [cls.to_param(elem) for elem in obj]
        
        assert hasattr(obj, 'to_engine_param')
        return obj.to_engine_param()
    
    @classmethod
    def to_params(cls, obj, annotations, params):
        for ann_name in annotations.keys():
            if not hasattr(obj, ann_name):
                continue

            params[ann_name] = cls.to_param(getattr(obj, ann_name))
        

class EngineParamTarget:

    def __init__(self, *args, **kwargs):
        try:
            from ...app_iface import PropertyGroup
            if isinstance(self, PropertyGroup):
                return super().__init__(*args, **kwargs)
        
        except ImportError:
            pass
        
        for attr_name, annotation in self.__annotations__.items():
            val = None

            if attr_name in kwargs:
                val = kwargs[attr_name]

            else:
                val = EngineParamUtils.init_attr(annotation)

            assert val is not None
            setattr(self, attr_name, val)

    @classmethod
    def from_engine_param(cls, param):
        ann = cls.__annotations__
        obj = cls()

        for attr_name, annotation in ann.items():
            setattr(obj, attr_name, EngineParamUtils.from_param(annotation, param[attr_name]))

        return obj

    def to_engine_param(self):
        return {attr_name: EngineParamUtils.to_param(getattr(self, attr_name)) for attr_name in self.__annotations__.keys()}
    
    def copy_from(self, other):
        for attr_name, annotation in self.__annotations__.items():
            setattr(self, attr_name, EngineParamUtils.copy_attr(annotation, getattr(other, attr_name)))
