from bpy.types import PropertyGroup
from bpy.props import StringProperty, FloatVectorProperty, FloatProperty, BoolProperty, IntProperty, CollectionProperty, EnumProperty
from ..addon.naming import RBDLabNaming

class Velocity(PropertyGroup):
    name: StringProperty(default="")
    frame: IntProperty(default=-1)
    speed: FloatProperty(default=0)


class Motion(PropertyGroup):
    index: IntProperty(default=0)
    velocities: CollectionProperty(type=Velocity)
    range: FloatVectorProperty(default=(-1, -1), size=2)
    # medium_speed: FloatProperty(default=0)

    def set_motion_range(self, frame_start: int, frame_end: int):
        self.range[0] = frame_start
        self.range[1] = frame_end

    def add_velocity(self, frame: int, speed: float) -> Velocity:
        vel: Velocity = self.velocities.add()
        vel.frame = frame
        vel.speed = speed
        vel.name = str(frame)
        # self.medium_speed = sum([vel.speed for vel in self.velocities]) / len(self.velocities)
        return vel

    def get_velocity(self, frame: int) -> float:
        return self.velocities.get(str(frame), 0)
        # for vel in self.velocities:
        #     if vel.frame == frame:
        #         return vel.speed
        # return 0

    def reset_velocities(self):
        for vel in self.velocities:
            vel.speed = 0
            vel.frame = -1

    def clear_velocities(self):
        self.velocities.clear()

    def clear(self):
        self.clear_velocities()
        self.range = (-1, -1)


class RBDLabObjectData(PropertyGroup):
    """ object.rbdlab.x """

    broken_at_frame: IntProperty(default=-1)
    # Cuando ha cumplido la condicion del distance threshold para las particulas:
    ok_distance_threshold: BoolProperty(default=False)

    motions: CollectionProperty(type=Motion)

    def add_motion(self, frame_start: int, frame_end: int) -> Motion:
        motion: Motion = self.motions.add()
        motion.index = len(self.motions)
        motion.set_motion_range(frame_start, frame_end)
        return motion

    def clear_motions(self):
        for motion in self.motions:
            motion.clear_velocities()
        self.motions.clear()

    @property
    def has_motions(self) -> bool:
        return len(self.motions) > 0
    
    
    ################################################################################################
    # Physics > [GROUND, RBD] > Collision Collections:

    @staticmethod
    def rbd_collections_update(self, context, from_target):

        def change_status(ob, from_property):
            for i, collection in enumerate(ob.rigid_body.collision_collections):
                ob.rigid_body.collision_collections[i] = str(i + 1) in from_property
        
        scn = context.scene
        rbdlab = scn.rbdlab

        # Si se llama desde RBD:
        if from_target == 'rbd_collections':
            tcoll_list = rbdlab.lists.target_coll_list
            chunks = tcoll_list.get_current_active_tcoll_valild_objects(context)
            for chunk in chunks:
                if not chunk.rigid_body:
                    continue
                change_status(chunk, self.rbd_collections)
        
        # Si se llama desde GROUND:
        elif from_target == 'rbd_ground_collections':
            ground = next((ob for ob in context.scene.objects if RBDLabNaming.GROUND in ob), None)
            if ground and ground.rigid_body:
                change_status(ground, self.rbd_ground_collections)

    
    items = [
            ('1',   "1",    ""),
            ('2',   "2",    ""),
            ('3',   "3",    ""),
            ('4',   "4",    ""),
            ('5',   "5",    ""),
            None,
            ('6',   "6",    ""),
            ('7',   "7",    ""),
            ('8',   "8",    ""),
            ('9',   "9",    ""),
            ('10',  "10",   ""),
            None,
            ('11',  "11",   ""),
            ('12',  "12",   ""),
            ('13',  "13",   ""),
            ('14',  "14",   ""),
            ('15',  "15",   ""),
            None,
            ('16',  "16",   ""),
            ('17',  "17",   ""),
            ('18',  "18",   ""),
            ('19',  "19",   ""),
            ('20',  "20",   ""),
        ]
   
    rbd_collections: EnumProperty(
        name="Collections",
        description="RigidBody Collections",
        items=items,
        options={'ENUM_FLAG'},
        default={'1'},
        update=lambda self, context: self.rbd_collections_update(self, context, 'rbd_collections')
    )
    rbd_ground_collections: EnumProperty(
        name="Collections",
        description="RigidBody Collections",
        items=items,
        options={'ENUM_FLAG'},
        default={'1'},
        update=lambda self, context: self.rbd_collections_update(self, context, 'rbd_ground_collections')
    )

    # Boolean Fracture GN:
    def bf_gn_distribution_type_update(self, context):
        scn = context.scene
        rbdlab = scn.rbdlab

        bfracture_gn_list = rbdlab.lists.bfracture_gn_list
        GN_ob = bfracture_gn_list.get_base_plane

        if not GN_ob:
            return
        
        GN_mod = GN_ob.modifiers.get(RBDLabNaming.BOOLFRACTURE_GN_OB)
        if not GN_mod:
            return
            
        if GN_ob.rbdlab.bf_gn_distribution_type == 'RANDOM':
            mode = 'DENSITY_RANDOM'
        elif GN_ob.rbdlab.bf_gn_distribution_type == 'GRID':
            mode = 'DENSITY_GRID'

        GN_mod.node_group.nodes['Distribute Points in Volume'].mode = mode


    bf_gn_distribution_type: EnumProperty(
        name="Distribution",
        description="Distribution Type",
        items=[
                ('RANDOM', "Random", ""),
                ('GRID', "Grid", ""),
        ],
        # default='GRID',
        default='RANDOM',
        update=bf_gn_distribution_type_update
    )

    def bf_gn_thickness_update(self, context):
        scn = context.scene
        rbdlab = scn.rbdlab

        bfracture_gn_list = rbdlab.lists.bfracture_gn_list

        # bool_planes = bfracture_gn_list.get_bool_planes
        bool_planes = bfracture_gn_list.get_all_bool_planes
        if not bool_planes:
            return

        for plane in bool_planes:
            mod = plane.modifiers.get(RBDLabNaming.SOLIDIFY_MOD)
            if mod:
                mod.thickness = self.bf_gn_thickness

    bf_gn_thickness: FloatProperty(name="Thickness", default=0.001, precision=3, subtype='DISTANCE', update=bf_gn_thickness_update)
    
    def bf_gn_wire_solid_update(self, context):

        # scn = context.scene
        # rbdlab = scn.rbdlab

        # bfracture_gn_list = rbdlab.lists.bfracture_gn_list
        # objects_to_fracture = bfracture_gn_list.get_objects_to_fracture

        # if not objects_to_fracture:
        #     return

        # for ob in objects_to_fracture:
        #     if self.bf_gn_wire_solid:
        #         ob.display_type = 'WIRE'
        #     else:
        #         ob.display_type = 'TEXTURED'

        context.space_data.shading.type = 'SOLID' if self.bf_gn_wire_solid else 'WIREFRAME'
        # # Forzar la actualización del viewport
        # import bpy
        # bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)

    bf_gn_wire_solid: BoolProperty(default=False, update=bf_gn_wire_solid_update)


    def metalsoft_remesh_toggle_wireframe_ob_update(self, context):
        ob = context.active_object
        ob.show_wire = self.metalsoft_remesh_toggle_wireframe_ob

    metalsoft_remesh_toggle_wireframe_ob: BoolProperty(
                                                name="Show/Hide Wireframe",
                                                description="Show/Hide Wireframe in active object",
                                                default=False, 
                                                update=metalsoft_remesh_toggle_wireframe_ob_update
                                                )