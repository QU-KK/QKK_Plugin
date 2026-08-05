
from .param import EngineParamTarget
from .box_utils import BoxRenderInfo
from .types import JsonMessageCode
from .uc_entry import uc

import json


class JsonBoxRenderInfoPayload(EngineParamTarget):

    box_info_array : list[BoxRenderInfo]


class JsonUtils:

    @staticmethod
    def send_json(code, payload):
        uc.packer.send_json(json.dumps({'code': code, 'payload': payload}))

    @classmethod
    def send_box_render_info(cls, box_info_array):
        cls.send_json(code=JsonMessageCode.BOX_RENDER_INFO, payload=JsonBoxRenderInfoPayload(box_info_array=box_info_array).to_engine_param())
