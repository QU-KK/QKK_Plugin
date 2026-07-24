import bpy


def _print(str, node=None, ret=False, tag=False, wrap=True, enque=None, textdata="BakeWrangler"):
    print(str)

# Follow an input link through any reroutes
def follow_input_link(link):
    if link.from_node.type == 'REROUTE':
        if link.from_node.inputs[0].is_linked:
            try: # During link insertion this can have weird states
                return follow_input_link(link.from_node.inputs[0].links[0])
            except:
                pass
    return link
    
class linkcls():
    def __init__(self):
        self.link_data = None
        self.link_list = []
    def set_links(self, link_data): self.link_data = link_data
    def new(self, lto, lfrom): 
        self.link_data.new(lto, lfrom)
        #self.link_list.append([self.link_data, lto, lfrom])
    def remove(self, link): self.link_data.remove(link)
    def create(self):
        for link in self.link_list:
            if debug: _print(">      Linking: %s to %s" % (link[1].node.name, link[2].node.name), tag=True)
            link[0].new(link[1], link[2])


def highlight_step(ntree, node):
    global step
    frame = ntree.nodes.new('NodeFrame')
    frame.parent = node.parent
    frame.location = node.location
    node.parent = frame
    frame.name = "BWStep"
    frame.label = frame.name
    step = step + 1
    

def check_step(node):
    if node.parent and node.parent.name.startswith("BWStep"):
        return True
    return False


def pick_material_output(node_tree):
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

    return node_selected_output


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
        node_emit.location = node.location
        node_emit.location[1] += 20
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
                        if first or node.name == named:
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
                # Set it to black if not found?
                node_emit.inputs['Color'].default_value = [0,0,0,0]
                return False
        else:
            ### Break ###
            if debug:
                highlight_step(tree, node)
                #__import__('code').interact(local=dict(globals(), **locals()))
            ###
            # Recurse
            #ret = prep_material_rec(next_node, next_sock, node_emit.inputs['Color'], bake_type, bake_settings, links, parent)
        return ["prep_material_rec(%s, %s, %s, bake_type, bake_settings, link_list, %s)\n" % (next_node.__repr__(), next_sock.__repr__(), node_emit.inputs['Color'].__repr__(), parent.__repr__())] #ret

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
            
            branchA = "prep_material_rec(%s, %s, %s, bake_type, bake_settings, link_list, %s)\n" % (nextA.from_node.__repr__(), nextA.from_socket.__repr__(), mix_node.inputs['Color1'].__repr__(), parent.__repr__())
        else:
            mix_node.inputs['Color1'].default_value = [0,0,0,0]
            branchA = None#True
        if nextB:
            if bake_settings['bbbk']: bake_settings['bbbk_sock'] = bbmix_node.inputs['Color2']
            
            branchB = "prep_material_rec(%s, %s, %s, bake_type, bake_settings, link_list, %s)\n" % (nextB.from_node.__repr__(), nextB.from_socket.__repr__(), mix_node.inputs['Color2'].__repr__(), parent.__repr__())
        else:
            mix_node.inputs['Color2'].default_value = [0,0,0,0]
            branchB = None#True
        if debug:
            highlight_step(tree, node)
        return [branchA, branchB] #branchA and branchB

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
                return None#True
            else:
                if debug: _print(">       Error: Group node active output not found", tag=True)
                return True
        # Follow the next node to be considered, use the added RGBA socket as link_sock (should be 2nd last)
        next = follow_input_link(gout.inputs.get(socket.identifier).links[0])
        if bake_settings['bbbk']: bake_settings['bbbk_sock'] = gout.inputs.get(bbsok.identifier)
        ### Break ###
        if debug:
            highlight_step(tree, node)
            #__import__('code').interact(local=dict(globals(), **locals()))
        ###
        return ["prep_material_rec(%s, %s, %s, bake_type, bake_settings, link_list, %s)\n" % (next.from_node.__repr__(), next.from_socket.__repr__(), gout.inputs.get(sok.identifier).__repr__(), gparent.__repr__())]

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
                __import__('code').interact(local=dict(globals(), **locals()))
                gout.inputs.get(sok.identifier).default_value = [0.0, 0.0, 0.0, 1.0]
                return None#True
            else:
                if debug: _print(">       Error: Group node input socket not linked", tag=True)
                return True
        # Return the next node to be considered, using the added RGBA external socket as the link_sock (should be last)
        next = follow_input_link(gout.inputs.get(socket.identifier).links[0])
        if bake_settings['bbbk']: bake_settings['bbbk_sock'] = gout.inputs.get(bbsok.identifier)
        ### Break ###
        if debug:
            highlight_step(tree, node)
            #__import__('code').interact(local=dict(globals(), **locals()))
        ###
        return ["prep_material_rec(%s, %s, %s, bake_type, bake_settings, link_list, %s)\n" % (next.from_node.__repr__(), next.from_socket.__repr__(), gout.inputs.get(sok.identifier).__repr__(), gparent.__repr__())]

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
                map_input_or_value(proxy, 'Emission', node.inputs['Color'])
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
        ### Break ###
        if debug:
            highlight_step(tree, node)
            #__import__('code').interact(local=dict(globals(), **locals()))
        ###
        return ["prep_material_rec(%s, %s, %s, bake_type, bake_settings, link_list, %s)\n" % (proxy.__repr__(), proxy.outputs[0].__repr__(), link_socket.__repr__(), parent.__repr__())]

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
        ### Break ###
        if debug:
            highlight_step(tree, node)
            #__import__('code').interact(local=dict(globals(), **locals()))
        ###

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
                return None#True
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
                ### Break ###
                #__import__('code').interact(local=dict(globals(), **locals()))
                ###
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
                    colornode.parent = node.parent
                    colornode.position = node.position
                    colorsoct = colornode.outputs["Color"]
                    links.new(link_socket, colorsoct)
                    colorsoct.default_value[0] = bake_input.default_value
                    colorsoct.default_value[1] = bake_input.default_value
                    colorsoct.default_value[2] = bake_input.default_value
                    colorsoct.default_value[3] = 1.0
            # Branch completed
            ### Break ###
            #highlight_step(tree, node)
            #__import__('code').interact(local=dict(globals(), **locals()))
            ###
            return None#True

    # Something went wrong
    if debug: _print(">       Error: Reached unsupported node type", tag=True)
    return None#False
    
def flatten(tree, mat):
    for node in tree.nodes:
        if node.type == 'GROUP':
            flatten(node.node_tree, mat)
            area = bpy.context.area
            old_type = area.type
            area.type = 'NODE_EDITOR'
            area.ui_type = 'ShaderNodeTree'
            bpy.context.space_data.node_tree = tree
            tree.nodes.active = node
            node.select = True
            bpy.ops.node.group_ungroup()
            area.type = old_type

    
global step

ntree = bpy.data.materials['Material SW'].node_tree

step = 1
link_list = linkcls()
node_selected_output = pick_material_output(ntree)
bake_type="ALBEDO"
bake_settings={'bbbk': False}
debug=True

if debug: _print(">      Chosen output [%s] descending tree:" % (node_selected_output.name), tag=True)

blend_temp = bpy.path.abspath(bpy.app.tempdir)
cmd_itr = blend_temp + "cmd_itr.txt"
cmd = []

from datetime import datetime
start = datetime.now()

flatten(ntree, bpy.data.materials['Material SW'])

#clear file
clear = True
if clear:
    clrfile = open(cmd_itr, "w", encoding="utf-8")
    clrfile.close()

try:
    with open(cmd_itr, "r", encoding="utf-8") as f:
        while True:
            cmdln = f.readline()
            if cmdln: cmd.append(cmdln)
            else: break
except:
    cmd = None
    cmd = prep_material_rec(node_selected_output, None, node_selected_output.inputs['Surface'], bake_type, bake_settings, link_list)
    
if cmd:
    while len(cmd):
        exec(f"ret = {cmd.pop()}")
        if ret:
            cmd.extend(ret)
    print("Time: %s" % (str(datetime.now() - start)))
else:
    ret = prep_material_rec(node_selected_output, None, node_selected_output.inputs['Surface'], bake_type, bake_settings, link_list)

if ret:
    cmd.extend(ret)
with open(cmd_itr, "w", encoding="utf-8") as f:
    for ln in cmd:
        if ln:
           f.write(ln)
