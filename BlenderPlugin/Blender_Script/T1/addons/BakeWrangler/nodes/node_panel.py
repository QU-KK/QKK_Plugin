import bpy
from .node_tree import _prefs, _print, BW_TREE_VERSION, BakeWrangler_Operator


# Panel displaying info about recipe version and containing update button
class BakeWrangler_RecipeInfo(bpy.types.Panel):
    '''Panel in node editor to show recipe information'''
    bl_label = "🧇 烘焙神器 (Bake Wrangler)"
    bl_idname = "OBJECT_PT_BW_RecipeInfo"
    bl_space_type = 'NODE_EDITOR'
    bl_region_type = 'UI'
    bl_context = "area"
    bl_category = "🧇"
    bl_options = {'DEFAULT_CLOSED'}
    
    @classmethod
    def poll(cls, context):
        # Only display if the edited tree is of the correct type
        return (context.area and context.area.ui_type == 'BakeWrangler_Tree')
    def draw_header_preset(self,context):self.layout.row().operator("wm.url_open",icon="SEQUENCE_COLOR_03").url = "https://www.bilibili.com/video/BV1ED421p7tL/"
    def draw(self, context):
        layout=self.layout;row=layout.row();row.operator("wm.url_open", text="插件视频",icon="FILE_MOVIE").url = "https://www.bilibili.com/video/BV1ED421p7tL/";row.operator("wm.url_open", text="更多插件",icon="COLORSET_09_VEC").url = "https://space.bilibili.com/454791153/video"
        if bpy.app.version < (3,4,0) :row=layout.row();row.alert=True;row.operator("wm.url_open",text="只支持blender3.4-4.2",icon="KEYTYPE_KEYFRAME_VEC").url = "https://www.bilibili.com/video/BV1Qv411F7ia/"

        tree = context.space_data.node_tree
        layout = self.layout
        if tree is None:
            layout.label(text="未加载配方")
            return
        tree_ver = getattr(tree, "tree_version", 0)
        curr_ver = BW_TREE_VERSION
        nodes = len(tree.nodes)
        
        col = layout.column()
        op = col.operator("bake_wrangler.show_log", icon='TEXT')
        op.tree = tree.name
        col.label(text="配方版本：" + str(tree_ver))
        col.label(text="插件版本：" + str(curr_ver))
        col.label(text="节点：" + str(nodes))
        
        if tree_ver != curr_ver:
            row = col.row()
            if tree_ver > curr_ver:
                row.label(text="状态：插件需要更新")
            else:
                row.label(text="状态：配方需要更新")
                op_row = col.row()
                if tree_ver >= 5:
                    op = op_row.operator("bake_wrangler_op.update_recipe", icon='FILE_REFRESH', text="更新配方")
                    op.tree = tree.name
                else:
                    op_row.operator("bake_wrangler_op.update_recipe", icon='CANCEL', text="更新不可用")
                    op_row.enabled = False
                    
                    
# Panel for automatic cage management tasks
class BakeWrangler_AutoCages(bpy.types.Panel):
    '''Panel in node editor to manage automatic cages'''
    bl_label = "自动外壳"
    bl_idname = "OBJECT_PT_BW_AutoCages"
    bl_space_type = 'NODE_EDITOR'
    bl_region_type = 'UI'
    bl_context = "area"
    bl_category = "🧇"
    bl_parent_id ='OBJECT_PT_BW_RecipeInfo'
    bl_options = {'HIDE_HEADER'}
    @classmethod
    def poll(cls, context):
        # Only display if the edited tree is of the correct type
        return (context.area and context.area.ui_type == 'BakeWrangler_Tree')

    def draw(self, context):
        tree = context.space_data.node_tree
        layout = self.layout
        if tree is None:
            layout.label(text="未加载配方")
            return
        col = layout.column()
        op = col.operator("bake_wrangler.auto_cage_create")
        op.tree = tree.name
        op = col.operator("bake_wrangler.auto_cage_update")
        op.tree = tree.name
        op = col.operator("bake_wrangler.auto_cage_remove")
        op.tree = tree.name


# Show log file
class BakeWrangler_Operator_ShowLog(BakeWrangler_Operator, bpy.types.Operator):
    '''Show last log created by this recipe'''
    bl_idname = "bake_wrangler.show_log"
    bl_label = "显示日志"
    bl_options = {"REGISTER"}

    # Called either after invoke from UI or directly from script
    def execute(self, context):
        return {'FINISHED'}
        
    # Called from button press, set modifier key states
    def invoke(self, context, event):
        tree = bpy.data.node_groups[self.tree]
        if tree.last_log:
            bpy.ops.screen.area_dupli('INVOKE_DEFAULT')
            open_ed = bpy.context.window_manager.windows[len(bpy.context.window_manager.windows) - 1].screen.areas[0]
            open_ed.type = 'TEXT_EDITOR'
            log = bpy.data.texts.load(tree.last_log)
            open_ed.spaces[0].text = log
            open_ed.spaces[0].show_line_numbers = False
            open_ed.spaces[0].show_syntax_highlight = False
            return {'FINISHED'}
        else:
            self.report({'WARNING'}, "没有设置日志文件")
            return {'CANCELLED'}


# Generate auto cages
class BakeWrangler_Operator_AutoCageCreate(BakeWrangler_Operator, bpy.types.Operator):
    '''Create cages in current scene for objects in recipe that don't have a cage set.\nShift-Click to exclude hidden objects'''
    bl_idname = "bake_wrangler.auto_cage_create"
    bl_label = "生成外壳"
    bl_options = {"REGISTER", "UNDO"}

    # Called either after invoke from UI or directly from script
    def execute(self, context):
        return {'FINISHED'}

    # Called from button press, set modifier key states
    def invoke(self, context, event):
        mod_shift = event.shift
        objs = get_auto_caged(bpy.data.node_groups[self.tree], mod_shift, context)
        if len(objs):
            # Check if cage collection exists and create it if needed
            if 'BW Cages' not in bpy.data.collections.keys():
                bpy.data.collections.new('BW Cages')
            # Check if cage collection is in current scene and link if needed
            if 'BW Cages' not in context.scene.collection.children.keys():
                context.scene.collection.children.link(bpy.data.collections['BW Cages'])
            bw_cages = bpy.data.collections['BW Cages'].objects
            # Create and link cages to the collection for all objects
            for obj in objs:
                if not obj[0].bw_auto_cage:
                    generate_auto_cage(obj[0], obj[1], obj[2], context)
                if obj[0].bw_auto_cage not in bw_cages.values():
                    bw_cages.link(obj[0].bw_auto_cage)
            return {'FINISHED'}
        else:
            self.report({'WARNING'}, "找不到具有自动保持架的对象")
            return {'CANCELLED'}


# Update auto cages
class BakeWrangler_Operator_AutoCageUpdate(BakeWrangler_Operator, bpy.types.Operator):
    '''Update cages in current scene for objects in recipe. Overwrites user changes if 'bw_cage' modifier has been removed.\nShift-Click to exclude hidden objects'''
    bl_idname = "bake_wrangler.auto_cage_update"
    bl_label = "更新外壳"
    bl_options = {"REGISTER", "UNDO"}

    # Called either after invoke from UI or directly from script
    def execute(self, context):
        return {'FINISHED'}

    # Called from button press, set modifier key states
    def invoke(self, context, event):
        mod_shift = event.shift
        objs = get_auto_caged(bpy.data.node_groups[self.tree], mod_shift, context)
        if len(objs):
            for obj in objs:
                if obj[0].bw_auto_cage:
                    cage = obj[0].bw_auto_cage
                    # If the modifier is still on the object just change it instead of making a new object
                    if "bw_cage" in cage.modifiers:
                        cage.modifiers["bw_cage"].strength = obj[1]
                        cage.data.auto_smooth_angle = obj[2]
                    elif 'BW Cages' in bpy.data.collections.keys():
                        bpy.data.collections['BW Cages'].objects.unlink(cage)
                        generate_auto_cage(obj[0], obj[1], obj[2], context)
            return {'FINISHED'}
        else:
            self.report({'WARNING'}, "找不到具有自动保持架的对象")
            return {'CANCELLED'}


# Remove auto cages
class BakeWrangler_Operator_AutoCageRemove(BakeWrangler_Operator, bpy.types.Operator):
    '''Remove cages in current scene for objects in recipe.\nShift-Click to exclude hidden objects'''
    bl_idname = "bake_wrangler.auto_cage_remove"
    bl_label = "移除外壳"
    bl_options = {"REGISTER", "UNDO"}

    # Called either after invoke from UI or directly from script
    def execute(self, context):
        return {'FINISHED'}

    # Called from button press, set modifier key states
    def invoke(self, context, event):
        mod_shift = event.shift
        if 'BW Cages' in bpy.data.collections.keys():
            bw_cages = bpy.data.collections['BW Cages'].objects
            objs = context.scene.collection.all_objects
            for obj in objs:
                if obj.bw_auto_cage and (not mod_shift or obj.visible_get()):
                    bw_cages.unlink(obj.bw_auto_cage)
                    obj.bw_auto_cage = None
            if 'BW Cages' in context.scene.collection.children:
                context.scene.collection.children.unlink(bw_cages.id_data)
            return {'FINISHED'}
        else:
            self.report({'WARNING'}, "找不到具有自动保持架的对象")
            return {'CANCELLED'}
        

# Return a list of objects that would get a cage auto generated
def get_auto_caged(tree, vis, context):
    nodes = tree.nodes
    objs = []
    for node in nodes:
        if node.bl_idname == 'BakeWrangler_Output_Image_Path':
            objs += node.get_unique_objects('TARGET', for_auto_cage=True)
    # Get a list of all objects in the scene and cull it down to only visible ones
    vl_objs = context.scene.collection.all_objects.values()
    if vis:
        vl_vis = []
        for obj in vl_objs:
            if obj.visible_get() and obj not in vl_vis:
                vl_vis.append(obj)
        vl_objs = vl_vis
    # Return a list of unique objects that are in the scene and visible and would have a cage
    objs_prune = []
    for obj in objs:
        if obj not in objs_prune and obj[0] in vl_objs:
            objs_prune.append(obj)
    return objs_prune


# Create an auto cage for the given mesh
def generate_auto_cage(mesh, cage_exp, smooth, context):
    # Create a copy of the base mesh with modifiers applied to use a the base cage
    cage = mesh.copy()
    cage.data = mesh.data.copy()
    cage.name = mesh.name + '.cage'
    cage.name = mesh.name + '.cage'
    cage.data.materials.clear()
    cage.data.polygons.foreach_set('material_index', [0] * len(cage.data.polygons))
    cage.display_type = 'WIRE'
    if cage not in bpy.data.collections['BW Cages'].objects.values():
        bpy.data.collections['BW Cages'].objects.link(cage)
    if len(cage.modifiers):
        prev_active = bpy.context.view_layer.objects.active
        bpy.context.view_layer.objects.active = cage
        for mod in cage.modifiers:
            if mod.show_render:
                try:
                    bpy.ops.object.modifier_apply(modifier=mod.name)
                except:
                    _print("Error applying modifier '%s' to object '%s'" % (mod.name, mesh.name))
                    bpy.ops.object.modifier_remove(modifier=mod.name)
            else:
                bpy.ops.object.modifier_remove(modifier=mod.name)
        bpy.context.view_layer.objects.active = prev_active
    # Expand cage on normals
    cage_disp = cage.modifiers.new("bw_cage", 'DISPLACE')
    cage_disp.strength = cage_exp
    cage_disp.direction = 'NORMAL'
    cage_disp.mid_level = 0.0
    cage_disp.show_in_editmode = True
    cage_disp.show_on_cage = True
    cage_disp.show_expanded = False
    # Smooth normals and clear sharps
    cage.data.use_auto_smooth = True
    cage.data.auto_smooth_angle = smooth
    for poly in cage.data.polygons:
        poly.use_smooth = True
    for edge in cage.data.edges:
        edge.use_edge_sharp = False
    # Link cage via property on mesh
    mesh.bw_auto_cage = cage


# Classes to register
classes = (
    BakeWrangler_RecipeInfo,
    BakeWrangler_AutoCages,
    BakeWrangler_Operator_ShowLog,
    BakeWrangler_Operator_AutoCageCreate,
    BakeWrangler_Operator_AutoCageUpdate,
    BakeWrangler_Operator_AutoCageRemove,
)


def register():
    # Add pointer to generated cage
    bpy.types.Object.bw_auto_cage = bpy.props.PointerProperty(name="外壳", description="烘焙牧马人自动生成的外壳", type=bpy.types.Object)
    from bpy.utils import register_class
    for cls in classes:
        register_class(cls)


def unregister():
    from bpy.utils import unregister_class
    for cls in reversed(classes):
        unregister_class(cls)


if __name__ == "__main__":
    register()