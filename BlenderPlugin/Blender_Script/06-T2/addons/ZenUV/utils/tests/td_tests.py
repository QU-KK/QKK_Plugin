# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####


import bpy
from .addon_test_utils import (
    _set_object_mode,
    _set_edit_mode,
    AddonTestError,
    AddonTestManual
    )
from .addon_test_utils import TestGeometry
from ZenUV.utils.vlog import Log


# ---------------------------------------------------------------------------------------
# Texel Density System Object Mode --> Start


class ZUV_OT_UnitTestTexelDensity(bpy.types.Operator):
    bl_idname = "wm.zenuv_td_unit_test"
    bl_label = "TD Unit Test"
    bl_description = "TD Unit Test"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        TdTestModule.UnitTestFull(context)
        return {'FINISHED'}


class ZUV_OT_TestPropertiesTexelDensity(bpy.types.Operator):
    bl_idname = "wm.zenuv_td_properties_test"
    bl_label = "TD Properties Test"
    bl_description = "TD Properties Test"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        TdTestModule.PropertiesTest(context)
        self.report({'INFO'}, 'See System console.')
        return {'FINISHED'}


class ZUV_OT_DevTestTexelDensity(bpy.types.Operator):
    bl_idname = "wm.zenuv_td_dev_test"
    bl_label = "TD Dev Test"
    bl_description = "TD Dev Test"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        TdTestModule.dev_test_get_texel_density(context)
        return {'FINISHED'}


class Contstants:

    default_image_x: int = 1024
    default_image_y: int = 1024
    default_units: str = 'm'
    dev_test: float = 128


class ReferenceValues:

    constants: Contstants = Contstants
    dev_td_temp_value = 12.5


class TdTestModule():

    @classmethod
    def prepare_dev_td_test(cls, context: bpy.types.Context, model="CUBE", count=2):
        try:
            if context.mode != 'EDIT_MESH':
                if bpy.ops.object.mode_set.poll():
                    bpy.ops.object.mode_set(mode='EDIT')

        except Exception:
            pass

        _set_object_mode(context)

        for p_obj in bpy.data.objects:
            bpy.data.objects.remove(p_obj)

        if len(bpy.data.objects):
            raise AddonTestError('PREPARE> Expect empty scene without objects!')

        loc = [0, 0, 0]
        uv_pos = [0, 0]
        for i in range(count):
            # TestGeometry.create(context, model=model)
            TestGeometry.create(context, model=model, location=loc, uv_position=uv_pos)
            loc[0] += -4
            uv_pos[0] += -1

        _set_edit_mode(context)
        bpy.ops.mesh.select_mode(use_extend=False, use_expand=False, type='FACE')

        if context.mode != 'EDIT_MESH':
            raise AddonTestError('PREPARE> Edit mode is expected!')

        if context.active_object is None:
            raise AddonTestError('PREPARE> Active object was not created!')

    @classmethod
    def reset_td_state(cls, context: bpy.types.Context):
        context.scene.zen_uv.td_props.TD_TextureSizeX = ReferenceValues.constants.default_image_x
        context.scene.zen_uv.td_props.TD_TextureSizeY = ReferenceValues.constants.default_image_y
        context.scene.zen_uv.td_props.td_unit = ReferenceValues.constants.default_units

    @classmethod
    def UnitTestFull(cls, context: bpy.types.Context):
        from ZenUV.utils.generic import ZenReport
        RP = ZenReport()
        Log.debug_header("Unit Test Texel Density Sys")
        Log.debug('Not Performed. Currently in Dev.')
        # RP.
        return RP

    @classmethod
    def PropertiesTest(cls, context: bpy.types.Context):
        # from ZenUV.prop.texel_density_props import ZUV_TdProperties
        from ZenUV.prop.zuv_preferences import get_prefs
        l_props = [
            'prp_current_td',
            'td_checker',
            'td_set_mode',
            'prp_uv_coverage',
            'td_unit',
            'TD_TextureSizeX',
            'TD_TextureSizeY',
            'td_im_size_presets',
            'col_equal',
            'col_less',
            'col_over',
        ]
        for prp in l_props:
            print(f'{prp = } in ZUV_TdProperties --> \t{hasattr(context.scene.zen_uv.td_props, prp)}')
        addon_prefs = get_prefs()
        print('\n\n')
        for prp in l_props:
            print(f'{prp = } in Zen UV Addon Properties --> \t{hasattr(addon_prefs, prp)}')

    @classmethod
    def dev_test_get_texel_density(cls, context):
        Log.debug_header("Test bpy.ops.uv.zenuv_get_texel_density()")

        TdTestModule.prepare_dev_td_test(context)
        TdTestModule.reset_td_state(context)

        ref_value = ReferenceValues.constants.dev_test
        temp_value = ReferenceValues.dev_td_temp_value

        Log.info(f'Reference TD --> {ref_value}')
        Log.info(f'Temporary TD --> {temp_value}')
        bpy.ops.mesh.select_all(action='SELECT')
        # _set_object_mode(context)
        _set_edit_mode(context)

        context.scene.zen_uv.td_props.prp_current_td = temp_value

        Log.info(f"Current TD is set to temporary value: {temp_value}")

        bpy.ops.uv.zenuv_get_texel_density()

        Log.info(f"Test performed. Result TD is {context.scene.zen_uv.td_props.prp_current_td}")

        if context.scene.zen_uv.td_props.prp_current_td != ref_value:
            raise AddonTestError(f"TEST> EDIT Mode. Result TD must be {ref_value} instead of {temp_value}")

        Log.debug_header_short(' Finished ')


# Texel Density System. Object Mode --> End
# ---------------------------------------------------------------------------------------


# Texel Density System. Mesh Mode --> Start

def Test_uv_zenuv_clear_baked_texel_density(context):
    ''' Disable displaying Texel Density in Viewport by chosen TD Checker value and colors '''
    # bpy.ops.uv.zenuv_clear_baked_texel_density(map_type='BALANCED')
    raise AddonTestManual


def Test_uv_zenuv_bake_td_to_vc_balanced(context):
    ''' Display Balanced Texel Density in Viewport by chosen TD Checker value and colors '''
    # bpy.ops.uv.zenuv_bake_td_to_vc(face_mode=False)
    raise AddonTestManual


def Test_uv_zenuv_get_texel_density(context):
    ''' Get Texel Density from selected Islands '''

    Log.info("Testing --> Get Texel Density from selected Objects In EDIT_MESH mode")

    TdTestModule.prepare_dev_td_test(context)
    TdTestModule.reset_td_state(context)

    bpy.ops.mesh.select_all(action='SELECT')
    # _set_object_mode(context)
    _set_edit_mode(context)
    temp_value = 12.5
    res_value = 128

    context.scene.zen_uv.td_props.prp_current_td = temp_value

    Log.info(f"Current TD is set to temporary value: {temp_value}")

    bpy.ops.uv.zenuv_get_texel_density()

    Log.info(f"Test performed. Result TD is {context.scene.zen_uv.td_props.prp_current_td}")

    if context.scene.zen_uv.td_props.prp_current_td != res_value:
        raise AddonTestError(f"TEST> EDIT Mode. Result TD must be {res_value} instead of {temp_value}")

    Log.info("Testing --> Get Texel Density from selected Objects In OBJECT mode")

    TdTestModule.prepare_dev_td_test(context)
    TdTestModule.reset_td_state(context)

    _set_object_mode(context)

    temp_value = 16.4
    test_value = 128.0

    context.scene.zen_uv.td_props.prp_current_td = temp_value

    Log.info(f"Current TD is set to temporary value: {temp_value}")

    bpy.ops.uv.zenuv_get_texel_density('INVOKE_DEFAULT')

    res_value = context.scene.zen_uv.td_props.prp_current_td
    Log.info(f"Test performed. Result TD is {res_value}")

    if res_value != test_value:
        raise AddonTestError(f"TEST> OBJECT Mode. Result TD must be {test_value} instead of {res_value}")


def Test_uv_zenuv_set_texel_density(context):
    ''' Set Texel Density to selected Islands '''

    Log.info("Testing --> Set Texel Density in EDIT_MESH mode")

    TdTestModule.prepare_dev_td_test(context)

    TdTestModule.reset_td_state(context)
    res_value = 12.0

    context.scene.zen_uv.td_props.prp_current_td = 2.0
    bpy.ops.uv.zenuv_get_texel_density()
    Log.info(f"Current TD is {context.scene.zen_uv.td_props.prp_current_td}")

    context.scene.zen_uv.td_props.prp_current_td = res_value
    Log.info(f"Current TD is set to value: {res_value}")
    bpy.ops.uv.zenuv_set_texel_density(td_value=res_value)
    bpy.ops.uv.zenuv_get_texel_density()
    Log.info(f"Test performed. Current TD is {context.scene.zen_uv.td_props.prp_current_td}")

    if context.scene.zen_uv.td_props.prp_current_td != res_value:
        raise AddonTestError(f"TEST> Result TD must be {res_value} instead of {context.scene.zen_uv.td_props.prp_current_td}")

    Log.info("Testing --> Set Texel Density in OBJECT mode")

    # _prepare_test(context)
    TdTestModule.prepare_dev_td_test(context)
    _set_object_mode(context)
    TdTestModule.reset_td_state(context)

    # 1-st
    bpy.ops.uv.zenuv_set_texel_density(global_mode=False, td_value=1024, image_size_x=1024, image_size_y=1024, units='m', set_mode='OVERALL')
    bpy.ops.uv.zenuv_get_texel_density('INVOKE_DEFAULT')
    Log.info(f"TEST 01> Texel Density is {context.scene.zen_uv.td_props.prp_current_td}")

    if context.scene.zen_uv.td_props.prp_current_td != 1024:
        string = f"TEST 01> Resulted TD must be 1024 instead of {context.scene.zen_uv.td_props.prp_current_td}"
        raise AddonTestError(string)

    # 2-nd
    bpy.ops.uv.zenuv_set_texel_density(global_mode=False, td_value=50, image_size_x=1024, image_size_y=1024, units='m', set_mode='OVERALL')
    bpy.ops.uv.zenuv_get_texel_density('INVOKE_DEFAULT')
    Log.info(f"TEST 02> Texel Density is {context.scene.zen_uv.td_props.prp_current_td}")

    if context.scene.zen_uv.td_props.prp_current_td != 50:
        raise AddonTestError(f"TEST 02> Resulted TD must be 50 instead of {context.scene.zen_uv.td_props.prp_current_td}")


def Test_uv_zenuv_get_uv_coverage(context):
    ''' Recalculate UV Coverage '''
    TdTestModule.reset_td_state(context)
    context.scene.zen_uv.td_props.prp_uv_coverage = 0
    tested_coverage = 75.0
    _set_object_mode(context)
    Log.info(f"UV Coverage is reset. Current UV Coverage: {context.scene.zen_uv.td_props.prp_uv_coverage}")
    Log.info("Testing in OBJECT Mode...")
    bpy.ops.uv.zenuv_get_uv_coverage()

    res_value = round(context.scene.zen_uv.td_props.prp_uv_coverage, 0)

    Log.info(f"Test performed. Current UV Coverage: {res_value}")

    if res_value != tested_coverage:
        raise AddonTestError(f"TEST> UV Coverage in the OBJECT Mode must be {tested_coverage} instead of {res_value}")

    Log.info("Testing in EDIT Mode...")
    _set_edit_mode(context)
    context.scene.zen_uv.td_props.prp_uv_coverage = 0
    Log.info(f"UV Coverage is reset. Current UV Coverage: {context.scene.zen_uv.td_props.prp_uv_coverage}")

    bpy.ops.uv.zenuv_get_uv_coverage()

    res_value = round(context.scene.zen_uv.td_props.prp_uv_coverage, 0)

    Log.info(f"Test performed. Current UV Coverage: {res_value}")

    if res_value != tested_coverage:
        raise AddonTestError(f"TEST> UV Coverage in the EDIT mode must be {tested_coverage} instead of {res_value}")


def Test_uv_zenuv_get_image_size_uv_layout(context):
    ''' Get image size from the image displayed in UV Editor '''
    TdTestModule.reset_td_state(context)
    image_name = "Zen UV Test Image"
    Log.info(f"Init Image Size X is: {context.scene.zen_uv.td_props.TD_TextureSizeX}")

    bpy.ops.image.new(name=image_name, width=122, height=123, color=(0, 0, 0, 1), alpha=True, generated_type='COLOR_GRID', float=False, use_stereo_3d=False, tiled=False)
    test_image = bpy.data.images[image_name]

    for area in bpy.context.screen.areas:
        if area.type == 'IMAGE_EDITOR':
            area.spaces.active.image = test_image

    bpy.ops.uv.zenuv_get_image_size_uv_layout()
    Log.info(f"Result Image Size X is: {context.scene.zen_uv.td_props.TD_TextureSizeX}")
    if context.scene.zen_uv.td_props.TD_TextureSizeX != 122:
        raise AddonTestError(f"TEST> Image Size X is {context.scene.zen_uv.td_props.prp_current_td} instead of 122. Possible UV Editor not in the UI. Recommended Manual Testing.")

# Texel Density System Mesh Mode --> End
# ---------------------------------------------------------------------------------------


# Texel Density System Presets Testing --> Start

def Test_zen_tdpr_set_td_from_preset(context):
    ''' Set TD from active preset to selected Islands '''
    TdTestModule.reset_td_state(context)
    bpy.ops.zen_tdpr.new_item()
    bpy.ops.zen_tdpr.set_td_from_preset()
    bpy.ops.uv.zenuv_get_texel_density()
    Log.debug()


def Test_zen_tdpr_move_item(context):
    ''' Move an item in the list '''
    TdTestModule.reset_td_state(context)
    bpy.ops.zen_tdpr.clear_presets()
    bpy.ops.zen_tdpr.new_item()
    bpy.ops.zen_tdpr.new_item()
    bpy.ops.zen_tdpr.new_item()
    bpy.ops.zen_tdpr.move_item(direction='UP')
    bpy.ops.zen_tdpr.move_item(direction='DOWN')


def Test_zen_tdpr_new_item(context):
    '''Add a new item to the list'''
    TdTestModule.reset_td_state(context)
    scene = context.scene
    Log.info(f"Items In the List: {len(scene.zen_tdpr_list)}")
    bpy.ops.zen_tdpr.clear_presets()
    Log.info(f"Clear List performed. Items In the List: {len(scene.zen_tdpr_list)}")
    bpy.ops.zen_tdpr.new_item()
    Log.info(f"New Item created. Items In the List: {len(scene.zen_tdpr_list)}")
    if len(scene.zen_tdpr_list) != 1:
        raise AddonTestError(f"TEST> Items in the List must be 1 instead of {len(scene.zen_tdpr_list)}")


def Test_zen_tdpr_delete_item(context):
    ''' Delete the selected item from the list '''
    TdTestModule.reset_td_state(context)
    scene = context.scene
    # scene.zen_tdpr_list_index
    Log.info(f"Items In the List: {len(scene.zen_tdpr_list)}")
    bpy.ops.zen_tdpr.clear_presets()
    Log.info(f"Presets Cleared. Items In the List: {len(scene.zen_tdpr_list)}")
    bpy.ops.zen_tdpr.new_item()
    Log.info(f"New Item Created Items In the List: {len(scene.zen_tdpr_list)}")
    bpy.ops.zen_tdpr.delete_item()
    Log.info(f"The Item deleted. Items In the List: {len(scene.zen_tdpr_list)}")


def Test_zen_tdpr_clear_presets(context):
    ''' Clear '''
    TdTestModule.reset_td_state(context)
    scene = context.scene
    Log.info(f"Items In the List: {len(scene.zen_tdpr_list)}")
    bpy.ops.zen_tdpr.new_item()
    bpy.ops.zen_tdpr.new_item()
    bpy.ops.zen_tdpr.new_item()
    Log.info(f"Presets generated. Items In the List: {len(scene.zen_tdpr_list)}")
    bpy.ops.zen_tdpr.clear_presets()
    Log.info(f"List Cleared. Items In the List: {len(scene.zen_tdpr_list)}")


# def Test_uv_zenuv_bake_td_to_vc_preset(context):
#     ''' Display Presets '''
#     # bpy.ops.uv.zenuv_bake_td_to_vc_preset(face_mode=False, presets_only=False)
#     raise AddonTestManual


def Test_zen_tdpr_select_by_texel_density(context):
    ''' Select Islands By Texel Density '''
    TdTestModule.reset_td_state(context)
    import bmesh
    tested_value = 128.0
    context.scene.zen_uv.td_props.prp_current_td = tested_value
    bpy.ops.mesh.select_all(action='DESELECT')
    obj = context.object
    bm = bmesh.from_edit_mesh(obj.data).copy()
    s_faces = [f.index for f in bm.faces if f.select]
    bm.free()
    Log.info(f'Current object: {obj.name}. Selected faces: {len(s_faces)}')
    bpy.ops.zen_tdpr.select_by_texel_density(texel_density=tested_value, treshold=0.01, clear_selection=True, sel_underrated=False, sel_overrated=False, by_value=True)

    bm = bmesh.from_edit_mesh(obj.data).copy()
    s_faces = [f.index for f in bm.faces if f.select]
    bm.free()
    Log.info(f'Test performed. Current object: {obj.name}. Selected faces: {len(s_faces)}')
    if len(s_faces) != 6:
        raise AddonTestError(f"TEST> Selected faces with TD {tested_value} must be 6 instead of {len(s_faces)}")


def Test_zen_tdpr_get_td_from_preset(context):
    '''Get TD from selected Islands to active preset'''
    TdTestModule.reset_td_state(context)
    bpy.ops.zen_tdpr.clear_presets()
    bpy.ops.zen_tdpr.new_item()
    from ZenUV.ops.texel_density.td_presets import PRESET_NEW
    default_new_value = PRESET_NEW["value"]
    Log.info(f"New List Item Created. Current Value: {default_new_value}")
    bpy.ops.zen_tdpr.get_td_from_preset()
    scene = context.scene
    list_index = scene.zen_tdpr_list_index
    if list_index in range(len(scene.zen_tdpr_list)):
        new_value = scene.zen_tdpr_list[list_index].value
    Log.info(f"Operator test performed. Current Value: {new_value}")
    if new_value != 128.0:
        raise AddonTestError(f"TEST> Resulted TD must be 128.0 instead of {new_value}")

# Texel Density System Presets Testing --> End
# ---------------------------------------------------------------------------------------


tests_texel_density = (
    Test_zen_tdpr_move_item,
    Test_zen_tdpr_set_td_from_preset,
    Test_zen_tdpr_clear_presets,
    # Test_uv_zenuv_bake_td_to_vc_preset,
    Test_zen_tdpr_delete_item,
    Test_uv_zenuv_clear_baked_texel_density,
    Test_zen_tdpr_select_by_texel_density,
    Test_uv_zenuv_bake_td_to_vc_balanced,
    # Test_zenuv_set_current_td_to_checker_td,
    Test_zen_tdpr_new_item,
    Test_zen_tdpr_get_td_from_preset,
    Test_uv_zenuv_get_texel_density,
    Test_uv_zenuv_set_texel_density,
    Test_uv_zenuv_get_uv_coverage,
    Test_uv_zenuv_get_image_size_uv_layout
)


classes = [
    ZUV_OT_UnitTestTexelDensity,
    ZUV_OT_DevTestTexelDensity,
    ZUV_OT_TestPropertiesTexelDensity
]


def register():
    from bpy.utils import register_class
    for cl in classes:
        register_class(cl)


def unregister():
    from bpy.utils import unregister_class
    for cl in classes:
        unregister_class(cl)


if __name__ == "__main__":
    pass
