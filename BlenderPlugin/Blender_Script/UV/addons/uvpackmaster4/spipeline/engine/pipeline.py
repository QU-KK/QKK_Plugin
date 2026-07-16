
from .utils import eprint, flag_islands
from .geom import IslandWrapper
from .uc_entry import uc


def extract_param(param_type, value, default_value=None):
    if value is None:
        return default_value
        
    return param_type(value)


class Struct(object):
    def __init__(self, data):
        for name, value in data.items():
            setattr(self, name, self._wrap(value))

    def _wrap_str(self, value):
        return value

    def _wrap(self, value):
        if isinstance(value, (tuple, list, set, frozenset)): 
            return type(value)([self._wrap(v) for v in value])
        elif isinstance(value, dict):
            return Struct(value)
        elif isinstance(value, str):
            return self._wrap_str(value)
        else:
            return value


class ScenarioConfig:

    def __init__(self, params):
        self.skip_topology_parsing = params['__skip_topology_parsing']
        self.disable_immediate_uv_update = params['__disable_immediate_uv_update']
        self.disable_tips = params['__disable_tips']


class GenericScenario:

    TIP_COLOR = 'green'
    TIP_HEADER = '<t color="{}">TIP:</t>'.format(TIP_COLOR)
    TOPOLOGY_PARSED = False

    VERTEX_BASED_TIP_SENT = False
    VERTEX_BASED_TIP_MSG_ARRAY = [
        "you are checking island similarity using a vertex-based similarity mode",
        "if you are getting inconsistent results using that mode, running 'Merge UVs By Distance' with a small distance may solve the problem"
    ]

    pack_ratio = 1.0

    def __init__(self, cx, **kwargs):
        self.cx = cx
        self.int_iparams_manager = uc.packer.int_iparams_manager()
        self.str_iparams_manager = uc.packer.str_iparams_manager()
        self.config = ScenarioConfig(self.cx.params)

        from .utils import gather_annotations
        scenario_annotations = gather_annotations(type(self))

        from .param import EngineParamUtils
        for ann_name, ann in scenario_annotations.items():
            val = kwargs[ann_name] if ann_name in kwargs.keys() else EngineParamUtils.from_param(ann, self.cx.params[ann_name])
            setattr(self, ann_name, val)

            if hasattr(val, 'engine_init'):
                val.engine_init()

    def handle_invalid_islands(self, status_msg, error_msg, invalid_islands):
        flag_islands(self.cx.input_islands, invalid_islands)
        uc.packer.send_log(uc.LogType.STATUS, status_msg)

        if error_msg:
            uc.packer.send_log(uc.LogType.ERROR, "{} (check the selected islands)".format(error_msg))

        return uc.RetCode.INVALID_ISLANDS

    def islands_for_topology_parsing(self):
        return self.cx.input_islands

    def parse_topology(self):
        if type(self).TOPOLOGY_PARSED:
            return

        islands_for_parsing = self.islands_for_topology_parsing()
        uc.packer.parse_island_topology(islands_for_parsing)

        type(self).TOPOLOGY_PARSED = True

    def send_tip(self, tip_msg):
        if self.config.disable_tips:
            return
        uc.packer.send_log(uc.LogType.INFO, "{} {}".format(self.TIP_HEADER, tip_msg), flags=uc.LogFlags.PARSE)

    def send_vertex_based_tip(self, matching_mode, suffix=None):
        from .types import UvpmSimilarityMode
        if not UvpmSimilarityMode.is_vertex_based(matching_mode):
            return

        cls = type(self)
        if cls.VERTEX_BASED_TIP_SENT:
            return
        
        cls.VERTEX_BASED_TIP_SENT = True
        suffix = ' ({})'.format(suffix) if suffix is not None else ''
        assert len(self.VERTEX_BASED_TIP_MSG_ARRAY) == 2

        self.send_tip(self.VERTEX_BASED_TIP_MSG_ARRAY[0] + suffix)
        self.send_tip(self.VERTEX_BASED_TIP_MSG_ARRAY[1])

    def init(self):
        if not self.config.skip_topology_parsing:
            self.parse_topology()

    def exec(self):
        ret_code = uc.RetCode.NOT_SET
        
        try:
            self.init()
            self.pre_run()
            ret_code = self.run()
            ret_code = self.post_run(ret_code)

        except uc.InputError as err:
            err_str = str(err)
            if err_str:
                uc.packer.send_log(uc.LogType.ERROR, err_str)
            uc.packer.send_log(uc.LogType.STATUS, 'Invalid operation input')
            return uc.RetCode.INVALID_INPUT

        except uc.InvalidTopologyExtendedError as err:
            return self.handle_invalid_islands(
                "Topology error",
                "Islands with invalid topology encountered",
                err.cause.invalid_islands)

        except uc.InvalidIslandsExtendedError as err:
            return self.handle_invalid_islands(
                "Invalid islands",
                "Invalid islands encountered",
                err.cause.invalid_islands)

        except uc.InvalidIslandsError as err:
            return self.handle_invalid_islands(
                "Invalid islands",
                None,
                err.cause.invalid_islands)

        except uc.OpCancelledException:
            return uc.RetCode.CANCELLED

        return ret_code

    def pre_run(self):
        pass
    
    def post_run(self, ret_code):
        return ret_code


from .geom import uc_array_bbox
from .props import MainProps, AppStateBase, EngineScenePropsBase
from .tdensity import TDensityValue
from .island_params import TexelDensityShowIParamInfo


class TexelDensityScenario(GenericScenario):

    app_state : AppStateBase # Must be declared as first
    e_scene_props : EngineScenePropsBase # Must be declared before main_props
    main_props : MainProps


    def init(self):
        super().init()
        self.show_iparam_desc = self.str_iparams_manager.iparam_desc(TexelDensityShowIParamInfo.SCRIPT_NAME)

        self.tdensity_to_set = self.main_props.tdensity_to_set
        self.tex_size = self.main_props.get_pixel_margin_tex_size(self.app_state)

    def calc_tdensity(self, island):
        return IslandWrapper(island, scale_length=self.app_state.scale_length).calc_tdensity(self.tex_size)
    
    def set_tdensity(self, island, tdensity_value, pivot=None):
        return IslandWrapper(island, scale_length=self.app_state.scale_length).set_tdensity(self.tex_size, tdensity_value, pivot=pivot).get()
    
    def set_tdensity_to_islands(self, input, tdensity_value):
        output = uc.IslandSet()
        pivot = uc_array_bbox(input).center()

        for island in input:
            o_island = island
            td_final = None

            try:
                o_island = self.set_tdensity(island, tdensity_value, pivot=pivot)
                td_final = tdensity_value
                
            except ValueError:
                td_final = TDensityValue.undefined()

            o_island.set_iparam(self.show_iparam_desc, td_final.to_s())
            output.append(o_island)

        return output
    