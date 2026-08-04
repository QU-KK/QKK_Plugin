import bpy
from .node_tree import _prefs, _print, BW_TREE_VERSION


# Msgbus will call this when the loaded node tree changes. Checks on tree version etc can be done
def BakeWrangler_Msgbus_NodeTreeChange(*args):
    debug = _prefs('debug')
    if debug: _print("Node Tree Changed")
    wm = bpy.context.window_manager
    ar = bpy.context.area
    if debug: _print("Context Area: %s" % (ar))
    # First find all the open node editors that belong to BW
    spaces = []
    for window in wm.windows:
        for area in window.screen.areas:
            if area.ui_type == 'BakeWrangler_Tree':
                if len(area.spaces) > 0:
                    for spc in area.spaces:
                        if spc.type == 'NODE_EDITOR' and hasattr(spc, 'node_tree'):
                            if debug: _print("Node editor found: %s" % (spc))
                            spaces.append(spc)
                            break
    for space in spaces:
        tree = space.node_tree
        # Init a new tree
        if tree and not tree.initialised:
            if debug: _print("New/Uninitialized node tree active")
            tree.use_fake_user = True
            # Give tree a nice name
            '''if tree.name.startswith("NodeTree"):
                num = 0
                for nodes in bpy.data.node_groups:
                    if nodes.name.startswith("Bake Recipe"):
                        if num == 0:
                            num = 1
                        splt = nodes.name.split('.')
                        if len(splt) > 1 and splt[1].isnumeric:
                            num = int(splt[1]) + 1
                if num == 0:
                    name = "Bake Recipe"
                else:
                    name = "Bake Recipe.%03d" % (num)
                tree.name = tree.name.replace("NodeTree", name, 1)'''
            # Add initial basic node set up
            if len(tree.nodes) == 0:
                bake_mesh = tree.nodes.new('BakeWrangler_Bake_Mesh')
                bake_pass = tree.nodes.new('BakeWrangler_Bake_Pass')
                output_img = tree.nodes.new('BakeWrangler_Output_Image_Path')
                global_set = tree.nodes.new('BakeWrangler_Settings')
                global_set.pinned = True
                
                bake_mesh.location[0] -= 300
                output_img.location[0] += 200
                global_set.location[0] -= 300
                global_set.location[1] += 210
                
                tree.links.new(bake_pass.inputs[1], bake_mesh.outputs[0])
                tree.links.new(output_img.inputs[2], bake_pass.outputs[0])
                output_img.inputs[2].valid = True
                
                tree.tree_version = BW_TREE_VERSION
            tree.initialised = True
            if debug: _print("Tree initialized")


# Reregister message bus subscription
bw_subscriber = object()
from bpy.app.handlers import persistent
@persistent
def BakeWrangler_Hook_Post_Load(dummy):
    BakeWrangler_Msgbus_Subscribe(bw_subscriber)
    

# Subscribe to message bus
def BakeWrangler_Msgbus_Subscribe(owner, sub=True):
    if owner is not None:
        bpy.msgbus.clear_by_owner(owner)
    if sub:
        subscribe_to = bpy.types.SpaceNodeEditor, "node_tree"
        bpy.msgbus.subscribe_rna(key=subscribe_to,
                                 owner=owner,
                                 args=(1,2),
                                 notify=BakeWrangler_Msgbus_NodeTreeChange)


def register():
    BakeWrangler_Msgbus_Subscribe(bw_subscriber)
    bpy.app.handlers.load_post.append(BakeWrangler_Hook_Post_Load)


def unregister():
    hook_index = None
    for idx in range(len(bpy.app.handlers.load_post)):
        if bpy.app.handlers.load_post[idx] == BakeWrangler_Hook_Post_Load:
            hook_index = idx
    if hook_index != None:
        bpy.app.handlers.load_post.pop(hook_index)
    BakeWrangler_Msgbus_Subscribe(bw_subscriber, False)


if __name__ == "__main__":
    register()
