import bpy
from bpy.types import PropertyGroup, Property
from bpy.props import StringProperty, BoolProperty, FloatVectorProperty, EnumProperty, IntProperty, FloatProperty, PointerProperty
from ..Global.functions import (
    # get_array_data_from_obj,
    normalize,
)
from ..addon.naming import RBDLabNaming
# Somke properties.


class RBDLab_PG_Smoke_Emiter(PropertyGroup):
    dirt: StringProperty()

    def get_flow_source_items(self, context):
        if self.flow_type == 'LIQUID':
            return (
                ('MESH', "Mesh", "Emit fluid from mesh surface or volume", 'META_CUBE', 0),
            )
        if not context.scene.rbdlab.has_smoke_ps():
            return (
                ('MESH', "Mesh", "Emit fluid from mesh surface or volume", 'META_CUBE', 0),
            )
        return (
            ('MESH', "Mesh", "Emit fluid from mesh surface or volume", 'META_CUBE', 0),
            ('PARTICLES', "Particles", "Emit fluid from particles", 'PARTICLES', 1)
        )

    def update(pg, ctx, ppt):
        if pg.dirt:
            pg.dirt = ("%s %s" % (pg.dirt, ppt))
        else:
            pg.dirt = ppt

        # intento fallido de intentar setear las particulas si existen:
        # print(ctx.object.name)
        # if ctx.object.modifiers[RBDLabNaming.SMOKE_MOD].flow_settings.particle_system is None:
        #     ps_smoke_name = [ps.name for ps in ctx.object.particle_systems if "_smoke_motion_" in ps.name][0]
        #     if ps_smoke_name:
        #         ctx.object.modifiers[RBDLabNaming.SMOKE_MOD].flow_settings.particle_system = ctx.object.particle_systems[ps_smoke_name]

    def update_flow_type(self, context):
        if self.flow_type == 'LIQUID':
            self.flow_source = 'MESH'
        self.update(context, "flow_type flow_source")

    def update_flow_source(self, context):
        if self.flow_source == 'PARTICLES' and not context.scene.rbdlab.has_smoke_ps():
            self.flow_source = 'MESH'
            return
        self.update(context, "flow_source")

    def get_default_properties(self, target_prop):
        for prop in self.bl_rna.properties:
            if prop.identifier == target_prop:
                if hasattr(prop, "default"):
                    return prop.default

    flow_type: EnumProperty(name="Flow Type",
                            description="Change type of fluid in the simulation",
                            items=(
                                 ('SMOKE', "Smoke", "Add smoke", 'VOLUME_DATA', 0),
                                 ('BOTH', "Fire + Smoke", "Add fire and smoke",
                                  'OUTLINER_OB_VOLUME', 1),
                                 ('FIRE', "Fire", "Add fire", 'SEQ_HISTOGRAM', 2),
                                 # ('LIQUID', "Liquid",
                                 # "Add liquid", 'MOD_FLUIDSIM', 3),
                            ),
                            default='SMOKE',
                            # Agregamos flow_source porque el flow_type afecta a este...
                            update=update_flow_type)

    flow_source: EnumProperty(
        name="Flow Source",
        description="Change how fluid is emitted",
        items=get_flow_source_items,
        # default='MESH',
        update=update_flow_source)

    surface_distance: FloatProperty(
        name="Surface Emission",
        description="Controls fluid emission from the mesh surface (higher values results in emission further away from the mesh surface)",
        precision=5, default=0.2, min=0.0, max=10.0,
        update=(lambda x, y: x.update(y, "surface_distance")))

    volume_density: FloatProperty(
        name="Volume Emission",
        description="Controls fluid emission from within the mesh (higher value results in greater emissions from inside the mesh)",
        precision=5, default=0.0, min=0.0, max=1.0,
        update=(lambda x, y: x.update(y, "volume_density")))

    particle_size: FloatProperty(
        name="Particle Size",
        description="Particle size in simulation cells",
        precision=5, default=1.0, min=0.5, max=5.0,
        update=(lambda x, y: x.update(y, "particle_size")))

    subframes: IntProperty(
        name="Sampling Substeps",
        description="Number of additional samples to take between frames to improve quality of fast moving flows",
        default=0, min=0,
        update=(lambda x, y: x.update(y, "subframes")))

    smoke_color: FloatVectorProperty(
        name="Smoke Color",
        description="Color of smoke",
        subtype='COLOR',
        size=3,
        default=(.7, .7, .7), min=0, max=1,
        update=(lambda x, y: x.update(y, "smoke_color")))

    temperature: FloatProperty(
        name="Temp. Diff.",
        description="Temperature difference to ambient temperature",
        precision=1, default=1.0, min=-10.0, max=10.0,
        update=(lambda x, y: x.update(y, "temperature")))

    density: FloatProperty(
        name="Density",
        description="",
        precision=4, default=1.0, min=0.0, max=1.0,
        update=(lambda x, y: x.update(y, "density")))

    # No podemos usar vertex group porque cada chunk tiene sus vertex groups y esto no resultaría en nada...
    # Habría que crear algo más especial y específico con ajustes y operador/es.
    # density_vertex_group: PointerProperty(type=VertexGroup)

    use_initial_velocity: BoolProperty(
        name="Initial Velocity",
        description="Fluid has some initial velocity when it is emitted",
        default=True,
        update=(lambda x, y: x.update(y, "use_initial_velocity")))

    velocity_factor: FloatProperty(
        name="Source",
        description="Multiplier of source velocity passed to fluid (source velocity is non-zero only if object is moving)",
        precision=5, default=1.0, soft_min=-2.0, soft_max=2.0,
        update=(lambda x, y: x.update(y, "velocity_factor")))

    velocity_normal: FloatProperty(
        name="Normal",
        description="Amount of normal directional velocity",
        precision=5, default=0.0, min=-2.0, max=2.0,
        update=(lambda x, y: x.update(y, "velocity_normal")))

    velocity_coord: FloatVectorProperty(
        name="Initial",
        description="Additional initial velocity in X, Y and Z axis (added to source velocity)",
        subtype='XYZ',
        unit='VELOCITY',
        size=3, precision=1, default=(0, 0, 0), min=-1000, max=1000,
        update=(lambda x, y: x.update(y, "velocity_coord")))


class RBDLab_PG_Smoke(PropertyGroup):

    def multiplier_update(self, context, target_type):
        rbdlab = context.scene.rbdlab

        if rbdlab.filtered_target_collection.name:
            coll_name = rbdlab.filtered_target_collection.name
            if coll_name:
                valid_objects = [obj for obj in rbdlab.filtered_target_collection.objects
                                 if obj.type == 'MESH' and obj.visible_get()]

                for obj in valid_objects:
                    flow = rbdlab.get_smoke_emiter(obj)

                    # remove keyframes first:
                    ad = obj.animation_data
                    if ad:
                        action = ad.action
                        if action:
                            fcurves = [fc for fc in action.fcurves if fc.data_path.endswith(target_type)]
                            # remove fcurves
                            while (fcurves):
                                fc = fcurves.pop()
                                action.fcurves.remove(fc)

                    if not flow:
                        continue

                    smoke_mod_name = RBDLabNaming.SMOKE_MOD
                    smoke_mod = None
                    if smoke_mod_name in obj.modifiers:
                        smoke_mod = obj.modifiers[smoke_mod_name]
                    else:
                        continue

                    if not smoke_mod:
                        continue

                    key_name = RBDLabNaming.VELOCITIES
                    if key_name in obj:

                        frame = None
                        velocity = None

                        # necesito todos los frames y todos los speeds en 2 listados:
                        obj_all_frames = []
                        obj_all_speeds = []

                        # por cada objeto actual recolecto sus frames y sus velocities para meterlo en un
                        for motion in obj.rbdlab.motions:
                            for velocity in motion.velocities:

                                # guardo todos los frames de cada objeto:
                                obj_all_frames.append(velocity.frame)

                                # guardo todas las velocidades de cada objeto:
                                obj_all_speeds.append(velocity.speed)

                        for frame, speed in zip(obj_all_frames, obj_all_speeds):
                            if float(speed) <= 0:
                                continue

                            # print("update", frame, velocity)
                            # hago esto primero para no perder el primer keyframe inicial

                            if target_type == "density":
                                value = normalize(
                                    normalize(
                                        speed,
                                        min(obj_all_speeds),
                                        max(obj_all_speeds)
                                    ), 0, 1
                                ) * rbdlab.smoke.density_multiplier
                            else:
                                value = normalize(
                                    normalize(
                                        speed,
                                        min(obj_all_speeds),
                                        max(obj_all_speeds)
                                    ), 0, 1
                                ) * rbdlab.smoke.fuel_multiplier

                                if value < 0.001:
                                    value = 0

                            if target_type == "density":
                                flow.density = value
                            else:
                                flow.fuel_amount = value

                            flow.keyframe_insert(
                                data_path=target_type,
                                frame=frame
                            )
                            # si es el primero pongo un keyframe a 0 en un frame anterior:
                            if frame == min(obj_all_frames):

                                if target_type == "density":
                                    flow.density = 0
                                else:
                                    flow.fuel_amount = 0

                                flow.keyframe_insert(
                                    data_path=target_type,
                                    frame=(frame - 1)
                                )

                # fuerzo a que recompute la cache:
                domain = [obj for obj in bpy.data.objects if obj.name.endswith(RBDLabNaming.SUFIX_DOMAIN)]
                if domain:
                    domain = domain[0]
                    domain.modifiers[RBDLabNaming.SMOKE_MOD].domain_settings.resolution_max = domain.modifiers[RBDLabNaming.SMOKE_MOD].domain_settings.resolution_max

                context.scene.frame_current = context.scene.frame_start

    def density_multiplier_update(self, context):
        self.multiplier_update(context, "density")

    def fuel_multiplier_update(self, context):
        self.multiplier_update(context, "fuel_amount")

    emiter: PointerProperty(type=RBDLab_PG_Smoke_Emiter)

    range_in: IntProperty(
        default=0,
    )
    range_out: IntProperty(
        default=250,
    )
    condition: EnumProperty(
        items=(
            (">", ">", ""),
            ("<", "<", ""),
        ),
        description="Condition",
        default=">"
    )
    speed_threshold: FloatProperty(
        default=0.02,
        min=0.000,
        precision=6,
        unit='VELOCITY'
    )

    source: EnumProperty(
        items=(
            ('CHUNKS', "From Mesh", "Emit from mesh (chunks)", 'MATCUBE', 0),
            ('PARTICLES', "From Particles",
             "Emit from smoke particle system", 'MOD_PARTICLES', 1),
        ),
        description="Emit Smoke from particles or chunks",
        default='CHUNKS'
        # default='PARTICLES'
    )
    density_multiplier: FloatProperty(
        name="Density Multiplier",
        description="Density Multiplier",
        min=0.001,
        default=1,
        # max=10,
        precision=3,
        update=density_multiplier_update,
    )
    fuel_multiplier: FloatProperty(
        name="Fuel Multiplier",
        min=0.001,
        default=1,
        max=10,
        precision=3,
        update=fuel_multiplier_update,
    )
    lifetime: FloatProperty(
        min=1.0,
        default=8
    )
    # toggle para el play stop
    toggle_play: BoolProperty(
        default=False
    )
