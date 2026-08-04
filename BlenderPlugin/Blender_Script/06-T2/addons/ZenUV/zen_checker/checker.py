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

# Copyright 2023, Valeriy Yatsenko

""" Zen Checker Texture System """

import bpy
from json import dumps

from .get_prefs import get_prefs, DEF_OVERRIDE_IMAGE_NAME

from ZenUV.ico import icon_get
from ZenUV.zen_checker.zen_checker_labels import ZCheckerLabels as label
from ZenUV.utils.generic import switch_shading_style, get_current_shading_style
from ZenUV.zen_checker.files import load_checker_image, update_files_info
from ZenUV.utils.messages import zen_message
from ZenUV.utils.blender_zen_utils import ZenPolls
from ZenUV.utils.register_util import RegisterUtils
from ZenUV.utils.vlog import Log


ZEN_IMAGE_NODE_NAME = "ZenUV_Texture_node"
ZEN_IMAGE_NAME = "zen-checker@4x.png"
ZEN_GENERATED_IMAGE_NAME = "BlenderChecker"
ZEN_GLOBAL_OVERRIDER_NAME = "Zen UV Checker"
ZEN_GLOBAL_OVERRIDER_NAME_OLD = "ZenUV_Checker"
ZEN_OVERRIDER_NAME = "ZenUV_Override"
ZEN_GENERIC_MAT_NAME = "ZenUV_Generic_Material"
ZEN_NODE_COLOR = (0.701, 0.017, 0.009)
ZEN_TILER_NODE_NAME = "ZenUV_Tiler_node"
ZEN_OFFSETTER_NODE_NAME = "ZenUV_Offsetter_node"


MES_NO_INP_CHANNELS = 'Zen Checker node group has no input channels. Need to reset the Checker'
MES_NO_OUT_CHANNELS = 'Zen Checker node group has no output channels. Need to reset the Checker'


class InpSocket:

    name: str = 'MainShader'
    in_out: str = 'INPUT'
    socket_type: str = 'NodeSocketShader'


class OutSocket:

    name: str = 'MixedShader'
    in_out: str = 'OUTPUT'
    socket_type: str = 'NodeSocketColor'


class VecAdd:

    inp_vec1 = None
    inp_vec2 = None
    out = None

    def create(self, node_group):
        add_node = node_group.nodes.new(type="ShaderNodeVectorMath")
        self.inp_vec1 = add_node.inputs[0]
        self.inp_vec2 = add_node.inputs[1]
        self.out = add_node.outputs[0]
        add_node.location = (-191.2, -2.82)


class VecCombine:

    inp = None
    out = None

    def create(self, node_group):
        comb_node = node_group.nodes.new(type="ShaderNodeCombineXYZ")
        self.inp = comb_node.inputs[1]
        self.out = comb_node.outputs[0]
        comb_node.location = (-419.8, -216.74)


class InpValue:

    value = None
    out = None

    def create(self, node_group):
        val_node = node_group.nodes.new(type="ShaderNodeValue")
        val_node.name = ZEN_OFFSETTER_NODE_NAME
        self.out = val_node.outputs[0]
        val_node.location = (-646.6902, -304.1786)


class CheckerOffsetter:

    add_node = None
    combine_node = None
    offset_value_node = None
    offset_value = 0.0
    inp = None
    out = None

    def init(self, node_group):
        self.add_node = VecAdd()
        self.add_node.create(node_group)
        self.combine_node = VecCombine()
        self.combine_node.create(node_group)
        self.offset_value_node = InpValue()
        self.offset_value_node.create(node_group)
        self.inp = self.add_node.inp_vec1
        self.out = self.add_node.out

        # Create Links
        node_group.links.new(self.offset_value_node.out, self.combine_node.inp)
        node_group.links.new(self.combine_node.out, self.add_node.inp_vec2)


def remove_zen_generic_mats():
    """Remove all Zen Generic Materials from bpy.data"""
    gen_mats = [m for m in bpy.data.materials if ZEN_GENERIC_MAT_NAME in m.name]
    # print("Generic Mats:", gen_mats)
    for mat in gen_mats:
        bpy.data.materials.remove(mat)


def zen_generic_mat():
    """ Return a Zen UV Generic material or create one and return """
    generic_material = bpy.data.materials.get(ZEN_GENERIC_MAT_NAME, None)
    if not generic_material:
        generic_material = bpy.data.materials.new(name=ZEN_GENERIC_MAT_NAME)
        generic_material.use_nodes = True
        generic_material.use_fake_user = True
    return generic_material


def get_zen_checker_image(context):
    """ Return Zen UV Checker image or create one and Return """
    from . properties import ZUV_CheckerProperties
    addon_prefs = get_prefs().uv_checker_props
    checker_prefs: ZUV_CheckerProperties = context.scene.zen_uv_checker

    if checker_prefs.use_custom_image and checker_prefs.override_image_name != DEF_OVERRIDE_IMAGE_NAME:
        image = bpy.data.images.get(checker_prefs.override_image_name, None)
    else:
        image = load_checker_image(context, addon_prefs.ZenCheckerImages)
    if image is not None:
        return image

    # Log.debug('TexChecker', f'image is {image}. Error In "get_zen_checker_image')
    # bpy.ops.wm.call_menu(name="ZUV_MT_ZenChecker_Popup")
    return load_checker_image(context, addon_prefs.ZenCheckerImages)


def zen_checker_image_update(context, _image):
    interpolation = {True: 'Linear', False: 'Closest'}
    _overrider = None
    if bpy.data.node_groups.items():
        _overrider = bpy.data.node_groups.get(ZEN_GLOBAL_OVERRIDER_NAME, None)
    if _overrider:
        if hasattr(_overrider, "nodes"):
            image_node = _overrider.nodes.get(ZEN_IMAGE_NODE_NAME)
            if image_node:
                image_node.image = _image
                image_node.interpolation = interpolation[context.scene.zen_uv.tex_checker_interpolation]


def zen_checker_image_ensure(context):
    """
    Enshure Checker (any) image exist in ZEN IMAGE NODE.
    """
    _overrider = None
    if bpy.data.node_groups.items():
        _overrider = bpy.data.node_groups.get(ZEN_GLOBAL_OVERRIDER_NAME, None)
    if _overrider:
        if hasattr(_overrider, "nodes"):
            image_node = _overrider.nodes.get(ZEN_IMAGE_NODE_NAME)
            if image_node:
                if not image_node.image:
                    Log.debug('TexChecker', f'image_node.image is {image_node.image}. Error In "zen_checker_image_ensure')
                    bpy.ops.wm.call_menu(name="ZUV_MT_ZenChecker_Popup")
                else:
                    image_node.image = get_zen_checker_image(context)
                return image_node.image
    return None


def enshure_material_slots(context, _obj):
    """ Return material slots or create single material slot if empty """
    return _obj.material_slots or create_material_slot(context, _obj)


def create_material_slot(context, _obj):
    """ Create Material Slot and Zen Generic material inside slot. Return new slot """
    context.view_layer.objects.active = _obj
    bpy.ops.object.material_slot_add()

    return _obj.material_slots


def enshure_material(_slot):
    """ If slot material is empty - insert in given slot
    Zen UV Generic material and switch to tree mode """
    if not _slot.material:
        _slot.material = zen_generic_mat().copy()


def enshure_user_mats_consistency(context, _objs):
    """ Refine and repair user materials from selected objects """
    for _obj in _objs:
        for _slot in enshure_material_slots(context, _obj):
            enshure_material(_slot)


def get_materials_from_objects(context, objs):
    """ Return materials from given objects set """
    _materials = []
    for _obj in objs:
        for _slot in enshure_material_slots(context, _obj):
            _materials.append(_slot.material)
    return _materials


def create_zen_global_overrider_node_tree(context, _overrider, create_in_out=True):
    """ Create node tree for Zen UV Global Overrider """
    # Create group inputs
    group_inputs = _overrider.nodes.new('NodeGroupInput')
    group_inputs.location = (-200, 0)

    # Create group outputs
    group_outputs = _overrider.nodes.new('NodeGroupOutput')
    group_outputs.location = (400, 0)

    if create_in_out:
        if ZenPolls.version_since_4_0_0:
            if hasattr(_overrider, 'interface'):

                if _overrider.interface.items_tree.get(InpSocket.name, None) is None:
                    _overrider.interface.new_socket(
                        InpSocket.name,
                        in_out=InpSocket.in_out,
                        socket_type=InpSocket.socket_type)

                if _overrider.interface.items_tree.get(OutSocket.name, None) is None:
                    _overrider.interface.new_socket(
                        OutSocket.name,
                        in_out=OutSocket.in_out,
                        socket_type=OutSocket.socket_type)
            else:
                return False
        else:
            if not len(_overrider.inputs):
                _overrider.inputs.new('NodeSocketShader', InpSocket.name)
            else:
                if _overrider.inputs.get(InpSocket.name, None) is None:
                    _overrider.inputs.new('NodeSocketShader', InpSocket.name)
            if not len(_overrider.outputs):
                _overrider.outputs.new('NodeSocketShader', OutSocket.name)
            else:
                if _overrider.outputs.get(OutSocket.name, None) is None:
                    _overrider.outputs.new('NodeSocketShader', OutSocket.name)

    # Create image node
    image_node = _overrider.nodes.new(type='ShaderNodeTexImage')
    image_node.name = ZEN_IMAGE_NODE_NAME
    image_node.image = get_zen_checker_image(context)

    # Create Tiler
    tiler = _overrider.nodes.new(type="ShaderNodeMapping")
    tiler.vector_type = "VECTOR"
    tiler.name = ZEN_TILER_NODE_NAME
    uv_source = _overrider.nodes.new(type="ShaderNodeTexCoord")

    # Create Offsetter
    offsetter = CheckerOffsetter()
    offsetter.init(_overrider)

    # Link outputs
    _overrider.links.new(uv_source.outputs['UV'], offsetter.inp)
    _overrider.links.new(offsetter.out, tiler.inputs['Vector'])
    _overrider.links.new(image_node.outputs[0], group_outputs.inputs[OutSocket.name])
    _overrider.links.new(tiler.outputs[0], image_node.inputs['Vector'])

    # Set locations
    tiler.location = (0.0, 0.0)
    image_node.location = (260.28, 2.87)
    uv_source.location = (-420.75, 58.79)
    offsetter.location = (-630.76, -320.93)
    group_outputs.location = (585.25, 146.0)
    group_inputs.location = (-818.57, 149.64)

    return True


def Zen_Global_Overrider(context):
    """ Create and return Zen UV Global Overrider """
    # Create a global overrider node group
    global_overrider = bpy.data.node_groups.new(ZEN_GLOBAL_OVERRIDER_NAME, 'ShaderNodeTree')
    if create_zen_global_overrider_node_tree(context, global_overrider) is False:
        return False
    global_overrider.use_fake_user = True
    return global_overrider


def disable_overrider(context, _materials):
    """ Disable overrider """
    # print("Overrider Removing --<")
    for _material in _materials:
        overriders = get_overrider(_material)
        for overrider in overriders:
            node_before_overrider = None
            node_after_overrider = None

            if hasattr(overrider, "inputs"):
                if len(overrider.inputs):
                    inp_channel = overrider.inputs.get(InpSocket.name)
                    if inp_channel is not None and inp_channel.links:
                        node_before_overrider = inp_channel.links[0].from_node
                else:
                    CheckerMessenger.state = False
                    CheckerMessenger.message = MES_NO_INP_CHANNELS

            if hasattr(overrider, "outputs"):
                if len(overrider.outputs):
                    out_channel = overrider.outputs.get(OutSocket.name)
                    if out_channel is not None and out_channel.links:
                        node_after_overrider = out_channel.links[0].to_node
                else:
                    CheckerMessenger.state = False
                    CheckerMessenger.message = MES_NO_OUT_CHANNELS

            _links = _material.node_tree.links
            # Remove link from Overrider node to User output material node
            if node_before_overrider:
                # print("NODE BEFORE OVERRIDER: ", node_before_overrider)
                _links.remove(node_before_overrider.outputs[0].links[0])
            # Create link from shader (prev node) to User output material node
            if node_before_overrider and node_after_overrider:
                _links.new(node_before_overrider.outputs[0], node_after_overrider.inputs[0])
            # print("Overrider", overrider, " disabled in: ", _material.name)
            if overrider:
                _material.node_tree.nodes.remove(overrider)
                if node_after_overrider:
                    node_after_overrider.socket_value_update(context)


def get_materials_with_overrider(_materials):
    """ Returm all the materials contained overrider from given set of the materials """
    _materials_with_overrider = []
    for material in _materials:
        if hasattr(material, "node_tree"):
            if hasattr(material.node_tree, "nodes"):
                for node in material.node_tree.nodes:
                    if hasattr(node, "node_tree") and node.node_tree is not None:
                        if node.node_tree.name == ZEN_GLOBAL_OVERRIDER_NAME \
                                or node.node_tree.name == ZEN_GLOBAL_OVERRIDER_NAME_OLD:
                            _materials_with_overrider.append(material)
    return _materials_with_overrider


def has_materials_with_override(context: bpy.types.Context):
    for obj in context.selected_objects:
        if obj.type == 'MESH' and len(obj.data.polygons) != 0:
            for slot in obj.material_slots:
                material = slot.material
                if hasattr(material, "node_tree"):
                    if hasattr(material.node_tree, "nodes"):
                        for node in material.node_tree.nodes:
                            if hasattr(node, "node_tree") and node.node_tree is not None:
                                if node.node_tree.name == ZEN_GLOBAL_OVERRIDER_NAME \
                                        or node.node_tree.name == ZEN_GLOBAL_OVERRIDER_NAME_OLD:
                                    return True
    return False


def get_overrider(_material):
    """ Return overriders from given material """
    overriders = []
    if hasattr(_material, "node_tree"):
        if hasattr(_material.node_tree, "nodes"):
            for _node in _material.node_tree.nodes:
                if hasattr(_node, "node_tree") and _node.node_tree is not None:
                    if _node.node_tree.name == ZEN_GLOBAL_OVERRIDER_NAME \
                            or _node.node_tree.name == ZEN_GLOBAL_OVERRIDER_NAME_OLD:
                        overriders.append(_node)
    return overriders


def implement_zen_overrider(context, _obj, _GlobalOverrider):
    """ Zen Overrider Implementation """
    # print("Overrider Implementation -->")
    # Check material slots. If NOT - Create one and standart material.
    material_slots = enshure_material_slots(context, _obj)

    for slot in material_slots:
        enshure_material(slot)
        slot.material.use_nodes = True
        mat_nodes = slot.material.node_tree.nodes

        # Check if Zen Overrider exist in Current material nodes
        zen_checker = mat_nodes.get(ZEN_OVERRIDER_NAME)
        if zen_checker:
            return

        # Implement Zen Overraider in to user material
        links = slot.material.node_tree.links

        # Define Material Output Node
        user_material_output_nodes = [node for node in mat_nodes if node.bl_rna.name == "Material Output"]
        if not user_material_output_nodes:
            mat_nodes.new("ShaderNodeOutputMaterial")
            user_material_output_nodes = [node for node in mat_nodes if node.bl_rna.name == "Material Output"]
        # user_material_output_node = user_material_output_nodes[0]
        for count, mat_out_node in enumerate(user_material_output_nodes):
            # print("Material Output Node: ", count)
            zen_checker = mat_nodes.new(type="ShaderNodeGroup")
            zen_checker.node_tree = _GlobalOverrider
            zen_checker.name = ZEN_OVERRIDER_NAME
            zen_checker.location = (200, 200)
            mat_nodes.active = zen_checker
            zen_checker.use_custom_color = True
            zen_checker.color = ZEN_NODE_COLOR

            user_mat_out_node_inputs = mat_out_node.inputs
            out_location = mat_out_node.location
            zen_checker.location = (out_location.x - 200, out_location.y)

            # Define Zen Overrider Input and Output Channels
            zen_overrider_input = zen_checker.inputs.get(InpSocket.name, None)
            zen_overrider_output = zen_checker.outputs.get(OutSocket.name, None)

            prev_user_link = None
            if user_mat_out_node_inputs["Surface"].links:
                prev_user_link = user_mat_out_node_inputs["Surface"].links[0].from_node

            if prev_user_link and prev_user_link.name != ZEN_OVERRIDER_NAME:
                if zen_overrider_output is not None:
                    links.new(zen_overrider_output, user_mat_out_node_inputs[0])
                else:
                    CheckerMessenger.state = False
                    CheckerMessenger.message = MES_NO_OUT_CHANNELS
                    return False
                if zen_overrider_input is not None:
                    prev_user_link = links.new(zen_overrider_input, prev_user_link.outputs[0])
                else:
                    CheckerMessenger.state = False
                    CheckerMessenger.message = MES_NO_INP_CHANNELS
                    return False
            else:
                if zen_overrider_output is not None:
                    links.new(zen_overrider_output, user_mat_out_node_inputs[0])
                else:
                    CheckerMessenger.state = False
                    CheckerMessenger.message = MES_NO_OUT_CHANNELS
                    return False


def repair_zen_generic_mat():
    """ Repair Zen UV Generic material """
    mat = zen_generic_mat()
    # mat.use_nodes = True
    _links = mat.node_tree.links
    pr_bsdf_node = mat.node_tree.nodes.get("Principled BSDF")
    # print("NODE BSDF", pr_bsdf_node)
    if not pr_bsdf_node:
        pr_bsdf_node = mat.node_tree.nodes.new(type="ShaderNodeBsdfPrincipled")
    pr_bsdf_node_output = pr_bsdf_node.outputs[0]

    mat_output = mat.node_tree.nodes.get("Material Output")
    # print("NODE OUTPUT", pr_bsdf_node)
    if not mat_output:
        mat_output = mat.node_tree.nodes.new(type="ShaderNodeBsdfPrincipled")
    mat_output_input = mat_output.inputs[0]

    _links.new(pr_bsdf_node_output, mat_output_input)


def repair_zen_overrider(context):
    """ Repair Zen UV Global overrider to default state or create new if no exist in data blocks """
    # print("Zen UV: Reset Checker")
    _overrider = None
    if bpy.data.node_groups.items():
        _overrider = bpy.data.node_groups.get(ZEN_GLOBAL_OVERRIDER_NAME, None)
    if _overrider:
        # print("Zen UV Global overrider repairing.")
        _overrider.nodes.clear()
        if create_zen_global_overrider_node_tree(context, _overrider, create_in_out=True) is False:
            return False
    else:
        _overrider = Zen_Global_Overrider(context)


def remove_zen_overrider(context):
    """ Remove Zen UV Overrider from all Materials in scene """
    disable_overrider(context, bpy.data.materials)


def disable_checker_in_uv_layout(context):
    screen = context.screen
    for area in screen.areas:
        if area.type == 'IMAGE_EDITOR':
            area.spaces.active.image = None


class CheckerMessenger:

    state: bool = True
    message: str = ''

    @classmethod
    def clear(cls):
        cls.state = True
        cls.message = ''


class ZUVChecker_OT_CheckerOn(bpy.types.Operator):

    bl_idname = "view3d.zenuv_checker_on"
    bl_label = 'Checker On'
    bl_description = 'Add checker texture to the selected mesh'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        if bpy.ops.view3d.zenuv_checker_toggle.poll():
            bpy.ops.view3d.zenuv_checker_toggle(action='ON')

        return {'FINISHED'}


class ZUVChecker_OT_CheckerOff(bpy.types.Operator):

    bl_idname = "view3d.zenuv_checker_off"
    bl_label = 'Checker Off'
    bl_description = 'Remove checker texture from the selected mesh'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        if bpy.ops.view3d.zenuv_checker_toggle.poll():
            bpy.ops.view3d.zenuv_checker_toggle(action='OFF')

        return {'FINISHED'}


class ZUVChecker_OT_CheckerToggle(bpy.types.Operator):
    """ Zen UV Checker Processor """
    bl_idname = "view3d.zenuv_checker_toggle"
    bl_label = label.OT_CHECKER_TOGGLE_LABEL
    bl_description = label.OT_CHECKER_TOGGLE_DESC
    bl_options = {'REGISTER', 'UNDO'}

    checked: bpy.props.BoolProperty(
        name='Checked',
        options={'HIDDEN', 'SKIP_SAVE'},
        default=False
    )
    action: bpy.props.EnumProperty(
        name='Action',
        description='Action',
        items=[
            ("ON", "On", "Turn on checker"),
            ("OFF", "Off", "Turn off checker"),
            ("TOGGLE", "Toggle", "Toggle checker")
            ],
        default='TOGGLE',
        options={'HIDDEN', 'SKIP_SAVE'},
        )

    LITERAL_PREV_IMAGE = 'zenuv_checker_prev_image'
    LITERAL_TOGGLE = 'zenuv_checker_toggle'

    @classmethod
    def draw_toggled(cls, layout: bpy.types.UILayout, context: bpy.types.Context):
        b_is_checked = has_materials_with_override(context)
        layout.operator(
            cls.bl_idname,
            depress=b_is_checked,
            icon_value=icon_get(label.ZEN_CHECKER_ICO)).action = 'TOGGLE'

    @classmethod
    def poll(cls, context):
        return context.area.type in {'VIEW_3D', 'IMAGE_EDITOR'}

    def execute(self, context):
        from ZenUV.ui.pie import ZsPieFactory
        from ZenUV.utils.generic import resort_by_type_mesh_in_edit_mode_and_sel

        ZsPieFactory.mark_pie_cancelled()
        CheckerMessenger.clear()

        objs = resort_by_type_mesh_in_edit_mode_and_sel(context)
        if len(objs) == 0:
            zen_message(context, "There are no selected objects")
            self.report({'WARNING'}, "There are no selected objects")
            return {'CANCELLED'}

        for obj in objs:
            if len(obj.data.uv_layers) == 0:
                obj.data.uv_layers.new()
            obj.material_slots.update()
            obj.update_from_editmode()
            if obj.display_type != 'TEXTURED':
                self.report({'WARNING'}, f"Zen UV: {obj.name} viewport display mode is {obj.display_type}")

        # Get or create Global Overrider
        GlobalOverrider = bpy.data.node_groups.get(ZEN_GLOBAL_OVERRIDER_NAME) or Zen_Global_Overrider(context)
        if GlobalOverrider is False:
            self.report({'WARNING'}, 'Zen UV: Checker nodes are damaged. Please perform "Reset Checker"')
            zen_message(context, 'Checker nodes are damaged. Please perform "Reset Checker"')
            return {'CANCELLED'}
        enshure_user_mats_consistency(context, objs)
        materials_with_overrider = get_materials_with_overrider(get_materials_from_objects(context, objs))

        bpy.app.driver_namespace[ZUVChecker_OT_CheckerToggle.LITERAL_TOGGLE] = False

        if materials_with_overrider:  # Case checker exist in currently selected objects - Turn Off Checker
            if self.action in {'OFF', 'TOGGLE'}:
                disable_overrider(context, materials_with_overrider)
                prev_color_type = context.scene.zen_uv_checker.prev_color_type
                switch_shading_style(context, prev_color_type if prev_color_type != '' else 'TEXTURE', switch=False)

                if context.space_data.type == 'IMAGE_EDITOR':
                    was_image_name = bpy.app.driver_namespace.get(
                        ZUVChecker_OT_CheckerToggle.LITERAL_PREV_IMAGE, '')
                    if was_image_name:
                        p_image = bpy.data.images.get(was_image_name, None)
                        if p_image:
                            context.space_data.image = p_image

        else:  # Else - Turn On Checker
            if self.action in {'ON', 'TOGGLE'}:
                if context.space_data.type == 'IMAGE_EDITOR':
                    was_image = context.space_data.image
                    bpy.app.driver_namespace[ZUVChecker_OT_CheckerToggle.LITERAL_PREV_IMAGE] = was_image.name if was_image else ''

                p_prev_type = get_current_shading_style(context)
                if p_prev_type is not None:
                    context.scene.zen_uv_checker.prev_color_type = p_prev_type
                repair_zen_generic_mat()
                for obj in objs:
                    implement_zen_overrider(context, obj, GlobalOverrider)
                p_image = zen_checker_image_ensure(context)
                if p_image is not None:

                    bpy.app.driver_namespace[ZUVChecker_OT_CheckerToggle.LITERAL_TOGGLE] = True

                    if context.space_data.type == 'IMAGE_EDITOR':
                        context.space_data.image = p_image
                switch_shading_style(context, "TEXTURE", switch=False)

        context = bpy.context

        for window in context.window_manager.windows:
            for area in window.screen.areas:
                if area.type in {'VIEW_3D', 'IMAGE_EDITOR'}:
                    area.tag_redraw()

        if CheckerMessenger.state is False:
            self.report({'WARNING'}, CheckerMessenger.message)
            return {'CANCELLED'}

        return {'FINISHED'}


class ZUVChecker_OT_Reset(bpy.types.Operator):
    """ Zen UV Checker Reset """
    bl_idname = "view3d.zenuv_checker_reset"
    bl_label = label.OT_CHECKER_RESET_LABEL
    bl_description = label.OT_CHECKER_RESET_DESC
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        from . properties import ZUV_CheckerProperties, get_prefs
        Log.debug('TexChecker', '>> Checker Reseting')
        addon_prefs = get_prefs().uv_checker_props
        checker_prefs: ZUV_CheckerProperties = context.scene.zen_uv_checker

        checker_prefs.use_custom_image = False
        checker_prefs.override_image_name = DEF_OVERRIDE_IMAGE_NAME

        repair_zen_overrider(context)

        context.scene.zen_uv.tex_checker_interpolation = True
        context.scene.zen_uv.tex_checker_tiling = (1.0, 1.0)
        context.scene.zen_uv.tex_checker_offset = 0.0

        addon_prefs.chk_rez_filter = False

        return {'FINISHED'}


class ZUVChecker_OT_Remove(bpy.types.Operator):
    """ Zen UV Checker Remove """
    bl_idname = "view3d.zenuv_checker_remove"
    bl_label = label.OT_CHECKER_REMOVE_LABEL
    bl_description = label.OT_CHECKER_REMOVE_DESC
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        remove_zen_overrider(context)
        disable_checker_in_uv_layout(context)
        remove_zen_generic_mats()
        return {'FINISHED'}


class ZUVChecker_OT_OpenEditor(bpy.types.Operator):
    """ Zen UV Checker Remove """
    bl_idname = "view3d.zenuv_checker_open_editor"
    bl_label = label.OT_CHECKER_OPEN_EDITOR_LABEL
    bl_description = label.OT_CHECKER_OPEN_EDITOR_DESC
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        if context.selected_objects:
            return True

    def execute(self, context):
        try:
            obj = context.selected_objects[0]
            material = obj.material_slots[0].material
            # bpy.context.preferences.active_section = 'VIEWPORT'
            bpy.ops.screen.userpref_show("INVOKE_DEFAULT")
            area = context.window_manager.windows[-1].screen.areas[0]
            area.type = 'NODE_EDITOR'
            # Seems like in 2.9 have some changes in API next line is for
            area.ui_type = 'ShaderNodeTree'

            area.spaces.active.node_tree = material.node_tree
            overrider = material.node_tree.nodes[ZEN_OVERRIDER_NAME]
            # node_group.select = True
            area.spaces.active.node_tree.nodes.active = overrider
            bpy.ops.node.group_edit()
        except Exception:
            print("Seems like problem with Shader editor opening...")

        return {'FINISHED'}


class ZUVChecker_OT_ResetPath(bpy.types.Operator):
    bl_idname = "ops.zenuv_checker_reset_path"
    bl_label = label.OT_RESET_PATH_LABEL
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = label.OT_RESET_PATH_DESC

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        layout.label(text=label.MESS_RESET_PATH)
        layout.separator()

    def execute(self, context):
        addon_prefs = get_prefs().uv_checker_props
        items = addon_prefs.__annotations__.keys()
        for pref in items:
            if pref == "checker_assets_path":
                addon_prefs.property_unset(pref)
        # Update main dict
        addon_prefs.files_dict = dumps(update_files_info(addon_prefs.checker_assets_path))
        addon_prefs["SizesY"] = 0
        addon_prefs["ZenCheckerImages"] = 0
        return {'FINISHED'}


classes = [
    ZUVChecker_OT_CheckerToggle,
    ZUVChecker_OT_Reset,
    ZUVChecker_OT_Remove,
    ZUVChecker_OT_OpenEditor,
    ZUVChecker_OT_ResetPath,
    ZUVChecker_OT_CheckerOn,
    ZUVChecker_OT_CheckerOff
]


def register():
    RegisterUtils.register(classes)


def unregister():
    RegisterUtils.unregister(classes)


if __name__ == '__main__':
    pass
