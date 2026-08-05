from ..pipeline import GenericScenario
from ..props import MainProps
from ..utils import eprint
from ..uc_entry import uc


class Scenario(GenericScenario):

    main_props : MainProps


    def run(self):
        self.send_tip('if you are getting unstable results when orienting islands, make sure the UV map has no N-gons')
        uc.packer.send_log(uc.LogType.STATUS, "Orienting islands...")

        orient_to3d_props = self.main_props.orient_to3d_props

        oriented_islands = self.cx.selected_islands.orient_to_3d_space(
            uc.Axis(orient_to3d_props.prim_3d_axis),
            uc.Axis(orient_to3d_props.prim_uv_axis),
            uc.Axis(orient_to3d_props.sec_3d_axis),
            uc.Axis(orient_to3d_props.sec_uv_axis),
            uc.CoordSpace(orient_to3d_props.axes_space),
            orient_to3d_props.prim_sec_bias)

        uc.packer.send_out_islands(oriented_islands, send_transform=True)
        uc.packer.send_log(uc.LogType.STATUS, "Done. Islands oriented: {}".format(len(oriented_islands)))
        return uc.RetCode.SUCCESS
