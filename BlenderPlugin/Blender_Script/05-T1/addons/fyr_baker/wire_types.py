"""Map types the addon tracks under its own name but the backend bakes as another.

* ATTRIBUTE rows are the backend's VERTEX_COLOR map over a corner colour stream the
  addon filled from the attribute (color_stream).
* DERIVATIVE rows are tangent NORMAL bakes the addon converts to slopes afterwards
  (derived_outputs).

Everything the backend reads (the job's map configs, output targets and dirty rects,
and the RUN / --maps selection) goes through :func:`backend_wire_map_type`; the addon
keeps its own name for naming, output tracking and the UI.
"""

from __future__ import annotations

from . import constants

_BACKEND_ALIASES = {
    constants.MAP_ATTRIBUTE: constants.MAP_VERTEX_COLOR,
    constants.MAP_DERIVATIVE: constants.MAP_NORMAL,
}


def backend_wire_map_type(map_type: str) -> str:
    """The map type the backend receives for ``map_type``."""
    normalized = str(map_type or "").strip()
    return _BACKEND_ALIASES.get(normalized.upper(), normalized)
