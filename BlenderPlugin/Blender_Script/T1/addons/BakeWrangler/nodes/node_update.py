import bpy
from .node_tree import _prefs, _print, BW_TREE_VERSION, get_input, follow_input_link


class BakeWrangler_Operator_UpdateRecipe(bpy.types.Operator):
    '''Update older recipe version to current version'''
    bl_idname = "bake_wrangler_op.update_recipe"
    bl_label = "更新配方"
    bl_options = {"REGISTER", "UNDO"}
    
    tree: bpy.props.StringProperty()
    
    @classmethod
    def poll(type, context):
        return context.area.type == "NODE_EDITOR" and context.space_data.tree_type == "BakeWrangler_Tree"
    
    def execute(self, context):
        tree = bpy.data.node_groups[self.tree]
        nodes = tree.nodes
        links = tree.links
        fail = False
        RGB = ['R', 'G', 'B']
        # Helper to get lists of desired nodes
        def get_bw_nodes(nodes, before_version=-1, idnames=[]):
            bw_nodes = []
            for node in nodes:
                if node.bl_idname in ['NodeFrame', 'NodeReroute']:
                    continue
                if before_version > -1 and getattr(node, "tree_version", before_version) >= before_version:
                    continue
                if len(idnames) and node.bl_idname not in idnames:
                    continue
                bw_nodes.append(node)
            return bw_nodes
        def link_route(input, node, socket, links):
            # If the input is linked via reroutes, this will get the tail reroutes input
            if len(input.links):
                input = follow_input_link(input.links[0]).to_socket
            # If the specified node is a reroute, follow to the source, and change the link at that end
            if node.bl_idname == 'NodeReroute':
                tail = follow_input_link(node.inputs[0].links[0])
                tail_node = tail.from_node
                tail_sock = tail.to_socket
                links.new(tail_node.outputs[socket], tail_sock)
                if input == tail_sock: return
                socket = 0
            links.new(input, node.outputs[socket])
        # 5 -> 6
        if getattr(tree, "tree_version", 0) == 5:
            # Load out dated nodes
            from .prev_trees import node_tree_v5 as node_tree_v5
            node_tree_v5.register()
            try:
                glob_bake = []
                glob_outp = []
                # First the active global res node should be found (if exists) and the values stored
                for node in tree.nodes:
                    if node.bl_idname == 'BakeWrangler_Global_Resolution' and node.is_active:
                        glob_bake.append(node.res_bake_x)
                        glob_bake.append(node.res_bake_y)
                        glob_outp.append(node.res_outp_x)
                        glob_outp.append(node.res_outp_y)
                        break
                # Go through all the nodes and update them as needed based on idname
                for node in get_bw_nodes(nodes, 6, ['BakeWrangler_Global_Resolution', 'BakeWrangler_Bake_Mesh', 'BakeWrangler_Bake_Pass', 'BakeWrangler_Output_Image_Path']):
                    if node.bl_idname == 'BakeWrangler_Global_Resolution':
                        nodes.remove(node) # No longer used
                        continue
                    socket_type = None
                    node_type = None
                    if node.bl_idname == 'BakeWrangler_Bake_Mesh':
                        socket_type = 'BakeWrangler_Socket_MeshSetting'
                        node_type = 'BakeWrangler_MeshSettings'
                    elif node.bl_idname == 'BakeWrangler_Bake_Pass':
                        socket_type = 'BakeWrangler_Socket_PassSetting'
                        node_type = 'BakeWrangler_PassSettings'
                    elif node.bl_idname == 'BakeWrangler_Output_Image_Path':
                        socket_type = 'BakeWrangler_Socket_OutputSetting'
                        node_type = 'BakeWrangler_OutputSettings'
                    # Setting input needs to be added and settings placed in the correct settings node
                    if 'Settings' not in node.inputs.keys():
                        sset = node.inputs.new(socket_type, "Settings")
                        node.inputs.move(len(node.inputs)-1, 0)
                        mset = nodes.new(node_type)
                        mset.location = [node.location[0] - 10, node.location[1] + 10]
                        links.new(sset, mset.outputs[0])
                        for key in node.keys():
                            if key == 'pause_update': continue
                            mset[key] = node[key]
                    # Finished with Mesh node
                    if node.bl_idname == 'BakeWrangler_Bake_Mesh':
                        node.tree_version = 6
                    # Extra work for bake pass
                    elif node.bl_idname == 'BakeWrangler_Bake_Pass':
                        xres = getattr(node, 'bake_xres', 0)
                        usex = getattr(node, 'bake_usex', False)
                        if not usex:
                            if len(glob_bake):
                                mset.res_bake_x = glob_bake[0]
                        else:
                            mset.res_bake_x = xres
                        yres = getattr(node, 'bake_yres', 0)
                        usey = getattr(node, 'bake_usey', False)
                        if not usey:
                            if len(glob_bake):
                                mset.res_bake_y = glob_bake[1]
                        else:
                            mset.res_bake_y = yres
                        # A pass was added to 'WRANG' cat at pos 3, so selected pass needs to move down one
                        if node.bake_cat == 'WRANG':
                            # It's an enum and stored as an int, but when addon loads becomes a string..
                            enum = 0
                            enum2str = {}
                            str2enum = {}
                            for wpass in node.passes_wrang:
                                str2enum[wpass[0]] = enum
                                enum2str[enum] = wpass[0]
                                enum += 1
                            if str2enum[node.bake_wrang] >= 3:
                                enum = str2enum[node.bake_wrang] + 1
                                node.bake_wrang = enum2str[enum]
                        # Version will get set when working back from an Output
                    # Extra work for output
                    elif node.bl_idname == 'BakeWrangler_Output_Image_Path':
                        node.inputs.new('BakeWrangler_Socket_ChanMap', "Alpha")
                        xres = getattr(node, 'img_xres', 0)
                        usex = getattr(node, 'img_usex', False)
                        if not usex:
                            if len(glob_bake):
                                mset.img_xres = glob_outp[0]
                        else:
                            mset.img_xres = xres
                        yres = getattr(node, 'img_yres', 0)
                        usey = getattr(node, 'img_usey', False)
                        if not usey:
                            if len(glob_bake):
                                mset.img_yres = glob_outp[1]
                        else:
                            mset.img_yres = yres
                # Loop over all the nodes again, just back tracking from outputs this time
                for node in get_bw_nodes(nodes, 6, ['BakeWrangler_Output_Image_Path']):
                    # Unless the only input is color and alpha, a mapping node needs to be set up
                    map = None
                    for input in node.inputs:
                        if input.name in ['R', 'G', 'B', 'A'] and input.islinked() and input.valid:
                            if map is None and not input.name == 'A':
                                # Create map node and connect the color socket
                                map = nodes.new('BakeWrangler_Channel_Map')
                                map.location = [node.location[0] - 20, node.location[1] - 20]
                                if node.inputs['Color'].islinked() and node.inputs['Color'].valid:
                                    link_route(map.inputs['Color'], node.inputs['Color'].links[0].from_node, 'Color', links)
                            # Connect up this input and set mapping
                            if input.name == 'A':
                                sock = node.inputs['Alpha']
                            else:
                                sock = map.inputs[input.name]
                            chan = follow_input_link(input.links[0]).from_socket.name[:1]
                            link_route(sock, input.links[0].from_node, 'Color', links)
                            _print("输入:" + str(input.name))
                            if chan == 'C':
                                if input.name == 'A':
                                    chan = 'V'
                                else:
                                    chan = input.name
                            sock.input_channel = chan
                            # Remove the old link
                            links.remove(input.links[0])
                    # If map wasn't created then just link the color input, else link the map
                    if map is None:
                        link_route(node.inputs['Color'], node.inputs['Color'].links[0].from_node, 'Color', links)
                    else:
                        link_route(node.inputs['Color'], map, 'Color', links)
                    # Remove the now unused sockets
                    for input in node.inputs:
                        if input.name in ['R', 'G', 'B', 'A']:
                            node.inputs.remove(input)
                    node.tree_version = 6
                # Go through all the pass nodes, only their color outputs should be linked now
                for node in get_bw_nodes(nodes, 6):
                    if node.bl_idname == 'BakeWrangler_Bake_Pass':
                        for output in node.outputs:
                            if output.name != 'Color':
                                node.outputs.remove(output)
                    node.tree_version = 6
                # Helper fn to compare and group settings
                def consolidate_settings(settings):
                    def group_settings(settings, groups={}, idx=0):
                        def compare_settings(this, that):
                            for key in this.keys():
                                if key == 'pause_update': continue
                                if getattr(that, key, None) == getattr(this, key, None): continue
                                return False
                            return True
                        excluded = []
                        if len(settings):
                            comp = settings[0]
                            groups[idx] = [comp]
                            for sett in settings[1:]:
                                if compare_settings(comp, sett):
                                    groups[idx].append(sett)
                                else:
                                    excluded.append(sett)
                            return group_settings(excluded, groups, idx+1)
                        return groups
                    if len(settings) > 1:
                        # Create groups of same
                        grps = group_settings(settings)
                        for key in grps.keys():
                            merge = grps[key][0].outputs[0]
                            mlinks = []
                            # Collect all the link dests
                            for sett in grps[key][1:]:
                                for link in sett.outputs[0].links:
                                    mlinks.append(link.to_socket)
                            # Link all the dests to the first setting node
                            for link in mlinks:
                                links.new(merge, link)
                            # Delete extra nodes
                            for sett in grps[key][1:]:
                                nodes.remove(sett)
                # Consolidate duplicate settings nodes
                consolidate_settings(get_bw_nodes(nodes, -1, ['BakeWrangler_MeshSettings']))
                consolidate_settings(get_bw_nodes(nodes, -1, ['BakeWrangler_PassSettings']))
                consolidate_settings(get_bw_nodes(nodes, -1, ['BakeWrangler_OutputSettings']))
                # Everything should be updated to version 6
                tree.tree_version = 6
            except Exception as err:
                _print("将配方从v5更新到v6失败: %s" % (str(err)))
                self.report({'ERROR'}, "将配方从v5更新到v6失败：%s" % (str(err)))
                fail = True
            else:
                _print("配方从v5更新到v6")
                node_tree_v5.unregister()
                if fail: return {'CANCELLED'}
        # 6 -> 7
        if getattr(tree, "tree_version", 0) == 6:
            try:
                # Output path nodes are changed up a bit
                for node in get_bw_nodes(nodes, 7):
                    if node.bl_idname == 'BakeWrangler_Output_Image_Path':
                        node.inputs.new('BakeWrangler_Socket_SplitOutput', "Split Output")
                        node.inputs.move(len(node.inputs)-1, 0)
                        node.update_inputs()
                    node.tree_version = 7
                tree.tree_version = 7
            except Exception as err:
                _print("将配方从v6更新到v7失败: %s" % (str(err)))
                self.report({'ERROR'}, "将配方从v6更新到v7失败：%s" % (str(err)))
                fail = True
            else:
                _print("配方从v6更新到v7")
            if fail: return {'CANCELLED'}
        # 7 -> 8
        if getattr(tree, "tree_version", 0) == 7:
            try:
                # Output paths moved to socket properties
                for node in get_bw_nodes(nodes, 8):
                    if node.bl_idname == 'BakeWrangler_Output_Image_Path':
                        socket = node.inputs["Split Output"]
                        for key in node.keys():
                            if key == 'disp_path' and node[key]: socket.disp_path = node[key]
                            if key == 'img_path' and node[key]: socket.img_path = node[key]
                            if key == 'img_name' and node[key]: socket.img_name = node[key]
                    node.tree_version = 8
                tree.tree_version = 8
            except Exception as err:
                _print("将配方从v7更新到v8失败: %s" % (str(err)))
                self.report({'ERROR'}, "将配方从v7更新到v8失败：%s" % (str(err)))
                fail = True
            else:
                _print("配方从v7更新到v8")
            if fail: return {'CANCELLED'}
        # 8 -> 9
        if getattr(tree, "tree_version", 0) == 8:
            try:
                # RGB sockets have changed to Red, Green, Blue and PassSettings gains a samples socket
                for node in get_bw_nodes(nodes, 9):
                    if node.bl_idname in ['BakeWrangler_Channel_Map', 'BakeWrangler_Post_SplitRGB', 'BakeWrangler_Post_JoinRGB']:
                        soks = node.inputs
                        if node.bl_idname == 'BakeWrangler_Post_SplitRGB': soks = node.outputs
                        for sok in soks:
                            if sok.name == 'R': sok.name = 'Red'
                            elif sok.name == 'G': sok.name = 'Green'
                            elif sok.name == 'B': sok.name = 'Blue'
                        soks = node.outputs
                        if node.bl_idname == 'BakeWrangler_Post_SplitRGB': soks = node.inputs
                        for sok in soks:
                            if sok.name == 'Image': sok.name = 'Color'
                    elif node.bl_idname == 'BakeWrangler_PassSettings':
                        node.inputs.new('BakeWrangler_Socket_SampleSetting', "Samples")
                    elif node.bl_idname == 'BakeWrangler_OutputSettings':
                        if not hasattr(node, 'img_color_space'):
                            node.img_color_space = bpy.data.scenes[0].sequencer_colorspace_settings.name
                    node.tree_version = 9
                tree.tree_version = 9
            except Exception as err:
                _print("将配方从v8更新到v9失败: %s" % (str(err)))
                self.report({'ERROR'}, "将配方从v8更新到v9失败：%s" % (str(err)))
                fail = True
            else:
                _print("配方从v8更新到v9")
            if fail: return {'CANCELLED'}
        return {'FINISHED'}

    # Ask the user if they really want to update
    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)


# Classes to register
classes = (
    BakeWrangler_Operator_UpdateRecipe,
)


def register():
    from bpy.utils import register_class
    for cls in classes:
        register_class(cls)


def unregister():
    from bpy.utils import unregister_class
    for cls in reversed(classes):
        unregister_class(cls)


if __name__ == "__main__":
    register()