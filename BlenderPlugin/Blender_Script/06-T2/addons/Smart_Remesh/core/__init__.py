"""Field-guided quad remeshing. numpy only,no Blender dependency.
Kept importable outside Blender on purpose,so the algorithm can be tested and
benchmarked against TopoLens without launching Blender at all.
"""
from .mesh import TriMesh
from .remesh import remesh
__all__=["TriMesh", "remesh"]
