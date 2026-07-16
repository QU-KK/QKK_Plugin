
from .geom.box import Box
from .param import EngineParamTarget


MAIN_TARGET_BOX_COLOR = (1, 1, 0, 1)


class BoxRenderInfo(EngineParamTarget):

    glob_idx : int
    box : Box
    color : tuple[float, float, float, float]
    outline_color : tuple[float, float, float, float]
    text : str
    text_raw : str
    text_line_num : int
    z_coord : float

    def __init__(self, glob_idx=0, box=None, color=(0.0, 0.0, 0.0, 1.0), text='', text_line_num=0, z_coord=0.0):
        self.glob_idx = glob_idx
        self.box = box
        self.color = color
        self.outline_color = color

        self.text = text
        self.text_raw = text

        self.text_line_num = text_line_num
        self.z_coord = z_coord
