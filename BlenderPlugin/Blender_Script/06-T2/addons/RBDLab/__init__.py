import os
import bpy
from .addon.paths import RBDLabPaths, RBDLabPreferences
from .addon import icons
from .addon import colors
from bpy.app.handlers import persistent
from bpy.utils import register_class, unregister_class
from .addon.preferences import RBDLabAddonPreferences
from .addon.naming import RBDLabNaming
from .Global.basics import context_override
from .libs import cell_fracture


bl_info = {
    "name": "RBDLab",
    "author": "RBDLab Studio",
    "version": (1, 5, 6),
    "blender": (4, 1, 0),
    "location": "View3D > RBDLab",
    "description": "Helpers for fracture",
    "warning": "",
    "doc_url": "https://sites.google.com/view/rbdlab-user-guide-en/home",
    "category": "Physics",
}


def on_load_post():

    # print(f"algo1 {algo1} algo2 {algo2}, type1 {type(algo1)} type2 {type(algo2)}")    
    

    # Inicializar variable temporal global
    # para el handler de dibujado para las constraints.
    bpy.rbdlab_const_draw_handler = None

    context = bpy.context
    rbdlab = context.scene.rbdlab
    # folder_addon_name = get_folder_addon_name()
    # if folder_addon_name:
    # rbdlab.folder_addon_name = __package__
    addon_preferences = RBDLabPreferences.get_prefs(context)
    rbdlab.rbdlab_cf_fast_exact = addon_preferences.rbdlab_cf_fast_exact_prefs

    # reseteo a 0 al cargar:
    rbdlab.chunks_selected = 0

    if addon_preferences.simplified_main_modules:
        rbdlab.ui.collapse_module_selector = True

    # copiamos en su sitio los presets:
    import shutil

    scripts_folder = bpy.utils.user_resource('SCRIPTS')
    particles_presets_folder = os.path.join(
        scripts_folder,
        os.path.join("presets", "RBDLab", "Particles")
    )

    # a tebito lo estaba ejecutando desde el desktop en lugar desde el folder del addon
    addon_folder = RBDLabPaths.ROOT

    # print(os.getcwd)
    current_dir = os.getcwd()
    os.chdir(addon_folder)

    # print("particles_presets_folder", particles_presets_folder)

    if not os.path.isdir(particles_presets_folder):
        os.makedirs(particles_presets_folder)

    debris_file = os.path.join("Presets", "Particles", "DefaultDebris.py")
    debris_dst = os.path.join(particles_presets_folder, "DefaultDebris.py")

    # print("os.getcwd()", os.getcwd())
    # print("debris_file", debris_file)
    # print("debris_dst", debris_dst)

    # if not os.path.isfile(debris_dst):
    #     shutil.copyfile(debris_file, debris_dst)
    # sobreescribo los presets siempre:
    shutil.copyfile(debris_file, debris_dst)

    dust_file = os.path.join("Presets", "Particles", "DefaultDust.py")
    dust_dst = os.path.join(particles_presets_folder, "DefaultDust.py")
    # print("dust_dst", dust_dst)
    # if not os.path.isfile(dust_dst):
    #     shutil.copyfile(dust_file, dust_dst)
    # sobreescribo los presets siempre:
    shutil.copyfile(dust_file, dust_dst)

    dust_file = os.path.join("Presets", "Particles", "RealDust.py")
    dust_dst = os.path.join(particles_presets_folder, "RealDust.py")
    # print("dust_dst", dust_dst)
    # if not os.path.isfile(dust_dst):
    #     shutil.copyfile(dust_file, dust_dst)
    # sobreescribo los presets siempre:
    shutil.copyfile(dust_file, dust_dst)

    smoke_file = os.path.join("Presets", "Particles", "DefaultSmoke.py")
    smoke_dst = os.path.join(particles_presets_folder, "DefaultSmoke.py")
    # print("smoke_dst", smoke_dst)
    # if not os.path.isfile(smoke_dst):
    #     shutil.copyfile(smoke_file, smoke_dst)
    # sobreescribo los presets siempre:
    shutil.copyfile(smoke_file, smoke_dst)

    os.chdir(current_dir)


# @persistent
# def load_handler(dummy):
#     if not "rbdlab_avalidable_ps" in bpy.context.scene:
#         bpy.context.scene["rbdlab_avalidable_ps"] = {}
#
#     rbdlab_avalidable_ps = [
#         ("", "", "", 0),
#     ]
#     avalidable_ps(rbdlab_avalidable_ps)


@persistent
def run_onload_scene(dummy):

    context = bpy.context
    scn = context.scene

    # from .Global.functions import set_active_collection_to_master_coll
    # set_active_collection_to_master_coll(context)

    # sobreescribir el contexto:
    def callback(context) -> None:
        area = context.area  # Accedemos al área desde el contexto
        for space in area.spaces:
            if space.type == 'OUTLINER':
                if not space.show_restrict_column_hide:
                    space.show_restrict_column_hide = True
                if not space.show_restrict_column_select:
                    space.show_restrict_column_select = True
                if not space.show_restrict_column_viewport:
                    space.show_restrict_column_viewport = True
        area.tag_redraw()

    context_override(context=context, area_type='OUTLINER', callback=callback)



    from .props.when_updating_property import stats_on
    stats_on(None, context)

    # solo seteo el substeps en on load un blend file:
    addon_preferences = RBDLabPreferences.get_prefs(context)

    # para poder setearlo tiene q existir alguno en la escena:
    if not scn.rigidbody_world:
        bpy.ops.rigidbody.world_add()

    # Si no exista la collection RBDLab, y el valor es diferente, entonces seteo los substeps_per_frame y solver_iterations:
    if RBDLabNaming._RBDLab_name not in bpy.data.collections:

        if scn.rigidbody_world.substeps_per_frame != addon_preferences.substeps_per_frame:
            scn.rigidbody_world.substeps_per_frame = addon_preferences.substeps_per_frame
        
        if scn.rigidbody_world.solver_iterations != addon_preferences.solver_iterations:
            scn.rigidbody_world.solver_iterations = addon_preferences.solver_iterations

    on_load_post()




def register():

    cell_fracture.register()
    
    if hasattr(icons, "register"):
        icons.register()

    if hasattr(colors, "register"):
        colors.register()

    register_class(RBDLabAddonPreferences)

    # addon_utils.enable("object_fracture_cell")

    # Registrar Properties...
    from .props import register as REGISTER_PROPS
    REGISTER_PROPS()

    # Add Handlers...
    # bpy.app.handlers.load_post.append(load_handler)
    bpy.app.handlers.load_post.append(run_onload_scene)
    # bpy.app.handlers.load_post.append(on_load_post)

    from . ops import register as REGISTER_OPS
    from . panels import register as REGISTER_UI
    # Registrar Operators...
    REGISTER_OPS()
    # Registrar UI...
    REGISTER_UI()


def unregister():

    cell_fracture.unregister()

    if hasattr(icons, "unregister"):
        icons.unregister()

    if hasattr(colors, "unregister"):
        colors.unregister()

    from . ops import unregister as UNREGISTER_OPS
    from . panels import unregister as UNREGISTER_UI

    # Unregister UI...
    UNREGISTER_UI()
    # Unregister Operators...
    UNREGISTER_OPS()
    # Unregister Preferences...
    unregister_class(RBDLabAddonPreferences)
    # Unregister Properties...
    from .props import unregister as UNREGISTER_PROPS
    UNREGISTER_PROPS()
    # del WindowManager.user_snap

    # Remove Handlers...
    if run_onload_scene in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(run_onload_scene)
   
    # para las preferencias de boolean method:
    if on_load_post in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(on_load_post)
