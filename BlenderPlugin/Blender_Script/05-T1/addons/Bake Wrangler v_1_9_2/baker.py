# Information needed to create a desired output. A solution has a destination file
# name and output format along with a list of the bake passes that are needed and
# how they are combined into the final image
class bake_solution():
    def __init__(self, socket, alpha, vcol):
        self.bakepass = {}  # Dict of Pass Nodes to process
        self.baketile = {}  # Dict keyed by Pass Nodes with a dict of UDIM tiles when enabled
        self.bakecols = {}  # Dict keyed by Object with Pass node and name of color data
        self.postproc = None# Material containing post processing information
        self.dopost = False # Enabled if post process nodes are set up
        self.sock = socket  # Socket of the output node for which this is the solution
        self.alpha = alpha  # Socket with alpha channel input
        self.vcol = vcol    # Is a vertex color output
        self.format = socket.node.get_settings() # Dict of format settings
        self.split = socket.node.get_split_objects() # List of objects to split output for
        self.get_passes(socket, False, vcol)
        if not vcol and alpha.enabled:
            self.get_passes(alpha, True, vcol)

    # Clear all results from solution
    def clear_results(self):
        for key in self.bakepass.keys():
            node = self.bakepass[key]
            node.bake_result = None
            node.mask_result = None
            node.sbake_result = None
            node.smask_result = None
            node.vcol_result = None
        for key in self.baketile.keys():
            self.baketile[key] = {}
            
    # Moves backwards down the tree from a given input socket and will be called
    # recursively until all paths have ended in a bake pass
    def get_passes(self, socket, is_alpha, is_vcol):
        node = get_input(socket)
        if not node: return

        # Add the process, even if it's a pass (add func will sort it out)
        self.add_postproc(node, socket, is_alpha, is_vcol)

        if node.bl_idname == 'BakeWrangler_Bake_Pass':
            # Add to pass list
            self.bakepass[node.name] = node
            self.baketile[node.name] = {}
            # Initialize results
            node.bake_result = None
            node.mask_result = None
            node.sbake_result = None
            node.smask_result = None
            node.vcol_result = None
        else:
            # It's not a pass node, so it must be a post process, recurse
            self.dopost = True
            for sock in node.inputs:
                self.get_passes(sock, is_alpha, is_vcol)

    # Adds the configuration from a post processing node into the post proc material
    def add_postproc(self, post, from_sock, is_alpha, is_vcol):
        #if self.postproc == None and (post.bl_idname == 'BakeWrangler_Bake_Pass' and not post.use_mask):
        #    return
        if self.postproc == None:
            if is_vcol:
                self.postproc = post_proc_col.copy()
                self.postproc.name = "BW_Post_Col" + self.sock.node.name + self.sock.suffix
            else:
                self.postproc = post_proc_mat.copy()
                self.postproc.name = "BW_Post_" + self.sock.node.name + self.sock.suffix

        nodes = self.postproc.node_tree.nodes
        links = self.postproc.node_tree.links
        # Reached bake pass node
        if post.bl_idname == 'BakeWrangler_Bake_Pass':
            if is_vcol:
                # Add vertex color attribute node
                if post.name not in nodes.keys():
                    vcols = nodes.new('ShaderNodeVertexColor')
                    vcols.name = post.name
                    # Originating node name stored in the label string so it can be looked up later
                    vcols.label = post.name
                else:
                    # It's already been set up, but may need another link added
                    vcols = nodes[post.name]
                    self.link_postproc(from_sock, vcols.outputs['Color'])
                    return
                self.link_postproc(from_sock, vcols.outputs['Color'])
            else:
                # Add a masked bake node set up
                if post.name not in nodes.keys():
                    masked_bake = nodes.new('ShaderNodeGroup')
                    masked_bake.node_tree = post_masked_bake
                    masked_bake.name = post.name
                    # Originating node name stored in the label string so it can be looked up later
                    masked_bake.label = post.name
                    # Invert output for smoothness passes
                    if post.bake_picked in ['SMOOTHNESS']:
                        masked_bake.inputs['Invert'].default_value = 1.0
                    else:
                        masked_bake.inputs['Invert'].default_value = 0.0
                else:
                    # It's already been set up, but may need another link added
                    masked_bake = nodes[post.name]
                    self.link_postproc(from_sock, masked_bake.outputs['Bake'])
                    return
                # Add and link image inputs
                bake = nodes.new('ShaderNodeTexImage')
                links.new(bake.outputs['Color'], masked_bake.inputs['Bake'])
                mask = nodes.new('ShaderNodeTexImage')
                links.new(mask.outputs['Color'], masked_bake.inputs['Mask'])
                self.link_postproc(from_sock, masked_bake.outputs['Bake'])
        # Channel mapping node
        elif post.bl_idname == 'BakeWrangler_Channel_Map':
            # Add channel map node
            if post.name not in nodes.keys():
                chan_map = nodes.new('ShaderNodeGroup')
                chan_map.node_tree = post_chan_map.copy()
                chan_map.name = post.name
            else:
                # It's already set up but may need another link added
                chan_map = nodes[post.name]
                self.link_postproc(from_sock, chan_map.outputs['Color'])
                return
            # Configure node internals (initial configuration has Color input set up)
            chan_nodes = chan_map.node_tree.nodes
            chan_links = chan_map.node_tree.links
            for chan in post.inputs.keys():
                if chan in ['Red', 'Green', 'Blue']:
                    if get_input(post.inputs[chan]):
                        # Connect up correct input
                        in_chan = post.inputs[chan].input_channel
                        if in_chan in ['Red', 'Green', 'Blue']:
                            chan_links.new(chan_nodes['Input'].outputs[chan], chan_nodes[chan + '_From'].inputs[0])
                            chan_links.new(chan_nodes[chan + '_From'].outputs[in_chan], chan_nodes['RGB_Map'].inputs[chan])
                        else:
                            chan_links.new(chan_nodes['Input'].outputs[chan], chan_nodes[chan + '_From_V'].inputs[0])
                            chan_links.new(chan_nodes[chan + '_From_V'].outputs[0], chan_nodes['RGB_Map'].inputs[chan])
            # Link to prev
            self.link_postproc(from_sock, chan_map.outputs['Color'])
        # Mix RGB
        elif post.bl_idname == 'BakeWrangler_Post_MixRGB':
            # Add mix node
            if post.name not in nodes.keys():
                mix_rgb = nodes.new('ShaderNodeMixRGB')
                mix_rgb.name = post.name
                mix_rgb.blend_type = post.op
                mix_rgb.inputs['Fac'].default_value = post.inputs['Fac'].value_fac
                mix_rgb.inputs['Color1'].default_value = post.inputs['Color1'].value_rgb
                mix_rgb.inputs['Color2'].default_value = post.inputs['Color2'].value_rgb
            # Link input
            mix_rgb = nodes[post.name]
            self.link_postproc(from_sock, mix_rgb.outputs['Color'])
        # Split RGB
        elif post.bl_idname == 'BakeWrangler_Post_SplitRGB':
            # Add split node
            if post.name not in nodes.keys():
                split_rgb = nodes.new('ShaderNodeSeparateColor')
                split_rgb.name = post.name
            # Link input
            split_rgb = nodes[post.name]
            self.link_postproc(from_sock, split_rgb.outputs[from_sock.links[0].from_socket.name])
        elif post.bl_idname == 'BakeWrangler_Post_JoinRGB':
            # Add join node
            if post.name not in nodes.keys():
                join_rgb = nodes.new('ShaderNodeCombineColor')
                join_rgb.name = post.name
                for chan in join_rgb.inputs:
                    chan.default_value = post.inputs[chan.name].value_col
            # Link input
            join_rgb = nodes[post.name]
            self.link_postproc(from_sock, join_rgb.outputs['Color'])
        elif post.bl_idname == 'BakeWrangler_Post_Math':
            # Add maths node
            if post.name not in nodes.keys():
                maths = nodes.new('ShaderNodeMath')
                maths.name = post.name
                maths.operation = post.op
                for val in post.inputs:
                    maths.inputs[int(val.identifier)].default_value = val.value
            # Link input
            maths = nodes[post.name]
            self.link_postproc(from_sock, maths.outputs['Value'])
        elif post.bl_idname == 'BakeWrangler_Post_Gamma':
            # Add gamma node
            if post.name not in nodes.keys():
                gamma = nodes.new('ShaderNodeGamma')
                gamma.name = post.name
                gamma.inputs['Gamma'].default_value = post.inputs['Gamma'].value_gam
            # Link input
            gamma = nodes[post.name]
            self.link_postproc(from_sock, gamma.outputs['Color'])

    # Link post proc to previous entry
    def link_postproc(self, from_sock, to_sock):
        nodes = self.postproc.node_tree.nodes
        links = self.postproc.node_tree.links
        if from_sock.node.bl_idname == 'BakeWrangler_Output_Vertex_Cols':
            prev_sock = nodes['bw_emit'].inputs['Color']
        elif from_sock.node.bl_idname == 'BakeWrangler_Output_Image_Path':
            if from_sock.name == 'Color':
                prev_sock = nodes['AlphaSwitch'].inputs['Out']
            else:
                prev_sock = nodes['AlphaMap'].inputs['Alpha']
                # Set up value mapping (default uses Value)
                if from_sock.input_channel in ['R', 'G', 'B']:
                    nodes['AlphaMap'].node_tree = nodes['AlphaMap'].node_tree.copy()
                    amap_nodes = nodes['AlphaMap'].node_tree.nodes
                    amap_links = nodes['AlphaMap'].node_tree.links
                    amap_links.new(amap_nodes['Alpha_Map'].outputs[from_sock.input_channel], amap_nodes['Output'].inputs['Alpha'])
        elif from_sock.node.bl_idname == 'BakeWrangler_Post_Math':
            # Determine which input it is since they have the same name
            prev_sock = nodes[from_sock.node.name].inputs[int(from_sock.identifier)]
        else:
            prev_sock = nodes[from_sock.node.name].inputs[from_sock.name]
        links.new(to_sock, prev_sock)


# Process the node tree with the given node as the starting point
def process_tree(tree_name, node_name, socket):
    # Create a base scene to work from that has every object in it
    global base_scene
    global mesh_scene
    global active_scene
    global current_frame
    global frame_range
    global padding
    global anim_seed
    global pdata
    base_scene = bpy.data.scenes.new("BakeWrangler_Base")
    mesh_scene = bpy.data.scenes.new("BakeWrangler_Mesh")
    active_scene = bpy.context.window.scene
    current_frame = active_scene.frame_current
    frame_range = None
    padding = None
    anim_seed = False
    pdata= False
    bpy.context.window.scene = base_scene
    # For now use active scenes current animation frame (maybe more advanced options later)
    base_scene.frame_current = current_frame
    for obj in bpy.data.objects:
        base_scene.collection.objects.link(obj)

    # Add a property on objects that can link to a copy made
    bpy.types.Object.bw_copy = bpy.props.PointerProperty(name="Object Copy", description="Copy with modifiers applied", type=bpy.types.Object)
    bpy.types.Object.bw_copy_frame = bpy.props.IntProperty(name="Object Copy frame", description="Frame number when created", default=current_frame)
    bpy.types.Object.bw_strip = bpy.props.PointerProperty(name="Object Stripped", description="Copy with modifiers stripped", type=bpy.types.Object)
    bpy.types.Object.bw_strip_frame = bpy.props.IntProperty(name="Object Stripped frame", description="Frame number when created", default=current_frame)
    bpy.types.Object.bw_vcols = bpy.props.PointerProperty(name="Object VCol Copy", description="Copy with modifiers intact", type=bpy.types.Object)
    bpy.types.Object.bw_auto_cage = bpy.props.PointerProperty(name="Cage", description="Bake Wrangler auto generated cage", type=bpy.types.Object)

    # Get tree position
    tree = bpy.data.node_groups[tree_name]
    node = tree.nodes[node_name]
    err = 0
    solutions = None
    global user_prop
    user_prop = None
    user_data = None
    solution_itr = 0
    frames_itr = 0
    batch_itr = 0
    global solution_restart
    global frames_restart
    global batch_restart

    if debug: _print("> Debugging output enabled", tag=True)
    modify_recipe(tree)
    
    # Create a list of output nodes (which will be 1 item if not a batch node)
    nouts = []
    batching = False
    if node.bl_idname == 'BakeWrangler_Output_Batch_Bake':
        batching = True
        for batch_input in node.inputs:
            nouts.append(get_input(batch_input))
        _print("> Batch Mode [%i jobs]" % (len(node.inputs) - 1), tag=True)
        # Batch mode has an optional user property that can be incremented, set that up
        if node.user_prop_objt and node.user_prop_name:
            user_data = node.user_prop_objt
            user_prop = node.user_prop_name
            if node.user_prop_zero:
                user_data[user_prop] = 0
                user_data.update_tag()
    elif node.bl_idname in ['BakeWrangler_Output_Image_Path', 'BakeWrangler_Output_Vertex_Cols']:
        nouts.append(node)
    else:
        _print("> Invalid bake tree starting node", tag=True)
        return True
    
    # Each output node will generate a dict of bake solutions which will then be processed. Results
    # are isolated within an output and may be regenerated if used in multiple outputs.
    for out_node in nouts:
        if not out_node: continue
        if batching:
            batch_itr += 1
            if (batch_itr - 1) < batch_restart: continue
        # A single output node, generate its solution list and then process them
        solutions = process_output_node(out_node, socket)
        if out_node.bl_idname == 'BakeWrangler_Output_Vertex_Cols':
            _print("> Processing [%s]: Creating %i vertex colors" % (out_node.get_name(), len(solutions.keys())), tag=True)
            _print(">", tag=True)
            for key in solutions.keys():
                solution_itr += 1
                if (solution_itr - 1) < solution_restart: continue
                else: solution_restart = 0
                err += process_vcol_solution(solutions[key])
                _print("<PSOLU>%i</PSOLU>" % (solution_itr))
            if batching:
                solution_itr = 0
                _print("<PSOLU>%i</PSOLU>" % (solution_itr))            
        else:
            # Check for frame ranges
            frames = sorted(out_node.frame_range())
            
            padding = out_node.frame_range(padding=True)
            anim_seed = out_node.frame_range(animated=True)
            pdata = out_node.frame_range(pdata=True)
            _print("Frames: %s Len: %s" % (frames, len(frames)), tag=True)
            if len(frames) <= 1:
                if len(frames) == 1: current_frame = frames.pop()                
                _print("> Processing [%s]: Creating %i images" % (out_node.get_name(), len(solutions.keys())), tag=True)
                _print(">", tag=True)
                for key in solutions.keys():
                    solution_itr += 1
                    if (solution_itr - 1) < solution_restart: continue
                    else: solution_restart = 0
                    err += process_solution(solutions[key])
                    _print("<PSOLU>%i</PSOLU>" % (solution_itr))
                if batching:
                    solution_itr = 0
                    free_data(freeImages=False)
                    _print("<PSOLU>%i</PSOLU>" % (solution_itr))
            elif len(frames) > 1:
                pack_data()
                frame_range = frames
                if debug: _print("> Frame range: %s" % (frame_range), tag=True)
                for frame in frames:
                    frames_itr += 1
                    if (frames_itr - 1) < frames_restart: continue
                    else: frames_restart = 0
                    current_frame = frame
                    base_scene.frame_current = current_frame
                    _print("> Processing [%s][Frame %s]: Creating %i images" % (out_node.get_name(), current_frame, len(solutions.keys())), tag=True)
                    _print(">", tag=True)
                    for key in solutions.keys():
                        solution_itr += 1
                        if (solution_itr - 1) < solution_restart: continue
                        else: solution_restart = 0
                        err += process_solution(solutions[key])
                        solutions[key].clear_results()
                        _print("<PSOLU>%i</PSOLU>" % (solution_itr))
                    _print("<PFRAM>%i</PFRAM>" % (frames_itr))
                    solution_itr = 0
                    _print("<PSOLU>%i</PSOLU>" % (solution_itr))
                    free_data()
                if batching:
                    frames_itr = 0
                    _print("<PFRAM>%i</PFRAM>" % (frames_itr))
        if batching:
            if user_prop != None:
                # Increment user property
                user_data[user_prop] += 1
                user_data.update_tag()
            _print("<PBATC%i</PBATC>" % (batch_itr))
            
    return err


# To simplify doing the texture normal pass, the recipe will be modified if that pass is in use (maybe other stuff in future)
def modify_recipe(tree):
    nodes = tree.nodes
    links = tree.links
    for node in nodes:
        if node.bl_idname == 'BakeWrangler_Bake_Pass' and node.bake_picked == 'TEXNORM' and node.norm_space == 'TANGENT' and node.use_subtraction:
            # Replace pass with a normal pass being subtracted from a object normals pass
            norms = node
            norms.bake_cat = 'CORE'
            norms.bake_core = 'NORMAL'
            objnorms = nodes.new('BakeWrangler_Bake_Pass')
            objnorms.bake_cat = 'PBR'
            objnorms.bake_pbr = 'OBJNORM'
            # Connect all the same inputs to the objnorm node
            for input in norms.inputs:
                if input.islinked():
                    if input.name == 'Settings':
                        links.new(input.links[0].from_socket, objnorms.inputs['Settings'])
                    else:
                        links.new(input.links[0].from_socket, objnorms.inputs[-1])
            # Create subtraction set up and insert it just after the pass nodes
            in_sub = nodes.new('BakeWrangler_Post_MixRGB')
            in_sub.op = 'SUBTRACT'
            in_sub.inputs['Fac'].value_fac = 1.0
            out_sub = nodes.new('BakeWrangler_Post_MixRGB')
            out_sub.op = 'ADD'
            out_sub.inputs['Fac'].value_fac = 1.0
            out_sub.inputs['Color2'].value_rgb = [0.5, 0.5, 1.0, 1.0]
            links.new(in_sub.outputs['Color'], out_sub.inputs['Color1'])

            for link in norms.outputs['Color'].links:
                links.new(out_sub.outputs['Color'], link.to_socket)

            links.new(norms.outputs['Color'], in_sub.inputs['Color1'])
            links.new(objnorms.outputs['Color'], in_sub.inputs['Color2'])
            in_sub.inputs['Color2'].valid = True


# Process an output node into a list of bake solutions
def process_output_node(node, socket=-1):
    solutions = {}
    idx = 0
    for sock in node.inputs:
        if sock.bl_idname == 'BakeWrangler_Socket_Color' and get_input(sock):
            if socket > -1:
                if socket == idx:
                    solutions[sock] = bake_solution(sock, node.inputs[idx+1], node.bl_idname == 'BakeWrangler_Output_Vertex_Cols')
            else:
                solutions[sock] = bake_solution(sock, node.inputs[idx+1], node.bl_idname == 'BakeWrangler_Output_Vertex_Cols')
        idx += 1
    return solutions


# Process solution for vetex color output, passes will be baked and saved to temp files for transfer
def process_vcol_solution(solution):
    err = 0
    # The first step in any solution is to bake all the required passes that haven't been done yet
    for key in solution.bakepass.keys():
        if not solution.bakepass[key].vcol_result:
            _print(">  Pass: [%s] " % (solution.bakepass[key].get_name()), tag=True, wrap=False)
            err += process_bake_pass(solution, key, solution.split)
    _print(">", tag=True)
    
    _print(">    -Exporting vertex colors:", tag=True, wrap=False)
    # Now process each objects output
    for obj in solution.bakecols.keys():
        if solution.dopost:
            # Set input vertex colors
            for node in solution.postproc.node_tree.nodes:
                if node.bl_idname == 'ShaderNodeVertexColor':
                    # Check there is a vcol for this node
                    if node.label in solution.bakecols[obj].keys():
                        node.layer_name = solution.bakecols[obj][node.label]
            berr, post_obj, post_vcol = bake_post_vcols(bpy.data.objects[obj].bw_vcols, solution.postproc, solution)
            err += berr
            if not berr:
                verr, file = ipc.bake_verts(verts=post_obj.data.color_attributes[post_vcol], object=obj, name=solution.sock.suffix, type=solution.format['vcol_type'], domain=solution.format['vcol_domain'])
                err += verr
                if not verr and file:
                    pickled_verts.append(file)
        else:
            for bake in solution.bakecols[obj].keys():
                verr, file = ipc.bake_verts(verts=bpy.data.objects[obj].bw_vcols.data.color_attributes[solution.bakecols[obj][bake]], object=obj, name=solution.sock.suffix, type=solution.format['vcol_type'], domain=solution.format['vcol_domain'])
                err += verr
                if not verr and file:
                    pickled_verts.append(file)
    return err


# Process a solution, all passes need to be baked and any post processes done before saving to an image
def process_solution(solution):
    err = 0
    # The first step in any solution is to bake all the required passes that haven't been done yet
    for key in solution.bakepass.keys():
        if not solution.bakepass[key].bake_result:
            _print(">  Pass: [%s] " % (solution.bakepass[key].get_name()), tag=True, wrap=False)
            err += process_bake_pass(solution, key, solution.split)
    ret = 0
    udim = solution.format['img_udim']
    if solution.split:
        # Go through each pass and generate just the objects in the split list saving each one
        for obj in solution.split:
            for key in solution.bakepass.keys():
                bake = solution.bakepass[key].bake_result
                if bake:
                    bake = bake.copy()
                mask = solution.bakepass[key].mask_result
                if mask:
                    mask = mask.copy()
                ret = process_bake_pass(solution, key, [obj], False, [bake, mask])
                if ret != -1:
                    err += ret
                    _print(">", tag=True)
                    if udim: # Output each udim
                        udims = []
                        for key in solution.baketile.keys():
                            for tile in solution.baketile[key].keys():
                                if tile not in udims:
                                    udims.append(tile)
                        udims.sort()
            if not err:
                obname = obj[0].name
                if len(obj) > 3: obname = obj[3]
                if udim:
                    for tile in udims:
                        err += process_output(solution, obname, udim=tile)
                else:
                    err += process_output(solution, obname)
    if not solution.split:# or ret == -1:
        _print(">", tag=True)
        if udim: # Output each udim
            udims = []
            for key in solution.baketile.keys():
                for tile in solution.baketile[key].keys():
                    if len(solution.baketile[key][tile]) and tile not in udims:
                        udims.append(tile)
            udims.sort()
            for tile in udims:
                err += process_output(solution, udim=tile)
        else:
            err += process_output(solution)
    return err


# Do post processing and generate output image
def process_output(solution, split="", udim=None):
    err = 0
    # Check for frame range
    frame_str = ''
    if frame_range or padding:
        if padding:
            pad_width = padding
        else:
            pad_width = len(str(max(frame_range)))
        frame_str = '{frame:0{width}}'.format(frame=current_frame, width=pad_width)
    # Get file path
    output_path = solution.sock.node.img_path
    use_tokens = solution.sock.node.use_tokens()
    if use_tokens:
        output_name = solution.sock.node.name_with_ext()
        unset_tokens = ""
        if output_name.find("<OBJECT>") == -1:
            unset_tokens = unset_tokens + split
        if output_name.find("<SUFFIX>") == -1:
            unset_tokens = unset_tokens + solution.sock.suffix
        if output_name.find("<UDIM>") == -1 and udim:
            unset_tokens = unset_tokens + "." + str(udim)
        if output_name.find("<FRAME>") == -1 and frame_str:
            unset_tokens = unset_tokens + "." + frame_str
        output_name = solution.sock.node.name_with_ext(unset_tokens)
        # Do token replacement on paths
        output_name = output_name.replace("<OBJECT>", split)
        output_name = output_name.replace("<SUFFIX>", solution.sock.suffix)
        output_name = output_name.replace("<UDIM>", str(udim))        
        output_name = output_name.replace("<FRAME>", frame_str)
    elif udim is not None:
        frameDotStr = ""
        if frame_str:
            frameDotStr = "." + frame_str
        output_name = solution.sock.node.name_with_ext(split + solution.sock.suffix + "." + str(udim) + frameDotStr)
    else:
        output_name = solution.sock.node.name_with_ext(split + solution.sock.suffix + frame_str)
    output_file = os.path.join(os.path.realpath(output_path), output_name)

    # See if the output exists or if a new file should be created
    orig_exists = False
    if os.path.exists(output_file):
        orig_image = bpy.data.images.load(os.path.abspath(output_file))
        bw_solution_data['images'].append(orig_image)
        orig_image.alpha_mode = 'CHANNEL_PACKED' # Prevent alpha changing output color
        orig_exists = True

    # Next post processing should take place as well as alpha channel creation if needed
    _print(">  Image: [%s] " % (output_name), tag=True)
    post_alpha = None
    if solution.format['img_color_mode'] == 'RGBA':
        post_alpha = bpy.data.images.new(output_name + "alpha", solution.format['img_xres'], solution.format['img_yres'])
        bw_solution_data['images'].append(post_alpha)
        post_alpha.use_generated_float = solution.format['img_use_float']
        post_alpha.alpha_mode = 'NONE'
        post_alpha.colorspace_settings.name = solution.format['img_non_color']
        post_alpha.colorspace_settings.is_data = True
    # See if this solution will use marginer and need the combined mask
    post_mask = None
    if solution.format['marginer']:
        post_mask = bpy.data.images.new(output_name + "mask", solution.format['img_xres'], solution.format['img_yres'])
        bw_solution_data['images'].append(post_mask)
        post_mask.alpha_mode = 'NONE'
        post_mask.colorspace_settings.name = solution.format['img_non_color']
        post_mask.colorspace_settings.is_data = True
    # Create post color image
    post_color = bpy.data.images.new(output_name + "color", solution.format['img_xres'], solution.format['img_yres'])
    bw_solution_data['images'].append(post_color)
    post_color.colorspace_settings.name = solution.format['img_color_space']
    post_color.use_generated_float = solution.format['img_use_float']

    nodes = solution.postproc.node_tree.nodes
    links = solution.postproc.node_tree.links
    # Set original image if it was loaded unless clear image is set
    if orig_exists and not solution.format['img_clear']:
        nodes['bw_input_orig'].image = orig_image
    else:
        nodes['bw_input_orig'].image = bpy.data.images["bw_default_orig"]
    # Images in the post proc need to be set before running it
    masks = []
    for node in nodes:
        if node.bl_idname == 'ShaderNodeGroup' and node.node_tree == post_masked_bake:
            # Set the bake input
            bake_img = None
            bake_set = solution.bakepass[node.label].get_settings()
            if node.inputs['Bake'].is_linked:
                bake_img = node.inputs['Bake'].links[0].from_node
                if bake_set['interpolate']:
                    bake_img.interpolation = 'Cubic'
                if split:
                    if udim is not None:
                        if udim in solution.baketile[node.label].keys():
                            bake_img.image = solution.baketile[node.label][udim][0]#.copy()
                            #bake_img.image.pixels = solution.baketile[node.label][udim][2].pixels[:]
                        else:
                            bake_img.image = bpy.data.images["bw_default_orig"]
                    else:
                        bake_img.image = solution.bakepass[node.label].sbake_result#.copy()
                        #bake_img.image.pixels = solution.bakepass[node.label].sbake_result.pixels[:]
                else:
                    if udim is not None:
                        if udim in solution.baketile[node.label].keys():
                            bake_img.image = solution.baketile[node.label][udim][0]#.copy()
                            #bake_img.image.pixels = solution.baketile[node.label][udim][0].pixels[:]
                        else:
                            bake_img.image = bpy.data.images["bw_default_orig"]
                    else:
                        bake_img.image = solution.bakepass[node.label].bake_result#.copy()
                        #bake_img.image.pixels = solution.bakepass[node.label].bake_result.pixels[:]
                bake_img.image.scale(solution.format['img_xres'], solution.format['img_yres'])
            mask_img = None
            if node.inputs['Mask'].is_linked:
                if bake_set['use_mask'] or solution.format['marginer']:
                    mask_img = node.inputs['Mask'].links[0].from_node
                    bake_set = solution.bakepass[node.label].get_settings()
                    if split:
                        if udim is not None:
                            if udim in solution.baketile[node.label]:
                                mask_img.image = solution.baketile[node.label][udim][3]
                            else:
                                mask_img.image = bpy.data.images["bw_default_orig"]
                        else:
                            mask_img.image = solution.bakepass[node.label].smask_result
                    else:
                        if udim is not None:
                            if udim in solution.baketile[node.label]:
                                mask_img.image = solution.baketile[node.label][udim][1]
                            else:
                                mask_img.image = bpy.data.images["bw_default_orig"]
                        else:
                            mask_img.image = solution.bakepass[node.label].mask_result
                    mask_img.image.scale(solution.format['img_xres'], solution.format['img_yres'])
                    masks.append(node)
                else:
                    links.remove(node.inputs['Mask'].links[0])
    # Add all masks together
    add_masks(masks, nodes, solution.postproc.node_tree.links)

    # Bake post material
    err += bake_post_material(post_color, post_alpha, solution.postproc, post_mask, bake_set['use_mask'])

    # Apply alpha channel if needed
    post_combined = None
    if post_alpha:
        _print(">   -Creating alpha channel", tag=True, wrap=False)
        post_combined = bpy.data.images.new(output_name + "combined", solution.format['img_xres'], solution.format['img_yres'])
        bw_solution_data['images'].append(post_combined)
        post_combined.colorspace_settings.name = solution.format['img_color_space']
        post_combined.use_generated_float = solution.format['img_use_float']
        post_combined.alpha_mode = 'CHANNEL_PACKED'
        aerr = alpha_pass(post_color, post_alpha, post_combined)
        if not aerr:
            _print("", tag=True)
        err += aerr

    # Switch into output scene and apply output format
    bpy.context.window.scene = output_scene
    apply_output_format(output_scene.render.image_settings, solution.format)
    solution_image = post_color
    if post_combined: solution_image = post_combined

    # Do final processing if needed
    if solution.format['marginer']: paint_margin(solution_image, post_mask, solution.format['marginer_size'], solution.format['marginer_fill'])
    if solution.format['fast_aa']: fast_aa(solution_image, solution.format['fast_aa_lvl'])

    # Save the image to disk
    _print(">   -Writing changes to %s" % (output_file), tag=True)
    _print(">", tag=True)
    solution_image.save_render(output_file, scene=output_scene)

    images_saved.append(output_file)
    bpy.context.window.scene = base_scene

    return err


# Takes a bake pass node and output format, creating an image in the bake_result and mask_result (if used)
def process_bake_pass(solution, key, split_list=None, exclude=True, imgs=None):
    err = False
    no_split = True
    node = solution.bakepass[key]
    format = solution.format
    udim = format['img_udim']
    vcol = True if 'vcol' in format.keys() else False
    

    # Gather pass settings
    bake_settings = node.get_settings()
    bake_settings['node_name'] = node.name
    bake_settings['vcol'] = vcol
    bake_meshes = node.get_inputs()
    bake_settings['tile_path'] = ""

    # Generate the bake and mask images
    def pbp_img_gen(imgs=None, node=None, bake_settings=None):
        if imgs is None or (len(imgs) and imgs[0] is None):
            if imgs is None: _print(" [Mesh Nodes (%i)]" % (len(bake_meshes)), tag=True)
            img_bake = bpy.data.images.new(node.get_name(), width=bake_settings["x_res"], height=bake_settings["y_res"])
            bw_solution_data['images'].append(img_bake)
            img_mask = None
            img_bake.alpha_mode = 'NONE'
            if format['img_use_float']:
                img_bake.use_generated_float = True
            img_bake.colorspace_settings.name = format['img_color_space']
            #img_bake.colorspace_settings.name = 'Linear'
            if 'sRGB' in format['img_color_space']:
                bake_settings['osl_curv_srgb'] = True
            if bake_settings['use_bg_col']:
                img_bake.generated_color = bake_settings['bg_color']
            else:
                if (bake_settings['bake_type'] in ['NORMAL', 'TEXNORM', 'OBJNORM', 'BEVNORMEMIT', 'BEVNORMNORM', 'CLEARNORM', 'OSL_BENTNORM'] and bake_settings['norm_s'] == 'TANGENT') or (bake_settings['bake_type'] == 'MULTIRES' and bake_settings['multi_pass'] == 'NORMALS'):
                    img_bake.generated_color = (0.5, 0.5, 1.0, 1.0)
                elif bake_settings['bake_type'] == 'CURVATURE':
                    img_bake.generated_color = (bake_settings["curv_mid"], bake_settings["curv_mid"], bake_settings["curv_mid"], 1.0)
                elif bake_settings['bake_type'] == 'OSL_HEIGHT':
                    img_bake.generated_color = (bake_settings["osl_height_midl"], bake_settings["osl_height_midl"], bake_settings["osl_height_midl"], 1.0)
            #if bake_settings['use_mask']:
            img_mask = bpy.data.images.new("mask_" + node.get_name(), width=bake_settings["x_res"], height=bake_settings["y_res"])
            bw_solution_data['images'].append(img_mask)
            img_mask.alpha_mode = 'NONE'
            img_mask.colorspace_settings.name = format['img_non_color']
            img_mask.colorspace_settings.is_data = True
        else:
            img_bake = imgs[0]
            img_mask = None
            #if bake_settings['use_mask'] and len(imgs) > 1:
            if len(imgs) > 1:
                img_mask = imgs[1]
        return img_bake, img_mask

    if not vcol:
        img_bake, img_mask = pbp_img_gen(imgs=imgs, node=node, bake_settings=bake_settings)
    else:
        _print(" [Mesh Nodes (%i)]" % (len(bake_meshes)), tag=True)
        img_bake = img_mask = None

    # Begin processing bake meshes
    for mesh_dat in bake_meshes:
        mesh = mesh_dat[0]
        multi = (bake_settings['bake_type'] == 'MULTIRES')

        # Determine bake type and object groups
        def pbp_type_and_obj_groups(mesh=None):
            hi2lo = False
            matbk = False
            bbbk = False
            bake_settings['bbbk'] = False
            if mesh.bl_idname == 'BakeWrangler_Sort_Meshes':
                input_src = get_input(mesh_dat[1])
                mesh_settings = mesh.get_settings(input=mesh_dat[1])
                mesh_settings['mesh_name'] = input_src.name
                mesh_settings['mesh_label'] = input_src.get_name()
                if input_src.bl_idname == 'BakeWrangler_Bake_Material':
                    hi2lo = False
                    matbk = True
                    active_meshes = input_src.get_materials()
                    selected_objs = []
                    scene_objs = []
                else:
                    hi2lo = True
                    active_meshes = mesh.get_objects('TARGET', mesh_dat[1])
                    selected_objs = mesh.get_objects('SOURCE', mesh_dat[1])
                    scene_objs = mesh.get_objects('SCENE', mesh_dat[1])
            else:
                mesh_settings = mesh.get_settings()
                mesh_settings['mesh_name'] = mesh.name
                mesh_settings['mesh_label'] = mesh.get_name()
                if mesh.bl_idname == 'BakeWrangler_Bake_Material':
                    matbk = True
                    active_meshes = mesh.get_materials()
                    selected_objs = []
                    scene_objs = []
                else:
                    if mesh.bl_idname == 'BakeWrangler_Bake_Billboard':
                        bbbk = True
                        bake_settings['bbbk'] = True
                    active_meshes = mesh.get_objects('TARGET')
                    selected_objs = mesh.get_objects('SOURCE')
                    scene_objs = mesh.get_objects('SCENE')
            return hi2lo, matbk, bbbk, mesh_settings, active_meshes, selected_objs, scene_objs

        hi2lo, matbk, bbbk, mesh_settings, active_meshes, selected_objs, scene_objs = pbp_type_and_obj_groups(mesh=mesh)
        bake_settings['bbbk'] = bbbk

        # Bake is supposed to be split into multiple files based on object names from list
        if split_list:
            active_split = []
            for act in active_meshes:
                msh = act
                if hi2lo:
                    replace_list = []
                    for splt in split_list:
                        replace_list.append(splt[0:3])
                    split_list  = replace_list
                    msh = act[0]
                if (exclude and msh not in split_list) or (not exclude and msh in split_list):
                    active_split.append(act)
            if len(active_split):
                active_meshes = active_split
                no_split = False
            else:
                continue

        if matbk:
            _print(">   Materials: [%s] [Targets (%i)]" % (mesh_settings['mesh_label'], len(active_meshes)), tag=True)
        elif bbbk:
            _print(">   Billboard: [%s]" % (mesh_settings['mesh_label']), tag=True)
        else:
            _print(">   Mesh: [%s] [Targets (%i)]" % (mesh_settings['mesh_label'], len(active_meshes)), tag=True)

        if mesh_settings['margin'] > 0 or mesh_settings['margin_auto']:
            if mesh_settings['margin_auto']:
                mesh_settings["margin"] = min(bake_settings["x_res"], bake_settings["y_res"]) / 256
                if mesh_settings["margin"] < 1: mesh_settings["margin"] = 1
                if mesh_settings["margin"] > 32: mesh_settings["margin"] = 32
            # Recalculate margin size based on ratio between bake and output images
            bake_ratio = math.sqrt(math.pow(bake_settings["x_res"], 2) + math.pow(bake_settings["y_res"], 2)) # Pythag for diagonal
            outp_ratio = math.sqrt(math.pow(format['img_xres'], 2) + math.pow(format['img_yres'], 2))
            margin_ratio = bake_ratio / outp_ratio # Ratio between sizes
            mesh_settings["margin"] *= margin_ratio # Multiply margin by ratio to maintain size in output
            if debug: _print(">   Margin %s" % (mesh_settings["margin"]), tag=True)

        # Process each active mesh
        for active in active_meshes:
            # Unpack active and selected from active if doing high to low poly auto mapped bake
            if hi2lo:
                scene_objs = active[2]
                selected_objs = active[1]
                active = active[0]
            # Load in template bake scene with mostly optimized settings for baking
            bake_scene_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "resources", "BakeWrangler_Scene.blend")
            with bpy.data.libraries.load(bake_scene_path, link=False, relative=False) as (file_from, file_to):
                file_to.scenes.append("BakeWrangler")
            bake_scene = file_to.scenes[0]
            bake_scene.name = "bake_" + node.get_name() + "_" + mesh.get_name() + "_" + active[0].name
            bake_scene.frame_current = current_frame
            if anim_seed:
                bake_scene.cycles.seed = current_frame
            if pdata:
                bake_scene.render.use_persistent_data = True
            bw_solution_data['scenes'].append(bake_scene)

            # Copy render settings if required
            if bake_settings['cpy_render']:
                if bake_settings['cpy_from'] in [None, ""]:
                    bake_settings['cpy_from'] = active_scene
                copy_render_settings(bake_settings['cpy_from'], bake_scene)
                
            # Set up camera if that is ray origin
            if 'view_from' in mesh_settings:
                bake_scene.collection.objects.link(mesh_settings['view_from'])
                bake_scene.camera = mesh_settings['view_from']
                bake_scene.render.bake.view_from = 'ACTIVE_CAMERA'
            else:
                bake_scene.render.bake.view_from = 'ABOVE_SURFACE'

            # Set the device and sample count to override anything that could have been copied
            bake_OSL = False
            bake_scene.cycles.device = bake_settings['bake_device']
            if bake_settings['bake_type'].startswith('OSL_') or (mesh_settings['material_replace'] and mesh_settings['material_osl']):
                if bake_settings['bake_type'] == 'OSL_HEIGHT':
                    bake_OSL = True
                bake_scene.cycles.device = 'CPU'
                bake_scene.cycles.shading_system = True
            bake_scene.cycles.samples = bake_settings['bake_samples']
            #bake_scene.cycles.aa_samples = bake_settings['bake_samples']
            bake_scene.cycles.use_adaptive_sampling = bake_settings['bake_usethresh']
            bake_scene.cycles.adaptive_threshold = bake_settings['bake_threshold']
            bake_scene.cycles.time_limit = bake_settings['bake_timelimit']

            # Set custom world instead of default if enabled
            if bake_settings['use_world']:
                if bake_settings['the_world'] not in [None, ""]:
                    bake_scene.world = bake_settings['the_world']
                else:
                    bake_scene.world = active_scene.world

            # Initialise bake type settings
            mesh_settings["cage"] = False
            mesh_settings["cage_object"] = None
            mesh_settings["cage_obj_name"] = ""
            to_active = False
            selected = None

            # For material bake, we can skip most of the rest of the steps
            if matbk:
                # Add a plane, sized correctly and put a copy of the material on it after being prepped
                matpln = material_plane.copy()
                bw_solution_data['objects'].append(matpln)
                matpln.data = material_plane.data.copy()
                matpln.name = "mat_plane_" + active[0].name
                matpln.dimensions = (mesh_settings['matbk_width'], mesh_settings['matbk_height'], 0.0)
                # Do material copy and prep
                mat2bk = active[0].copy()
                bw_solution_data['materials'].append(mat2bk)
                matpln.data.materials.append(mat2bk)
                bake_scene.collection.objects.link(matpln)
                # Switch into bake scene
                bpy.context.window.scene = bake_scene
                # Select the target and make it active
                bpy.ops.object.select_all(action='DESELECT')
                matpln.select_set(True)
                bpy.context.view_layer.objects.active = matpln
                # Bake the plane
                err += bake_solo(img_bake, {'mat': mat2bk}, bake_settings, mesh_settings)
                # Switch back to main scene before next pass. Nothing will be deleted so that the file can be examined for debugging.
                bpy.context.window.scene = base_scene
                # Skip the rest of the steps
                continue

            # Determine what strategy to use for this bake
            if not multi:
                # See if there are valid source objects to do a selected to active bake
                for obj in selected_objs:
                    # Let a duplicate of the target object count if they use different UV Maps
                    if obj[0] != active[0] or (len(obj) > 1 and len(active) > 1 and obj[1] != active[1]):
                        to_active = True
                        break
                if mesh_settings["bake_mods"]: to_active = True
                # Copy all selected objects over if 'to active' pass
                if to_active:
                    selected = bpy.data.collections.new("Selected_" + active[0].name)
                    bw_solution_data['collections'].append(selected)
                    if mesh_settings["bake_mods"]:
                        # Add the Target to the Sources if it isn't already in the list before processing
                        active_in_selected = False
                        for obj in selected_objs:
                            if obj[0] == active[0]:
                                active_in_selected = True
                                break
                        if not active_in_selected:
                            selected_objs.append(active)
                    for obj in selected_objs:
                        # Let a duplicate of the target object in if they use different UV Maps
                        if obj[0] != active[0] or (len(obj) > 1 and len(active) > 1 and obj[1] != active[1]) or mesh_settings["bake_mods"]:
                            copy = prep_object_for_bake(obj[0], invert=mesh_settings["bake_mods_invert"], vcols=[vcol, active[0]])
                            bw_solution_data['objects'].append(copy)
                            selected.objects.link(copy)
                            # Set UV map to use if one was selected
                            if len(obj) > 1 and obj[1] not in [None, ""]:
                                copy.data.uv_layers.active = copy.data.uv_layers[obj[1]]
                    bake_scene.collection.children.link(selected)
                    # Add the cage copy to the scene because it doesn't work properly in a different scene currently
                    if len(active) > 2 and active[2]:
                        mesh_settings["cage"] = True
                        mesh_settings["cage_object"] = prep_object_for_bake(active[2], invert=mesh_settings["bake_mods_invert"], vcols=[vcol, active[0]])
                        bw_solution_data['objects'].append(mesh_settings["cage_object"])
                        mesh_settings["cage_obj_name"] = mesh_settings["cage_object"].name
                    elif active[0].bw_auto_cage:
                        mesh_settings["cage"] = True
                        mesh_settings["cage_object"] = prep_object_for_bake(active[0].bw_auto_cage, invert=mesh_settings["bake_mods_invert"], vcols=[vcol, active[0]])
                        bw_solution_data['objects'].append(mesh_settings["cage_object"])
                        mesh_settings["cage_obj_name"] = mesh_settings["cage_object"].name
            else:
                # Collection of base objects for multi-res to link into
                base_col = bpy.data.collections.new("Base_" + active[0].name)
                bw_solution_data['collections'].append(base_col)
                bake_scene.collection.children.link(base_col)

            # Regardless of strategy the following data will be used. Copies are made so other passes can get the originals
            if not multi:
                if mesh_settings["bake_mods"]:
                    target = prep_object_for_bake(active[0], strip=True, invert=mesh_settings["bake_mods_invert"], vcols=[vcol, active[0]])
                else:
                    target = prep_object_for_bake(active[0], vcols=[vcol, active[0]])
            else:
                active_obj = active[0]
                target = active_obj.copy()
                target.data = active_obj.data.copy()
            bw_solution_data['objects'].append(target)

            # Check for valid cage now if one is set
            if mesh_settings["cage"]:
                if len(target.data.polygons) != len(mesh_settings["cage_object"].data.polygons):
                    _print(">    !Cage invalid for [%s]" % (active[0].name), tag=True)
                    mesh_settings["cage"] = False
                    mesh_settings["cage_obj_name"] = ""

            # Set UV map to use if one was selected
            if len(active) > 1 and active[1] not in [None, ""]:
                target.data.uv_layers.active = target.data.uv_layers[active[1]]

            # Materials should be removed from the target copy for To active
            if to_active:
                target.data.materials.clear()
                target.data.polygons.foreach_set('material_index', [0] * len(target.data.polygons))
                target.data.update()
                # If no specific cage, but auto cage is enabled, create a cage for the object
                if not mesh_settings["cage"] and mesh_settings["auto_cage"]:
                    mesh_settings["cage"] = True
                    mesh_settings["cage_object"] = target.copy()
                    mesh_settings["cage_object"].data = target.data.copy()
                    mesh_settings["cage_object"].name = "%s.%s" % (target.name, "auto_cage")
                    mesh_settings["cage_obj_name"] = mesh_settings["cage_object"].name
                    # Expand the cage object
                    cage_displace = mesh_settings["cage_object"].modifiers.new("cage_disp", 'DISPLACE')
                    cage_displace.strength = mesh_settings['acage_expansion']
                    cage_displace.direction = 'NORMAL'
                    cage_displace.mid_level = 0.0
                    # Smooth normals
                    cage_smooth = mesh_settings["cage_object"].modifiers.new("cage_smov", 'NODES')
                    cage_smooth.node_group = auto_smooth
                    cage_smooth["Input_1"] = mesh_settings['acage_smooth']
                    for poly in mesh_settings["cage_object"].data.polygons:
                        poly.use_smooth = True
                    # Clear sharps
                    for edge in mesh_settings["cage_object"].data.edges:
                        edge.use_edge_sharp = False

            # Add target before doing mats
            if not to_active or bake_OSL:
                bake_scene.collection.objects.link(target)

            # Replace materials if required
            if bake_settings['bake_cat'] == 'WRANG' or mesh_settings['material_replace']:
                replace_materials_for_shader_bake(bake_scene, bake_settings, mesh_settings)
                # Add OSL materials to target now so they can be configured by the next step
                if bake_settings['bake_type'] == 'OSL_HEIGHT':
                    target.data.materials.append(osl_height)
            # Create unique copies for every material in the scene before anything else is done
            unique_mats = make_materials_unique_to_scene(bake_scene, "_" + node.name + "_" + mesh.name + "_" + active[0].name, bake_settings)
            for mkey in unique_mats.keys():
                bw_solution_data['materials'].append(unique_mats[mkey])

            # Add target after doing mats
            if to_active and not bake_OSL:
                bake_scene.collection.objects.link(target)

            # Make sure a basic material is on the target
            if bbbk:
                # Modify settings for billboard bake here to use glossy color pass with special material
                basic_mat = billboard_mat.copy()
                bw_solution_data['materials'].append(basic_mat)
                basic_mat.name = billboard_mat.name + node.name + mesh.name
                check_has_material(target, None, basic_mat)
            else:
                basic_mat = bpy.data.materials.new(name="bw_basic_" + node.name + "_" + mesh.name)
                bw_solution_data['materials'].append(basic_mat)
                basic_mat.use_nodes = True
                check_has_material(target, unique_mats, basic_mat)
                # Add a material to any objects lacking a material for bent norms
                if bake_settings['bake_type'] == 'OSL_BENTNORM':
                    bent_mat = basic_mat.copy()
                    bw_solution_data['materials'].append(bent_mat)
                    bent_mat.name = "bw_bent_" + node.name + "_" + mesh.name
                    if to_active:
                        for from_obj in selected.objects:
                            check_has_material(from_obj, unique_mats, bent_mat)

            # Rotation of target
            bake_settings['bb_rot'] = active[0].rotation_euler

            # Copy all scene objects over if not a multi-res pass
            if not multi:
                scene = bpy.data.collections.new("Scene_" + active[0].name)
                bw_solution_data['collections'].append(scene)
                for obj in scene_objs:
                    # Exclude current target if its in the list as well as any source objects as these
                    # cause problems in blender 3.1
                    dups = [active[0]]
                    for dup in selected_objs:
                        dups.append(dup[0])
                    if obj[0] not in dups:
                        scene.objects.link(obj[0])
                bake_scene.collection.children.link(scene)
                # Add cage object
                if mesh_settings["cage"]:
                    bake_scene.collection.objects.link(mesh_settings["cage_object"])

            # Switch into bake scene
            bpy.context.window.scene = bake_scene

            # OSL setup for cage, swaps cage for target
            if (bake_OSL or bbbk) and mesh_settings["cage_object"]:
                target.hide_render = True
                mesh_settings["cage_object"].data.materials.clear()
                mesh_settings["cage_object"].data.polygons.foreach_set('material_index', [0] * len(target.data.polygons))
                mesh_settings["cage_object"].data.update()
                mesh_settings["cage_object"].data.materials.append(target.data.materials[0])
                target = mesh_settings["cage_object"]
                mesh_settings["cage"] = False

            # Select the target and make it active
            bpy.ops.object.select_all(action='DESELECT')
            target.select_set(True)
            bpy.context.view_layer.objects.active = target

            # If UDIM tiles are enabled, the bake must repeat for each tile and the UV map needs to be modified between
            if udim:
                tiles = solution.baketile[key]
                udims = udim_util.uv_to_udim(solution, key, target.data.uv_layers.active)
                
                # Make copes of the bake (and mask) image data blocks to load the individual tiles into after bake
                for tile in udims:
                    if not len(tiles[tile]):
                        tile_bake = img_bake.copy()
                        bw_solution_data['images'].append(tile_bake)
                        tile_bake.name = "%s.%s" % (img_bake.name, tile)
                        tile_mask = None
                        if bake_settings['use_mask'] or format['marginer']:
                            tile_mask = img_mask.copy()
                            bw_solution_data['images'].append(tile_mask)
                            tile_mask.name = "%s.%s" % (img_mask.name, tile)
                        tiles[tile] = [tile_bake, tile_mask]
                
                # Modify bake image data to reflect tile configuration
                udim_util.create_tiles(img_bake, udims)
                if bake_settings['use_mask'] or format['marginer']:
                    udim_util.create_tiles(img_mask, udims)
               
                _print(">    UDIM: [%s] [Tiles (%s)]" % (active[0].name, len(udims)), tag=True)
                
                # Perform bake type needed
                if multi:
                    err += bake_multi_res(img_bake, unique_mats, bake_settings, mesh_settings, base_col, target, active_obj)
                elif to_active and not bake_OSL:
                    err += bake_to_active(img_bake, unique_mats, bake_settings, mesh_settings, selected)
                else:
                    err += bake_solo(img_bake, unique_mats, bake_settings, mesh_settings)
                if bake_settings['use_mask'] or format['marginer']:
                    err += bake_mask(img_mask, unique_mats, bake_settings, mesh_settings, to_active, target, selected)
                
                # Separate tiles
                apply_output_format(bake_scene.render.image_settings, solution.format)
                udim_util.separate_tiles(src=img_bake, tiles=tiles, index=0)
                if bake_settings['use_mask'] or format['marginer']:
                    udim_util.separate_tiles(src=img_mask, tiles=tiles, index=1)
            else:
                if vcol:
                    img_vcol = target.data.color_attributes.new(node.get_name(), format['vcol_type'], format['vcol_domain'])
                    target.data.color_attributes.active_color = img_vcol

                # Perform bake type needed
                if multi:
                    if vcol: _print(">    Multi-Resolution cannot be output to vertex colors, skipping pass", tag=True)
                    else: err += bake_multi_res(img_bake, unique_mats, bake_settings, mesh_settings, base_col, target, active_obj)
                elif to_active and not bake_OSL:
                    err += bake_to_active(img_bake, unique_mats, bake_settings, mesh_settings, selected)
                else:
                    err += bake_solo(img_bake, unique_mats, bake_settings, mesh_settings)

                # Bake the mask if samples are non zero
                if (bake_settings['use_mask'] or format['marginer']) and not vcol:
                    # Set samples to the mask value
                    bake_scene.cycles.device = bake_settings['bake_device']
                    bake_scene.cycles.samples = 1
                    #bake_scene.cycles.aa_samples = 1
                    err += bake_mask(img_mask, unique_mats, bake_settings, mesh_settings, to_active, target, selected)

                # Output vcolors to vcol object copy
                if vcol:
                    if active[0].name not in solution.bakecols.keys():
                        # Create dict for this object if not done already
                        solution.bakecols[active[0].name] = {}
                    # Store name of vcols for this bake node
                    solution.bakecols[active[0].name][node.name] = img_vcol.name
                    # Copy vcols to base object copy
                    copy_vert_cols(name=img_vcol.name, cpy_from=target, cpy_to=active[0].bw_vcols)

            # Switch back to main scene before next pass. Nothing will be deleted so that the file can be examined for debugging.
            bpy.context.window.scene = base_scene

    # Return early if no split list item was baked
    if split_list and no_split:
        if not exclude:
            return -1
        else:
            return err

    # Finished inputs, return the bakes
    if not vcol:
        if exclude:
            node.bake_result = img_bake
            node.mask_result = img_mask
        else:
            node.sbake_result = img_bake
            node.smask_result = img_mask
    elif vcol:
        node.vcol_result = img_vcol
    return err



# Bake a multi-res pass
def bake_multi_res(img_bake, materials, bake_settings, mesh_settings, base_col, target, original, pre_only=False, tile=None):
    # Set multi res levels on copy
    multi_mod = None
    if not tile: # Tile is assumed to have run a pre only time first
        for mod in target.modifiers:
            if mod.type == 'MULTIRES':
                multi_mod = mod
                break
        if multi_mod:
            multi_mod.levels = 0
            multi_mod.render_levels = multi_mod.total_levels
            if bake_settings["multi_samp"] == 'FROMMOD':
                src_mod = None
                for mod in original.modifiers:
                    if mod.type == 'MULTIRES':
                        src_mod = mod
                        break
                if src_mod:
                    multi_mod.levels = src_mod.levels
                    multi_mod.render_levels = src_mod.render_levels
            elif bake_settings["multi_samp"] == 'CUSTOM':
                if bake_settings["multi_targ"] >= 0 and bake_settings["multi_targ"] <= multi_mod.total_levels:
                    multi_mod.levels = bake_settings["multi_targ"]
                if bake_settings["multi_sorc"] >= 0 and bake_settings["multi_sorc"] <= multi_mod.total_levels:
                    multi_mod.render_levels = bake_settings["multi_sorc"]

        # Next link all the objects from the base scene to hopefully stop any modifier errors
        for obj in base_scene.objects:
            base_col.objects.link(obj)
            obj.select_set(False)

    # Add a bake target image node to each material
    for mat in materials.values():
        if not tile:
            if debug: _print(">    Preparing material [%s] for [Multi-Res %s] bake" % (mat.name, bake_settings['bake_type']), tag=True)
            image_node = mat.node_tree.nodes.new("ShaderNodeTexImage")
            image_node.image = img_bake
            image_node.select = True
            mat.node_tree.nodes.active = image_node
        else:
            # In the case of a tile, the node should already be created and active, so just change image path
            image_node = mat.node_tree.nodes.active
            image_node.image = tile

    # Bake it
    if pre_only: return 0
    return bake(bake_settings['bake_cat'], bake_settings['multi_pass'], bake_settings, mesh_settings, False, True)



# Bake a to-active pass
def bake_to_active(img_bake, materials, bake_settings, mesh_settings, selected, pre_only=False, tile=None):
    if not tile:
        # Make the source objects selected
        if not bake_settings['bbbk']:
            for obj in selected.objects:
                obj.select_set(True)

        # Add texture node set up to target object
        mat = bpy.context.view_layer.objects.active.material_slots[0].material
        image_node = mat.node_tree.nodes.new("ShaderNodeTexImage")
        image_node.image = img_bake
        image_node.select = True
        mat.node_tree.nodes.active = image_node

        # Prepare the materials for the bake type
        for mat in materials.values():
            if debug: _print(">     Preparing material [%s] for [%s] bake" % (mat.name, bake_settings['bake_type']), tag=True)
            if not mat.name.startswith('bw_basic_'): prep_material_for_bake(mat.node_tree, bake_settings['bake_type'], bake_settings)
    else:
        # In the case of a tile, the node should already be created and active, so just change image path
        mat = bpy.context.view_layer.objects.active.material_slots[0].material
        image_node = mat.node_tree.nodes.active
        image_node.image = tile

    # Bake it
    if pre_only: return 0
    return bake(bake_settings['bake_cat'], bake_settings['bake_type'], bake_settings, mesh_settings, True, False)



# Bake single object pass
def bake_solo(img_bake, materials, bake_settings, mesh_settings, pre_only=False, tile=None):
    # Prepare the materials for the bake type
    for mat in materials.values():
        if not tile:
            if debug: _print(">     Preparing material [%s] for [%s] bake" % (mat.name, bake_settings['bake_type']), tag=True)
            prep_material_for_bake(mat.node_tree, bake_settings['bake_type'], bake_settings)
            # For non To active bakes, add an image node to the material and make it selected + active for bake image
            image_node = mat.node_tree.nodes.new("ShaderNodeTexImage")
            image_node.image = img_bake
            image_node.select = True
            mat.node_tree.nodes.active = image_node
        else:
            # In the case of a tile, the node should already be created and active, so just change image path
            image_node = mat.node_tree.nodes.active
            image_node.image = tile

    # Bake it
    if pre_only: return 0
    return bake(bake_settings['bake_cat'], bake_settings['bake_type'], bake_settings, mesh_settings, False, False)



# Bake a masking pass
def bake_mask(img_mask, materials, bake_settings, mesh_settings, to_active, target, selected, pre_only=False, tile=None):
    if not tile:
        # Make sure a basic material is on every object
        mat = bpy.data.materials.new(name="bw_mask_" + bake_settings["node_name"] + "_" + mesh_settings["mesh_name"])
        bw_solution_data['materials'].append(mat)
        mat.use_nodes = True
        objs = [target]
        if selected:
            for obj in selected.objects:
                objs.append(obj)
        for obj in objs:
            check_has_material(obj, materials, mat)

    # Requires adding a pure while emit shader to all the materials first and changing target image
    for mat in materials.values():
        if not tile:
            prep_material_for_bake(mat.node_tree, 'MASK', bake_settings)

        # Add image node to material and make it selected + active
        if not to_active:
            if not tile:
                image_node = mat.node_tree.nodes.new("ShaderNodeTexImage")
                image_node.image = img_mask
                image_node.select = True
                mat.node_tree.nodes.active = image_node
            else:
                # In the case of a tile, the node should already be created and active, so just change image path
                image_node = mat.node_tree.nodes.active
                image_node.image = tile

    # Add image node to target and make it selected + active (should only be one material at this point)
    if to_active:
        if not tile:
            image_node = bpy.context.view_layer.objects.active.material_slots[0].material.node_tree.nodes.new("ShaderNodeTexImage")
            image_node.image = img_mask
            image_node.select = True
            bpy.context.view_layer.objects.active.material_slots[0].material.node_tree.nodes.active = image_node
        else:
            # In the case of a tile, the node should already be created and active, so just change image path
            image_node = bpy.context.view_layer.objects.active.material_slots[0].material.node_tree.nodes.active
            image_node.image = tile

    # Bake it
    #mesh_settings["margin"] += mesh_settings["mask_margin"]
    if pre_only: return 0
    return bake('PBR', 'MASK', bake_settings, mesh_settings, to_active, False)



# Call actual bake commands
def bake(bake_cat, bake_type, bake_settings, mesh_settings, to_active, multi):
    # Set 'real' bake pass. PBR use EMIT rather than the named pass, since those passes don't exist.
    if bake_settings['bbbk']:
        real_bake_type = 'GLOSSY'
        bake_settings['influences'] = set()
        bake_settings['influences'].add('DIRECT')
        bpy.context.scene.cycles.transparent_max_bounces = mesh_settings['alpha_bounce']
        to_active = False
    elif bake_cat in ['PBR', 'WRANG']:
        if bake_type in ['NORMAL', 'OBJNORM', 'BEVNORMNORM', 'OSL_BENTNORM']: real_bake_type = 'NORMAL'
        else: real_bake_type = 'EMIT'
    elif bake_cat == 'CORE' and bake_type == 'SMOOTHNESS':
        real_bake_type = 'ROUGHNESS'
    else:
        real_bake_type = bake_type

    # Set target of output
    target_mode = 'VERTEX_COLORS' if ('vcol' in bake_settings.keys() and bake_settings['vcol']) else 'IMAGE_TEXTURES'

    # Set threads if not default
    if bake_settings['threads'] != 0:
        bpy.context.scene.render.threads_mode = 'FIXED'
        bpy.context.scene.render.threads = bake_settings['threads']

    # Set tile sizes if not default
    if bake_settings['tiles'] in ['IMG', 'CUST']:
        if bake_settings['tiles'] == 'IMG':
            bpy.context.scene.cycles.tile_size = bake_settings["x_res"]
        else:
            bpy.context.scene.cycles.tile_size = bake_settings["tile_size"]

    if mesh_settings["margin_extend"]: bpy.context.scene.render.bake.margin_type = 'EXTEND'
    else: bpy.context.scene.render.bake.margin_type = 'ADJACENT_FACES'
    
    saveMode = 'INTERNAL'
    savePath = ''
    
    if debug: _print(">     Real bake type set to [%s], Mode [%s]" % (real_bake_type, target_mode), tag=True)

    # Update view layer to be safe
    bpy.context.view_layer.update()
    start = datetime.now()
    if 'tile_no' in bake_settings.keys():
        _print(">    -Baking %s pass [tile %s]: " % (bake_type, bake_settings['tile_no']), tag=True, wrap=False)
        del bake_settings['tile_no']
    else:
        _print(">    -Baking %s pass: " % (bake_type), tag=True, wrap=False)

    # Do the bake. Most of the properties can be passed as arguments to the operator.
    err = False
    try:
        if not multi:
            bpy.ops.object.bake(
                type=real_bake_type,
                pass_filter=bake_settings["influences"],
                margin=int(mesh_settings["margin"]),
                use_selected_to_active=to_active,
                max_ray_distance=mesh_settings["max_ray_dist"],
                cage_extrusion=mesh_settings["ray_dist"],
                cage_object=mesh_settings["cage_obj_name"],
                normal_space=bake_settings["norm_s"],
                normal_r=bake_settings["norm_r"],
                normal_g=bake_settings["norm_g"],
                normal_b=bake_settings["norm_b"],
                target=target_mode,
                save_mode=saveMode,
                filepath=savePath,
                use_clear=False,
                use_cage=mesh_settings["cage"],
            )
        else:
            bpy.context.scene.render.use_bake_multires = True
            bpy.context.scene.render.bake_margin = int(mesh_settings["margin"])
            bpy.context.scene.render.bake_type = bake_type
            bpy.context.scene.render.use_bake_clear = False
            bpy.ops.object.bake_image()
    except RuntimeError as error:
        _print("%s" % (error), tag=True)
        err = True
    else:
        _print("Completed in %s" % (str(datetime.now() - start)), tag=True)
    return err



# Handle post processes that need to be applied to the baked data to create the desired map
def bake_post(img_bake, settings, format):
    post_obj = post_scene.objects["BW_Post_%s" % (settings['bake_type'])]
    post_mat = post_obj.material_slots[0].material.node_tree.nodes
    post_src = post_mat["bw_post_input"]
    post_out = post_mat["bw_post_output"]

    post_img = bpy.data.images.new(img_bake.name + "_POST", width=settings["x_res"], height=settings["y_res"])
    post_img.colorspace_settings.name = format['img_color_space']
    post_img.colorspace_settings.is_data = img_bake.colorspace_settings.is_data
    post_img.use_generated_float = img_bake.use_generated_float

    # Switch into post scene and set up the selection state
    bpy.context.window.scene = post_scene
    bpy.ops.object.select_all(action='DESELECT')
    post_obj.select_set(True)
    bpy.context.view_layer.objects.active = post_obj

    # Set up standard images
    post_src.image = img_bake
    post_out.image = post_img

    # Generate image
    bpy.context.view_layer.update()
    err = False
    try:
        bpy.ops.object.bake(
            type="EMIT",
            save_mode='INTERNAL',
            use_clear=False,
        )
    except RuntimeError as error:
        _print(": %s" % (error), tag=True)
        err = True
    else:
        pass
    return [err, post_img]



# Bake post processing step for a vcol output
def bake_post_vcols(post_obj, post_mat, solution):
    # Add copy of object to post scene
    post_cpy = post_obj.copy()
    post_cpy.data = post_obj.data.copy()
    post_scene.collection.objects.link(post_cpy)
    # Clear materials and set it to use post material
    post_cpy.data.materials.clear()
    post_cpy.data.polygons.foreach_set('material_index', [0] * len(post_cpy.data.polygons))
    post_cpy.data.update()
    post_cpy.data.materials.append(post_mat)
    # Add vertex color slot to bake into
    vcol = post_cpy.data.color_attributes.new(post_mat.name, solution.format['vcol_type'], solution.format['vcol_domain'])
    post_cpy.data.color_attributes.active_color = vcol
    
    # Switch into scene and set up selection
    bpy.context.window.scene = post_scene
    bpy.ops.object.select_all(action='DESELECT')
    post_cpy.select_set(True)
    bpy.context.view_layer.objects.active = post_cpy

    # Generate output
    bpy.context.view_layer.update()
    _print(">   -Performing post bake processing", tag=True, wrap=False)
    err = False
    try:
        bpy.ops.object.bake(
            type="EMIT",
            target='VERTEX_COLORS',
            save_mode='INTERNAL',
        )
    except RuntimeError as error:
        _print(": %s" % (error), tag=True)
        err = True
    else:
        _print("", tag=True)
       
    return [err, post_cpy, vcol.name]
   
   
   
# Perform bake of a post processing material shader
def bake_post_material(post_col, post_alp, post_mat, post_msk, masked):
    post_obj = post_scene.objects["BW_Post"]
    post_obj.material_slots[0].material = post_mat
    post_mat_nodes = post_mat.node_tree.nodes
    post_out_col = post_mat_nodes["bw_post_output"]
    post_out_alp = post_mat_nodes["bw_post_output_alpha"]
    post_out_msk = post_mat_nodes["bw_post_output_mask"]
    output_switch = post_mat_nodes["AlphaSwitch"].inputs["AlphaSwitch"]
    mask_switch = post_mat_nodes["AlphaSwitch"].inputs["MaskSwitch"]
    use_mask = post_mat_nodes["AlphaSwitch"].inputs["UseMask"]

    # Switch into scene and set up selection
    bpy.context.window.scene = post_scene
    bpy.ops.object.select_all(action='DESELECT')
    post_obj.select_set(True)
    bpy.context.view_layer.objects.active = post_obj

    # Set output image
    post_out_col.image = post_col
    post_out_col.select = True
    post_mat_nodes.active = post_out_col
    output_switch.default_value = 0.0
    mask_switch.default_value = 0.0
    use_mask.default_value = 0.0
    if masked:
        use_mask.default_value = 1.0

    # Generate output
    bpy.context.view_layer.update()
    _print(">   -Performing post bake processing", tag=True, wrap=False)
    err = False
    try:
        bpy.ops.object.bake(
            type="EMIT",
            save_mode='INTERNAL',
            use_clear=False,
        )
    except RuntimeError as error:
        _print(": %s" % (error), tag=True)
        err = True
    else:
        post_out_col.select = False
        if post_alp is None and post_msk is None:
            _print("", tag=True)

    # Set alpha output if enabled
    if post_alp:
        post_out_alp.image = post_alp
        post_out_alp.select = True
        post_mat_nodes.active = post_out_alp
        output_switch.default_value = 1.0
        mask_switch.default_value = 0.0

        # Generate alpha output
        bpy.context.view_layer.update()
        try:
            bpy.ops.object.bake(
                type="EMIT",
                save_mode='INTERNAL',
                use_clear=False,
            )
        except RuntimeError as error:
            _print(": %s" % (error), tag=True)
            err = True
        else:
            post_out_alp.select = False
            if post_msk is None:
                _print("", tag=True)

    # Set mask output if enabled
    if post_msk:
        post_out_msk.image = post_msk
        post_out_msk.select = True
        post_mat_nodes.active = post_out_msk
        output_switch.default_value = 0.0
        mask_switch.default_value = 1.0

        # Generate mask output
        bpy.context.view_layer.update()
        try:
            bpy.ops.object.bake(
                type="EMIT",
                save_mode='INTERNAL',
                use_clear=False,
            )
        except RuntimeError as error:
            _print(": %s" % (error), tag=True)
            err = True
        else:
            post_out_msk.select = False
            _print("", tag=True)

    return err



# Combine alpha channel with color image
def alpha_pass(color, alpha, combined):
    stride = 4
    col_px = list(color.pixels)
    alp_px = list(alpha.pixels)

    # Sanity check
    if len(col_px) != len(alp_px):
        _print(": Input/Output pixel count mismatch", tag=True)
        return True

    # Write channel
    for pixel in range(int(len(col_px)/stride)):
        position = pixel * stride
        alpha_ch = position + 3
        col_px[alpha_ch] = alp_px[position] # Alpha image is greyscale, so any channel value will do

    combined.pixels = col_px[:]
    combined.update()
    return False



# Paint a margin around masked objects to the specified pixels or completely fill the empty space
def paint_margin(image, mask, margin, fill, step=12, samples=3):
    if fill: margin = -1
    if not margin: return
    start = datetime.now()
    _print(">   -Painting margin: ", tag=True, wrap=False)
    # Put this in a try block because it can explode
    try:
        mpixels, mmask, mbools, mmargins, mw, mh, mmargin_step = marginer.set_up(image, mask, step)
        margined = marginer.add_margin(mpixels, mmask, mbools, mmargins, mw, mh, mmargin_step, margin, samples)
        marginer.write_back(image, margined)
    except Exception as err:
        _print("Failed (%s)" % (str(err)), tag=True)
    else:
        _print("Completed in %s" % (str(datetime.now() - start)), tag=True)



# Move a UDIM tile into the 0-1 UV range
def focus_udim_tile(uvmap, udim, unfocus=False):
    # Calculate offset
    v_shift = int((udim - 1001) / 10)
    u_shift = int((udim - 1001) - (v_shift * 10))
    if unfocus:
        v_shift = v_shift * -1
        u_shift = u_shift * -1
    # Move all the UVs by offset
    for uv in uvmap.data.values():
        uv.uv[0] -= u_shift
        uv.uv[1] -= v_shift



# Take a UV map and split it into UDIM tiles using standard format
def uv_to_udim(solution, key, uvmap):
    tiles = solution.baketile[key]
    udim = []
    # TODO: Check fastest way to get all the uvs
    uvs = [uvmap.data[i].uv[:] for i in range(len(uvmap.data.values()))]
    for u, v in uvs:
        if int(u) == u and u > 0: u -= 1
        if int(v) == v and v > 0: v -= 1
        tile_no = (int(v) * 10) + int(u) + 1001
        if tile_no not in tiles:
            tiles[tile_no] = []
        if tile_no not in udim:
            #_print("Tile u:%s (%s) v:%s (%s) tile: %s" % (str(u), str(int(u)), str(v), str(int(v)), str(tile_no)), tag=True)
            udim.append(tile_no)
    udim.sort()
    return udim



# Fast AA pass by scaling pixels
def fast_aa(image, level):
    img_x = image.size[0]
    img_y = image.size[1]
    x_lvl = img_x * ((10 - level) * 0.1)
    y_lvl = img_y * ((10 - level) * 0.1)
    image.scale(int(x_lvl), int(y_lvl))
    image.update()
    image.scale(int(img_x), int(img_y))
    image.update()



# Copy vert colors between object copies
def copy_vert_cols(name=None, cpy_from=None, cpy_to=None):
    # Set array to size of data and copy it in
    from_cols = cpy_from.data.color_attributes[name]
    data = [0.0] * (len(from_cols.data) * 4)
    from_cols.data.foreach_get('color', data)
    # Create new color attrib and copy array into it
    cpy_to.data.color_attributes.new(name, from_cols.data_type, from_cols.domain)
    to_data = cpy_to.data.color_attributes[name].data
    to_data.foreach_set('color', data)    



# Add masks together by editing internal node group
def add_masks(masks, nodes, links):
    mask_sock = nodes['AlphaSwitch'].inputs['Mask']
    # Simplest case is one mask
    prev_adder = None
    if len(masks) == 1:
        links.new(masks[0].outputs['Mask'], mask_sock)
    # At least two masks or more
    elif len(masks) > 1:
        prev_adder = masks[0]
        for idx in range(1, len(masks)):
            # Add a mask adder node group
            mask_adder = nodes.new('ShaderNodeGroup')
            mask_adder.node_tree = internal_add_mask
            # Link prev adder to new adder and mask to adder
            links.new(prev_adder.outputs['Mask'], mask_adder.inputs['Mask1'])
            links.new(masks[idx].outputs['Mask'], mask_adder.inputs['Mask2'])
            prev_adder = mask_adder
    # Link the last adder to mask socket
    if prev_adder:
        links.new(prev_adder.outputs['Mask'], mask_sock)



# Clear an existing image to all black all transparent
def clear_image(solution):
    # Proceed if clear is set
    if solution.node.img_clear:
        output_path = solution.node.img_path
        output_name = solution.node.name_with_ext()
        output_file = os.path.join(os.path.realpath(output_path), output_name)

        # Nothing to do if image doesn't exist
        if os.path.exists(output_file):
            img = bpy.data.images.load(os.path.abspath(output_file))
            img.generated_type = 'BLANK'
            img.generated_color = (0.0, 0.0, 0.0, 0.0)
            img.generated_width = img.size[0]
            img.generated_height = img.size[1]
            img.source = 'GENERATED'
            img.filepath_raw = output_file
            img.save()
            _print(">  -Image Cleared", tag=True)



# Take a list of values and return the highest
def pixel_value(channels):
    value = 0
    for val in channels:
        if val > value:
            value = val
    return value



# Apply image format settings to scenes output settings
def apply_output_format(target_settings, format):
    # Configure output image settings
    target_settings.file_format = img_type = format["img_type"]

    # Color mode
    target_settings.color_mode = format['img_color_mode']
    # Color Depth
    if format['img_color_depth']:
        target_settings.color_depth = format['img_color_depth']
    # Compression / Quality for formats that support it
    if img_type == 'PNG':
        target_settings.compression = format['img_quality']
    elif img_type in ['JPEG', 'JPEG2000']:
        target_settings.quality = format['img_quality']
    # Codecs for formats that use them
    if img_type == 'JPEG2000':
        target_settings.jpeg2k_codec = format['img_codec']
    elif img_type in ['OPEN_EXR', 'OPEN_EXR_MULTILAYER']:
        target_settings.exr_codec = format['img_codec']
    elif img_type == 'TIFF':
        target_settings.tiff_codec = format['img_codec']
    # Additional settings used by some formats
    if img_type == 'JPEG2000':
        target_settings.use_jpeg2k_cinema_preset = format["img_jpeg2k_cinema"]
        target_settings.use_jpeg2k_cinema_48 = format["img_jpeg2k_cinema48"]
        target_settings.use_jpeg2k_ycc = format["img_jpeg2k_ycc"]
    elif img_type == 'DPX':
        target_settings.use_cineon_log = format["img_dpx_log"]



# Copy render settings from source scene to active scene
def copy_render_settings(source, target):
    # Copy all Cycles settings
    for setting in source.cycles.bl_rna.properties.keys():
        if setting not in ["rna_type", "name"]:
            setattr(target.cycles, setting, getattr(source.cycles, setting))
    for setting in source.cycles_curves.bl_rna.properties.keys():
        if setting not in ["rna_type", "name"]:
            setattr(target.cycles_curves, setting, getattr(source.cycles_curves, setting))
    # Copy SOME Render settings
    for setting in source.render.bl_rna.properties.keys():
        if setting in ["dither_intensity",
                       "filter_size",
                       "film_transparent",
                       "use_freestyle",
                       "threads",
                       "threads_mode",
                       "hair_type",
                       "hair_subdiv",
                       "use_simplify",
                       "simplify_subdivision",
                       "simplify_child_particles",
                       "simplify_subdivision_render",
                       "simplify_child_particles_render",
                       "use_simplify_smoke_highres",
                       "simplify_gpencil",
                       "simplify_gpencil_onplay",
                       "simplify_gpencil_view_fill",
                       "simplify_gpencil_remove_lines",
                       "simplify_gpencil_view_modifier",
                       "simplify_gpencil_shader_fx",
                       "simplify_gpencil_blend",
                       "simplify_gpencil_tint",
                      ]:
            setattr(target.render, setting, getattr(source.render, setting))



# Pretty much everything here is about preventing blender crashing or failing in some way that only happens
# when it runs a background bake. Perhaps it wont be needed some day, but for now trying to keep all such
# things in one place. Modifiers are applied or removed and non mesh types are converted.
def prep_object_for_bake(object, strip=False, invert=False, vcols=[False, None]):
    # Create a copy of the object to modify and put it into the mesh only scene
    if ((not object.bw_copy or object.bw_copy_frame != current_frame) and not strip and not vcols[0])\
        or ((not object.bw_strip or object.bw_strip_frame != current_frame) and strip and not vcols[0])\
        or (not object.bw_vcols and vcols[0]) or user_prop:
        copy = object.copy()
        copy.bw_copy = None
        copy.bw_strip = None
        copy.bw_vcols = None
        copy.data = object.data.copy()
        bw_solution_data['frames_objects'].append(copy)
        copy.name = ("BW_SMOD_" if strip else ("BW_VCOL_" if vcols[0] else "BW_")) + object.name
        base_scene.collection.objects.link(copy)
        bpy.context.view_layer.update()
    else:
        # Object already preped
        retcpy = (object.bw_strip if strip else (object.bw_vcols if vcols[0] else object.bw_copy))
        ret = retcpy.copy()
        ret.data = retcpy.data.copy()
        return ret

    # Can't modify object for vertex colors as vert count might change
    if vcols[0] and object == vcols[1] and not strip:
        object.bw_vcols = copy
        bw_solution_data['frames_objects'].append(copy)
        mesh_scene.collection.objects.link(copy)
        base_scene.collection.objects.unlink(copy)
        
        # Create copy of the copy for return object
        ret = copy.copy()
        ret.data = copy.data.copy()
        return ret
            
    # Objects need to be selectable and visible in the viewport in order to convert them
    copy.hide_select = False
    copy.hide_viewport = False

    # If ignoring visibility is enabled, also make the object shown for render
    if ignorevis:
        copy.hide_render = False

    # Apply active shape keys to copy so that modifiers can be applied
    if hasattr(copy.data, "shape_keys") and copy.data.shape_keys is not None:
        copy.shape_key_add(name="BW_Combined", from_mix=True)
        for skey in copy.data.shape_keys.key_blocks:
            copy.shape_key_remove(skey)

    # Make obj the only selected + active
    bpy.ops.object.select_all(action='DESELECT')
    copy.select_set(True)
    bpy.context.view_layer.objects.active = copy
    # Deal with mods
    if len(copy.modifiers):
        for mod in copy.modifiers:
            show_vp = mod.show_viewport
            if invert: show_vp = not show_vp
            if mod.show_render and (not strip or not show_vp):
                # A mod can be disabled by invalid settings, which will throw an exception when trying to apply it
                try:
                    if object.type == 'MESH':
                        bpy.ops.object.make_local()
                        bpy.ops.object.modifier_apply(modifier=mod.name)
                except:
                    _print(">    Error applying modifier '%s' to object '%s'" % (mod.name, object.name), tag=True)
                    bpy.ops.object.modifier_remove(modifier=mod.name)
            else:
                bpy.ops.object.modifier_remove(modifier=mod.name)

    # Deal with object type
    if object.type != 'MESH':
        # Apply render resolution if its set before turning into a mesh
        if object.type == 'META':
            if copy.data.render_resolution > 0:
                copy.data.resolution = copy.data.render_resolution
        else:
            if copy.data.render_resolution_u > 0:
                copy.data.resolution_u = copy.data.render_resolution_u
            if object.data.render_resolution_v > 0:
                copy.data.resolution_v = copy.data.render_resolution_v
        # Convert
        bpy.ops.object.convert(target='MESH')

        # Meta objects seem to get deleted and a new object replaces them, breaking the reference
        if object.type == 'META':
            copy = bpy.context.view_layer.objects.active

    # Link copy to original, remove from base scene and add to mesh scene
    if strip:
        object.bw_strip = copy
        object.bw_strip_frame = current_frame
    else:
        object.bw_copy = copy
        object.bw_copy_frame = current_frame
    mesh_scene.collection.objects.link(copy)
    base_scene.collection.objects.unlink(copy)
    
    # Return copy of copy
    ret = copy.copy()
    ret.data = copy.data.copy()
    return ret


# Takes a materials node tree and makes any changes necessary to perform the given bake type. A material must
# end with principled shader(s) and mix shader(s) connected to a material output in order to be set up for any
# emission node bakes.
def prep_material_for_bake(node_tree, bake_type, bake_settings):
    # Bake types with built-in passes don't require any preparation
    if not node_tree or ((bake_settings['bake_cat'] != 'PBR' or bake_type in ['NORMAL']) and bake_type not in ['MASK', 'OSL_BENTNORM']):
        return

    # Mask is a special case where an emit shader and output can just be added to any material
    elif bake_type == 'MASK':
        nodes = node_tree.nodes

        # Add white emit and a new active output
        emit = nodes.new('ShaderNodeEmission')
        emit.inputs['Color'].default_value = [1.0, 1.0, 1.0, 1.0]
        outp = nodes.new('ShaderNodeOutputMaterial')
        node_tree.links.new(emit.outputs['Emission'], outp.inputs['Surface'])
        outp.target = 'CYCLES'

        # Make all outputs not active
        for node in nodes:
            if node.type == 'OUTPUT_MATERIAL':
                node.is_active_output = False

        outp.is_active_output = True
        return


    # The material has to have a node tree and it needs at least 2 nodes to be valid
    elif len(node_tree.nodes) < 2:
        # AOV bake only requires that material has the named AOV node
        if bake_type == 'AOV' and len(node_tree.nodes):
            pass
        else:
            return

    # All other bake types use an emission shader with the value plugged into it

    # A material can have multiple output nodes. Blender seems to preference the output to use like so:
    # 1 - Target set to current Renderer and Active (picks first if multiple are set active)
    # 2 - First output with Target set to Renderer if no others with that target are set Active
    # 3 - Active output (picks first if mutliple are active)
    #
    # Strategy will be to find all valid outputs and evaluate if they can be used in the same order as above.
    # The first usable output found will be selected and also changed to be the first choice for blender.
    # Four buckets: Cycles + Active, Cycles, Generic + Active, Generic
    nodes = node_tree.nodes
    node_cycles_out_active = []
    node_cycles_out = []
    node_generic_out_active = []
    node_generic_out = []
    node_selected_output = None

    # Collect all outputs
    for node in nodes:
        if node.type == 'OUTPUT_MATERIAL':
            if node.target == 'CYCLES':
                if node.is_active_output:
                    node_cycles_out_active.append(node)
                else:
                    node_cycles_out.append(node)
            elif node.target == 'ALL':
                if node.is_active_output:
                    node_generic_out_active.append(node)
                else:
                    node_generic_out.append(node)

    # Select the first usable output using the order explained above and make sure no other outputs are set active
    node_outputs = node_cycles_out_active + node_cycles_out + node_generic_out_active + node_generic_out
    for node in node_outputs:
        input = node.inputs['Surface']
        if not node_selected_output: # and material_recursor(node):
            node_selected_output = node
            node.is_active_output = True
        else:
            node.is_active_output = False

    if not node_selected_output:
        # For an AOV bake, just add an output now if there wasn't one
        if bake_type == 'AOV':
            node_selected_output = nodes.new('ShaderNodeOutputMaterial')
            node_selected_output.is_active_output = True
        else:
            return

    # Output has been selected. An emission shader will now be built, replacing mix shaders with mix RGB
    # nodes and principled shaders with just the desired data for the bake type. Recursion used.
    if debug: _print(">      Chosen output [%s] descending tree:" % (node_selected_output.name), tag=True)
    class linkcls():
        def __init__(self):
            self.link_data = None
            self.link_list = []
        def set_links(self, link_data): self.link_data = link_data
        def new(self, lto, lfrom): self.link_list.append([self.link_data, lto, lfrom])
        def remove(self, link): self.link_data.remove(link)
        def create(self):
            for link in self.link_list:
                if debug: _print(">      Linking: %s to %s" % (link[1].node.name, link[2].node.name), tag=True)
                link[0].new(link[1], link[2])
    link_list = linkcls()
    ret = prep_material_rec(node_selected_output, None, node_selected_output.inputs['Surface'], bake_type, bake_settings, link_list)
    if bake_type != 'OSL_BENTNORM':
        link_list.create()
    return ret



# Takes a node of type OUTPUT_MATERIAL, BSDF_PRINCIPLED or MIX/ADD_SHADER. Starting with an output node it will
# recursively generate an emission shader to replace the output with the desired bake type. The link_socket
# is used for creating node tree links. Also added dealing with Custom Node Groups.
def prep_material_rec(node, socket, link_socket, bake_type, bake_settings, link_list, parent=None):
    if debug: print("%s:%s->%s:%s" % (link_socket.node.type, link_socket.name, node.name, (socket.name if socket else "None")))
    tree = node.id_data
    nodes = tree.nodes
    links = link_list
    links.set_links(tree.links)
    # Helper to get links or values for node inputs
    def link_or_value(socket):
        if socket.is_linked: return follow_input_link(socket.links[0]).from_socket, 0
        else: return socket.default_value, 1
    # Helper to either create a link or set the default value
    def map_input_or_value(proxy, proxy_input, socket):
        sock, is_val = link_or_value(socket)
        if is_val: proxy.inputs[proxy_input].default_value = sock
        else: links.link_data.new(sock, proxy.inputs[proxy_input])
    # Helper to check both inputs to mix/add are connected
    def check_both_inputs(node):
        if node.type == 'MIX_SHADER':
            input1 = 1
            input2 = 2
        else:
            input1 = 0
            input2 = 1
        recon_link = 0
        if node.inputs[input1].is_linked:
            recon_link = 1
        elif node.inputs[input2].is_linked:
            recon_link = 2
        return [(node.inputs[input1].is_linked) and (node.inputs[input2].is_linked), recon_link]
    # Cases:
    if node.type == 'OUTPUT_MATERIAL':
        # Start of shader. Create new emission shader and connect it to the output
        next = follow_input_link(link_socket.links[0])
        next_node = next.from_node
        next_sock = next.from_socket
        node_emit = nodes.new('ShaderNodeEmission')
        if bake_settings['bbbk']:
            # billboard bake needs to respect alpha by creating a separate alpha mix
            bbbk_node = nodes.new('ShaderNodeBsdfTransparent')
            bbbk_mix = nodes.new('ShaderNodeMixShader')
            bbbk_mix.inputs['Fac'].default_value = 0.0
            bake_settings['bbbk_sock'] = bbbk_mix.inputs['Fac']
            # Link it all up
            links.new(node_emit.outputs['Emission'], bbbk_mix.inputs[2])
            links.new(bbbk_node.outputs['BSDF'], bbbk_mix.inputs[1])
            sock_toout = bbbk_mix.outputs['Shader']
        else:
            sock_toout = node_emit.outputs['Emission']
        # Link output
        links.new(sock_toout, link_socket)

        # AOV bake will try to find and connect the named AOV node to the shader now and return
        if bake_type == 'AOV':
            # Helper to find named AOV
            def find_aov(named, nodes):
                first = not len(named)
                for node in nodes:
                    if node.type == 'OUTPUT_AOV':
                        if first or node.aov_name == named:
                            return node
                return None
            aov_node = find_aov(bake_settings['aov_name'], nodes)
            if aov_node:
                if bake_settings['aov_input'] == 'COL':
                    map_input_or_value(node_emit, 'Color', aov_node.inputs['Color'])
                else:
                    socket, is_val = link_or_value(aov_node.inputs['Value'])
                    if is_val: node_emit.inputs['Color'].default_value = [socket, socket, socket, socket]
                    else: links.new(socket, node_emit.inputs['Color'])
                return True
            else:
                _print(">       Error: AOV node named %s not found in material" % (bake_settings['aov_name']), tag=True)
                # Set it to black if not found?
                node_emit.inputs['Color'].default_value = [0,0,0,0]
                return False
        else:
            # Recurse
            ret = prep_material_rec(next_node, next_sock, node_emit.inputs['Color'], bake_type, bake_settings, links, parent)
        return ret

    if node.type in ['MIX_SHADER', 'ADD_SHADER']:
        # If there aren't two inputs then the node is essentially muted, so a delete with reconnect should be the answer..
        check_inputs = check_both_inputs(node)
        '''if not check_inputs[0]:
            if check_inputs[1] is not None:
                return prep_material_rec(check_inputs[1].from_node, check_inputs[1].from_socket, link_socket, bake_type, bake_settings, links, parent)
            else: return False'''
        # Mix shader needs to generate a mix RGB maintaining the same Fac input if linked
        mix_node = nodes.new('ShaderNodeMixRGB')
        mix_node.label = node.label
        mix_node.parent = node.parent
        mix_node.location = node.location
        mix_node.mute = node.mute
        mix_node.blend_type = 'MIX'
        if bake_settings['bbbk']: # duplicate everything for alpha
            bbmix_node = nodes.new('ShaderNodeMixRGB')
            bbmix_node.blend_type = 'MIX'
        if node.type == 'MIX_SHADER' and node.inputs['Fac'].is_linked:
            # Connect Fac input
            links.new(follow_input_link(node.inputs['Fac'].links[0]).from_socket, mix_node.inputs['Fac'])
            if bake_settings['bbbk']: links.new(follow_input_link(node.inputs['Fac'].links[0]).from_socket, bbmix_node.inputs['Fac'])
        else:
            if node.type == 'MIX_SHADER':
                # Set Fac value to match instead
                mix_node.inputs['Fac'].default_value = node.inputs['Fac'].default_value
                if bake_settings['bbbk']: bbmix_node.inputs['Fac'].default_value = node.inputs['Fac'].default_value
            else:
                # Add shader is a Fac of 1
                mix_node.inputs['Fac'].default_value = 1
                mix_node.blend_type = 'ADD'
                if bake_settings['bbbk']:
                    bbmix_node.inputs['Fac'].default_value = 1
                    bbmix_node.blend_type = 'ADD'
        # Connect mix output to previous socket
        links.new(mix_node.outputs['Color'], link_socket)
        if bake_settings['bbbk']: links.new(bbmix_node.outputs['Color'], bake_settings['bbbk_sock'])
        # Recurse
        if node.type == 'MIX_SHADER':
            input1 = 1
            input2 = 2
        else:
            input1 = 0
            input2 = 1
        if not check_inputs[0]:
            if check_inputs[1] == 1:
                nextA = follow_input_link(node.inputs[input1].links[0])
                nextB = False
            elif check_inputs[1] == 2:
                nextA = False
                nextB = follow_input_link(node.inputs[input2].links[0])
            else:
                return False
        else:
            nextA = follow_input_link(node.inputs[input1].links[0])
            nextB = follow_input_link(node.inputs[input2].links[0])
        if nextA:
            if bake_settings['bbbk']: bake_settings['bbbk_sock'] = bbmix_node.inputs['Color1']
            branchA = prep_material_rec(nextA.from_node, nextA.from_socket, mix_node.inputs['Color1'], bake_type, bake_settings, links, parent)
        else:
            mix_node.inputs['Color1'].default_value = [0,0,0,0]
            branchA = True
        if nextB:
            if bake_settings['bbbk']: bake_settings['bbbk_sock'] = bbmix_node.inputs['Color2']
            branchB = prep_material_rec(nextB.from_node, nextB.from_socket, mix_node.inputs['Color2'], bake_type, bake_settings, links, parent)
        else:
            mix_node.inputs['Color2'].default_value = [0,0,0,0]
            branchB = True
        return branchA and branchB

    if node.type == 'GROUP' and socket:
        # First the 'group' should be replaced with a copy along with adding a RGBA output and connecting it
        node.node_tree = node.node_tree.copy()
        if bake_settings['bbbk']:
            #node.node_tree.outputs.new('NodeSocketColor', 'BW_BBOut')
            bbsok = node.node_tree.interface.new_socket(name="BW_BBOut", in_out='OUTPUT', socket_type='NodeSocketColor')
            links.new(bake_settings['bbbk_sock'], node.outputs.get(bbsok.identifier))
        #node.node_tree.outputs.new('NodeSocketColor', 'BW_Out')
        sok = node.node_tree.interface.new_socket(name="BW_Out", in_out='OUTPUT', socket_type='NodeSocketColor')
        links.new(link_socket, node.outputs.get(sok.identifier))
        # Set links to the internal tree
        links.set_links(node.node_tree.links)
        # Entering a custom group, has some code duplication with exiting
        # Descending node tree, origin needs to be added to parent stack (using a copy to deal with branching)
        if parent:
            gparent = parent.copy()
            gparent.append(node)
        else:
            gparent = [node]
        gout = None
        for gnode in node.node_tree.nodes:
            if gnode.type == 'GROUP_OUTPUT' and gnode.is_active_output:
                gout = gnode
                break
        # Quick sanity check
        if not gout or not gout.inputs.get(socket.identifier).is_linked:
            # If there is no link, lets just connect a black color input to it
            if not gout.inputs.get(socket.identifier).is_linked:
                blk = node.node_tree.nodes.new('ShaderNodeRGB')
                blk.outputs['Color'].default_value = [0.0, 0.0, 0.0, 1.0]
                links.new(gout.inputs.get(socket.identifier), blk.outputs['Color'])
            else:
                if debug: _print(">       Error: Group node active output not found", tag=True)
            return True
        # Follow the next node to be considered, use the added RGBA socket as link_sock (should be 2nd last)
        next = follow_input_link(gout.inputs.get(socket.identifier).links[0])
        if bake_settings['bbbk']: bake_settings['bbbk_sock'] = gout.inputs.get(bbsok.identifier)
        return prep_material_rec(next.from_node, next.from_socket, gout.inputs.get(sok.identifier), bake_type, bake_settings, links, gparent)

    if node.type == 'GROUP_INPUT' and socket and parent:
        # Exiting a custom group, has some code duplication with entering
        # Acceding node tree, pop origin off the parent stack (using a copy to deal with branching)
        gparent = parent.copy()
        gout = gparent.pop()
        # First add a new RGBA input to the parent and connect it to the previous thing (should be 2nd last on inside)
        if bake_settings['bbbk']:
            #gout.node_tree.inputs.new('NodeSocketColor', 'BW_BBIn')
            bbsok = gout.node_tree.interface.new_socket(name="BW_BBIn", in_out='INPUT', socket_type='NodeSocketColor')
            links.new(bake_settings['bbbk_sock'], node.outputs.get(bbsok.identifier))
        #gout.node_tree.inputs.new('NodeSocketColor', 'BW_In')
        sok = gout.node_tree.interface.new_socket(name="BW_In", in_out='INPUT', socket_type='NodeSocketColor')
        links.new(link_socket, node.outputs.get(sok.identifier))
        # Set links to the external tree
        links.set_links(gout.id_data.links)
        # Quick sanity check
        if not gout or not gout.inputs.get(socket.identifier).is_linked:
            # If there is no link, lets just set socket to black and return
            if not gout.inputs.get(socket.identifier).is_linked:
                gout.inputs.get(sok.identifier).default_value = [0.0, 0.0, 0.0, 1.0]
            else:
                if debug: _print(">       Error: Group node input socket not linked", tag=True)
            return True
        # Return the next node to be considered, using the added RGBA external socket as the link_sock (should be last)
        next = follow_input_link(gout.inputs.get(socket.identifier).links[0])
        if bake_settings['bbbk']: bake_settings['bbbk_sock'] = gout.inputs.get(bbsok.identifier)
        return prep_material_rec(next.from_node, next.from_socket, gout.inputs.get(sok.identifier), bake_type, bake_settings, links, gparent)

    # All of the shader types that aren't really supported. Instead of failing, they will be converted to Principled using some assumptions.
    if node.type in ['BSDF_DIFFUSE', 'BSDF_GLOSSY', 'BSDF_GLASS', 'BSDF_REFRACTION', 'BSDF_TRANSLUCENT', 'BSDF_TRANSPARENT', 'BSDF_ANISOTROPIC', 'SUBSURFACE_SCATTERING', 'EMISSION', 'HOLDOUT', 'BSDF_HAIR', 'BSDF_HAIR_PRINCIPLED', 'PRINCIPLED_VOLUME', 'BSDF_TOON', 'BSDF_VELVET', 'VOLUME_ABSORPTION', 'VOLUME_SCATTER']:
        proxy = nodes.new('ShaderNodeBsdfPrincipled')
        proxy.parent = node.parent
        proxy.location = node.location
        proxy.inputs['Base Color'].default_value = [0,0,0,0]
        #links.new(proxy.outputs[0], link_socket)
        # Almost all of these have a color input that can be mapped
        if node.type != 'HOLDOUT':
            if node.type == 'SUBSURFACE_SCATTERING':
                map_input_or_value(proxy, 'Subsurface Color', node.inputs['Color'])
            elif node.type == 'EMISSION':
                map_input_or_value(proxy, 'Emission Color', node.inputs['Color'])
            else:
                map_input_or_value(proxy, 'Base Color', node.inputs['Color'])
        # Many also have a roughness value
        if node.type in ['BSDF_GLOSSY', 'BSDF_DIFFUSE', 'BSDF_GLASS', 'BSDF_REFRACTION', 'BSDF_ANISOTROPIC', 'BSDF_HAIR_PRINCIPLED']:
            map_input_or_value(proxy, 'Roughness', node.inputs['Roughness'])
        # A bunch can have a normal input mapped
        if node.type in ['BSDF_GLOSSY', 'BSDF_DIFFUSE', 'BSDF_GLASS', 'BSDF_REFRACTION', 'SUBSURFACE_SCATTERING', 'BSDF_ANISOTROPIC', 'BSDF_TRANSLUCENT', 'BSDF_TOON', 'BSDF_VELVET']:
            map_input_or_value(proxy, 'Normal', node.inputs['Normal'])
        # Not really any more common properties, but still a few that can be mapped
        if node.type in ['BSDF_GLASS', 'BSDF_REFRACTION', 'BSDF_HAIR_PRINCIPLED']:
            map_input_or_value(proxy, 'IOR', node.inputs['IOR'])
        if node.type == 'EMISSION':
            map_input_or_value(proxy, 'Emission Strength', node.inputs['Strength'])
        if node.type == 'SUBSURFACE_SCATTERING':
            map_input_or_value(proxy, 'Subsurface Radius', node.inputs['Radius'])
        if node.type in ['BSDF_ANISOTROPIC', 'PRINCIPLED_VOLUME', 'VOLUME_SCATTER']:
            map_input_or_value(proxy, 'Anisotropic', node.inputs['Anisotropy'])
        if node.type == 'BSDF_ANISOTROPIC':
            map_input_or_value(proxy, 'Anisotropic Rotation', node.inputs['Rotation'])
        if node.type in ['BSDF_HAIR', 'BSDF_ANISOTROPIC']:
            map_input_or_value(proxy, 'Tangent', node.inputs['Tangent'])
        # Work out a metalness based on some nodes
        if node.type in ['BSDF_DIFFUSE', 'BSDF_GLOSSY', 'BSDF_TOON', 'BSDF_ANISOTROPIC']:
            if node.type == 'BSDF_TOON':
                if node.component == 'DIFFUSE': proxy.inputs['Metallic'].default_value = 0.0
                else: proxy.inputs['Metallic'].default_value = 1.0
            elif node.type == 'BSDF_DIFFUSE': proxy.inputs['Metallic'].default_value = 0.0
            elif node.type == 'BSDF_GLOSSY': proxy.inputs['Metallic'].default_value = 1.0
            elif node.type == 'BSDF_ANISOTROPIC': proxy.inputs['Metallic'].default_value = 1.0
        # Clear coat
        if node.type == 'BSDF_HAIR_PRINCIPLED':
            map_input_or_value(proxy, 'Clearcoat', node.inputs['Coat'])
        if node.type == 'PRINCIPLED_VOLUME':
            map_input_or_value(proxy, 'Emission', node.inputs['Emission Color'])
            map_input_or_value(proxy, 'Emission Strength', node.inputs['Emission Strength'])
        # Alpha
        if node.type == 'BSDF_TRANSPARENT':
            proxy.inputs['Alpha'].default_value = 0.0
        return prep_material_rec(proxy, proxy.outputs[0], link_socket, bake_type, bake_settings, links, parent)

    if node.type == 'BSDF_PRINCIPLED':
        # End of a branch as far as the prep is concerned. Either link the desired bake value or set the
        # previous socket to the value if it isn't linked
        if bake_type == 'ALBEDO':
            bake_input = node.inputs['Base Color']
        elif bake_type == 'METALLIC':
            bake_input = node.inputs['Metallic']
        elif bake_type in ['ROUGHNESS' ,'SMOOTHNESS']:
            bake_input = node.inputs['Roughness']    
        elif bake_type == 'IOR':
            bake_input = node.inputs['IOR']
        elif bake_type == 'ALPHA':
            bake_input = node.inputs['Alpha']
        
        elif bake_type in ['TEXNORM', 'OBJNORM', 'BBNORM', 'OSL_BENTNORM']:
            bake_input = node.inputs['Normal']
        elif bake_type == 'COATNORM':
            bake_input = node.inputs['Coat Normal']
        
        elif bake_type == 'EMIT':
            bake_input = node.inputs['Emission Color']
        elif bake_type == 'EMITSTR':
            bake_input = node.inputs['Emission Strength']
        
        elif bake_type == 'SUBWEIGHT':
            bake_input = node.inputs['Subsurface Weight']
        elif bake_type == 'SUBRADIUS':
            bake_input = node.inputs['Subsurface Radius']
        elif bake_type == 'SUBSCALE':
            bake_input = node.inputs['Subsurface Scale']
        elif bake_type == 'SUBIOR':
            bake_input = node.inputs['Subsurface IOR']
        elif bake_type == 'SUBANISO':
            bake_input = node.inputs['Subsurface Anisotropy']
        
        elif bake_type == 'SPECIOR':
            bake_input = node.inputs['Specular IOR Level']
        elif bake_type == 'SPECTINT':
            bake_input = node.inputs['Specular Tint']
        elif bake_type == 'SPECANISO':
            bake_input = node.inputs['Anisotropic']
        elif bake_type == 'SPECANISOROT':
            bake_input = node.inputs['Anisotropic Rotation']
        elif bake_type == 'SPECTAN':
            bake_input = node.inputs['Tangent']
        
        elif bake_type == 'TRANSMISSION':
            bake_input = node.inputs['Transmission Weight']
            
        elif bake_type == 'COATWEIGHT':
            bake_input = node.inputs['Coat Weight']
        elif bake_type == 'COATROUGH':
            bake_input = node.inputs['Coat Roughness']
        elif bake_type == 'COATIOR':
            bake_input = node.inputs['Coat IOR']
        elif bake_type == 'COATTINT':
            bake_input = node.inputs['Coat Tint']
        
        elif bake_type == 'SHEENWIGHT':
            bake_input = node.inputs['Sheen Weight']
        elif bake_type == 'SHEENROUGH':
            bake_input = node.inputs['Sheen Roughness']
        elif bake_type == 'SHEENTINT':
            bake_input = node.inputs['Sheen Tint']
        
        else:
            bake_input = None

        if debug: _print(">       Reached branch end, ", tag=True, wrap=False)

        if bake_input:
            if bake_settings['bbbk']:
                # Connect alpha to billboard bake alpha mix nodes
                bbbk_input = node.inputs['Alpha']
                if bbbk_input.is_linked:
                    links.new(bbbk_input.links[0].from_socket, bake_settings['bbbk_sock'])
                else:
                    # Create a color node to use as input
                    bbcolornode = nodes.new('ShaderNodeRGB')
                    bbcolorsoct = bbcolornode.outputs["Color"]
                    links.new(bake_settings['bbbk_sock'], bbcolorsoct)
                    bbcolorsoct.default_value[0] = bbbk_input.default_value
                    bbcolorsoct.default_value[1] = bbbk_input.default_value
                    bbcolorsoct.default_value[2] = bbbk_input.default_value
                    bbcolorsoct.default_value[3] = 1.0
            if bake_type in ['TEXNORM', 'CLEARNORM', 'BBNORM']:
                # Normal map types need an extra step, plus configuration of space and swizzle
                # Add normal mapping node group
                normgrp = nodes.new('ShaderNodeGroup')
                if bake_type == 'BBNORM':
                    normgrp.node_tree = billboard_norm.copy()
                    normgrp.inputs['Rotation'].default_value = bake_settings['bb_rot']
                else:
                    normgrp.node_tree = normals_group.copy()
                normnod = normgrp.node_tree.nodes
                normlnk = normgrp.node_tree.links
                # Link it
                links.new(normgrp.outputs["Color"], link_socket)
                link_socket = normgrp.inputs["Normal"]
                # Configure it
                if bake_type == 'BBNORM':
                    spacenod = normnod["bw_norm"]
                else:
                    normlnk.new(normnod["bw_inputnorm"].outputs["Normal"], normnod["bw_normal_input"].inputs[0])
                    spacenod = normnod[bake_settings["norm_s"]]
                swizzleR = spacenod.outputs[bake_settings["norm_r"]]
                swizzleG = spacenod.outputs[bake_settings["norm_g"]]
                swizzleB = spacenod.outputs[bake_settings["norm_b"]]
                normoutp = normnod["bw_normal_xyz"]
                normlnk.new(swizzleR, normoutp.inputs["X"])
                normlnk.new(swizzleG, normoutp.inputs["Y"])
                normlnk.new(swizzleB, normoutp.inputs["Z"])
            if bake_type in ['OSL_BENTNORM']:
                # Add bent normals group to material and set values
                bentnormgrp = nodes.new('ShaderNodeGroup')
                bentnormgrp.node_tree = bent_norm_group
                bentnormgrp.inputs['Distance'].default_value = bake_settings['osl_bentnorm_dist']
                bentnormgrp.inputs['Samples'].default_value = bake_settings['osl_bentnorm_samp']
                # Link it
                if bake_input.is_linked:
                    if debug: _print("Normals Link found, [%s] will be connected" % (bake_input.links[0].from_socket.name), tag=True)
                    tree.links.new(bake_input.links[0].from_socket, bentnormgrp.inputs['Normal'])
                else: # For Bent normals just connect object normals instead
                    if debug: _print("Nomrals not linked, objects normals used instead", tag=True)
                    objgeo = nodes.new('ShaderNodeNewGeometry')
                    tree.links.new(objgeo.outputs['Normal'], bentnormgrp.inputs['Normal'])
                tree.links.new(bentnormgrp.outputs["Bent Normal"], bake_input)
                return True
            if bake_input.is_linked:
                if debug: _print("Link found, [%s] will be connected" % (bake_input.links[0].from_socket.name), tag=True)
                if bake_type == 'OBJNORM':
                    # Remove any texture influence to normals
                    links.remove(bake_input.links[0])
                else:
                    # Connect the linked node up to the emit shader
                    links.new(bake_input.links[0].from_socket, link_socket)
            else:
                if debug: _print("Not linked, value will be copied", tag=True)
                if link_socket.is_linked:
                    links.remove(link_socket.links[0])
                # Copy the value into the socket instead
                if bake_input.type == 'RGBA':
                    link_socket.default_value = bake_input.default_value
                elif bake_input.type == 'VECTOR':
                    link_socket.default_value[0] = bake_input.default_value[0]
                    link_socket.default_value[1] = bake_input.default_value[1]
                    link_socket.default_value[2] = bake_input.default_value[2]
                    #link_socket.default_value[3] = 1.0
                else:
                    # Create a color node to use as input
                    colornode = nodes.new('ShaderNodeRGB')
                    colorsoct = colornode.outputs["Color"]
                    links.new(link_socket, colorsoct)
                    colorsoct.default_value[0] = bake_input.default_value
                    colorsoct.default_value[1] = bake_input.default_value
                    colorsoct.default_value[2] = bake_input.default_value
                    colorsoct.default_value[3] = 1.0
            # Branch completed
            return True

    # Something went wrong
    if debug: _print(">       Error: Reached unsupported node type", tag=True)
    return False



# Make sure object has at least a generic material
def check_has_material(object, materials, mat):
    # A material is generally required to direct baking output, so add a generic one if none is present
    add_mat = True
    if len(object.material_slots):
        for slot in object.material_slots:
            if slot.material:
                add_mat = False
                break
    if add_mat:
        if materials and mat.name not in materials:
            materials[mat.name] = mat
        object.data.materials.append(mat)



# Replace all materials in scene with a shader for bake type
def replace_materials_for_shader_bake(scene, bake_settings, mesh_settings):
    bake_type = bake_settings['bake_type']
    bake_cat = bake_settings['bake_cat']
    override = mesh_settings['material_replace']
    override_mat = mesh_settings['material_override']
    for obj in scene.objects:
        # First strip existing materials unless they are needed
        if bake_type not in ['MATID', 'OSL_BENTNORM']:
            obj.data.materials.clear()
            obj.data.polygons.foreach_set('material_index', [0] * len(obj.data.polygons))
            obj.data.update()
        # Do material override if it makes sense
        if bake_cat != 'WRANG' and override and override_mat:
            obj.data.materials.append(override_mat)
        # Add correct shader for bake type
        elif bake_type == 'BEVMASK':
            obj.data.materials.append(bevmask_shader)
        elif bake_type == 'BEVNORMEMIT':
            obj.data.materials.append(bevnormemit_shader)
        elif bake_type == 'BEVNORMNORM':
            obj.data.materials.append(bevnormnorm_shader)
        elif bake_type == 'CAVITY':
            obj.data.materials.append(cavity_shader)
        elif bake_type == 'CURVATURE':
            obj.data.materials.append(curvature_shader)
        elif bake_type == 'ISLANDID':
            obj.data.materials.append(islandid_shader)
        elif bake_type == 'OBJCOL':
            obj.data.materials.append(objcol_shader)
        elif bake_type == 'WORLDPOS':
            obj.data.materials.append(worldpos_shader)
        elif bake_type == 'THICKNESS':
            obj.data.materials.append(thickness_shader)
        elif bake_type == 'VERTCOL':
            obj.data.materials.append(vertcol_shader)
        elif bake_type == 'OSL_CURV':
            obj.data.materials.append(osl_curvature)
        elif bake_type == 'MASKPASS':
            obj.data.materials.append(mask_pass_shader)



# Consider all materials in scene and create scene only copies
def make_materials_unique_to_scene(scene, suffix, bake_settings):
    # Go through all the materials on every object
    materials = {}
    bake_type = bake_settings['bake_type']
    bake_cat = bake_settings['bake_cat']

    for obj in scene.objects:
        if len(obj.material_slots):
            for slot in obj.material_slots:
                if slot.material:
                    # If its a new material, create a copy (adding suffix) and add the pair to the list
                    if slot.material.name not in materials:
                        copy = slot.material.copy()
                        copy.name = slot.material.name + suffix
                        materials[slot.material.name] = copy
                        replace = copy
                    else:
                        replace = materials[slot.material.name]
                    # Replace with copy
                    slot.material = replace

    # For shader bakes there should now be only one material and it will be configured now
    if bake_cat == 'WRANG':
        mat_key = materials.keys()
        if len(mat_key) > 1 and bake_type != 'MATID': _print(">   Sanity Error: Doing shader bake, but objects had multiple materials", tag=True)
        for key in mat_key:
            nodes = materials[key].node_tree.nodes

        if bake_type in ['BEVMASK', 'BEVNORMEMIT', 'BEVNORMNORM']:
            bevel = nodes["bw_bevel"]
            bevel.inputs["Radius"].default_value = bake_settings["bev_rad"]
            bevel.samples = bake_settings["bev_samp"]
            if bake_type == 'BEVNORMEMIT':
                # Configure normal settings
                bevel_norm = nodes["BW_Normals.Bevel"]
                normnod = bevel_norm.node_tree.nodes
                normlnk = bevel_norm.node_tree.links
                spacenod = normnod[bake_settings["norm_s"]]
                swizzleR = spacenod.outputs[bake_settings["norm_r"]]
                swizzleG = spacenod.outputs[bake_settings["norm_g"]]
                swizzleB = spacenod.outputs[bake_settings["norm_b"]]
                normoutp = normnod["bw_normal_xyz"]
                normlnk.new(swizzleR, normoutp.inputs["X"])
                normlnk.new(swizzleG, normoutp.inputs["Y"])
                normlnk.new(swizzleB, normoutp.inputs["Z"])
        elif bake_type in ['CAVITY', 'THICKNESS']:
            node_ao = nodes["bw_ao"]
            node_ao.inputs["Distance"].default_value = bake_settings["cavity_dist"]
            node_ao.samples = bake_settings["cavity_samp"]
            if bake_type == 'CAVITY':
                node_gamma = nodes["bw_ao_cavity_gamma"]
                node_ao.inside = bake_settings["cavity_edges"]
                node_gamma.inputs["Gamma"].default_value = bake_settings["cavity_gamma"]
        elif bake_type == 'CURVATURE':
            con_vex = nodes["bw_convex_range"]
            con_cav = nodes["bw_concave_range"]
            midv = bake_settings["curv_mid"]
            cavv = bake_settings["curv_cav"]
            vexv = bake_settings["curv_vex"]
            con_vex.color_ramp.elements[0].color = [midv, midv, midv, 1.0]
            con_vex.color_ramp.elements[1].color = [vexv, vexv, vexv, 1.0]
            con_vex.color_ramp.elements[1].position = bake_settings["curv_vex_max"]
            con_cav.color_ramp.elements[1].color = [midv, midv, midv, 1.0]
            con_cav.color_ramp.elements[0].color = [cavv, cavv, cavv, 1.0]
            con_cav.color_ramp.elements[0].position = bake_settings["curv_cav_min"]
        elif bake_type == 'OSL_CURV':
            osl_scr = nodes["bw_osl_script"]
            osl_scr.inputs["Distance"].default_value = bake_settings["osl_curv_dist"]
            osl_scr.inputs["Samples"].default_value = bake_settings["osl_curv_samp"]
            osl_scr.inputs["contrast"].default_value = bake_settings["osl_curv_cont"]
            if bake_settings["osl_curv_srgb"]:
                osl_scr.inputs["srgb"].default_value = 1
            else:
                osl_scr.inputs["srgb"].default_value = 0
        elif bake_type == 'OSL_HEIGHT':
            osl_scr = nodes["bw_osl_script"]
            osl_scr.inputs["Distance"].default_value = bake_settings["osl_height_dist"]
            osl_scr.inputs["Midlevel"].default_value = bake_settings["osl_height_midl"]
            osl_scr.inputs["iterations"].default_value = bake_settings["osl_height_samp"]
            osl_scr.inputs["Voidcolor"].default_value = bake_settings["osl_height_void"]
        elif bake_type == 'VERTCOL':
            verts = nodes["bw_vertex_col"]
            verts.layer_name = bake_settings["vert_col"]
        elif bake_type == 'MATID':
            # This one is different to the rest as it must replace all the existing materials with a unique per material color output
            col_used = []
            for name, mat in materials.items():
                ntree = materials[name].node_tree
                ntree.nodes.clear()
                outp = ntree.nodes.new('ShaderNodeOutputMaterial')
                if bake_settings["use_material_vpcolor"]:
                    # Use materials viewport color
                    colg = ntree.nodes.new('ShaderNodeEmission')
                    colg.inputs["Color"].default_value = materials[name].diffuse_color
                else:
                    # Generate a random color using name as seed for repeatability
                    random.seed(a=name)
                    col = round(random.random(), 2)
                    while col in col_used:
                        round(random.random(), 2)
                    col_used.append(col)
                    # Clear all nodes and place the custom group connected to a output with the above value set
                    colg = ntree.nodes.new('ShaderNodeGroup')
                    colg.node_tree = materialid_group.copy()
                    colg.inputs["Random"].default_value = col
                ntree.links.new(colg.outputs["Emission"], outp.inputs["Surface"])
        elif bake_type in ['UV_ISLAND', 'FACE_SET']:
            # Helper function for finding the data
            import bmesh
            from collections import defaultdict
            def find_uv_islands(bm, uv_layer):
                # Step 1: Set up data structures to make relating vertexes, faces, and islands to each other easier.
                uv_islands = [] # Islands are just lists of the faces in the island
                face_to_island = {} # key is face IDX, value is Island IDX
                vertex_to_faces = defaultdict(set)

                # mapping UV vertices to the faces they belong to
                for face in bm.faces:
                    for loop in face.loops:
                        uv_vert = loop[uv_layer].uv[:]
                        vertex_to_faces[uv_vert].add(face)  # Key is the uv_vert, value is a list of the faces that share it

                # Step 2: Find connected faces to form islands
                for face in bm.faces:
                    if face.index in face_to_island:
                        continue  # Skip if face is already assigned to an island
                    
                    # Because of the above short circuit after this point we can assume this is actually a per-island 
                    # loop not a per-face loop. We just have to set up per-island variables.
                    
                    # Start a new UV island
                    new_island = set() # list of faces that compose the island
                    stack = [face]     # Initialize the working stack, used instead of doing recursion, I'm old fasioned and don't trust recursion.

                    while stack:
                        current_face = stack.pop()
                        if current_face.index in face_to_island:
                            continue  # Already processed this face, skip it.
                        
                        # Assign the current face to the new island
                        new_island.add(current_face)
                        face_to_island[current_face.index] = len(uv_islands)

                        # Look for neighboring faces that share UV vertices  <----- possibly a good point to add multithreading? 
                        for loop in current_face.loops:
                            uv_vert = loop[uv_layer].uv[:]
                            neighboring_faces = vertex_to_faces[uv_vert]

                            for neighbor in neighboring_faces:
                                if neighbor.index not in face_to_island:
                                    stack.append(neighbor) # Faux "Recurse" - put the neighbor on the stack so it gets added to the list of faces to process

                    # Add the new island to the list of UV islands
                    uv_islands.append(list(new_island))
                return uv_islands
            
            # Face Set Helper
            def find_face_sets(bm, set_layer):
                face_dic = {}
                for face in bm.faces:
                    if face[set_layer] in face_dic.keys():
                        face_dic[face[set_layer]].append(face)
                    else:
                        face_dic[face[set_layer]] = []
                face_lists = []
                for sets in face_dic.keys():
                    face_lists.append(face_dic[sets])
                return face_lists                
            
            # Go through each object and assign a material with a random color for each island or face set the object has
            col_used = []
            for obj in scene.objects:
                # BMesh from obj to search for data
                bm = bmesh.new()
                bm.from_mesh(obj.data)
                # Find UV islands manually
                if bake_type == 'UV_ISLAND':
                    uv_islands = find_uv_islands(bm, bm.loops.layers.uv.active)
                else:
                    uv_islands = find_face_sets(bm, bm.faces.layers.int.get(".sculpt_face_set"))
                
                # Add a random color material for each island
                random.seed(a=obj.name)
                for island in uv_islands:
                    mat = color_random.copy()
                    materials[mat.name] = mat
                    obj.data.materials.append(mat)
                    col = round(random.random(), 2)
                    while col in col_used:
                        col = round(random.random(), 2)
                    col_used.append(col)
                    mat.node_tree.nodes["Group"].inputs["Random"].default_value = col
                
                # Now assign the correct material to each face in the BMesh
                matslot = 0
                for island in uv_islands:
                    for face in island:
                        face.material_index = matslot
                    matslot += 1
                
                # Apply changes back to object and free BMesh
                bm.to_mesh(obj.data)
                bm.free()

    # Return the dict
    return materials
    

# Free up memory by removing created data
def free_data(freeImages=True):
    has_refs = []
    if debug: _print("> Clearing data created for previous bake(s)", tag=True)
    # Scenes first
    while len(bw_solution_data['scenes']):
        obj = bw_solution_data['scenes'].pop()
        # Unlink any objects in the base collection
        for obx in obj.collection.objects:
            obj.collection.objects.unlink(obx)
        # Remove the scene
        if obj.name in bpy.data.scenes.keys(): bpy.data.scenes.remove(obj)
    # Collections
    while len(bw_solution_data['collections']):
        obj = bw_solution_data['collections'].pop()
        # Unlink any objects in the base collection
        for obx in obj.objects:
            obj.objects.unlink(obx)
        # Remove collection
        if obj.name in bpy.data.collections.keys() and not obj.users: bpy.data.collections.remove(obj)
        else:
            has_refs.append(['COL', obj])
            if debug: _print("> Collection: %s removal postponed with %s users" % (obj.name, obj.users), tag=True)
    # Objects
    while len(bw_solution_data['objects']):
        obj = bw_solution_data['objects'].pop()
        # Unlink object from any collections
        for col in bpy.data.collections:
            if obj.name in col.objects.keys():
                col.objects.unlink(obj)
        # Unlink object from any scenes
        for scn in bpy.data.scenes:
            if obj.name in scn.collection.objects.keys():
                scn.collection.objects.unlink(obj)
        # Clear all materials from object
        obj.data.materials.clear()
        # Remove object
        if obj.name in bpy.data.objects.keys() and not obj.users: bpy.data.objects.remove(obj)
        else:
            has_refs.append(['OBJ', obj])
            if debug: _print("> Object: %s removal postponed with %s users" % (obj.name, obj.users), tag=True)
    # Frames Objects (objects only removed if doing a frame range, between frames)
    while len(bw_solution_data['frames_objects']) and freeImages:
        obj = bw_solution_data['frames_objects'].pop()
        # Unlink object from any collections
        for col in bpy.data.collections:
            if obj.name in col.objects.keys():
                col.objects.unlink(obj)
        # Unlink object from any scenes
        for scn in bpy.data.scenes:
            if obj.name in scn.collection.objects.keys():
                scn.collection.objects.unlink(obj)
        # Clear all materials from object
        obj.data.materials.clear()
        # Remove object
        if obj.name in bpy.data.objects.keys() and not obj.users: bpy.data.objects.remove(obj)
        else:
            has_refs.append(['OBJ', obj])
            if debug: _print("> Object: %s removal postponed with %s users" % (obj.name, obj.users), tag=True)
    # Materials
    while len(bw_solution_data['materials']):
        obj = bw_solution_data['materials'].pop()
        if obj.name in bpy.data.materials.keys() and not obj.users: bpy.data.materials.remove(obj)
        else:
            has_refs.append(['MAT', obj])
            if debug: _print("> Material: %s removal postponed with %s users" % (obj.name, obj.users), tag=True)
    # Images
    while len(bw_solution_data['images']) and freeImages:
        obj = bw_solution_data['images'].pop()
        if obj.name in bpy.data.images.keys() and not obj.users:
            imgFile = None
            if obj.source == 'FILE' and obj.filepath and obj.filepath.find("BW_T") > -1:
                imgFile = obj.filepath
            bpy.data.images.remove(obj)
            if imgFile: os.remove(imgFile)
        else:
            has_refs.append(['IMG', obj])
            if debug: _print("> Image: %s removal postponed with %s users" % (obj.name, obj.users), tag=True)
    # Data postponed due to having references last run
    while len(bw_solution_data['had_refs']):
        obj = bw_solution_data['had_refs'].pop()
        if obj[0]   == 'COL': dataBlk = bpy.data.collections
        elif obj[0] == 'OBJ': dataBlk = bpy.data.objects
        elif obj[0] == 'MAT': dataBlk = bpy.data.materials
        elif obj[0] == 'IMG': dataBlk = bpy.data.images
        else:
            if debug: _print("> Unknown data type in postponed data blocks: %s for %s" % (obj[0], obj[1].name), tag=True)
            continue
        # Try to remove it again
        if obj[1].name in dataBlk.keys() and not obj[1].users: dataBlk.remove(obj[1])
        else:
            has_refs.append([obj[0], obj[1]])
            if debug: _print("> Postponed data block: %s removal postponed AGAIN with %s users" % (obj[1].name, obj[1].users), tag=True)
    # Clear any zero ref count data blocks
    #bpy.ops.outliner.orphans_purge(do_recursive=True)
    # Add postponed data into data list
    bw_solution_data['had_refs'] = has_refs


# Pack all textures
def pack_data():
    if debug: _print("> Packing all textures into temporary blend file", tag=True)
    for img in bpy.data.images:
        if img.source != 'GENERATED' and not img.packed_file and len(img.packed_files.values()) == 0:
            try:
                img.pack()
            except:
                _print("> Unable to pack %s" % (img.name), tag=True)



# It's a me, main
def main():
    import sys       # to get command line args
    import argparse  # to parse options for us and print a nice help message

    # get the args passed to blender after "--", all of which are ignored by
    # blender so scripts may receive their own arguments
    argv = sys.argv

    if "--" not in argv:
        argv = []  # as if no args are passed
    else:
        argv = argv[argv.index("--") + 1:]  # get all args after "--"

    # When --help or no args are given, print this help
    usage_text = (
        "This script is used internally by Bake Wrangler add-on."
    )

    parser = argparse.ArgumentParser(description=usage_text)

    # Possible types are: string, int, long, choice, float and complex.
    parser.add_argument(
        "-t", "--tree", dest="tree", type=str, required=True,
        help="Name of bakery tree where the starting node is",
    )
    parser.add_argument(
        "-n", "--node", dest="node", type=str, required=True,
        help="Name of bakery node to start process from",
    )
    parser.add_argument(
        "-o", "--sock", dest="sock", type=int, required=False,
        help="Socket for single suffix output",
    )
    parser.add_argument(
        "-v", "--ignorevis", dest="ignorevis", type=int, required=False,
        help="Treat all selected objects as visibile",
    )
    parser.add_argument(
        "-d", "--debug", dest="debug", type=int, required=False,
        help="Enable debug messages",
    )
    parser.add_argument(
        "-r", "--rend_dev", dest="rend_dev", type=str, required=False,
        help="Cycles render device type",
    )
    parser.add_argument(
        "-u", "--rend_use", dest="rend_use", type=str, required=False,
        help="Cycles enabled render devices",
    )
    parser.add_argument(
        "--solitr", dest="solution_restart", type=str, required=False,
        help="Iterations of solutions before retry",
    )
    parser.add_argument(
        "--frameitr", dest="frames_restart", type=str, required=False,
        help="Iterations of frames before retry",
    )
    parser.add_argument(
        "--batchitr", dest="batch_restart", type=str, required=False,
        help="Iterations of batches before retry",
    )
    
    args = parser.parse_args(argv)

    if not argv:
        parser.print_help()
        return

    if not args.tree or not args.node:
        print("Error: Bake Wrangler baker required arguments not found")
        return
    
    if not args.sock:
        args.sock = -1

    global ignorevis
    if args.ignorevis:
        ignorevis = bool(args.ignorevis)
    else:
        ignorevis = False

    global debug
    if args.debug:
        debug = bool(args.debug)
    else:
        debug = False

    global images_saved
    images_saved = []

    global pickled_verts
    pickled_verts = []
    
    global solution_restart
    solution_restart = 0
    if args.solution_restart:
        solution_restart = int(args.solution_restart)
    global frames_restart
    frames_restart = 0
    if args.frames_restart:
        frames_restart = int(args.frames_restart)
    global batch_restart
    batch_restart = 0
    if args.batch_restart:
        batch_restart = int(args.batch_restart)
    
    # Track created data
    global bw_solution_data
    bw_solution_data = {'scenes': [],
                        'collections': [],
                        'objects': [],
                        'frames_objects': [],
                        'materials': [],
                        'images': [],
                        'had_refs': [],
                        }

    # Reconfigure cycles render devices if args supplied
    if args.rend_dev and args.rend_use:
        bpy.context.preferences.addons["cycles"].preferences.get_devices()
        bpy.context.preferences.addons["cycles"].preferences.compute_device_type = args.rend_dev
        itr = 0
        for char in args.rend_use:
            bpy.context.preferences.addons["cycles"].preferences.devices[itr].use = int(char)
            itr += 1

    # Make sure the node classes are registered
    try:
        node_tree.register()
    except:
        print("Info: Bake Wrangler nodes already registered")
    else:
        print("Info: Bake Wrangler nodes registered")

    # Make sure to be in object mode before doing anything
    if bpy.context.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')

    # Load shaders and scenes
    bake_scene_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "resources", "BakeWrangler_Scene.blend")
    with bpy.data.libraries.load(bake_scene_path, link=False, relative=False) as (file_from, file_to):
        file_to.materials.append("BW_Bevel_Mask")
        file_to.materials.append("BW_Bevel_Normals_Emit")
        file_to.materials.append("BW_Bevel_Normals_Norm")
        file_to.materials.append("BW_Cavity_Map")
        file_to.materials.append("BW_Curvature_Map")
        file_to.materials.append("BW_Island_ID")
        file_to.materials.append("BW_Object_Color")
        file_to.materials.append("BW_Thickness_Map")
        file_to.materials.append("BW_Vertex_Color")
        file_to.materials.append("BW_World_Pos")
        file_to.materials.append("BW_OSL_Curvature")
        file_to.materials.append("BW_OSL_Height")
        file_to.materials.append("BW_Post_")
        file_to.materials.append("BW_Post_Col_")
        file_to.materials.append("BW_Billboard")
        file_to.materials.append("BW_Mask_Pass")
        file_to.materials.append("BW_Material_ID")
        file_to.node_groups.append("BW_Material_ID")
        file_to.node_groups.append("BW_Normals")
        file_to.node_groups.append("BW_Masked_Bake")
        file_to.node_groups.append("BW_Channel_Map")
        file_to.node_groups.append("bw_add_mask")
        file_to.node_groups.append("BW_Billboard_Norm")
        file_to.node_groups.append("BW_Bent_Norm")
        file_to.node_groups.append("BW_AutoSmooth")
        file_to.scenes.append("BakeWrangler_Post")
        file_to.scenes.append("BakeWrangler_Output")
        file_to.objects.append("BW_MatPlane")
    global bevmask_shader
    global bevnormemit_shader
    global bevnormnorm_shader
    global cavity_shader
    global curvature_shader
    global islandid_shader
    global objcol_shader
    global thickness_shader
    global vertcol_shader
    global worldpos_shader
    global osl_curvature
    global osl_height
    global post_proc_mat
    global post_proc_col
    global billboard_mat
    global mask_pass_shader
    global color_random
    bevmask_shader = file_to.materials[0]
    bevnormemit_shader = file_to.materials[1]
    bevnormnorm_shader = file_to.materials[2]
    cavity_shader = file_to.materials[3]
    curvature_shader = file_to.materials[4]
    islandid_shader = file_to.materials[5]
    objcol_shader = file_to.materials[6]
    thickness_shader = file_to.materials[7]
    vertcol_shader = file_to.materials[8]
    worldpos_shader = file_to.materials[9]
    osl_curvature = file_to.materials[10]
    osl_height = file_to.materials[11]
    post_proc_mat = file_to.materials[12]
    post_proc_col = file_to.materials[13]
    billboard_mat = file_to.materials[14]
    mask_pass_shader = file_to.materials[15]
    color_random = file_to.materials[16]
    global materialid_group
    global normals_group
    global post_masked_bake
    global post_chan_map
    global internal_add_mask
    global billboard_norm
    global bent_norm_group
    global auto_smooth
    materialid_group = file_to.node_groups[0]
    normals_group = file_to.node_groups[1]
    post_masked_bake = file_to.node_groups[2]
    post_chan_map = file_to.node_groups[3]
    internal_add_mask = file_to.node_groups[4]
    billboard_norm = file_to.node_groups[5]
    bent_norm_group = file_to.node_groups[6]
    auto_smooth = file_to.node_groups[7]
    global post_scene
    global output_scene
    post_scene = file_to.scenes[0]
    output_scene = file_to.scenes[1]
    global material_plane
    material_plane = file_to.objects[0]

    # Start processing bakery node tree
    err = process_tree(args.tree, args.node, args.sock)

    # Send comma separated list of files written
    file_list_str = "<PFILE>"
    for file in images_saved:
        file_list_str += file
        if file != images_saved[-1]:
            file_list_str += ","
    file_list_str += "</PFILE>"
    _print(file_list_str)

    # Send comma separated list of pickled vertex colors
    pickle_list_str = "<PVERT>"
    for file in pickled_verts:
        pickle_list_str += file
        if file != pickled_verts[-1]:
            pickle_list_str += ","
    pickle_list_str += "</PVERT>"
    _print(pickle_list_str)

    # Send end tag
    if err:
        _print("<ERRORS>", tag=True)
    else:
        _print("<FINISH>", tag=True)

    # Save changes to the file for debugging and exit
    if debug:
        bpy.ops.wm.save_mainfile(filepath=bpy.data.filepath, exit=True)

    return 0


if __name__ == "__main__":
    import os.path
    import math
    import random
    import bpy
    from datetime import datetime
    '''try:
        from BakeWrangler.nodes import node_tree
        from BakeWrangler.nodes.node_tree import _print
        from BakeWrangler.nodes.node_tree import material_recursor
        from BakeWrangler.nodes.node_tree import get_input
        from BakeWrangler.nodes.node_tree import follow_input_link
        from BakeWrangler.nodes.node_tree import gather_output_links
        import BakeWrangler.marginer as marginer
    except:'''
    # Need to import this stuff without referencing the BW module so marginer doesn't try to import the module
    import sys
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    from nodes import node_tree
    from nodes.node_tree import _print
    from nodes.node_tree import material_recursor
    from nodes.node_tree import get_input
    from nodes.node_tree import follow_input_link
    from nodes.node_tree import gather_output_links
    from vert import ipc
    from udim import udim as udim_util
    import marginer
    main()
