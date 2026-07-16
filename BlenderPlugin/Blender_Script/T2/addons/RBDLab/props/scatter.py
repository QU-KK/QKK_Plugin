import bpy
from ..addon.naming import RBDLabNaming
from bpy.types import PropertyGroup
from bpy.props import BoolProperty, FloatProperty, IntProperty, EnumProperty, FloatVectorProperty
from .when_updating_property import (
    texture_particle_count_update,
    texture_secondary_emit_from_update,
    texture_noise_basis_update,
    texture_noise_type_update,
    texture_cloud_type_update,
    texture_noise_scale_upadte,
    texture_noise_depth_update,
    texture_texture_coords_update,
    texture_mapping_offset_update,
    texture_mapping_size_update,
    texure_use_color_ramp_update,
    scatter_geo_from_update,
    scatter_geo_count_update,
    scatter_geo_seed_update,
    scatter_geo_child_count_update,
    scatter_geo_ps_child_size_update,
    scatter_geo_particle_size_update,
    scatter_geo_size_random_update,
)


class RBDLab_PG_scatter(PropertyGroup):

    ######################################################################################
    # Scatter by Texture
    ######################################################################################
    texture_particle_count: IntProperty(
        default=50000,
        min=1,
        update=texture_particle_count_update
    )
    texture_secondary_emit_from: EnumProperty(
        items=(
            ('VOLUME', "Volume", "", 0),
            ('VERT', "Vertex", "", 1),
            ('FACE', "Faces", "", 2)
        ),
        name="texture_secondary_emit_from",
        description="",
        default='VOLUME',
        update=texture_secondary_emit_from_update
    )
    texture_noise_basis: EnumProperty(
        items=(
            ('BLENDER_ORIGINAL', "Blender Original", "", 0),
            ('IMPROVED_PERLIN', "Improved Perlin", "", 1),
            ('VORONOI_F1', "Voronoi F1", "", 2),
            ('VORONOI_F2', "Voronoi F2", "", 3),
            ('VORONOI_F3', "Voronoi F3", "", 4),
            ('VORONOI_F4', "Voronoi F4", "", 5),
            ('VORONOI_F2_F1', "Voronoi F2 F1", "", 6),
            ('VORONOI_CRACKLE', "Voronoi Crackle", "", 7),
        ),
        name="texture_noise_basis",
        description="",
        default='BLENDER_ORIGINAL',
        update=texture_noise_basis_update
    )
    texture_noise_type: EnumProperty(
        items=(
            ('SOFT_NOISE', "Soft", "", 0),
            ('HARD_NOISE', "Hard", "", 1),
        ),
        name="texture_noise_type",
        description="",
        default='SOFT_NOISE',
        update=texture_noise_type_update
    )
    texture_cloud_type: EnumProperty(
        items=(
            ('GRAYSCALE', "Grayscale", "", 0),
            ('COLOR', "Color", "", 1),
        ),
        name="texture_cloud_type",
        description="",
        default='GRAYSCALE',
        update=texture_cloud_type_update
    )
    texture_noise_scale: FloatProperty(
        name="texture_noise_scale",
        default=0.25,
        min=0,
        max=2,
        precision=3,
        update=texture_noise_scale_upadte
    )
    texture_noise_depth: IntProperty(
        name="texture_noise_depth",
        min=0,
        max=24,
        default=2,
        update=texture_noise_depth_update
    )
    texture_texture_coords: EnumProperty(
        items=(
            ('GLOBAL', "Global", "", 0),
            ('OBJECT', "Object", "", 1),
            ('UV', 'UV', "", 2),
            ('ORCO', "Generated", "", 3),
            ('STRAND', "Strand", "", 4),
        ),
        name="texture_texture_coords",
        description="",
        # default='UV',
        default='ORCO',
        update=texture_texture_coords_update
    )
    texture_mapping_offset: FloatVectorProperty(
        size=3,
        update=texture_mapping_offset_update
    )
    texture_mapping_size: FloatVectorProperty(
        size=3,
        default=[1, 1, 1],
        update=texture_mapping_size_update
    )
    texure_use_color_ramp: BoolProperty(
        default=True,
        update=texure_use_color_ramp_update
    )

    ######################################################################################
    # End Scatter by Texture
    ######################################################################################
    ######################################################################################
    # Scatter by organic
    ######################################################################################
    scatter_geo_from: EnumProperty(
        items=(
            ('VOLUME', "Volume", "", 0),
            ('VERT', "Vertex", "", 1),
            ('FACE', "Faces", "", 2)
        ),
        update=scatter_geo_from_update
    )
    scatter_geo_count: IntProperty(
        min=1,
        default=30,
        update=scatter_geo_count_update
    )
    scatter_geo_seed: IntProperty(
        default=0,
        update=scatter_geo_seed_update
    )
    scatter_geo_child_count: IntProperty(
        min=1,
        default=10000,
        update=scatter_geo_child_count_update
    )
    scatter_geo_ps_child_size: FloatProperty(
        min=0,
        default=0.035,
        precision=3,
        update=scatter_geo_ps_child_size_update
    )
    scatter_geo_particle_size: FloatProperty(
        min=0.01,
        default=0.5,
        update=scatter_geo_particle_size_update
    )
    scatter_geo_size_random: FloatProperty(
        min=0,
        max=1,
        default=0.5,
        update=scatter_geo_size_random_update
    )
    ######################################################################################
    # End Scatter by geometry
    ######################################################################################

    ######################################################################################
    # Boolean Fracture GN
    ######################################################################################
    def scatter_bfracture_method_update(self, context):
        
        scn = context.scene
        rbdlab = scn.rbdlab

        bfracture_gn_list = rbdlab.lists.bfracture_gn_list
        to_fracture_obs = bfracture_gn_list.get_objects_to_fracture

        for ob in to_fracture_obs:
            bool_mod = ob.modifiers.get(RBDLabNaming.BOOLEAN_MOD)
            if bool_mod: 
                bool_mod.solver = self.scatter_bfracture_method

    scatter_bfracture_method: EnumProperty(
        items=(
            ('FAST', "Fast", "", 0),
            ('EXACT', "Exact", "", 1),
        ),
        default='FAST',
        description="Method for booleans modifiers (Only in the current selected objects)",
        update=scatter_bfracture_method_update
    )
    ######################################################################################
    # End Boolean Fracture GN
    ######################################################################################

    ######################################################################################
    # Scatter by Edge Fractures
    ######################################################################################
    edge_method: EnumProperty(
        name="Method",
        items=(
            ('M1', "Simple", "", 0),
            ('M2', "Organic", "", 1),
        ),
        description="",
        default='M2'
    )

    # Modifiers:
    def edge_solidify_thickness_update(self, context):
        rbdlab = context.scene.rbdlab
        if rbdlab.filtered_target_collection:
            coll_name = rbdlab.filtered_target_collection.name
            if coll_name:
                for obj in rbdlab.filtered_target_collection.objects:
                    if RBDLabNaming.SOLIDIFY_MOD in obj.modifiers:
                        obj.modifiers[RBDLabNaming.SOLIDIFY_MOD].thickness = self.edge_solidify_thickness

    def edge_displace_strength_update(self, context):
        rbdlab = context.scene.rbdlab
        if rbdlab.filtered_target_collection:
            coll_name = rbdlab.filtered_target_collection.name
            if coll_name:
                for obj in rbdlab.filtered_target_collection.objects:
                    if RBDLabNaming.DISPLACE in obj.modifiers:
                        obj.modifiers[RBDLabNaming.DISPLACE].strength = self.edge_displace_strength

    edge_solidify_thickness: FloatProperty(
        name="Thinckness",
        min=-10,
        max=10,
        subtype='DISTANCE',
        update=edge_solidify_thickness_update
    )
    edge_displace_strength: FloatProperty(
        name="Offse Thinckness",
        min=-100,
        max=100,
        update=edge_displace_strength_update
    )

    def edge_curve_bevel_depth_update(self, context):
        rbdlab = context.scene.rbdlab
        if rbdlab.filtered_target_collection:
            coll_name = rbdlab.filtered_target_collection.name
            if coll_name:
                for obj in rbdlab.filtered_target_collection.objects:
                    if obj.type == 'CURVE':
                        obj.data.bevel_depth = self.edge_curve_bevel_depth

    edge_curve_bevel_depth: FloatProperty(
        name="Curve Depth",
        default=0,
        min=0,
        max=100,
        subtype='DISTANCE',
        update=edge_curve_bevel_depth_update
    )
    # End Modifiers

    # particles scatter edges:
    ps_name = "Particle_Scatter"

    @staticmethod
    def selection_or_target_coll(context):
        rbdlab = context.scene.rbdlab
        objects = None

        if context.selected_objects:
            objects = context.selected_objects

            childrens = []

            for obj in objects:
                if len(obj.children) == 1:
                    childrens.append(obj.children[0])

            if childrens:
                objects = childrens
        else:
            if rbdlab.filtered_target_collection:
                coll_name = rbdlab.filtered_target_collection.name
                if coll_name:
                    objects = rbdlab.filtered_target_collection.objects

        if objects:
            return objects

    # Density
    def edge_count_update(self, context):

        objects = self.selection_or_target_coll(context)

        if objects:
            for obj in objects:
                if self.ps_name in obj.modifiers:
                    obj.particle_systems[self.ps_name].settings.count = self.edge_count

    edge_count: IntProperty(
        name="Count",
        # default=30,
        default=15000,
        min=1,
        update=edge_count_update
    )

    # Seed
    def edge_seed_update(self, context):

        objects = self.selection_or_target_coll(context)

        if objects:
            valid_objects = [obj for obj in objects if obj.type == 'MESH' and obj.visible_get()]
            i = 0
            for obj in valid_objects:
                if len(obj.particle_systems) > 0:
                    if self.ps_name in obj.particle_systems:
                        ps = obj.particle_systems[self.ps_name]
                        ps.seed = self.edge_seed + i
                    i += 1

    edge_seed: IntProperty(
        name="Seed",
        default=0,
        update=edge_seed_update
    )

    # Size
    def edge_p_size_update(self, context):

        objects = self.selection_or_target_coll(context)

        if objects:
            for obj in objects:
                if self.ps_name in obj.modifiers:
                    obj.particle_systems[self.ps_name].settings.display_size = self.edge_p_size

    edge_p_size: FloatProperty(
        name="Size",
        default=0.035,
        description="Scatter Edge Particles Size in Viewport.",
        update=edge_p_size_update
    )

    # From(volume)
    def egde_emit_from_update(self, context):

        objects = self.selection_or_target_coll(context)

        if objects:
            for obj in objects:
                if len(obj.particle_systems) > 0:
                    if self.ps_name in obj.particle_systems:
                        obj.particle_systems[self.ps_name].settings.emit_from = self.egde_emit_from

    egde_emit_from: EnumProperty(
        name="Emit From",
        items=(
            ('VOLUME', "Volume", "", 0),
            ('VERT', "Vertex", "", 1),
            ('FACE', "Faces", "", 2)
        ),
        description="Emit From",
        update=egde_emit_from_update
    )

    # use
    def edge_use_modifier_stack_update(self, context):

        objects = self.selection_or_target_coll(context)

        if objects:
            for obj in objects:
                if len(obj.particle_systems) > 0:
                    if self.ps_name in obj.particle_systems:
                        obj.particle_systems[self.ps_name].settings.use_modifier_stack = self.edge_use_modifier_stack

    edge_use_modifier_stack: BoolProperty(
        name="Use Modifier Stack",
        default=True,
        update=edge_use_modifier_stack_update
    )

    # Distribution
    def edge_distribution_update(self, context):

        objects = self.selection_or_target_coll(context)

        if objects:
            for obj in objects:
                if len(obj.particle_systems) > 0:
                    if self.ps_name in obj.particle_systems:
                        obj.particle_systems[self.ps_name].settings.distribution = self.edge_distribution

    edge_distribution: EnumProperty(
        name="Distribution",
        items=(
            ('JIT', "Jittered", "", 0),
            ('RAND', "Random", "", 1),
            ('GRID', "Grid", "", 2)
        ),
        description="Hot to distribute particles",
        default='RAND',
        update=edge_distribution_update
    )

    # jittered
    def edge_userjit_update(self, context):
        objects = self.selection_or_target_coll(context)

        if objects:
            for obj in objects:
                if len(obj.particle_systems) > 0:
                    if self.ps_name in obj.particle_systems:
                        obj.particle_systems[self.ps_name].settings.userjit = self.edge_userjit

    edge_userjit: IntProperty(
        name="Particles/Face",
        default=0,
        min=0,
        max=1000,
        update=edge_userjit_update
    )

    def edge_jitter_factor_update(self, context):

        objects = self.selection_or_target_coll(context)

        if objects:
            for obj in objects:
                if len(obj.particle_systems) > 0:
                    if self.ps_name in obj.particle_systems:
                        obj.particle_systems[self.ps_name].settings.jitter_factor = self.edge_jitter_factor

    edge_jitter_factor: FloatProperty(
        name="Jittering Amount",
        default=1,
        min=0,
        max=2,
        precision=3,
        update=edge_jitter_factor_update
    )

    # grid
    def edge_invert_grid_update(self, context):

        objects = self.selection_or_target_coll(context)

        if objects:
            for obj in objects:
                if len(obj.particle_systems) > 0:
                    if self.ps_name in obj.particle_systems:
                        obj.particle_systems[self.ps_name].settings.invert_grid = self.edge_invert_grid

    edge_invert_grid: BoolProperty(
        name="Invert Grid",
        default=False,
        update=edge_invert_grid_update
    )

    def edge_hexagonal_grid_update(self, context):

        objects = self.selection_or_target_coll(context)

        if objects:
            for obj in objects:
                if len(obj.particle_systems) > 0:
                    if self.ps_name in obj.particle_systems:
                        obj.particle_systems[self.ps_name].settings.hexagonal_grid = self.edge_hexagonal_grid

    edge_hexagonal_grid: BoolProperty(
        name="Hexagonal Grid",
        default=False,
        update=edge_hexagonal_grid_update
    )

    def edge_grid_resolution_update(self, context):

        objects = self.selection_or_target_coll(context)

        if objects:
            for obj in objects:
                if len(obj.particle_systems) > 0:
                    if self.ps_name in obj.particle_systems:
                        obj.particle_systems[self.ps_name].settings.grid_resolution = self.edge_grid_resolution

    edge_grid_resolution: IntProperty(
        default=10,
        min=1,
        max=50,
        update=edge_grid_resolution_update
    )

    def edge_grid_random_update(self, context):

        objects = self.selection_or_target_coll(context)

        if objects:
            for obj in objects:
                if len(obj.particle_systems) > 0:
                    if self.ps_name in obj.particle_systems:
                        obj.particle_systems[self.ps_name].settings.grid_random = self.edge_grid_random

    edge_grid_random: FloatProperty(
        default=0,
        min=0,
        max=1,
        precision=3,
        update=edge_grid_random_update
    )

    # Random Order
    def edge_use_emit_random_update(self, context):

        objects = self.selection_or_target_coll(context)

        if objects:
            for obj in objects:
                if len(obj.particle_systems) > 0:
                    if self.ps_name in obj.particle_systems:
                        obj.particle_systems[self.ps_name].settings.use_emit_random = self.edge_use_emit_random

    edge_use_emit_random: BoolProperty(
        name="Random Order",
        default=True,
        update=edge_use_emit_random_update
    )

    # Even Distribution
    def edge_use_even_distribution_update(self, context):

        objects = self.selection_or_target_coll(context)

        if objects:
            for obj in objects:
                if len(obj.particle_systems) > 0:
                    if self.ps_name in obj.particle_systems:
                        obj.particle_systems[self.ps_name].settings.use_even_distribution = self.edge_use_even_distribution

    edge_use_even_distribution: BoolProperty(
        name="Even Distribution",
        default=True,
        update=edge_use_even_distribution_update
    )

    # end particles scatter edges

    ######################################################################################
    # End Scatter by Edge Fractures
    ######################################################################################
