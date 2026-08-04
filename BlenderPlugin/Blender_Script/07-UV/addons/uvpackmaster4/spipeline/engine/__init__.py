
from .scenario import get_scenario_class
from .uc_entry import uc


def run(cx):
    Scenario = get_scenario_class(cx.params['__scenario_id'])

    try:
        return Scenario(cx).exec()

    except RuntimeError as err:
        err_str = str(err)
        if err_str:
            uc.packer.send_log(uc.LogType.ERROR, err_str)
        uc.packer.send_log(uc.LogType.STATUS, 'Error')
        return uc.RetCode.INVALID_INPUT # MUSTDO: return ERROR code
