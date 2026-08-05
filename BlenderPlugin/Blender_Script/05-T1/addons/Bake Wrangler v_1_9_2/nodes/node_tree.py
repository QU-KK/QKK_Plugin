import os
import sys
import threading, queue
import subprocess
from datetime import datetime, timedelta
import bpy
from bpy.types import NodeTree, Node, NodeSocket, NodeSocketColor, NodeSocketFloat, NodeFrame, NodeReroute
try:
    from ..status_bar.status_bar_icon import ensure_bw_icon as update_status_bar
except:
    from status_bar.status_bar_icon import ensure_bw_icon as update_status_bar

BW_TREE_VERSION = 9
BW_VERSION_STRING = '1.9.0'


# Message formatter
def _print(str, node=None, ret=False, tag=False, wrap=True, enque=None, textdata="BakeWrangler"):
    output = "%s" % (str)
    endl = ''
    flsh = False

    if node:
        output = "[%s]: %s" % (node.get_name(), output)

    if tag:
        output.replace("<", "<_")
        output = "<%s>%s" % ("PBAKE", output)
        flsh = True
        if wrap:
            output = "%s</%s>" % (output, "PWRAP")
        else:
            output = "%s</%s>" % (output, "PBAKE")

    if wrap:
        endl = '\n'

    if enque != None:
        eout = "%s%s" % (output, endl)
        enque.put(eout)
        return None

    if ret:
        return output

    if textdata != None and _prefs('text_msgs'):
        if not textdata in bpy.data.texts.keys():
            bpy.data.texts.new(textdata)
        text = bpy.data.texts[textdata]
        end = len(text.lines[len(text.lines) - 1].body) - 1
        text.cursor_set(len(text.lines) - 1, character=end)
        tout = "%s%s" % (output, endl)
        text.write(tout)

    print(output, end=endl, flush=flsh)



# Preference reader
default_true  = ["text_msgs", "clear_msgs", "def_filter_mesh", "def_filter_curve", "def_filter_surface",
                 "def_filter_meta", "def_filter_font", "def_filter_light", "auto_open", "fact_start", "show_icon"]
default_false = ["def_filter_collection", "def_show_adv", "ignore_vis", "make_dirs", "wind_close",
                 "invert_bakemod", "wind_msgs", "save_packed", "save_images", "retry",]
default_res   = ["def_xres", "def_yres", "def_xout", "def_yout",]
default_zero  = ["def_margin", "def_mask_margin", "def_max_ray_dist",]
def _prefs(key):
    try:
        name = __package__.split('.')
        prefs = bpy.context.preferences.addons[name[0]].preferences
    except:
        pref = False
    else:
        pref = True

    if pref and key in prefs:
        return prefs[key]
    else:
        # Default values to fall back on
        if key == 'debug':
            if pref:
                return False
            else:
                #return False
                return True
        elif key in default_true:
            return True
        elif key in default_false:
            return False
        elif key in default_res:
            return 1024
        elif key in default_zero:
            return 0
        elif key == 'def_device':
            return 0 # CPU
        elif key == 'def_samples':
            return 1
        elif key == 'def_format':
            return 2 # PNG
        elif key == 'def_raydist':
            return 0.01
        elif key == 'def_outpath':
            return ""
        elif key == 'def_outname':
            return "Image"
        elif key == 'img_non_color':
            return None
        else:
            return None



# Material validation recursor (takes a shader node and descends the tree via recursion)
def material_recursor(node, link=None, parent=None):
    # Accepted node types are OUTPUT_MATERIAL, BSDF_PRINCIPLED, MIX/ADD_SHADER and GROUP (plus REROUTE)
    if node.type == 'BSDF_PRINCIPLED':
        return True
    if node.type == 'OUTPUT_MATERIAL' and node.inputs['Surface'].is_linked:
        return material_recursor(node.inputs['Surface'].links[0].from_node, node.inputs['Surface'].links[0], parent)
    if node.type in ['MIX_SHADER', 'ADD_SHADER']:
        if node.type == 'MIX_SHADER':
            input1 = 1
            input2 = 2
        else:
            input1 = 0
            input2 = 1
        inputA = False
        if node.inputs[input1].is_linked:
            inputA = material_recursor(node.inputs[input1].links[0].from_node, node.inputs[input1].links[0], parent)
        inputB = False
        if node.inputs[input2].is_linked:
            inputB = material_recursor(node.inputs[input2].links[0].from_node, node.inputs[input2].links[0], parent)
        return inputA and inputB
    if node.type == 'REROUTE' and node.inputs[0].is_linked:
        return material_recursor(node.inputs[0].links[0].from_node, node.inputs[0].links[0], parent)
    if node.type == 'GROUP' and link:
        # Entering a group, requires similar steps to exiting, but will duplicate code for now
        if parent:
            # Parent modification is always performed on a copy due to branching of recursion
            gparent = parent.copy()
            gparent.append(node)
        else:
            gparent = [node]
        gout = None
        gsoc = 0
        # Find active group socket to begin from. Names may not be unique, so get index
        for soc in node.outputs:
            if link.from_socket == soc: break
            else: gsoc += 1
        for gnode in node.node_tree.nodes:
            if gnode.type == 'GROUP_OUTPUT' and gnode.is_active_output:
                gout = gnode
                break
        if gout and gout.inputs[gsoc].is_linked:
            return material_recursor(gout.inputs[gsoc].links[0].from_node, gout.inputs[gsoc].links[0], gparent)
    if node.type == 'GROUP_INPUT' and link and parent:
        # Exiting a group, requires similar steps to entering, but will duplicate code for now
        # Parent modification is always performed on a copy due to branching of recursion
        gparent = parent.copy()
        gout = gparent.pop()
        gsoc = 0
        for soc in node.outputs:
            if link.from_socket == soc: break
            else: gsoc += 1
        if gout and gout.inputs[gsoc].is_linked:
            return material_recursor(gout.inputs[gsoc].links[0].from_node, gout.inputs[gsoc].links[0], gparent)
    return False



# Return the node connected to an input, dealing with re-routes
def get_input(input):
    if not input.is_output and input.islinked() and input.valid:
        link = follow_input_link(input.links[0])
        return link.from_node
    return None



# Prune error messages to remove duplicates
def prune_messages(messages):
    unique = []
    for msg in messages:
        if not unique.count(msg):
            unique.append(msg)
    return unique



# Prune a list of objects to remove duplicate references
def prune_objects(objs, allow_dups=False):
    count = []
    dups = []
    # First remove duplicates
    for obj in objs:
        if objs.count(obj) > 1:
            objs.remove(obj)
    # Then remove non duplicate entries that reference the same object where appropriate
    for obj in objs:
        # Get a list of just the referenced objects to count them
        count.append(obj[0])
    for obj in count:
        # Create a list of objects with multiple refs and count how many
        if count.count(obj) > 1:
            found = False
            for dup in dups:
                if dup[0] == obj:
                    found = True
                    dup[1] += 1
                    break
            if not found:
                dups.append([obj, 1])
    for obj in dups:
        # Go over all the duplicate entries and prune appropriately
        num = obj[1]
        for dup in objs:
            if dup[0] == obj[0]:
                # For target set, remove only dups that came from a group (the user may
                # want the same object with different settings)
                if allow_dups:
                    if len(dup) == 1:
                        objs.remove(dup)
                        num -= 1
                # For other sets just reduce to one reference
                else:
                    objs.remove(dup)
                    num -= 1
                # Break out when/if one dup remains
                if num == 1:
                    break

    # Return pruned object list
    return objs



# Follow an input link through any reroutes
def follow_input_link(link):
    if link.from_node.type == 'REROUTE':
        if link.from_node.inputs[0].is_linked:
            try: # During link insertion this can have weird states
                return follow_input_link(link.from_node.inputs[0].links[0])
            except:
                pass
    return link



# Gather all links from an output, going past any reroutes
def gather_output_links(output):
    links = []
    for link in output.links:
        if link.is_valid:
            if link.to_node.type == 'REROUTE':
                if link.to_node.outputs[0].is_linked:
                    links += gather_output_links(link.to_node.outputs[0])
            else:
                links.append(link)
    return links
    
    
# Switch mode to object/back again - Returns the mode being switched from unless no swich is needed
def switch_mode(mode='OBJECT'):
    curr_mode = bpy.context.mode
    # Convert mode to mode set enum (why are these different?!)
    if curr_mode in ['OBJECT', 'SCULPT']:
        enum_mode = curr_mode
    elif curr_mode.startswith('PAINT_'):
        enum_mode = curr_mode[6:] + "_PAINT"
    else:
        enum_mode = 'EDIT'
    
    if enum_mode != mode:
        bpy.ops.object.mode_set(mode=mode)
        return enum_mode
    else:
        return None


#
# Bake Wrangler Operators
#

# Base class for all bakery operators, provides data to find owning node, etc.
class BakeWrangler_Operator:
    # Use strings to store their names, since Node isn't a subclass of ID it can't be stored as a pointer
    tree: bpy.props.StringProperty()
    node: bpy.props.StringProperty()
    sock: bpy.props.IntProperty(default=-1)

    @classmethod
    def poll(type, context):
        if context.area is not None:
            return True
            #return context.area.type == "NODE_EDITOR" and context.space_data.tree_type == "BakeWrangler_Tree"
        else:
            return False


# Dummy operator to draw when no vertex colors are in list
class BakeWrangler_Operator_Dummy_VCol(BakeWrangler_Operator, bpy.types.Operator):
    '''No vertex data currently in cache'''
    bl_idname = "bake_wrangler.dummy_vcol"
    bl_label = ""

    @classmethod
    def poll(type, context):
        # This operator is always supposed to be disabled
        return False



# Dummy operator to draw when a bake is in progress
class BakeWrangler_Operator_Dummy(BakeWrangler_Operator, bpy.types.Operator):
    '''Bake currently in progress, either cancel the current bake or wait for it to finish'''
    bl_idname = "bake_wrangler.dummy"
    bl_label = ""

    @classmethod
    def poll(type, context):
        # This operator is always supposed to be disabled
        return False



# Contol filter selection by allowing modifier keys
class BakeWrangler_Operator_FilterToggle(BakeWrangler_Operator, bpy.types.Operator):
    '''Ctrl-Click to deselect others, Shift-Click to select all others'''
    bl_idname = "bake_wrangler.filter_toggle"
    bl_label = ""
    bl_options = {"REGISTER", "UNDO"}
    
    filters = ('filter_mesh',
               'filter_curve',
               'filter_surface',
               'filter_meta',
               'filter_font',
               'filter_light')
    
    filter: bpy.props.StringProperty()
    
    @classmethod
    def description(self, context, properties):
        return properties.filter.split("_")[1].title() + " filter toggle. Ctrl-Click to deselect others, Shift-Click to select all others"
    
    def execute(self, context):
        return {'FINISHED'}
        
    def invoke(self, context, event):
        mod_shift = event.shift
        mod_ctrl = event.ctrl
        tree = bpy.data.node_groups[self.tree]
        node = tree.nodes[self.node]
        if node and node.bl_idname == 'BakeWrangler_Input_ObjectList':
            # Toggle
            if not mod_ctrl and not mod_shift:
                setattr(node, self.filter, not getattr(node, self.filter))
            # Enable self and disable others
            elif mod_ctrl and not mod_shift:
                for fltr in self.filters:
                    setattr(node, fltr, False)
                setattr(node, self.filter, True)
            # Disable self and enable others
            elif not mod_ctrl and mod_shift:
                for fltr in self.filters:
                    setattr(node, fltr, True)
                setattr(node, self.filter, False)
            # Invert current states
            elif mod_ctrl and mod_shift:
                for fltr in self.filters:
                    setattr(node, fltr, not getattr(node, fltr))
        return {'FINISHED'}



# Double/Halve value
class BakeWrangler_Operator_DoubleVal(BakeWrangler_Operator, bpy.types.Operator):
    '''Description set by function'''
    bl_idname = "bake_wrangler.double_val"
    bl_label = ""
    bl_options = {"REGISTER", "UNDO"}
    
    val: bpy.props.StringProperty()
    half: bpy.props.BoolProperty()
    
    @classmethod
    def set_props(self, inst, node, tree, value, half=False):
            inst.tree = tree
            inst.node = node
            inst.val = value
            inst.half = half
            
    @classmethod
    def description(self, context, properties):
        if properties.half: return "Halve value"
        else: return "Double value"
        
    def execute(self, context):
        return {'FINISHED'}
        
    def invoke(self, context, event):
        tree = bpy.data.node_groups[self.tree]
        node = tree.nodes[self.node]
        value = getattr(node, self.val)
        if self.half: value /= 2
        else: value *= 2
        setattr(node, self.val, int(value))
        return {'FINISHED'}

    
    
# Pick an enum from a menu
class BakeWrangler_Operator_PickMenuEnum(BakeWrangler_Operator, bpy.types.Operator):
    '''Description set by function'''
    bl_idname = "bake_wrangler.pick_menu_enum"
    bl_label = ""
    bl_options = {"REGISTER", "UNDO"}
    
    enum_id: bpy.props.StringProperty()
    enum_desc: bpy.props.StringProperty()
    enum_prop: bpy.props.StringProperty()
    
    @classmethod
    def set_props(self, inst, e_id, e_desc, e_prop, node, tree):
            inst.tree = tree
            inst.node = node
            inst.enum_prop = e_prop
            inst.enum_desc = e_desc
            inst.enum_id = e_id
            
    @classmethod
    def description(self, context, properties):
        return properties.enum_desc
    
    def execute(self, context):
        return {'FINISHED'}
        
    def invoke(self, context, event):
        tree = bpy.data.node_groups[self.tree]
        node = tree.nodes[self.node]
        setattr(node, self.enum_prop, self.enum_id)
        return {'FINISHED'}



# Add selected objects to an ObjectList node (ignoring duplicates unless Shift held)
class BakeWrangler_Operator_AddSelected(BakeWrangler_Operator, bpy.types.Operator):
    '''Adds selected objects to the node, respecting filter and ignoring duplicates\nShift-Click: Adds items even if they are duplicates'''
    bl_idname = "bake_wrangler.add_selected"
    bl_label = "Add Selected"
    bl_options = {"REGISTER", "UNDO"}

    mod_shift = False

    # Called either after invoke from UI or directly from script
    def execute(self, context):
        tree = bpy.data.node_groups[self.tree]
        node = tree.nodes[self.node]

        existing_objs = []
        # Get all the objects in the current node (ignoring connected nodes and groups)
        for input in node.inputs:
            if not input.is_linked and input.value:
                existing_objs.append(input.value)

        selected_objs = []
        # Get a list of all selected objects that also match current filter
        for obj in context.selected_objects:
            if node.input_filter(obj.name, obj):
                selected_objs.append(obj)

        # Add non duplicate objects to the end of the node (includes duplicates if Shift)
        for obj in selected_objs:
            if self.mod_shift or obj not in existing_objs:
                node.inputs[-1].value = obj

        return {'FINISHED'}

    # Called from button press, set modifier key states
    def invoke(self, context, event):
        self.mod_shift = event.shift
        return self.execute(context)


# Read vertex color data from temp files and apply to current file
class BakeWrangler_Operator_DiscardBakedVertCols(BakeWrangler_Operator, bpy.types.Operator):
    '''Discard baked vertex color data'''
    bl_idname = "bake_wrangler.discard_vertcols"
    bl_label = "Discard Data"
    
    # Read and apply vertex colors
    def execute(self, context):
        tree = bpy.data.node_groups[self.tree]
        node = tree.nodes[self.node]
        if node.bl_idname not in ['BakeWrangler_Output_Vertex_Cols', 'BakeWrangler_Output_Batch_Bake']:
            return {'CANCELLED'}
        files = node.vert_files
        while len(node.vert_files):
            jar = node.vert_files.pop()
            try:
                os.remove(jar)
            except:
                pass
                
        self.report({'INFO'}, "Data Removed")
        return {'FINISHED'}

    # Confirm the action
    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)


# Read vertex color data from temp files and apply to current file
class BakeWrangler_Operator_ApplyBakedVertCols(BakeWrangler_Operator, bpy.types.Operator):
    '''Apply baked vertex color data to current blend file objects'''
    bl_idname = "bake_wrangler.apply_vertcols"
    bl_label = "Apply Data"
    
    # Read and apply vertex colors
    def execute(self, context):
        try:
            from BakeWrangler.vert import ipc
        except:
            sys.path.append(os.path.dirname(os.path.abspath(__file__)))
            from vert import ipc
        tree = bpy.data.node_groups[self.tree]
        node = tree.nodes[self.node]
        if node.bl_idname not in ['BakeWrangler_Output_Vertex_Cols', 'BakeWrangler_Output_Batch_Bake']:
            return {'CANCELLED'}
        files = node.vert_files
        if not len(files):
            return {'CANCELLED'}
        
        # Open each file and apply the data one at a time
        oerr = 0
        for jar in files:
            fd = ipc.open_pickle_jar(file=jar)
            data = ipc.depickle_verts(file=fd)
            err, str = ipc.import_verts(cols=data)
            if err:
                _print("Error applying vertex data: %s" % (str), node=node)
                oerr += 1
            else:
                _print("Applied %s" % (str), node=node)
            if fd: fd.close()
            
        if oerr:
            self.report({'ERROR'}, "Apply Failed")
            return {'CANCELLED'}
        
        # Remove temp files if no errors
        while len(node.vert_files):
            jar = node.vert_files.pop()
            try:
                os.remove(jar)
            except:
                pass
                
        self.report({'INFO'}, "Data Applied")
        return {'FINISHED'}

    # Confirm the action
    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)
        
        
# Kill switch to stop a bake in progress
class BakeWrangler_Operator_BakeStop(BakeWrangler_Operator, bpy.types.Operator):
    '''Cancel currently running bake'''
    bl_idname = "bake_wrangler.bake_stop"
    bl_label = "Cancel Bake"

    # Stop the currently running bake
    def execute(self, context):
        tree = bpy.data.node_groups[self.tree]
        if tree.baking != None:
            tree.baking.stop()
            tree.interface_update(context)
        return {'FINISHED'}

    # Ask the user if they really want to cancel bake
    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)


# Operator for bake pass node
class BakeWrangler_Operator_BakePass(BakeWrangler_Operator, bpy.types.Operator):
    '''Perform requested bake action(s)'''
    bl_idname = "bake_wrangler.bake_pass"
    bl_label = "Bake Pass"

    _timer = None

    _thread = None
    _kill = False
    _success = False
    _finish = False
    _lock = threading.Lock()
    _queue = queue.SimpleQueue()
    _ifileq = queue.SimpleQueue()
    _vfileq = queue.SimpleQueue()
    stopping = False

    open_win = None
    open_ed = None
    node_ed = None

    start = None
    valid = None
    blend_copy = None
    blend_log = None
    bake_proc = None
    was_dirty = False
    img_list = []
    vert_list = []
    shutdown = False

    # Stop this bake if it's currently running
    def stop(self, kill=True):
        if self._thread and self._thread.is_alive() and kill:
            with self._lock:
                self.stopping = self._kill = True
        return self.stopping

    # Runs a blender subprocess
    def thread(self, node_name, tree_name, file_name, exec_name, script_name):
        tree = bpy.data.node_groups[self.tree]
        node = tree.nodes[self.node]
        sock = self.sock
        debug = _prefs('debug')
        ignorevis = _prefs('ignore_vis')
        factory = ""
        rend_dev_str = ""
        rend_dev_val = ""
        rend_use_str = ""
        rend_use_val = ""
        solution_itr = last_solution = 0
        frames_itr = last_frame = 0
        batch_itr = last_batch = 0
        retry = _prefs('retry')
        tries = 2
        if _prefs('fact_start'):
            factory = "--factory-startup"
            # Need to reselect gpu render some how when fact starting
            rend_type = bpy.context.preferences.addons['cycles'].preferences.compute_device_type
            rend_use = ""
            for dev in bpy.context.preferences.addons['cycles'].preferences.devices:
                if dev.use: rend_use = "%s1" % rend_use
                else: rend_use = "%s0" % rend_use
            rend_dev_str = "--rend_dev"
            rend_dev_val = str(rend_type)
            rend_use_str = "--rend_use"
            rend_use_val = str(rend_use)

        _print("Launching background process:", node=node, enque=self._queue)
        _print("================================================================================", enque=self._queue)
        _print('Cmd: "{0}" "{1}" --background --python "{2}" {3} -- --tree "{4}" --node "{5}"'.format(exec_name,file_name,script_name,factory,tree_name,node_name), enque=self._queue)
        while not self._finish and tries > 0:
            sub = subprocess.Popen([
                exec_name,
                file_name,
                "--background",
                "--python", script_name,
                factory,
                "--",
                "--tree", tree_name,
                "--node", node_name,
                "--sock", str(int(sock)),
                "--debug", str(int(debug)),
                "--ignorevis", str(int(ignorevis)),
                "--solitr", str(solution_itr),
                "--frameitr", str(frames_itr),
                "--batchitr", str(batch_itr),
                rend_dev_str, rend_dev_val,
                rend_use_str, rend_use_val,
                ], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")

            # Read output from subprocess and print tagged lines
            out = ""
            kill = False
            while sub.poll() == None:
                # Check for kill flag
                if self._lock.acquire(blocking=False):
                    if self._kill:
                        _print("Bake canceled, terminating process...", enque=self._queue)
                        sub.kill()
                        out, err = sub.communicate()
                        kill = True
                    self._lock.release()

                if not kill:
                    out = sub.stdout.read(1)
                    # Collect tagged lines and display them in console
                    if out == '<':
                        out += sub.stdout.read(6)
                        if out == "<PBAKE>":
                            tag_end = False
                            tag_line = ""
                            out = ""
                            tag_out = ""
                            # Read until end tag is found
                            while not tag_end:
                                tag = sub.stdout.read(1)

                                if tag == '<':
                                    tag_line = sub.stdout.read(1)
                                    if tag_line != '_':
                                        tag_line = tag + tag_line + sub.stdout.read(6)
                                        if tag_line == "</PBAKE>":
                                            tag_end = True
                                            out += '\n'
                                        elif tag_line == "</PWRAP>":
                                            tag_end = True
                                            tag_out += '\n'
                                            #sys.stdout.write('\n')
                                            #sys.stdout.flush()
                                        elif tag_line == "<FINISH>":
                                            tag_line += sub.stdout.read(8)
                                            tag_end = True
                                            self._success = True
                                            self._finish = True
                                        elif tag_line == "<ERRORS>":
                                            tag_line += sub.stdout.read(8)
                                            tag_end = True
                                            self._success = False
                                            self._finish = True
                                if tag != '' and not tag_end:
                                    tag_out += tag
                                    #sys.stdout.write(tag_line)
                                    #sys.stdout.flush()
                                    out += tag
                            _print(tag_out, enque=self._queue, wrap=False)
                        if out == "<PFILE>" or out == "<PVERT>":
                            tag_end = False
                            tag_line = ""
                            files = ""
                            # Set output queue
                            if out == "<PFILE>":
                                que = self._ifileq
                            else:
                                que = self._vfileq
                            while not tag_end:
                                tag = sub.stdout.read(1)
                                if tag == '<':
                                    tag_line = sub.stdout.read(1)
                                    if tag_line != '_':
                                        tag_line = tag + tag_line + sub.stdout.read(6)
                                        if tag_line == "</PFILE>" or tag_line == "</PVERT>":
                                            tag_end = True
                                            _print(files, enque=que, wrap=False)
                                if tag != '' and not tag_end:
                                    files += tag
                            out = ''
                        if out == "<PFRAM>" or out == "<PSOLU>" or out == "<PBATC>":
                            tag_end = False
                            tag_line = ""
                            num = ""
                            while not tag_end:
                                tag = sub.stdout.read(1)
                                if tag == '<':
                                    tag_line = sub.stdout.read(1)
                                    if tag_line != '_':
                                        tag_line = tag + tag_line + sub.stdout.read(6)
                                        if tag_line == "</PFRAM>":
                                            tag_end = True
                                            frames_itr = int(num)
                                        elif tag_line == "</PSOLU>":
                                            tag_end = True
                                            solution_itr = int(num)
                                        elif tag_line == "</PBATC>":
                                            tag_end = True
                                            batch_itr = int(num)
                                if tag != '' and not tag_end:
                                    num += tag
                            out = ''
                # Write to log
                if out != '' and self.blend_log:
                    self.blend_log.write(out)
                    self.blend_log.flush()
            _print("================================================================================", enque=self._queue)
            _print("Background process ended", node=node, enque=self._queue)
            if not self._finish:
                if (batch_itr > last_batch or solution_itr > last_solution or frames_itr > last_frame or tries == 2) and retry:
                    tries = 1
                    _print("Process did not complete, retry from last known success", node=node, enque=self._queue)
                else:
                    tries = 0
                    _print("Process did not complete and no progress made on retry", node=node, enque=self._queue)

    # Event handler
    def modal(self, context, event):
        tree = bpy.data.node_groups[self.tree]
        node = tree.nodes[self.node]

        # Check if the bake thread has ended every timer event
        if event.type == 'TIMER':
            self.print_queue(context)
            # Reapply dirt by pushing something to undo stack (not ideal)
            if self.was_dirty and not bpy.data.is_dirty and bpy.ops.node.select_all.poll():
                bpy.ops.node.select_all(action='INVERT')
                bpy.ops.node.select_all(True, action='INVERT')
                self.was_dirty = False
            if not self._thread.is_alive():
                self.cancel(context)
                if self._kill:
                    _print("Bake canceled after %s" % (str(datetime.now() - self.start)), node=node, enque=self._queue)
                    _print("Canceled\n", node=node, enque=self._queue)
                    self.report({'WARNING'}, "Bake Canceled")
                    self.update_images()
                    self.print_queue(context)
                    if self.blend_log:
                        context.window_manager.bw_lastlog = self.blend_copy + ".log"
                        context.window_manager.bw_lastfile = self.blend_copy
                    return {'CANCELLED'}
                else:
                    if self._success and self._finish:
                        _print("Bake finished in %s" % (str(datetime.now() - self.start)), node=node, enque=self._queue)
                        _print("Success\n", node=node, enque=self._queue)
                        self.report({'INFO'}, "Bake Completed")
                        context.window_manager.bw_status = 0 # Bake finished / idle status
                    elif self._finish:
                        _print("Bake finished with errors after %s" % (str(datetime.now() - self.start)), node=node, enque=self._queue)
                        _print("Errors\n", node=node, enque=self._queue)
                        self.report({'WARNING'}, "Bake Finished with Errors")
                        context.window_manager.bw_status = 2 # Bake error status
                    else:
                        _print("Bake failed after %s" % (str(datetime.now() - self.start)), node=node, enque=self._queue)
                        _print("Failed\n", node=node, enque=self._queue)
                        self.report({'ERROR'}, "Bake Failed")
                        context.window_manager.bw_status = 2 # Bake error status
                    self.print_queue(context)
                    if self.blend_log:
                        context.window_manager.bw_lastlog = self.blend_copy + ".log"
                        context.window_manager.bw_lastfile = self.blend_copy
                    # Update images
                    self.dequeue_files(context, self._ifileq, self.img_list)
                    if _prefs('debug'): _print("Img list: %s" % self.img_list)
                    self.update_images()
                    # Send vertex file names to node
                    if hasattr(node, 'vert_files'):
                        self.dequeue_files(context, self._vfileq, self.vert_list)
                        if _prefs('debug'): _print("Vert list: %s" % self.vert_list)
                        for vfile in self.vert_list:
                            node.vert_files.append(vfile)
                    # Check if a post-bake user script should be run
                    if self._finish and node.bl_idname == 'BakeWrangler_Output_Batch_Bake' and node.loc_post != 'NON':
                        _print("Running user created post-bake script: ", node=node, wrap=False)
                        if node.loc_post == 'INT':
                            post_scr = node.script_post_int.as_string()
                        elif node.loc_post == 'EXT':
                            with open(node.script_post_can, "r") as scr:
                                post_scr = scr.read()
                        try:
                            exec(post_scr, {'BW_TARGETS': node.get_unique_objects('TARGET'), 'BW_SOURCES': node.get_unique_objects('SOURCE'),
                                            'BW_IMAGES': self.img_list})
                        except Exception as err:
                            _print(" Failed - %s" % (str(err)))
                        else:
                            _print(" Done")
                    if _prefs("wind_msgs") and self.open_win:
                        if _prefs("wind_close"):
                            bpy.ops.wm.window_close({"window": self.open_win})
                    # Do batch shutdown
                    if self.shutdown:
                        if sys.platform == 'win32':
                            os.system('shutdown /s /t 60')
                        else:
                            os.system('sudo shutdown +1')
                    if _prefs("show_icon"): update_status_bar()
                    return {'FINISHED'}
        return {'PASS_THROUGH'}
    
    # Get queued file list
    def dequeue_files(self, context, queue, list):
        fstr = ""
        try:
            # An Empty exception will be raised when nothing is in the queue
            while True:
                fstr += queue.get_nowait()
        except:
            list += fstr.split(",")
            return
            
    # Print queued messages
    def print_queue(self, context):
        try:
            # An Empty exception will be raised when nothing is in the queue
            while True:
                msg = self._queue.get_nowait()
                _print(msg, wrap=False)
        except:
            return

    # Display log file if debugging is enabled and the bake failed or had errors
    def show_log(self):
        if _prefs('debug') and self.blend_log and self.node_ed:
            bpy.ops.screen.area_dupli({'area': self.node_ed}, 'INVOKE_DEFAULT')
            open_ed = bpy.context.window_manager.windows[len(bpy.context.window_manager.windows) - 1].screen.areas[0]
            open_ed.type = 'TEXT_EDITOR'
            log = bpy.data.texts.load(self.blend_copy + ".log")
            open_ed.spaces[0].text = log
            open_ed.spaces[0].show_line_numbers = False
            open_ed.spaces[0].show_syntax_highlight = False

    # Update any loaded images that might be changed by the bake
    def update_images(self):
        if len(self.img_list):
            cwd = os.path.dirname(bpy.data.filepath)
            open_imgs = {}
            for img in bpy.data.images:
                open_imgs[os.path.normpath(os.path.join(cwd, bpy.path.abspath(img.filepath_raw)))] = img
            for img in self.img_list:
                if img in open_imgs.keys():
                    open_imgs[img].reload()
                elif _prefs("auto_open"):
                    try:
                        bpy.data.images.load(img)
                    except:
                        pass

    # Called after invoke to perform the bake if everything passed validation
    def execute(self, context):
        # If called from script, do prepare now
        if self.valid == None:
            if self.tree and self.node:
                tree = bpy.data.node_groups[self.tree]
                node = tree.nodes[self.node]
                self.prepare(context, tree, node)
            else:
                self.valid = [False]
                self.valid.append([_print("Bake Tree/Node missing", ret=True), ": Bake Tree or Node was not set for operator"])
                self.report({'ERROR'}, "Operator required arguments missing")
                return {'CANCELLED'}
        # Do any interactive actions if called from invoke
        else:
            # If message log in new window is enabled
            if _prefs("text_msgs") and _prefs("wind_msgs"):
                bpy.ops.screen.area_dupli('INVOKE_DEFAULT')
                self.open_win = context.window_manager.windows[len(context.window_manager.windows) - 1]
                self.open_ed = self.open_win.screen.areas[0]
                self.open_ed.type = 'TEXT_EDITOR'
                self.open_ed.spaces[0].text = bpy.data.texts["BakeWrangler"]
                self.open_ed.spaces[0].show_line_numbers = False
                self.open_ed.spaces[0].show_syntax_highlight = False

        if not self.valid[0]:
            self.cancel(context)
            self.report({'ERROR'}, "Validation failed")
            return {'CANCELLED'}

        self.start = datetime.now()
        tree = bpy.data.node_groups[self.tree]
        node = tree.nodes[self.node]

        # Check for batch shutdown
        if node.bl_idname == 'BakeWrangler_Output_Batch_Bake' and node.shutdown_after:
            self.shutdown = True

        # Save a temporary copy of the blend file and store the path. Make sure the path doesn't exist first.
        # All baking will be done using this copy so the user can continue working in this session.
        blend_name = bpy.path.clean_name(bpy.path.display_name_from_filepath(bpy.data.filepath))
        blend_temp = bpy.path.abspath(bpy.app.tempdir)
        node_cname = bpy.path.clean_name(node.get_name())
        blend_copy = os.path.join(blend_temp, "BW_" + blend_name)

        # Increment file name until it doesn't exist
        if os.path.exists(blend_copy + ".blend"):
            fno = 1
            while os.path.exists(blend_copy + "_%03i.blend" % (fno)):
                fno = fno + 1
            blend_copy = blend_copy + "_%03i.blend" % (fno)
        else:
            blend_copy = blend_copy + ".blend"
            
        # Check if a pre-bake user script should be run
        if node.bl_idname == 'BakeWrangler_Output_Batch_Bake' and node.loc_pre != 'NON':
            _print("Running user created pre-bake script: ", node=node, wrap=False)
            if node.loc_pre == 'INT':
                pre_scr = node.script_pre_int.as_string()
            elif node.loc_pre == 'EXT':
                with open(node.script_pre_can, "r") as scr:
                    pre_scr = scr.read()
            try:
                exec(pre_scr, {'BW_TARGETS': node.get_unique_objects('TARGET'), 'BW_SOURCES': node.get_unique_objects('SOURCE')})
            except Exception as err:
                _print(" Failed - %s" % (str(err)))
                return {'CANCELLED'}
            else:
                _print(" Done")

        # Print out start message and temp path
        _print("")
        _print("=== Bake starts ===", node=node)
        _print("Creating temporary files in %s" % (blend_temp), node=node)

        # Maintain dirt
        if bpy.data.is_dirty:
            self.was_dirty = True
            
        # Save dirty images based on preferences as unsaved changes will not effect bake
        if _prefs("save_packed") or _prefs("save_images"):
            for img in bpy.data.images:
                if img.is_dirty:
                    if (img.packed_file is not None and _prefs("save_packed")) or (img.packed_file is None and _prefs("save_images")):
                        bpy.ops.image.save({'edit_image': img})
        
        try:
            bpy.ops.wm.save_as_mainfile(filepath=blend_copy, copy=True)
        except RuntimeError as err:
            _print("Temporary file creation failed: %s" % (str(err)), node=node)
            self.report({'ERROR'}, "Blend file copy failed")
            return {'CANCELLED'}
        else:            
            # Check copy exists
            if not os.path.exists(blend_copy):
                _print("Temporary file creation failed", node=node)
                self.report({'ERROR'}, "Blend file copy failed")
                return {'CANCELLED'}
            else:
                self.blend_copy = blend_copy                

        # Open a log file at the same location with a .log appended to the name
        log_err = None
        blend_log = None
        try:
            blend_log = open(blend_copy + ".log", "w", encoding="utf-8", errors="replace")
        except OSError as err:
            self.report({'WARNING'}, "Couldn't create log file")
            log_err = err.strerror
        else:
            self.blend_log = blend_log
            tree.last_log = blend_copy + ".log"

        # Print out blend copy and log names
        _print(" - %s" % (os.path.basename(self.blend_copy)), node=node)
        if self.blend_log and not log_err:
            _print(" - %s" % (os.path.basename(self.blend_copy + ".log")), node=node)
        else:
            _print(" - Log file creation failed: %s" % (log_err), node=node)
        _print("Blender: %s Addon: %s" % (bpy.app.version_string, BW_VERSION_STRING), node=node)
        
        # Create a thread which will launch a background instance of blender running a script that does all the work.
        # Process is complete when thread exits. Will need full path to blender, node, temp file and proc script.
        blend_exec = bpy.path.abspath(bpy.app.binary_path)
        _print("Exec: Node(%s) Tree(%s) Blend(%s) Exe(%s) Script(%s)" % (self.node, self.tree, self.blend_copy, blend_exec, self.bake_proc), node=node)
        self._thread = threading.Thread(target=self.thread, args=(self.node, self.tree, self.blend_copy, blend_exec, self.bake_proc,))

        # Get a list of image file names that will be updated by the bake so they can be reloaded on success
        self.img_list = []
        '''if node.bl_idname == 'BakeWrangler_Output_Batch_Bake':
            for input in node.inputs:
                outnode = get_input(input)
                if outnode and outnode.bl_idname == 'BakeWrangler_Output_Image_Path':
                    files = outnode.get_output_files()
                    for name in files.keys():
                        img_name = os.path.join(outnode.img_path, name)
                        if not self.img_list.count(img_name):
                            self.img_list.append(img_name)
        elif node.bl_idname == 'BakeWrangler_Output_Image_Path':
            files = node.get_output_files()
            for name in files.keys():
                img_name = os.path.join(node.img_path, name)
                if not self.img_list.count(img_name):
                    self.img_list.append(img_name)'''
                    
        # Init vert file list
        self.vert_list = []
        bpy.ops.bake_wrangler.discard_vertcols(node=self.node, tree=self.tree)

        # Add a timer to periodically check if the bake has finished
        wm = context.window_manager
        self._timer = wm.event_timer_add(0.5, window=context.window)
        wm.modal_handler_add(self)

        self._thread.start()

        # Go modal
        context.window_manager.bw_status = 1 # Baking status
        if _prefs("show_icon"): update_status_bar()
        return {'RUNNING_MODAL'}

    # Called by UI when the button is clicked. Will validate settings and prepare files for execute
    def invoke(self, context, event):
        # Prep for bake
        self.node_ed = context.area
        if self.tree and self.node:
            tree = bpy.data.node_groups[self.tree]
            node = tree.nodes[self.node]
            self.prepare(context, tree, node)
        else:
            self.valid = [False]
            self.valid.append([_print("Bake Tree/Node missing", ret=True), ": Bake Tree or Node was not set for operator"])
            self.report({'ERROR'}, "Operator properties not set")
            return {'CANCELLED'}
        
        if not self.valid[0] or len(self.valid) > 1:
            # Draw pop-up that will use custom draw function to display any validation errors
            return context.window_manager.invoke_props_dialog(self, width=400)
        else:
            return self.execute(context)

    # Prepare for bake, do all validation tasks and set properties
    def prepare(self, context, tree, node):
        # Init variables
        self.valid = [False]

        # Are text editor messages enabled?
        if _prefs("text_msgs"):
            # Make sure the text block exists
            if not "BakeWrangler" in bpy.data.texts.keys():
                bpy.data.texts.new("BakeWrangler")
            # Clear the block if option set
            if _prefs("clear_msgs"):
                bpy.data.texts["BakeWrangler"].clear()

        # Do full validation of bake so it can be reported
        tree.baking = self
        tree.interface_update(context)
        self.valid = node.validate(is_primary=True)
        
        # Remove UV errors if node is a vertex color output, kinda dumb, but... Least changes required this way
        if node.bl_idname == 'BakeWrangler_Output_Vertex_Cols' and not self.valid[0]:
            idx = 0
            for msg in self.valid:
                if idx == 0: 
                    idx += 1
                    continue
                if msg[0].endswith("UV error"):
                    self.valid.pop(idx)
                idx += 1
            if len(self.valid) == 1:
                self.valid[0] = True

        # Check tree is of the current version
        if tree.tree_version != BW_TREE_VERSION:
            self.valid[0] = False
            if tree.tree_version < BW_TREE_VERSION:
                self.valid.append([_print("Bake Recipe for older version of Bake Wrangler", node=node, ret=True), ": Recipe is version %s, but version %s is requied. Please use the auto-update function if available, or create a new recipe" % (tree.tree_version, BW_TREE_VERSION)])
            else:
                self.valid.append([_print("Bake Recipe for newer version of Bake Wrangler", node=node, ret=True), ": Recipe is version %s, but version %s is requied. You need to update Bake Wrangler to a version that supports this recipe, or create a new recipe" % (tree.tree_version, BW_TREE_VERSION)])
        # Check processing script exists
        bake_path = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
        bake_proc = bpy.path.abspath(os.path.join(bake_path, "baker.py"))
        if not os.path.exists(bake_proc):
            self.valid[0] = False
            self.valid.append([_print("File missing", node=node, ret=True), ": Bake processing script wasn't found at '%s'" % (bake_proc)])
        else:
            self.bake_proc = bake_proc

        # Check baking scene file exists
        scene_file = bpy.path.abspath(os.path.join(bake_path, "resources", "BakeWrangler_Scene.blend"))
        if not os.path.exists(scene_file):
            self.valid[0] = False
            self.valid.append([_print("File missing", node=node, ret=True), ": Bake scene library wasn't found at '%s'" % (scene_file)])
        self.valid = prune_messages(self.valid)

    # Cancel the bake
    def cancel(self, context):
        tree = bpy.data.node_groups[self.tree]
        node = tree.nodes[self.node]
        if self._timer:
            wm = context.window_manager
            wm.event_timer_remove(self._timer)
        if self.blend_log:
            self.blend_log.close()
        if tree.baking != None:
            tree.baking = None
            tree.interface_update(context)
        if self.blend_copy and os.path.exists(self.blend_copy):
            if not _prefs("debug"):
                try:
                    os.remove(self.blend_copy)
                except OSError as err:
                    _print("Temporary file removal failed: %s\n" % (err.strerror), node=node, enque=self._queue)

    # Draw custom pop-up
    def draw(self, context):
        tree = bpy.data.node_groups[self.tree]
        node = tree.nodes[self.node]
        layout = self.layout.column(align=True)
        if not self.valid[0]:
            layout.label(text="!!! Validation FAILED:")
            _print("")
            _print("!!! Validation FAILED:", node=node)
            col = layout.column()
            for i in range(len(self.valid) - 1):
                col.label(text=self.valid[i + 1][0])
                _print(self.valid[i + 1][0] + self.valid[i + 1][1])
            layout.label(text="See console for details")
            _print("")
        elif len(self.valid) > 1:
            layout.label(text="")
            layout.label(text="!!! Material Warnings:")
            _print("")
            _print("!!! Material Warnings:")
            col = layout.column()
            for i in range(len(self.valid) - 1):
                col.label(text=self.valid[i + 1][0])
                _print(self.valid[i + 1][0] + self.valid[i + 1][1])
            layout.label(text="See console for details")
            _print("")            



#
# Bake Wrangler nodes system
#


# Node tree definition that shows up in the editor type list. Sets the name, icon and description.
class BakeWrangler_Tree(NodeTree):
    '''Improved baking system to extend and replace existing internal bake system'''
    bl_label = 'Bake Recipe'
    bl_icon = 'NODETREE'

    # Get pinned mesh settings if exists
    def get_pinned_settings(self, setting):
        # Combined settings node has prio
        for node in self.nodes:
            if node.bl_idname == 'BakeWrangler_Settings' and node.pinned:
                return node
        for node in self.nodes:
            if node.bl_idname == 'BakeWrangler_' + setting and node.pinned:
                return node
        return None

    # Get the active global resolution node in a tree
    def get_active_res(self):
        for node in self.nodes:
            if node.bl_idname == 'BakeWrangler_Global_Resolution' and node.is_active:
                return node
        return None

    # Does this need a lock for modal event access?
    baking = None

    # Do some initial set up when a new tree is created
    initialised: bpy.props.BoolProperty(name="Initialized", default=False)
    tree_version: bpy.props.IntProperty(name="Tree Version", default=0)
    last_log: bpy.props.StringProperty(name="Last Log", default="")



# Custom Sockets:

# Base class for all bakery sockets
class BakeWrangler_Tree_Socket:
    # Workaround for link.is_valid being un-usable
    valid: bpy.props.BoolProperty()

    def socket_label(self, text):
        if self.is_output or (self.is_linked and self.valid) or (not self.is_output and not self.is_linked):
            return text
        else:
            return text + " [invalid]"

    def socket_color(self, color):
        if not self.is_output and self.is_linked and not self.valid:
            return (1.0, 0.0, 0.0, 1.0)
        else:
            return color

    # Returns a list of valid bl_idnames that can connect
    def valid_inputs(self):
        return [self.bl_idname]

    # Follows through reroutes
    def islinked(self):
        if self.is_linked and not self.is_output:
            try: # During link removal this can be in a weird state
                node = self.links[0].from_node
                while node.type == "REROUTE":
                    if node.inputs[0].is_linked and node.inputs[0].links[0].is_valid:
                        node = node.inputs[0].links[0].from_node
                    else:
                        return False
                return True
            except:
                pass
        return False



# Socket for an object or list of objects to be used in a bake pass in some way
class BakeWrangler_Socket_Object(BakeWrangler_Tree_Socket, NodeSocket):
    '''Socket for baking relevant objects'''
    bl_label = 'Object'

    object_types = ['MESH', 'CURVE', 'SURFACE', 'META', 'FONT', 'LIGHT']

    # Called to filter objects listed in the value search field
    def value_prop_filter(self, object):
        return self.node.input_filter(self.name, object)

    def cage_prop_filter(self, cage):
        return cage.type == 'MESH'

    # Try to auto locate the cage by name when enabled
    def use_cage_update(self, context):
        if self.use_cage and not self.cage and self.value:
            for obj in bpy.data.objects:
                if obj.name.startswith(self.value.name) and obj.name.lower().startswith("cage", len(self.value.name) + 1):
                    self.cage = obj
                    break

    # Called when the value property changes
    def value_prop_update(self, context):
        self.type = 'NONE'
        if self.value:
            if self.value.rna_type.identifier == 'Collection':
                self.type = 'GROUP'
            elif self.value.rna_type.identifier == 'Object':
                if self.value.type in self.object_types:
                    self.type = '%s_DATA' % (self.value.type)
        if self.node:
            self.node.update_inputs()

    # Get own objects or the full linked tree
    def get_objects(self, only_mesh=False, no_lights=False, only_groups=False):
        objects = []
        # Follow links
        if self.islinked() and self.valid:
            return follow_input_link(self.links[0]).from_node.get_objects(only_mesh, no_lights, only_groups)
        # Otherwise return self values
        if self.value and self.type and self.type != 'NONE' and not self.is_linked:
            # Only interested in mesh types?
            if self.type not in ['MESH_DATA', 'GROUP'] and only_mesh:
                return []
            if self.type == 'LIGHT_DATA' and no_lights:
                return []
            if only_groups and self.type != 'GROUP':
                return []
            # Need to get all the grouped objects
            if self.type == 'GROUP':
                filter = list(self.object_types)
                if no_lights:
                    filter.remove('LIGHT')
                if only_mesh:
                    filter = ['MESH']
                # Iterate over the objects applying the type filter
                for obj in self.get_grouped():
                    if obj.type in filter:
                        objects.append([obj])
                if only_groups:
                    return [[self.value, objects]]
            # Mesh data can have a few extra properties
            elif self.type == 'MESH_DATA':
                uv_map = ""
                if self.pick_uv and self.uv_map:
                    uv_map = self.uv_map
                cage = None
                if self.use_cage and self.cage:
                    cage = self.cage
                objects.append([self.value, uv_map, cage])
            else:
                objects.append([self.value])
        return objects

    # Return objects contained in a group
    def get_grouped(self):
        if self.recursive:
            return self.value.all_objects
        else:
            return self.value.objects

    # Validate value(s)
    def validate(self, check_materials=False, check_as_active=False, check_multi=False):
        valid = [True]
        # Follow links
        if self.islinked() and self.valid:
            return follow_input_link(self.links[0]).from_node.validate(check_materials, check_as_active, check_multi)
        # Has a value and isn't linked
        if self.value and self.type and not self.islinked():
            objs = [self.value]
            if self.type == 'GROUP':
                objs = self.get_grouped()

            # Iterate over objs, it will just be one object unless the type is group (but maintains a single algo for both)
            for obj in objs:
                # Perform checks needed for an active bake target
                if check_as_active:
                    # Only a mesh type object can be a valid target, it will just be silently ignored
                    if obj.type != 'MESH':
                        return valid
                    # Any UV map?
                    if len(obj.data.uv_layers) < 1:
                        valid[0] = False
                        valid.append([_print("UV error", node=self.node, ret=True), ": No UV Maps found on object <%s>." % (obj.name)])
                    # Custom UV map still exists? (can't be done for grouped objects)
                    if self.type != 'GROUP' and self.pick_uv and self.uv_map not in obj.data.uv_layers and self.uv_map != "":
                        valid[0] = False
                        valid.append([_print("UV error", node=self.node, ret=True), ": Selected UV map <%s> not present on object <%s> (it could have been deleted or renamed)" % (self.uv_map, obj.name)])
                    # Check for a valid multi-res mod if enabled
                    if check_multi:
                        has_multi_mod = False
                        if len(obj.modifiers):
                            for mod in obj.modifiers:
                                if mod.type == 'MULTIRES' and mod.total_levels > 0:
                                    has_multi_mod = True
                                    break
                        if not has_multi_mod:
                            valid[0] = False
                            valid.append([_print("Multires error", node=self.node, ret=True), ": No multires data on object <%s>." % (obj.name)])
                # Check that materials can be converted to enable PBR data bakes
                if check_materials and obj.type in self.object_types:
                    mats = []
                    if len(obj.material_slots):
                        for slot in obj.material_slots:
                            mat = slot.material
                            if mat != None and not mat in mats:
                                mats.append(mat)
                                # Is node based?
                                if not mat.node_tree or not mat.node_tree.nodes:
                                    valid.append([_print("Material warning", node=self.node, ret=True), ": <%s> not a node based material" % (mat.name)])
                                    continue
                                # Is a 'principled' material?
                                passed = False
                                for node in mat.node_tree.nodes:
                                    if node.type == 'OUTPUT_MATERIAL' and node.target in ['CYCLES', 'ALL']:
                                        if material_recursor(node):
                                            passed = True
                                            break
                                if not passed:
                                    valid.append([_print("Material warning", node=self.node, ret=True), ": <%s> Output doesn't appear to be a valid combination of Principled and Mix/Add shaders. Baked values may not be correct for this material." % (mat.name)])
        return valid

    # Blender Properties
    value: bpy.props.PointerProperty(name="Object", description="Object to be used in some way in a bake pass", type=bpy.types.ID, poll=value_prop_filter, update=value_prop_update)
    type: bpy.props.StringProperty(name="Type", description="ID String of value type", default="NONE")
    recursive: bpy.props.BoolProperty(name="Recursive Selection", description="When enabled all collections within the selected collection will be used", default=False)
    pick_uv: bpy.props.BoolProperty(name="Pick UV Map", description="Enables selecting which UV map to use instead of the active one", default=False)
    uv_map: bpy.props.StringProperty(name="UV Map", description="UV Map to use instead of active if value is a mesh", default="")
    use_cage: bpy.props.BoolProperty(name="Use Cage", description="Enables cage usage and selection of cage mesh", default=False, update=use_cage_update)
    cage: bpy.props.PointerProperty(name="Cage", description="Mesh to use a cage", type=bpy.types.Object, poll=cage_prop_filter)

    def draw(self, context, layout, node, text):
        if not self.is_output and not self.islinked() and not self.node.bl_idname == 'BakeWrangler_Bake_Material':
            row = layout.row(align=True)
            label = ""
            if self.name in ['Target', 'Source', 'Scene']:
                split_fac = 44 / self.node.width
                split = row.split(factor=split_fac)
                rowl = split.row(align=True)
                rowl.label(text=self.name)
                row = split.row(align=True)
            if self.name in ['Target', 'Source'] or (hasattr(node, "filter_collection") and not node.filter_collection):
                row.prop_search(self, "value", bpy.data, "objects", text=label, icon=self.type)
            else:
                row.prop_search(self, "value", bpy.data, "collections", text=label, icon=self.type)
            if self.value and self.type:
                if self.type == 'GROUP':
                    row.prop(self, "recursive", icon='OUTLINER', text="")
                if self.type == 'MESH_DATA':
                    row.prop(self, "pick_uv", icon='UV', text="")
                    if self.pick_uv:
                        row.prop_search(self, "uv_map", self.value.data, "uv_layers", text="", icon='UV_DATA')
                    row.prop(self, "use_cage", icon='FILE_VOLUME', text="")
                    if self.use_cage:
                        row.prop_search(self, "cage", bpy.data, "objects", text="", icon='MESH_DATA')
        elif self.is_output:
            row = layout.row(align=False)
            row0 = row.row()
            row0.ui_units_x = 50
            op = row0.operator("bake_wrangler.add_selected")
            op.tree = self.node.id_data.name
            op.node = self.node.name
            row2 = row.row(align=False)
            row2.alignment = 'RIGHT'
            row2.label(text=BakeWrangler_Tree_Socket.socket_label(self, text))
        else:
            layout.label(text=BakeWrangler_Tree_Socket.socket_label(self, text))


    def draw_color(self, context, node):
        return BakeWrangler_Tree_Socket.socket_color(self, (0.0, 0.2, 1.0, 1.0))


# Socket for materials baking
class BakeWrangler_Socket_Material(BakeWrangler_Tree_Socket, NodeSocket):
    '''Socket for specifying a material to bake'''
    bl_label = 'Material'
    
    # Called when the value property changes
    def value_prop_update(self, context):
        if self.node:
            self.node.update_inputs()
            
    value: bpy.props.PointerProperty(name="Material", description="Material to be used in a bake pass", type=bpy.types.Material, update=value_prop_update)
    
    def draw(self, context, layout, node, text):
        if not self.is_output:
            row = layout.row(align=True)
            split_fac = 52 / self.node.width
            split = row.split(factor=split_fac)
            rowl = split.row(align=True)
            rowl.label(text=self.name)
            rowr = split.row(align=True)
            rowr.prop_search(self, "value", bpy.data, "materials", icon='MATERIAL_DATA', text="")
        else:
            layout.label(text=BakeWrangler_Tree_Socket.socket_label(self, text))

    def draw_color(self, context, node):
        if self.is_output:
            return BakeWrangler_Tree_Socket.socket_color(self, (0.0, 0.5, 1.0, 1.0))
        return BakeWrangler_Tree_Socket.socket_color(self, (0.0, 0.0, 0.0, 0.0))


# Socket for sharing a target mesh
class BakeWrangler_Socket_Mesh(BakeWrangler_Tree_Socket, NodeSocket):
    '''Socket for connecting a mesh node'''
    bl_label = 'Mesh'
    
    # Returns a list of valid bl_idnames that can connect
    def valid_inputs(self):
        return [self.bl_idname, 'BakeWrangler_Socket_Material']
        
    def draw(self, context, layout, node, text):
        if node.bl_idname == 'BakeWrangler_Bake_Pass':
            if self.islinked() and self.valid:
                if get_input(self).bl_idname == 'BakeWrangler_Bake_Material':
                    label = "Material"
                else:
                    label = "Mesh"
            else:
                label = "Mesh / Material"
            layout.label(text=BakeWrangler_Tree_Socket.socket_label(self, label))
        else:
            layout.label(text=BakeWrangler_Tree_Socket.socket_label(self, text))

    def draw_color(self, context, node):
        return BakeWrangler_Tree_Socket.socket_color(self, (0.0, 0.5, 1.0, 1.0))


# Socket for RGB(A) data, extends the base color node
class BakeWrangler_Socket_Color(NodeSocketColor, BakeWrangler_Tree_Socket):
    '''Socket for RGB(A) data'''
    bl_label = 'Color'
    
    # Returns a list of valid bl_idnames that can connect
    def valid_inputs(self):
        return [self.bl_idname, 'BakeWrangler_Socket_Float']
        
    #Props
    suffix: bpy.props.StringProperty(name="Suffix", description="Suffix appended to filename for this output")
    value_rgb: bpy.props.FloatVectorProperty(name="Color", subtype='COLOR', soft_min=0.0, soft_max=1.0, step=10, default=[0.5,0.5,0.5,1.0], size=4)

    def draw(self, context, layout, node, text):
        if self.is_linked and self.valid and node.bl_idname in ['BakeWrangler_Output_Image_Path', 'BakeWrangler_Output_Vertex_Cols']:
            row = layout.row(align=True)
            sfac = 40 / node.width
            split = row.split(factor=sfac)
            if node.bl_idname == 'BakeWrangler_Output_Image_Path':
                split.label(text="Suffix")
            else:
                split.label(text="Name")
            srow = split.row(align=True)
            srow.prop(self, "suffix", text="")
            idx = 0
            for input in node.inputs:
                if input == self:
                    break
                idx += 1
            BakeWrangler_Tree_Node.draw_bake_button(node, srow, 'IMAGE', "", True, idx)
        elif node.bl_idname == 'BakeWrangler_Post_MixRGB' and not self.is_linked and not self.is_output:
            layout.prop(self, "value_rgb", text=self.name)
        else:
            layout.label(text=BakeWrangler_Tree_Socket.socket_label(self, text))

    def draw_color(self, context, node):
        return BakeWrangler_Tree_Socket.socket_color(self, (0.78, 0.78, 0.16, 1.0))


# Socket to map input value to output channel. Works like a separator/combiner node pair
class BakeWrangler_Socket_ChanMap(NodeSocketColor, BakeWrangler_Tree_Socket):
    '''Socket for splitting and joining color channels'''
    bl_label = 'Channel Map'

    # Returns a list of valid bl_idnames that can connect
    def valid_inputs(self):
        return ['BakeWrangler_Socket_Color']

    channels = (
        ('Red', "Red", "Red"),
        ('Green', "Green", "Green"),
        ('Blue', "Blue", "Blue"),
        ('Value', "Value", "Value"),
    )

    # Props
    input_channel: bpy.props.EnumProperty(name="Input Channel", description="Channel of input color data to take values from", items=channels, default='Value')

    def draw(self, context, layout, node, text):
        row = layout.row(align=True)
        label = row.row()
        if not self.is_output and self.is_linked and self.valid:
            chan = row.row()
            chan.prop(self, "input_channel", text="From")
        label.label(text=BakeWrangler_Tree_Socket.socket_label(self, text))

    def draw_color(self, context, node):
        if self.name == 'Alpha':
            return BakeWrangler_Tree_Socket.socket_color(self, (0.631, 0.631, 0.631, 1.0))
        else:
            return BakeWrangler_Tree_Socket.socket_color(self, (0.78, 0.78, 0.16, 1.0))


# Socket for Float data, extends the base float node
class BakeWrangler_Socket_Float(NodeSocketFloat, BakeWrangler_Tree_Socket):
    '''Socket for Float data'''
    bl_label = 'Float'
    
    # Returns a list of valid bl_idnames that can connect
    def valid_inputs(self):
        return [self.bl_idname, 'BakeWrangler_Socket_Color']
    
    value_fac: bpy.props.FloatProperty(name="Fac", default=0.5, subtype='FACTOR', min=0.0, max=1.0, precision=3, step=10)
    value_col: bpy.props.FloatProperty(name="Fac", soft_min=0.0, soft_max=1.0, precision=3, step=10)
    value_gam: bpy.props.FloatProperty(name="Fac", default=1.0, min=0.0, soft_min=0.001, soft_max=10.0, precision=3, step=1)
    value: bpy.props.FloatProperty(name="Value", precision=3, step=10)
    
    def draw(self, context, layout, node, text):
        if node.bl_idname == 'BakeWrangler_Post_MixRGB' and not self.islinked() and not self.is_output:
            layout.prop(self, "value_fac")
        elif node.bl_idname == 'BakeWrangler_Post_JoinRGB' and not self.islinked() and not self.is_output:
            layout.prop(self, "value_col", text=self.name)
        elif node.bl_idname == 'BakeWrangler_Post_Math' and not self.islinked() and not self.is_output:
            if node.op == 'POWER':
                if self.identifier == '0':
                    layout.prop(self, "value", text="Base")
                elif self.identifier == '1':
                    layout.prop(self, "value", text="Exponent")
            elif node.op == 'LOGARITHM' and self.identifier == '1':
                layout.prop(self, "value", text="Base")
            else:
                layout.prop(self, "value", text=self.name)
        elif node.bl_idname == 'BakeWrangler_Post_Gamma' and not self.islinked() and not self.is_output:
            layout.prop(self, "value_gam", text=self.name)
        else:
            layout.label(text=BakeWrangler_Tree_Socket.socket_label(self, text))

    def draw_color(self, context, node):
        return BakeWrangler_Tree_Socket.socket_color(self, (0.631, 0.631, 0.631, 1.0))


# Socket for connecting an output image to a batch job node
class BakeWrangler_Socket_Bake(BakeWrangler_Tree_Socket, NodeSocket):
    '''Socket for connecting an output image node to a batch node'''
    bl_label = 'Bake'

    def draw(self, context, layout, node, text):
        row = layout.row(align=True)
        if self.is_output:
            row0 = row.row()
            row0.ui_units_x = 50
            row1 = row.row(align=False)
            row1.alignment = 'RIGHT'
            if self.node.bl_idname == 'BakeWrangler_Output_Image_Path':
                BakeWrangler_Tree_Node.draw_bake_button(self.node, row0, 'IMAGE', "Bake Image")
            elif self.node.bl_idname == 'BakeWrangler_Output_Vertex_Cols':
                BakeWrangler_Tree_Node.draw_bake_button(self.node, row0, 'IMAGE', "Bake Colors")
            row1.label(text=BakeWrangler_Tree_Socket.socket_label(self, text))
        else:
            row.label(text=BakeWrangler_Tree_Socket.socket_label(self, text))

    def draw_color(self, context, node):
        return BakeWrangler_Tree_Socket.socket_color(self, (1.0, 0.5, 1.0, 1.0))


# Socket for connecting a mesh settings node to a mesh
class BakeWrangler_Socket_MeshSetting(BakeWrangler_Tree_Socket, NodeSocket):
    '''Socket for connecting a mesh settings node to a mesh node'''
    bl_label = 'Mesh Settings'

    def draw(self, context, layout, node, text):
        row = layout.row(align=False)
        if self.is_output:
            row0 = row.row()
            row1 = row.row(align=False)
            row1.alignment = 'RIGHT'
            row1.ui_units_x = 100
            if self.node.pinned:
                row0.prop(self.node, "pinned", toggle=True, icon="PINNED", text="")
            else:
                row0.prop(self.node, "pinned", toggle=True, icon="UNPINNED", text="")
            row1.label(text=BakeWrangler_Tree_Socket.socket_label(self, text))
        else:
            row.label(text=BakeWrangler_Tree_Socket.socket_label(self, text))

    def draw_color(self, context, node):
        return BakeWrangler_Tree_Socket.socket_color(self, (1.0, 0.3, 0.0, 1.0))


# Socket for connecting a pass settings node to a pass
class BakeWrangler_Socket_PassSetting(BakeWrangler_Tree_Socket, NodeSocket):
    '''Socket for connecting a pass settings node to a pass node'''
    bl_label = 'Pass Settings'

    # Returns a list of valid bl_idnames that can connect
    def valid_inputs(self):
        return [self.bl_idname, 'BakeWrangler_Socket_SampleSetting']
        
    def draw(self, context, layout, node, text):
        row = layout.row(align=False)
        if self.is_output:
            row0 = row.row()
            row1 = row.row(align=False)
            row1.alignment = 'RIGHT'
            row1.ui_units_x = 100
            if self.node.pinned:
                row0.prop(self.node, "pinned", toggle=True, icon="PINNED", text="")
            else:
                row0.prop(self.node, "pinned", toggle=True, icon="UNPINNED", text="")
            row1.label(text=BakeWrangler_Tree_Socket.socket_label(self, text))
        elif not self.is_linked:
            split = row.split(factor=0.35)
            split.label(text=BakeWrangler_Tree_Socket.socket_label(self, text))
            split.prop(self.node, "bake_samples", text="Samples")
        else:
            row.label(text=BakeWrangler_Tree_Socket.socket_label(self, text))

    def draw_color(self, context, node):
        return BakeWrangler_Tree_Socket.socket_color(self, (0.37, 0.08, 1.0, 1.0))


# Socket for connecting a pass settings node to a pass
class BakeWrangler_Socket_SampleSetting(BakeWrangler_Tree_Socket, NodeSocket):
    '''Socket for connecting a pass settings node to a pass node'''
    bl_label = 'Sample Settings'

    def draw(self, context, layout, node, text):
        row = layout.row(align=False)
        if self.is_output:
            row0 = row.row()
            row1 = row.row(align=False)
            row1.alignment = 'RIGHT'
            row1.ui_units_x = 100
            if self.node.pinned:
                row0.prop(self.node, "pinned", toggle=True, icon="PINNED", text="")
            else:
                row0.prop(self.node, "pinned", toggle=True, icon="UNPINNED", text="")
            row1.label(text=BakeWrangler_Tree_Socket.socket_label(self, text))
        else:
            row.label(text=BakeWrangler_Tree_Socket.socket_label(self, text))

    def draw_color(self, context, node):
        return BakeWrangler_Tree_Socket.socket_color(self, (0.4, 0.08, 1.0, 1.0))
        
        
# Socket for connecting an output settings node to an output
class BakeWrangler_Socket_OutputSetting(BakeWrangler_Tree_Socket, NodeSocket):
    '''Socket for connecting an output settings node to an output node'''
    bl_label = 'Output Settings'

    def draw(self, context, layout, node, text):
        row = layout.row(align=False)
        if self.is_output:
            row0 = row.row()
            row1 = row.row(align=False)
            row1.alignment = 'RIGHT'
            row1.ui_units_x = 100
            if self.node.pinned:
                row0.prop(self.node, "pinned", toggle=True, icon="PINNED", text="")
            else:
                row0.prop(self.node, "pinned", toggle=True, icon="UNPINNED", text="")
            row1.label(text=BakeWrangler_Tree_Socket.socket_label(self, text))
        else:
            row.label(text=BakeWrangler_Tree_Socket.socket_label(self, text))

    def draw_color(self, context, node):
        return BakeWrangler_Tree_Socket.socket_color(self, (0.14, 1.0, 1.0, 1.0))


# Socket that takes the names of all objects input to use for filename outputs
class BakeWrangler_Socket_ObjectNames(BakeWrangler_Tree_Socket, NodeSocket):
    '''Take the names of input objects'''
    bl_label = 'Object Names'
    
    # Returns a list of valid bl_idnames that can connect
    def valid_inputs(self):
        return ['BakeWrangler_Socket_Mesh', 'BakeWrangler_Socket_Object', 'BakeWrangler_Socket_Material']
    
    def draw(self, context, layout, node, text):
        layout.label(text=BakeWrangler_Tree_Socket.socket_label(self, text))
    
    def draw_color(self, context, node):
        return BakeWrangler_Tree_Socket.socket_color(self, (0.0, 0.5, 1.0, 1.0))


# Socket to take objects to use for splitting output into separate files
class BakeWrangler_Socket_SplitOutput(BakeWrangler_Tree_Socket, NodeSocket):
    '''Split output into files based on input'''
    bl_label = 'Split Output'
    
    # Returns a list of valid bl_idnames that can connect
    def valid_inputs(self):
        if not self.name == "Path/Filename":
            return [self.bl_idname, 'BakeWrangler_Socket_Mesh', 'BakeWrangler_Socket_Object', 'BakeWrangler_Socket_Material']
        return [None]
    
    # Get what ever the split list input node is, if there is one
    def get_split(self):
        linked = get_input(self)
        if linked:
            if linked.bl_idname == 'BakeWrangler_Input_Filenames':
                return linked.get_names()
            return [linked]
        return None        
    
    # Get full path, removing any relative references
    def get_full_path(self):
        linked = get_input(self)
        if linked and linked.bl_idname == 'BakeWrangler_Input_Filenames':
            return linked.inputs["Path/Filename"].get_full_path()
        cwd = os.path.dirname(bpy.data.filepath)
        self.img_path = os.path.normpath(os.path.join(cwd, bpy.path.abspath(self.disp_path)))
        return self.img_path

    # Deal with any path components that may be in the filename and remove recognised extensions
    def update_filename(self, context):
        if self.img_name == "":
            return
        fullpath = os.path.normpath(bpy.path.abspath(self.img_name))
        path, name = os.path.split(fullpath)
        if path:
            self.disp_path = self.img_name[:-len(name)]
        if name:
            # Remove file extension if recognised
            nname, ext = os.path.splitext(name)
            if ext not in [".", "", None]:
                for enum, iext in self.img_ext:
                    if ext.lower() == iext:
                        name = nname
                        break
            if self.img_name != name:
                self.img_name = name
    
    # Return the file name with the correct image type extension (unless it has an existing unknown extension)
    def name_with_ext(self, suffix="", type=""):
        linked = get_input(self)
        if linked and linked.bl_idname == 'BakeWrangler_Input_Filenames':
            return linked.inputs["Path/Filename"].name_with_ext(suffix, type)
        for enum, iext in self.img_ext:
            if type == enum:
                return (self.img_name + suffix + iext)
                
    def frame_range(self, padding=False, animated=False, pdata=False):
        linked = get_input(self)
        if linked and linked.bl_idname == 'BakeWrangler_Input_Filenames':
            return linked.get_frames(padding, animated, pdata)
        if padding: return None
        elif animated: return False
        else: return []
                
    def get_path(self):
        linked = get_input(self)
        if linked and  linked.bl_idname == 'BakeWrangler_Input_Filenames':
            return linked.inputs["Path/Filename"].get_path()
        return self.disp_path
        
    def get_name(self):
        linked = get_input(self)
        if linked and  linked.bl_idname == 'BakeWrangler_Input_Filenames':
            return linked.inputs["Path/Filename"].get_name()
        return self.img_name
        
    def use_tokens(self):
        linked = get_input(self)
        if linked and linked.bl_idname == 'BakeWrangler_Input_Filenames':
            return linked.inputs["Path/Filename"].tokens
            
    # Properties
    disp_path: bpy.props.StringProperty(name="Output Path", description="Path to save image in", default="", subtype='DIR_PATH')
    img_path: bpy.props.StringProperty(name="Output Path", description="Path to save image in", default="", subtype='DIR_PATH')
    img_name: bpy.props.StringProperty(name="Output File", description="File prefix to save image as", default="Image", subtype='FILE_PATH', update=update_filename)
    tokens: bpy.props.BoolProperty(name="Use Token Substitution", description="All occurrences of <OBJECT>, <SUFFIX>, <UDIM> and <FRAME> in the file name will be replaced with the current values. Missing tokens will be omitted from the name giving full control over namings", default=False)
        
    img_ext = (
        ('BMP', ".bmp"),
        ('IRIS', ".rgb"),
        ('PNG', ".png"),
        ('JPEG', ".jpg"),
        ('JPEG2000', ".jp2"),
        ('TARGA', ".tga"),
        ('TARGA_RAW', ".tga"),
        ('CINEON', ".cin"),
        ('DPX', ".dpx"),
        ('OPEN_EXR_MULTILAYER', ".exr"),
        ('OPEN_EXR', ".exr"),
        ('HDR', ".hdr"),
        ('TIFF', ".tif"),
    )
    
    def draw(self, context, layout, node, text):
        colpath = layout.column(align=True)
        linked = get_input(self)
        if node.bl_idname == 'BakeWrangler_Output_Image_Path' and linked and linked.bl_idname == 'BakeWrangler_Input_Filenames':
            colpath.label(text="Path: " + linked.inputs["Path/Filename"].get_path())
            colpath.label(text="Name: " + linked.inputs["Path/Filename"].get_name())
        elif not self.is_output:
            colpath.prop(self, "disp_path", text="")
            rowname = colpath.row(align=True)
            rowname.prop(self, "img_name", text="")
        else:
            layout.label(text=BakeWrangler_Tree_Socket.socket_label(self, text))
    
    def draw_color(self, context, node):
        if self.node.bl_idname == 'BakeWrangler_Input_Filenames' and not self.is_output:
            return BakeWrangler_Tree_Socket.socket_color(self, (0.0, 0.0, 0.0, 0.0))
        return BakeWrangler_Tree_Socket.socket_color(self, (0.0, 0.35, 1.0, 1.0))


# Socket for connecting a mesh settings node to a mesh
class BakeWrangler_Socket_Setting(BakeWrangler_Tree_Socket, NodeSocket):
    '''Socket for connecting a settings node'''
    bl_label = 'Settings'
    
    # Returns a list of valid bl_idnames that can connect
    def valid_inputs(self):
        return [self.bl_idname, 'BakeWrangler_Socket_SampleSetting', 'BakeWrangler_Socket_MeshSetting', 'BakeWrangler_Socket_PassSetting', 'BakeWrangler_Socket_OutputSetting']
    
    def draw(self, context, layout, node, text):
        row = layout.row(align=False)
        if self.is_output:
            row0 = row.row()
            row1 = row.row(align=False)
            row1.alignment = 'RIGHT'
            row1.ui_units_x = 100
            if self.node.pinned:
                row0.prop(self.node, "pinned", toggle=True, icon="PINNED", text="")
            else:
                row0.prop(self.node, "pinned", toggle=True, icon="UNPINNED", text="")
            row1.label(text=BakeWrangler_Tree_Socket.socket_label(self, text))
        elif not self.is_linked:
            split = row.split(factor=0.35)
            split.label(text=BakeWrangler_Tree_Socket.socket_label(self, text))
            split.prop(self.node, "bake_samples", text="Samples")
        else:
            row.label(text=BakeWrangler_Tree_Socket.socket_label(self, text))

    def draw_color(self, context, node):
        return BakeWrangler_Tree_Socket.socket_color(self, (0.14, 1.0, 1.0, 1.0))
 

# Custom Nodes:

# Base class for all bakery nodes. Identifies that they belong in the bakery tree.
class BakeWrangler_Tree_Node:
    # Tree version that created the node
    tree_version: bpy.props.IntProperty(name="Tree Version", default=0)
    def init(self, context):
        self.tree_version = BW_TREE_VERSION
        
    @classmethod
    def poll(cls, ntree):
        return ntree.bl_idname == 'BakeWrangler_Tree'

    def get_name(self):
        name = self.name
        #if self.label:
        #    name += ".%s" % (self.label)
        return name

    def validate(self, inputs=False, endl=False):
        if not inputs:
            return [True]
        valid = [True]
        # Validate inputs
        has_valid_input = False
        for input in self.inputs:
            if input.islinked() and input.valid:
                input_valid = get_input(input).validate()
                valid[0] = input_valid.pop(0)
                if valid[0]:
                    has_valid_input = True
                valid += input_valid
        errs = len(valid)
        if not has_valid_input and errs < 2:
            if endl: return valid
            valid[0] = False
            valid.append([_print("Input error", node=self, ret=True), ": No valid inputs connected"])
        return valid

    # Makes sure there is always one empty input socket at the bottom by adding and removing sockets
    def update_inputs(self, socket_type=None, socket_name=None, sub_socket_dict=None, noRem=False):
        if socket_type is None or self.tree_version != BW_TREE_VERSION:
            return
        idx = 0
        sub = 0
        if sub_socket_dict:
            sub = len(sub_socket_dict.keys())
        for socket in self.inputs:
            if socket.bl_idname != socket_type:
                idx = idx + 1
                continue
            if socket.is_linked or (hasattr(socket, 'value') and socket.value):
                if len(self.inputs) == idx + 1 + sub:
                    self.inputs.new(socket_type, socket_name)
                    if sub_socket_dict:
                        for key in sub_socket_dict.keys():
                            self.inputs.new(sub_socket_dict[key], key)
            else:
                if not noRem and len(self.inputs) > idx + 1 + sub:
                    self.inputs.remove(socket)
                    rem = idx
                    idx = idx - 1
                    if sub_socket_dict:
                        for key in sub_socket_dict.keys():
                            self.inputs.remove(self.inputs[rem])
                            idx = idx - 1
            idx = idx + 1

    # Update inputs and links on updates
    def update(self):
        if self.tree_version != BW_TREE_VERSION:
            return
        self.update_inputs()
        # Links can get inserted without calling insert_link, but update is called.
        for socket in self.inputs:
            if socket.islinked():
                self.insert_link(socket.links[0])

    # Validate incoming links
    def insert_link(self, link):
        if link.to_node == self:
            if follow_input_link(link).from_socket.bl_idname in link.to_socket.valid_inputs() and link.is_valid:
                link.to_socket.valid = True
            else:
                link.to_socket.valid = False
    
    # Draw a double/halve button set
    def draw_double_halve(self, layout, value):
        op = layout.operator("bake_wrangler.double_val", icon='SORT_DESC', text="")
        BakeWrangler_Operator_DoubleVal.set_props(op, self.name, self.id_data.name, value)
        op = layout.operator("bake_wrangler.double_val", icon='SORT_ASC', text="")
        BakeWrangler_Operator_DoubleVal.set_props(op, self.name, self.id_data.name, value, True)
    
    # Draw bake button in correct state
    def draw_bake_button(self, layout, icon, label, icon_only=False, socket=-1):
        is_self = False
        baking_valid = False
        try:
            if self.id_data.baking:
                baking_valid = True
                if self.id_data.baking.node == self.name:
                    is_self = True
        except ReferenceError:
            is_self = False
            baking_valid = False

        if baking_valid:
            if is_self:
                if self.id_data.baking.stop(kill=False):
                    if icon_only:
                        stext = ""
                    else:
                        stext = "Stopping..."
                    layout.operator("bake_wrangler.dummy", icon='CANCEL', text=stext)
                else:
                    if icon_only:
                        stext = ""
                    else:
                        stext = "Cancel Bake"
                    op = layout.operator("bake_wrangler.bake_stop", icon='CANCEL', text=stext)
                    op.tree = self.id_data.name
                    op.node = self.name
                    op.sock = socket
            else:
                layout.operator("bake_wrangler.dummy", icon=icon, text=label)
        else:
            op = layout.operator("bake_wrangler.bake_pass", icon=icon, text=label)
            op.tree = self.id_data.name
            op.node = self.name
            op.sock = socket


# All settings which are not pass specific
class BakeWrangler_Settings(BakeWrangler_Tree_Node, Node):
    '''Settings node'''
    bl_label = 'Settings'
    bl_width_default = 173

    # Inputs are static (none)
    def update_inputs(self):
        pass

    # Only one of this node can be pinned at a time
    def pin_node(self, context):
        if self.pinned:
            tree = self.id_data
            for node in tree.nodes:
                if node != self and node.bl_idname == 'BakeWrangler_Settings':
                    node.pinned = False
    
    def copy(self, node):
        self.pinned = False
        
    # Update output nodes to display alpha input or not depending on setting
    def check_alpha(self, context):
        tree = self.id_data
        for node in tree.nodes:
            if node.bl_idname == 'BakeWrangler_Output_Image_Path':
                node.update_inputs()
                    
    # Props
    cycles_devices = (
        ('CPU', "CPU", "Use CPU for baking"),
        ('GPU', "GPU", "Use GPU for baking"),
    )
    
    tile_sizes = (
        ('DEF', "Default", "Use Bake Wrangler default"),
        ('IMG', "Bake Size", "Use size of bake as tile size"),
        ('CUST', "Custom", "Enter your own custom tile size"),
    )
    
    pinned: bpy.props.BoolProperty(name="Pin", description="When pinned, use settings globally in node tree", default=False, update=pin_node)
    show_mesh: bpy.props.BoolProperty(name="Mesh Settings", description="Show or hide settings", default=False)
    show_pass: bpy.props.BoolProperty(name="Pass Settings", description="Show or hide settings", default=False)
    show_outp: bpy.props.BoolProperty(name="Output Settings", description="Show or hide settings", default=False)
    adv_pass: bpy.props.BoolProperty(name="Pass Advanced Settings", description="Show or hide advanced settings", default=False)
    adv_outp: bpy.props.BoolProperty(name="Output Advanced Settings", description="Show or hide advanced settings", default=False)
    show_samp: bpy.props.BoolProperty(name="Sample Settings", description="Show or hide settings", default=False)
    
    ### Mesh Props ###
    ray_dist: bpy.props.FloatProperty(name="Ray Distance", description="Distance to use for inward ray cast when using a selected to active bake", default=0.01, step=1, min=0.0, unit='LENGTH')
    max_ray_dist: bpy.props.FloatProperty(name="Max Ray Dist", description="The maximum ray distance for matching points between the active and selected objects. If zero, there is no limit", default=0.0, step=1, min=0.0, unit='LENGTH')
    margin: bpy.props.IntProperty(name="Margin", description="Extends the baked result as a post process filter", default=0, min=0, subtype='PIXEL')
    margin_extend: bpy.props.BoolProperty(name="Extend", description="Margin extends border pixels outward (instead of taking values from adjacent faces)", default=True)
    margin_auto: bpy.props.BoolProperty(name="Auto Margin", description="Automatically set margin size based on smallest dimension of texture", default=True)
    #mask_margin: bpy.props.IntProperty(name="Mask Margin", description="Adds extra padding to the mask bake. Use if edge details are being cut off when masking is enabled", default=0, min=0, subtype='PIXEL')
    auto_cage: bpy.props.BoolProperty(name="Auto Cage", description="Automatically generate a cage for objects that don't have one set", default=False)
    acage_expansion: bpy.props.FloatProperty(name="Cage Expansion", description="Distance to expand automatically generated cage geometry from original object", default=0.02, step=0.01, precision=3, unit='LENGTH')
    acage_smooth: bpy.props.IntProperty(name="Cage Smoothing Angle", description="Angle range that automatic normal smoothing will be applied to", default=179)
    material_replace: bpy.props.BoolProperty(name="Material Override", description="Replace all materials on selected objects with the specified material (objects without a material will have it added)", default=False)
    material_override: bpy.props.PointerProperty(name="Override Material", description="Material that will be used in place of all other materials", type=bpy.types.Material)
    material_osl: bpy.props.BoolProperty(name="OSL", description="Material uses an OSL shader node", default=False)
    bake_mods: bpy.props.BoolProperty(name="Bake Mods to Unmodded", description="Modifiers with viewport visibility enabled will be stripped from Target objects and a copy with those modifiers applied will be created and used as the Source object (Disable viewport visibility on a modifier to exclude it - this setting can be inverted in the add-on preferences if you prefer the visibilty setting to work the other way)", default=False)
    
    ### Pass Props ###
    res_bake_x: bpy.props.IntProperty(name="Bake X resolution ", description="Width (X) to bake maps at", default=2048, min=1, subtype='PIXEL')
    res_bake_y: bpy.props.IntProperty(name="Bake Y resolution ", description="Height (Y) to bake maps at", default=2048, min=1, subtype='PIXEL')
    bake_device: bpy.props.EnumProperty(name="Device", description="Bake device", items=cycles_devices, default='CPU')
    interpolate: bpy.props.BoolProperty(name="Interpolate", description="Use cubic interpolation between baked pixel and output pixel, creating a soft anti-aliasing effect", default=False)

    use_world: bpy.props.BoolProperty(name="Use World", description="Enabled to pick a world to use (empty to use active), instead of Bake Wranglers default", default=False)
    the_world: bpy.props.PointerProperty(name="World", description="World to use instead of Bake Wranglers default (empty to use active)", type=bpy.types.World)
    cpy_render: bpy.props.BoolProperty(name="Copy Settings", description="Copy render settings from selected scene (empty to use active), instead of using defaults", default=False)
    cpy_from: bpy.props.PointerProperty(name="Render Scene", description="Scene to copy render settings from (empty to use active)", type=bpy.types.Scene)
    render_tile: bpy.props.IntProperty(name="Tiles", description="Render tile size", default=2048, min=8, subtype='PIXEL')
    use_tiles: bpy.props.EnumProperty(name="Tiles", description="Render tile size", items=tile_sizes, default='DEF')
    render_threads: bpy.props.IntProperty(name="Threads", description="Maximum number of CPU cores to use simultaneously (set to zero for automatic)", default=0, min=0, max=1024)
    use_bg_col: bpy.props.BoolProperty(name="BG Color", description="Background color for blank areas", default=False)
    bg_color: bpy.props.FloatVectorProperty(name="BG Color", description="Background color used in blank areas", subtype='COLOR', soft_min=0.0, soft_max=1.0, step=10, default=[0.0,0.0,0.0,1.0], size=4)
    
    ### Output Props ###
    # Recreate image format drop down as the built in one doesn't seem usable? Also most of the settings
    # for the built in image settings selector don't seem applicable to saving from script...
    img_format = (
        ('BMP', "BMP", "Output image in bitmap format."),
        ('IRIS', "Iris", "Output image in (old!) SGI IRIS format."),
        ('PNG', "PNG", "Output image in PNG format."),
        ('JPEG', "JPEG", "Output image in JPEG format."),
        ('JPEG2000', "JPEG 2000", "Output image in JPEG 2000 format."),
        ('TARGA', "Targa", "Output image in Targa format."),
        ('TARGA_RAW', "Targa Raw", "Output image in uncompressed Targa format."),
        ('CINEON', "Cineon", "Output image in Cineon format."),
        ('DPX', "DPX", "Output image in DPX format."),
        ('OPEN_EXR_MULTILAYER', "OpenEXR MultiLayer", "Output image in multilayer OpenEXR format."),
        ('OPEN_EXR', "OpenEXR", "Output image in OpenEXR format."),
        ('HDR', "Radiance HDR", "Output image in Radiance HDR format."),
        ('TIFF', "TIFF", "Output image in TIFF format."),
    )

    img_color_modes = (
        ('BW', "BW", "Image saved in 8 bit grayscale"),
        ('RGB', "RGB", "Image saved with RGB (color) data"),
        ('RGBA', "RGBA", "Image saved with RGB and Alpha data"),
    )

    img_color_modes_noalpha = (
        ('BW', "BW", "Image saved in 8 bit grayscale"),
        ('RGB', "RGB", "Image saved with RGB (color) data"),
    )

    img_color_depths_8_16 = (
        ('8', "8", "8 bit color channels"),
        ('16', "16", "16 bit color channels"),
    )

    img_color_depths_8_12_16 = (
        ('8', "8", "8 bit color channels"),
        ('12', "12", "12 bit color channels"),
        ('16', "16", "16 bit color channels"),
    )

    img_color_depths_8_10_12_16 = (
        ('8', "8", "8 bit color channels"),
        ('10', "10", "10 bit color channels"),
        ('12', "12", "12 bit color channels"),
        ('16', "16", "16 bit color channels"),
    )

    img_color_depths_16_32 = (
        ('16', "Float (Half)", "16 bit color channels"),
        ('32', "Float (Full)", "32 bit color channels"),
    )

    img_codecs_jpeg2k = (
        ('JP2', "JP2", ""),
        ('J2K', "J2K", ""),
    )

    img_codecs_openexr = (
        ('DWAA', "DWAA (lossy)", ""),
        ('B44A', "B44A (lossy)", ""),
        ('ZIPS', "ZIPS (lossless)", ""),
        ('RLE', "RLE (lossless)", ""),
        ('RLE', "RLE (lossless)", ""),
        ('PIZ', "PIZ (lossless)", ""),
        ('ZIP', "ZIP (lossless)", ""),
        ('PXR24', "Pxr24 (lossy)", ""),
        ('NONE', "None", ""),
    )

    img_codecs_tiff = (
        ('PACKBITS', "Pack Bits", ""),
        ('LZW', "LZW", ""),
        ('DEFLATE', "Deflate", ""),
        ('NONE', "None", ""),
    )

    img_color_spaces = []
    for space in bpy.types.ColorManagedInputColorspaceSettings.bl_rna.properties['name'].enum_items.keys():
       img_color_spaces.append((space, space, space))
    img_color_spaces = tuple(img_color_spaces)
    
    img_xres: bpy.props.IntProperty(name="Image X resolution", description="Number of horizontal pixels in image. Bake pass data will be scaled to fit the image size. Power of 2 sizes are usually best for exporting", default=2048, min=1, subtype='PIXEL')
    img_yres: bpy.props.IntProperty(name="Image Y resolution", description="Number of vertical pixels in image. Bake pass data will be scaled to fit the image size. Power of 2 sizes are usually best for exporting", default=2048, min=1, subtype='PIXEL')
    img_clear: bpy.props.BoolProperty(name="Clear Image", description="Clear image before writing bake data", default=False)
    img_udim: bpy.props.BoolProperty(name="UDIM", description="Treat UV map as UDIM space and append standard number system to file name", default=False)
    img_type: bpy.props.EnumProperty(name="Image Format", description="File format to save bake as", items=img_format, default='PNG')
    fast_aa: bpy.props.BoolProperty(name="Fast Anti-Alias", description="Fast Anti-Aliasing. For more control use down or up sampling of bake to output by using different resolutions", default=False)
    fast_aa_lvl: bpy.props.IntProperty(name="Fast AA Level", description="Level of fast AA to apply from 1 to 9", default=3, min=1, max=9)

    marginer: bpy.props.BoolProperty(name="Marginer", description="Use alternative margin generator (slower)", default=False)
    marginer_size: bpy.props.IntProperty(name="Marginer Size", description="Extends the baked result as a post process filter", default=0, min=0, subtype='PIXEL')
    marginer_fill: bpy.props.BoolProperty(name="Marginer Fill", description="Fill all gaps with margin instead of using a fixed width", default=False)
    
    # Core settings
    img_color_space: bpy.props.EnumProperty(name="Color Space", description="Color space to use when saving the image", items=img_color_spaces)
    img_use_float: bpy.props.BoolProperty(name="Use 32 Bit Float", description="Generate all input passes using 32 bit floating point color (128 bits per pixel). Note this isn't very useful if your image format isn't set to a high bit depth", default=False)
    img_color_mode: bpy.props.EnumProperty(name="Color", description="Choose BW for saving grayscale images, RGB for saving red, green and blue channels, and RGBA for saving red, green, blue and alpha channels", items=img_color_modes, default='RGB', update=check_alpha)
    img_color_mode_noalpha: bpy.props.EnumProperty(name="Color", description="Choose BW for saving grayscale images, RGB for saving red, green and blue channels", items=img_color_modes_noalpha, default='RGB')
    img_non_color: bpy.props.StringProperty(name="Non Color Space", default="NONE")
    
    # Color Depths
    img_color_depth_8_16: bpy.props.EnumProperty(name="Color Depth", description="Bit depth per channel", items=img_color_depths_8_16, default='8')
    img_color_depth_8_12_16: bpy.props.EnumProperty(name="Color Depth", description="Bit depth per channel", items=img_color_depths_8_12_16, default='8')
    img_color_depth_8_10_12_16: bpy.props.EnumProperty(name="Color Depth", description="Bit depth per channel", items=img_color_depths_8_10_12_16, default='8')
    img_color_depth_16_32: bpy.props.EnumProperty(name="Color Depth", description="Bit depth per channel", items=img_color_depths_16_32, default='16')

    # Compression / Quality
    img_compression: bpy.props.IntProperty(name="Compression", description="Amount of time to determine best compression: 0 = no compression, 100 = maximum lossless compression", default=15, min=0, max=100, subtype='PERCENTAGE')
    img_quality: bpy.props.IntProperty(name="Quality", description="Quality for image formats that support lossy compression", default=90, min=0, max=100, subtype='PERCENTAGE')

    # Codecs
    img_codec_jpeg2k: bpy.props.EnumProperty(name="Codec", description="Codec settings for jpeg2000", items=img_codecs_jpeg2k, default='JP2')
    img_codec_openexr: bpy.props.EnumProperty(name="Codec", description="Codec settings for OpenEXR", items=img_codecs_openexr, default='ZIP')
    img_codec_tiff: bpy.props.EnumProperty(name="Compression", description="Compression mode for TIFF", items=img_codecs_tiff, default='DEFLATE')

    # Other random image format settings
    img_jpeg2k_cinema: bpy.props.BoolProperty(name="Cinema", description="Use Openjpeg Cinema Preset", default=True)
    img_jpeg2k_cinema48: bpy.props.BoolProperty(name="Cinema (48)", description="Use Openjpeg Cinema Preset (48 fps)", default=False)
    img_jpeg2k_ycc: bpy.props.BoolProperty(name="YCC", description="Save luminance-chrominance-chrominance channels instead of RGB colors", default=False)
    img_dpx_log: bpy.props.BoolProperty(name="Log", description="Convert to logarithmic color space", default=False)
    
    ### Samples Props ###
    bake_samples: bpy.props.IntProperty(name="Bake Samples", description="Number of samples to bake for each pixel. Use 1 for all PBR passes and Normal maps. Values over 50 generally won't improve results.\nQuality is gained by increasing resolution rather than samples past that point", default=1, min=1)
    bake_threshold: bpy.props.FloatProperty(name="Noise Threshold", description="Noise level to stop sampling at if reached before sample count", default=0.01, min=0.001, max=1.0)
    bake_usethresh: bpy.props.BoolProperty(name="Use Threshold", description="Enables use of noise level threshold", default=False)
    bake_timelimit: bpy.props.FloatProperty(name="Time Limit", description="Maximum time to spend on a single bake. Zero to disable", default=0.0, min=0.0, subtype='TIME_ABSOLUTE', unit='TIME_ABSOLUTE', step=100)
    

    def init(self, context):
        BakeWrangler_Tree_Node.init(self, context)
        # Sockets IN
        # Sockets OUT
        self.outputs.new('BakeWrangler_Socket_Setting', "Settings")
        # Mesh Prefs
        self.ray_dist = _prefs("def_raydist")
        self.max_ray_dist = _prefs("def_max_ray_dist")
        self.margin = _prefs("def_margin")
        #self.mask_margin = _prefs("def_mask_margin")
        # Pass Prefs
        self.res_bake_x = _prefs("def_xres")
        self.res_bake_y = _prefs("def_yres")
        self.bake_samples = _prefs("def_samples")
        self.bake_device = self.cycles_devices[int(_prefs("def_device"))][0]
        self.adv_pass = _prefs("def_show_adv")
        # Output Prefs
        self.img_type = self.img_format[_prefs("def_format")][0]
        self.img_xres = _prefs("def_xout")
        self.img_yres = _prefs("def_yout")
        self.adv_outp = _prefs("def_show_adv")
        self.img_color_space = bpy.data.scenes[0].sequencer_colorspace_settings.name
        # Sample Prefs
        self.bake_samples = _prefs("def_samples")
        
    def draw_buttons(self, context, layout):
        colnode = layout.column(align=False)
        
        ### Mesh Settings
        meshset = colnode.row()
        meshset.alignment = 'LEFT'
        if not self.show_mesh:
            meshset.prop(self, "show_mesh", icon="DISCLOSURE_TRI_RIGHT", emboss=False, text="Mesh Settings:")
            meshset.separator()
        else:
            meshset.prop(self, "show_mesh", icon="DISCLOSURE_TRI_DOWN", emboss=False, text="Mesh Settings:")
            meshset.separator()
            
            col = colnode.column(align=True)
            row = col.row(align=True)
            row.prop(self, "margin_auto", toggle=True, icon_only=True, icon='MOD_MESHDEFORM')
            mrg = row.row(align=True)
            mrg.prop(self, "margin")
            if self.margin_auto:
                mrg.enabled = False
            row.prop(self, "margin_extend", toggle=True, icon_only=True, icon='IMAGE_PLANE')
            #col.prop(self, "mask_margin")
            col.prop(self, "ray_dist")
            col.prop(self, "max_ray_dist")
            if not self.auto_cage:
                col.prop(self, "auto_cage", toggle=True)
            else:
                row = col.row(align=True)
                row.prop(self, "auto_cage", toggle=True)
                row.prop(self, "acage_expansion", text="")
                row.prop(self, "acage_smooth", text="")
            if not self.material_replace:
                col.prop(self, "material_replace", toggle=True)
            else:
                row = col.row(align=True)
                row.prop(self, "material_replace", toggle=True)
                row.prop_search(self, "material_override", bpy.data, "materials", text="")
                row.prop(self, "material_osl", toggle=True, icon_only=True, icon='SCRIPT')
            col.prop(self, "bake_mods", toggle=True)

        ### Pass Settings
        passset = colnode.row()
        passset.alignment = 'LEFT'
        if not self.show_pass:
            passset.prop(self, "show_pass", icon="DISCLOSURE_TRI_RIGHT", emboss=False, text="Pass Settings:")
            passset.separator()
        else:
            passset.prop(self, "show_pass", icon="DISCLOSURE_TRI_DOWN", emboss=False, text="Pass Settings:")
            passset.separator()
            
            colbasic = colnode.column(align=True)
            rowbasic = colbasic.row(align=True)
            rowbasic.prop(self, "res_bake_x", text="X")
            BakeWrangler_Tree_Node.draw_double_halve(self, rowbasic, "res_bake_x")
            rowbasic = colbasic.row(align=True)
            rowbasic.prop(self, "res_bake_y", text="Y")
            BakeWrangler_Tree_Node.draw_double_halve(self, rowbasic, "res_bake_y")
            #colbasic.prop(self, "bake_samples", text="Samples")
            colbasic.prop(self, "interpolate")
            
            split = colnode.split(factor=0.35)
            split.label(text="Device:")
            split.prop(self, "bake_device", text="")
        
        ### Advanced Pass Settings
        advrow = colnode.row()
        advrow.alignment = 'LEFT'
        if not self.adv_pass:
            advrow.prop(self, "adv_pass", icon="DISCLOSURE_TRI_RIGHT", emboss=False, text="Pass Advanced:")
            advrow.separator()
        else:
            advrow.prop(self, "adv_pass", icon="DISCLOSURE_TRI_DOWN", emboss=False, text="Pass Advanced:")
            advrow.separator()
            advcol = colnode.column(align=True)

            row = advcol.row(align=True)
            row.prop(self, "use_world", text="Use My World", toggle=True)
            if self.use_world:
                row.prop_search(self, "the_world", bpy.data, "worlds", text="")

            row = advcol.row(align=True)
            row.prop(self, "cpy_render", text="Use My Settings", toggle=True)
            if self.cpy_render:
                row.prop_search(self, "cpy_from", bpy.data, "scenes", text="")
                
            row = advcol.row(align=True)
            row.prop(self, "use_tiles")
            if self.use_tiles == 'CUST':
                row.prop(self, "render_tile", text="")
                
            row = advcol.row(align=True)
            row.prop(self, "render_threads")
            
            row = advcol.row(align=True)
            row.prop(self, "use_bg_col", toggle=True)
            if self.use_bg_col:
                row.prop(self, "bg_color", text="")
        
        ### Output Settings
        outpset = colnode.row()
        outpset.alignment = 'LEFT'
        if not self.show_outp:
            outpset.prop(self, "show_outp", icon="DISCLOSURE_TRI_RIGHT", emboss=False, text="Output Settings:")
            outpset.separator()
        else:
            outpset.prop(self, "show_outp", icon="DISCLOSURE_TRI_DOWN", emboss=False, text="Output Settings:")
            outpset.separator()
            
            colbasic = colnode.column(align=True)
            rowbasic = colbasic.row(align=True)
            rowbasic.prop(self, "img_xres", text="X")
            BakeWrangler_Tree_Node.draw_double_halve(self, rowbasic, "img_xres")
            rowbasic = colbasic.row(align=True)
            rowbasic.prop(self, "img_yres", text="Y")
            BakeWrangler_Tree_Node.draw_double_halve(self, rowbasic, "img_yres")
            rowbasic = colbasic.row(align=True)
            rowbasic.prop(self, "img_clear", text="Clear", toggle=True)
            rowbasic.prop(self, "img_udim", toggle=True)
            rowbasic = colbasic.row(align=True)
            if not self.fast_aa:
                rowbasic.prop(self, "fast_aa", toggle=True)
            if self.fast_aa:
                rowbasic.prop(self, "fast_aa", toggle=True, text="Fast AA:")
                rowbasic.prop(self, "fast_aa_lvl", text="")

            split = colnode.split(factor=0.35)
            split.label(text="Format:")
            split.prop(self, "img_type", text="")
        
        ### Advanced Output Settings
        advrow = colnode.row()
        advrow.alignment = 'LEFT'
        if not self.adv_outp:
            advrow.prop(self, "adv_outp", icon="DISCLOSURE_TRI_RIGHT", emboss=False, text="Output Advanced:")
            advrow.separator()
        else:
            advrow.prop(self, "adv_outp", icon="DISCLOSURE_TRI_DOWN", emboss=False, text="Output Advanced:")
            advrow.separator()
            coladv = colnode.column(align=True)
            
            row = coladv.row(align=True)
            if self.marginer:
                row.prop(self, "marginer", toggle=True, icon_only=True, icon='NODE_INSERT_OFF')
            else:
                row.prop(self, "marginer", toggle=True, icon='NODE_INSERT_OFF')
            if self.marginer:
                row_size = row.row(align=True)
                row_size.prop(self, "marginer_size", text="")
                if self.marginer_fill:
                    row_size.enabled = False
                row.prop(self, "marginer_fill", toggle=True, icon_only=True, icon='TPAINT_HLT')
                
            coladv.prop(self, "img_use_float", toggle=True)

            splitadv = coladv.split(factor=0.4)
            coladvtxt = splitadv.column(align=True)
            coladvopt = splitadv.column(align=True)

            # Color Spaces
            if self.img_type != 'CINEON':
                coladvtxt.label(text="Space:")
                coladvopt.prop(self, "img_color_space", text="")
            # Color Modes
            if self.img_type in ['BMP', 'JPEG', 'CINEON', 'HDR']:
                coladvtxt.label(text="Color:")
                coladvopt.prop(self, "img_color_mode_noalpha", text="")
            if self.img_type in ['IRIS', 'PNG', 'JPEG2000', 'TARGA', 'TARGA_RAW', 'DPX', 'OPEN_EXR_MULTILAYER', 'OPEN_EXR', 'TIFF']:
                coladvtxt.label(text="Color:")
                coladvopt.prop(self, "img_color_mode", text="")
            # Color Depths
            if self.img_type in ['PNG', 'TIFF']:
                coladvtxt.label(text="Depth:")
                coladvopt.prop(self, "img_color_depth_8_16", text="")
            if self.img_type == 'JPEG2000':
                coladvtxt.label(text="Depth:")
                coladvopt.prop(self, "img_color_depth_8_12_16", text="")
            if self.img_type == 'DPX':
                coladvtxt.label(text="Depth:")
                coladvopt.prop(self, "img_color_depth_8_10_12_16", text="")
            if self.img_type in ['OPEN_EXR_MULTILAYER', 'OPEN_EXR']:
                coladvtxt.label(text="Depth:")
                coladvopt.prop(self, "img_color_depth_16_32", text="")
            # Compression / Quality
            if self.img_type == 'PNG':
                coladvtxt.label(text="Compression:")
                coladvopt.prop(self, "img_compression", text="")
            if self.img_type in ['JPEG', 'JPEG2000']:
                coladvtxt.label(text="Quality:")
                coladvopt.prop(self, "img_quality", text="")
            # Codecs
            if self.img_type == 'JPEG2000':
                coladvtxt.label(text="Codec:")
                coladvopt.prop(self, "img_codec_jpeg2k", text="")
            if self.img_type in ['OPEN_EXR', 'OPEN_EXR_MULTILAYER']:
                coladvtxt.label(text="Codec:")
                coladvopt.prop(self, "img_codec_openexr", text="")
            if self.img_type == 'TIFF':
                coladvtxt.label(text="Compression:")
                coladvopt.prop(self, "img_codec_tiff", text="")
            # Other random image settings
            if self.img_type == 'JPEG2000':
                coladv.prop(self, "img_jpeg2k_cinema")
                coladv.prop(self, "img_jpeg2k_cinema48")
                coladv.prop(self, "img_jpeg2k_ycc")
            if self.img_type == 'DPX':
                coladv.prop(self, "img_dpx_log")
        
        ### Sample Settings
        sampset = colnode.row()
        sampset.alignment = 'LEFT'
        if not self.show_samp:
            sampset.prop(self, "show_samp", icon="DISCLOSURE_TRI_RIGHT", emboss=False, text="Sample Settings:")
            sampset.separator()
        else:
            sampset.prop(self, "show_samp", icon="DISCLOSURE_TRI_DOWN", emboss=False, text="Sample Settings:")
            sampset.separator()
            
            colbasic = colnode.column(align=True)
            rowbasic = colbasic.row(align=True)
            rowbasic.label(text="Noise")
            rowbasic.prop(self, "bake_usethresh", text="")
            rowbasic.prop(self, "bake_threshold", text="")
            colbasic.prop(self, "bake_samples", text="Samples")
            colbasic.prop(self, "bake_timelimit")


# Node to configure pass settings, which can be pinned as global
class BakeWrangler_MeshSettings(BakeWrangler_Tree_Node, Node):
    '''Mesh settings node'''
    bl_label = 'Mesh Settings (Depreciated)'
    bl_width_default = 173

    # Inputs are static (none)
    def update_inputs(self):
        pass

    # Only one of this node can be pinned at a time
    def pin_node(self, context):
        if self.pinned:
            tree = self.id_data
            for node in tree.nodes:
                if node != self and node.bl_idname == 'BakeWrangler_MeshSettings':
                    node.pinned = False

    # Props
    pinned: bpy.props.BoolProperty(name="Pin", description="When pinned, use settings globally in node tree", default=False, update=pin_node)
    ray_dist: bpy.props.FloatProperty(name="Ray Distance", description="Distance to use for inward ray cast when using a selected to active bake", default=0.01, step=1, min=0.0, unit='LENGTH')
    max_ray_dist: bpy.props.FloatProperty(name="Max Ray Dist", description="The maximum ray distance for matching points between the active and selected objects. If zero, there is no limit", default=0.0, step=1, min=0.0, unit='LENGTH')
    margin: bpy.props.IntProperty(name="Margin", description="Extends the baked result as a post process filter", default=0, min=0, subtype='PIXEL')
    margin_extend: bpy.props.BoolProperty(name="Extend", description="Margin extends border pixels outward (instead of taking values from adjacent faces)", default=True)
    margin_auto: bpy.props.BoolProperty(name="Auto Margin", description="Automatically set margin size based on smallest dimension of texture", default=True)
    #mask_margin: bpy.props.IntProperty(name="Mask Margin", description="Adds extra padding to the mask bake. Use if edge details are being cut off when masking is enabled", default=0, min=0, subtype='PIXEL')
    auto_cage: bpy.props.BoolProperty(name="Auto Cage", description="Automatically generate a cage for objects that don't have one set", default=False)
    acage_expansion: bpy.props.FloatProperty(name="Cage Expansion", description="Distance to expand automatically generated cage geometry from original object", default=0.02, step=0.01, precision=3, unit='LENGTH')
    acage_smooth: bpy.props.IntProperty(name="Cage Smoothing Angle", description="Angle range that automatic normal smoothing will be applied to", default=179)
    material_replace: bpy.props.BoolProperty(name="Material Override", description="Replace all materials on selected objects with the specified material (objects without a material will have it added)", default=False)
    material_override: bpy.props.PointerProperty(name="Override Material", description="Material that will be used in place of all other materials", type=bpy.types.Material)
    material_osl: bpy.props.BoolProperty(name="OSL", description="Material uses an OSL shader node", default=False)
    bake_mods: bpy.props.BoolProperty(name="Bake Mods to Unmodded", description="Modifiers with viewport visibility enabled will be stripped from Target objects and a copy with those modifiers applied will be created and used as the Source object (Disable viewport visibility on a modifier to exclude it - this setting can be inverted in the add-on preferences if you prefer the visibilty setting to work the other way)", default=False)
    
    def copy(self, node):
        self.pinned = False

    def init(self, context):
        BakeWrangler_Tree_Node.init(self, context)
        # Sockets IN (none)
        # Sockets OUT
        self.outputs.new('BakeWrangler_Socket_MeshSetting', "Mesh Settings")
        # Prefs
        self.ray_dist = _prefs("def_raydist")
        self.max_ray_dist = _prefs("def_max_ray_dist")
        self.margin = _prefs("def_margin")
        #self.mask_margin = _prefs("def_mask_margin")

    def draw_buttons(self, context, layout):
        col = layout.column(align=True)
        row = col.row(align=True)
        row.prop(self, "margin_auto", toggle=True, icon_only=True, icon='MOD_MESHDEFORM')
        mrg = row.row(align=True)
        mrg.prop(self, "margin")
        if self.margin_auto:
            mrg.enabled = False
        row.prop(self, "margin_extend", toggle=True, icon_only=True, icon='IMAGE_PLANE')
        #col.prop(self, "mask_margin")
        col.prop(self, "ray_dist")
        col.prop(self, "max_ray_dist")
        if not self.auto_cage:
            col.prop(self, "auto_cage", toggle=True)
        else:
            row = col.row(align=True)
            row.prop(self, "auto_cage", toggle=True)
            row.prop(self, "acage_expansion", text="")
            row.prop(self, "acage_smooth", text="")
        if not self.material_replace:
            col.prop(self, "material_replace", toggle=True)
        else:
            row = col.row(align=True)
            row.prop(self, "material_replace", toggle=True)
            row.prop_search(self, "material_override", bpy.data, "materials", text="")
            row.prop(self, "material_osl", toggle=True, icon_only=True, icon='SCRIPT')
        col.prop(self, "bake_mods", toggle=True)


# Node to configure pass settings, which can be pinned as global
class BakeWrangler_PassSettings(BakeWrangler_Tree_Node, Node):
    '''Pass settings node'''
    bl_label = 'Pass Settings (Depreciated)'
    bl_width_default = 144

    # Inputs are static (none)
    def update_inputs(self):
        pass

    # Only one of this node can be pinned at a time
    def pin_node(self, context):
        if self.pinned:
            tree = self.id_data
            for node in tree.nodes:
                if node != self and node.bl_idname == 'BakeWrangler_PassSettings':
                    node.pinned = False

    cycles_devices = (
        ('CPU', "CPU", "Use CPU for baking"),
        ('GPU', "GPU", "Use GPU for baking"),
    )
    
    tile_sizes = (
        ('DEF', "Default", "Use Bake Wrangler default"),
        ('IMG', "Bake Size", "Use size of bake as tile size"),
        ('CUST', "Custom", "Enter your own custom tile size"),
    )

    # Props
    pinned: bpy.props.BoolProperty(name="Pin", description="When pinned, use settings globally in node tree", default=False, update=pin_node)
    res_bake_x: bpy.props.IntProperty(name="Bake X resolution ", description="Width (X) to bake maps at", default=2048, min=1, subtype='PIXEL')
    res_bake_y: bpy.props.IntProperty(name="Bake Y resolution ", description="Height (Y) to bake maps at", default=2048, min=1, subtype='PIXEL')
    bake_device: bpy.props.EnumProperty(name="Device", description="Bake device", items=cycles_devices, default='CPU')
    interpolate: bpy.props.BoolProperty(name="Interpolate", description="Use cubic interpolation between baked pixel and output pixel, creating a soft anti-aliasing effect", default=False)

    adv_settings: bpy.props.BoolProperty(name="Advanced Settings", description="Show or hide advanced settings", default=False)
    use_world: bpy.props.BoolProperty(name="Use World", description="Enabled to pick a world to use (empty to use active), instead of Bake Wranglers default", default=False)
    the_world: bpy.props.PointerProperty(name="World", description="World to use instead of Bake Wranglers default (empty to use active)", type=bpy.types.World)
    cpy_render: bpy.props.BoolProperty(name="Copy Settings", description="Copy render settings from selected scene (empty to use active), instead of using defaults", default=False)
    cpy_from: bpy.props.PointerProperty(name="Render Scene", description="Scene to copy render settings from (empty to use active)", type=bpy.types.Scene)
    render_tile: bpy.props.IntProperty(name="Tiles", description="Render tile size", default=2048, min=8, subtype='PIXEL')
    use_tiles: bpy.props.EnumProperty(name="Tiles", description="Render tile size", items=tile_sizes, default='DEF')
    render_threads: bpy.props.IntProperty(name="Threads", description="Maximum number of CPU cores to use simultaneously (set to zero for automatic)", default=0, min=0, max=1024)
    use_bg_col: bpy.props.BoolProperty(name="BG Color", description="Background color for blank areas", default=False)
    bg_color: bpy.props.FloatVectorProperty(name="BG Color", description="Background color used in blank areas", subtype='COLOR', soft_min=0.0, soft_max=1.0, step=10, default=[0.0,0.0,0.0,1.0], size=4)
    
    def copy(self, node):
        self.pinned = False

    def init(self, context):
        BakeWrangler_Tree_Node.init(self, context)
        # Sockets IN (none)
        self.inputs.new('BakeWrangler_Socket_SampleSetting', "Samples")
        # Sockets OUT
        self.outputs.new('BakeWrangler_Socket_PassSetting', "Pass Settings")
        # Prefs
        self.res_bake_x = _prefs("def_xres")
        self.res_bake_y = _prefs("def_yres")
        self.bake_samples = _prefs("def_samples")
        self.bake_device = self.cycles_devices[int(_prefs("def_device"))][0]
        self.adv_settings = _prefs("def_show_adv")

    def draw_buttons(self, context, layout):
        colnode = layout.column(align=False)

        colbasic = colnode.column(align=True)
        rowbasic = colbasic.row(align=True)
        rowbasic.prop(self, "res_bake_x", text="X")
        BakeWrangler_Tree_Node.draw_double_halve(self, rowbasic, "res_bake_x")
        rowbasic = colbasic.row(align=True)
        rowbasic.prop(self, "res_bake_y", text="Y")
        BakeWrangler_Tree_Node.draw_double_halve(self, rowbasic, "res_bake_y")
        #colbasic.prop(self, "bake_samples", text="Samples")
        colbasic.prop(self, "interpolate")
        
        split = colnode.split(factor=0.35)
        split.label(text="Device:")
        split.prop(self, "bake_device", text="")

        advrow = colnode.row()
        advrow.alignment = 'LEFT'
        if not self.adv_settings:
            advrow.prop(self, "adv_settings", icon="DISCLOSURE_TRI_RIGHT", emboss=False, text="Advanced:")
            advrow.separator()
        else:
            advrow.prop(self, "adv_settings", icon="DISCLOSURE_TRI_DOWN", emboss=False, text="Advanced:")
            advrow.separator()
            advcol = colnode.column(align=True)

            row = advcol.row(align=True)
            row.prop(self, "use_world", text="Use My World", toggle=True)
            if self.use_world:
                row.prop_search(self, "the_world", bpy.data, "worlds", text="")

            row = advcol.row(align=True)
            row.prop(self, "cpy_render", text="Use My Settings", toggle=True)
            if self.cpy_render:
                row.prop_search(self, "cpy_from", bpy.data, "scenes", text="")
                
            row = advcol.row(align=True)
            row.prop(self, "use_tiles")
            if self.use_tiles == 'CUST':
                row.prop(self, "render_tile", text="")
                
            row = advcol.row(align=True)
            row.prop(self, "render_threads")
            
            row = advcol.row(align=True)
            row.prop(self, "use_bg_col", toggle=True)
            if self.use_bg_col:
                row.prop(self, "bg_color", text="")
            


# Node to configure pass settings, which can be pinned as global
class BakeWrangler_SampleSettings(BakeWrangler_Tree_Node, Node):
    '''Pass settings node'''
    bl_label = 'Sample Settings (Depreciated)'
    bl_width_default = 144

    # Inputs are static (none)
    def update_inputs(self):
        pass

    # Only one of this node can be pinned at a time
    def pin_node(self, context):
        if self.pinned:
            tree = self.id_data
            for node in tree.nodes:
                if node != self and node.bl_idname == 'BakeWrangler_SampleSettings':
                    node.pinned = False

    # Props
    pinned: bpy.props.BoolProperty(name="Pin", description="When pinned, use settings globally in node tree", default=False, update=pin_node)
    bake_samples: bpy.props.IntProperty(name="Bake Samples", description="Number of samples to bake for each pixel. Use 1 for all PBR passes and Normal maps. Values over 50 generally won't improve results.\nQuality is gained by increasing resolution rather than samples past that point", default=1, min=1)
    bake_threshold: bpy.props.FloatProperty(name="Noise Threshold", description="Noise level to stop sampling at if reached before sample count", default=0.01, min=0.001, max=1.0)
    bake_usethresh: bpy.props.BoolProperty(name="Use Threshold", description="Enables use of noise level threshold", default=False)
    bake_timelimit: bpy.props.FloatProperty(name="Time Limit", description="Maximum time to spend on a single bake. Zero to disable", default=0.0, min=0.0, subtype='TIME_ABSOLUTE', unit='TIME_ABSOLUTE', step=100)
    
    def copy(self, node):
        self.pinned = False

    def init(self, context):
        BakeWrangler_Tree_Node.init(self, context)
        # Sockets IN (none)
        # Sockets OUT
        self.outputs.new('BakeWrangler_Socket_SampleSetting', "Sample Settings")
        # Prefs
        self.bake_samples = _prefs("def_samples")
        
    def draw_buttons(self, context, layout):
        colnode = layout.column(align=False)

        colbasic = colnode.column(align=True)
        rowbasic = colbasic.row(align=True)
        rowbasic.label(text="Noise")
        rowbasic.prop(self, "bake_usethresh", text="")
        rowbasic.prop(self, "bake_threshold", text="")
        colbasic.prop(self, "bake_samples", text="Samples")
        colbasic.prop(self, "bake_timelimit")        
        
        
# Node to configure output settings, which can be pinned as global
class BakeWrangler_OutputSettings(BakeWrangler_Tree_Node, Node):
    '''Output settings node'''
    bl_label = 'Output Settings (Depreciated)'
    bl_width_default = 152

    # Inputs are static (none)
    def update_inputs(self):
        pass

    # Only one of this node can be pinned at a time
    def pin_node(self, context):
        if self.pinned:
            tree = self.id_data
            for node in tree.nodes:
                if node != self and node.bl_idname == 'BakeWrangler_OutputSettings':
                    node.pinned = False
                    
    # Update output nodes to display alpha input or not depending on setting
    def check_alpha(self, context):
        tree = self.id_data
        for node in tree.nodes:
            if node.bl_idname == 'BakeWrangler_Output_Image_Path':
                node.update_inputs()

    # Recreate image format drop down as the built in one doesn't seem usable? Also most of the settings
    # for the built in image settings selector don't seem applicable to saving from script...
    img_format = (
        ('BMP', "BMP", "Output image in bitmap format."),
        ('IRIS', "Iris", "Output image in (old!) SGI IRIS format."),
        ('PNG', "PNG", "Output image in PNG format."),
        ('JPEG', "JPEG", "Output image in JPEG format."),
        ('JPEG2000', "JPEG 2000", "Output image in JPEG 2000 format."),
        ('TARGA', "Targa", "Output image in Targa format."),
        ('TARGA_RAW', "Targa Raw", "Output image in uncompressed Targa format."),
        ('CINEON', "Cineon", "Output image in Cineon format."),
        ('DPX', "DPX", "Output image in DPX format."),
        ('OPEN_EXR_MULTILAYER', "OpenEXR MultiLayer", "Output image in multilayer OpenEXR format."),
        ('OPEN_EXR', "OpenEXR", "Output image in OpenEXR format."),
        ('HDR', "Radiance HDR", "Output image in Radiance HDR format."),
        ('TIFF', "TIFF", "Output image in TIFF format."),
    )

    img_color_modes = (
        ('BW', "BW", "Image saved in 8 bit grayscale"),
        ('RGB', "RGB", "Image saved with RGB (color) data"),
        ('RGBA', "RGBA", "Image saved with RGB and Alpha data"),
    )

    img_color_modes_noalpha = (
        ('BW', "BW", "Image saved in 8 bit grayscale"),
        ('RGB', "RGB", "Image saved with RGB (color) data"),
    )

    img_color_depths_8_16 = (
        ('8', "8", "8 bit color channels"),
        ('16', "16", "16 bit color channels"),
    )

    img_color_depths_8_12_16 = (
        ('8', "8", "8 bit color channels"),
        ('12', "12", "12 bit color channels"),
        ('16', "16", "16 bit color channels"),
    )

    img_color_depths_8_10_12_16 = (
        ('8', "8", "8 bit color channels"),
        ('10', "10", "10 bit color channels"),
        ('12', "12", "12 bit color channels"),
        ('16', "16", "16 bit color channels"),
    )

    img_color_depths_16_32 = (
        ('16', "Float (Half)", "16 bit color channels"),
        ('32', "Float (Full)", "32 bit color channels"),
    )

    img_codecs_jpeg2k = (
        ('JP2', "JP2", ""),
        ('J2K', "J2K", ""),
    )

    img_codecs_openexr = (
        ('DWAA', "DWAA (lossy)", ""),
        ('B44A', "B44A (lossy)", ""),
        ('ZIPS', "ZIPS (lossless)", ""),
        ('RLE', "RLE (lossless)", ""),
        ('RLE', "RLE (lossless)", ""),
        ('PIZ', "PIZ (lossless)", ""),
        ('ZIP', "ZIP (lossless)", ""),
        ('PXR24', "Pxr24 (lossy)", ""),
        ('NONE', "None", ""),
    )

    img_codecs_tiff = (
        ('PACKBITS', "Pack Bits", ""),
        ('LZW', "LZW", ""),
        ('DEFLATE', "Deflate", ""),
        ('NONE', "None", ""),
    )

    img_color_spaces = []
    for space in bpy.types.ColorManagedInputColorspaceSettings.bl_rna.properties['name'].enum_items.keys():
       img_color_spaces.append((space, space, space))
    img_color_spaces = tuple(img_color_spaces)
    
    # Props
    pinned: bpy.props.BoolProperty(name="Pin", description="When pinned, use settings globally in node tree", default=False, update=pin_node)
    img_xres: bpy.props.IntProperty(name="Image X resolution", description="Number of horizontal pixels in image. Bake pass data will be scaled to fit the image size. Power of 2 sizes are usually best for exporting", default=2048, min=1, subtype='PIXEL')
    img_yres: bpy.props.IntProperty(name="Image Y resolution", description="Number of vertical pixels in image. Bake pass data will be scaled to fit the image size. Power of 2 sizes are usually best for exporting", default=2048, min=1, subtype='PIXEL')
    img_clear: bpy.props.BoolProperty(name="Clear Image", description="Clear image before writing bake data", default=False)
    img_udim: bpy.props.BoolProperty(name="UDIM", description="Treat UV map as UDIM space and append standard number system to file name", default=False)
    img_type: bpy.props.EnumProperty(name="Image Format", description="File format to save bake as", items=img_format, default='PNG')
    fast_aa: bpy.props.BoolProperty(name="Fast Anti-Alias", description="Fast Anti-Aliasing. For more control use down or up sampling of bake to output by using different resolutions", default=False)
    fast_aa_lvl: bpy.props.IntProperty(name="Fast AA Level", description="Level of fast AA to apply from 1 to 9", default=3, min=1, max=9)

    marginer: bpy.props.BoolProperty(name="Marginer", description="Use alternative margin generator (slower)", default=False)
    marginer_size: bpy.props.IntProperty(name="Marginer Size", description="Extends the baked result as a post process filter", default=0, min=0, subtype='PIXEL')
    marginer_fill: bpy.props.BoolProperty(name="Marginer Fill", description="Fill all gaps with margin instead of using a fixed width", default=False)
    
    adv_settings: bpy.props.BoolProperty(name="Advanced Settings", description="Display or hide advanced settings", default=False)

    # Core settings
    img_color_space: bpy.props.EnumProperty(name="Color Space", description="Color space to use when saving the image", items=img_color_spaces)
    img_use_float: bpy.props.BoolProperty(name="Use 32 Bit Float", description="Generate all input passes using 32 bit floating point color (128 bits per pixel). Note this isn't very useful if your image format isn't set to a high bit depth", default=False)
    img_color_mode: bpy.props.EnumProperty(name="Color", description="Choose BW for saving grayscale images, RGB for saving red, green and blue channels, and RGBA for saving red, green, blue and alpha channels", items=img_color_modes, default='RGB', update=check_alpha)
    img_color_mode_noalpha: bpy.props.EnumProperty(name="Color", description="Choose BW for saving grayscale images, RGB for saving red, green and blue channels", items=img_color_modes_noalpha, default='RGB')
    img_non_color: bpy.props.StringProperty(name="Non Color Space", default="NONE")
    
    # Color Depths
    img_color_depth_8_16: bpy.props.EnumProperty(name="Color Depth", description="Bit depth per channel", items=img_color_depths_8_16, default='8')
    img_color_depth_8_12_16: bpy.props.EnumProperty(name="Color Depth", description="Bit depth per channel", items=img_color_depths_8_12_16, default='8')
    img_color_depth_8_10_12_16: bpy.props.EnumProperty(name="Color Depth", description="Bit depth per channel", items=img_color_depths_8_10_12_16, default='8')
    img_color_depth_16_32: bpy.props.EnumProperty(name="Color Depth", description="Bit depth per channel", items=img_color_depths_16_32, default='16')

    # Compression / Quality
    img_compression: bpy.props.IntProperty(name="Compression", description="Amount of time to determine best compression: 0 = no compression, 100 = maximum lossless compression", default=15, min=0, max=100, subtype='PERCENTAGE')
    img_quality: bpy.props.IntProperty(name="Quality", description="Quality for image formats that support lossy compression", default=90, min=0, max=100, subtype='PERCENTAGE')

    # Codecs
    img_codec_jpeg2k: bpy.props.EnumProperty(name="Codec", description="Codec settings for jpeg2000", items=img_codecs_jpeg2k, default='JP2')
    img_codec_openexr: bpy.props.EnumProperty(name="Codec", description="Codec settings for OpenEXR", items=img_codecs_openexr, default='ZIP')
    img_codec_tiff: bpy.props.EnumProperty(name="Compression", description="Compression mode for TIFF", items=img_codecs_tiff, default='DEFLATE')

    # Other random image format settings
    img_jpeg2k_cinema: bpy.props.BoolProperty(name="Cinema", description="Use Openjpeg Cinema Preset", default=True)
    img_jpeg2k_cinema48: bpy.props.BoolProperty(name="Cinema (48)", description="Use Openjpeg Cinema Preset (48 fps)", default=False)
    img_jpeg2k_ycc: bpy.props.BoolProperty(name="YCC", description="Save luminance-chrominance-chrominance channels instead of RGB colors", default=False)
    img_dpx_log: bpy.props.BoolProperty(name="Log", description="Convert to logarithmic color space", default=False)

    def copy(self, node):
        self.pinned = False

    def init(self, context):
        BakeWrangler_Tree_Node.init(self, context)
        # Sockets IN (none)
        # Sockets OUT
        self.outputs.new('BakeWrangler_Socket_OutputSetting', "Output Settings")
        # Prefs
        self.img_type = self.img_format[_prefs("def_format")][0]
        self.img_xres = _prefs("def_xout")
        self.img_yres = _prefs("def_yout")
        self.adv_settings = _prefs("def_show_adv")
        self.img_color_space = bpy.data.scenes[0].sequencer_colorspace_settings.name

    def draw_buttons(self, context, layout):
        colnode = layout.column(align=False)

        colbasic = colnode.column(align=True)
        rowbasic = colbasic.row(align=True)
        rowbasic.prop(self, "img_xres", text="X")
        BakeWrangler_Tree_Node.draw_double_halve(self, rowbasic, "img_xres")
        rowbasic = colbasic.row(align=True)
        rowbasic.prop(self, "img_yres", text="Y")
        BakeWrangler_Tree_Node.draw_double_halve(self, rowbasic, "img_yres")
        rowbasic = colbasic.row(align=True)
        rowbasic.prop(self, "img_clear", text="Clear", toggle=True)
        rowbasic.prop(self, "img_udim", toggle=True)
        rowbasic = colbasic.row(align=True)
        if not self.fast_aa:
            rowbasic.prop(self, "fast_aa", toggle=True)
        if self.fast_aa:
            rowbasic.prop(self, "fast_aa", toggle=True, text="Fast AA:")
            rowbasic.prop(self, "fast_aa_lvl", text="")

        split = colnode.split(factor=0.35)
        split.label(text="Format:")
        split.prop(self, "img_type", text="")

        advrow = colnode.row()
        advrow.alignment = 'LEFT'
        if not self.adv_settings:
            advrow.prop(self, "adv_settings", icon="DISCLOSURE_TRI_RIGHT", emboss=False, text="Advanced:")
            advrow.separator()
        else:
            advrow.prop(self, "adv_settings", icon="DISCLOSURE_TRI_DOWN", emboss=False, text="Advanced:")
            advrow.separator()
            coladv = colnode.column(align=True)
            
            row = coladv.row(align=True)
            if self.marginer:
                row.prop(self, "marginer", toggle=True, icon_only=True, icon='NODE_INSERT_OFF')
            else:
                row.prop(self, "marginer", toggle=True, icon='NODE_INSERT_OFF')
            if self.marginer:
                row_size = row.row(align=True)
                row_size.prop(self, "marginer_size", text="")
                if self.marginer_fill:
                    row_size.enabled = False
                row.prop(self, "marginer_fill", toggle=True, icon_only=True, icon='TPAINT_HLT')
                
            coladv.prop(self, "img_use_float", toggle=True)

            splitadv = coladv.split(factor=0.4)
            coladvtxt = splitadv.column(align=True)
            coladvopt = splitadv.column(align=True)

            # Color Spaces
            if self.img_type != 'CINEON':
                coladvtxt.label(text="Space:")
                coladvopt.prop(self, "img_color_space", text="")
            # Color Modes
            if self.img_type in ['BMP', 'JPEG', 'CINEON', 'HDR']:
                coladvtxt.label(text="Color:")
                coladvopt.prop(self, "img_color_mode_noalpha", text="")
            if self.img_type in ['IRIS', 'PNG', 'JPEG2000', 'TARGA', 'TARGA_RAW', 'DPX', 'OPEN_EXR_MULTILAYER', 'OPEN_EXR', 'TIFF']:
                coladvtxt.label(text="Color:")
                coladvopt.prop(self, "img_color_mode", text="")
            # Color Depths
            if self.img_type in ['PNG', 'TIFF']:
                coladvtxt.label(text="Depth:")
                coladvopt.prop(self, "img_color_depth_8_16", text="")
            if self.img_type == 'JPEG2000':
                coladvtxt.label(text="Depth:")
                coladvopt.prop(self, "img_color_depth_8_12_16", text="")
            if self.img_type == 'DPX':
                coladvtxt.label(text="Depth:")
                coladvopt.prop(self, "img_color_depth_8_10_12_16", text="")
            if self.img_type in ['OPEN_EXR_MULTILAYER', 'OPEN_EXR']:
                coladvtxt.label(text="Depth:")
                coladvopt.prop(self, "img_color_depth_16_32", text="")
            # Compression / Quality
            if self.img_type == 'PNG':
                coladvtxt.label(text="Compression:")
                coladvopt.prop(self, "img_compression", text="")
            if self.img_type in ['JPEG', 'JPEG2000']:
                coladvtxt.label(text="Quality:")
                coladvopt.prop(self, "img_quality", text="")
            # Codecs
            if self.img_type == 'JPEG2000':
                coladvtxt.label(text="Codec:")
                coladvopt.prop(self, "img_codec_jpeg2k", text="")
            if self.img_type in ['OPEN_EXR', 'OPEN_EXR_MULTILAYER']:
                coladvtxt.label(text="Codec:")
                coladvopt.prop(self, "img_codec_openexr", text="")
            if self.img_type == 'TIFF':
                coladvtxt.label(text="Compression:")
                coladvopt.prop(self, "img_codec_tiff", text="")
            # Other random image settings
            if self.img_type == 'JPEG2000':
                coladv.prop(self, "img_jpeg2k_cinema")
                coladv.prop(self, "img_jpeg2k_cinema48")
                coladv.prop(self, "img_jpeg2k_ycc")
            if self.img_type == 'DPX':
                coladv.prop(self, "img_dpx_log")



# File names input to allow attaching prefixes to outputs and make object->filename system more intuitive
class BakeWrangler_Input_Filenames(BakeWrangler_Tree_Node, Node):
    '''File Names node'''
    bl_label = 'File Names'
    bl_width_default = 198
    
    def get_names(self):
        names = []
        for input in self.inputs:
            if input.bl_idname == 'BakeWrangler_Socket_ObjectNames' and get_input(input):
                names.append(get_input(input))
        return names
    
    def get_frames(self, padding=False, animated=False, pdata=False):
        if animated: return self.use_rnd_seed
        if pdata: return self.pdata
        frames = []
        pad = None
        # Parse string
        ranges = self.frame_ranges.split(sep=",")
        import re
        extract = re.compile(r'(\D*#([0-9]*)\D*)|(\D*([0-9]*)-?([0-9]*):?([0-9]*)\D*)')
        for arange in ranges:
            match = extract.match(arange)
            if match.group(1) and padding:
                pad = int(match.group(2))
            elif match.group(3) and not padding:
                start = int(match.group(4))
                end = int(match.group(5)) if match.group(5) else None
                step = int(match.group(6)) if match.group(6) else 1
                if end:
                    if end < start:
                        step *= -1
                        end -= 1
                    else: end +=1
                    for f in range(start, end, step): frames.append(f)
                else:
                    frames.append(start)
            else: continue
        if padding:
            return pad
        return set(frames)

    def update_inputs(self):
        BakeWrangler_Tree_Node.update_inputs(self, 'BakeWrangler_Socket_ObjectNames', "Object Names")
        
    # Props
    frame_ranges: bpy.props.StringProperty(name="Frame Ranges", description="Comma separated list of frame ranges to bake with optional step size (eg: 1,3, 4-12, 12-24:4). For non-default zero padding include #number_of_zeros as one of your ranges (eg: #3,1-3,10 to pad all numbers to 3). Frame numbers are added to the end of file names", default="")
    use_rnd_seed: bpy.props.BoolProperty(name="Use Animated Seed", description="Use different seed values (and hence noise patterns) at different frames", default=True)
    pdata: bpy.props.BoolProperty(name="Persistent Data", description="Keep render data between frames reducing render times at the cost of memory usage", default=True)
        
    def init(self, context):
        BakeWrangler_Tree_Node.init(self, context)
        # Sockets IN
        self.inputs.new('BakeWrangler_Socket_SplitOutput', "Path/Filename")
        self.inputs.new('BakeWrangler_Socket_ObjectNames', "Object Names")
        # Sockets OUT
        self.outputs.new('BakeWrangler_Socket_SplitOutput', "Path / Filenames / Frames")
        
    def draw_buttons(self, context, layout):
        col = layout.column(align=True)
        row0 = col.row()
        row0.label(text="Frame Ranges:")
        row1 = col.row(align=True)
        row1.prop(self, "frame_ranges", text="")
        row1.prop(self, "use_rnd_seed", text="", icon='TIME')
        row1.prop(self, "pdata", text="", icon='GHOST_ENABLED')
        row2 = col.row()
        row2.prop(self.inputs["Path/Filename"], "tokens")


    
# Input node that contains a list of objects relevant to baking
class BakeWrangler_Input_ObjectList(BakeWrangler_Tree_Node, Node):
    '''Object list node'''
    bl_label = 'Objects'
    bl_width_default = 198

    # Makes sure there is always one empty input socket at the bottom by adding and removing sockets
    def update_inputs(self):
        BakeWrangler_Tree_Node.update_inputs(self, 'BakeWrangler_Socket_Object', "Object", noRem=True)

    # Determine if object meets current input filter
    def input_filter(self, input_name, object):
        if self.filter_collection:
            if object.rna_type.identifier == 'Collection':
                return True
        elif object.rna_type.identifier == 'Object':
            if (self.filter_mesh and object.type == 'MESH') or \
               (self.filter_curve and object.type == 'CURVE') or \
               (self.filter_surface and object.type == 'SURFACE') or \
               (self.filter_meta and object.type == 'META') or \
               (self.filter_font and object.type == 'FONT') or \
               (self.filter_light and object.type == 'LIGHT'):
                return True
        return False

    # Get all objects in tree from this node (mostly just uses the sockets methods)
    def get_objects(self, only_mesh=False, no_lights=False, only_groups=False):
        objects = []
        for input in self.inputs:
            in_objs = input.get_objects(only_mesh, no_lights, only_groups)
            if len(in_objs):
                objects += in_objs
        return objects

    # Validate all objects in tree from this node (mostly just uses the sockets methods)
    def validate(self, check_materials=False, check_as_active=False, check_multi=False):
        valid = [True]
        for input in self.inputs:
            valid_input = input.validate(check_materials, check_as_active, check_multi)
            if not valid_input.pop(0):
                valid[0] = False
            if len(valid_input):
                valid += valid_input
        return valid

    filter_mesh: bpy.props.BoolProperty(name="Meshes", description="Show mesh type objects", default=True)
    filter_curve: bpy.props.BoolProperty(name="Curves", description="Show curve type objects", default=True)
    filter_surface: bpy.props.BoolProperty(name="Surfaces", description="Show surface type objects", default=True)
    filter_meta: bpy.props.BoolProperty(name="Metas", description="Show meta type objects", default=True)
    filter_font: bpy.props.BoolProperty(name="Fonts", description="Show font type objects", default=True)
    filter_light: bpy.props.BoolProperty(name="Lights", description="Show light type objects", default=True)
    filter_collection: bpy.props.BoolProperty(name="Collections", description="Toggle only collections", default=False)
    
    def copy(self, node):
        pass

    def init(self, context):
        BakeWrangler_Tree_Node.init(self, context)
        # Sockets IN
        self.inputs.new('BakeWrangler_Socket_Object', "Object")
        # Sockets OUT
        self.outputs.new('BakeWrangler_Socket_Object', "Objects")
        # Prefs
        self.filter_mesh = _prefs("def_filter_mesh")
        self.filter_curve = _prefs("def_filter_curve")
        self.filter_surface = _prefs("def_filter_surface")
        self.filter_meta = _prefs("def_filter_meta")
        self.filter_font = _prefs("def_filter_font")
        self.filter_light = _prefs("def_filter_light")
        self.filter_collection = _prefs("def_filter_collection")

    def draw_buttons(self, context, layout):
        row = layout.row(align=True)
        row0 = row.row()
        row0.label(text="Filter:")

        row1 = row.row(align=True)
        row1.alignment = 'RIGHT'
        for fltr in BakeWrangler_Operator_FilterToggle.filters:
            icn = fltr.split("_")[1].upper() + "_DATA"
            op = row1.operator("bake_wrangler.filter_toggle", icon=icn, text="", depress=getattr(self, fltr))
            op.tree = self.id_data.name
            op.node = self.name
            op.filter = fltr
        if self.filter_collection:
            row1.enabled = False

        row2 = row.row(align=False)
        row2.alignment = 'RIGHT'
        row2.prop(self, "filter_collection", text="", icon='GROUP')



# Automatic sorting of meshes into groups for baking
class BakeWrangler_Sort_Meshes(BakeWrangler_Tree_Node, Node):
    '''Sorting and grouping of meshes by name'''
    bl_label = 'Auto Sort Meshes'
    bl_width_default = 240
    
    # Inputs are static on this node
    def update_inputs(self):
        BakeWrangler_Tree_Node.update_inputs(self, 'BakeWrangler_Socket_Mesh', "Mesh")
    
    # Try to get nodes settings from local or global node
    def get_settings(self, validating=False, input=None):
        if input:
            settings = get_input(input)
            if settings:
                return settings.get_settings()
        return {}
    
    # Check node settings are valid to bake. Returns true/false, plus error message.
    def validate(self, check_materials=False, multires=False):
        valid = [True]
        has_valid_input = False
        for inpt in self.inputs:
            if inpt.islinked() and inpt.valid:
                mesh = get_input(inpt)
                if mesh:
                    input_valid = mesh.validate(check_materials, multires)
                    if not input_valid.pop(0):
                        valid[0] = False
                    else:
                        has_valid_input = True
                    if len(input_valid):
                        valid += input_valid
        if not has_valid_input and len(valid) < 2:
            valid[0] = False
            valid.append([_print("Input error", node=self, ret=True), ": No valid inputs connected"])
        return valid
    
    # Return name with ident removed or empty string if ident not in name
    def find_ident(self, type, name, ident, case_sens=True):
        if type == 'PASS' or not ident:
            return name
        ident_idx = 0
        ident_len = len(ident)
        cname = name
        cident = ident
        if not case_sens:
            cname = name.lower()
            cident = ident.lower()
        if type == 'STARTS':
            if not cname.startswith(cident):
                return ''
            else: return name[ident_len:]
        elif type == 'ENDS':
            if not cname.endswith(cident):
                return ''
            else: return name[:-ident_len]
        elif type in ['SCONTAINS', 'ECONTAINS']:
            if type == 'SCONTAINS':
                ident_idx = cname.find(cident)
            if type == 'ECONTAINS':
                ident_idx = cname.rfind(cident)
            if ident_idx == -1:
                return ''
            else: return name[:ident_idx] + name[ident_idx + ident_len:]
        
    # Return a list of object pairings
    def get_objects(self, set, input):
        objs = []
        mesh = get_input(input)
        if not mesh:
            return []
        if set == 'TARGET' and 'Target' in mesh.inputs.keys():
            targets = prune_objects(mesh.inputs["Target"].get_objects(only_mesh=True), True)
            sources = prune_objects(mesh.inputs["Source"].get_objects(no_lights=True))
            sourgrp = prune_objects(mesh.inputs["Source"].get_objects(no_lights=True, only_groups=True))
            scenes  = prune_objects(mesh.inputs["Scene"].get_objects())
            scengrp = prune_objects(mesh.inputs["Scene"].get_objects(only_groups=True))
            if not len(sources) and self.high_search != 'PASS':
                sources = prune_objects(mesh.inputs["Target"].get_objects(no_lights=True))
                sourgrp = prune_objects(mesh.inputs["Target"].get_objects(no_lights=True, only_groups=True))
            
            # Create pairings of high to low, first ident possible low polys
            for obj in targets:
                low_name = self.find_ident(self.low_search, obj[0].name, self.low_string, self.low_case)
                high_obj = []
                scen_obj = []
                if not low_name: continue
                # Create the high poly name string based on the possible low objects name
                if self.high_search == 'PASS':
                    high_obj = sources
                else:
                    if self.high_collect:
                        for high in sourgrp:
                            high_name = self.find_ident(self.high_search, high[0].name, self.high_string, self.high_case)
                            if high_name == low_name:
                                high_obj += high[1]
                    if not len(high_obj):
                        for high in sources:
                            high_name = self.find_ident(self.high_search, high[0].name, self.high_string, self.high_case)
                            if high_name == low_name:
                                high_obj.append(high)
                # Check scene objects (if no scene string is set, scene is included as is)
                if self.scene_search == 'PASS':
                    scen_obj = scenes
                else:
                    if self.scene_collect:
                        for scen in scengrp:
                            scen_name = self.find_ident(self.scene_search, scen[0].name, self.scene_string, self.scene_case)
                            if scen_name == low_name:
                                scen_obj += scen[1]
                    if not len(scen_obj):
                        for scen in scenes:
                            scen_name = self.find_ident(self.scene_search, scen[0].name, self.scene_string, self.scene_case)
                            if scen_name == low_name:
                                scen_obj.append(scen)
                # Only paired objects will be added
                if (len(high_obj) and self.high_search != 'PASS') or (len(scen_obj) and self.scene_search != 'PASS') or self.low_search == 'PASS':
                    objs.append([obj, high_obj, scen_obj, low_name])
        else: pass

        # Return pruned object list
        return objs
    
    # Get a list of unique objects used as either source or target
    def get_unique_objects(self, type, for_auto_cage=False, input=None):
        if type not in ['TARGET', 'SOURCE']:
            return []
        objs_set = []
        objs = self.get_objects('TARGET', input)
        if len(objs):
            if for_auto_cage:
                settings = self.get_settings(input=input)
                if not settings['auto_cage']:
                    return []
            for obj in objs:
                if type == 'TARGET':
                    if for_auto_cage:
                        if len(obj[0]) > 2 and obj[0][2]:
                            continue
                        objs_set.append([obj[0][0], settings['acage_expansion'], settings['acage_smooth']])
                    else:
                        objs_set.append(obj[0])
                elif type == 'SOURCE':
                    objs_set.append(obj[1])
                else:
                    return []
        return objs_set        
    
    search_type = (
        ('PASS', "Pass Through", "Pass all items through without doing any matching", 'ANIM', 0),
        ('STARTS', "Starts", "Starts with ID", 'TRIA_RIGHT', 1),
        ('ENDS', "Ends", "Ends with ID", 'TRIA_LEFT', 2),
        ('SCONTAINS', "Contains ->", "Contains ID, searching from start", 'NEXT_KEYFRAME', 3),
        ('ECONTAINS', "Contains <-", "Contains ID, searching from end", 'PREV_KEYFRAME', 4),
    )
    
    low_search: bpy.props.EnumProperty(name="Target Search", description="How to search for target identifier", items=search_type, default='PASS')
    low_string: bpy.props.StringProperty(name="Target Ident", description="Target identifier")
    low_case: bpy.props.BoolProperty(name="Target case sensitivity", description="Use case sensitive matching", default=True)
    high_string: bpy.props.StringProperty(name="Source Ident", description="Source identifier")
    high_search: bpy.props.EnumProperty(name="Source Search", description="How to search for source identifier", items=search_type, default='PASS')
    high_collect: bpy.props.BoolProperty(name="Match Collections", description="Try to match a source collection before trying the items inside it", default=True)
    high_case: bpy.props.BoolProperty(name="Source case sensitivity", description="Use case sensitive matching", default=True)
    scene_string: bpy.props.StringProperty(name="Scene Ident", description="Scene identifier")
    scene_search: bpy.props.EnumProperty(name="Scene Search", description="How to search for scene identifier", items=search_type, default='PASS')
    scene_collect: bpy.props.BoolProperty(name="Match Collections", description="Try to match a scene collection before trying the items inside it", default=True)
    scene_case: bpy.props.BoolProperty(name="Scene case sensitivity", description="Use case sensitive matching", default=True)
    
    show_groupings: bpy.props.BoolProperty(name="Show Groupings", default=False)
    
    def init(self, context):
        BakeWrangler_Tree_Node.init(self, context)
        # Sockets IN
        self.inputs.new('BakeWrangler_Socket_Mesh', "Mesh")
        # Sockets OUT
        self.outputs.new('BakeWrangler_Socket_Mesh', "Mesh")
    
    def draw_buttons(self, context, layout):
        colnode = layout.column(align=True)
        split_fac = 60 / self.width
        split = colnode.split(factor=split_fac)
        split.label(text="Target ID:")
        row = split.row(align=True)
        row1 = row.row(align=True)
        row2 = row.row(align=True)
        row1.prop(self, "low_string", text="")
        row1.prop(self, "low_case", text="", icon_only=True, icon='SMALL_CAPS')
        row2.prop(self, "low_search", text="", icon_only=True)
        if self.low_search == 'PASS':
            row1.enabled = False
        
        split = colnode.split(factor=split_fac)
        split.label(text="Source ID:")
        row = split.row(align=True)
        row1 = row.row(align=True)
        row2 = row.row(align=True)
        row1.prop(self, "high_string", text="")
        row1.prop(self, "high_collect", text="", icon_only=True, icon='OUTLINER_COLLECTION')
        row1.prop(self, "high_case", text="", icon_only=True, icon='SMALL_CAPS')
        row2.prop(self, "high_search", text="", icon_only=True)
        if self.high_search == 'PASS':
            row1.enabled = False
        
        split = colnode.split(factor=split_fac)
        split.label(text="Scene ID:")
        row = split.row(align=True)
        row1 = row.row(align=True)
        row2 = row.row(align=True)
        row1.prop(self, "scene_string", text="")
        row1.prop(self, "scene_collect", text="", icon_only=True, icon='OUTLINER_COLLECTION')
        row1.prop(self, "scene_case", text="", icon_only=True, icon='SMALL_CAPS')
        row2.prop(self, "scene_search", text="", icon_only=True)
        if self.scene_search == 'PASS':
            row1.enabled = False
            
    def draw_buttons_ext(self, context, layout):
        layout.prop(self, 'show_groupings')
        if self.show_groupings:
            for input in self.inputs:
                mesh = get_input(input)
                if mesh:
                    layout.label(text=mesh.get_name())
                    box = layout.box()
                    for obj_grp in self.get_objects('TARGET', input):
                        boxin = box.box()
                        col = boxin.column(align=True)
                        row = col.row()
                        row.label(text=obj_grp[0][0].name)
                        row.label(text="", icon=obj_grp[0][0].type + '_DATA')
                        col.label(text="-Source:")
                        for hi in obj_grp[1]:
                            row = col.row()
                            row.label(text="  " + hi[0].name)
                            row.label(text="", icon=hi[0].type + '_DATA')
                        col.label(text="-Scene:")
                        for scen in obj_grp[2]:
                            row = col.row()
                            row.label(text="  " + scen[0].name)
                            row.label(text="", icon=scen[0].type + '_DATA')



# Settings to be used when baking a billboard
class BakeWrangler_Bake_Billboard(BakeWrangler_Tree_Node, Node):
    '''Mesh input node'''
    bl_label = 'Input Billboard'
    bl_width_default = 240

    # Inputs are static on this node
    def update_inputs(self):
        pass

    # Determine if object meets current input filter
    def input_filter(self, input_name, object):
        if input_name == "Target":
            if object.type == 'MESH':
                return True
        elif input_name == "Source":
            if object.type in ['MESH', 'CURVE', 'SURFACE', 'META', 'FONT']:
                return True
        return False

    # Try to get nodes settings from local or global node
    def get_settings(self, validating=False):
        settings = get_input(self.inputs["Settings"])
        if not settings:
            settings = self.id_data.get_pinned_settings("MeshSettings")
        if validating:
            return settings
        mesh_settings = {}
        mesh_settings['ray_dist']           = 0
        mesh_settings['max_ray_dist']       = 0
        mesh_settings['margin']             = settings.margin
        mesh_settings['margin_extend']      = settings.margin_extend
        mesh_settings['margin_auto']        = settings.margin_auto
        #mesh_settings['marginer']           = settings.marginer
        #mesh_settings['marginer_fill']      = settings.marginer_fill
        #mesh_settings['mask_margin']        = settings.mask_margin
        mesh_settings['auto_cage']          = False
        mesh_settings['acage_expansion']    = 0
        mesh_settings['acage_smooth']       = 0
        mesh_settings['material_replace']   = False
        mesh_settings['material_override']  = None
        mesh_settings['material_osl']       = False
        mesh_settings['bake_mods']          = False
        mesh_settings['bake_mods_invert']   = False
        mesh_settings['alpha_bounce']       = self.alpha_bounce
        return mesh_settings

    # Check node settings are valid to bake. Returns true/false, plus error message.
    def validate(self, check_materials=False, multires=False):
        valid = [True]
        # Check settings are set somewhere
        if not self.get_settings(validating=True):
            valid[0] = False
            valid.append([_print("Settings missing", node=self, ret=True), ": No pinned or connected mesh settings found"])
        # Check source objects
        has_selected = False
        if not multires:
            has_selected = len(self.inputs["Source"].get_objects()) > 0
        if has_selected and check_materials:
            valid_selected = self.inputs["Source"].validate(check_materials)
            # Add any generated messages to the stack. Material errors wont stop bake
            if len(valid_selected) > 1:
                valid_selected.pop(0)
                valid += valid_selected
        # Check target meshes
        has_active = len(self.inputs["Target"].get_objects(True)) > 0
        if has_active:
            valid_active = self.inputs["Target"].validate(check_materials and not has_selected, True, multires)
            valid[0] = valid_active.pop(0)
            # Add any generated messages to the stack. Errors here will stop bake
            if len(valid_active):
                valid += valid_active
        else:
            valid[0] = False
            valid.append([_print("Target error", node=self, ret=True), ": No valid target objects selected"])
        return valid

    # Return the requested set of objects from the appropriate input socket
    def get_objects(self, set):
        #if _prefs("debug"): _print("Getting objects in %s" % (set))
        if set == 'TARGET':
            objs = prune_objects(self.inputs["Target"].get_objects(only_mesh=True), True)
        elif set == 'SOURCE':
            objs = prune_objects(self.inputs["Source"].get_objects(no_lights=True))
        elif set == 'SCENE':
            objs = []
        # Return pruned object list
        return objs
    
    # Get a list of unique objects used as either source or target
    def get_unique_objects(self, type, for_auto_cage=False):
        if for_auto_cage:
            return []
        objs = self.get_objects(type)
        return objs
        
    alpha_bounce: bpy.props.IntProperty(name="Alpha Bounces", description="Number of times a ray can pass through transparent surfaces", default=3, min=1)
    
    def init(self, context):
        BakeWrangler_Tree_Node.init(self, context)
        # Sockets IN
        self.inputs.new('BakeWrangler_Socket_Setting', "Settings")
        self.inputs.new('BakeWrangler_Socket_Object', "Target")
        self.inputs.new('BakeWrangler_Socket_Object', "Source")
        # Sockets OUT
        self.outputs.new('BakeWrangler_Socket_Mesh', "Mesh")

    def draw_buttons(self, context, layout):
        layout.prop(self, "alpha_bounce")


# Bake materials as a texture by projecting them on a plane
class BakeWrangler_Bake_Material(BakeWrangler_Tree_Node, Node):
    '''Material input node'''
    bl_label = 'Input Material'
    bl_width_default = 240
    
    # Makes sure there is always one empty input socket at the bottom by adding and removing sockets
    def update_inputs(self):
        BakeWrangler_Tree_Node.update_inputs(self, 'BakeWrangler_Socket_Material', "Material")
    
    # Hard coded settings as the values are either not used or have only one meaningful possible value for this node
    def get_settings(self, validating=False):
        mesh_settings = {}
        mesh_settings['ray_dist']           = 0
        mesh_settings['max_ray_dist']       = 0
        mesh_settings['margin']             = 0
        mesh_settings['margin_extend']      = False
        mesh_settings['margin_auto']        = False
        #mesh_settings['marginer']           = False
        #mesh_settings['mask_margin']        = 0
        mesh_settings['auto_cage']          = False
        mesh_settings['acage_expansion']    = 0
        mesh_settings['acage_smooth']       = 0
        mesh_settings['material_replace']   = False
        mesh_settings['material_override']  = None
        mesh_settings['material_osl']       = False
        mesh_settings['bake_mods']          = False
        mesh_settings['bake_mods_invert']   = False
        mesh_settings['matbk_width']        = self.mat_width
        mesh_settings['matbk_height']       = self.mat_height
        return mesh_settings
        
    # Check node settings are valid to bake. Returns true/false, plus error message.
    def validate(self, check_materials=False, multires=False):
        valid = [True]
        mats = self.get_materials()
        # Check is has some materials
        if not len(mats):
            valid[0] = False
            valid.append([_print("Input error", node=self, ret=True), ": No valid inputs"])
            return valid
        # Check the materials can be baked if required
        if check_materials:
            for mat in mats:
                # Is node based?
                if not mat[0].node_tree or not mat[0].node_tree.nodes:
                    valid.append([_print("Material warning", node=self.node, ret=True), ": <%s> not a node based material" % (mat.name)])
                    continue
                # Is a 'principled' material?
                passed = False
                for node in mat[0].node_tree.nodes:
                    if node.type == 'OUTPUT_MATERIAL' and node.target in ['CYCLES', 'ALL']:
                        if material_recursor(node):
                            passed = True
                            break
                if not passed:
                    valid.append([_print("Material warning", node=self.node, ret=True), ": <%s> Output doesn't appear to be a valid combination of Principled and Mix shaders. Baked values will not be correct for this material." % (mat.name)])
        return valid            
    
    # Create a list of unique materials from node inputs
    def get_materials(self):
        materials = []
        # First collect any objects in the object input
        objs = self.inputs[0].get_objects(no_lights=True)
        # If there are any objects, collect their materials
        for obj in objs:
            for mat in obj[0].data.materials:
                materials.append([mat])
        # Next just add materials from the remaining inputs
        for input in self.inputs:
            if input.bl_idname == 'BakeWrangler_Socket_Material':
                if input.value is not None:
                    materials.append([input.value])
        # Now prune out any duplicates
        return prune_objects(materials)
    
    mat_width: bpy.props.FloatProperty(name="Width", description="Width of plane to project material on", precision=3, unit='LENGTH', default=1, min=0)
    mat_height: bpy.props.FloatProperty(name="Height", description="Height of plane to project material on", precision=3, unit='LENGTH', default=1, min=0)
    
    def init(self, context):
        BakeWrangler_Tree_Node.init(self, context)
        # Sockets IN
        self.inputs.new('BakeWrangler_Socket_Object', "Materials from Objects")
        self.inputs.new('BakeWrangler_Socket_Material', "Material")
        # Sockets OUT
        self.outputs.new('BakeWrangler_Socket_Material', "Material")
        
    def draw_buttons(self, context, layout):
        col = layout.column(align=True)
        col.prop(self, "mat_width")
        col.prop(self, "mat_height")


# Mesh settings to be used when baking attached objects
class BakeWrangler_Bake_Mesh(BakeWrangler_Tree_Node, Node):
    '''Mesh input node'''
    bl_label = 'Input Mesh'
    bl_width_default = 240

    # Inputs are static on this node
    def update_inputs(self):
        pass

    # Determine if object meets current input filter
    def input_filter(self, input_name, object):
        if input_name == "Target":
            if object.type == 'MESH':
                return True
        elif input_name == "Source":
            if object.type in ['MESH', 'CURVE', 'SURFACE', 'META', 'FONT']:
                return True
        elif input_name == "Scene":
            if object.rna_type.identifier == 'Collection':
                return True
        return False

    # Try to get nodes settings from local or global node
    def get_settings(self, validating=False):
        settings = get_input(self.inputs["Settings"])
        if not settings:
            settings = self.id_data.get_pinned_settings("MeshSettings")
        if validating:
            return settings
        mesh_settings = {}
        mesh_settings['ray_dist']           = settings.ray_dist
        mesh_settings['max_ray_dist']       = settings.max_ray_dist
        mesh_settings['margin']             = settings.margin
        mesh_settings['margin_extend']      = settings.margin_extend
        mesh_settings['margin_auto']        = settings.margin_auto
        #mesh_settings['marginer']           = settings.marginer
        #mesh_settings['marginer_fill']      = settings.marginer_fill
        #mesh_settings['mask_margin']        = settings.mask_margin
        mesh_settings['auto_cage']          = settings.auto_cage
        mesh_settings['acage_expansion']    = settings.acage_expansion
        mesh_settings['acage_smooth']       = settings.acage_smooth
        mesh_settings['material_replace']   = settings.material_replace
        mesh_settings['material_override']  = settings.material_override
        mesh_settings['material_osl']       = settings.material_osl
        mesh_settings['bake_mods']          = settings.bake_mods
        mesh_settings['bake_mods_invert']   = _prefs("invert_bakemod")
        if self.view_from == 'CAM' and self.view_cam:
            mesh_settings['view_from']      = self.view_cam
        return mesh_settings

    # Check node settings are valid to bake. Returns true/false, plus error message.
    def validate(self, check_materials=False, multires=False):
        valid = [True]
        # Check settings are set somewhere
        if not self.get_settings(validating=True):
            valid[0] = False
            valid.append([_print("Settings missing", node=self, ret=True), ": No pinned or connected mesh settings found"])
        # Check source objects
        has_selected = False
        if not multires:
            has_selected = len(self.inputs["Source"].get_objects()) > 0
        if has_selected and check_materials:
            valid_selected = self.inputs["Source"].validate(check_materials)
            # Add any generated messages to the stack. Material errors wont stop bake
            if len(valid_selected) > 1:
                valid_selected.pop(0)
                valid += valid_selected
        # Check target meshes
        has_active = len(self.inputs["Target"].get_objects(True)) > 0
        if has_active:
            valid_active = self.inputs["Target"].validate(check_materials and not has_selected, True, multires)
            valid[0] = valid_active.pop(0)
            # Add any generated messages to the stack. Errors here will stop bake
            if len(valid_active):
                valid += valid_active
        else:
            valid[0] = False
            valid.append([_print("Target error", node=self, ret=True), ": No valid target objects selected"])
        return valid

    # Return the requested set of objects from the appropriate input socket
    def get_objects(self, set):
        #if _prefs("debug"): _print("Getting objects in %s" % (set))
        if set == 'TARGET':
            objs = prune_objects(self.inputs["Target"].get_objects(only_mesh=True), True)
        elif set == 'SOURCE':
            objs = prune_objects(self.inputs["Source"].get_objects(no_lights=True))
        elif set == 'SCENE':
            objs = prune_objects(self.inputs["Scene"].get_objects())
        # Return pruned object list
        return objs
    
    # Get a list of unique objects used as either source or target
    def get_unique_objects(self, type, for_auto_cage=False):
        if for_auto_cage:
            settings = self.get_settings()
            if not settings['auto_cage']:
                return []
        objs = self.get_objects(type)
        if for_auto_cage:
            objs_cage = []
            for obj in objs:
                if len(obj) > 2 and obj[2]:
                    continue
                else:
                    objs_cage.append([obj[0], settings['acage_expansion'], settings['acage_smooth']])
            return objs_cage
        return objs
    
    view_orig = (
        ('ABV', "Above Surface", "Cast rays from above surface"),
        ('CAM', "Camera", "Cast rays from camera location"),
    )
    
    view_from: bpy.props.EnumProperty(name="View from", description="Ray casting origin (where applicable)", items=view_orig, default='ABV')
    view_cam: bpy.props.PointerProperty(name="View camera", description="Camera to use for ray origins", type=bpy.types.Object)
    
    def init(self, context):
        BakeWrangler_Tree_Node.init(self, context)
        # Sockets IN
        self.inputs.new('BakeWrangler_Socket_Setting', "Settings")
        self.inputs.new('BakeWrangler_Socket_Object', "Target")
        self.inputs.new('BakeWrangler_Socket_Object', "Source")
        self.inputs.new('BakeWrangler_Socket_Object', "Scene")
        # Sockets OUT
        self.outputs.new('BakeWrangler_Socket_Mesh', "Mesh")

    def draw_buttons(self, context, layout):
        row0 = layout.row(align=True)
        row1 = row0.row(align=True)
        row2 = row0.row(align=True)
        
        row1.prop(self, "view_from", text="View")
        row2.prop_search(self, "view_cam", bpy.data, "objects", text="", icon='CAMERA_DATA')
        
        if self.view_from == 'CAM':
            row2.enabled = True
        else:
            row2.enabled = False


# Baking node that holds all the settings for a type of bake 'pass'. Takes one or more mesh input nodes as input.
class BakeWrangler_Bake_Pass(BakeWrangler_Tree_Node, Node):
    '''Baking pass node'''
    bl_label = 'Bake Pass'
    bl_width_default = 160

    # Returns the most identifing string for the node
    def get_name(self):
        name = BakeWrangler_Tree_Node.get_name(self)
        if self.bake_picked:
            name += " (%s)" % (self.bake_picked)
        return name

    # Makes sure there is always one empty input socket at the bottom by adding and removing sockets
    def update_inputs(self):
        BakeWrangler_Tree_Node.update_inputs(self, 'BakeWrangler_Socket_Mesh', "Mesh")

    # Update node label based on selected pass
    def update_pass(self, context):
        if self.bake_cat == 'PBR':
            pass_enum = self.passes_pbr
            pass_bake = self.bake_pbr
        elif self.bake_cat == 'CORE':
            pass_enum = self.passes_core
            pass_bake = self.bake_core
        else:
            pass_enum = self.passes_wrang
            pass_bake = self.bake_wrang

        # Update picked value
        self.bake_picked = pass_bake

        if self.label == "":
            pass_label = "Pass: "
        elif ":" in self.label:
            start, sep, end = self.label.rpartition(":")
            pass_label = start + ": "
        for pas in pass_enum:
            if pas[0] == pass_bake:
                self.label = pass_label + pas[1]
                break
    
    # Get Mesh node inputs
    def get_inputs(self):
        meshes = []
        for input in self.inputs:
            if input.bl_idname == 'BakeWrangler_Socket_Mesh':
                mesh = get_input(input)
                if mesh:
                    if mesh.bl_idname == 'BakeWrangler_Sort_Meshes':
                        for inpt in mesh.inputs:
                            if inpt.islinked() and inpt.valid:
                                meshes.append([mesh, inpt])
                    else:
                        meshes.append([mesh])
        return meshes
    
    # Try to get nodes settings from local or global node
    def get_settings(self, validating=False):
        pass_settings = {}
        settings = sampsets = get_input(self.inputs["Settings"])
        if not settings or settings.bl_idname == 'BakeWrangler_SampleSettings':
            settings = self.id_data.get_pinned_settings("PassSettings")
        # Handle sample settings if pass settings found
        if settings:
            if not sampsets or sampsets.bl_idname not in ['BakeWrangler_SampleSettings', 'BakeWrangler_Settings']:
                sampsets = None
                # See if the settings has a connected samples settings
                if "Samples" in settings.inputs.keys():
                    sampsets = get_input(settings.inputs["Samples"])
                if not sampsets:
                    # See if there is a pinned samples settings
                    sampsets = self.id_data.get_pinned_settings("SampleSettings")
        if validating:
            return settings
        # Make it so having no sample settings node still works
        if not sampsets:
            pass_settings['bake_samples'] = self.bake_samples if self.bake_samples != 0 else 1
            pass_settings['bake_threshold'] = 0.0
            pass_settings['bake_usethresh'] = False
            pass_settings['bake_timelimit'] = 0.0
        else:
            if not get_input(self.inputs["Settings"]) and self.bake_samples != 0:
                pass_settings['bake_samples'] = self.bake_samples
            pass_settings['bake_samples']   = sampsets.bake_samples if 'bake_samples' not in pass_settings else pass_settings['bake_samples']
            pass_settings['bake_threshold'] = sampsets.bake_threshold
            pass_settings['bake_usethresh'] = sampsets.bake_usethresh
            pass_settings['bake_timelimit'] = sampsets.bake_timelimit
        pass_settings['x_res']          = settings.res_bake_x
        pass_settings['y_res']          = settings.res_bake_y
        pass_settings['bake_device']    = settings.bake_device
        pass_settings['interpolate']    = settings.interpolate
        pass_settings['use_world']      = settings.use_world
        pass_settings['the_world']      = settings.the_world
        pass_settings['cpy_render']     = settings.cpy_render
        pass_settings['cpy_from']       = settings.cpy_from
        pass_settings['tiles']          = settings.use_tiles
        pass_settings['tile_size']      = settings.render_tile
        pass_settings['threads']        = settings.render_threads
        pass_settings['use_bg_col']     = settings.use_bg_col
        pass_settings['bg_color']       = settings.bg_color
        pass_settings['bake_cat']       = self.bake_cat
        pass_settings['bake_type']      = self.bake_picked
        pass_settings['use_mask']       = self.use_mask           
        pass_settings['node_name']      = self.get_name()
        pass_settings['norm_s']         = self.norm_space
        pass_settings['norm_r']         = self.norm_R
        pass_settings['norm_g']         = self.norm_G
        pass_settings['norm_b']         = self.norm_B
        pass_settings['multi_pass']     = self.multi_pass
        pass_settings['multi_samp']     = self.multi_samp
        pass_settings['multi_targ']     = self.multi_targ
        pass_settings['multi_sorc']     = self.multi_sorc
        pass_settings['bev_rad']        = self.bev_rad
        pass_settings['bev_samp']       = self.bev_samp
        pass_settings['cavity_samp']    = self.cavity_samp
        pass_settings['cavity_dist']    = self.cavity_dist
        pass_settings['cavity_gamma']   = self.cavity_gamma
        pass_settings['cavity_edges']   = self.cavity_edges
        pass_settings['curv_mid']       = self.curv_mid
        pass_settings['curv_vex']       = self.curv_vex
        pass_settings['curv_cav']       = self.curv_cav
        pass_settings['curv_vex_max']   = self.curv_vex_max
        pass_settings['curv_cav_min']   = self.curv_cav_min
        pass_settings['osl_curv_dist']  = self.osl_curv_dist
        pass_settings['osl_curv_samp']  = self.osl_curv_samp
        pass_settings['osl_curv_cont']  = self.osl_curv_cont
        pass_settings['osl_curv_srgb']  = False
        pass_settings['osl_height_dist'] = self.osl_height_dist
        pass_settings['osl_height_samp'] = self.osl_height_samp
        pass_settings['osl_height_midl'] = self.osl_height_midl
        pass_settings['osl_height_void'] = self.osl_height_void
        pass_settings['vert_col']       = self.vert_col
        pass_settings['influences']     = set()
        pass_settings['aov_name']       = self.aov_name
        pass_settings['aov_input']      = self.aov_input
        pass_settings['use_material_vpcolor'] = self.use_material_vpcolor
        pass_settings['osl_bentnorm_dist'] = self.osl_bentnorm_dist
        pass_settings['osl_bentnorm_samp'] = self.osl_bentnorm_samp
        
        if self.use_direct:
            pass_settings['influences'].add('DIRECT')
        if self.use_indirect:
            pass_settings['influences'].add('INDIRECT')
        if self.use_color:
            pass_settings['influences'].add('COLOR')
        if self.bake_picked == 'COMBINED':
            if self.use_diffuse:
                pass_settings['influences'].add('DIFFUSE')
            if self.use_glossy:
                pass_settings['influences'].add('GLOSSY')
            if self.use_transmission:
                pass_settings['influences'].add('TRANSMISSION')
            #if self.use_ao:
            #    pass_settings['influences'].add('AO')
            if self.use_emit:
                pass_settings['influences'].add('EMIT')
        if self.use_bg_col:
            pass_settings['use_bg_col'] = self.use_bg_col
            pass_settings['bg_color'] = self.bg_color
        return pass_settings

    # Check node settings are valid to bake. Returns true/false, plus error message(s).
    def validate(self, is_primary=False):
        valid = [True]
        # Validate has Settings
        self.update_pass(None)
        if not self.get_settings(validating=True):
            valid[0] = False
            valid.append([_print("Settings missing", node=self, ret=True), ": No pinned or connected pass settings found"])
        # Validate inputs
        has_valid_input = False
        is_multires = (self.bake_cat == 'CORE' and self.bake_core == 'MULTIRES')
        for input in self.inputs:
            if input.bl_idname == 'BakeWrangler_Socket_Mesh' and input.islinked() and input.valid:
                if self.bake_cat == 'PBR':
                    input_valid = get_input(input).validate(check_materials=True)
                else:
                    input_valid = get_input(input).validate(multires=is_multires)
                if not input_valid.pop(0):
                    valid[0] = False
                else:
                    has_valid_input = True
                if len(input_valid):
                    valid += input_valid
        errs = len(valid)
        if not has_valid_input and errs < 2:
            valid[0] = False
            valid.append([_print("Input error", node=self, ret=True), ": No valid inputs connected"])
        # Validate outputs
        if is_primary:
            has_valid_output = False
            for output in self.outputs:
                if output.is_linked:
                    for link in gather_output_links(output):
                        if link.is_valid and link.to_socket.valid:
                            output_valid = link.to_node.validate()
                            if not output_valid.pop(0):
                                valid[0] = False
                            else:
                                has_valid_output = True
                            if len(output_valid):
                                valid += output_valid
            if not has_valid_output and errs == len(valid):
                valid[0] = False
                valid.append([_print("Output error", node=self, ret=True), ": No valid outputs connected"])
        # Validated
        return valid

    pass_cats = (
        ('PBR', "PBR", "Bake passes for PBR materials. Most require the material to use a Principled BSDF"),
        ('CORE', "Blender", "Standard bake passes normally found in blender. Passes with the same name in a different category will have different behavior"),
        ('WRANG', "Wrangler", "Additional passes provided in Bake Wrangler that aren't PBR specific"),
    )

    passes_pbr = (
        ('', "Common", ""),
        ('ALBEDO', "Albedo", "Surface color without lighting (Principled shader only)"),
        ('METALLIC', "Metallic", "Surface 'metalness' values (Principled shader only)"),
        ('ROUGHNESS', "Roughness", "Surface roughness values with no other influences (Principled shader only)"),
        ('SMOOTHNESS', "Smoothness", "Surface inverted roughness values with no other influences (Principled shader only)"),
        ('IOR', "IOR", "Index of Refraction (Principled shader only)"),
        ('ALPHA', "Alpha", "Surface transparency values (Principled shader only)"),
        ('AOV', "AOV Node", "The color or value channel of a named AOV node in the materials"),
        
        ('', "Normals", ""),
        ('NORMAL', "Combined", "Combined surface normals"),
        ('TEXNORM', "Texture", "Surface normals influenced only by texture values (no geometry)"),
        ('COATNORM', "Coat", "Surface normals influenced only by the coat values"),
        ('OBJNORM', "Geometry", "Surface normals ignoring any influence from textures"),
        ('BBNORM', "Billboard", "Normals using target billboards rotation as tangent space"),
        
        ('', "Emission", ""),
        ('EMIT', "Color", "Surface self emission color values with no other influences (Principled shader only)"),
        ('EMITSTR', "Strength", "Surface self emission strength values with no other influences (Principled shader only)"),
        
        ('', "Subsurface", ""),
        ('SUBWEIGHT', "Weight", "Blend between diffuse and subsurface scattering (Principled shader only)"),
        ('SUBRADIUS', "Radius", "Distance light scatters below the surface, each channel is for that R/G/B color of light (a higher R value will mean red light travels deeper) (Principled shader only)"),
        ('SUBSCALE', "Scale", "Multiplies with the subsurface radius to determine distance light travels below the surface (Principled shader only)"),
        ('SUBIOR', "IOR", "Subsurface scattering IOR (Principled shader only)"),
        ('SUBANISO', "Anisotropy", "Amount of anisotropy in subsurface (Principled shader only)"),
        
        ('', "Specular", ""),
        ('SPECIOR', "IOR", "IOR for specual intensity (Princpled shader only)"),
        ('SPECTINT', "Tint", "Tint of direct facing reflections (Note: dielectrics have colorless reflections, but this allows faking some effects) (Principled shader only)"),
        ('SPECANISO', "Anisotropic", "Amount of anisotropy for specular reflections (Principled shader only)"),
        ('SPECANISOROT', "Aniso Rotation", "Rotation direction of anisotropy for specular reflections (Principled shader only)"),
        ('SPECTAN', "Tangent", "Tangent vector for specular highlights (Princpled shader only)"),
        
        ('', "Transmission", ""),
        ('TRANSMISSION', "Weight", "Opacity values of surface with no other influences (Principled shader only)"),
        
        ('', "Coat", ""),
        ('COATWEIGHT', "Weight", "Intensity of coat layer for both reflections and tint (Principled shader only)"),
        ('COATROUGH', "Roughness", "Roughness values of the coat (Principled shader only)"),
        ('COATIOR', "IOR", "IOR values of the coat (Principled shader only)"),
        ('COATTINT', "Tint", "Tint color of the coat (Principled shader only)"),
        
        ('', "Sheen", ""),
        ('SHEENWIGHT', "Weight", "Amount of soft velvet like reflections near edges for cloth like materials (Principled shader only)"),
        ('SHEENROUGH', "Roughness", "Roughness values for sheen reflections (Principled shader only)"),
        ('SHEENTINT', "Tint", "Color mixed with white for sheen reflections (Principled shader only)"),
    )

    passes_core = (
        ('COMBINED', "Combined", "Combine multiple passes into a single bake"),
        ('AO', "Ambient Occlusion", "Surface self occlusion values"),
        ('SHADOW', "Shadow", "Shadow map"),
        ('POSITION', "Position", "Position map"),
        ('NORMAL', "Normal", "Surface normals"),
        ('UV', "UV", "UV Layout"),
        ('ROUGHNESS', "Roughness", "Surface roughness values"),
        ('SMOOTHNESS', "Smoothness", "Surface inverted roughness values"),
        ('EMIT', "Emit", "Surface self emission color values"),
        ('ENVIRONMENT', "Environment", "Colors coming from the environment"),
        ('DIFFUSE', "Diffuse", "Colors of a surface generated by a diffuse shader"),
        ('GLOSSY', "Glossy", "Colors of a surface generated by a glossy shader"),
        ('TRANSMISSION', "Transmission", "Colors of light passing through a material"),
        ('MULTIRES', "Multiresolution", "Data from a multiresolution modifier"),
    )

    passes_wrang = (
        ('BEVMASK', "Bevel Mask", "Map of bevels where beveled areas will be baked in white"),
        ('BEVNORMEMIT', "Bevel Normals (Emit)", "Normal map with only bevel influences (can bake from one object to another, but inverted faces will be backwards)"),
        ('BEVNORMNORM', "Bevel Normals (Norm)", "Normal map with only bevel influences (does not work for baking from one object to another, but handles inverted faces)"),
        ('CAVITY', "Cavity/Edges", "Surface cavity occlusion or edges map"),
        ('CURVATURE', "Curvature", "Surface curvature map"),
        #('OSL_CURV', "Curvature (OSL)", "OSL implementation of surface curvature map (CPU only)"),
        ('OSL_HEIGHT', "Height (OSL)", "Height map created by the distance between two surfaces (OSL shader only supports CPU)"),
        ('ISLANDID', "Island ID", "Map where each island of faces are baked in a different color"),
        ('MATID', "Material ID", "Map where each material is baked in a random solid color (based on their name)"),
        ('OBJCOL', "Object Color", "Each object is baked using its assigned viewport color"),
        ('WORLDPOS', "Position", "Areas of the object are baked with colors representing their position in the world"),
        ('THICKNESS', "Thickness", "Mesh thickness is baked from white (thin) to black (thick)"),
        ('VERTCOL', "Vertex Color", "Selected vertex colors are baked as the surface color"),
        ('OSL_BENTNORM', "Bent Normals (OSL)", "Bends normals based on ambient occlusion giving a directional bias"),
        ('MASKPASS', "UV Mask", "Black and white mask of pixels covered by UV islands"),
        ('UV_ISLAND', "UV Islands", "Each UV Island is baked using a random color for each"),
        ('FACE_SET', "Sculpt Face Sets", "Each Face Set defined in your sculpt is baked using a random color for each"),
    )

    passes_all = passes_pbr + passes_core + passes_wrang

    bake_has_influence = ['SUBSURFACE', 'TRANSMISSION', 'GLOSSY', 'DIFFUSE', 'COMBINED']

    normal_spaces = (
        ('TANGENT', "Tangent", "Bake the normals in tangent space"),
        ('OBJECT', "Object", "Bake the normals in object space"),
    )

    normal_swizzle = (
        ('POS_X', "+X", ""),
        ('POS_Y', "+Y", ""),
        ('POS_Z', "+Z", ""),
        ('NEG_X', "-X", ""),
        ('NEG_Y', "-Y", ""),
        ('NEG_Z', "-Z", ""),
    )

    multires_subpasses = (
        ('NORMALS', "Normals", "Bake Normals"),
        ('DISPLACEMENT', "Displacement", "Bake Displacement"),
    )

    multires_sampling = (
        ('MAXIMUM', "Max to Min", "Bake the highest resolution down to the lowest"),
        ('FROMMOD', "Modifier Values", "Bake from the current render resolution to the current preview resolution"),
        ('CUSTOM', "Custom Values", "Choose custom values for the target and source resolutions"),
    )
    
    aov_inputs = (
        ('COL', "Color", "Use color data"),
        ('VAL', "Value", "Use value data"),
    )
    
    bake_result: bpy.props.PointerProperty(name="bake_result", description="Used internally by BW", type=bpy.types.Image)
    mask_result: bpy.props.PointerProperty(name="mask_result", description="Used internally by BW", type=bpy.types.Image)
    sbake_result: bpy.props.PointerProperty(name="sbake_result", description="Used internally by BW", type=bpy.types.Image)
    smask_result: bpy.props.PointerProperty(name="smask_result", description="Used internally by BW", type=bpy.types.Image)
    
    bake_cat: bpy.props.EnumProperty(name="Group", description="Category to select bake passes from", items=pass_cats, default='PBR', update=update_pass)
    bake_pbr: bpy.props.EnumProperty(name="Pass", description="Type of PBR pass to bake", items=passes_pbr, default='ALBEDO', update=update_pass)
    bake_core: bpy.props.EnumProperty(name="Pass", description="Type of Blender standard pass to bake", items=passes_core, default='COMBINED', update=update_pass)
    bake_wrang: bpy.props.EnumProperty(name="Pass", description="Type of Wrangler pass to bake", items=passes_wrang, default='BEVMASK', update=update_pass)
    bake_picked: bpy.props.EnumProperty(name="Picked", description="Selected bake type", items=passes_all)
    bake_samples: bpy.props.IntProperty(name="Bake Samples", description="Number of samples to bake for each pixel. Use 25 to 50 samples for most bake types (AO may look better with more).\nQuality is gained by increaseing resolution rather than samples past that point", default=0, min=0)

    adv_settings: bpy.props.BoolProperty(name="Advanced Settings", description="Show or hide advanced settings", default=False)

    use_mask: bpy.props.BoolProperty(name="Use Masking", description="Generate a map of changed UV islands to use as a mask when updating pixel values. Allows layering of multiple passes onto a single image so long as they don't overlap", default=False)
    use_direct: bpy.props.BoolProperty(name="Direct", description="Add direct lighting contribution", default=True)
    use_indirect: bpy.props.BoolProperty(name="Indirect", description="Add indirect lighting contribution", default=True)
    use_color: bpy.props.BoolProperty(name="Color", description="Color the pass", default=True)
    use_diffuse: bpy.props.BoolProperty(name="Diffuse", description="Add diffuse contribution", default=True)
    use_glossy: bpy.props.BoolProperty(name="Glossy", description="Add glossy contribution", default=True)
    use_transmission: bpy.props.BoolProperty(name="Transmission", description="Add transmission contribution", default=True)
    #use_subsurface: bpy.props.BoolProperty(name="Subsurface", description="Add subsurface contribution", default=True)
    #use_ao: bpy.props.BoolProperty(name="Ambient Occlusion", description="Add ambient occlusion contribution", default=True)
    use_emit: bpy.props.BoolProperty(name="Emit", description="Add emission contribution", default=True)

    norm_space: bpy.props.EnumProperty(name="Space", description="Space to bake the normals in", items=normal_spaces, default='TANGENT')
    norm_R: bpy.props.EnumProperty(name="R", description="Axis to bake in Red channel", items=normal_swizzle, default='POS_X')
    norm_G: bpy.props.EnumProperty(name="G", description="Axis to bake in Green channel", items=normal_swizzle, default='POS_Y')
    norm_B: bpy.props.EnumProperty(name="B", description="Axis to bake in Blue channel", items=normal_swizzle, default='POS_Z')
    multi_pass: bpy.props.EnumProperty(name="Multires Type", description="Type of multiresolution pass to bake", items=multires_subpasses, default='NORMALS')
    multi_samp: bpy.props.EnumProperty(name="Multires Method", description="Method to pick multiresolution source and target", items=multires_sampling, default='MAXIMUM')
    multi_targ: bpy.props.IntProperty(name="Multires Target", description="Subdivision level for target of bake", default=0, min=0, soft_max=16)
    multi_sorc: bpy.props.IntProperty(name="Multires Source", description="Subdivision level for source of bake", default=8, min=0, soft_max=16)

    bev_rad: bpy.props.FloatProperty(name="Bevel Radius", description="Width of bevel on edges", default=0.05, min=0)
    bev_samp: bpy.props.IntProperty(name="Bevel Samples", description="Number of samples to take (more gives greater accuracy at cost of time. A value of 4 works well in most cases and noise can be resolved by using more bake pass samples instead of increasing this value)", min=2, max=16, default=4)
    cavity_samp: bpy.props.IntProperty(name="Cavity Over Samples", description="Number of samples to take (more gives a more accurate result but takes longer, increase bake pass samples to reduce noise before increasing this value)", default=16, min=1, max=128)
    cavity_dist: bpy.props.FloatProperty(name="Cavity Sample Distance", description="How far away a face can be to contribute to the calculation (may need larger distances for larger objects)", default=0.4, step=1, min=0.0, unit='LENGTH')
    cavity_gamma: bpy.props.FloatProperty(name="Cavity Gamma", description="Gamma transform to be performed on cavity values", default=1.0, step=1)
    cavity_edges: bpy.props.BoolProperty(name="Edge Mode", description="Inverts the cavity map normals to find edges. If it's too dark, lower distance value", default=False)
    curv_mid: bpy.props.FloatProperty(name="Curvature Flat", description="Value to assign to the mid-point between curves (flat area)", default=0.5, min=0.0, max=1.0)
    curv_vex: bpy.props.FloatProperty(name="Curvature Convex", description="Value to assign to the sharpest (maximum) point of a convex curve", default=1.0, min=0.0, max=1.0)
    curv_cav: bpy.props.FloatProperty(name="Curvature Concave", description="Value to assign to the sharpest (minimum) point of a concave curve", default=0.0, min=0.0, max=1.0)
    curv_vex_max: bpy.props.FloatProperty(name="Curvature Convex Max", description="Convex value to consider the maximum curvature (higher values create a greater range)", default=0.2, min=0.0001, max=1.0)
    curv_cav_min: bpy.props.FloatProperty(name="Curvature Concave Min", description="Concave value to consider the minimum curvature (lower values create a greater range)", default=0.8, min=0.0, max=0.9999)
    osl_curv_dist: bpy.props.FloatProperty(name="Curvature Distance (OSL)", description="Distance to search for a neighboring surface", default=0.1, min=0.0)
    osl_curv_samp: bpy.props.IntProperty(name="Curvature Samples (OSL)", description="Number of attempts to try finding a neighboring surface within the distance value", default=16, min=1)
    osl_curv_cont: bpy.props.FloatProperty(name="Curvature Contrast (OSL)", description="Contrast level applied to curvature value", default=0.0, min=0.0)
    osl_height_dist: bpy.props.FloatProperty(name="Height Distance", description="Maximum distance from source to look for a surface", default=0.1, min=0.0)
    osl_height_samp: bpy.props.IntProperty(name="Height Samples", description="How many surfaces to consider for each point. Must be at least two but complex objects with faces close together may need more for correct results", default=2, min=2)
    osl_height_midl: bpy.props.FloatProperty(name="Height Mid Level", description="Value to use as the middel level (neither high or low)", default=0.5, min=0.0, max=1.0)
    osl_height_void: bpy.props.FloatVectorProperty(name="Height Void Color", description="Color to fill in areas where no height value could be found within the search distance", default=[0.5,0.5,0.5,1.0], size=4, subtype='COLOR', soft_min=0.0, soft_max=1.0, step=10)
    vert_col: bpy.props.StringProperty(name="Vertex Color Layer", description="Vertex color layer to bake from (leaving blank will use active)", default="")
    use_bg_col: bpy.props.BoolProperty(name="BG Color", description="Background color for blank areas", default=False)
    bg_color: bpy.props.FloatVectorProperty(name="BG Color", description="Background color used in blank areas", subtype='COLOR', soft_min=0.0, soft_max=1.0, step=10, default=[0.0,0.0,0.0,1.0], size=4)
    aov_name: bpy.props.StringProperty(name="AOV Name", description="Name assigned to AOV node you want to bake from", default="")
    aov_input: bpy.props.EnumProperty(name="AOV Source", description="Take data from either color or value input of AOV node", items=aov_inputs, default='COL')
    use_material_vpcolor: bpy.props.BoolProperty(name="Use Viewport Color", description="Use the materials assigned viewport color instead of generating a random one based on its name", default=False)
    use_subtraction: bpy.props.BoolProperty(name="Use Subtraction", description="Subtract the object normals from the material normals to isolate them. This results in correct tangent normal rotations but may not be as clean a result", default=True)
    osl_bentnorm_dist: bpy.props.FloatProperty(name="Bent Normals Distance", description="Maximum distance for a surface to contribute to ambient occlusion", default=1.0, min=0.001)
    osl_bentnorm_samp: bpy.props.IntProperty(name="Height Samples", description="Number of ambient light samples to take for each surface point", default=8, min=1)
    
    def init(self, context):
        BakeWrangler_Tree_Node.init(self, context)
        # Set label to pass
        self.update_pass(context)
        # Sockets IN
        self.inputs.new('BakeWrangler_Socket_Setting', "Settings")
        self.inputs.new('BakeWrangler_Socket_Mesh', "Mesh")
        # Sockets OUT
        self.outputs.new('BakeWrangler_Socket_Color', "Color")
        # Prefs
        self.adv_settings = _prefs("def_show_adv")

    def draw_buttons(self, context, layout):
        colnode = layout.column(align=False)

        colpass = colnode.column(align=True)
        colpass.prop(self, "bake_cat")
        if self.bake_cat == 'PBR':
            colpass.prop(self, "bake_pbr")
        elif self.bake_cat == 'CORE':
            colpass.prop(self, "bake_core")
        else:
            colpass.prop(self, "bake_wrang")

        advrow = colnode.row()
        advrow.alignment = 'LEFT'

        if not self.adv_settings:
            adv = advrow.prop(self, "adv_settings", icon="DISCLOSURE_TRI_RIGHT", emboss=False, text="Advanced:")
            advrow.separator()
        else:
            adv = advrow.prop(self, "adv_settings", icon="DISCLOSURE_TRI_DOWN", emboss=False, text="Advanced:")
            advrow.separator()

            col = colnode.column(align=True)
            col.prop(self, "use_mask", toggle=True)
            bg_col = col.row(align=True)
            bg_col.prop(self, "use_bg_col", toggle=True)
            if self.use_bg_col:
                bg_col.prop(self, "bg_color", toggle=True, text="")

            splitopt = colnode.split(factor=0.5)
            colopttxt = splitopt.column(align=True)
            colopttxt.alignment = 'RIGHT'
            coloptval = splitopt.column(align=True)
            
            # Additional options for PBR passes
            if self.bake_cat == 'PBR':
                # AOV ouput
                if self.bake_pbr == 'AOV':
                    colopttxt.label(text="Name:")
                    colopttxt.label(text="Input:")

                    coloptval.prop(self, "aov_name", text="")
                    coloptval.prop(self, "aov_input", text="")
            # Additional options for 'Wrangler' passes
            if self.bake_cat == 'WRANG':
                # Bevel mask
                if self.bake_wrang in ['BEVMASK', 'BEVNORMEMIT', 'BEVNORMNORM']:
                    colopttxt.label(text="Samples:")
                    colopttxt.label(text="Radius:")

                    coloptval.prop(self, "bev_samp", text="")
                    coloptval.prop(self, "bev_rad", text="")
                elif self.bake_wrang == 'CAVITY':
                    colopttxt.label(text="Edge Mode:")
                    colopttxt.label(text="Over Samples:")
                    colopttxt.label(text="Distance:")
                    colopttxt.label(text="Gamma:")

                    coloptval.prop(self, "cavity_edges", text="")
                    coloptval.prop(self, "cavity_samp", text="")
                    coloptval.prop(self, "cavity_dist", text="")
                    coloptval.prop(self, "cavity_gamma", text="")
                elif self.bake_wrang == 'THICKNESS':
                    colopttxt.label(text="Over Samples:")
                    colopttxt.label(text="Distance:")

                    coloptval.prop(self, "cavity_samp", text="")
                    coloptval.prop(self, "cavity_dist", text="")
                elif self.bake_wrang == 'CURVATURE':
                    colopttxt.label(text="Flat:")
                    colopttxt.label(text="Convex:")
                    colopttxt.label(text="Convex Max:")
                    colopttxt.label(text="Concave:")
                    colopttxt.label(text="Concave Min:")

                    coloptval.prop(self, "curv_mid", text="")
                    coloptval.prop(self, "curv_vex", text="")
                    coloptval.prop(self, "curv_vex_max", text="")
                    coloptval.prop(self, "curv_cav", text="")
                    coloptval.prop(self, "curv_cav_min", text="")
                elif self.bake_wrang == 'OSL_CURV':
                    colopttxt.label(text="Distance:")
                    colopttxt.label(text="Samples:")
                    colopttxt.label(text="Contrast:")

                    coloptval.prop(self, "osl_curv_dist", text="")
                    coloptval.prop(self, "osl_curv_samp", text="")
                    coloptval.prop(self, "osl_curv_cont", text="")
                elif self.bake_wrang == 'OSL_HEIGHT':
                    colopttxt.label(text="Distance:")
                    colopttxt.label(text="Samples:")
                    colopttxt.label(text="Mid Level:")
                    colopttxt.label(text="Void Color:")

                    coloptval.prop(self, "osl_height_dist", text="")
                    coloptval.prop(self, "osl_height_samp", text="")
                    coloptval.prop(self, "osl_height_midl", text="")
                    coloptval.prop(self, "osl_height_void", text="")
                elif self.bake_wrang == 'VERTCOL':
                    colopttxt.label(text="Layer:")

                    coloptval.prop(self, "vert_col", text="")
                elif self.bake_wrang == 'MATID':
                    colnode.prop(self, "use_material_vpcolor")
                elif self.bake_wrang == 'OSL_BENTNORM':
                    colopttxt.label(text="Distance:")
                    colopttxt.label(text="Samples:")
                    
                    coloptval.prop(self, "osl_bentnorm_dist", text="")
                    coloptval.prop(self, "osl_bentnorm_samp", text="")
                
            # Additional options for 'core' passes
            if self.bake_cat == 'CORE':
                # Multires
                if self.bake_core == 'MULTIRES':
                    colopttxt.label(text="Type:")
                    colopttxt.label(text="Method:")

                    coloptval.prop(self, "multi_pass", text="")
                    coloptval.prop(self, "multi_samp", text="")
                    if self.multi_samp == 'CUSTOM':
                        colopttxt.label(text="Target Divs:")
                        colopttxt.label(text="Source Divs:")

                        coloptval.prop(self, "multi_targ", text="")
                        coloptval.prop(self, "multi_sorc", text="")
                elif self.bake_core in self.bake_has_influence:
                    row = colnode.row(align=True)
                    row.use_property_split = False
                    row.prop(self, "use_direct", toggle=True)
                    row.prop(self, "use_indirect", toggle=True)
                    if self.bake_core != 'COMBINED':
                        row.prop(self, "use_color", toggle=True)
                    else:
                        col = colnode.column(align=True)
                        col.prop(self, "use_diffuse")
                        col.prop(self, "use_glossy")
                        col.prop(self, "use_transmission")
                        #col.prop(self, "use_subsurface")
                        #col.prop(self, "use_ao")
                        col.prop(self, "use_emit")
            # Any normal map passes
            if (self.bake_cat == 'PBR' and self.bake_pbr in ['TEXNORM', 'CLEARNORM', 'OBJNORM', 'BBNORM']) \
                or (self.bake_cat == 'CORE' and self.bake_core in ['NORMAL']) \
                or (self.bake_cat == 'WRANG' and self.bake_wrang in ['BEVNORMEMIT', 'BEVNORMNORM', 'OSL_BENTNORM']):
                if self.bake_picked == 'TEXNORM':
                    colnode.prop(self, "use_subtraction")
                colopttxt.label(text="Space:")
                colopttxt.label(text="R:")
                colopttxt.label(text="G:")
                colopttxt.label(text="B:")

                coloptval.prop(self, "norm_space", text="")
                coloptval.prop(self, "norm_R", text="")
                coloptval.prop(self, "norm_G", text="")
                coloptval.prop(self, "norm_B", text="")



# The channel map combines inputs by mapping them to RGBA channels of the output and sits between passes and output
# images
class BakeWrangler_Channel_Map(BakeWrangler_Tree_Node, Node):
    '''Channel map node'''
    bl_label = 'Channel Map'

    def update_inputs(self):
        pass
        
    def validate(self):
        return BakeWrangler_Tree_Node.validate(self, True)

    def init(self, context):
        BakeWrangler_Tree_Node.init(self, context)
        # Sockets IN
        self.inputs.new('BakeWrangler_Socket_Color', "Color")
        self.inputs.new('BakeWrangler_Socket_ChanMap', "Red")
        self.inputs.new('BakeWrangler_Socket_ChanMap', "Green")
        self.inputs.new('BakeWrangler_Socket_ChanMap', "Blue")
        # Sockets OUT
        self.outputs.new('BakeWrangler_Socket_Color', "Color")



# Mix RGB via a factor and operation
class BakeWrangler_Post_MixRGB(BakeWrangler_Tree_Node, Node):
    '''Mix RGB node'''
    bl_label = 'Mix RGB'
    
    def update_inputs(self):
        pass
        
    def validate(self):
        return BakeWrangler_Tree_Node.validate(self, True, True)
    
    ops = (
        ('MIX', "Mix", ""),
        ('ADD', "Add", ""),
        ('SUBTRACT', "Subtract", ""),
        ('MULTIPLY', "Multiply", ""),
        ('DIVIDE', "Divide", ""),
        ('OVERLAY', "Overlay", ""),
    )
    
    op: bpy.props.EnumProperty(name="Operator", description="Mathematical operation to perform", items=ops, default='MIX')
    
    def init(self, context):
        BakeWrangler_Tree_Node.init(self, context)
        # Sockets IN
        self.inputs.new('BakeWrangler_Socket_Float', "Fac")
        self.inputs.new('BakeWrangler_Socket_Color', "Color1")
        self.inputs.new('BakeWrangler_Socket_Color', "Color2")
        # Sockets OUT
        self.outputs.new('BakeWrangler_Socket_Color', "Color")
    
    def draw_buttons(self, context, layout):
        layout.prop(self, "op", text="")



# Split RGB ouput into channels
class BakeWrangler_Post_SplitRGB(BakeWrangler_Tree_Node, Node):
    '''Split RGB node'''
    bl_label = 'Split RGB'
    
    def update_inputs(self):
        pass
        
    def validate(self):
        return BakeWrangler_Tree_Node.validate(self, True)
    
    def init(self, context):
        BakeWrangler_Tree_Node.init(self, context)
        # Sockets IN
        self.inputs.new('BakeWrangler_Socket_Color', "Color")
        # Sockets OUT
        self.outputs.new('BakeWrangler_Socket_Float', "Red")
        self.outputs.new('BakeWrangler_Socket_Float', "Green")
        self.outputs.new('BakeWrangler_Socket_Float', "Blue")



# Join channels into single RGB color
class BakeWrangler_Post_JoinRGB(BakeWrangler_Tree_Node, Node):
    '''Join RGB node'''
    bl_label = 'Join RGB'
    
    def update_inputs(self):
        pass
        
    def validate(self):
        return BakeWrangler_Tree_Node.validate(self, True, True)
    
    def init(self, context):
        BakeWrangler_Tree_Node.init(self, context)
        # Sockets IN
        self.inputs.new('BakeWrangler_Socket_Float', "Red")
        self.inputs.new('BakeWrangler_Socket_Float', "Green")
        self.inputs.new('BakeWrangler_Socket_Float', "Blue")
        # Sockets OUT
        self.outputs.new('BakeWrangler_Socket_Color', "Color")



# Perform math functions on image data
class BakeWrangler_Post_Math(BakeWrangler_Tree_Node, Node):
    '''Math node'''
    bl_label = 'Math'
    
    def update_inputs(self):
        pass
        
    def validate(self):
        return BakeWrangler_Tree_Node.validate(self, True, True)
    
    # Disable inputs based on function
    def chg_op(self, context):
        if self.op in ['FLOOR', 'CEIL']:
            self.inputs[1].enabled = False
        else:
            self.inputs[1].enabled = True
        
    ops = (
        ('ADD', "Add", "A + B"),
        ('SUBTRACT', "Subtract", "A - B"),
        ('MULTIPLY', "Multiply", "A * B"),
        ('DIVIDE', "Divide", "A / B"),
        
        ('POWER', "Power", "A^B"),
        ('LOGARITHM', "Logarithm", "Log A base B"),
        
        ('FLOOR', "Floor", "Largest integer <= A"),
        ('CEIL', "Ceil", "Smallest integer >= A"),
        ('MODULO', "Modulo", "Mod A / B"),
    )
    
    op: bpy.props.EnumProperty(name="Operator", description="Mathematical operation to perform", items=ops, update=chg_op, default='ADD')
    
    def init(self, context):
        BakeWrangler_Tree_Node.init(self, context)
        # Sockets IN
        self.inputs.new('BakeWrangler_Socket_Float', "Value", identifier="0")
        self.inputs.new('BakeWrangler_Socket_Float', "Value", identifier="1")
        # Sockets OUT
        self.outputs.new('BakeWrangler_Socket_Float', "Value")
    
    def draw_buttons(self, context, layout):
        layout.menu("BW_MT_math_ops", text=layout.enum_item_name(self, "op", self.op))

# Menu displayed in the math node to select function
#
# Found out headers can be created in enums by setting all but name to empty string
# eg ("", "ColumnName", "") - So this could probably be replaced with that, but w/e
#
class BakeWrangler_Post_Math_OpMenu(bpy.types.Menu):
    bl_idname = "BW_MT_math_ops"
    bl_label = "Ops"
    
    def draw(self, context):
        layout = self.layout.row()
        layout.alignment = 'LEFT'
        col1 = layout.column()
        col1.alignment = 'LEFT'
        col1.label(text="Functions")
        col1.separator()
        for op in context.node.ops:
            if op[0] in ['ADD', 'SUBTRACT', 'MULTIPLY', 'DIVIDE']:
                itm = col1.operator("bake_wrangler.pick_menu_enum", icon='NONE', text=op[1])
                BakeWrangler_Operator_PickMenuEnum.set_props(itm, op[0], op[2], "op", context.node.name, context.node.id_data.name)
        col1.separator()
        for op in context.node.ops:
            if op[0] in ['POWER', 'LOGARITHM']:
                itm = col1.operator("bake_wrangler.pick_menu_enum", icon='NONE', text=op[1])
                BakeWrangler_Operator_PickMenuEnum.set_props(itm, op[0], op[2], "op", context.node.name, context.node.id_data.name)
        col2 = layout.column()
        col2.alignment = 'LEFT'
        col2.label(text="Rounding")
        col2.separator()
        for op in context.node.ops:
            if op[0] in ['FLOOR', 'CEIL', 'MODULO']:
                itm = col2.operator("bake_wrangler.pick_menu_enum", icon='NONE', text=op[1])
                BakeWrangler_Operator_PickMenuEnum.set_props(itm, op[0], op[2], "op", context.node.name, context.node.id_data.name)



# Apply gamma transform to color
class BakeWrangler_Post_Gamma(BakeWrangler_Tree_Node, Node):
    '''Gamma node'''
    bl_label = 'Gamma'
    
    def update_inputs(self):
        pass
        
    def validate(self):
        return BakeWrangler_Tree_Node.validate(self, True)
    
    def init(self, context):
        BakeWrangler_Tree_Node.init(self, context)
        # Sockets IN
        self.inputs.new('BakeWrangler_Socket_Color', "Color")
        self.inputs.new('BakeWrangler_Socket_Float', "Gamma")
        # Sockets OUT
        self.outputs.new('BakeWrangler_Socket_Color', "Color")



# Output node that specifies the path to a file where a bake should be saved along with size and format information.
# Takes input from the outputs of a bake pass node. Connecting multiple inputs will cause higher position inputs to
# be over written by lower ones. Eg: Having a color input and an R input would cause the R channel of the color data
# to be overwritten by the data connected tot he R input.
class BakeWrangler_Output_Image_Path(BakeWrangler_Tree_Node, Node):
    '''Output image path node'''
    bl_label = 'Output Image Path'
    bl_width_default = 160

    # Returns the most identifying string for the node
    def get_name(self):
        name = BakeWrangler_Tree_Node.get_name(self)
        if self.inputs['Split Output'].get_name():
            name += " (%s)" % (self.inputs['Split Output'].get_name())
        return name

    def update_inputs(self):
        BakeWrangler_Tree_Node.update_inputs(self, 'BakeWrangler_Socket_Color', "Color", {'Alpha':'BakeWrangler_Socket_ChanMap'})
        settings = self.get_settings()
        if settings:
            if settings['img_color_mode'] != 'RGBA':
                for input in self.inputs:
                    if input.name == 'Alpha' and input.enabled:
                        input.enabled = False
            else:
                idx = 0
                for input in self.inputs:
                    if input.name == 'Color':
                        if input.is_linked:
                            self.inputs[idx+1].enabled = True
                        else:
                            self.inputs[idx+1].enabled = False
                    idx += 1

    # Try to get nodes settings from local or global node
    def get_settings(self, validating=False):
        settings = None
        if 'Settings' in self.inputs:
            settings = get_input(self.inputs["Settings"])
        if not settings:
            settings = self.id_data.get_pinned_settings("OutputSettings")
        if validating:
            img_non_color = None
            if not settings:
                return settings, img_non_color
            if 'Non-Color' in bpy.types.ColorManagedInputColorspaceSettings.bl_rna.properties['name'].enum_items.keys():
                img_non_color = 'Non-Color'
            elif _prefs('img_non_color') is not None and (len(bpy.types.ColorManagedInputColorspaceSettings.bl_rna.properties['name'].enum_items.keys()) - 1) >= int(_prefs('img_non_color')):
                img_non_color = bpy.types.ColorManagedInputColorspaceSettings.bl_rna.properties['name'].enum_items.keys()[_prefs('img_non_color')]
            settings.img_non_color = img_non_color
            return settings, img_non_color
        if not settings:
            # No local or pinned settings
            return None
        output_settings = {}
        output_settings['img_non_color']        = settings.img_non_color
        output_settings['img_xres']             = settings.img_xres
        output_settings['img_yres']             = settings.img_yres
        output_settings['img_clear']            = settings.img_clear
        output_settings['fast_aa']              = settings.fast_aa
        output_settings['fast_aa_lvl']          = settings.fast_aa_lvl
        output_settings['img_type']             = settings.img_type
        output_settings['img_udim']             = settings.img_udim
        output_settings['img_color_space']      = settings.img_color_space
        output_settings['img_use_float']        = settings.img_use_float
        output_settings['img_jpeg2k_cinema']    = settings.img_jpeg2k_cinema
        output_settings['img_jpeg2k_cinema48']  = settings.img_jpeg2k_cinema48
        output_settings['img_jpeg2k_ycc']       = settings.img_jpeg2k_ycc
        output_settings['img_dpx_log']          = settings.img_dpx_log
        output_settings['marginer']             = settings.marginer
        output_settings['marginer_size']        = settings.marginer_size
        output_settings['marginer_fill']        = settings.marginer_fill

        output_settings['img_color_mode']       = None
        if settings.img_type in ['BMP', 'JPEG', 'CINEON', 'HDR']:
            output_settings['img_color_mode']   = settings.img_color_mode_noalpha
        elif settings.img_type in ['IRIS', 'PNG', 'JPEG2000', 'TARGA', 'TARGA_RAW', 'DPX', 'OPEN_EXR_MULTILAYER', 'OPEN_EXR', 'TIFF']:
            output_settings['img_color_mode']   = settings.img_color_mode

        output_settings['img_color_depth']      = None
        if settings.img_type in ['PNG', 'TIFF']:
            output_settings['img_color_depth']  = settings.img_color_depth_8_16
        elif settings.img_type == 'JPEG2000':
            output_settings['img_color_depth']  = settings.img_color_depth_8_12_16
        elif settings.img_type == 'DPX':
            output_settings['img_color_depth']  = settings.img_color_depth_8_10_12_16
        elif settings.img_type in ['OPEN_EXR_MULTILAYER', 'OPEN_EXR']:
            output_settings['img_color_depth']  = settings.img_color_depth_16_32

        output_settings['img_quality']          = None
        if settings.img_type == 'PNG':
            output_settings['img_quality']      = settings.img_compression
        elif settings.img_type in ['JPEG', 'JPEG2000']:
            output_settings['img_quality']      = settings.img_quality

        output_settings['img_codec']            = None
        if settings.img_type == 'JPEG2000':
            output_settings['img_codec']        = settings.img_codec_jpeg2k
        elif settings.img_type in ['OPEN_EXR', 'OPEN_EXR_MULTILAYER']:
            output_settings['img_codec']        = settings.img_codec_openexr
        elif settings.img_type == 'TIFF':
            output_settings['img_codec']        = settings.img_codec_tiff

        output_settings['img_path']             = self.get_full_path()
        
        return output_settings

    # Check node settings are valid to bake. Returns true/false, plus error message(s).
    def validate(self, is_primary=False):
        valid = [True]
        # Validate has Settings
        settings, none_color = self.get_settings(True)
        if not settings:
            valid[0] = False
            valid.append([_print("Settings missing", node=self, ret=True), ": No pinned or connected output settings found"])
            return valid
        if not none_color:
            valid[0] = False
            valid.append([_print("Non-standard color spaces", node=self, ret=True), ": Please set up your color space in addon preferences"])
            return valid
        # Validate inputs
        has_valid_input = False
        for input in self.inputs:
            if input.bl_idname == 'BakeWrangler_Socket_Color' and input.islinked() and input.valid:
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
            valid.append([_print("Input error", node=self, ret=True), ": No valid inputs connected"])
        # Validate file path
        self.img_path = self.get_full_path()
        if not os.path.isdir(os.path.abspath(self.img_path)):
            # Try creating the path if enabled in prefs
            if _prefs("make_dirs") and not os.path.exists(os.path.abspath(self.img_path)):
                try:
                    os.makedirs(os.path.abspath(self.img_path))
                except OSError as err:
                    valid[0] = False
                    valid.append([_print("Path error", node=self, ret=True), ": Trying to create path at '%s'" % (err.strerror)])
                    return valid
            else:
                valid[0] = False
                valid.append([_print("Path error", node=self, ret=True), ": Invalid path '%s'" % (os.path.abspath(self.img_path))])
                return valid
        # Check if there is read/write access to the file/directory
        settings = self.get_settings()
        file_path = os.path.join(os.path.abspath(self.img_path), self.name_with_ext(settings['img_type']))
        if self.use_tokens():
            # Remove tokens to check for file writing to location
            file_path = file_path.replace("<OBJECT>", "")
            file_path = file_path.replace("<SUFFIX>", "")
            file_path = file_path.replace("<UDIM>", "")        
            file_path = file_path.replace("<FRAME>", "")
        if os.path.exists(file_path):
            if os.path.isfile(file_path):
                # It exists so try to open it r/w
                try:
                    file = open(file_path, "a")
                except OSError as err:
                    valid[0] = False
                    valid.append([_print("File error", node=self, ret=True), ": Trying to open file at '%s'" % (err.strerror)])
                else:
                    # See if it can be read as an image
                    file.close()
                    file_img = bpy.data.images.load(file_path)
                    if not len(file_img.pixels):
                        valid[0] = False
                        valid.append([_print("File error", node=self, ret=True), ": File exists but doesn't seem to be a known image format"])
                    bpy.data.images.remove(file_img)
            else:
                # It exists but isn't a file
                valid[0] = False
                valid.append([_print("File error", node=self, ret=True), ": File exists but isn't a regular file '%s'" % (file_path)])
        else:
            # See if it can be created
            try:
                file = open(file_path, "a")
            except OSError as err:
                valid[0] = False
                valid.append([_print("File error", node=self, ret=True), ": %s trying to create file at '%s'" % (err.strerror, file_path)])
            else:
                file.close()
                os.remove(file_path)
        # Validated
        return valid

    # Get full path, removing any relative references
    def get_full_path(self):
        return self.inputs["Split Output"].get_full_path()

    # Return the file name with the correct image type extension (unless it has an existing unknown extension)
    def name_with_ext(self, suffix=""):
        settings = self.get_settings()
        return self.inputs["Split Output"].name_with_ext(suffix, settings['img_type'])
        
    def use_tokens(self):
        return self.inputs["Split Output"].use_tokens()
        
    # Return frame ranges or padding or animated seed if set, otherwise empty list, None or False
    def frame_range(self, padding=False, animated=False, pdata=False):
        return self.inputs["Split Output"].frame_range(padding, animated, pdata)

    # Return a dict of format settings
    def get_format(self):
        format = {}
        for prop in self.rna_type.properties.keys():
            format[prop] = getattr(self, prop)
        return format
    
    # Return a dict of output files with their connected input
    def get_output_files(self):
        output_files = {}
        for input in self.inputs:
            if input.bl_idname == 'BakeWrangler_Socket_Color' and input.islinked() and input.valid:
                output_files[self.name_with_ext(suffix=input.suffix)] = input
        return output_files
    
    # Get list of mesh objects from the split output socket
    def get_split_objects(self):
        objs = []
        split = self.inputs["Split Output"].get_split()
        if split and len(split):
            for splt in split:
                if splt.bl_idname == 'BakeWrangler_Bake_Mesh':
                    objs += prune_objects(splt.inputs["Target"].get_objects(only_mesh=True))
                elif splt.bl_idname == 'BakeWrangler_Input_ObjectList':
                    objs += prune_objects(splt.get_objects(only_mesh=True))
                elif splt.bl_idname == 'BakeWrangler_Bake_Material':
                    objs += splt.get_materials()
                elif splt.bl_idname == 'BakeWrangler_Sort_Meshes':
                    sobj = []
                    for inpt in splt.inputs:
                        if inpt.islinked() and inpt.valid:
                            if get_input(inpt).bl_idname == 'BakeWrangler_Bake_Material':
                                for mat in get_input(inpt).get_materials():
                                    sobj += [[mat]]
                            sobj += splt.get_objects('TARGET', inpt)
                    for grp in sobj:
                        grp[0].append(grp[3])
                        objs.append(grp[0])
            objs = prune_objects(objs)
        if len(objs): return objs
        else: return None
    
    # Get a list of unique objects used as either source or target
    def get_unique_objects(self, type, for_auto_cage=False):
        def get_meshes(socket, meshes):
            pas = get_input(socket)
            if pas:
                if pas.bl_idname == 'BakeWrangler_Bake_Pass':
                    meshes += pas.get_inputs()
                else:
                    for input in pas.inputs:
                        get_meshes(input, meshes)
        meshes = []
        for input in self.inputs:
            if input.name in ["Color", "Alpha"]:
                get_meshes(input, meshes)
        objs = []
        for mesh in meshes:
            if len(mesh) > 1:
                objs += mesh[0].get_unique_objects(type, for_auto_cage, mesh[1])
            else:
                objs += mesh[0].get_unique_objects(type, for_auto_cage)
        objs = prune_objects(objs)
        if for_auto_cage:
            return objs
        return objs
        
    img_ext = (
        ('BMP', ".bmp"),
        ('IRIS', ".rgb"),
        ('PNG', ".png"),
        ('JPEG', ".jpg"),
        ('JPEG2000', ".jp2"),
        ('TARGA', ".tga"),
        ('TARGA_RAW', ".tga"),
        ('CINEON', ".cin"),
        ('DPX', ".dpx"),
        ('OPEN_EXR_MULTILAYER', ".exr"),
        ('OPEN_EXR', ".exr"),
        ('HDR', ".hdr"),
        ('TIFF', ".tif"),
    )

    # Core settings
    img_path: bpy.props.StringProperty(name="Output Path", description="Path to save image in", default="", subtype='DIR_PATH')
    
    def init(self, context):
        BakeWrangler_Tree_Node.init(self, context)
        # Sockets IN
        self.inputs.new('BakeWrangler_Socket_SplitOutput', "Split Output")
        self.inputs.new('BakeWrangler_Socket_Setting', "Settings")
        self.inputs.new('BakeWrangler_Socket_Color', "Color")
        self.inputs.new('BakeWrangler_Socket_ChanMap', "Alpha")
        # Sockets OUT
        self.outputs.new('BakeWrangler_Socket_Bake', "Bake")
        # Prefs
        self.inputs['Split Output'].disp_path = _prefs("def_outpath")
        self.inputs['Split Output'].img_name = _prefs("def_outname")

    def draw_buttons(self, context, layout):
        pass
        #colnode = layout.column(align=False)
        #colpath = colnode.column(align=True)
        #colpath.prop(self, "disp_path", text="")
        #colpath.prop(self, "img_name", text="")


class BakeWrangler_Output_Vertex_Cols(BakeWrangler_Tree_Node, Node):
    '''Output vertex colors node'''
    bl_label = 'Output Vertex Colors'
    bl_width_default = 160
    
    vert_files = []

    # Returns the most identifying string for the node
    def get_name(self):
        name = BakeWrangler_Tree_Node.get_name(self)
        return name

    # Make sure an empty input is always at the bottom
    def update_inputs(self):
        BakeWrangler_Tree_Node.update_inputs(self, 'BakeWrangler_Socket_Color', "Color")
    
    # All objects are split objects? We don't use this
    def get_split_objects(self):
        return None
    
    # Image settings are mostly irrelevant here, mostly static values will be set
    def get_settings(self, validating=False):
        output_settings = {}
        output_settings['vcol']                 = True
        output_settings['vcol_type']            = self.vcol_type
        output_settings['vcol_domain']          = self.vcol_domain
        output_settings['img_udim']             = False
        output_settings['marginer']             = False
        output_settings['marginer_size']        = 0
        output_settings['marginer_fill']        = False
        output_settings['img_color_mode']       = None
        output_settings['img_color_depth']      = None
        output_settings['img_path']             = None
        return output_settings
        
    # Check node settings are valid to bake. Returns true/false, plus error message(s).
    def validate(self, is_primary=False):
        valid = [True]
        # Validate inputs
        has_valid_input = False
        for input in self.inputs:
            if input.bl_idname == 'BakeWrangler_Socket_Color' and input.islinked() and input.valid:
                if not input.suffix or not len(input.suffix):
                    valid[0] = False
                    valid.append([_print("Input error", node=self, ret=True), ": Connected vertex output requires valid name for data"])
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
            valid.append([_print("Input error", node=self, ret=True), ": No valid inputs connected"])
        return valid
    
    vcol_domains = (
        ('POINT', "Vertex", "Vertex"),
        ('CORNER', "Face Corner", "Face Corner"),
    )
    
    vcol_types = (
        ('FLOAT_COLOR', "Color", "32-bit floating point values"),
        ('BYTE_COLOR', "Byte Color", "8-bit integer values"),
    )
    
    # Core settings
    vcol_domain: bpy.props.EnumProperty(name="Domain", description="Type of element the data is stored on", items=vcol_domains, default='POINT')
    vcol_type: bpy.props.EnumProperty(name="Data Type", description="Type of data stored in element", items=vcol_types, default='FLOAT_COLOR')
        
    def init(self, context):
        BakeWrangler_Tree_Node.init(self, context)
        # Sockets IN
        self.inputs.new('BakeWrangler_Socket_Color', "Color")
        # Sockets OUT
        self.outputs.new('BakeWrangler_Socket_Bake', "Bake")
        # Prefs
        
    def draw_buttons(self, context, layout):
        row = layout.row(align=True)
        col = layout.column(align=True)
        if not len(self.vert_files):
            row.operator("bake_wrangler.dummy_vcol", icon='CHECKMARK', text="Apply")
            row.operator("bake_wrangler.dummy_vcol", icon='PANEL_CLOSE', text="Discard")
        else:
            op1 = row.operator("bake_wrangler.apply_vertcols", icon='CHECKMARK', text="Apply")
            op1.tree = self.id_data.name
            op1.node = self.name
            op2 = row.operator("bake_wrangler.discard_vertcols", icon='PANEL_CLOSE', text="Discard")
            op2.tree = self.id_data.name
            op2.node = self.name
        
        col.prop(self, "vcol_domain", text="")
        col.prop(self, "vcol_type", text="")
        
        
# Output controller node provides batch execution of multiple connected bake passes.
class BakeWrangler_Output_Batch_Bake(BakeWrangler_Tree_Node, Node):
    '''Output controller oven node'''
    bl_label = 'Batch Bake'
    
    vert_files = []

    # Makes sure there is always one empty input socket at the bottom by adding and removing sockets
    def update_inputs(self):
        BakeWrangler_Tree_Node.update_inputs(self, 'BakeWrangler_Socket_Bake', "Bake")

    # Check node settings are valid to bake. Returns true/false, plus error message(s).
    def validate(self, is_primary=True):
        valid = [True]
        # Batch mode needs to avoid validating the same things more than once. Collect a
        # unique list of the passes before validating them.
        img_node_list = []
        pass_node_list = []
        for input in self.inputs:
            if input.islinked() and input.valid:
                img_node = follow_input_link(input.links[0]).from_node
                if not img_node_list.count(img_node):
                    img_node_list.append(img_node)
                    for img_node_input in img_node.inputs:
                        if img_node_input.islinked() and img_node_input.valid:
                            pass_node = follow_input_link(img_node_input.links[0]).from_node
                            if not pass_node_list.count(pass_node):
                                pass_node_list.append(pass_node)
        # Validate all the listed nodes
        has_valid_input = False
        for node in img_node_list:
            img_node_valid = node.validate()
            if not img_node_valid.pop(0):
                valid[0] = False
            if valid[0]:
                has_valid_input = True
            valid += img_node_valid
        for node in pass_node_list:
            pass_node_valid = node.validate()
            if not pass_node_valid.pop(0):
                valid[0] = False
            valid += pass_node_valid
        errs = len(valid)
        if not has_valid_input and errs < 2:
            valid[0] = False
            valid.append([_print("Input error", node=self, ret=True), ": No valid inputs connected"])
        # Validate pre and post scripts if set to external file
        if self.loc_pre == 'EXT':
            file_path = self.script_pre_can
            # Validate file path
            if os.path.exists(file_path):
                if os.path.isfile(file_path):
                    # It exists so try to open it for read
                    try:
                        file = open(file_path, "r")
                    except OSError as err:
                        valid[0] = False
                        valid.append([_print("Pre-Script file error", node=self, ret=True), ": Trying to open file at '%s'" % (err.strerror)])
                else:
                    # It exists but isn't a file
                    valid[0] = False
                    valid.append([_print("Pre-Script file error", node=self, ret=True), ": File exists but isn't a regular file '%s'" % (file_path)])
        # See if the pre script compiles if set
        if self.loc_pre != 'NON':
            if self.loc_pre == 'INT':
                pre_scr = self.script_pre_int.as_string()
            elif self.loc_pre == 'EXT':
                with open(self.script_pre_can, "r") as scr:
                    pre_scr = scr.read()
            try:
                compile(pre_scr, '<string>', 'exec')
            except SyntaxError or ValueError as err:
                valid[0] = False
                valid.append([_print("Pre-Script compile error", node=self, ret=True), ": %s" % (str(err))])
        if self.loc_post == 'EXT':
            file_path = self.script_post_can
            # Validate file path
            if os.path.exists(file_path):
                if os.path.isfile(file_path):
                    # It exists so try to open it for read
                    try:
                        file = open(file_path, "r")
                    except OSError as err:
                        valid[0] = False
                        valid.append([_print("Post-Script file error", node=self, ret=True), ": Trying to open file at '%s'" % (err.strerror)])
                else:
                    # It exists but isn't a file
                    valid[0] = False
                    valid.append([_print("Post-Script file error", node=self, ret=True), ": File exists but isn't a regular file '%s'" % (file_path)])
        # See if the pre script compiles if set
        if self.loc_post != 'NON':
            if self.loc_post == 'INT':
                post_scr = self.script_post_int.as_string()
            elif self.loc_post == 'EXT':
                with open(self.script_post_can, "r") as scr:
                    post_scr = scr.read()
            try:
                compile(post_scr, '<string>', 'exec')
            except SyntaxError or ValueError as err:
                valid[0] = False
                valid.append([_print("Post-Script compile error", node=self, ret=True), ": %s" % (str(err))])
        # Everything validated
        return valid
    
    # Get a list of unique objects used as either source or target
    def get_unique_objects(self, type):
        objs = []
        for input in self.inputs:
            input = get_input(input)
            if input and input.bl_idname == 'BakeWrangler_Output_Image_Path':
                objs += input.get_unique_objects(type)
        objs = prune_objects(objs)
        objs_single = []
        for obj in objs:
            objs_single.append(obj[0])
        return objs_single
        
    # Generate enum of base collection types
    def get_collection_types(self, context):
        col_types = []
        for prop in bpy.data.bl_rna.properties:
            if prop.type == 'COLLECTION':
                col_types.append((prop.identifier, prop.name, prop.description))
        return col_types

    # Generate enum of props
    def get_user_props(self, context):
        props = []
        if self.user_prop_objt:
            for prop in self.user_prop_objt.keys():
                props.append((prop, prop, prop + " custom property"))
        return props

    # Set the nodes background color to red when shutdown is enabled
    def shutdown_update(self, context):
        if self.shutdown_after:
            self.use_custom_color = True
            self.color = [0.9, 0, 0]
        else:
            self.use_custom_color = False
            self.color = [0.608, 0.608, 0.608]
    
    # Get full path, removing any relative references
    def update_pre_script(self, context):
        cwd = os.path.dirname(bpy.data.filepath)
        self.script_pre_can = os.path.normpath(os.path.join(cwd, bpy.path.abspath(self.script_pre)))
    
    # Get full path, removing any relative references
    def update_post_script(self, context):
        cwd = os.path.dirname(bpy.data.filepath)
        self.script_post_can = os.path.normpath(os.path.join(cwd, bpy.path.abspath(self.script_post)))
        
    loc = (
        ('EXT', "External", ""),
        ('INT', "Internal", ""),
        ('NON', "None", ""),
    )
    
    loc_pre: bpy.props.EnumProperty(name="Script Location", description="Either internal or external file", items=loc, default='NON')
    script_pre: bpy.props.StringProperty(name="Script path", description="Path to python script to run", default="", subtype='FILE_PATH', update=update_pre_script)
    script_pre_can: bpy.props.StringProperty(name="Canical Script File", description="Canicial path to script", default="", subtype='FILE_PATH')
    script_pre_int: bpy.props.PointerProperty(name="Script", description="Python script to run", type=bpy.types.Text)
    
    loc_post: bpy.props.EnumProperty(name="Script Location", description="Either internal or external file", items=loc, default='NON')
    script_post: bpy.props.StringProperty(name="Script path", description="Path to python script to run", default="", subtype='FILE_PATH', update=update_post_script)
    script_post_can: bpy.props.StringProperty(name="Canical Script File", description="Canicial path to script", default="", subtype='FILE_PATH')
    script_post_int: bpy.props.PointerProperty(name="Script", description="Python script to run", type=bpy.types.Text)
    
    user_prop: bpy.props.BoolProperty(name="User Property", description="Enable custom user property incrementer", default=False)
    user_prop_type: bpy.props.EnumProperty(name="Type", description="Type of data property is on", items=get_collection_types)
    user_prop_objt: bpy.props.PointerProperty(name="Data", description="Data property is on", type=bpy.types.ID)
    user_prop_name: bpy.props.EnumProperty(name="Name", description="Name of the property", items=get_user_props)
    user_prop_zero: bpy.props.BoolProperty(name="Zero on Bake", description="Resets property to zero when bake starts", default=True)
    shutdown_after: bpy.props.BoolProperty(name="Shutdown on Completion", description="Attempt to shutdown system after batch bake completes", default=False, update=shutdown_update)

    def init(self, context):
        BakeWrangler_Tree_Node.init(self, context)
        self.inputs.new('BakeWrangler_Socket_Bake', "Bake")

    def draw_buttons(self, context, layout):
        BakeWrangler_Tree_Node.draw_bake_button(self, layout, 'OUTLINER', "Bake All")
        row = layout.row(align=True)
        if not len(self.vert_files):
            row.operator("bake_wrangler.dummy_vcol", icon='CHECKMARK', text="Apply")
            row.operator("bake_wrangler.dummy_vcol", icon='PANEL_CLOSE', text="Discard")
        else:
            op1 = row.operator("bake_wrangler.apply_vertcols", icon='CHECKMARK', text="Apply")
            op1.tree = self.id_data.name
            op1.node = self.name
            op2 = row.operator("bake_wrangler.discard_vertcols", icon='PANEL_CLOSE', text="Discard")
            op2.tree = self.id_data.name
            op2.node = self.name
        layout.label(text="Bake Images:")

    def draw_buttons_ext(self, context, layout):
        col = layout.column(align=False)
        
        col.label(text="Pre-Bake Script:")
        row = col.row(align=True)
        row.prop_enum(self, "loc_pre", "NON")
        row.prop_enum(self, "loc_pre", "INT")
        row.prop_enum(self, "loc_pre", "EXT")
        if self.loc_pre == 'EXT':
            col.prop(self, "script_pre", text="")
        elif self.loc_pre == 'INT':
            col.prop_search(self, "script_pre_int", bpy.data, "texts", text="")

        col.label(text="Post-Bake Script:")
        row = col.row(align=True)
        row.prop_enum(self, "loc_post", "NON")
        row.prop_enum(self, "loc_post", "INT")
        row.prop_enum(self, "loc_post", "EXT")
        if self.loc_post == 'EXT':
            col.prop(self, "script_post", text="")
        elif self.loc_post == 'INT':
            col.prop_search(self, "script_post_int", bpy.data, "texts", text="")
        
        row = col.row(align=True)
        row.prop(self, "user_prop", text="Increment Property")
        if self.user_prop:
            col.prop(self, "user_prop_type")
            col.prop_search(self, "user_prop_objt", bpy.data, self.user_prop_type)
            col.prop(self, "user_prop_name")
            col.prop(self, "user_prop_zero")
        col.prop(self, "shutdown_after")



#
# Node Categories
#

import nodeitems_utils
from nodeitems_utils import NodeCategory, NodeItem

# Base class for the node category menu system
class BakeWrangler_Node_Category(NodeCategory):
    @classmethod
    def poll(cls, context):
        tree_type = getattr(context.space_data, "tree_type", None)
        return tree_type == 'BakeWrangler_Tree'

# List of all bakery nodes put into categories with identifier, name
BakeWrangler_Node_Categories = [
    BakeWrangler_Node_Category('BakeWrangler_Settings', "Settings", items=[
        NodeItem("BakeWrangler_Settings"),
        NodeItem("BakeWrangler_MeshSettings"),
        NodeItem("BakeWrangler_SampleSettings"),
        NodeItem("BakeWrangler_PassSettings"),
        NodeItem("BakeWrangler_OutputSettings"),
    ]),
    BakeWrangler_Node_Category('BakeWrangler_Nodes', "Bake", items=[
        NodeItem("BakeWrangler_Input_Filenames"),
        NodeItem("BakeWrangler_Input_ObjectList"),
        NodeItem("BakeWrangler_Bake_Billboard"),
        NodeItem("BakeWrangler_Bake_Material"),
        NodeItem("BakeWrangler_Bake_Mesh"),
        NodeItem("BakeWrangler_Sort_Meshes"),
        NodeItem("BakeWrangler_Bake_Pass"),
        NodeItem("BakeWrangler_Output_Image_Path"),
        NodeItem("BakeWrangler_Output_Vertex_Cols"),
        NodeItem("BakeWrangler_Output_Batch_Bake"),
    ]),
    BakeWrangler_Node_Category('BakeWrangler_Post', "Post", items=[
        NodeItem("BakeWrangler_Channel_Map"),
        NodeItem("BakeWrangler_Post_MixRGB"),
        NodeItem("BakeWrangler_Post_SplitRGB"),
        NodeItem("BakeWrangler_Post_JoinRGB"),
        NodeItem("BakeWrangler_Post_Math"),
        NodeItem("BakeWrangler_Post_Gamma"),
    ]),
    BakeWrangler_Node_Category('BakeWrangler_Layout', "Layout", items=[
        NodeItem("NodeFrame"),
        NodeItem("NodeReroute"),
    ]),
]


#
# Registration
#

# All bakery classes that need to be registered
classes = (
    BakeWrangler_Operator_Dummy,
    BakeWrangler_Operator_Dummy_VCol,
    BakeWrangler_Operator_FilterToggle,
    BakeWrangler_Operator_DoubleVal,
    BakeWrangler_Operator_PickMenuEnum,
    BakeWrangler_Operator_AddSelected,
    BakeWrangler_Operator_DiscardBakedVertCols,
    BakeWrangler_Operator_ApplyBakedVertCols,
    BakeWrangler_Operator_BakeStop,
    BakeWrangler_Operator_BakePass,
    BakeWrangler_Tree,
    BakeWrangler_Socket_Object,
    BakeWrangler_Socket_Material,
    BakeWrangler_Socket_Mesh,
    BakeWrangler_Socket_Color,
    BakeWrangler_Socket_ChanMap,
    BakeWrangler_Socket_Float,
    BakeWrangler_Socket_Bake,
    BakeWrangler_Socket_MeshSetting,
    BakeWrangler_Socket_PassSetting,
    BakeWrangler_Socket_SampleSetting,
    BakeWrangler_Socket_OutputSetting,
    BakeWrangler_Socket_ObjectNames,
    BakeWrangler_Socket_SplitOutput,
    BakeWrangler_Socket_Setting,
    BakeWrangler_MeshSettings,
    BakeWrangler_Settings,
    BakeWrangler_SampleSettings,
    BakeWrangler_PassSettings,
    BakeWrangler_OutputSettings,
    BakeWrangler_Input_ObjectList,
    BakeWrangler_Input_Filenames,
    BakeWrangler_Bake_Billboard,
    BakeWrangler_Bake_Material,
    BakeWrangler_Bake_Mesh,
    BakeWrangler_Sort_Meshes,
    BakeWrangler_Bake_Pass,
    BakeWrangler_Channel_Map,
    BakeWrangler_Post_MixRGB,
    BakeWrangler_Post_SplitRGB,
    BakeWrangler_Post_JoinRGB,
    BakeWrangler_Post_Math,
    BakeWrangler_Post_Math_OpMenu,
    BakeWrangler_Post_Gamma,
    BakeWrangler_Output_Image_Path,
    BakeWrangler_Output_Vertex_Cols,
    BakeWrangler_Output_Batch_Bake,
)


def register():
    from bpy.utils import register_class
    for cls in classes:
        register_class(cls)
    nodeitems_utils.register_node_categories('BakeWrangler_Nodes', BakeWrangler_Node_Categories)


def unregister():
    nodeitems_utils.unregister_node_categories('BakeWrangler_Nodes')
    from bpy.utils import unregister_class
    for cls in reversed(classes):
        unregister_class(cls)



if __name__ == "__main__":
    register()
