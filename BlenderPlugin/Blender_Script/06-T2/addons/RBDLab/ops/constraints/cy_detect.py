import numpy as np
from typing import List, Dict
from time import time
from ctypes import Structure, c_bool, sizeof, c_int, c_float, POINTER, addressof
# from _ctypes import PyCArrayType
from dataclasses import dataclass
import sys
import platform


from bpy.types import Object, MeshEdge, MeshVertex
from mathutils import Vector, Matrix


sys_platform = sys.platform

if sys_platform == 'win32':
    from ...cy_rbdlab import distances_win as distances

elif sys_platform == 'linux':
    from ...cy_rbdlab import distances_lnx as distances

elif sys_platform == 'darwin':

    arq = platform.processor()
    if arq == "i386": 
        from ...cy_rbdlab import distances_mac_intel as distances

    elif arq == "arm":
        from ...cy_rbdlab import distances_mac_arm as distances

    


from ...addon.naming import RBDLabNaming


USE_DEBUG = False

@dataclass
class BBOX:
    xmin: float
    ymin: float
    zmin: float
    xmax: float
    ymax: float
    zmax: float

    @classmethod
    def create_from_object(cls, object: Object) -> 'BBOX':
        s = object.scale
        t = object.matrix_world.translation
        bb = [t + Vector(p) * s for p in object.bound_box]
        return BBOX(
            min(bb, key=lambda p: p.x).x,
            min(bb, key=lambda p: p.y).y,
            min(bb, key=lambda p: p.z).z,
            max(bb, key=lambda p: p.x).x,
            max(bb, key=lambda p: p.y).y,
            max(bb, key=lambda p: p.z).z
        )

    def expand(self, margin: float = 0.001) -> 'BBOX':
        self.xmin -= margin
        self.ymin -= margin
        self.zmin -= margin
        self.xmax += margin
        self.ymax += margin
        self.zmax += margin
        return self

    def intersect(self, other_bbox: 'BBOX') -> bool:
        return (self.xmax > other_bbox.xmin) and (self.xmin < other_bbox.xmax) and\
            (self.ymax > other_bbox.ymin) and (self.ymin < other_bbox.ymax) and\
            (self.zmax > other_bbox.zmin) and (self.zmin < other_bbox.zmax)


# Extended Types.
c_float_p = POINTER(c_float)
c_int_p = POINTER(c_int)
c_bool_p = POINTER(c_bool)


class BB(Structure):
    _fields_ = [
        ('bb', (c_float * 3) * 8),
    ]

class Cell(Structure):
    _fields_ = [
        ('index', c_int),
        ('coll_index', c_int),
        ('links_start', c_int),
        ('v_count', c_int),
        ('e_count', c_int),
        ('n_count', c_int),
        ('origin', c_float * 3),
        ('vertices', c_float_p), # ('vertices', POINTER(c_float * 3)),
        ('edges', c_int_p), # ('edges', POINTER(c_int * 2)),
        ('cell_links', c_int_p) # POINTER(c_int * 2)),
    ]

next_cell = lambda cell: Cell.from_address(addressof(cell) + sizeof(Cell))

Cell_pointer = POINTER(Cell)


def pylist_float_to_array(list: List[float], size: int | None = None):
    size = size if size is not None else len(list)
    return (c_float * size)(*list)

def pylist_int_to_array(list: List[int], size: int | None = None):
    size = size if size is not None else len(list)
    return (c_int * size)(*list)

# Util Functions.
def get_mw_location(object: Object) -> Vector:
    return object.matrix_world.translation


# Main Function.
def cy_calcute_chunks_neighbors(context,
                                chunk_list: List[Object], # Filtered list of chunks.
                                virtual_cube_threshold: float = 0.001,
                                vertex_distance_threshold: float = 0.001) -> Dict[Object, List[Object]]:
    # CLEANUP.
    sub_time = time()
    def clear_neighbors(cell: Object):
        cell.neighbor_chunks.clear()
        for k in list(cell.keys()):
            if k.startswith('neig'):
                del cell[k]
    {clear_neighbors(chunk) for chunk in chunk_list}
    print("INFO! Time to clean-up existing neighbors data: %.3f seconds" % (time() - sub_time))


    start_time = time()
    sub_time = time()

    chunk_count: int = len(chunk_list)
    chunk_bbox: Dict[Object, BBOX] = {}

    sources_ids: Dict[str, int] = {}
    source_idx = 0

    # Set Temporal Neighbor IDS / Index.
    for idx, chunk in enumerate(chunk_list):
        chunk['temp_index'] = idx
        chunk_bbox[chunk] = BBOX.create_from_object(chunk).expand(margin=virtual_cube_threshold)

        # Link source name with an index.
        chunk_src = chunk.get(RBDLabNaming.FROM)
        if chunk_src is not None:

            if chunk_src in sources_ids:
                chunk['temp_coll_index'] = sources_ids[chunk_src]
            else:
                chunk['temp_coll_index'] = sources_ids[chunk_src] = source_idx*1
                source_idx += 1
            
        else:
            print("[cy_calcute_chunks_neighbors]: " + chunk.name + " Dont have rbdlab_from!!")

    # Forces an update.
    scene = context.scene
    # scene.frame_set(0) # <- JuanFran lo tenía en 0
    # scene.frame_set(scene.frame_current)
    scene.frame_set(scene.frame_start)

    # Get evaluated depsgraph.
    # depsgraph = context.evaluated_depsgraph_get()

    print("INFO! Time for preparations and some temporal caching: %.3f seconds" % (time() - sub_time))


    # ----------------------------------------------------------------
    # Find neighbor candidates for each chunk.
    # ----------------------------------------------------------------

    sub_time = time()
    # origins = ((c_float * 3) * chunk_count)()
    # bb = (((c_float * 3) * 8) * chunk_count)()
    bb = np.empty((chunk_count, 8, 3), dtype=np.float32)

    # bb = [t + Vector(p) * s for p in object.bound_box]
    for i, chunk in enumerate(chunk_list):
        mw = chunk.matrix_world
        s = mw.to_scale()
        t = mw.translation
        # t = mw.translation
        # origins[i][0] = t.x
        # origins[i][1] = t.y
        # origins[i][2] = t.z
        for j, row in enumerate(chunk.bound_box):
            vec = t + Vector((row)) * s # mw @ Vector((row))
            bb[i][j][0] = vec.x
            bb[i][j][1] = vec.y
            bb[i][j][2] = vec.z

    # print("BBOX[0] R0: %f, %f, %f" % (bb[chunk_count-1][0][0], bb[chunk_count-1][0][1], bb[chunk_count-1][0][2]))
    # print("BBOX[0] R1: %f, %f, %f" % (bb[chunk_count-1][1][0], bb[chunk_count-1][1][1], bb[chunk_count-1][1][2]))
    # print("BBOX[0] R2: %f, %f, %f" % (bb[chunk_count-1][2][0], bb[chunk_count-1][2][1], bb[chunk_count-1][2][2]))
    # print("BBOX[0] R3: %f, %f, %f" % (bb[chunk_count-1][3][0], bb[chunk_count-1][3][1], bb[chunk_count-1][3][2]))

    cell_link_count = np.zeros((chunk_count), dtype=np.uint8)
    cell_links = np.full((chunk_count, 30), -1, np.int32)
    cell_link_starts = np.full((chunk_count), -1, dtype=np.int32)

    print("INFO! Prepare BB data for Cython calc: %.3f seconds" % (time() - sub_time))

    sub_time = time()
    n_links: int = distances.get_bb_intersections(
        bb, # c_float_p(bb[0]),
        chunk_count,
        cell_links, # memoryview(links)
        cell_link_starts,
        cell_link_count
    )

    print("n_links by cython:", n_links)

    print("INFO! BB intersections from Cython: %.3f seconds" % (time() - sub_time))

    '''
    sub_time = time()

    neighbor_candidates: dict[Object, set[Object]] = defaultdict(set)
    n_links = 0

    cell_links: Dict[Object, set[int]] = defaultdict(set)

    for chunk_A in chunk_list:
        # Create fake bounding box for the fake cube used as a distance filter.
        bbox_A = chunk_bbox[chunk_A]
        _tmp_n_links = n_links
        for chunk_B in chunk_list:
            if chunk_A == chunk_B: continue
            if chunk_A in neighbor_candidates[chunk_B]: continue

            if bbox_A.intersect(chunk_bbox[chunk_B]):
                # Neighbor Candidate !!!
                neighbor_candidates[chunk_A].add(chunk_B)
                # neighbor_candidates[chunk_B].add(chunk_A)
                cell_links[chunk_A].add((chunk_B['temp_index']))
                n_links += 1

        if _tmp_n_links != n_links:
            # Any links added to this cell?
            chunk_A['temp_links_start'] = _tmp_n_links
        else:
            # No neighbors or links covered by other cells.
            chunk_A['temp_links_start'] = -1

    del neighbor_candidates
    del chunk_bbox


    print("INFO! Time to filter the neighbor candidates for each chunk: %.3f seconds" % (time() - sub_time))
    print("n_links by python:", n_links)
    return
    '''

    # CYTHON DATA.
    if USE_DEBUG:
        indices_to_debug = [0, 1, chunk_count-1]
        print("\n\n[DEBUG][PYTHON][FROM_BPY_OBJECTS]")
        for chunk_idx in indices_to_debug:
            chunk_ob = chunk_list[chunk_idx]
            eval_chunk_ob = chunk_ob # .evaluated_get(depsgraph)
            mw = eval_chunk_ob.matrix_world
            vertices = eval_chunk_ob.data.vertices
            edges = eval_chunk_ob.data.edges
            print("\nCELL %d - '%s'" % (chunk_idx, chunk_ob.name))
            # for i, v in enumerate(eval_chunk_ob.data.vertices):
            #     co: Vector = mw @ v.co
            #     print("\t- Vertex %i: [%.2f, %.2f, %.2f]" % (i, co.x, co.y, co.z))
            co: Vector = mw @ vertices[0].co
            print("\t- Vertices  0: [%.2f, %.2f, %.2f]" % (co.x, co.y, co.z))
            co: Vector = mw @ vertices[1].co
            print("\t            1: [%.2f, %.2f, %.2f]" % (co.x, co.y, co.z))
            co: Vector = mw @ vertices[-1].co
            print("\t            N: [%.2f, %.2f, %.2f]" % (co.x, co.y, co.z))

            # for i, e in enumerate(eval_chunk_ob.data.edges):
            #     print("\t- Edge %i: [%i, %i]" % (i, e.vertices[0], e.vertices[1]))
            print("\t- Edges  0: [%i, %i]" % (edges[0].vertices[0], edges[0].vertices[1]))
            print("\t         1: [%i, %i]" % (edges[1].vertices[0], edges[1].vertices[1]))
            print("\t         N: [%i, %i]" % (edges[-1].vertices[0], edges[-1].vertices[1]))


    sub_time = time()

    CELLS = (Cell * chunk_count)()

    for chunk_idx, chunk_ob in enumerate(chunk_list):
        cell: Cell = CELLS[chunk_idx]

        cell.index = chunk_ob['temp_index']
        cell.coll_index = chunk_ob['temp_coll_index']
        cell.links_start = cell_link_starts[chunk_idx] # chunk_ob['temp_links_start']

        del chunk_ob['temp_index']
        del chunk_ob['temp_coll_index']
        # del chunk_ob['temp_links_start']

        eval_chunk_ob = chunk_ob # .evaluated_get(depsgraph)

        mw: Matrix = eval_chunk_ob.matrix_world

        # Location / Origin.
        cell.origin = pylist_float_to_array(mw.translation, 3)

        # Vertices.
        vertices: List[MeshVertex] = eval_chunk_ob.data.vertices
        v_count = len(vertices)

        arr_vertices = np.array(
            tuple((mw @ v.co).to_tuple() for v in vertices),
            dtype=np.float32
        ).flatten()
        cell.vertices = c_float_p( pylist_float_to_array(arr_vertices, v_count * 3) )
        cell.v_count = v_count

        # Edges.
        edges: List[MeshEdge] = eval_chunk_ob.data.edges
        e_count = len(edges)

        arr_edges = np.array(
            tuple(tuple(edge.vertices) for edge in edges),
            dtype=np.int32
        ).flatten()
        cell.edges = c_int_p( pylist_int_to_array(arr_edges, e_count * 2) )
        cell.e_count = e_count

        # Candidates.
        # candidate_indices = cell_links[chunk_ob]
        link_count = cell_link_count[chunk_idx]
        candidate_indices = cell_links[chunk_idx][:link_count] # [i for i in cell_links[chunk_idx] if i != -1]
        # print("Cell %i - Start %i - Candidates:" % (chunk_idx, cell_link_starts[chunk_idx]), candidate_indices)
        cell.n_count = link_count
        if link_count > 0:
            cell.cell_links = c_int_p( pylist_int_to_array(candidate_indices, link_count) )


    print("INFO! Time to prepare data for Cython: %.3f seconds" % (time() - sub_time))

    sub_time = time()
    output = distances.generate_neighbors(
        addressof(CELLS),
        chunk_count,
        n_links,
        vertex_distance_threshold,
        int(USE_DEBUG)
    )

    print("\n\nINFO! Time to generate neighbors on Cython: %.3f seconds" % (time() - sub_time))
    print("INFO! TOTAL TIME: %.3f seconds" % (time() - start_time))

    if USE_DEBUG:
        print("\n\n[DEBUG][PYTHON][FROM_CELLS_DATA]")
        for chunk_idx in indices_to_debug:
            cell = CELLS[chunk_idx]
            print("\nCell-[%d] '%s':" % (cell.index, chunk_list[cell.index].name))
            # print("Address:", addressof(CELLS), addressof(CELLS[0]))
            print("\t> Counts: V[%i], E[%i], N[%i]" % (cell.v_count, cell.e_count, cell.n_count))
            print("\t> Origin:", tuple(cell.origin))
            v = cell.vertices
            totv = cell.v_count
            # for i in range(totv):
            #     k = i * 3
            #     print("Vertex[%i]: [%.2f, %.2f, %.2f]" % (i, v[k], v[k+1], v[k+2]))
            print("\t> Vertices  0: [%.2f, %.2f, %.2f]" % (v[0], v[1], v[2]))
            print("\t            1: [%.2f, %.2f, %.2f]" % (v[3], v[4], v[5]))
            print("\t            N: [%.2f, %.2f, %.2f]" % (v[totv*3-3], v[totv*3-2], v[totv*3-1]))
            e = cell.edges
            tote = cell.e_count
            # for i in range(tote):
            #     k = i * 2
            #     print("Edge[%i]: [%i, %i]" % (i, e[k], e[k+1]))
            print("\t> Edges  0: [%i, %i]" % (e[0], e[1]))
            print("\t         1: [%i, %i]" % (e[2], e[3]))
            print("\t         N: [%i, %i]" % (e[tote*2-2], e[tote*2-1]))

            if cell.n_count > 0 and cell.links_start != -1 and cell.cell_links is not None:
                print("\t> Cell-Links  0: S[%d] - A[%d], B[%d] ---> Distance[%.2f m]" % (cell.links_start, cell.index, cell.cell_links[0], output[cell.links_start]))
                if cell.n_count > 1:
                    print("\t              1: S[%d] - A[%d], B[%d] ---> Distance[%.2f m]" % (cell.links_start+1, cell.index, cell.cell_links[1], output[cell.links_start+1]))
                if cell.n_count > 2:
                    print("\t              N: S[%d] - A[%d], B[%d] ---> Distance[%.2f m]" % (cell.links_start+cell.n_count-1, cell.index, cell.cell_links[cell.n_count-1], output[cell.links_start+cell.n_count-1]))
            #'''

    # Convert output to custom properties.
    prefix = 'neighbour_'
    # link_index_offset = 0
    n_good_links = 0
    for cell_idx, cell_A in enumerate(chunk_list):
        # links_start = cell_A['temp_links_start']
        links_start = cell_link_starts[cell_idx]
        if links_start == -1:
            ## print("links start is negative", cell_A)
            continue
        ## print(f"[{cell_A.name}] Cell-Links:")
        cell_A_neighbors = cell_A.neighbor_chunks
        for links_off, candidate_index in enumerate([i for i in cell_links[cell_idx] if i != -1]):
            if candidate_index == -1:
                ## print("no more candidates", cell_A)
                break
            d: float = float(output[links_start+links_off]) # distance between cell_A and cell_B.
            # print(f"\t> [{chunk_list[candidate_index].name}]] -> {round(d, 2)} m")
            if d >= 0:
                if USE_DEBUG:
                    print(f"\t> [{cell_A.name}]---[{chunk_list[candidate_index].name}]] ---> {round(d, 2)} m")
                n_good_links += 1
                cell_B: Object = chunk_list[candidate_index]
                cell_A[prefix + cell_B.name] = d
                cell_B[prefix + cell_A.name] = d
                cell_A_neighbors.add_neighbor(cell_B, d)
                cell_B.neighbor_chunks.add_neighbor(cell_A, d)

    print("good links count:", n_good_links)

    del chunk_list
    del cell_links
    del cell_link_starts
