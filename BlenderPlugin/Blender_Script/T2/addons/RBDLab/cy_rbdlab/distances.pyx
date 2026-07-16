# cython: profile=True
# cython: embedsignature=True
# cython: language_level=3
# distutils: language=c++

cimport cython
from cython.parallel import prange#, parallel, threadid
# cimport openmp
import sys

from cpython.mem cimport PyMem_Malloc, PyMem_Free

from libc.stdio cimport printf

from libc.math cimport sqrt, hypot


import numpy as np
cimport numpy as cnp


cdef float EPS = <float>sys.float_info.epsilon


cdef struct Cell:
    int index
    int coll_index
    int links_start # index at start of links for this cell
    int v_count
    int e_count
    int n_count
    float origin[3]
    float *vertices
    int *edges
    # cnp.float32_t (*vertices)[3]
    # cnp.int32_t (*edges)[2]
    # cnp.int32_t (*cell_links)[2]
    int *cell_links

# ----------------------------------------------------------------


@cython.boundscheck(False)  # Deactivate bounds checking
cdef inline float dotprod(const float A[3], const float B[3]) nogil:
    return A[0] * B[0] + A[1] * B[1] + A[2] * B[2]


@cython.boundscheck(False)  # Deactivate bounds checking
cdef inline void mult_v3_f(float A[3], const float value) nogil:
    A[0] *= value
    A[1] *= value
    A[2] *= value

@cython.boundscheck(False)  # Deactivate bounds checking
cdef inline void add_v3(const float A[3], const float B[3], float output[3]) nogil:
    output[0] = A[0] + B[0]
    output[1] = A[1] + B[1]
    output[2] = A[2] + B[2]

@cython.boundscheck(False)  # Deactivate bounds checking
cdef inline void sub_v3(const float A[3], const float B[3], float output[3]) nogil:
    output[0] = A[0] - B[0]
    output[1] = A[1] - B[1]
    output[2] = A[2] - B[2]


# ----------------------------------------------------------------


@cython.boundscheck(False)  # Deactivate bounds checking
@cython.wraparound(False)   # Deactivate negative indexing.
@cython.nonecheck(False)
@cython.cdivision(False)
cdef inline float distance_between(float A[3], float B[3]) nogil:
    # sqrt(sum((px - qx) ** 2.0 for px, qx in zip(p, q)))
    cdef float AB[3]
    AB[0] = A[0] - B[0]
    AB[1] = A[1] - B[1]
    AB[2] = A[2] - B[2]
    return absf(<float>sqrt(AB[0] * AB[0] + AB[1] * AB[1] + AB[2] * AB[2]))

    # return <float>sqrt((B[0] - A[0])**2 +
    #                    (B[1] - A[1])**2 +
    #                    (B[2] - A[2])**2)


@cython.boundscheck(False)  # Deactivate bounds checking
@cython.wraparound(False)   # Deactivate negative indexing.
@cython.nonecheck(False)
@cython.cdivision(False)
cdef inline float maxf2(float a, float b) nogil:
    return a if a > b else b


@cython.boundscheck(False)  # Deactivate bounds checking
@cython.wraparound(False)   # Deactivate negative indexing.
@cython.nonecheck(False)
@cython.cdivision(False)
cdef inline float minf2(float a, float b) nogil:
    return a if a < b else b


@cython.boundscheck(False)  # Deactivate bounds checking
@cython.wraparound(False)   # Deactivate negative indexing.
@cython.nonecheck(False)
@cython.cdivision(False)
cdef inline float maxf3(float a, float b, float c) nogil:
    if a > b:
        if c > a:
            return c
        return a
    if c > b:
        return c
    return b


@cython.boundscheck(False)  # Deactivate bounds checking
@cython.wraparound(False)   # Deactivate negative indexing.
@cython.nonecheck(False)
@cython.cdivision(False)
cdef inline float absf(float a) nogil:
    return a if a >= 0 else 0


#@cython.profile(True)
@cython.boundscheck(False)  # Deactivate bounds checking
@cython.wraparound(False)   # Deactivate negative indexing.
@cython.nonecheck(False)
@cython.cdivision(False)
cdef inline float distance_point_segment(float A[3], float B[3], float P[3]) nogil:
    cdef:
        float[3] AB
        float[3] mul
        float area, area_2

    AB[0] = B[0] - A[0]
    AB[1] = B[1] - A[1]
    AB[2] = B[2] - A[2]

    area_2 = <float>sqrt(AB[0] * AB[0] + AB[1] * AB[1] + AB[2] * AB[2])

    if area_2 == 0:
        return 0 # Ok.

    mul[0] = AB[0] * (P[0] - A[0])
    mul[1] = AB[1] * (P[1] - A[1])
    mul[2] = AB[2] * (P[2] - A[2])

    area = <float>sqrt(mul[0] * mul[0] + mul[1] * mul[1] + mul[2] * mul[2])
    return area / area_2


#@cython.profile(True)
@cython.boundscheck(False)  # Deactivate bounds checking
@cython.wraparound(False)   # Deactivate negative indexing.
@cython.nonecheck(False)
@cython.cdivision(False)
cdef inline float line_line_intersect(float p1[3], float p2[3], float p3[3], float p4[3]) nogil:
    cdef:
        float[2] p13, p43, p21
        float d1343, d4321, d1321, d4343, d2121
        float numer, denom
        float[2] pa, pb
        float mua, mub

    p13[0] = p1[0] - p3[0]
    p13[1] = p1[1] - p3[1]
    p13[2] = p1[2] - p3[2]
    p43[0] = p4[0] - p3[0]
    p43[1] = p4[1] - p3[1]
    p43[2] = p4[2] - p3[2]
    if (absf(p43[0]) < EPS and absf(p43[1]) < EPS and absf(p43[2]) < EPS):
        return 10000.0

    p21[0] = p2[0] - p1[0]
    p21[1] = p2[1] - p1[1]
    p21[2] = p2[2] - p1[2]
    if (absf(p21[0]) < EPS and absf(p21[1]) < EPS and absf(p21[2]) < EPS):
        return 10000.0

    d1343 = p13[0] * p43[0] + p13[1] * p43[1] + p13[2] * p43[2]
    d4321 = p43[0] * p21[0] + p43[1] * p21[1] + p43[2] * p21[2]
    d1321 = p13[0] * p21[0] + p13[1] * p21[1] + p13[2] * p21[2]
    d4343 = p43[0] * p43[0] + p43[1] * p43[1] + p43[2] * p43[2]
    d2121 = p21[0] * p21[0] + p21[1] * p21[1] + p21[2] * p21[2]

    denom = d2121 * d4343 - d4321 * d4321
    if (absf(denom) < EPS):
        return 10000.0

    numer = d1343 * d4321 - d1321 * d4343

    mua = numer / denom
    mub = (d1343 + d4321 * (mua)) / d4343

    pa[0] = p1[0] + mua * p21[0]
    pa[1] = p1[1] + mua * p21[1]
    pa[2] = p1[2] + mua * p21[2]
    pb[0] = p3[0] + mub * p43[0]
    pb[1] = p3[1] + mub * p43[1]
    pb[2] = p3[2] + mub * p43[2]

    return distance_between(pa, pb)
    return 1


#@cython.profile(True)
@cython.boundscheck(False)  # Deactivate bounds checking
@cython.wraparound(False)   # Deactivate negative indexing.
@cython.nonecheck(False)
@cython.cdivision(False)
cdef inline float dist3D_Segment_to_Segment(float p0[3], float p1[3], float q0[3], float q1[3]) nogil:
    cdef:
        float[3] u, v, w
        float[3] dP
        float a, b, c, d, e
        float D, sD, tD
        float sN, tN

    sub_v3(p1, p0, u)
    sub_v3(q1, q0, v)
    sub_v3(p0, q0, w)

    a = dotprod(u, u)	# always >= 0
    b = dotprod(u, v)
    c = dotprod(v, v)	# always >= 0
    d = dotprod(u, w)
    e = dotprod(v, w)

    D = a*c - b*b	 # always >= 0
    sD = D	# sc = sN / sD, default sD = D >= 0
    tD = D	# tc = tN / tD, default tD = D >= 0

    # compute the line parameters of the two closest points
    if (D < EPS): # the lines are almost parallel
        sN = 0.0	# force using point P0 on segment S1
        sD = 1.0	# to prevent possible division by 0.0 later
        tN = e
        tD = c
    else:# get the closest points on the infinite lines
        sN = (b*e - c*d)
        tN = (a*e - b*d)
        if (sN < 0.0): # sc < 0 => the s=0 edge is visible
            sN = 0.0
            tN = e
            tD = c
        elif (sN > sD): # sc > 1 => the s=1 edge is visible
            sN = sD
            tN = e + b
            tD = c

    if (tN < 0.0): # tc < 0 => the t=0 edge is visible
        tN = 0.0
        # recompute sc for this edge
        if (-d < 0.0):
            sN = 0.0
        elif (-d > a):
            sN = sD
        else:
            sN = -d
            sD = a

    elif (tN > tD): # tc > 1 => the t=1 edge is visible
        tN = tD
        # recompute sc for this edge
        if ((-d + b) < 0.0):
            sN = 0.0
        elif ((-d + b) > a):
            sN = sD
        else:
            sN = (-d + b)
            sD = a

    # finally do the division to get sc and tc
    sc = 0.0 if (absf(sN) < EPS) else (sN / sD)
    tc = 0.0 if (absf(tN) < EPS) else (tN / tD)

    # get the difference of the two closest points
    mult_v3_f(u, sc)
    mult_v3_f(v, tc)
    add_v3(w, u, dP)
    sub_v3(dP, v, dP)
    ## dP = w + (sc * u) - (tc * v)	# = S1(sc) - S2(tc)

    return <float>sqrt(dotprod(dP, dP))	 # return the closest distance



cdef inline void debug_points(float A[3], float B[3], float P[3]) nogil:
    printf("\n\n\t> point_seg_dist \tA: [%.2f, %.2f, %.2f]", A[0], A[1], A[2])
    printf("\n\t                 \tB: [%.2f, %.2f, %.2f]", B[0], B[1], B[2])
    printf("\n\t                 \tP: [%.2f, %.2f, %.2f]", P[0], P[1], P[2])

#@cython.profile(True)
@cython.boundscheck(False)  # Deactivate bounds checking
@cython.wraparound(False)   # Deactivate negative indexing.
@cython.nonecheck(False)
@cython.cdivision(False)
cdef inline float point_seg_dist(float A[3], float B[3], float P[3]) nogil:
    # ap = p-a
    # ab = b-a
    # result = a + dot(ap,ab)/dot(ab,ab) * ab

    cdef:
        float[3] AB, AP, C
        float d

    # From A to B.
    AB[0] = B[0] - A[0]
    AB[1] = B[1] - A[1]
    AB[2] = B[2] - A[2]

    # From O to P.
    # O can be any point in the line... like A.
    AP[0] = P[0] - A[0]
    AP[1] = P[1] - A[1]
    AP[2] = P[2] - A[2]

    # The distance d from O to the intersection point (closest point) X can be calculated by the Dot product.
    d = (AP[0] * AB[0] + AP[1] * AB[1] + AP[2] * AB[2]) / (AB[0] * AB[0] + AB[1] * AB[1] + AB[2] * AB[2])

    # Closest point to P on line...
    C[0] = A[0] + d * AB[0]
    C[1] = A[1] + d * AB[1]
    C[2] = A[2] + d * AB[2]

    return distance_between(P, C)

    cdef:
        float[3] AB, AP, D
        float lenAB #, d

    # O ... any point on the line
    # D ... unit vector which points in the direction of the line
    # P ... the "Point"

    # From A to B.
    AB[0] = absf(B[0] - A[0])
    AB[1] = absf(B[1] - A[1])
    AB[2] = absf(B[2] - A[2])

    lenAB = sqrt(AB[0]*AB[0] + AB[1]*AB[1] + AB[2]*AB[2])

    D[0] = AB[0] / lenAB
    D[1] = AB[1] / lenAB
    D[2] = AB[2] / lenAB

    # From O to P.
    # O can be any point in the line... like A.
    AP[0] = P[0] - A[0]
    AP[1] = P[1] - A[1]
    AP[2] = P[2] - A[2]

    # The distance d from O to the intersection point (closest point) X can be calculated by the Dot product.
    # In general The dot product of 2 vectors is equal the cosine of the angle between the 2 vectors
    # multiplied by the magnitude (length) of both vectors.
    # d = dot( A, B ) == | A | * | B | * cos( angle_A_B )
    # d = dot(V, D);
    return D[0]*AP[0] + D[1]*AP[1] + D[2]*AP[2]



    # d = norm(cross(x2-x1 , x1-x0)) / norm(x2-x1);


@cython.boundscheck(False)  # Deactivate bounds checking
@cython.wraparound(False)   # Deactivate negative indexing.
@cython.nonecheck(False)
@cython.cdivision(False)
cdef inline int check_bb_intersections(float [:,:] bb_1, float [:,:] bb_2) nogil: # [8][3], [8][3]
    # bb[0][0] = xmin
    # bb[0][1] = ymin
    # bb[0][2] = zmin
    # bb[1][0] = xmax
    # bb[1][1] = ymax
    # bb[1][2] = zmax
    return <int>((bb_1[1][0] > bb_2[0][0]) and (bb_1[0][0] < bb_2[1][0]) and\
           (bb_1[1][1] > bb_2[0][1]) and (bb_1[0][1] < bb_2[1][1]) and\
           (bb_1[1][2] > bb_2[0][2]) and (bb_1[0][2] < bb_2[1][2]))


@cython.boundscheck(False)  # Deactivate bounds checking
@cython.wraparound(False)   # Deactivate negative indexing.
@cython.nonecheck(False)
@cython.cdivision(False)
cpdef inline int get_bb_intersections(float [:,:,:] bbox,
                                      int cell_count,
                                      int [:,:] links,
                                      int [:] link_starts,
                                      unsigned char [:] link_count):

    cdef:
        int i = 0, j = 0, n = 0, row_idx = 0, skip = 0, n_links = 0, k = 0
        float xmin=100000.0, ymin=100000.0, zmin=100000.0, xmax=100000.0, ymax=100000.0, zmax=100000.0
        ## int *link_count
        ## cdef short *kidx, *k # access via k[0]... k[0] += 1, k[0] = n...

    ## link_count = <int *>PyMem_Malloc(sizeof(int) * cell_count)
    ## kidx = <short *>PyMem_Malloc(sizeof(double) * openmp.omp_get_max_threads() * 32)

    # printf("\nCell Count: %d", cell_count)
    # printf("\nBBOX[N] R0: %f, %f, %f", bbox[cell_count-1][0][0], bbox[cell_count-1][0][1], bbox[cell_count-1][0][2])
    # printf("\nBBOX[N] R1: %f, %f, %f", bbox[cell_count-1][1][0], bbox[cell_count-1][1][1], bbox[cell_count-1][1][2])
    # printf("\nBBOX[N] R2: %f, %f, %f", bbox[cell_count-1][2][0], bbox[cell_count-1][2][1], bbox[cell_count-1][2][2])
    # printf("\nBBOX[N] R3: %f, %f, %f", bbox[cell_count-1][3][0], bbox[cell_count-1][3][1], bbox[cell_count-1][3][2])

    with nogil: #, parallel():
        ## for j in prange(cell_count):
        ##     link_count[j] = 0

        for i in prange(cell_count):
            #bb = bbox[i]
            # Get xmin, ymin, zmin, xmax, ymax, zmax.
            for row_idx in range(8):
                # Iterate over rows.
                xmin = minf2(xmin, bbox[i][row_idx][0])
                xmax = maxf2(xmax, bbox[i][row_idx][0])
                ymin = minf2(ymin, bbox[i][row_idx][1])
                ymax = maxf2(ymax, bbox[i][row_idx][1])
                zmin = minf2(zmin, bbox[i][row_idx][2])
                zmax = maxf2(zmax, bbox[i][row_idx][2])

            # Save them into the current bb array to save-up space.
            # in the first  bb[0][X] the min,
            # in the second bb[1][X] the max.
            bbox[i][0][0] = xmin - 0.002
            bbox[i][0][1] = ymin - 0.002
            bbox[i][0][2] = zmin - 0.002
            bbox[i][1][0] = xmax + 0.002
            bbox[i][1][1] = ymax + 0.002
            bbox[i][1][2] = zmax + 0.002

            # Reset to maximum values.
            xmin=100000
            ymin=100000
            zmin=100000
            xmax=100000
            ymax=100000
            zmax=100000


    for i in range(cell_count):
        k = 0 # Reset for next cell.
        ## k = kidx + 32 * threadid()
        skip = 0 # Skip check condition.

        for j in range(cell_count):

            # Can't link to itself lmao.
            if i == j:
                continue

            # The limit is 30 links per cell actually...
            if k == 30:
                break

            # Check if this link was added in the other way around.
            if i > j:
                # Solo tiene sentido cuando el segundo iterator va por delante del primero.
                # Ya que se necesita chequear sobre el indice segundo que ya se haya procesado.
                for n in range(30):
                    if links[j][n] == i:
                        skip = 1
                        break
            if skip == 1:
                skip = 0
                continue

            # The actual BB intersection to check if they are potentially connected.
            if check_bb_intersections(bbox[i], bbox[j]) == 1:
                links[i][k] = j
                k += 1
                # printf("> Link between %d and %d", i, j)

                # Non parallel code:
                if link_starts[i] == -1:
                    link_starts[i] = n_links
                n_links += 1

                link_count[i] += 1

    # Apply the start link indices per cell.
    ## n = 0
    ## for i in range(cell_count):
    ##     if link_count[i] != 0:
    ##         link_starts[i] = n
    ##         n += link_count[i]
    ## PyMem_Free(link_count)
    ## PyMem_Free(kidx)
    return n_links


# @cython.profile(True)
@cython.boundscheck(False)  # Deactivate bounds checking
@cython.wraparound(False)   # Deactivate negative indexing.
@cython.nonecheck(False)
@cython.cdivision(False)
cpdef inline cnp.ndarray[cnp.float32_t, ndim=1] generate_neighbors(long long cells_p,
                                                                   int cell_count,
                                                                   int n_links,
                                                                   float distance_threshold,
                                                                   int use_debug): # nogil

    cdef Cell *cells = (<Cell*>cells_p)
    cdef:
        int cell_idx = 0, other_cell_idx = 0, cell_n_idx = 0, i = 0, j = 0
        float d = 10000.0
        Cell cell_a, cell_b
        float *cell_link_distances = <float *>PyMem_Malloc(n_links * sizeof(float))
        cnp.ndarray[cnp.float32_t, ndim=1] output = np.full((n_links), -1.0, dtype=np.float32)

    # [zebus] Intentamos fixear si es menos de 3 objetos, para que no de errores de expected 3, got 2:
    cdef int[3] test_indices  # Declarar la variable test_indices
    # Asignando valores:
    if cell_count >= 3:
        test_indices = {0, 1, cell_count-1}
    else:
        test_indices = {0, 1, 3}


    # ''' DEBUG --------------------------------------------------------------------------
    if use_debug == 1:

        printf("\n\n\n[DEBUG][CYTHON]")
        for j in range(0, 3):
            cell_idx = test_indices[j]
            cell_a = cells[cell_idx]
            printf("\n\nCell-Index[%d]", cell_a.index)

            # printf("\n\t> V-Count: %d", cell_a.v_count)
            # printf("\n\t> E-Count: %d", cell_a.e_count)
            # printf("\n\t> N-Count: %d", cell_a.n_count)
            printf("\n\t> Counts: V[%i], E[%i], N[%i]", cell_a.v_count, cell_a.e_count, cell_a.n_count)

            printf("\n\t> Origin: [%.2f, %.2f, %.2f]", cell_a.origin[0], cell_a.origin[1], cell_a.origin[2])

            # printf("\n\t> Vertex 0: [%.2f, %.2f, %.2f]", cell_a.vertices[0][0], cell_a.vertices[0][1], cell_a.vertices[0][2])
            # printf("\n\t> Vertex N: [%.2f, %.2f, %.2f]", cell_a.vertices[cell_a.v_count-1][0], cell_a.vertices[cell_a.v_count-1][1], cell_a.vertices[cell_a.v_count-1][2])
            # for i in range(cell_a.v_count):
            #     k = i * 3
            #     printf("\n\t> Vertex %d: [%.2f, %.2f, %.2f]", i, cell_a.vertices[k], cell_a.vertices[k+1], cell_a.vertices[k+2])
            printf("\n\t> Vertices \t0: [%.2f, %.2f, %.2f]", cell_a.vertices[0], cell_a.vertices[1], cell_a.vertices[2])
            printf("\n\t           \t1: [%.2f, %.2f, %.2f]", cell_a.vertices[3], cell_a.vertices[4], cell_a.vertices[5])
            printf("\n\t           \tN: [%.2f, %.2f, %.2f]", cell_a.vertices[cell_a.v_count*3-3], cell_a.vertices[cell_a.v_count*3-2], cell_a.vertices[cell_a.v_count*3-1])

            # for i in range(cell_a.e_count):
            #     k = i * 2
            #     printf("\n\t> Edge %d: v1[%d], v2[%d]", i, cell_a.edges[k], cell_a.edges[k+1])
            printf("\n\t> Edges\t0:   [%d, %d]", cell_a.edges[0], cell_a.edges[1])
            printf("\n\t       \t1:   [%d, %d]", cell_a.edges[2], cell_a.edges[3])
            # printf("\n\t       \tN-1: [%d, %d]", cell_a.edges[cell_a.e_count*2-4], cell_a.edges[cell_a.e_count*2-3])
            printf("\n\t       \tN:   [%d, %d]", cell_a.edges[cell_a.e_count*2-2], cell_a.edges[cell_a.e_count*2-1])

            if cell_a.n_count != 0 and cell_a.links_start != -1 and cell_a.cell_links != NULL:
                printf("\n\t> Cell-Links\t0: S[%d] - A[%d], B[%d]", cell_a.links_start, cell_a.index, cell_a.cell_links[0])
                if cell_a.n_count > 1:
                    printf("\n\t            \t1: S[%d] - A[%d], B[%d]", cell_a.links_start+1, cell_a.index, cell_a.cell_links[1])
                if cell_a.n_count > 2:
                    printf("\n\t            \tN: S[%d] - A[%d], B[%d]", cell_a.links_start+cell_a.n_count-1, cell_a.index, cell_a.cell_links[cell_a.n_count-1])

    # DEBUG -------------------------------------------------------------------------- '''

    # printf("\n\nTOTAL CELLS -> [%d]", cell_count)
    # printf("\nTOTAL LINKS -> [%d]", n_links)

    # for cell_idx in range(cell_count):
    #     printf("\nCYTHON CELL [%d]", cell_idx)
    #     cell_a = cells[cell_idx]
    #     for i in range(cell_a.v_count):
    #         printf("\n\t> Vertex %d: [%.2f, %.2f, %.2f]", i, cell_a.vertices[i][0], cell_a.vertices[i][1], cell_a.vertices[i][2])

    with nogil:
        for i in prange(n_links):
            cell_link_distances[i] = -1.0

        for cell_idx in prange(cell_count):
            cell_a = cells[cell_idx]

            if cell_a.n_count == 0:
                # printf("\n> SKIPPING Cell-Index[%d]", cell_a.index)
                continue

            # printf("\n\nCell-Index[%d]", cell_a.index)
            # printf("\n\t> V-Count: %d", cell_a.v_count)
            # printf("\n\t> E-Count: %d", cell_a.e_count)
            # printf("\n\t> N-Count: %d", cell_a.n_count)

            for cell_n_idx in range(cell_a.n_count):
                other_cell_idx = cell_a.cell_links[cell_n_idx]
                # if other_cell_idx >= cell_count or other_cell_idx < 0:
                #     continue

                cell_b = cells[other_cell_idx]

                # Different Collections / Sources?
                if cell_a.coll_index != cell_b.coll_index:
                    # printf("\n\t> Running Edge Method... [%d]", cell_b.index)
                    # EDGE METHOD.
                    for i in range(cell_a.e_count):
                        for j in range(cell_b.e_count):
                            # distance_point_segment # &cell_a.vertices[i*3] # line_line_intersect
                            if dist3D_Segment_to_Segment(
                                &cell_b.vertices[cell_b.edges[j*2]*3],
                                &cell_b.vertices[cell_b.edges[j*2+1]*3],
                                &cell_a.vertices[cell_a.edges[i*2]*3],
                                &cell_a.vertices[cell_a.edges[i*2+1]*3]) < distance_threshold:
                                # if cell_a.index == 0:
                                #     printf("\n\nDistance A[%d]-B[%d]: %.4f m", cell_a.index, cell_b.index, d)
                                #     debug_points(
                                #         &cell_b.vertices[cell_b.edges[j*2]*3],
                                #         &cell_b.vertices[cell_b.edges[j*2+1]*3],
                                #         &cell_a.vertices[i*3]
                                #     )
                                # printf("\n\t> [Edge] Neighbor! -> [%d]-[%d]", cell_a.index, cell_b.index)
                                cell_link_distances[cell_a.links_start + cell_n_idx] = distance_between(cell_a.origin, cell_b.origin)
                                break
                        else:
                            continue
                        break

                else:
                    # VERT METHOD.
                    # printf("\n\t> Running Vert Method... [%d]", cell_b.index)
                    for i in range(cell_a.v_count):
                        for j in range(cell_b.v_count):
                            if distance_between(&cell_a.vertices[i*3], &cell_b.vertices[j*3]) < distance_threshold:
                                # printf("\n\t> [Vert] Neighbor! -> [%d]-[%d]", cell_a.index, cell_b.index)
                                cell_link_distances[cell_a.links_start + cell_n_idx] = distance_between(cell_a.origin, cell_b.origin)
                                break
                        else:
                            continue
                        break

    for i in range(n_links):
        output[i] = cell_link_distances[i]
    PyMem_Free(cell_link_distances)
    return output
