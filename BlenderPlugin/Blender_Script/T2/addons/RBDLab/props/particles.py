import bpy
from bpy.types import PropertyGroup, Collection
from bpy.props import StringProperty, BoolProperty, FloatProperty, IntProperty, PointerProperty, EnumProperty, FloatVectorProperty
from ..addon.naming import RBDLabNaming


class RBDLab_PG_particles_add_props(PropertyGroup):
    ''' CREATE PARTICLES OPERATOR PROPERTIES/SETTINGS. '''
    options: EnumProperty(
        items=(
            ('BROKEN', "Broken", "Wheter the chunk is broken based in the distance threshold / separation with neighboring chunks"),
            ('MOTION', "Motion", "Whether the chunk surpasses the velocity threshold")
        ),
        default={'BROKEN', 'MOTION'},
        options={'ENUM_FLAG'}
    )

    @property
    def ps_count(self) -> int:
        return self.max_ps_count if self.limit_ps_per_chunk else 10

    @property
    def use_broken(self) -> bool:
        return 'BROKEN' in self.options

    @property
    def use_motions(self) -> bool:
        return 'MOTION' in self.options

    distance_threshold: FloatProperty(
        name="Distance Threshold",
        description="If the chunk is separated this distance (in meters) from any neighbor chunk it will emit particles at the time the separation is performed",
        min=0.01, max=10, soft_max=1, default=0.15, unit='LENGTH', update=lambda self,
        ctx: setattr(self, "force_update_broken_motion", True))

    velocity_threshold: FloatProperty(
        name="Velocity Threshold",
        description="Velocity threshold (in m/s). If the chunk velocity exceeds this threshold, will start emitting particles",
        default=0.4,
        min=0,
        soft_min=0.01,
        soft_max=10,
        unit='VELOCITY',
        max=1000,
        update=lambda self,
        ctx: setattr(self, "force_update_broken_motion", True))

    condition: EnumProperty(
        name="Condition",
        description="Condition to be used to determine whether the velocity is greater or less than the thresold",
        items=[
            ('GREATER_THAN',    ">", "", 0),
            ('LESS_THAN',       "<", "", 1),
        ],
        default='GREATER_THAN'
    )

    limit_ps_per_chunk: BoolProperty(
        name="Limit PS Per Chunk",
        description="Limit Particle System Count per Chunk. Disable means unlimited ParticleSystems",
        default=True
    )

    max_ps_count: IntProperty(
        name="Max PS",
        description="Max Particle System Count per Chunk (mainly used for different chunk motions)",
        default=1,
        min=1,
        max=5,
    )

    by_selection: BoolProperty(
        default=False,
        description="Emit particles by selected chunks"
    )

    frame_step: IntProperty(
        name="Frame Step",
        description="Number of frames to skip forward while calculating brokens/motions each frame",
        default=2,
        min=1,
        soft_max=5,
        max=10
    )

    force_update_broken_motion: BoolProperty(default=False)


class RBDLab_PG_particles_common:
    ################################################
    ''' CREATE PARTICLES OPERATOR PROPERTIES/SETTINGS. '''
    create: PointerProperty(type=RBDLab_PG_particles_add_props)

    frame_offset: IntProperty(
        name="Frame Offset",
        description="Apply an offset to the particle emission",
        default=0,
        soft_min=-15,
        soft_max=15
    )

    ################################################

    def filter_coll_debris(self, object):
        blacklist_collections = ["RigidBodyConstraints", "RigidBodyWorld"]

        if object.name not in blacklist_collections:
            if "_GlueConstraints" in object.name:
                return False
            else:
                return True
        else:
            return False

    ''' New neighbor system
    use_broken: BoolProperty(
        default=False,
        description="use broken constraint detection to emit only from detached chunks"
    )

    broken_threshold: FloatProperty(
        default=0.005,
        min=0.0,
        precision=6,
        # if in your last frame the chunks are very far apart, you will have to raise this value more if you want to decrease chunks.
        description="Broken Threshold (high values, less chunks to evaluate)",
        subtype='DISTANCE',
        unit='LENGTH'
    )
    '''

    max_particle_systems: IntProperty(
        default=1,
        min=0,
        description="For each detected movement a new particle system is generated. This is the maximum number of particle systems per chunk allowed (using 0 for unlimited)."
    )

    range_in: IntProperty(
        default=0,
        description="the start of the range to calculate the motions in this range"
    )

    range_out: IntProperty(
        default=250,
        description="the end of the range to calculate the motions in this range"
    )

    speed_threshold: FloatProperty(
        default=0.05,
        min=0.000,
        precision=6,
        unit='VELOCITY',
        description="the threshold that will determine whether there has been a motion or not"
    )

    # properties on created particles
    count: IntProperty(
        name="Count",
        description="Total number of particles",
        default=20
    )
    ''' New neighbor system
    offset: IntProperty(
        name="Offset",
        description="Offset",
        min=-10, max=10, default=0,
    )
    '''
    use_dead: BoolProperty(
        default=False,
        description="Show particles after they have died"
    )
    show_instancer_for_render: BoolProperty(
        name="Show Emitter",
        description="Show Emitter in render",
        default=False
    )
    # render size:
    particle_size: FloatProperty(
        min=0.001,
        default=0.2,
        precision=3
    )
    size_random: FloatProperty(
        name="Size Random",
        description="Give the particle size a random variation (Only in render)",
        default=1.0,
        min=0.0,
        max=1.0
    )
    use_rotation: BoolProperty(
        default=True
    )
    random_phase: FloatProperty(
        default=2.0
    )
    dynamic: BoolProperty(
        default=True
    )
    seed: IntProperty(
        default=0,
    )
    # display_method: EnumProperty(
    #     items=(
    #         ('NONE', "None", "", 0),
    #         ('RENDER', "Render", "", 1),
    #         ('DOT', "Point", "", 2),
    #         ('CIRC', "Circ", "", 3),
    #         ('CROSS', "Cross", "", 4),
    #         ('AXIS', "Axis", "", 5)
    #     ),
    #     name="Display Method",
    #     description="How particles are displayed in viewport",
    #     default='RENDER'
    # )
    display_method: EnumProperty(
        items=(
            ('DOT', "Point", "", 0),
            ('RENDER', "Render", "", 1),
            ('NONE', "Nothing", "", 2),
        ),
        name="Display Method",
        description="How particles are displayed in viewport",
        default='RENDER'
    )
    display_color: EnumProperty(
        name="Display Color",
        items=(
            ('NONE', "None", "", 0),
            ('MATERIAL', "Material", "", 1),
            ('VELOCITY', "Velocity", "", 2),
            ('ACCELERATION', "Acceleration", "", 3),
        ),
        default='MATERIAL'
    )
    # viewport size:
    display_size: FloatProperty(
        name="Particle Size",
        description="The size of the particles (in Viewport and Render)",
        # description="Size of particles on viewport",
        default=0.1,
        min=0,
        unit='LENGTH',
    )
    show_instancer_for_viewport: BoolProperty(
        name="Show Emitter",
        description="Show Emitter in viewport",
        default=False
    )
    normal: FloatProperty(
        default=0.5,
        min=0,
        unit='VELOCITY'
    )
    direction: FloatVectorProperty(
        name="",
        description="",
        default=(0.0, 0.0, 0.0),
        subtype='VELOCITY'
    )
    object_velocity: FloatProperty(
        # default=0,
        default=0.5,
        soft_min=-1,
        soft_max=1
    )
    velocity_randomize: FloatProperty(
        default=2,
        min=0,
        description="Velocity Randomize"
    )
    timestep: FloatProperty(
        name="Timestep",
        description="The simulation timestep per frame (seconds per frame)",
        default=0.04,
        soft_min=0.01,
        soft_max=10.0,
        precision=3
    )
    subframes: IntProperty(
        name="Subframes",
        description="Subframes to simulate for improved stability and finer granularity simulations (dt = timestep / (subframes+1))",
        min=0,
        # default=0,
        default=1,
        max=1000
    )
    use_multiply_size_mass: BoolProperty(default=False)

    use_rotations: BoolProperty(
        default=True,
        description="Calculate particle rotations."
    )
    # use_size_deflect: BoolProperty(
    #     default=False
    # )
    # use_die_on_collision: BoolProperty(
    #     default=False
    # )
    # collision_collection: PointerProperty(
    #     name="Collision Collection",
    #     description="Liimt colliders to this collection",
    #     type=Collection,
    # )
    rotation_mode: EnumProperty(
        items=(
            ('NONE', "None", "", 0),
            ('NOR', "Normal", "", 1),
            ('NOR_TAN', "Normal-Tangent", "", 2),
            ('VEL', "Velocity / Hair", "", 3),
            ('GLOB_X', "Global X", "", 4),
            ('GLOB_Y', "Global Y", "", 5),
            ('GLOB_Z', "Global Z", "", 6),
            ('OB_X', "Object X", "", 6),
            ('OB_Y', "Object Y", "", 6),
            ('OB_Z', "Object Z", "", 6),
        ),
        name="Orientation Axis",
        description="Particle orientation axis (does not affect Explode modifier's result):",
        default='VEL'
    )
    rotation_factor_random: FloatProperty(
        min=0,
        max=1,
        default=1,
        description="Randomize particle orientation."
    )
    phase_factor: FloatProperty(
        min=-1,
        max=1,
        default=0,
        description="Randomize rotation around the chosen axis."
    )
    phase_factor_random: FloatProperty(
        min=0,
        max=2,
        default=0,
        description="Calculate particle rotations."
    )
    use_dynamic_rotation: BoolProperty(
        default=False,
        description="Calculate particle rotations."
    )
    lifetime: FloatProperty(
        min=1.0,
        default=8
    )
    lifetime_random: FloatProperty(
        min=0,
        max=1
    )
    enable_end_trails: BoolProperty(
        name="Use End Trails",
        default=False,
        description="When it starts to emit for some movement, I can limit the number of frames it will continue to emit, or it will stop emitting when the movement is finished"
    )
    end_trails: IntProperty(
        # default=5,
        # default=10,
        default=1,
        min=1,
        description="Limit the maximum number of frames it will continue to emit particles while are in motion"
    )
    debris_coll: PointerProperty(
        type=Collection,
        poll=filter_coll_debris
    )
    # Field Weights #################################################
    #################################################################
    effector_weights_collection: PointerProperty(
        name="Effector Colelction",
        description="Limit effectors to this collection",
        type=Collection,
    )
    all: FloatProperty(
        min=0,
        max=1,
        default=1
    )
    gravity: FloatProperty(
        min=0,
        max=1,
        default=1
    )
    force: FloatProperty(
        min=0,
        max=1,
        default=1
    )
    vortex: FloatProperty(
        min=0,
        max=1,
        default=1
    )
    magnetic: FloatProperty(
        min=0,
        max=1,
        default=1
    )
    harmonic: FloatProperty(
        min=0,
        max=1,
        default=1
    )
    charge: FloatProperty(
        min=0,
        max=1,
        default=1
    )
    lennardjones: FloatProperty(
        min=0,
        max=1,
        default=1
    )
    wind: FloatProperty(
        min=0,
        max=1,
        default=1
    )
    curve_guide: FloatProperty(
        min=0,
        max=1,
        default=1
    )
    texture: FloatProperty(
        min=0,
        max=1,
        default=1
    )
    smokeflow: FloatProperty(
        min=0,
        max=1,
        default=1
    )
    turbulence: FloatProperty(
        min=0,
        max=1,
        default=1
    )
    drag: FloatProperty(
        min=0,
        max=1,
        default=1
    )
    boid: FloatProperty(
        min=0,
        max=1,
        default=1
    )

    def basic_subdivision_type_update(self, context):
        if RBDLabNaming.BASIC_DEBRIS_COLL_NAME in bpy.data.collections:
            for obj in bpy.data.collections[RBDLabNaming.BASIC_DEBRIS_COLL_NAME].objects:
                for mod in obj.modifiers:
                    if mod.type != 'SUBSURF':
                        continue
                    mod.subdivision_type = self.basic_subdivision_type

    def basic_subdivision_level_update(self, context=bpy.context):
        if RBDLabNaming.BASIC_DEBRIS_COLL_NAME in bpy.data.collections:
            for obj in bpy.data.collections[RBDLabNaming.BASIC_DEBRIS_COLL_NAME].objects:
                for mod in obj.modifiers:
                    if mod.type != 'SUBSURF':
                        continue
                    mod.levels = self.basic_subdivision_level
                    mod.render_levels = self.basic_subdivision_level

    def basic_decimate_collapse_update(self, context=bpy.context):
        if RBDLabNaming.BASIC_DEBRIS_COLL_NAME in bpy.data.collections:
            for obj in bpy.data.collections[RBDLabNaming.BASIC_DEBRIS_COLL_NAME].objects:
                for mod in obj.modifiers:
                    if mod.type != 'DECIMATE':
                        continue
                    mod.ratio = self.basic_decimate_collapse

    def basic_disp_strength_update(self, context):
        if RBDLabNaming.BASIC_DEBRIS_COLL_NAME in bpy.data.collections:
            for obj in bpy.data.collections[RBDLabNaming.BASIC_DEBRIS_COLL_NAME].objects:
                for mod in obj.modifiers:
                    if mod.type != 'DISPLACE':
                        continue
                    mod.strength = self.basic_disp_strength

    def basic_clouds_size_update(self, context=bpy.context):
        if RBDLabNaming.BASIC_DEBRIS_COLL_NAME in bpy.data.textures:
            texture = bpy.data.textures[RBDLabNaming.BASIC_DEBRIS_COLL_NAME]
            texture.noise_scale = self.basic_clouds_size

    def basic_clouds_depth_update(self, context=bpy.context):
        if RBDLabNaming.BASIC_DEBRIS_COLL_NAME in bpy.data.textures:
            texture = bpy.data.textures[RBDLabNaming.BASIC_DEBRIS_COLL_NAME]
            texture.noise_depth = self.basic_clouds_depth

    def basic_outher_material_update(self, context=bpy.context):
        if self.basic_outher_material in bpy.data.materials:
            material = bpy.data.materials[self.basic_outher_material]
            if RBDLabNaming.BASIC_DEBRIS_COLL_NAME in bpy.data.collections:
                for obj in bpy.data.collections[RBDLabNaming.BASIC_DEBRIS_COLL_NAME].objects:
                    obj.material_slots[0].material = material
                    # obj["rbdlab_basic_outher_material"] = material.name

    def basic_inner_material_update(self, context=bpy.context):
        if self.basic_inner_material in bpy.data.materials:
            material = bpy.data.materials[self.basic_inner_material]
            if RBDLabNaming.BASIC_DEBRIS_COLL_NAME in bpy.data.collections:
                for obj in bpy.data.collections[RBDLabNaming.BASIC_DEBRIS_COLL_NAME].objects:
                    obj.material_slots[1].material = material
                    # obj["rbdlab_basic_inner_material"] = material.name

    basic_subdivision_type: EnumProperty(
        name="Subdivision Type",
        items=(
            ('CATMULL_CLARK', "Catmull-Clark", "", 0),
            ('SIMPLE', "Simple", "", 1),
        ),
        default='SIMPLE',
        update=basic_subdivision_type_update
    )
    basic_subdivision_level: IntProperty(
        name="Subdivision Level",
        min=0,
        max=6,
        default=0,
        update=basic_subdivision_level_update
    )
    basic_decimate_collapse: FloatProperty(
        name="Decimate",
        default=1,
        min=0,
        max=1,
        precision=4,
        update=basic_decimate_collapse_update
    )
    basic_disp_strength: FloatProperty(
        name="Strength",
        min=-100,
        max=100,
        default=0,
        precision=3,
        update=basic_disp_strength_update
    )
    basic_clouds_size: FloatProperty(
        name="Clouds Size",
        min=0.000,
        max=2,
        default=0.25,
        precision=3,
        update=basic_clouds_size_update
    )
    basic_clouds_depth: IntProperty(
        name="Clouds Depth",
        min=0,
        max=24,
        default=2,
        update=basic_clouds_depth_update
    )
    basic_outher_material: StringProperty(
        name="Outher Material",
        default="BasicDebris_Outer_mat",
        update=basic_outher_material_update
    )
    basic_inner_material: StringProperty(
        name="Inner Material",
        default=RBDLabNaming.BASIC_DEBRIS_INNER_MAT,
        update=basic_inner_material_update
    )

    def get_default_properties(self, target_prop):
        for prop in self.bl_rna.properties:
            if prop.identifier == target_prop:
                if hasattr(prop, "default"):
                    return prop.default


class RBDLab_PG_particles_debris(RBDLab_PG_particles_common, PropertyGroup):
    pass


class RBDLab_PG_particles_dust(RBDLab_PG_particles_common, PropertyGroup):
    pass


class RBDLab_PG_particles_smoke(RBDLab_PG_particles_common, PropertyGroup):
    pass


class RBDLab_PG_particles(PropertyGroup):
    ''' Cada collection tiene unas custom properties para reconocer si
        posee o no particulas de cada tipo (debris, dust, smoke).
        • Debris: "has_particles_debris"
    '''
    debris: PointerProperty(type=RBDLab_PG_particles_debris)
    dust: PointerProperty(type=RBDLab_PG_particles_dust)
    smoke: PointerProperty(type=RBDLab_PG_particles_smoke)
