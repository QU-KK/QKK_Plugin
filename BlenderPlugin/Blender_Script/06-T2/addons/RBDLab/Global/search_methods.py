from mathutils import Vector, Color

from enum import Enum

from . math import distance_between
from . functions import generate_bounding_box


MAX_CHUNKS_TO_USE_VERTICES_METHOD = 256

class SearchMethod(Enum):
    CENTROID = 0 # Método rápido.
    VERTICES = 1 # Método lento pero más exacto.
    AUTO = 2     # Método autómatico.


def search_chunks_by_overlap_sphere(
     sphere_location: Vector or list[3] or tuple[3],
     sphere_radius: float,
     chunk_list: list["Object"],
     method: SearchMethod = SearchMethod.AUTO) -> list:

    if method == SearchMethod.AUTO:
        method = SearchMethod.CENTROID if len(chunk_list) > MAX_CHUNKS_TO_USE_VERTICES_METHOD else SearchMethod.VERTICES

    if method == SearchMethod.CENTROID:
        return [chunk for chunk in chunk_list if distance_between(sphere_location, chunk.matrix_world.translation) <= sphere_radius]

    if method == SearchMethod.VERTICES:
        def any_chunk_vertice_inside_sphere(chunk: "Object") -> bool:
            mw = chunk.matrix_world
            for vertice in chunk.data.vertices:
                if distance_between(sphere_location, mw @ vertice.co) <= sphere_radius:
                    return True
            return False

        return [chunk for chunk in chunk_list if any_chunk_vertice_inside_sphere(chunk)]
