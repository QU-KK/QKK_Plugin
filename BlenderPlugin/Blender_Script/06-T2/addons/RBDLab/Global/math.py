from mathutils import Vector
from math import sqrt, pow


def distance_between(A: Vector or list[2] or tuple[2], B: Vector or list[2] or tuple[2]) -> float:
    return sqrt(pow(B[0] - A[0], 2) +
                pow(B[1] - A[1], 2) +
                pow(B[2] - A[2], 2) * 1.0)


def map_value_from_range_to_range(val: float or int, src: tuple, dst: tuple) -> float:
    """
    Scale the given value from the scale of src to the scale of dst.
    """
    return ((val - src[0]) / (src[1] - src[0])) * (dst[1] - dst[0]) + dst[0]


def clamp(value, _min, _max):
    return min(max(value, _min), _max)


def smoothstep(edge0, edge1, x):
    if edge0 == edge1:
        return 0
    # Scale, bias and saturate x to 0..1 range
    x = clamp((x - edge0) / (edge1 - edge0), 0.0, 1.0)
    # Evaluate polynomial
    return x * x * (3 - 2 * x)
