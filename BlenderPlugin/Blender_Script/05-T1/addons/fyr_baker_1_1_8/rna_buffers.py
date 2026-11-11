"""Buffers whose numpy buffer format matches what Blender's ``foreach_get`` fast path wants.

Blender takes the memcpy / C loop only when the buffer's format character equals the RNA
property's exactly; anything else falls back to a per-element Python int loop. On Windows
``np.int32`` has format ``'l'``, which matches nothing, so a plain int32 buffer was always
on the slow path (4M triangles: 134 ms vs 2.5 ms for ``loop_triangles.loops``).

* Built-in mesh collection integer properties (``loop_triangles.*``, ``polygons.*``,
  ``loops.*``, ``edges.*``) want ``np.uintc`` (format ``'I'``).
* Generic attribute INT data ``value`` wants ``np.intc`` (format ``'i'``).
* Generic attribute BOOLEAN data ``value`` wants ``np.bool_``.

``empty_u32_for_rna`` returns the uintc buffer; ``as_i32`` hands the filled buffer back as
an int32 view (same bytes, so values and dtype for downstream code are unchanged for any
index below 2**31).
"""

from __future__ import annotations


def empty_u32_for_rna(shape):
    """Uninitialised uintc buffer for a built-in mesh collection integer property."""
    import numpy as np

    return np.empty(shape, dtype=np.uintc)


def empty_i32_for_attribute(shape):
    """Uninitialised intc buffer for a generic INT attribute ``value`` read."""
    import numpy as np

    return np.empty(shape, dtype=np.intc)


def as_i32(buffer):
    """int32 view of a buffer filled through a 32-bit RNA integer read (no copy)."""
    import numpy as np

    return buffer.view(np.int32)


def zeros_u32_for_rna(shape):
    """Zeroed uintc buffer (padded reads); same format rule as :func:`empty_u32_for_rna`."""
    import numpy as np

    return np.zeros(shape, dtype=np.uintc)
