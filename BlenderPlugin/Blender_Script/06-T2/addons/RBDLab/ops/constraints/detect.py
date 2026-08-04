from time import time
from bpy.types import Operator
import bpy
from bpy.types import Object, MeshPolygon, Material, Mesh, Context
from typing import List, Dict, Tuple, Set
from mathutils import Vector, Matrix, kdtree
from collections import defaultdict
import numpy as np
from math import dist, radians, degrees, hypot
import bmesh
from bmesh.types import BMLayerCollection, BMLayerItem
from colorsys import hsv_to_rgb
from ...addon.naming import RBDLabNaming
from dataclasses import dataclass
from itertools import takewhile
from .cy_detect import cy_calcute_chunks_neighbors
from mathutils.geometry import intersect_point_line
# from ...props.constraints import NeighborChunks
from ...Global.get_common_vars import get_common_vars


RAD_10 = radians(10)

USE_VISUAL_DEBUG = True
USE_COLOR_GRADIENT = False
ALLOW_COMPLETELY_SEPARATED_BECOME_PARTIAL_SEPARATED = False
GENERATE_POLY_LAYERS = False
COLOR_SOURCE = 'ATTRIBUTES'  # 'MATERIAL'


def lineseg_dist(p, a, b, d):
    # B3D mathutils Method.
    closest_point_on_line, dist_to_a_as_percent = intersect_point_line(p, a, b)
    # print("percent -> ", dist_to_a_as_percent)
    if dist_to_a_as_percent < 0:
        return False
    if (closest_point_on_line - p).length < d:
        if abs(dist_to_a_as_percent - d) <= 1:
            # print("closest point distance porcentage to A:", dist_to_a_as_percent)
            return True
    return False
    #return dist_to_a_as_percent >= 0 and dist_to_a_as_percent <= 1:
    # distance1 = (closest_point_on_line - a).length
    # distance2 = (closest_point_on_line - b).length
    # distance3 = (closest_point_on_line - p).length
    # return distance3 < d
    # return dist(closest_point_on_line, p)

    ''' Alt method...
    # Distance point to line segment.
    c = Vector((0, 0, 0))

    # From A to B.
    ab = b - a

    # From O to P.
    # O can be any point in the line... like A.
    ap = p - a

    # The distance d from O to the intersection point (closest point) X can be calculated by the Dot product.
    d = ap.dot(ab) / ab.dot(ab)

    # Closest point to P on line...
    c[0] = a[0] + d * b[0]
    c[1] = a[1] + d * b[1]
    c[2] = a[2] + d * b[2]

    return dist(p, c)
    '''

    ''' OLD (slower) ...
    # normalized tangent vector
    d = np.divide(b - a, np.linalg.norm(b - a))
    # signed parallel distance components
    s = np.dot(a - p, d)
    t = np.dot(p - b, d)
    # clamped parallel distance
    h = np.maximum.reduce([s, t, 0])
    # perpendicular distance component
    c = np.cross(p - a, d)
    return np.hypot(h, np.linalg.norm(c))
    '''


def distance_between_object_locations(object_A: Object, object_B: Object) -> float:
    """ Returns the distance between two objects.

    Args:
        object_A (bpy.types.Object): The first object.
        object_B (bpy.types.Object): The second object.
    """
    return dist(object_A.matrix_world.translation.to_tuple(), object_B.matrix_world.translation.to_tuple())


def get_chunk_neighbors_by_location(target_chunk: Object, chunk_list: List[Object]) -> List[Object]:
    """ Iterate over chunk_list to check distance between chunk_list and target chunk. """
    neighbor_chunks: List[Object] = []

    for other_chunk in chunk_list:
        if other_chunk is target_chunk:
            continue
        if distance_between_object_locations(target_chunk, chunk_list) < 0.01:
            neighbor_chunks.append(other_chunk)

    return neighbor_chunks


def angle_diff_between_objects(object_A: Object, object_B: Object) -> Vector:
    _lA, rA, _sA = object_A.matrix_world.decompose()
    _lB, rB, _sB = object_B.matrix_world.decompose()
    return Vector(rA-rB)


######################################################
######################################################

@dataclass
class BBOX:
    xmin: float
    ymin: float
    zmin: float
    xmax: float
    ymax: float
    zmax: float

    @classmethod
    def create_at_origin(cls, origin: Vector, size: Vector) -> 'BBOX':
        size_h = size / 2.0
        return cls(
            *(origin-size_h).to_tuple(),
            *(origin+size_h).to_tuple(),
        )

    def point_inside(self, p: Vector) -> bool:
        return self.xmin <= p.x <= self.xmax and self.ymin <= p.y <= self.ymax and self.zmin <= p.z <= self.zmax

    def intersect(self, other_bbox: 'BBOX') -> bool:
        return (self.xmax > other_bbox.xmin) and (self.xmin < other_bbox.xmax) and\
            (self.ymax > other_bbox.ymin) and (self.ymin < other_bbox.ymax) and\
            (self.zmax > other_bbox.zmin) and (self.zmin < other_bbox.zmax)

    def create_intersect_bbox(self, other: 'BBOX') -> 'BBOX':
        return BBOX(
            # los minimos son los maximos de los minimos.
            # los maximos son los minimos de los maximos.
            max(self.xmin, other.xmin),
            max(self.ymin, other.ymin),
            max(self.zmin, other.zmin),
            min(self.xmax, other.xmax),
            min(self.ymax, other.ymax),
            min(self.zmax, other.zmax),
        )


def detect_neighbors_between_collections(context, chunk_list: List[Object]) -> dict[str, list[Object]]:
    # Clasifica los chunks por collection ID.
    chunks_per_coll = defaultdict(set)
    for chunk in chunk_list:
        chunks_per_coll[chunk[RBDLabNaming.OBJECT__COLL_ID]].add(chunk)

    # Todas las posibles combinaciones 1-1 entre collections.
    all_coll_combinations: list[tuple[str, str]] = []
    skip_id: set[str] = set()
    for coll_id in chunks_per_coll.keys():
        for other_coll_id in chunks_per_coll.keys():
            if other_coll_id in skip_id:
                continue
            if coll_id != other_coll_id:
                all_coll_combinations.append((coll_id, other_coll_id))
        skip_id.add(coll_id)

    # Relaciona el collection ID con un Bounding Box.
    bbox_per_collection: dict[str, BBOX] = {}
    expanded_bbox_per_collection: dict[str, BBOX] = {}
    # max_chunk_dim_per_collection: dict[str, Vector] = {}
    # Calculo de BBOX y de dimensiones maximas de chunk. Por collection.
    for coll_id, coll_chunks in chunks_per_coll.items():
        loc_arr = np.array([ob.location for ob in coll_chunks])
        bbox_min = np.min(loc_arr, axis=0)
        bbox_max = np.max(loc_arr, axis=0)

        dim_arr = np.array([ob.dimensions for ob in coll_chunks])
        # dim_min = np.min(dim_arr, axis=0)
        dim_max = np.max(dim_arr, axis=0) * 0.65

        threshold_arr = np.array([0.01, 0.01, 0.01])
        bbox_per_collection[coll_id] = BBOX(*(bbox_min-threshold_arr), *(bbox_max+threshold_arr))
        # max_chunk_dim_per_collection[coll_id] = Vector(dim_max.tolist())

        # Expanded BBOX.
        bbox_min -= dim_max
        bbox_max += dim_max
        expanded_bbox_per_collection[coll_id] = BBOX(*bbox_min, *bbox_max)

    # Detect intersections between pairs (collections).
    # coll_intersections = defaultdict(set)
    coll_x_coll_chunks: dict[str, list[Object]] = defaultdict(list)
    for (coll_A_id, coll_B_id) in all_coll_combinations:
        # coll_A_bbox = bbox_per_collection[coll_A_id]
        # coll_B_bbox = bbox_per_collection[coll_B_id]
        coll_A_bbox = expanded_bbox_per_collection[coll_A_id]
        coll_B_bbox = expanded_bbox_per_collection[coll_B_id]

        if coll_A_bbox.intersect(coll_B_bbox):
            # coll_intersections[coll_A_id].add(coll_B_id)
            # coll_intersections[coll_B_id].add(coll_A_id)

            # coll_A_bbox = expanded_bbox_per_collection[coll_A_id]
            # coll_B_bbox = expanded_bbox_per_collection[coll_B_id]
            intersect_bbox: BBOX = coll_A_bbox.create_intersect_bbox(coll_B_bbox)

            intersect_id: str = coll_A_id + "&" + coll_B_id

            # Detect chunks inside the intersection coll_x_coll BBOX.
            chunks_from_both_coll = chunks_per_coll[coll_A_id].union(chunks_per_coll[coll_B_id])
            for chunk in chunks_from_both_coll:
                if intersect_bbox.point_inside(chunk.location):
                    coll_x_coll_chunks[intersect_id].append(chunk)

    # print(coll_x_coll_chunks)
    return coll_x_coll_chunks


def end_of_loop():
    raise StopIteration


def calcute_chunks_neighbors(context, chunk_list: List[Object],
                             use_between_collections: bool = False,
                             between_colls: tuple[str, str] = None,
                             search_method: str = 'VERT_KDTREE',  # {'VERT', 'EDGE', 'BBOX', 'VERT_KDTREE'}
                             virtual_cube_threshold: float = 0.001,
                             vertex_distance_threshold: float = 0.001) -> Dict[Object, List[Object]]:
    # vertex_distance_threshold CANNOT BE LESS THAN virtual_cube_threshold
    vertex_distance_threshold = max(virtual_cube_threshold, vertex_distance_threshold)
    if search_method == 'CYTHON':
        return cy_calcute_chunks_neighbors(context, chunk_list, virtual_cube_threshold, vertex_distance_threshold)
    '''
        Calculate neighbor chunks over the given chunks.

        Parameters:
        - chunk_list: already filtered list of chunks to add neighbors to.
        - search_method: metodo de busqueda a usar sobre los neigbir candidates.
        - virtual_cube_threshold: Adds a threshold to virtual cubes used to pre-filter neighbor candidates.
        - vertex_distance_threshold: distance threshold to compare between neigbor candidate vertices.
    '''

    USE_EDGES: bool = search_method == 'EDGE'
    USE_VERTICES: bool = 'VERT' in search_method
    USE_KDTREE: bool = 'KDTREE' in search_method
    USE_BBOX: bool = search_method == 'BBOX'

    start_time = time()

    # por si no existiera algún chunk:
    def validate_exist_object(ob):
        try:
            # Intenta acceder a alguna propiedad o atributo del objeto para verificar su validez
            ob.name
            return True
        except ReferenceError:
            # Si se produce un ReferenceError, el objeto ya no es válido
            return False

    chunk_list = [ob for ob in chunk_list if validate_exist_object(ob)]
    chunk_list = list(set([ob for ob in chunk_list if ob is not None and ob.name in bpy.data.objects]))

    chunk_count: int = len(chunk_list)
    chunk_vertices_cache: Dict[Object, Tuple[Vector]] = {}
    chunks_edge_vertices_cache: Dict[Object, Tuple[Tuple[Vector, Vector]]] = {}
    chunks_kdtree_cache: Dict[Object, kdtree.KDTree] = {}

    chunk_neighbor_chunks_data: Dict[Object, type] = {}  # NeighborChunks type.


    if use_between_collections:
        if between_colls is not None:
            # Interseccion de collections...
            coll_A_id, coll_B_id = between_colls
        else:
            # Cleanup old neighbors data.
            for chunk in chunk_list:
                for coll_neighbor in chunk.coll_neighbor_chunks:
                    coll_neighbor.clear()
                chunk.coll_neighbor_chunks.clear()

            # Calculate new coll neighbors.
            collection_neighbors_relationships = detect_neighbors_between_collections(context, chunk_list)
            for coll_x_coll, intersect_chunks in collection_neighbors_relationships.items():
                coll_A, coll_B = coll_x_coll.split("&")
                calcute_chunks_neighbors(context,
                                         intersect_chunks,
                                         use_between_collections=True,
                                         between_colls=(coll_A, coll_B),
                                         search_method=search_method,
                                         virtual_cube_threshold=virtual_cube_threshold,
                                         vertex_distance_threshold=vertex_distance_threshold)
            return collection_neighbors_relationships

    scene = context.scene
    scene.frame_set(1)
    scene.frame_set(0)

    if GENERATE_POLY_LAYERS:
        chunk_neighbor_indices_layers: Dict[Object, BMLayerItem] = {}
        chunk_neighbor_materials: Dict[Object, Material] = {}
        chunk_neighbor_color_attributes: Dict[Object, None] = {}
        data_mat = bpy.data.materials
        color_hue_factor: float = 1 / chunk_count

    # ----------------------------------------------------------------------------------------------
    # Calcular dimensiones mínimas y máximas por cada eje :
    # ----------------------------------------------------------------------------------------------

    rbdlab, rbdlab_const = get_common_vars(context, get_rbdlab=True, get_constraints=True)
    dimensiones = np.array([chunk.dimensions for chunk in chunk_list])
    # X:
    dimensiones_minimas_x = np.min(dimensiones[:, 0])  # Mínimas en el eje X
    dimensiones_maximas_x = np.max(dimensiones[:, 0])  # Máximas en el eje X
    # Y:
    dimensiones_minimas_y = np.min(dimensiones[:, 1])  # Mínimas en el eje Y
    dimensiones_maximas_y = np.max(dimensiones[:, 1])  # Máximas en el eje Y
    # Z:
    dimensiones_minimas_z = np.min(dimensiones[:, 2])  # Mínimas en el eje Z
    dimensiones_maximas_z = np.max(dimensiones[:, 2])  # Máximas en el eje Z

    # El offset por defecto para el resto de metodos siempre es 0:
    off_x, off_y, off_z = 0, 0, 0

    if USE_BBOX and rbdlab.ui.main_modules == 'CONSTRAINTS':

        # Si usamos bounding box podemos ampliar las dimensiones del faje cube artificialmente:
        bbox_offset_unified = rbdlab_const.bbox_offset_unified
        bbox_offset_unified_toggle = rbdlab_const.bbox_offset_unified_toggle

        off_x = rbdlab_const.bbox_offset_x if bbox_offset_unified_toggle else bbox_offset_unified
        off_y = rbdlab_const.bbox_offset_y if bbox_offset_unified_toggle else bbox_offset_unified
        off_z = rbdlab_const.bbox_offset_z if bbox_offset_unified_toggle else bbox_offset_unified        

    # Calcular dimensiones medias por cada eje:
    dimensiones_medias_x = (dimensiones_minimas_x + dimensiones_maximas_x + off_x) / 2
    dimensiones_medias_y = (dimensiones_minimas_y + dimensiones_maximas_y + off_y) / 2
    dimensiones_medias_z = (dimensiones_minimas_z + dimensiones_maximas_z + off_z) / 2

    # Crear un Vector con las dimensiones medias en los tres ejes
    fake_cube_dimension = Vector((dimensiones_medias_x, dimensiones_medias_y, dimensiones_medias_z))
    
    # ----------------------------------------------------------------------------------------------
    # End Calcular dimensiones mínimas y máximas por cada eje.
    # ----------------------------------------------------------------------------------------------

    # Lo que usaba JuanFran antes de usar el (Calcular dimensiones mínimas y máximas por cada eje):
    # # fake_cube_dimension: Vector = Vector(tuple(np.array([chunk.dimensions for chunk in chunk_list]).sum(axis=0) / chunk_count)) * 1.5
    # fake_cube_dimension: Vector = Vector(tuple(np.array([chunk.dimensions for chunk in chunk_list]).max(axis=0)))  # * .5


    depsgraph = context.evaluated_depsgraph_get()
    # raycast = context.scene.ray_cast

    for idx, chunk_ob in enumerate(chunk_list):
        if USE_VERTICES or USE_EDGES:
            eval_chunk_ob = chunk_ob.evaluated_get(depsgraph)
            mw: Matrix = eval_chunk_ob.matrix_world
            vertices = eval_chunk_ob.data.vertices
            chunk_vertices_cache[chunk_ob] = tuple(
                (mw @ vertice.co) for vertice in vertices
            )

        if USE_KDTREE:
            kd = kdtree.KDTree(len(vertices))
            {kd.insert(co, idx) for idx, co in enumerate(chunk_vertices_cache[chunk_ob])}
            kd.balance()
            chunks_kdtree_cache[chunk_ob] = kd

        if USE_EDGES:
            chunks_edge_vertices_cache[chunk_ob] = tuple(tuple(
                (
                    (mw @ vertices[edge.vertices[0]].co),
                    (mw @ vertices[edge.vertices[1]].co)
                )
                for edge in eval_chunk_ob.data.edges
            ))

        if GENERATE_POLY_LAYERS:
            if "neighbor_indices" in chunk_ob.data.polygon_layers_int:
                chunk_neighbor_indices_layers[chunk_ob] = chunk_ob.data.polygon_layers_int["neighbor_indices"]
            else:
                chunk_neighbor_indices_layers[chunk_ob] = chunk_ob.data.polygon_layers_int.new(name="neighbor_indices")

            # Materials.
            if COLOR_SOURCE == 'MATERIAL':
                mat = data_mat.get("Neighbor@" + chunk_ob.name, None)
                if not mat:
                    color = (*hsv_to_rgb(color_hue_factor * idx, 0.9, 0.9), 1.0)
                    mat = data_mat.new(name="Neighbor@" + chunk_ob.name)
                    mat.use_nodes = False
                    mat.diffuse_color = color
                chunk_neighbor_materials[chunk_ob] = mat

            elif COLOR_SOURCE == 'ATTRIBUTES':
                mesh: Mesh = chunk_ob.data
                if ".neighbor_color" not in mesh.attributes:
                    chunk_neighbor_color_attributes[chunk_ob] = mesh.color_attributes.new(
                        ".neighbor_color", 'FLOAT_COLOR', 'CORNER')  # FACE

                if "neighbor_color" not in chunk_ob:
                    color = (*hsv_to_rgb(color_hue_factor * idx, 0.9, 0.9), 1.0)
                    chunk_ob["neighbor_color"] = color
                    chunk_ob.id_properties_ui("neighbor_color").update(subtype='COLOR')

        # clear data.
        if not use_between_collections:

            for k in list(chunk_ob.keys()):
                if k.startswith("neighbour_"):
                    del chunk_ob[k]

            chunk_ob.neighbor_chunks.clear()

            # Usamos esto como workaround proxy para dar soporte tanto si usamos collections como si no.
            chunk_neighbor_chunks_data[chunk_ob] = chunk_ob.neighbor_chunks

        else:
            # Tomamos la collection contraria (no a la que pertenece).
            neigh_coll_id = coll_A_id if coll_A_id != chunk_ob[RBDLabNaming.OBJECT__COLL_ID] else coll_B_id

            # Buscamos el data correspondiente a esa otra collection dentro del chunk.
            neigh_coll = None

            # for coll_neighbor in chunk_ob.coll_neighbor_chunks:
            #     if coll_neighbor.other_collection_id == neigh_coll_id:
            #         neigh_coll = coll_neighbor
            #         break
            neigh_coll = next((coll_neighbor for coll_neighbor in chunk_ob.coll_neighbor_chunks if coll_neighbor.other_collection_id == neigh_coll_id), None)

            # Si no existe, creamos el data.
            if neigh_coll is None:
                neigh_coll = chunk_ob.coll_neighbor_chunks.add()
                neigh_coll.other_collection_id = neigh_coll_id

            # Usamos esto como workaround proxy para dar soporte tanto si usamos collections como si no.
            chunk_neighbor_chunks_data[chunk_ob] = neigh_coll

    print("[TIME] Generating Neighbors... method=[%s] - threshold=[%f] - First Pass (Cache): %.2f seconds" % (search_method, vertex_distance_threshold, time() - start_time))

    neighbor_chunks: Dict[Object, Set[Object]] = defaultdict(set)

    for chunk_A in chunk_list:
        if USE_VERTICES or USE_EDGES:
            verts_A = chunk_vertices_cache[chunk_A]

        if USE_EDGES:
            edges_A = chunks_edge_vertices_cache[chunk_A]

        fake_cube_origin = chunk_A.location
        virtual_cube_threshold_v = Vector((virtual_cube_threshold, virtual_cube_threshold, virtual_cube_threshold))
        x_min, y_min, z_min = fake_cube_origin - fake_cube_dimension - virtual_cube_threshold_v
        x_max, y_max, z_max = fake_cube_origin + fake_cube_dimension + virtual_cube_threshold_v

        for chunk_B in chunk_list:
            if chunk_A is chunk_B:
                # Same chunk. SKip.
                continue
            if chunk_A in neighbor_chunks[chunk_B]:
                # Chunk is neighbor already.
                # print(f"* Chunk {chunk_B.name} is already neighbor of {chunk_A.name}.")
                continue

            if use_between_collections:
                if chunk_A[RBDLabNaming.OBJECT__COLL_ID] == chunk_B[RBDLabNaming.OBJECT__COLL_ID]:
                    continue

            # Create fake bounding box for the fake cube used as a distance filter.
            chunk_origin = chunk_B.location
            if x_min <= chunk_origin.x <= x_max and y_min <= chunk_origin.y <= y_max and z_min <= chunk_origin.z <= z_max:
                # OK! Está dentro!
                pass
            else:
                # Está fuera!
                continue

            if USE_KDTREE:
                if USE_VERTICES:
                    tree_B = chunks_kdtree_cache[chunk_B]
                    # ok_distance = False
                    # def end_of_loop():
                    #     nonlocal ok_distance
                    #    ok_distance = True
                    #    raise StopIteration
                    # Loop sobre los vértices de A para comprobar si están cerca de algún vértice de B.

                    # if np.min([tree_B.find(v_A)[2] for v_A in verts_A]) > vertex_distance_threshold:
                    try:

                        # {end_of_loop() if tree_B.find(v_A)[2] < vertex_distance_threshold else None for v_A in verts_A}
                        {end_of_loop()
                         if tree_B.find(v_A)[2] < vertex_distance_threshold else None for v_A in verts_A
                         if tree_B.find(v_A)[2] is not None}

                        continue

                    except StopIteration:
                        pass
                    # ok_distance = len(verts_A) != len(list(takewhile(lambda v_A: tree_B.find(v_A)[2] > vertex_distance_threshold, verts_A)))
                    # if ok_distance:
                    #    # demasiado lejos
                    #    continue

            elif USE_BBOX:
                # Already filtered : -)
                pass

            else:
                verts_B = chunk_vertices_cache[chunk_B]

                if USE_VERTICES:
                    if np.min([dist(v_A, v_B) for v_B in verts_B for v_A in verts_A]) > vertex_distance_threshold:
                        # too far!
                        continue
                elif USE_EDGES:
                    ''' OLD (slower) ...
                    if np.min([lineseg_dist(v_B, *e_A) for v_B in verts_B for e_A in edges_A]) > vertex_distance_threshold:
                        # too far!
                        continue
                    '''

                    try:
                        {end_of_loop()
                         if lineseg_dist(v_B, *e_A, vertex_distance_threshold) else None
                         for v_B in verts_B for e_A in edges_A}

                        continue

                    except StopIteration:
                        pass

            # Is neighbor !!!
            # print(f"Chunk {chunk_A.name} is neighbour of {chunk_B.name} by a distance of {min(distances)} meters.")
            # print(f"Chunk {chunk_A.name} is neighbour of {chunk_B.name}.")

            neighbor_chunks[chunk_A].add(chunk_B)
            neighbor_chunks[chunk_B].add(chunk_A)

            # el maximo para un IDProperty name son 63 character:
            prefix = "neighbour_"
            chunk_A[prefix + chunk_B.name[:63-len(prefix)]] = 1.0
            chunk_B[prefix + chunk_A.name[:63-len(prefix)]] = 1.0

            data_chunk_A = chunk_neighbor_chunks_data[chunk_A].add_neighbor(chunk_B)
            data_chunk_B = chunk_neighbor_chunks_data[chunk_B].add_neighbor(chunk_A)
            data_chunk_A.distance = data_chunk_B.distance = distance_between_object_locations(chunk_A, chunk_B)
            # data_chunk_A.angle_diff = data_chunk_B.angle_diff = angle_diff_between_objects(chunk_A, chunk_B)

            if GENERATE_POLY_LAYERS:
                good_verts_A = set()
                good_verts_B = set()
                distances = None
                for dist_AB, v_idx_A, v_idx_B in distances:
                    if dist_AB > 0.001:
                        continue
                    good_verts_A.add(v_idx_A)
                    good_verts_B.add(v_idx_B)

                # Get faces whose vertices are all included in good_verts sets.
                mesh_polygons_A: List[MeshPolygon] = chunk_A.data.polygons
                mesh_polygons_B: List[MeshPolygon] = chunk_B.data.polygons

                # index = count - 1
                chunk_A_target_neighbor_index: int = chunk_neighbor_chunks_data[chunk_A].count() - 1
                # index = count - 1
                chunk_B_target_neighbor_index: int = chunk_neighbor_chunks_data[chunk_B].count() - 1

                layer_A = chunk_neighbor_indices_layers[chunk_A].data
                layer_B = chunk_neighbor_indices_layers[chunk_B].data

                if COLOR_SOURCE == 'MATERIAL':
                    chuck_A_material: Material = chunk_neighbor_materials[chunk_A]
                    chuck_B_material: Material = chunk_neighbor_materials[chunk_B]
                    if chunk_A.data.materials.get(chuck_B_material.name, None) is None:
                        chunk_A.data.materials.append(chuck_B_material)
                    if chunk_B.data.materials.get(chuck_A_material.name, None) is None:
                        chunk_B.data.materials.append(chuck_A_material)
                elif COLOR_SOURCE == 'ATTRIBUTES':
                    color_attribute_A = chunk_neighbor_color_attributes[chunk_A].data
                    color_attribute_B = chunk_neighbor_color_attributes[chunk_B].data
                    chunk_A_color = Vector(chunk_A["neighbor_color"])
                    chunk_B_color = Vector(chunk_B["neighbor_color"])

                for poly_idx, poly in enumerate(mesh_polygons_A):
                    if all([bool(vert_idx in good_verts_A) for vert_idx in poly.vertices]):
                        layer_A[poly_idx].value = chunk_A_target_neighbor_index
                        if COLOR_SOURCE == 'MATERIAL':
                            # index offset for inner/outer materials.
                            poly.material_index = chunk_A_target_neighbor_index + 2
                        elif COLOR_SOURCE == 'ATTRIBUTES':
                            for loop_idx in poly.loop_indices:
                                color_attribute_A[loop_idx].color = chunk_B_color

                for poly_idx, poly in enumerate(mesh_polygons_B):
                    if all([bool(vert_idx in good_verts_B) for vert_idx in poly.vertices]):
                        layer_B[poly_idx].value = chunk_B_target_neighbor_index
                        if COLOR_SOURCE == 'MATERIAL':
                            # index offset for inner/outer materials.
                            poly.material_index = chunk_B_target_neighbor_index + 2
                        elif COLOR_SOURCE == 'ATTRIBUTES':
                            for loop_idx in poly.loop_indices:
                                color_attribute_B[loop_idx].color = chunk_A_color

    del chunk_neighbor_chunks_data
    del chunk_vertices_cache
    del chunks_edge_vertices_cache
    del chunks_kdtree_cache
    del chunk_list

    if GENERATE_POLY_LAYERS:
        del chunk_neighbor_indices_layers
        del chunk_neighbor_materials
        del chunk_neighbor_color_attributes

    del fake_cube_dimension

    # marco el Target Collection:
    # ---------------------------------------------------------------------
    scn = context.scene
    rbdlab = scn.rbdlab

    tcoll_list = rbdlab.lists.target_coll_list
    tcoll = tcoll_list.active

    if tcoll and neighbor_chunks:

        if RBDLabNaming.LAST_CREATED_COLLS in tcoll:

            target_collections = tcoll[RBDLabNaming.LAST_CREATED_COLLS]
            if target_collections:
                for target_coll in target_collections:
                    target_coll[RBDLabNaming.COMPUTED_NEIGHBORS] = True

        else:
             tcoll[RBDLabNaming.COMPUTED_NEIGHBORS] = True

    # ---------------------------------------------------------------------

        # Esto lo hago por el bloqueo de solo usar motions si no se computaron vecinos:
        # vuelvo a poner por defecto las opciones de las particulas:
        rbdlab.particles.debris.create.options = {'BROKEN', 'MOTION'}
        rbdlab.particles.dust.create.options = {'BROKEN', 'MOTION'}
        rbdlab.particles.smoke.create.options = {'BROKEN', 'MOTION'}

    print(f"Total time spent generating neighbors: {round(time() - start_time, 2)} seconds")
    return neighbor_chunks


state_colors: Tuple = (
    (0.2, 0.16, 0.8, 1.0),
    (0.5, 0.16, 0.5, 1.0),
    (0.8, 0.16, 0.2, 1.0)
)


def check_separated_neighbor_chunks(
        context: Context,
        distance_threshold: float,
        chunk_list: List[Object],
        separated_neighbor_chunks: Dict[Object, Set[Object]] = defaultdict(set),
        separated_but_joint: Set[Object] = set(),
        completely_separated_chunks: Set[Object] = set(),
        skip_partially_separated: bool = False,  # DEPRECATED !
        use_partial_broken: bool = True) -> Tuple[Dict[Object, Set[Object]],  Set[Object],  Set[Object]]:
    ''' broken_mode: {'PARTIAL', 'COMPLETE'}'''

    use_distance_threshold = distance_threshold != 0.01
    neighbor_threshold = max(0.01, distance_threshold)
    use_partial_broken_mode = use_partial_broken
    use_complete_broken_mode = not use_partial_broken

    frame = context.scene.frame_current

    def set_completely_separated(ob: Object):
        completely_separated_chunks.add(ob)
        # ob.color = state_colors[2]

    def set_separated_but_joint(ob: Object, factor: float = 0.5):
        separated_but_joint.add(ob)
        # ob.color = state_colors[1]

    def set_full_joint(ob):
        pass  # ob.color = state_colors[0]

    def separate_chunk(ob: Object) -> None:
        if ob.rbdlab.broken_at_frame == -1:
            ob["broken_at_frame"] = frame
            ob["broken_state"] = 1.0
            ob.rbdlab.broken_at_frame = frame

    for chunk_ob in chunk_list:
        if chunk_ob in completely_separated_chunks:
            continue

        neighbor_count: int = chunk_ob.neighbor_chunks.count()
        if neighbor_count == 0:
            set_completely_separated(chunk_ob)
            continue

        # neighbors: List[Tuple[Object, float]] = chunk_ob.neighbor_chunks.get_neighbors()
        for neighbor in chunk_ob.neighbor_chunks.chunks:

            # si no tiene el objeto neighbor skip:
            if neighbor.object is None:
                continue

            neighbor_ob: Object = neighbor.object

            if neighbor_ob in completely_separated_chunks:
                # Completely separated. Ignore it!
                continue
            if neighbor_ob in separated_neighbor_chunks[chunk_ob]:
                # Matched already.
                continue

            # CALCULATE DISTANCE.
            dist_AB: float = distance_between_object_locations(chunk_ob, neighbor_ob)
            dist_off = abs(dist_AB - neighbor.distance)

            #########################

            if dist_off < 0.01:
                # SKIP! TOO CLOSE!
                continue

            if use_distance_threshold:
                if dist_off < neighbor_threshold:
                    # NOPE! Condition of distance threshold not fullfilled!
                    pass  # process should continue...
                else:
                    # OK! distance threshold condition is fullfiled now...
                    chunk_ob.rbdlab.ok_distance_threshold = True
                    neighbor_ob.rbdlab.ok_distance_threshold = True

            ''' CONEXIÓN ROTA !!!!!!!!!! ########################################### '''
            # print(f"Chunk {chunk_ob.name} is separated from {neighbor_ob.name} by {dist_AB} meters. . Diff distance of {(dist_AB - neighbor.distance)}.")

            # Using distance threshold? (particles creation)
            if use_partial_broken_mode:
                separate_chunk(chunk_ob)
                separate_chunk(neighbor_ob)

            # Register broken link.
            separated_neighbor_chunks[chunk_ob].add(neighbor_ob)
            separated_neighbor_chunks[neighbor_ob].add(chunk_ob)

            # CHECK IF NEIGHBOR IS COMPLETELY SEPARATED TOO WITH THIS NEW BROKEN CONNECTION.
            if neighbor_ob.neighbor_chunks.count() == len(separated_neighbor_chunks[neighbor_ob]):
                set_completely_separated(neighbor_ob)

            # if use_complete_broken_mode:
            # separate_chunk(neighbor_ob)
            # else:
            # set_separated_but_joint(neighbor_ob)

        # Check if the chunk is completely separated, partially or not at all.
        separated_chunks_count: int = len(separated_neighbor_chunks[chunk_ob])
        if separated_chunks_count == neighbor_count:
            set_completely_separated(chunk_ob)
            if use_complete_broken_mode:
                separate_chunk(chunk_ob)
        elif separated_chunks_count > 0:
            set_separated_but_joint(chunk_ob)  # , separated_chunks_count/neighbor_count if USE_COLOR_GRADIENT else 1)
        else:
            # FULL JOINT!
            set_full_joint(chunk_ob)

    return separated_neighbor_chunks, separated_but_joint, completely_separated_chunks


#####################################################################
#####################################################################
#####################################################################


class RBDLAB_OT_neighbour_chunks_calculate_broken(Operator):
    bl_idname = "rbdlab.neighbour_chunks_calculate_broken"
    bl_label = "Calculate Broken Neighbor Chunks"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        start_time = time()
        rbdlab = context.scene.rbdlab

        chunk_list: List[Object] = rbdlab.get_chunks()
        if not chunk_list:
            return {'CANCELLED'}

        for chunk in chunk_list:
            if "broken_state" in chunk:
                del chunk["broken_state"]
            chunk.rbdlab.broken_at_frame = -1
            # chunk.prev_location = chunk.location

        scene = context.scene

        scene.frame_set(0)
        # calcute_chunks_neighbors(context, chunk_list)

        separated_neighbor_chunks: Dict[Object, List[Object]] = defaultdict(set)
        completely_separated_chunks: Set[Object] = set()
        separated_but_joint: Set[Object] = set()
        for frame_idx in range(scene.frame_start, scene.frame_end):
            scene.frame_set(frame_idx)

            separated_neighbor_chunks, separated_but_joint, completely_separated_chunks = check_separated_neighbor_chunks(
                context,
                0.01,
                chunk_list,
                separated_neighbor_chunks,
                separated_but_joint,
                completely_separated_chunks,
                skip_partially_separated=False
            )
            # Update the chunk list to exclude chunks that are completely_separated_chunks.
            # chunk_list = list(set(chunk_list).difference(completely_separated_chunks))

            # separated_neighbors.update(separated_neighbor_chunks)

        # for chunk_ob, neighbors_ob in separated_neighbors.items():
        #    neighbors_count: int = chunk_ob.neighbor_chunks.count()
        #    separated_count: int = len(neighbors_ob)
        #    print(f"- Chunk {chunk_ob.name} has {neighbors_count-separated_count}/{neighbors_count} neighbors.")

        # print("* CompletelySeparatedChunks: ", completely_separated_chunks)
        # print("* SeparatedButJointChunks  : ", separated_but_joint)
        # from pprint import pprint
        # pprint(separated_neighbor_chunks, indent=4)
        tot_time_msg = f"Time spent detecting breaks: {round(time()-start_time, 2)} seconds"
        print(tot_time_msg)
        self.report({'INFO'}, tot_time_msg)

        scene.frame_set(0)
        bpy.ops.screen.animation_play()
        return {'FINISHED'}


def detect_broken_chunks_frames(context):
    start_time = time()
    rbdlab = context.scene.rbdlab

    chunk_list: List[Object] = rbdlab.get_chunks()
    if not chunk_list:
        return None

    for chunk in chunk_list:
        if "broken_state" in chunk:
            del chunk["broken_state"]
        chunk.rbdlab.broken_at_frame = -1
        # chunk.prev_location = chunk.location

    scene = context.scene

    scene.frame_set(0)
    # calcute_chunks_neighbors(context, chunk_list)

    separated_neighbor_chunks: Dict[Object, List[Object]] = defaultdict(set)
    completely_separated_chunks: Set[Object] = set()
    separated_but_joint: Set[Object] = set()
    for frame_idx in range(scene.frame_start, scene.frame_end):
        scene.frame_set(frame_idx)

        separated_neighbor_chunks, separated_but_joint, completely_separated_chunks = check_separated_neighbor_chunks(
            context,
            0.01,
            chunk_list,
            separated_neighbor_chunks,
            separated_but_joint,
            completely_separated_chunks,
            skip_partially_separated=False
        )
        # Update the chunk list to exclude chunks that are completely_separated_chunks.
        # chunk_list = list(set(chunk_list).difference(completely_separated_chunks))

        # separated_neighbors.update(separated_neighbor_chunks)

    # for chunk_ob, neighbors_ob in separated_neighbors.items():
    #    neighbors_count: int = chunk_ob.neighbor_chunks.count()
    #    separated_count: int = len(neighbors_ob)
    #    print(f"- Chunk {chunk_ob.name} has {neighbors_count-separated_count}/{neighbors_count} neighbors.")

    # print("* CompletelySeparatedChunks: ", completely_separated_chunks)
    # print("* SeparatedButJointChunks  : ", separated_but_joint)
    # from pprint import pprint
    # pprint(separated_neighbor_chunks, indent=4)
    tot_time_msg = f"Time spent detecting breaks: {round(time()-start_time, 2)} seconds"
    print(tot_time_msg)

    scene.frame_set(0)

    return completely_separated_chunks


def get_broken_chunks_at_frame(chunks: List[Object], frame: int) -> List[Object]:
    return [
        chunk
        for chunk in chunks if
        "broken_state" in chunk and
        chunk.rbdlab.broken_at_frame >= frame
    ]


def get_broken_chunks_at_frame_inv(chunks: List[Object], frame: int) -> List[Object]:
    return [
        chunk
        for chunk in chunks if
        "broken_state" in chunk and
        chunk.rbdlab.broken_at_frame <= frame
    ]



###############################################################################
# COMMON METHODS PARA RECALCULAR VECINOS (POR EJEMPLO EN CONSTRAINTS ADJACENTS)
###############################################################################

recomp_adj = RBDLabNaming.WM_RECOMP_ADJACENT
ascii_decor = "\n##################################################################\n" 
text_info = "[ * Recompute Adjacents Neighbors * ]"


def recalculate_neighbors_for_adjacents(context) -> None:

    rbdlab, rbdlab_const = get_common_vars(context, get_rbdlab=True, get_constraints=True)
    src_collections = rbdlab_const.get_selected_work_group_collections

    chunks = [ob for coll in src_collections for ob in coll.objects if ob.type == 'MESH' and "rbdlab_from" in ob and ob.visible_get() and ob.name in context.view_layer.objects]

    if not chunks: 
        return -1
    
    # Para evitar recomputar vecinos más veces de la cuenta:
    
    # Propiedades que pueden ir cambiando:
    search_method = rbdlab_const.neighbors_search_method
    virtual_cube_threshold = rbdlab_const.neighbors_virtual_cube_threshold

    bbox_offset_unified = rbdlab_const.bbox_offset_unified
    bbox_offset_unified_toggle = int(rbdlab_const.bbox_offset_unified_toggle)
    bbox_offset_x = rbdlab_const.bbox_offset_x
    bbox_offset_y = rbdlab_const.bbox_offset_y
    bbox_offset_z = rbdlab_const.bbox_offset_z
    adjacents_only_between_different_froms = rbdlab_const.adjacents_only_between_different_froms

    data = {search_method: [virtual_cube_threshold, bbox_offset_unified, bbox_offset_unified_toggle, bbox_offset_x, bbox_offset_y, bbox_offset_z, int(adjacents_only_between_different_froms)]}

    def recalculate():
        # muestro que se esta recalculando:
        print(f" {ascii_decor} {text_info} (Recalculate for Adjacents) {ascii_decor}")
        
        # recalculamos:
        calcute_chunks_neighbors(context, chunks, search_method=search_method, virtual_cube_threshold=virtual_cube_threshold)
        
        # guardamos la data utilizada:
        rbdlab[recomp_adj] = data

    if recomp_adj not in rbdlab: # si no está marcado lo recalculamos y marcamos:
        recalculate()
    
    # Si está marcado vemos si a cambiado, y si a cambiado, lo recalculamos:
    elif data != rbdlab[recomp_adj].to_dict():
        recalculate()


def restore_default_neighbors(context) -> None:
    
    rbdlab, rbdlab_const = get_common_vars(context, get_rbdlab=True, get_constraints=True)
    src_collections = rbdlab_const.get_selected_work_group_collections

    chunks = [ob for coll in src_collections for ob in coll.objects if ob.type == 'MESH' and "rbdlab_from" in ob and ob.visible_get() and ob.name in context.view_layer.objects]

    if not chunks: 
        return -1

    # Reestablecemos los venicos por defecto:
    #-------------------------------------------------------------------------------------------------------
    src_collections = rbdlab_const.get_selected_work_group_collections
    chunks = [ob for coll in src_collections for ob in coll.objects if ob.type == 'MESH' and "rbdlab_from" in ob and ob.visible_get() and ob.name in context.view_layer.objects]
    print(f" {ascii_decor} {text_info} (Restore to defaults) {ascii_decor}")


    ob_by_from: dict[str, List[Object]] = defaultdict(list)
    for ob in chunks:
        from_name = ob.get(RBDLabNaming.FROM)
        if from_name:
            ob_by_from[from_name].append(ob)
    
    # Por cada objeto original:
    for chunks in ob_by_from.values():
        calcute_chunks_neighbors(context, chunks, search_method='CYTHON', virtual_cube_threshold=0.001)
    
    if recomp_adj in rbdlab:
        del rbdlab[recomp_adj]
