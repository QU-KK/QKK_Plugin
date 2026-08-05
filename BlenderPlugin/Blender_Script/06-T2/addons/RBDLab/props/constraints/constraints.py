import bpy

from math import radians
from time import time
from typing import List, Set, Tuple, Union
from colorsys import hsv_to_rgb

# from datetime import datetime
# from collections import defaultdict
from ...ops.constraints.detect import restore_default_neighbors, recalculate_neighbors_for_adjacents

from ...Global.get_common_vars import get_common_vars

from bpy.types import PropertyGroup, Object, Collection
from bpy.props import EnumProperty, StringProperty, FloatVectorProperty, FloatProperty, BoolProperty, IntProperty, PointerProperty, CollectionProperty

import random
from uuid import uuid4

import gpu
from gpu_extras.batch import batch_for_shader

# from ...Global.basics import set_active_object

# from ...Global.math import distance_between
from ...Global.search_methods import search_chunks_by_overlap_sphere, SearchMethod, Vector
from ...Global.functions import deselect_all_objects, set_shading_color
from ..when_updating_property import size_delimiter_small_update, size_delimiter_big_update, contraints_visual_size_update, contraints_visual_size_update, hide_const_coll_in_viewport_update

from ...Global.gpu import TempDrawMeshGroupsManager, SHADER_UNIF_COLOR
from ...addon.naming import RBDLabNaming

from .animations import RBDLab_PG_ConstraintsAnimation
from ..lists.animations.constraints.glue_strength_anim_list import GlueStrengthList
from ..lists.animations.constraints.springs import SpringsList

# from ...ops.constraints.detect import distance_between_object_locations
from ...ops.constraints.detect import calcute_chunks_neighbors


sphere_origins = []


# cluster_colors = []


class Chunk(PropertyGroup):
    object: PointerProperty(type=Object)

    ''' NeighborChunks properties. '''
    distance: FloatProperty(default=100000000)
    angle_diff: FloatVectorProperty(default=(0, 0, 0, 0), size=4)
    # broken_connection: BoolProperty(default=False)


class NeighborChunks(PropertyGroup):
    ''' Property of an Object 'neighbor_chunks'. '''
    # Identifier of the neighbor collection.
    # Used for constraints between collections.
    other_collection_id: StringProperty()

    chunks: CollectionProperty(type=Chunk)

    def count(self) -> int:
        return len(self.chunks)

    def add_neighbor(self, chunk_object: Object, distance: float = 10000) -> Chunk:
        chunk: Chunk = self.chunks.add()
        chunk.object = chunk_object
        chunk.distance = distance
        return chunk

    def get_neighbors(self, use_cluster: bool = False) -> List[Tuple[Object, float]]:
        # FixBug JohN_STARK aircraft_vfx.rar 3.blend:
        # Por alguna razon algunos chunk.object son None, para que no tire error primero se comprueba si no son None:
        if use_cluster:
            return [(chunk.object, chunk.distance) for chunk in self.chunks if chunk.object is not None and RBDLabNaming.CLUSTER_ID in chunk.object]
        return [(chunk.object, chunk.distance) for chunk in self.chunks if chunk.object is not None]

    def get_distances(self, include_indices: bool = False, use_cluster: bool = False) -> List[float]:
        if include_indices:
            if use_cluster:

                # return [(i, chunk.distance) for i, chunk in enumerate(self.chunks) if RBDLabNaming.CLUSTER_ID in chunk.object]
                return [(i, chunk.distance) for i, chunk in enumerate(self.chunks) if chunk.object is not None and RBDLabNaming.CLUSTER_ID in chunk.object]

            return [(i, chunk.distance) for i, chunk in enumerate(self.chunks)]
        return [chunk.distance for chunk in self.chunks]

    def get_n_nearest_neighbors(self, n: int = 1, use_cluster: bool = False) -> List[Tuple[Object, float]]:
        if n >= self.count():
            return self.get_neighbors()
        idx_distances = self.get_distances(include_indices=True, use_cluster=use_cluster)
        idx_distances.sort(key=lambda x: x[1])

        def get_neighbor_data(chunk):
            return (chunk.object, chunk.distance)
        return [get_neighbor_data(self.chunks[idx]) for (idx, dist) in idx_distances[:n]]

    def clear(self) -> None:
        self.chunks.clear()


class Cluster(PropertyGroup):
    id: StringProperty(default="")
    chunks: CollectionProperty(type=Chunk)
    color: FloatVectorProperty(size=3, subtype='COLOR')

    def select_chunks(self, state: bool = True):
        for chunk in self.chunks:
            # chunk.object[RBDLabNaming.CLUSTER_ID] = self.id
            chunk.object.select_set(state)

    def add_chunk(self, chunk_object: Object) -> None:
        chunk_item: Chunk = self.chunks.add()
        chunk_item.object = chunk_object
        chunk_object[RBDLabNaming.CLUSTER_ID] = self.id

    def add_chunks(self, chunk_list: List[Object]) -> None:
        add_chunk_item = self.chunks.add
        for chunk_object in chunk_list:
            chunk_object[RBDLabNaming.CLUSTER_ID] = self.id
            chunk_item = add_chunk_item()
            chunk_item.object = chunk_object

    def get_chunk_objects(self) -> List[Object]:
        return [chunk.object for chunk in self.chunks if chunk.object is not None]

    def clear(self) -> None:
        for chunk in self.chunks:
            if RBDLabNaming.CLUSTER_ID in chunk.object:
                del chunk.object[RBDLabNaming.CLUSTER_ID]
            chunk.object = None
        self.chunks.clear()


class ConstraintCollListItem(PropertyGroup):
    def update_data(self, context):
        print("UPDATE DATA COLLECTION", self.data.name)
        if not self.data:
            context.scene.rbdlab.constraints.remove_coll_list(self)

    def do_remove(self, context):
        if not self.remove:
            return
        self.remove = False
        context.scene.rbdlab.constraints.remove_coll_list(self)
        # rbdlab_const.active_group_index = len(rbdlab_const.group_list)-1

    remove: BoolProperty(default=False, update=do_remove)
    selected: BoolProperty(default=False)
    data: PointerProperty(type=Collection, update=update_data)


# Iconos de colores para los grupos.
coll_item_list = [("SEQUENCE_COLOR_0%s" % idx, " ", "", "SEQUENCE_COLOR_0%s" % idx, idx-1) for idx in range(1, 10)]

# Resolver cambio de nombre del grupo.


def update_group_name(self, context):
    group_names: Set[str] = {group.name for group in context.scene.rbdlab.constraints.group_list if group != self}

    new_name = self.name
    i: int = 1
    while new_name in group_names:
        new_name = self.name + "." + str(i).zfill(3)
        i += 1

    if new_name != self.name:
        # Esto trigea de nuevo un update.
        # Returnar aquí, y el nombre de la collection
        # se actualizará en el siguiente update.
        self.name = new_name
        return

    if self.collection is not None:
        setattr(self.collection, "name", RBDLabNaming.PREFIX_CONST + self.name)


def update_show_clusters(self, ctx):
    if not self.show_clusters:
        return
    self.active_cluster_index = -1
    self.show_clusters = False


class ConstraintGroup(PropertyGroup):
    name: StringProperty(default="Constraint Group", update=update_group_name)
    idname: StringProperty(default="")
    # Define si fue creado por 'COLLECTION', 'SELECTION' o 'CLUSTER'. o 'INTER_CLUSTER'. o 'ADJACENTS'.
    type: StringProperty(name="Group Type", default="")
    chunk_list: CollectionProperty(type=Chunk)
    # Usado para saber cual es el indice del cluster activo.
    # antes el time_to_die  estaba en = 3.0 lo baje a 2.0
    active_cluster_index: IntProperty(default=-1, update=lambda self, ctx: TempDrawMeshGroupsManager.draw_cluster(ctx, 2.0, self.get_active_cluster()))
    cluster_list: CollectionProperty(type=Cluster)  # Usado cuando el type es 'CLUSTER'.
    cluster_select: EnumProperty(  # Selector de cluster. -1 significa TODOS.
        name="Selected Cluster",
        description="Visualize/Select Cluster",
        items=lambda x, y: [(str(idx), "All" if idx == -1 else str(idx), "") for idx in range(-1, len(x.cluster_list))],
        update=lambda x, s: setattr(x, "active_cluster_index", int(x.cluster_select)),
        # options={'ENUM_FLAG'},
    )
    show_clusters: BoolProperty(name="Show Clusters Overlay", default=False, update=update_show_clusters)
    icon: EnumProperty(
        name="Icon",
        items=coll_item_list,
        default='SEQUENCE_COLOR_01'
    )
    collection: PointerProperty(type=Collection)  # Collection que tiene los objetos de constraints.
    
    # guardamos el glue que se utilizaba para luego leerlo, ya que al hacer animations hay conflicto al leerlo:
    glue_strength: FloatProperty(name="Glue Strength", default=420)

    # Constratints > Animation > Glue Strenght:
    glue_strength_list: PointerProperty(type=GlueStrengthList)

    # Constratints > Animation > Springs:
    springs_list: PointerProperty(type=SpringsList)

    def do_remove(self, context):
        if not self.remove:
            return

        scn = context.scene
        rbdlab = scn.rbdlab
        rbdlab_const = rbdlab.constraints
        rbdlab_const.remove_group(self)
        # rbdlab_const.list_index = len(rbdlab_const.list)-1
        self.remove = False

    remove: BoolProperty(default=False, update=do_remove)

    

    def update_selection_state(self, context):
        for const in self.collection.objects:
            if const.parent:
                const.parent.select_set(self.selection)

    selection: BoolProperty(default=False, update=update_selection_state)

    total_constrainst: IntProperty(default=0)

    def select_cluster_by_chunk_update(self, context):
        wm = context.window_manager
        prop_name = "cluster_selected_" + self.idname

        if not self.select_cluster_by_chunk:

            # (para que no salga azul el boton) para hacer el toggle de deselect:
            if prop_name in wm:
                if wm[prop_name] == 0:
                    bpy.ops.object.select_all(action='DESELECT')

            return

        if len(context.selected_objects) == 1:
            target_object = context.selected_objects[0]
            bpy.ops.object.select_all(action='DESELECT')
            current_cluster_group = self.get_active_cluster()

            for cluster in current_cluster_group:
                chunks = cluster.get_chunk_objects()

                if target_object not in chunks:
                    continue

                for obj in chunks:
                    obj.select_set(True)

            if len(context.selected_objects) > 1:
                wm[prop_name] = 1

            # para que no salga azul el boton:
            self.select_cluster_by_chunk = False

        else:
            wm[prop_name] = 0
            print("You just have to have a chunk selected")
            # para que no salga azul el boton:
            self.select_cluster_by_chunk = False

    select_cluster_by_chunk: BoolProperty(
        name="Select Cluster",
        description="From a single chunk selection, we select all other chunks belonging to the same cluster",
        default=False,
        update=select_cluster_by_chunk_update
    )

    def get_active_cluster(self) -> Union[Cluster, List[Cluster]]:
        if self.type != 'CLUSTER':
            return None
        if self.active_cluster_index == -1:
            return [cluster for cluster in self.cluster_list]
        return self.cluster_list[self.active_cluster_index]

    def get_chunks_from_selected_cluster(self) -> List[Object]:
        active_cluster = self.get_active_cluster()
        if not active_cluster:
            print("No active cluster!")
            return None
        if isinstance(active_cluster, list):
            chunks: List[Object] = []
            for cluster in active_cluster:
                chunks += cluster.get_chunk_objects()
            return chunks
        else:
            return active_cluster.get_chunk_objects()

    def get_constraint_objects(self, from_chunks: bool = False, get_const_from_all_groups: bool = False, filtered_chunks: Set[Object] = None) -> Tuple[List[Object], List[Object]]:
        
        if self.type == 'CLUSTER':
            chunks = self.get_chunks_from_selected_cluster()
        else:
            chunks = self.get_chunks()
        
        if not chunks:
            return None, None
        
        group_id = self.idname
        
        if filtered_chunks:
            chunks = [chunk for chunk in chunks if chunk in filtered_chunks]
        
        if from_chunks:

            # No filter by ID (takes all constraint objects from chunks.... from all groups).
            if get_const_from_all_groups:
                # print(1)
                const_objects = [const_ob for chunk in chunks if chunk.children for const_ob in chunk.children
                                if const_ob.rigid_body_constraint and const_ob.type == RBDLabNaming.CONST_TYPE and
                                const_ob[RBDLabNaming.GROUP_ID] == group_id]
            else:
                # print(2) 
                # Filtra por ID del grupo.
                const_objects = [const_ob for chunk in chunks if chunk.children for const_ob in chunk.children if const_ob.rigid_body_constraint and const_ob.type == RBDLabNaming.CONST_TYPE and const_ob[RBDLabNaming.GROUP_ID] == group_id]
        else:

            # from collection.
            if self.type == 'CLUSTER' and self.cluster_select != "-1":
                # print(3)
                # Exclude const objects that are not part of the selected cluster.
                chunks_set: Set[Object] = set(chunks)
                const_objects = [const_ob for const_ob in self.collection.objects if const_ob.rigid_body_constraint and const_ob.type == RBDLabNaming.CONST_TYPE and const_ob.parent in chunks_set and const_ob[RBDLabNaming.GROUP_ID] == group_id]
            else:
                # print(4)
                const_objects = [const_ob for const_ob in self.collection.objects
                                if const_ob.rigid_body_constraint and const_ob.type == RBDLabNaming.CONST_TYPE and
                                const_ob[RBDLabNaming.GROUP_ID] == group_id]
                
        return chunks, const_objects

    def add_cluster(self, custom_id: str = None, custom_color: tuple = None) -> Cluster:
        cluster_item: Cluster = self.cluster_list.add()
        cluster_item.id = custom_id if custom_id else uuid4().hex
        cluster_item.color = custom_color if custom_color else (random.random(), random.random(), random.random())
        return cluster_item

    def remove_cluster(self, cluster: Cluster) -> None:
        pass

    def get_chunks(self) -> List[Object]:
        return [chunk.object for chunk in self.chunk_list if chunk.object is not None]

    def get_chunks_set(self) -> List[Object]:
        return {chunk.object for chunk in self.chunk_list if chunk.object is not None}

    def add_chunk(self, chunk: Object):
        chunk_item = self.chunk_list.add()
        chunk_item.object = chunk

    def add_chunks(self, chunk_list: List[Object]) -> None:
        add_chunk = self.chunk_list.add
        for chunk_ob in chunk_list:
            chunk_item: Chunk = add_chunk()
            chunk_item.object = chunk_ob

    def remove_chunk(self, target_chunk: Object) -> None:
        match_index = -1
        for i, chunk_item in enumerate(self.chunk_list):
            if chunk_item.object == target_chunk:
                match_index = i
                chunk_item.object = None
                break
        if match_index != -1:
            self.chunk_list.remove(match_index)

    def update_visible_state(self, context):
        scn = context.scene
        rbdlab = scn.rbdlab

        if self.visible:
            # Activar visibilidad de constraints si no lo están ya.
            rbdlab.constraints.enable_const_visibility(context)
            set_shading_color(context, shading='WIREFRAME', xray=False)
        else:
            # Desactivar la visibilidad de constraints solo si no hay otros con ojito activo.
            if not any(item_list.visible for item_list in rbdlab.constraints.group_list):
                rbdlab.constraints.disable_const_visibility()
                # por si termino de ver los constraints y pongo wire lo quiero con xray:
                set_shading_color(context, shading='WIREFRAME', xray=True)
                set_shading_color(context, shading='SOLID', xray=False)

    # Cambia su estado de visibilidad,
    # activarlo para mostrar las lineas de constraints a modo de overlay.
    visible: BoolProperty(default=False, name="Show Constraints Overlay", description="Show/Hide Group Constraints", update=update_visible_state)

    def update_enabled(self, context):
        # const_id: str = self.idname
        state: bool = self.enabled
        group_id: str = self.idname
        if not state and self.visible:
            self.visible = False
        for chunk in self.chunk_list:
            if not chunk.object:
                continue
            const_objects = chunk.object.children
            if not const_objects:
                continue
            for const_ob in const_objects:
                if const_ob.type != RBDLabNaming.CONST_TYPE:
                    continue
                rbconst = const_ob.rigid_body_constraint
                if rbconst is None:
                    continue
                if const_ob[RBDLabNaming.GROUP_ID] != group_id:
                    # BUG. We need to skip constraints from other groups...
                    continue
                rbconst.enabled = state

    enabled: BoolProperty(default=True, description="Enable/disable constraints in this group", update=update_enabled)
    
    # para el acrtivators hacer record solo de los que esten con este compute:
    compute: BoolProperty(default=True)

    """ Spring (plasticidad Sfot Constraints) Properties. """
    # Properties para soft constraints guardadas dentro del group
    #------------------------------------------------------------------------------------------
    spring_type: EnumProperty(
        name="Implementation",
        description="Wich implementation of spring to use:",
        items=(
            ('SPRING1', "Blender 2.7",  "Spring implementation used in Blender 2.7. Damping is capped to 1.0", 0),
            ('SPRING2', "Blender 2.8",  "New implementation avalidable snice 2.8", 1),
        ),
        default='SPRING1',
    )

    use_limit_ang_x: BoolProperty(default=False)
    use_limit_ang_y: BoolProperty(default=False)
    use_limit_ang_z: BoolProperty(default=False)

    def limit_ang_both_uniq_update(self, context):
        self.limit_ang_lower_uniq = self.limit_ang_both_uniq * -1
        self.limit_ang_upper_uniq = self.limit_ang_both_uniq

    # Unificados:
    limit_ang_both_uniq:FloatProperty(
        name="Lower Upper Angle Limit",
        description="Lower Upper Limit of axis rotation",
        default=radians(45),
        min=0,
        max=radians(360),
        precision=0,
        subtype='ANGLE',
        update=limit_ang_both_uniq_update
    )

    limit_ang_lowers_uniq: BoolProperty(default=False)
    limit_ang_lower_uniq: FloatProperty(
        name="Lower XYZ Angle Limit",
        description="Lower Limit of XYZ axis rotation",
        default=radians(-45),
        min=radians(-360),
        max=radians(360),
        precision=0,
        subtype='ANGLE',
    )

    limit_ang_x_lower: FloatProperty(
        name="Lower X Angle Limit",
        description="Lower Limit of X axis rotation",
        default=radians(-45),
        min=radians(-360),
        max=radians(360),
        precision=0,
        subtype='ANGLE',
    )
    limit_ang_y_lower: FloatProperty(
        name="Lower Y Angle Limit",
        description="Lower Limit of Y axis rotation",
        default=radians(-45),
        min=radians(-360),
        max=radians(360),
        subtype='ANGLE',
    )
    limit_ang_z_lower: FloatProperty(
        name="Lower Z Angle Limit",
        description="Lower Limit of Z axis rotation",
        default=radians(-45),
        min=radians(-360),
        max=radians(360),
        subtype='ANGLE',
    )

    limit_ang_uppers_uniq: BoolProperty(default=False)
    limit_ang_upper_uniq:FloatProperty(
        name="Upper X Angle Limit",
        description="Upper Limit of X axis rotation",
        default=radians(45),
        min=radians(-360),
        max=radians(360),
        subtype='ANGLE',
    )
    limit_ang_x_upper:FloatProperty(
        name="Upper X Angle Limit",
        description="Upper Limit of X axis rotation",
        default=radians(45),
        min=radians(-360),
        max=radians(360),
        subtype='ANGLE',
    )
    limit_ang_y_upper: FloatProperty(
        name="Upper Y Angle Limit",
        description="Upper Limit of Y axis rotation",
        default=radians(45),
        min=radians(-360),
        max=radians(360),
        subtype='ANGLE',
    )
    limit_ang_z_upper: FloatProperty(
        name="Upper Z Angle Limit",
        description="Upper Limit of Z axis rotation",
        default=radians(45),
        min=radians(-360),
        max=radians(360),
        subtype='ANGLE',
    )

    use_limit_lin_x: BoolProperty(default=False)
    use_limit_lin_y: BoolProperty(default=False)
    use_limit_lin_z: BoolProperty(default=False)

    def limit_lin_both_update(self, context):
        self.limit_lin_lower_uniq = self.limit_lin_both * -1
        self.limit_lin_upper_uniq = self.limit_lin_both

    # Unificados:
    limit_lin_both: FloatProperty(
        name="Lower Upper Limit",
        description="Upper Upper Limit of axis translation",
        default=1,
        min=0,
        unit='LENGTH',
        subtype='DISTANCE',
        update=limit_lin_both_update
    )

    limit_lin_lowers_uniq: BoolProperty(default=False)
    limit_lin_lower_uniq: FloatProperty(
        name="Lower X Limit",
        description="Upper Limit of X axis translation",
        default=-1,
        unit='LENGTH',
        subtype='DISTANCE'
    )
    limit_lin_x_lower: FloatProperty(
        name="Lower X Limit",
        description="Upper Limit of X axis translation",
        default=-1,
        unit='LENGTH',
        subtype='DISTANCE'
    )
    limit_lin_y_lower: FloatProperty(
        name="Lower Y Limit",
        description="Upper Limit of Y axis translation",
        default=-1,
        unit='LENGTH',
        subtype='DISTANCE'
    )
    limit_lin_z_lower: FloatProperty(
        name="Lower Z Limit",
        description="Upper Limit of Z axis translation",
        default=-1,
        unit='LENGTH',
        subtype='DISTANCE'
    )

    limit_lin_x_uppers_uniq: BoolProperty(default=False)
    limit_lin_upper_uniq: FloatProperty(
        name="Upper X Limit",
        description="Upper Limit of X axis translation",
        default=1,
        unit='LENGTH',
        subtype='DISTANCE'
    )
    limit_lin_x_upper: FloatProperty(
        name="Upper X Limit",
        description="Upper Limit of X axis translation",
        default=1,
        unit='LENGTH',
        subtype='DISTANCE'
    )
    limit_lin_y_upper: FloatProperty(
        name="Upper Y Limit",
        description="Upper Limit of Y axis translation",
        default=1,
        unit='LENGTH',
        subtype='DISTANCE'
    )
    limit_lin_z_upper: FloatProperty(
        name="Upper Z Limit",
        description="Upper Limit of Z axis translation",
        default=1,
        unit='LENGTH',
        subtype='DISTANCE'
    )


    use_spring_ang_x: BoolProperty(default=True)
    use_spring_ang_y: BoolProperty(default=True)
    use_spring_ang_z: BoolProperty(default=True)

    springs_stiffness_ang_uniq: BoolProperty(default=False)
    spring_stiffness_ang_uniq: FloatProperty(
        name="Stiffness",
        description="Stiffness Rotational",
        default=10,
        min=0,
        soft_max=100.0,
    )
    spring_stiffness_ang_x: FloatProperty(
        name="X Angle Stiffness",
        description="Stiffness on the X rotational axis",
        default=10,
        min=0,
        soft_max=100.0,
    )
    spring_stiffness_ang_y: FloatProperty(
        name="Y Angle Stiffness",
        description="Stiffness on the Y rotational axis",
        default=10,
        min=0,
        soft_max=100.0,
    )
    spring_stiffness_ang_z: FloatProperty(
        name="Z Angle Stiffness",
        description="Stiffness on the Z rotational axis",
        default=10,
        min=0,
        soft_max=100.0,
    )

    springs_damping_ang_uniq: BoolProperty(default=False)
    spring_damping_ang_uniq: FloatProperty(
        name="Damping",
        description="Damping Rotation",
        default=1,
        min=0,
    )
    spring_damping_ang_x: FloatProperty(
        name="Damping X Angle",
        description="Damping on the X rotation axis",
        default=0.5,
        min=0,
    )
    spring_damping_ang_y: FloatProperty(
        name="Damping Y Angle",
        description="Damping on the Y rotation axis",
        default=0.5,
        min=0,
    )
    spring_damping_ang_z: FloatProperty(
        name="Damping Z Angle",
        description="Damping on the Z rotation axis",
        default=0.5,
        min=0,
    )

    use_spring_x: BoolProperty(default=True)
    use_spring_y: BoolProperty(default=True)
    use_spring_z: BoolProperty(default=True)

    springs_stiffness_uniq: BoolProperty(default=False)
    spring_stiffness_uniq: FloatProperty(
        name="Stiffness",
        description="Linear Stiffness",
        default=10,
        min=0,
        soft_max=100.0,
    )
    spring_stiffness_x: FloatProperty(
        name="X Axis Stiffness",
        description="Stiffness on the X axis",
        default=10,
        min=0,
        soft_max=100.0,
    )
    spring_stiffness_y: FloatProperty(
        name="Y Axis Stiffness",
        description="Stiffness on the Y axis",
        default=10,
        min=0,
        soft_max=100.0,
    )
    spring_stiffness_z: FloatProperty(
        name="Z Axis Stiffness",
        description="Stiffness on the Z axis",
        default=10,
        min=0,
        soft_max=100.0,
    )

    springs_damping_uniq: BoolProperty(default=False)
    spring_damping_uniq: FloatProperty(
        name="Damping",
        description="Linear Damping",
        default=1,
        min=0,
    )
    spring_damping_x: FloatProperty(
        name="Damping X",
        description="Damping on the X axis",
        default=0.5,
        min=0,
    )
    spring_damping_y: FloatProperty(
        name="Damping Y",
        description="Damping on the Y axis",
        default=0.5,
        min=0,
    )
    spring_damping_z: FloatProperty(
        name="Damping Z Angle",
        description="Damping on the Z axis",
        default=0.5,
        min=0,
    )
    # End Spring ------------------------------------------------------------------------------------------
    
    def get_default_properties(self, target_prop):
        for prop in self.bl_rna.properties:
            if prop.identifier == target_prop:
                if hasattr(prop, "default"):
                    return prop.default


    


class RBDLab_PG_Constraints(PropertyGroup):
    """ context.scene.rbdlab.constraints.x """

    animations: PointerProperty(type=RBDLab_PG_ConstraintsAnimation)

    ''' Constraint Work-Group.
        ++++++++++++++++++++++++++++++++++++++++ '''
    list_index: IntProperty(name="Constraint Work-Group", default=0)
    list: CollectionProperty(type=ConstraintCollListItem)

    def init_coll_list(self, context):
        saved_collections = self.get_selected_work_group_collections

        self.list.clear()
        rbdlab = context.scene.rbdlab
        
        if not rbdlab.root_collection:
            return
        
        target_collection = rbdlab.filtered_target_collection

        def add_collections(collections):
            for coll in collections:
            
                if 'RBDLAB' not in coll:
                    continue
            
                coll_list_item = self.list.add()
                coll_list_item.data = coll
            
                if saved_collections:
                    # Cuando hace un RELOAD.
                    # Para recuperar la seleccion anterior.
                    if coll in saved_collections:
                        coll_list_item.selected = True
                elif coll == target_collection:
                    # Cuando se inicializa por primera vez.
                    # Para al menos tener una coleccion seleccionada.
                    coll_list_item.selected = True
        
                add_collections(coll.children)
        
        add_collections(rbdlab.root_collection.children)

    def remove_coll_list(self, target_coll_list_item: ConstraintCollListItem):
        coll_index = -1
        for i, coll_list_item in enumerate(self.list):
            if target_coll_list_item == coll_list_item:
                coll_index = i
                break
        if coll_index != -1:
            self.list.remove(coll_index)

    @property
    def get_work_group_collections(self) -> List[Collection]:
        return [coll_list_item.data for coll_list_item in self.list]
    
    @property
    def get_selected_work_group_collections(self) -> List[Collection]:
        return [coll_list_item.data for coll_list_item in self.list if coll_list_item.selected]

    
    def get_source_collections_item(self, index) -> List[Collection]:
        if 0 <= index < len(self.list):
            return self.list[index]
    

    def group_list_update(self, context):
        scn = context.scene
        rbdlab = scn.rbdlab

        if not self.get_active_group:
            return
        
        coll_to_work = self.get_active_group.collection

        if not coll_to_work:
            return

        rbdlab_const = rbdlab.constraints
        if len(coll_to_work.objects) > 0:

            ob = coll_to_work.objects[0]

            ob_rb_const = ob.rigid_body_constraint
            
            rbdlab_const.breakable = ob_rb_const.use_breaking
            rbdlab_const.disable_collisions = ob_rb_const.disable_collisions
            
            rbdlab_const.constraint_type = ob_rb_const.type

            if "rbdlab_use_glue_strength_random" not in ob:
                rbdlab_const.glue_strength_mode = False
                rbdlab_const.glue_strength = ob_rb_const.breaking_threshold
            else:
                rbdlab_const.glue_strength_mode = True
                if "rbdlab_glue_strength_random_from" in ob:
                    rbdlab_const.glue_strength_range[0] = ob["rbdlab_glue_strength_random_from"]
                if "rbdlab_glue_strength_random_to" in ob:
                    rbdlab_const.glue_strength_range[1] = ob["rbdlab_glue_strength_random_to"]

            rbdlab_const.override_iterations = ob_rb_const.use_override_solver_iterations
            rbdlab_const.iterations = ob_rb_const.solver_iterations

        else:

            # get defaults:
            rbdlab_const.glue_strength_mode = False
            rbdlab_const.breakable = rbdlab_const.get_default_properties("breakable")
            rbdlab_const.disable_collisions = rbdlab_const.get_default_properties("disable_collisions")
            rbdlab_const.glue_strength = rbdlab_const.get_default_properties("glue_strength")
            rbdlab_const.override_iterations = rbdlab_const.get_default_properties("override_iterations")
            rbdlab_const.iterations = rbdlab_const.get_default_properties("iterations")


    ''' Constraint-Groups.
        ++++++++++++++++++++++++++++++++++++++++ '''
    active_group_index: IntProperty(
        name="Constraints Groups",
        default=-1,
        update=group_list_update
    )
    group_list: CollectionProperty(type=ConstraintGroup)
    visible_const: BoolProperty(default=False)
    const_draw_handler = None
    const_draw_data = {"time": 0, "batches": [], "frame": 0, "group_count": 0, "visible_group_count": 0}

    def create_group(self) -> ConstraintGroup:
        group = self.group_list.add()
        group.idname = uuid4().hex
        group.icon = "SEQUENCE_COLOR_0%i" % random.randint(1, 9)
        self.active_group_index = len(self.group_list)-1
        return group

    def remove_group(self, target_group: ConstraintGroup) -> None:
        idx = next((idx for idx, group in enumerate(self.group_list) if group == target_group), None)
        self.group_list.remove(idx)
        self.active_group_index = len(self.group_list)-1

    # LIST:
    @property
    def is_void(self):
        return False if len(self.list) > 0 else True
    
    @property
    def length(self):
        return len(self.list)

    # GROUP LIST:
    @property
    def group_is_void(self):
        return False if len(self.group_list) > 0 else True

    @property
    def group_length(self):
        return len(self.group_list)
    
    @property
    def group_active(self):
        return self.group_list[self.active_group_index]

    @property
    def get_all_constraints_groups(self):
        return [item for item in self.group_list]
    
    @property
    def get_all_computable_constraints(self):

        all_const = set()
        for item in self.group_list:
            if item.compute:
                for const in item.collection.objects:
                    all_const.add(const)

        return list(all_const)

    def draw_constraints(self, context):
        scene = context.scene
        rbdlab_const: RBDLab_PG_Constraints = scene.rbdlab.constraints
        group_count = len(rbdlab_const.group_list)
        if group_count == 0:
            self.disable_const_visibility()
            return
        hue_factor = 1.0 / group_count

        anim_change = scene.frame_current != self.const_draw_data["frame"] and (
            time() - self.const_draw_data["time"] > .1)
        group_change = len(rbdlab_const.group_list) != self.const_draw_data["group_count"] or self.const_draw_data["visible_group_count"] != len(
            [g for g in rbdlab_const.group_list if g.visible])
        if self.const_draw_data["batches"] and not group_change and not anim_change:  # and\
            # time() - self.const_draw_data["time"] < .1:
            for i, batch in enumerate(self.const_draw_data["batches"]):
                SHADER_UNIF_COLOR.bind()
                SHADER_UNIF_COLOR.uniform_float("color", (*hsv_to_rgb(hue_factor*i, 0.8, 0.9), 1.0))
                batch.draw(SHADER_UNIF_COLOR)
            return

        self.const_draw_data["batches"].clear()
        # start_time = time()
        # depsgraph = context.evaluated_depsgraph_get()
        for i, group in enumerate(rbdlab_const.group_list):
            if not group.visible:
                continue
            if not group.enabled:
                continue
            group_id = group.idname
            # TODO: Código de dibujado de líneas de constraints.
            # TESTS: 500 Chunks y 27 clusters.
            # CODIGO 1: 0.119-0.121 seconds.
            lines = []
            for chunk in group.chunk_list:
                if not chunk.object:
                    continue
                const_objects = chunk.object.children
                if not const_objects:
                    continue
                # parent = ob.parent
                # if parent:
                #    parent = parent.evaluated_get(depsgraph)

                for const_ob in const_objects:
                    if const_ob.type != RBDLabNaming.CONST_TYPE:
                        continue
                    rbconst = const_ob.rigid_body_constraint
                    if rbconst is None:
                        continue
                    if const_ob[RBDLabNaming.GROUP_ID] != group_id:
                        # BUG. We need to skip constraints from other groups...
                        continue
                    # Add Point
                    # object1 = rbconst.object1.evaluated_get(depsgraph)
                    # object2 = rbconst.object2.evaluated_get(depsgraph)
                    # if parent:
                    #    lines.append((object1.matrix_world.translation + parent.matrix_world.translation).to_tuple())
                    #    lines.append((object2.matrix_world.translation + parent.matrix_world.translation).to_tuple())
                    # else:
                    if rbconst.object1 is None:
                        continue
                    if rbconst.object2 is None:
                        continue

                    # Solo se dibujan lineas si los objetos estan en el view layer (si esta en el limbo, no)
                    if rbconst.object1.name in context.view_layer.objects:
                        lines.append(rbconst.object1.matrix_world.translation.to_tuple())
                    
                    if rbconst.object2.name in context.view_layer.objects:
                        lines.append(rbconst.object2.matrix_world.translation.to_tuple())
                    
                # CODIGO 1.2: 0.123-0.125 seconds
                # lines += [f(const_ob) for const_ob in const_objects if ok_const_ob(const_ob) for f in (f1, f2)]
            '''
            # CODIGO 2: 0.13 seconds
            ok_const_ob = lambda const_ob: const_ob.type == RBDLabNaming.CONST_TYPE and const_ob.rigid_body_constraint is not None
            f1 = lambda const_ob: const_ob.rigid_body_constraint.object1.matrix_world.translation.to_tuple()
            f2 = lambda const_ob: const_ob.rigid_body_constraint.object2.matrix_world.translation.to_tuple()
            ok_const_ob = lambda const_ob: const_ob.type == RBDLabNaming.CONST_TYPE and const_ob.rigid_body_constraint is not None
            f1 = lambda const_ob: const_ob.rigid_body_constraint.object1.matrix_world.translation.to_tuple()
            f2 = lambda const_ob: const_ob.rigid_body_constraint.object2.matrix_world.translation.to_tuple()
            # chunks: List[Object] = group.get_chunks()
            lines: Tuple[Tuple[float, float, float]] = tuple(f(const_ob) for chunk in group.chunk_list if chunk.object for const_ob in chunk.object.children if ok_const_ob(const_ob) for f in (f1, f2))
            '''
            # print("[TIME] Draw Lines Calc -> %.4f" % (time()-start_time))
            # start_time = time()
            batch = batch_for_shader(SHADER_UNIF_COLOR, 'LINES', {"pos": lines})
            SHADER_UNIF_COLOR.bind()
            SHADER_UNIF_COLOR.uniform_float("color", (*hsv_to_rgb(hue_factor*i, 0.8, 0.9), 1.0))
            batch.draw(SHADER_UNIF_COLOR)

            # Cache batch.
            self.const_draw_data["batches"].append(batch)
            # print("[TIME] Draw Lines Batcher -> %.4f" % (time()-start_time))

        self.const_draw_data["time"] = time()
        self.const_draw_data["frame"] = scene.frame_current
        # self.const_draw_data["subframe"] = scene.frame_subframe
        self.const_draw_data["group_count"] = len(rbdlab_const.group_list)
        self.const_draw_data["visible_group_count"] = len([g for g in rbdlab_const.group_list if g.visible])

    def enable_const_visibility(self, context) -> None:
        # Ya están visibles!
        if self.visible_const:
            return
        self.const_draw_data["batches"].clear()
        self.const_draw_data["group_count"] = 0
        # Empezamos un draw handler que muestre
        # los overlays en el viewport 3d.
        from bpy.types import SpaceView3D
        bpy.rbdlab_const_draw_handler = SpaceView3D.draw_handler_add(
            self.draw_constraints, (context,), 'WINDOW', 'POST_VIEW')
        self.visible_const = True
        print("Activando dibujado...", bpy.rbdlab_const_draw_handler)

    def disable_const_visibility(self) -> None:
        # Ya están desactivadas.
    
        # print("Desactivando dibujado...", bpy.rbdlab_const_draw_handler)

        # me daba este error:
        # AttributeError: 'RBDLab_PG_Constraints' object has no attribute 'visible_const'
        try:
            if not hasattr(self, "visible_const"):
                return
        except AttributeError as e:
            print("Error: {}".format(e))
            return

        if not self.visible_const:
            return
        if bpy.rbdlab_const_draw_handler is None:
            return
        self.const_draw_data["batches"].clear()
        self.const_draw_data["group_count"] = 0
        # Skip si hay algun grupo con la visibilidad activa.
        for group in self.group_list:
            if group.visible:
                return    
        # Quitar el draw handler.
        from bpy.types import SpaceView3D
        SpaceView3D.draw_handler_remove(bpy.rbdlab_const_draw_handler, 'WINDOW')
        bpy.rbdlab_const_draw_handler = None
        self.visible_const = False

    @property
    def get_active_group(self) -> ConstraintGroup:
        # print(self.active_group_index, len(self.group_list))
        
        if self.active_group_index == -1:
            return None
        if self.active_group_index >= len(self.group_list):
            return None
        return self.group_list[self.active_group_index]
    
    def get_group_item_by_name(self, target_name) -> ConstraintGroup:

        if self.active_group_index == -1:
            return None
        
        for item in self.group_list:
            if not item.collection:
                return None
            
            if item.collection.name == target_name:
                return item
    
    def get_group_name_by_idname(self, idname:str):
        return next((group.name for group in self.group_list if group.idname == idname), None)
    
    def get_group_by_idname(self, idname:str):
        return next((group for group in self.group_list if group.idname == idname), None)
    
    def get_chunks_from_group(self, index: int = -1) -> List[Object]:
        if index == -1:
            group = self.get_active_group
            if group is None:
                return None
        else:
            if index >= len(self.group_list):
                return None
            group = self.group_list[index]
        return group.get_chunks()

    def remove_chunk_from_constraint_groups(self, chunk: Object) -> None:
        for group in self.group_list:
            group.remove_chunk(chunk)

    ''' Indices para los grupos de constraints.
        ++++++++++++++++++++++++++++++++++++++++ '''
    max_group_index: IntProperty(default=0)

    ###

    ''' Aquí guardamos los clusters al ejecutar la busqueda.
        ++++++++++++++++++++++++++++++++++++++++ '''
    clusters: CollectionProperty(type=Cluster)

    def clear_clusters(self):
        for cluster in self.clusters:
            cluster.clear()
        self.clusters.clear()

    def execute_search(self, context, recalc_sphere_origin: bool = False):
        rbdlab = context.scene.rbdlab
        rbdlab_const = rbdlab.constraints
        coll_workgroup = rbdlab_const.get_selected_work_group_collections

        # Limpiar colecciones de clusters.
        self.clear_clusters()

        if self.search_over_selection:
            chunk_list = context.scene.rbdlab.get_selected_chunks_from_collections(coll_workgroup)
        else:
            chunk_list = context.scene.rbdlab.get_chunks_from_collections(coll_workgroup)
        if not chunk_list or len(chunk_list) <= self.cluster_min_chunks:
            return
        chunk_list = [chunk for chunk in chunk_list if RBDLabNaming.CLUSTER_ID not in chunk]

        chunk_list_redux = chunk_list  # deepcopy(chunk_list)

        # Creamos un draw manager para dibujar los overlays...
        # En caso de ya existir uno, se pararía automáticamente.
        temp_draw_manager = TempDrawMeshGroupsManager(context)

        if not self.search_over_selection:
            deselect_all_objects(context)

        global sphere_origins
        sphere_radius = self.search_radius
        # global cluster_colors

        if recalc_sphere_origin or not sphere_origins:  # or not cluster_colors
            sphere_origins = [Vector((0, 0, 0))] * self.cluster_count
            # cluster_colors = [(1, 1, 1, 1)] * self.cluster_count

        method = getattr(SearchMethod, self.clusters_search_method, SearchMethod.AUTO)
        USING_VERTICES_METHOD = method == SearchMethod.VERTICES

        for cluster_n in range(0, self.cluster_count):
            if not chunk_list_redux:
                break
            if self.use_random_search_radius:
                sphere_radius = random.uniform(*self.search_radius_range)

            if recalc_sphere_origin:
                # Get random color.
                # cluster_colors[cluster_n] = (random.random(), random.random(), random.random(), 1.0)

                # Get random chunk from list.
                max_index = len(chunk_list_redux) - 1
                random_index = random.randint(0, max_index)
                # if cluster_n == 0:

                # Si está emparentado, debe moverse con el padre.
                # if USING_VERTICES_METHOD and chunk_list_redux[random_index].parent:
                #    sphere_origins[cluster_n] = chunk_list_redux[random_index].location + chunk_list_redux[random_index].parent.location
                # else:
                #    sphere_origins[cluster_n] = chunk_list_redux[random_index].location

                sphere_origins[cluster_n] = chunk_list_redux[random_index].matrix_world.translation

                # else:
                # while distance_between(sphere_origins[cluster_n-1], chunk_list_redux[random_index].location):
                #    random_index = random.randint(0, max_index)

            # Chunks inside/overlapping the imaginary sphere.
            chunks = search_chunks_by_overlap_sphere(sphere_origins[cluster_n], sphere_radius, chunk_list_redux, method)

            # Verificar que se haya llegado al mínimo de chunks por cluster especificado por el usuario.
            if len(chunks) < self.cluster_min_chunks:
                print("WARN: NOT ENOUGH CHUNKS TO CREATE CLUSTER")
                break

            new_cluster: Cluster = self.clusters.add()
            new_cluster.id = uuid4().hex

            # Setear los chunks y borrarlos de la lista que usará el resto de clusters.
            for chunk in chunks:
                if not self.search_over_selection:
                    chunk.select_set(True)
                # chunk.color = cluster_color
                chunk_list_redux.remove(chunk)
                new_cluster.add_chunk(chunk)

            # Ponemos a dibujar el nuevo grupo.
            temp_draw_manager.add_mesh_group(chunks)

        temp_draw_manager.start_timer(10.0)

        for i, cluster in enumerate(self.clusters):
            cluster.color = temp_draw_manager.colors[i][:3]

        # for i, cluster in enumerate(self.clusters):
        #    print("%i Cluster:" % i)
        #    for chunk in cluster.chunks:
        #        print("\t- Chunk: %s" % chunk.object.name)

    """ Selection Properties. """

    size_delimiter_big: FloatProperty(
        name="size_delimiter_big",
        description="Select chunks that are greater than this value",
        default=30,
        min=0,
        update=size_delimiter_big_update
    )
    size_delimiter_small: FloatProperty(
        name="size_delimiter_small",
        description="Select chunks that are smaller than this value",
        default=20,
        min=0,
        update=size_delimiter_small_update
    )

    """ Cluster-Options Properties. """
    clustering_method: EnumProperty(
        name="Clustering Method",
        items=(
            ('STANDARD', "Standard", "Use spheric shapes to create clusters in random locations over specified chunks"),
            ('VIRUS', "Virus", "Spread clusters randomly along neighbour chunks"),
            ('VORONOI', "Voronoi", "Use voronoi shapes to create clusters")
        ),
        default='STANDARD'
    )

    cluster_count: IntProperty(
        name="Number of clusters",
        description="A high cluster count can impact performance! (cluster count = number of iterations)",
        default=2,
        min=1, soft_max=100,
        update=(lambda x, y: x.execute_search(y, recalc_sphere_origin=True))
    )

    cluster_use_auto_count: BoolProperty(
        name="Use Auto Count",
        default=False,
        update=(lambda x, y: x.execute_search(y, recalc_sphere_origin=True))
    )

    cluster_offset: FloatProperty(
        name="Offset between Clusters",
        default=0.5,
        min=0, soft_max=10,
        subtype='DISTANCE',
        update=(lambda x, y: x.execute_search(y, recalc_sphere_origin=False))
    )

    cluster_min_chunks: IntProperty(
        name="Minimum number of chunks per cluster (Skips clusters with a number of chunks <= the specified number)",
        default=4,
        min=3,
        update=(lambda x, y: x.execute_search(y, recalc_sphere_origin=False))
    )

    """ Cluster-Search Properties. """

    def update_search_execute(self, context):
        if not self.search_execute:
            return
        self.search_execute = False
        self.execute_search(context, True)

    # Fake Operator.
    search_execute: BoolProperty(
        default=False,
        update=update_search_execute
    )

    clusters_search_method: EnumProperty(
        name="Search Method",
        items=(
            ('AUTO', "Automatic", "Use centroid or vertices method depending on performance hit"),
            ('CENTROID', "Centroid", "(Faster) Use the center of the chunks as reference"),
            ('VERTICES', "Vertices", "(Slower) Use every vertice of the chunks as reference")
        ),
        default='AUTO',
        update=(lambda x, y: x.execute_search(y, recalc_sphere_origin=False))
    )

    search_over_selection: BoolProperty(
        name="Search over selection",
        default=False,
        update=(lambda x, y: x.execute_search(y, recalc_sphere_origin=True))
    )

    use_random_search_radius: BoolProperty(
        name="Random search radius",
        description="Enable range of values for search radius",
        default=False,
        update=(lambda x, y: x.execute_search(y, recalc_sphere_origin=False))
    )

    search_radius: FloatProperty(
        name="Search Radius",
        soft_min=0.1, soft_max=50,
        default=1,
        subtype='DISTANCE',
        update=(lambda x, y: x.execute_search(y, recalc_sphere_origin=False))
    )

    search_radius_range: FloatVectorProperty(
        name="Search Radius Range",
        size=2,
        soft_min=0.1, soft_max=50,
        default=(0.5, 2.0),
        unit='LENGTH',
        update=(lambda x, y: x.execute_search(y, recalc_sphere_origin=False))
    )

    """ Cluster-Virus Properties.  """
    # virus : PointerProperty(type=RBDLab_PG_ClusterVirus)

    """ Constraints Properties """
    apply_by: EnumProperty(
        items=(
            ('COLLECTION', "Collections", "By selected source collections", 'OUTLINER_COLLECTION', 0),
            ('SELECTION', "Selection", "By user object selection", 'RESTRICT_SELECT_OFF', 1),
            ('CLUSTER', "Clusters", "By created clusters", 'MOD_BUILD', 2),
        ),
        description="Apply constraints by",
        default='COLLECTION',
        # update=constraint_type_update
    )
    ignore_chunks_with_constraints: BoolProperty(
        default=False,
        name="Ignore Chunks with Constraints",
    )
    constraints_between_chunks: BoolProperty(
        name="Constraints Between Chunks",
        description="Locate the constraints between chunks",
        default=False,
    )

    def filter_adjacents_update(self, context):
        recalculate_neighbors_for_adjacents(context) if self.filter_adjacents else restore_default_neighbors(context)

    filter_adjacents: BoolProperty(
        default=False,
        name="Adjacents",
        description="Create groups based on adjacent chunks between different from objects",
        update=filter_adjacents_update
    )

    # SELECT ADJACENTS POR PROXIMIDAD:
    def threshold_adjacents_selection(self, context):
        # start = datetime.now()

        constraints = get_common_vars(context, get_constraints=True)
        src_collections = constraints.get_selected_work_group_collections

        chunks = [ob for coll in src_collections for ob in coll.objects if ob.type == 'MESH' and "rbdlab_from" in ob and ob.visible_get() and ob.name in context.view_layer.objects]
        if not chunks:
            return 
        
        bpy.ops.object.select_all(action='DESELECT')
        threshold = self.threshold_adjacents_selection
        selected_objects = set()

        ob1_and_froms = { ob1 : ob1.get("rbdlab_from") for ob1 in chunks }
        for ob1, ob1_from in ob1_and_froms.items():            

            for ob2 in chunks:
                
                if ob1 == ob2: 
                    continue

                if ob2 in selected_objects:
                    continue

                if ob1_from == ob2.get("rbdlab_from"):
                    continue

                if Vector(ob1.location - ob2.location).length < threshold:
                    selected_objects.add(ob2)
            
        # Finalmente los selecciono:
        [ob.select_set(True) for ob in selected_objects]
        
        # print("rbdlab.select_adjacents_neighbours End: " + str(datetime.now() - start))

    threshold_adjacents_selection: FloatProperty(
        name="Selector by Distance",
        description="Select chunks with different from objects, by distance",
        default=1, 
        min=0,
        update=threshold_adjacents_selection
    )
    
    # Para recomputar vecinos en panel Constraints Adjacents -----------------------------------------------------------
    neighbors_search_method: EnumProperty(
        name="Neighbor Search Method",
        items=(
            # ('VERT', 'Vertices', "Use nearest vertices. (PRECISE in organic patterns, don't use for brick walls)"),
            ('CYTHON', 'Automatic', "Use automatic method powered by Cython"),
            ('VERT_KDTREE', 'Vertices', "Use nearest vertices. (PRECISE in organic patterns, don't use for brick walls)"),
            # ('EDGE', 'Edges', "Use nearest edges. (SLOWER BUT PRECISE IN ALMOST EVERY CASE)"), # este es muy lento por eso lo desactivo
            # ('DISTANCE', 'Distance', "Use distance between the chunks.")
            ('BBOX', 'Bounding Box', "Use bounding box intersection between the chunks. (FASTEST, really nice for brick walls or similar)")
        ),
        default='CYTHON'
    )
    neighbors_virtual_cube_threshold: FloatProperty(
        min=0.0001, 
        max=0.1, 
        default=0.001, 
        precision=4, 
        step=1 / 1000, 
        name="Neighbors Threshold",
        description="Distance threshold to consider a chunk is neighbor of another chunk"
    )
    # Para poder hacer offset al cubo virtual al calcular vecinos en Constraints > Adjacents:
    bbox_offset_unified_toggle: BoolProperty(default=False)
    bbox_offset_unified: FloatProperty(
        min=0, 
        default=0, 
        name="Bounding Box Offset",
        description="Bounding Box Offset Unified"
    ) 
    bbox_offset_x: FloatProperty(
        min=0, 
        default=0, 
        name="Bounding Box Offset",
        description="Bounding Box Offset X"
    )
    bbox_offset_y: FloatProperty(
        min=0, 
        default=0, 
        name="Bounding Box Offset",
        description="Bounding Box Offset Y"
    )
    bbox_offset_z: FloatProperty(
        min=0, 
        default=0, 
        name="Bounding Box Offset",
        description="Bounding Box Offset Z"
    )
    # End Para recomputar vecinos en panel Constraints Adjacents -------------------------------------------------------
    adjacents_only_between_different_froms: BoolProperty(
        name="Adjacents with different froms",
        description="Adjacents only between different froms objects",
        default=True,
    )
    
    add_inter_clusters: BoolProperty(
        name="Add Inter Clusters",
        description="Add Inter Clusters between clusters",
        default=False
    )

    # Si uso attach to geo desactivo adjacents:
    def const_to_ob_update(self, context):
        if self.const_to_ob:
            self.filter_adjacents = False

    const_to_ob: BoolProperty(
        name="Constraints to single object",
        description="Create constraint from chunks to single object",
        default=False,
        update=const_to_ob_update
    )

    const_per_islands: BoolProperty(
        name="Constraints per islands",
        description="Create constraint per islands",
        default=False,
    )
    def to_ob_choose_original(self, ob):
        # if RBDLabNaming.ORIGINALS in bpy.data.collections:
        #     return ob.name in bpy.data.collections[RBDLabNaming.ORIGINALS].objects
        # else:
        #     return False 
        return True
    
    to_ob_choose: PointerProperty(type=Object, poll=to_ob_choose_original)
    # filter_radius: FloatProperty()

    # Constraints #########################
    const_by_selection: BoolProperty(
        default=False
    )


    def constraint_type_update(self, context):
        if self.constraint_type == 'GENERIC_SPRING':
            scn = context.scene
            rbdlab = scn.rbdlab
            rbdlab.constraints.spring_type = 'SPRING1'
            rbdlab.constraints.use_spring_ang_x = True
            rbdlab.constraints.use_spring_ang_y = True
            rbdlab.constraints.use_spring_ang_z = True
            rbdlab.constraints.use_spring_x = True
            rbdlab.constraints.use_spring_y = True
            rbdlab.constraints.use_spring_z = True


    constraint_type: EnumProperty(
        items=(
            ('FIXED',           "Fixed",    "", 0),
            ('POINT',           "Point",    "", 1),
            ('GENERIC_SPRING',  "Soft",   "", 2)
        ),
        description="Type of Rigid Body Constraint",
        default='FIXED',
        update=constraint_type_update
    )


    breakable: BoolProperty(
        default=True
    )
    disable_collisions: BoolProperty(
        name="Disable Collisions",
        description="Disable Collisions between constrained rigid bodies",
        default=False,
    )

    glue_strength: FloatProperty(
        name="Glue Strength",
        # precision=3,
        default=420
    )
    glue_strength_range: FloatVectorProperty(
        size=2,
        default=(400.0, 1200.0)
    )
    # for constant strength or random range ( in clusters for now ):
    glue_strength_mode: BoolProperty(
        description="Glue Strength mode",
        default=False,
    )
    # glue animable
    glue_anim_by_selection: BoolProperty(
        name="Anim by selection",
        description="Anim constraints by chunks selection",
        default=False
    )
    # Springs animable
    springs_anim_by_selection: BoolProperty(
        name="Anim by selection",
        description="Anim Springs constraints by chunks selection",
        default=False
    )
    # end glue animable
    override_iterations: BoolProperty(
        default=False,
        description="Override Iterations"
    )
    iterations: IntProperty(
        default=100,
        min=1,
        max=1000,
        description="Override Iterations"
    )
    visual_size: FloatProperty(
        # default=0.12,
        default=0.01,
        min=0.01,
        max=100,
        description="Constraints Visual Size",
        update=contraints_visual_size_update
    )
    hide_const_coll_in_viewport: EnumProperty(
        items=(
            ('SHOW', "Show", " "),
            ('HIDE', "Hide", ""),
        ),
        description="Show or Hide Constraints",
        default='HIDE',
        update=hide_const_coll_in_viewport_update
    )

    # Used for adjacent constraints only.
    max_const_dist: FloatProperty(
        name="Search Area",
        min=0,
        soft_max=10,
        max=100,
        default=0.0,
        description="The search area to connect the chunks among them. 0.0 means automatic calculation."
    )
    maximun_constraints: IntProperty(
        name="Maximum connections",
        soft_min=0,
        soft_max=100,
        default=3,
        description="Maximum connections per chunks"
    )

    # Used by new constraints by neighbors.
    limit_neighbor_constraints: BoolProperty(
        name="Limit Constraints",
        description="Clamp the number of constraints to add to each chunk",
        default=True,
    )
    maximun_neighbor_constraints: IntProperty(
        name="Maximum connections",
        min=1,
        soft_max=10,
        default=3,
        description="Maximum connections per chunks"
    )

    def get_default_properties(self, target_prop):
        for prop in self.bl_rna.properties:
            if prop.identifier == target_prop:
                if hasattr(prop, "default"):
                    return prop.default
