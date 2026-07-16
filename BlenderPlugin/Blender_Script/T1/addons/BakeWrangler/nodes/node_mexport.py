from bl_operators.presets import AddPresetBase
from bl_ui.utils import PresetPanel
from bpy.types import Panel, Menu, Operator
import bpy


# Helper functions and data for exporting meshes


# Classes to manage FBX preset panel/menu
class BW_PT_PresetsFBX(PresetPanel, Panel):
    bl_label = 'FBX预设' 
    preset_subdir = 'bake_wrangler\export.fbx'
    preset_operator = 'script.execute_preset'
    preset_add_operator = 'bake_wrangler.add_preset_fbx'
    
class BW_MT_PresetsFBX(Menu): 
    bl_label = 'FBX预设'
    preset_subdir = 'bake_wrangler\export.fbx'
    preset_operator = 'script.execute_preset'
    draw = Menu.draw_preset
    
class BW_OT_AddPresetFBX(AddPresetBase, Operator):
    '''Add new FBX preset'''
    bl_idname = 'bake_wrangler.add_preset_fbx'
    bl_label = '添加FBX预设'
    preset_menu = 'BW_MT_PresetsFBX'

    # Common variable used for all preset values
    preset_defines = [
                        'node = bpy.context.active_node.FBX',
                     ]

    # Properties to store in the preset
    preset_values = [] 
    for key in bpy.ops.export_scene.fbx.get_rna_type().properties.keys()[2:]:
        preset_values.append("node." + key)

    # Directory to store the presets
    preset_subdir = 'bake_wrangler\export.fbx'    


#Helper functions and data
export_supported = {
    'FBX': [BW_PT_PresetsFBX, 'export_scene.fbx', None],
    }
exporters = {}


def get_exporters():
    presets_enum = []
    for key, val in exporters.items():
        if key == 'FBX':
            presets_enum.append(('FBX', "FBX", "导出为FBX"))
    return tuple(presets_enum)


def draw_presets(preset, layout):
    exporters[preset][0].draw_menu(layout)


def draw_properties(node, preset, layout):
    props = getattr(node, preset)
    #for prop in props.rna_type.properties.keys():
    #    if prop not in ["rna_type", "name"]:
    #        layout.prop(props, prop)
    # Go the road to hell and have custom layouts for each format mostly stolen from their panels
    # instead of just displaying all the properties and letting god sort them out
    if preset == 'FBX':
        # Main section
        layout.use_property_decorate = False
        row = layout.row(align=True)
        row.prop(props, "path_mode")
        sub = row.row(align=True)
        sub.enabled = (props.path_mode == 'COPY')
        sub.prop(props, "embed_textures", text="", icon='PACKAGE' if props.embed_textures else 'UGLYPACKAGE')
        box = layout.box()
        if not node.show_pt_1:
            box.prop(node, "show_pt_1", icon="DISCLOSURE_TRI_RIGHT", emboss=False, text="包括")
        else:
            box.prop(node, "show_pt_1", icon="DISCLOSURE_TRI_DOWN", emboss=False, text="包括")
            box.use_property_split = True
            box.column().prop(props, "object_types")
            box.prop(props, "use_custom_props")
        box = layout.box()
        if not node.show_pt_2:
            box.prop(node, "show_pt_2", icon="DISCLOSURE_TRI_RIGHT", emboss=False, text="转换")
        else:
            box.prop(node, "show_pt_2", icon="DISCLOSURE_TRI_DOWN", emboss=False, text="转换")
            box.use_property_split = True
            box.prop(props, "global_scale")
            box.prop(props, "apply_scale_options")

            box.prop(props, "axis_forward")
            box.prop(props, "axis_up")

            box.prop(props, "apply_unit_scale")
            box.prop(props, "use_space_transform")
            row = box.row()
            row.prop(props, "bake_space_transform")
            row.label(text="", icon='ERROR')
        box = layout.box()
        if not node.show_pt_3:
            box.prop(node, "show_pt_3", icon="DISCLOSURE_TRI_RIGHT", emboss=False, text="几何")
        else:
            box.prop(node, "show_pt_3", icon="DISCLOSURE_TRI_DOWN", emboss=False, text="几何")
            box.use_property_split = True
            box.prop(props, "mesh_smooth_type")
            box.prop(props, "use_subsurf")
            box.prop(props, "use_mesh_modifiers")
            box.prop(props, "use_mesh_edges")
            sub = box.row()
            sub.prop(props, "use_tspace")
        box = layout.box()
        if not node.show_pt_4:
            box.prop(node, "show_pt_4", icon="DISCLOSURE_TRI_RIGHT", emboss=False, text="骨架")
        else:
            box.prop(node, "show_pt_4", icon="DISCLOSURE_TRI_DOWN", emboss=False, text="骨架")
            box.use_property_split = True
            box.prop(props, "primary_bone_axis")
            box.prop(props, "secondary_bone_axis")
            box.prop(props, "armature_nodetype")
            box.prop(props, "use_armature_deform_only")
            box.prop(props, "add_leaf_bones")
        box = layout.box()
        hed = box.row()
        if not node.show_pt_5:
            hed.prop(node, "show_pt_5", icon="DISCLOSURE_TRI_RIGHT", emboss=False, text="")
            hed.prop(props, "bake_anim", text="")
            hed.prop(node, "show_pt_5", icon="NONE", emboss=False, text="烘焙动画")
        else:
            hed.prop(node, "show_pt_5", icon="DISCLOSURE_TRI_DOWN", emboss=False, text="")
            hed.prop(props, "bake_anim", text="")
            hed.prop(node, "show_pt_5", icon="NONE", emboss=False, text="烘焙动画")
            box.use_property_split = True
            col = box.column()
            col.enabled = props.bake_anim
            col.prop(props, "bake_anim_use_all_bones")
            col.prop(props, "bake_anim_use_nla_strips")
            col.prop(props, "bake_anim_use_all_actions")
            col.prop(props, "bake_anim_force_startend_keying")
            col.prop(props, "bake_anim_step")
            col.prop(props, "bake_anim_simplify_factor")


# Creates a property group from an operators properties
def prop_grp_from_op(opName, grpName):
    oppath, opnm = opName.split(".")
    op = getattr(bpy.ops, oppath, None)
    if op is None:
        return op
    op = getattr(op, opnm, None)
    if op is None:
        return op
    props = op.get_rna_type()
    props = props.properties
    grp_props = {'__annotations__' : {}}
    for prop in props:
        if prop.identifier in ["rna_type", "filepath"]:
            continue
        if prop.type == 'BOOLEAN':
            grp_props['__annotations__'][prop.identifier] = bpy.props.BoolProperty(
                    name=prop.name,
                    description=prop.description,
                    default=prop.default,
                    subtype=prop.subtype)
        elif prop.type == 'ENUM':
            eitems = []
            eopts = set()
            ende =prop.default
            if prop.is_enum_flag:
                eopts = set({'ENUM_FLAG'})
                ende = prop.default_flag
            for key in prop.enum_items.keys():
                eitems.append((key, prop.enum_items[key].name, prop.enum_items[key].description))
            grp_props['__annotations__'][prop.identifier] = bpy.props.EnumProperty(
                    items=tuple(eitems),
                    name=prop.name,
                    description=prop.description,
                    options=eopts,
                    default=ende)
        elif prop.type == 'STRING':
            grp_props['__annotations__'][prop.identifier] = bpy.props.StringProperty(
                    name=prop.name,
                    description=prop.description,
                    default=prop.default,
                    maxlen=prop.length_max,
                    subtype=prop.subtype)
        elif prop.type == 'POINTER':
            grp_props['__annotations__'][prop.identifier] = bpy.props.PointerProperty(
                    type=getattr(bpy.types, prop.fixed_type.name),
                    name=prop.name,
                    description=prop.description)
        elif prop.type == 'FLOAT':
            grp_props['__annotations__'][prop.identifier] = bpy.props.FloatProperty(
                    name=prop.name,
                    description=prop.description,
                    default=prop.default,
                    min=prop.hard_min,
                    max=prop.hard_max,
                    soft_min=prop.soft_min,
                    soft_max=prop.soft_max,
                    step=prop.step,
                    precision=prop.precision,
                    subtype=prop.subtype,
                    unit=prop.unit)
        else:
            print("Unknown type: %s on %s" % (prop.type, prop.identifier))
    # Create and return prop group class from the props
    return type(grpName, tuple([bpy.types.PropertyGroup]), grp_props)
    

# Node to export baked models in some format
class BakeWrangler_Output_Export_Mesh(Node, BakeWrangler_Tree_Node):
    '''Node to export baked models to the selected format'''
    bl_label = '输出导出网格'
    
    # Makes sure there is always one empty input socket at the bottom by adding and removing sockets
    def update_inputs(self):
        BakeWrangler_Tree_Node.update_inputs(self, 'BakeWrangler_Socket_Mesh', "Mesh")
    
    # Check node settings are valid to bake. Returns true/false, plus error message(s).
    def validate(self, is_primary=False):
        valid = [True]
        # Validate inputs
        has_valid_input = False
        for input in self.inputs:
            if not is_primary:
                has_valid_input = True
                break
            else:
                input_valid = get_input(input).validate()
                valid[0] = input_valid.pop(0)
                if valid[0]:
                    has_valid_input = True
                valid += input_valid
        errs = len(valid)
        if not has_valid_input and errs < 2:
            valid[0] = False
            valid.append([_print("输入错误", node=self, ret=True), ": No valid inputs connected"])
        # Validate file path
        self.get_full_path(bpy.context)
        if not os.path.isdir(os.path.abspath(self.out_path)):
            # Try creating the path if enabled in prefs
            if _prefs("make_dirs") and not os.path.exists(os.path.abspath(self.out_path)):
                try:
                    os.makedirs(os.path.abspath(self.out_path))
                except OSError as err:
                    valid[0] = False
                    valid.append([_print("路径错误", node=self, ret=True), ": Trying to create path at '%s'" % (err.strerror)])
                    return valid
            else:
                valid[0] = False
                valid.append([_print("路径错误", node=self, ret=True), ": Invalid path '%s'" % (os.path.abspath(self.out_path))])
                return valid
        # Check if there is read/write access to the file/directory
        file_path = os.path.join(os.path.abspath(self.out_path), self.name_with_ext())
        if os.path.exists(file_path):
            if os.path.isfile(file_path):
                # It exists so try to open it r/w
                try:
                    file = open(file_path, "a")
                except OSError as err:
                    valid[0] = False
                    valid.append([_print("文件错误", node=self, ret=True), ": Trying to open file at '%s'" % (err.strerror)])
            else:
                # It exists but isn't a file
                valid[0] = False
                valid.append([_print("文件错误", node=self, ret=True), ": File exists but isn't a regular file '%s'" % (file_path)])
        else:
            # See if it can be created
            try:
                file = open(file_path, "a")
            except OSError as err:
                valid[0] = False
                valid.append([_print("文件错误", node=self, ret=True), ": %s trying to create file at '%s'" % (err.strerror, file_path)])
            else:
                file.close()
                os.remove(file_path)
        # Validated
        return valid
        
    # Get full path, removing any relative references
    def get_full_path(self, context):
        cwd = os.path.dirname(bpy.data.filepath)
        self.out_path = os.path.normpath(os.path.join(cwd, bpy.path.abspath(self.disp_path)))

    # Deal with any path components that may be in the filename
    def update_filename(self, context):
        fullpath = os.path.normpath(bpy.path.abspath(self.out_name))
        path, name = os.path.split(fullpath)
        if path:
            self.disp_path = self.out_name[:-len(name)]
        if name and self.out_name != name:
            self.out_name = name

    # Return the file name with the correct extension and suffix
    def name_with_ext(self, suffix=""):
        return self.out_name + suffix + self.exporter.lower()
                        
    def get_exporters(self, context):
        return node_mexport.get_exporters()
    
    # Core settings
    disp_path: bpy.props.StringProperty(name="输出路径", description="保存栅格的路径", default="", subtype='DIR_PATH', update=get_full_path)
    out_path: bpy.props.StringProperty(name="输出路径", description="保存栅格的路径", default="", subtype='DIR_PATH')
    out_name: bpy.props.StringProperty(name="输出文件", description="将栅格另存为的文件前缀", default="Mesh", subtype='FILE_PATH', update=update_filename)
    exporter: bpy.props.EnumProperty(name="总体安排", description="导出文件格式", items=get_exporters)
    
    show_pt_1: bpy.props.BoolProperty(default=True)
    show_pt_2: bpy.props.BoolProperty(default=False)
    show_pt_3: bpy.props.BoolProperty(default=False)
    show_pt_4: bpy.props.BoolProperty(default=False)
    show_pt_5: bpy.props.BoolProperty(default=False)
            
    def init(self, context):
        super().init(context)
        # Sockets IN
        self.inputs.new('BakeWrangler_Socket_Mesh', "Mesh")
        # Sockets OUT
        self.outputs.new('BakeWrangler_Socket_Bake', "Bake")
        # Prefs
        self.disp_path = _prefs("def_meshpath")
        self.out_name = _prefs("def_meshname")
    
    def draw_buttons(self, context, layout):
        colnode = layout.column(align=False)
        colpath = colnode.column(align=True)
        colpath.prop(self, "disp_path", text="")
        colpath.prop(self, "out_name", text="")
        colpath.prop(self, "exporter")
    
    def draw_buttons_ext(self, context, layout):
        node_mexport.draw_presets(self.exporter, layout.row())
        col = layout.column()
        node_mexport.draw_properties(self, self.exporter, col)


# Classes to register
classes = (
    BW_PT_PresetsFBX,
    BW_MT_PresetsFBX,
    BW_OT_AddPresetFBX,
)


def register():
    from bpy.utils import register_class
    for cls in classes:
        register_class(cls)
    for exp in export_supported.keys():
        if getattr(bpy.ops, exp[1], None) is not None:
            prop_grp = prop_grp_from_op(export_supported[exp][1], "BW_PropGrp" + exp)
            exporters[exp] = [export_supported[exp][0], export_supported[exp][1], prop_grp]
            register_class(prop_grp)
            from .node_tree import BakeWrangler_Output_Export_Mesh
            setattr(BakeWrangler_Output_Export_Mesh, exp, bpy.props.PointerProperty(type=prop_grp))


def unregister():
    from bpy.utils import unregister_class
    for cls in reversed(classes):
        unregister_class(cls)
    for exp in exporters.keys():
        unregister_class(exporters[exp][2])
    exporters = {}


if __name__ == "__main__":
    register()
