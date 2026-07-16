
import importlib


def get_scenario_class(scenario_id):
    scenario = importlib.import_module(".{}".format(scenario_id), package=__package__)

    return scenario.Scenario

def get_scenario_annotations(scenario_id):
    from ..utils import gather_annotations
    return gather_annotations(get_scenario_class(scenario_id))
