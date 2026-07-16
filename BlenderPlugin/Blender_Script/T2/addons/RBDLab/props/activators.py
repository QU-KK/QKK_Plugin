import bpy
from mathutils import Vector
from bpy.types import PropertyGroup
from bpy.props import BoolProperty, FloatProperty, EnumProperty, IntProperty, FloatVectorProperty, StringProperty

from ..Global.basics import deselect_all_objects, deselect_object, select_object
from .when_updating_property import get_objects_centroids
from ..addon.naming import RBDLabNaming


class RBDLab_PG_activators(PropertyGroup):

    # activators substeps:
    type_selection: EnumProperty(
        items=(
            ("Collection", "Target Collection", "", 0),
            ("Scene", "Scene", "", 1),
        ),
        name="Type of Selection",
        default="Collection",
        description="Activators Affect to Target Collection, or affect to all chunks in the current scene"
    )
    
    substeps: IntProperty(
        default=1,
        min=1,
        max=10
    )
    work_with: EnumProperty(
        name="Work with",
        items=[
            ('DEACTIVATION',    "Deactivations",    "Activators Affect to Deactivations",   'LOCKVIEW_OFF', 0),
            ('KINEMATIC',       "Kinematics",       "Activators Affect to Kinematics",      'ONIONSKIN_ON', 1),
            ('CONSTRAINTS',     "Constraints",      "Activators Affect to Constraints",     'MOD_SIMPLIFY', 2),
            ('DYNAMIC',         "Dynamic",          "Activators Affect to Dynamic",         'ORIENTATION_GIMBAL', 3),
            ('VERTEX_GROUPS',   "Vertex Groups",    "Vertex Groups",                        'STICKY_UVS_LOC', 4),
        ],
        # options={'ENUM_FLAG'}, # <- para permitir multiples opciones
        # default={'DEACTIVATION', 'KINEMATIC', 'CONSTRAINTS'},
        default='KINEMATIC',
    )
    force_mode: EnumProperty(
        name="Force Direction Mode",
        items=(
            ('AUTO', "Automatic", "Automatic force direction"),
            ('MANUAL', "Manual", "Manual force direction")
        ),
        default='MANUAL'
    )
    # loc

    def force_direction_update(self, context):
        
        scn = context.scene
        rbdlab = scn.rbdlab

        x, y, z = [0, 1, 2]
        force = rbdlab.activators.force_direction.copy()
        force_mult = rbdlab.activators.force_loc_scale

        if rbdlab.filtered_target_collection:
            if "activators_recorded" in rbdlab.filtered_target_collection or "activators_force_preview_recorded" in rbdlab.filtered_target_collection:
                if rbdlab.ui.activators_force_loc_mode == 'CONST':
                    objects = rbdlab.filtered_target_collection.objects

                    for obj in objects:

                        if not obj.animation_data:
                            continue
                        if not obj.animation_data.action:
                            continue

                        action = obj.animation_data.action
                        previous_kf = 0
                        new_value = 0

                        for fc in action.fcurves:
                            if "location" in fc.data_path:
                                for i, kf in enumerate(fc.keyframe_points):

                                    if i == 0:
                                        previous_kf = kf.co.y
                                    if i == 1:
                                        if previous_kf:

                                            if fc.array_index == x:
                                                new_value = previous_kf + force.x
                                            elif fc.array_index == y:
                                                new_value = previous_kf + force.y
                                            elif fc.array_index == z:
                                                new_value = previous_kf + force.z

                                            # if new_value != 0:
                                            #     new_value *= force_mult

                                            kf.co.y = new_value
                                            kf.handle_left.y = new_value
                                            kf.handle_right.y = new_value

    force_direction: FloatVectorProperty(
        name="Force Direction",
        description="Force to apply when chunks get in contact with the activators object",
        min=-5, max=5, size=3, default=(0, 0, 0), precision=2, subtype='XYZ_LENGTH',
        update=force_direction_update
    )
    # xyz min/max random loc:
    force_x_min_loc_rand: FloatProperty(
        name="Minimum for random value in x axis",
        default=0,
        min=-5, max=5,
        subtype='DISTANCE'
    )
    force_x_max_loc_rand: FloatProperty(
        name="Maximum for random value in x axis",
        default=0,
        min=-5, max=5,
        subtype='DISTANCE'
    )
    force_y_min_loc_rand: FloatProperty(
        name="Minimum for random value in y axis",
        default=0,
        min=-5, max=5,
        subtype='DISTANCE'
    )
    force_y_max_loc_rand: FloatProperty(
        name="Maximum for random value in y axis",
        default=0,
        min=-5, max=5,
        subtype='DISTANCE'
    )
    force_z_min_loc_rand: FloatProperty(
        name="Minimum for random value in z axis",
        default=0,
        min=-5, max=5,
        subtype='DISTANCE'
    )
    force_z_max_loc_rand: FloatProperty(
        name="Maximum for random value in z axis",
        default=0,
        min=-5, max=5,
        subtype='DISTANCE'
    )
    # explode

    automatic_range_with_keyframes: BoolProperty(
        name="Automatic/Manual Range",
        description="Automatic/Manual range of frames to compute",
        default=True
    )
    rbdw_substeps_per_frame: IntProperty(
        name="Substeps Per Frame", 
        description="Number of simulation steps taken per frame (higer values are more accurate but slower)", 
        default=1
    )

    #-----------------------------------------------------------------------------------------------
    # Activators Brushes:
    #-----------------------------------------------------------------------------------------------
    def dpaint_brush_update(_self, self, context, call_from:str) -> None:
        scn = context.scene
        rbdlab = scn.rbdlab

        ac_layers_list = rbdlab.lists.ac_layers_list
        layer = ac_layers_list.active
        if layer:

            activators_list = layer.activators_list
            if not activators_list.is_void:

                prop_value = getattr(self, "dpaint_" + call_from)
                
                # El usuario puede elegir sobre que elementos del listado va a setear:
                if self.dpaint_target_acts == 'ALL':
                    activators = activators_list.get_all_activators
                
                elif self.dpaint_target_acts == 'MARKED':
                    activators = activators_list.get_all_computable_activators

                elif self.dpaint_target_acts == 'CURR_SEL':
                    activators = [activators_list.get_current_activator]

                
                for act in activators:

                    brush_mod = act.modifiers.get(RBDLabNaming.ACT_BRUSH_MOD)
                    if not brush_mod:
                        continue

                    # solo se setea si es diferente:
                    if prop_value != getattr(brush_mod.brush_settings, call_from):
                        setattr(brush_mod.brush_settings, call_from, prop_value)
    
    dpaint_target_acts: EnumProperty(
        name="Activators",
        description="Activators to set",
        items=[
            ('ALL',                 "All",              "",     '', 1),
            ('MARKED',              "All Marked",       "",     '', 2),
            ('CURR_SEL',            "Current Selected", "",     '', 3),
        ],
        default='CURR_SEL',
        # update=lambda self, context: self.dpaint_brush_update(self, context, "paint_source")
    )
    dpaint_paint_source: EnumProperty(
        name="Paint Source",
        items=[
            # ('PARTICLE_SYSTEM',     "Particle System",          "",     'PARTICLE_DATA',    0),
            ('POINT',               "Object Center",            "",     'EMPTY_AXIS',       1),
            ('DISTANCE',            "Proximity",                "",     'DRIVER_DISTANCE',  2),
            ('VOLUME_DISTANCE',     "Mesh Volume + Proximity",  "",     'META_CUBE',        3),
            ('VOLUME',              "Mesh Volume",              "",     'MESH_CUBE',        4),
        ],
        default='VOLUME_DISTANCE',
        update=lambda self, context: self.dpaint_brush_update(self, context, "paint_source")
    )
    dpaint_paint_distance: FloatProperty(
        name="Proximity Distance",
        description="Maximum distance from brush to mesh surface to affect paint",
        min=0,
        default=1,
        max=500.0,
        update=lambda self, context: self.dpaint_brush_update(self, context, "paint_distance")
    )
    dpaint_proximity_falloff: EnumProperty(
        name="Proximity",
        description="Proximity falloff type",
        items=[
                ('SMOOTH',      "Smooth",       "", 'SPHERECURVE',  0),
                ('CONSTANT',    "Constant",     "", 'NOCURVE',      1),
                ('RAMP',        "Color Ramp",   "", 'COLOR',        2),
        ], 
        default='SMOOTH',
        update=lambda self, context: self.dpaint_brush_update(self, context, "proximity_falloff")
    )
    dpaint_use_proximity_project: BoolProperty(
        name="Project",
        description="Brush is projected to canvas from defined direction within brush proximity",
        default=False,
        update=lambda self, context: self.dpaint_brush_update(self, context, "use_proximity_project")
    )
    dpaint_ray_direction: EnumProperty(
        name="Ray Direction", 
        description="Ray direction to use for projection (if brush object is located in that direction it'is painted)",
        items=[
            ('CANVAS',  "Canvas Normal",    "", '', 0),
            ('BRUSH',   "Brush Normal",     "", '', 1),
            ('Z_AXIS',  "Z-Axis",           "", '', 2),
        ], 
        default='CANVAS',
        update=lambda self, context: self.dpaint_brush_update(self, context, "ray_direction")
    )
    dpaint_invert_proximity: BoolProperty(
        description="Proximity falloff is applied inside the volume",
        default=False,
        update=lambda self, context: self.dpaint_brush_update(self, context, "invert_proximity")
    )
    dpaint_use_negative_volume: BoolProperty(
        description="Negate influence inside the volume",
        default=False,
        update=lambda self, context: self.dpaint_brush_update(self, context, "use_negative_volume")
    )



    # End Activators Bruses 
    #-----------------------------------------------------------------------------------------------


    # with_rbdw: BoolProperty(name="Use Rigid Body World", description="Enable or Disable Rigid Body World (Disable is mosre faster)", default=False)

    total_frames: IntProperty(
        name="Frames to compute",
        description="Only the total number of frames indicated here will be computed from the beginning of the simulation",
        default=250, min=0)

    # Passive Mode:
    # pasive mode en activators deja encendido el RBD World para computar.
    def passive_mode_update(self, context):
        if self.passive_mode:
            scn = context.scene
            rbdlab = scn.rbdlab
            rbdlab.activators.automatic_range_with_keyframes = False

    passive_mode: BoolProperty(
        default=False,
        update=passive_mode_update
    )
    # End Passive Mode

    def force_explode_amount_update(self, context):
        rbdlab = context.scene.rbdlab

        if rbdlab.filtered_target_collection:
            coll_name = rbdlab.filtered_target_collection.name
            if coll_name:

                valid_objects = [obj for obj in rbdlab.filtered_target_collection.objects
                                 if RBDLabNaming.ACETONABLE in obj]

                if len(valid_objects) > 0:

                    speed_decrementor = 20
                    context.scene.frame_current = context.scene.frame_start
                    centroid, total_objects, v_objects = get_objects_centroids(context)

                    if "Activators_explode_centroid" in context.scene.objects:
                        centroid_obj = context.scene.objects.get("Activators_explode_centroid")
                        centroid = centroid_obj.matrix_world.translation

                    fuerza = rbdlab.activators.force_explode_amount
                    for obj in valid_objects:
                        if RBDLabNaming.ACTIVATORS_INITIAL_EXPLODE not in obj:
                            obj[RBDLabNaming.ACTIVATORS_INITIAL_EXPLODE] = obj.matrix_world.translation

                        initial_location = Vector((obj[RBDLabNaming.ACTIVATORS_INITIAL_EXPLODE]))

                        direccion = obj.matrix_world.translation - centroid
                        obj.matrix_world.translation = initial_location + (direccion * (fuerza/speed_decrementor))

    force_explode_amount: FloatProperty(
        name="Amount",
        description="Amount of force",
        default=0,
        min=0,
        precision=5,
        update=force_explode_amount_update
    )

    def explode_empty_size_update(self, context):
        rbdlab = context.scene.rbdlab

        if rbdlab.filtered_target_collection:
            coll_name = rbdlab.filtered_target_collection.name
            if coll_name:
                if "Activators_explode_centroid" in context.scene.objects:
                    centroid_obj = context.scene.objects.get("Activators_explode_centroid")
                    centroid_obj.empty_display_size = self.explode_empty_size

    explode_empty_size: FloatProperty(
        default=3,
        min=1,
        precision=1,
        update=explode_empty_size_update
    )

    def explode_centroid_visibility_update(self, context):
        rbdlab = context.scene.rbdlab

        if rbdlab.filtered_target_collection:
            coll_name = rbdlab.filtered_target_collection.name
            if coll_name:

                if "Activators_explode_centroid" in context.scene.objects:
                    centroid_obj = context.scene.objects.get("Activators_explode_centroid")
                    if self.explode_centroid_visibility:
                        centroid_obj.hide_set(False)
                    else:
                        centroid_obj.hide_set(True)

    explode_centroid_visibility: BoolProperty(
        default=True,
        update=explode_centroid_visibility_update
    )

    def explode_centroid_select_update(self, context):
        rbdlab = context.scene.rbdlab

        if rbdlab.filtered_target_collection:
            coll_name = rbdlab.filtered_target_collection.name
            if coll_name:

                if "Activators_explode_centroid" in context.scene.objects:
                    deselect_all_objects(context)
                    centroid_obj = context.scene.objects.get("Activators_explode_centroid")

                    if self.explode_centroid_select:
                        select_object(context, centroid_obj)
                    else:
                        deselect_object(centroid_obj)

    explode_centroid_select: BoolProperty(
        default=False,
        update=explode_centroid_select_update
    )

    # rot
    force_rotation: FloatVectorProperty(
        name="Force Rotation",
        description="Rotation Force to apply when chunks get in contact with the activators object",
        min=-3.1415927410125732, max=3.1415927410125732, size=3, subtype='EULER', default=(0, 0, 0), precision=3
    )
    # xyz min/max random rot:
    force_x_min_rot_rand: FloatProperty(
        name="Minimum for random value in x axis",
        default=0,
        min=-3.1415927410125732, max=3.1415927410125732,
        unit='ROTATION',
        subtype='ANGLE'
    )
    force_x_max_rot_rand: FloatProperty(
        name="Maximum for random value in x axis",
        default=0,
        min=-3.1415927410125732, max=3.1415927410125732,
        unit='ROTATION',
        subtype='ANGLE'
    )
    force_y_min_rot_rand: FloatProperty(
        name="Minimum for random value in y axis",
        default=0,
        min=-3.1415927410125732, max=3.1415927410125732,
        unit='ROTATION',
        subtype='ANGLE'
    )
    force_y_max_rot_rand: FloatProperty(
        name="Maximum for random value in y axis",
        default=0,
        min=-3.1415927410125732, max=3.1415927410125732,
        unit='ROTATION',
        subtype='ANGLE'
    )
    force_z_min_rot_rand: FloatProperty(
        name="Minimum for random value in z axis",
        default=0,
        min=-3.1415927410125732, max=3.1415927410125732,
        unit='ROTATION',
        subtype='ANGLE'
    )
    force_z_max_rot_rand: FloatProperty(
        name="Maximum for random value in z axis",
        default=0,
        min=-3.1415927410125732, max=3.1415927410125732,
        unit='ROTATION',
        subtype='ANGLE'
    )
    # Activators Ease In-Out Animation.
    # +++++++++++++++++++++++++++++++++++++++++++++++

    def update_activators_force_ease(self, _context, transform_type: str, ease_type: str):
        if transform_type == 'LOC':
            cur_ease_in, cur_ease_out = self.force_loc_ease_in,  self.force_loc_ease_out
        elif transform_type == 'EXP':
            cur_ease_in, cur_ease_out = self.force_exp_ease_in,  self.force_exp_ease_out
        elif transform_type == 'ROT':
            cur_ease_in, cur_ease_out = self.force_rot_ease_in,  self.force_rot_ease_out
        ease_sum = cur_ease_in + cur_ease_out
        if ease_sum <= 100:
            return
        overflow = ease_sum - 100

        if transform_type == 'LOC':
            pre_ease_in, pre_ease_out = self.force_loc_ease_inout_prev
        elif transform_type == 'EXP':
            pre_ease_in, pre_ease_out = self.force_exp_ease_inout_prev
        elif transform_type == 'ROT':
            pre_ease_in, pre_ease_out = self.force_rot_ease_inout_prev
        if ease_type == 'IN':
            dir_slider = 1 if cur_ease_in > pre_ease_in else -1
            # Se está modificando el Ease-IN...
            # Equilibrar el Ease-Out para evitar conflictos.
            if dir_slider == 1:
                if transform_type == 'LOC':
                    self.force_loc_ease_out -= overflow
                elif transform_type == 'EXP':
                    self.force_exp_ease_out -= overflow
                elif transform_type == 'ROT':
                    self.force_rot_ease_out -= overflow
        else:
            dir_slider = 1 if cur_ease_out > pre_ease_out else -1
            # Se está modificando el Ease-OUT.
            # Equilibrar el Ease-In para evitar conflictos.
            if dir_slider == 1:
                if transform_type == 'LOC':
                    self.force_loc_ease_in -= overflow
                elif transform_type == 'EXP':
                    self.force_exp_ease_in -= overflow
                elif transform_type == 'ROT':
                    self.force_rot_ease_in -= overflow

        # Guardar el estado.
        if transform_type == 'LOC':
            self.force_loc_ease_inout_prev = (self.force_loc_ease_in,  self.force_loc_ease_out)
        elif transform_type == 'EXP':
            self.force_exp_ease_inout_prev = (self.force_exp_ease_in,  self.force_exp_ease_out)
        elif transform_type == 'ROT':
            self.force_rot_ease_inout_prev = (self.force_rot_ease_in,  self.force_rot_ease_out)
    # -- Location Ease.
    force_loc_ease_in: FloatProperty(
        name="Ease In",
        default=0,
        subtype='PERCENTAGE',
        min=0, max=100,
        update=lambda x, y: x.update_activators_force_ease(y, 'LOC', 'IN')
    )
    force_loc_ease_out: FloatProperty(
        name="Ease Out",
        default=0,
        subtype='PERCENTAGE',
        min=0, max=100,
        update=lambda x, y: x.update_activators_force_ease(y, 'LOC', 'OUT')
    )
    force_loc_ease_inout_prev: FloatVectorProperty(
        default=(0, 0),
        size=2,
        min=0, max=100,
    )
    force_exp_ease_in: FloatProperty(
        name="Ease In",
        default=0,
        subtype='PERCENTAGE',
        min=0, max=100,
        update=lambda x, y: x.update_activators_force_ease(y, 'EXP', 'IN')
    )
    force_exp_ease_out: FloatProperty(
        name="Ease Out",
        default=0,
        subtype='PERCENTAGE',
        min=0, max=100,
        update=lambda x, y: x.update_activators_force_ease(y, 'EXP', 'OUT')
    )
    force_exp_ease_inout_prev: FloatVectorProperty(
        default=(0, 0),
        size=2,
        min=0, max=100,
    )
    # -- Rotation Ease.
    force_rot_ease_in: FloatProperty(
        name="Ease In",
        default=0,
        subtype='PERCENTAGE',
        min=0, max=100,
        update=lambda x, y: x.update_activators_force_ease(y, 'ROT', 'IN')
    )
    force_rot_ease_out: FloatProperty(
        name="Ease Out",
        default=0,
        subtype='PERCENTAGE',
        min=0, max=100,
        update=lambda x, y: x.update_activators_force_ease(y, 'ROT', 'OUT')
    )
    force_rot_ease_inout_prev: FloatVectorProperty(
        default=(0, 0),
        size=2,
        min=0, max=100,
    )
    # +++++++++++++++++++++++++++++++++++++++++++++++
    force_loc_frame_offset: IntProperty(
        name="Frame Offset",
        description="Offset of frames to animate the forces. 0 is automatic.",
        min=0, max=10, default=0,
    )
    force_explode_frame_offset: IntProperty(
        name="Frame Offset",
        description="Offset of frames to animate the forces. 0 is automatic.",
        min=0, max=10, default=0,
    )
    force_rot_frame_offset: IntProperty(
        name="Frame Offset",
        description="Offset of frames to animate the forces. 0 is automatic.",
        min=0, max=10, default=0,
    )
    force_loc_scale: FloatProperty(
        name="Force Scale",
        description="Force multiplier to scale up or down the force",
        min=0.001, max=1, default=0.1,
        update=force_direction_update
    )
    force_explode_scale: FloatProperty(
        name="Explode Force Scale",
        description="Force multiplier to scale up or down the force",
        min=0.001, max=1, default=0.1,
    )
    force_rot_scale: FloatProperty(
        name="Force Scale",
        description="Force multiplier to scale up or down the force",
        min=0.001, max=1, default=0.1,
    )
    angular_range: FloatVectorProperty(
        name="Angular Force Range",
        size=2, min=-180, max=180, default=(0, 0),
    )
    angular_scale: FloatProperty(
        name="Angular Force Scale",
        description="Angular Force multiplier to scale up or down the force",
        min=0.001, max=1, default=0.1,
    )

    activators_show_explode_amount_feedback: StringProperty(default="")
