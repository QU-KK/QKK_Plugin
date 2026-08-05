import bpy
from typing import Union
from bpy.types import Collection
from .functions import set_active_object


def create_particle_system(
        context, ob, ps_name,
        # emission:
        ps_type: str = 'VOLUME',
        ps_count: int = 30,
        frame_start: Union[float, int] = 1,
        frame_end: Union[float, int] = 250,
        lifetime: int = 250,
        # emission source:
        distribution: str = 'RAND',
        use_modifier_stack: bool = False,
        # render
        render_type: str = 'HALO',
        particle_size: float = 0.1,
        size_random: float = -1,
        # render collection:
        instance_collection: Collection = None,
        # render extras:
        show_unborn: bool = True, use_dead: bool = True,
        # display viewport:
        display_size: float = 0.035,
        # physics:
        physics_type: str = 'NEWTON',
        # velocity:
        normal_factor: float = -1,
        factor_random: float = -1,
        # rotation:
        use_rotations: bool = False,
        phase_factor_random: float = -1,
        use_dynamic_rotation: bool = False,
        vertex_group_density: str = None,
        edge_method: bool = False,
) -> None:

    # buscamos si ya tiene ese sistema de particulas:
    psys = None
    ps_mods = [mod for mod in ob.modifiers if mod.type == 'PARTICLE_SYSTEM' and mod.name == ps_name]
    if ps_mods:
        psys = ps_mods[-1].particle_system

    # si no lo tiene se crea:
    if psys is None:
        # Crea un nuevo sistema de partículas
        ps_mod = ob.modifiers.new(ps_name, type='PARTICLE_SYSTEM')
        psys = ps_mod.particle_system

    # Accede a la configuración del sistema actualmente seleccionado
    settings = psys.settings

    settings.name = ps_name
    settings.emit_from = ps_type
    settings.count = ps_count
    settings.frame_start = frame_start
    settings.frame_end = frame_end
    settings.lifetime = lifetime
    settings.render_type = render_type
    settings.particle_size = particle_size
    settings.display_size = display_size
    settings.physics_type = physics_type
    settings.distribution = distribution
    settings.use_modifier_stack = use_modifier_stack
    settings.show_unborn = show_unborn
    settings.use_dead = use_dead
    settings.use_rotations = use_rotations
    settings.use_dynamic_rotation = use_dynamic_rotation

    if normal_factor != -1:
        settings.normal_factor = normal_factor

    if factor_random != -1:
        settings.factor_random = factor_random

    if phase_factor_random != -1:
        settings.phase_factor_random = phase_factor_random

    if size_random != -1:
        settings.size_random = size_random

    if instance_collection:
        settings.instance_collection = instance_collection

    # random seed:
    psys.seed = list(context.view_layer.objects).index(ob)

    if vertex_group_density:
        psys.vertex_group_density = vertex_group_density

    if edge_method:
        settings.frame_start = context.scene.frame_current
        settings.frame_end = context.scene.frame_current


def particle_system_remove(context, ps_name: str) -> None:
    scn = context.scene
    rbdlab = scn.rbdlab

    tcoll_list = rbdlab.lists.target_coll_list
    chunks = tcoll_list.get_current_active_tcoll_valild_objects(context)

    if chunks:
        prev_active = context.active_object
        for ob in chunks:
            set_active_object(context, ob)

            for i, ps in enumerate(ob.particle_systems):
                if ps_name in ps.name:
                    ob.particle_systems.active_index = i

            bpy.ops.object.particle_system_remove()

        set_active_object(context, prev_active)


def copy_particle_system_to_selected_objects(context, ps_name: str) -> None:
    if ps_name in bpy.data.particles:
        ao = context.active_object
        for ob in context.selected_objects:
            if ob == ao:
                continue
            set_active_object(context, ob)
            bpy.ops.object.particle_system_add()
            ob.particle_systems[-1].name = ps_name
            ps = ao.particle_systems.get(ps_name)
            ob.particle_systems[-1].settings = ps.settings


@staticmethod
def selected_objects_ps_update_settings(self, context, ps_name: str, target_attr: str) -> None:
    for ob in context.selected_objects:
        for ps in ob.particle_systems:
            if not ps.name.startswith(ps_name):
                continue
            setattr(ps.settings, target_attr, getattr(self, target_attr))
