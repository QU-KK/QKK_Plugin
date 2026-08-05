import bpy
from ..base_node import SN_ScriptingBaseNode


class SN_MB_Purge_By_Type_Node(SN_ScriptingBaseNode, bpy.types.Node):

    bl_idname = "SN_MB_Purge_By_Type_Node"
    bl_label = "MB_Purge By Type"
    node_color = "PROGRAM"
    bl_width_default = 160

    def on_create(self, context):
        # create your sockets here

        # inputs
        self.add_execute_input()

        # outputs
        self.add_execute_output()
        self.add_integer_output("Purge Count")

    # Custom Enum Property
    type: bpy.props.EnumProperty(name="",
                                 items=[("Actions", "Actions", "", 115, 0),
                                        ("Armatures", "Armatures", "", 172, 1),
                                        ("Brushes", "Brushes", "", 182, 2),
                                        ("Cache File", "Cache File", "", 184, 3),
                                        ("Camera", "Camera", "", 168, 4),
                                        ("Collections", "Collections", "", 250, 5),
                                        ("Curve", "Curve", "", 161, 6),
                                        ("Hair Curves", "Hair Curves", "", 651, 7),
                                        ("Font", "Font", "", 186, 8),
                                        ("Grease Pencil", "Grease Pencil", "", 197, 9),
                                        ("Images", "Images", "", 183, 10),
                                        ("Keys", "Keys", "", 176, 11),
                                        ("Lattice", "Lattice", "", 163, 12),
                                        ("Library", "Library", "", 170, 13),
                                        ("Light", "Light", "", 78, 14),
                                        ("Light Probe", "Light Probe", "", 326, 15),
                                        ("Line Style", "Line Style", "", 198, 16),
                                        ("Mask", "Mask", "", 467, 17),
                                        ("Materials", "Materials", "", 79, 18),
                                        ("Meshes", "Meshes", "", 160, 19),
                                        ("Metaball", "Metaball", "", 162, 20),
                                        ("Movie Clip", "Movie Clip", "", 123, 21),
                                        ("Node Groups", "Node Groups", "", 119, 22),
                                        ("Objects", "Objects", "", 159, 23),
                                        ("Paint Curve", "Paint Curve", "", 321, 24),
                                        ("Palette", "Pallet", "", 54, 25),
                                        ("Particle", "Particle", "", 88, 26),
                                        ("Point Cloud", "Point Cloud", "", 654, 27),
                                        ("Scene", "Scene", "", 156, 28),
                                        # ("Simulation", "Simulation", "", 89, 29),
                                        ("Sound", "Sound", "", 114, 30),
                                        ("Speaker", "Speaker", "", 90, 31),
                                        ("Text", "Text", "", 112, 32),
                                        ("Texture", "Texture", "", 80, 33),
                                        ("Volume", "Volume", "", 657, 34),
                                        ("Window Manager", "Window Manager", "", 26, 35),
                                        ("Workspace", "Workspace", "", 27, 36),
                                        ("World", "World", "", 82, 37),
                                        ],
                                 update=SN_ScriptingBaseNode._evaluate)

    def evaluate(self, context):
		# generate the code here
        self.code = f"""
        
                    if {self.type == "Actions"}:
                        purge_count = 0
                        for a in range(len(bpy.data.actions)-1,-1,-1):
                            if (bpy.data.actions[a].users == 0):
                                bpy.data.actions.remove(action=bpy.data.actions[a], )
                                purge_count += 1
                                
                    if {self.type == "Armatures"}:
                        purge_count = 0
                        for ar in range(len(bpy.data.armatures)-1,-1,-1):
                            if (bpy.data.armatures[ar].users == 0):
                                bpy.data.armatures.remove(armature=bpy.data.armatures[ar], )
                                purge_count += 1
                                
                    if {self.type == "Brushes"}:
                        purge_count = 0
                        for b in range(len(bpy.data.brushes)-1,-1,-1):
                            if (bpy.data.brushes[b].users == 0):
                                bpy.data.brushes.remove(brush=bpy.data.brushes[b], )
                                purge_count += 1
                                
                    if {self.type == "Cache File"}:
                        purge_count = 0
                        for cf in range(len(bpy.data.cache_files)-1,-1,-1):
                            if (bpy.data.cache_files[cf].users == 0):
                                bpy.data.cache_files.remove(cache_file=bpy.data.brushes[cf], )
                                purge_count += 1
                                
                    if {self.type == "Camera"}:
                        purge_count = 0
                        for c in range(len(bpy.data.cameras)-1,-1,-1):
                            if (bpy.data.cameras[c].users == 0):
                                bpy.data.cameras.remove(camera=bpy.data.cameras[c], )
                                purge_count += 1

                    if {self.type == "Collections"}:
                        purge_count = 0
                        for c in range(len(bpy.data.collections)-1,-1,-1):
                            if (bpy.data.collections[c].users == 0):
                                bpy.data.collections.remove(collection=bpy.data.collections[c], )
                                purge_count += 1
                                
                    if {self.type == "Curve"}:
                        purge_count = 0
                        for c in range(len(bpy.data.curves)-1,-1,-1):
                            if (bpy.data.curves[c].users == 0):
                                bpy.data.curves.remove(curve=bpy.data.curves[c], )
                                purge_count += 1
                                
                    if {self.type == "Hair Curves"}:
                        purge_count = 0
                        for hc in range(len(bpy.data.hair_curves)-1,-1,-1):
                            if (bpy.data.hair_curves[hc].users == 0):
                                bpy.data.hair_curves.remove(curves=bpy.data.hair_curves[hc], )
                                purge_count += 1
                                
                    if {self.type == "Font"}:
                        purge_count = 0
                        for f in range(len(bpy.data.fonts)-1,-1,-1):
                            if (bpy.data.fonts[f].users == 0):
                                bpy.data.fonts.remove(font=bpy.data.fonts[f], )
                                purge_count += 1
                                
                    if {self.type == "Grease Pencil"}:
                        purge_count = 0
                        for gp in range(len(bpy.data.grease_pencils)-1,-1,-1):
                            if (bpy.data.grease_pencils[gp].users == 0):
                                bpy.data.grease_pencils.remove(grease_pencil=bpy.data.grease_pencils[gp], )
                                purge_count += 1
                                
                    if {self.type == "Images"}:
                        purge_count = 0
                        for i in range(len(bpy.data.images)-1,-1,-1):
                            if (bpy.data.images[i].users == 0):
                                bpy.data.images.remove(image=bpy.data.images[i], )
                                purge_count += 1
                                
                    if {self.type == "Keys"}:
                        purge_count = 0
                        for k in range(len(bpy.data.shape_keys)-1,-1,-1):
                            if (bpy.data.shape_keys[k].users == 0):
                                bpy.data.shape_keys.remove(key=bpy.data.shape_keys[k], )
                                purge_count += 1
                                
                    if {self.type == "Lattice"}:
                        purge_count = 0
                        for l in range(len(bpy.data.lattices)-1,-1,-1):
                            if (bpy.data.lattices[l].users == 0):
                                bpy.data.lattices.remove(lattice=bpy.data.lattices[l], )
                                purge_count += 1
                                
                    if {self.type == "Library"}:
                        purge_count = 0
                        for l in range(len(bpy.data.libraries)-1,-1,-1):
                            if (bpy.data.libraries[l].users == 0):
                                bpy.data.libraries.remove(library=bpy.data.libraries[l], )
                                purge_count += 1
                                
                    if {self.type == "Light"}:
                        purge_count = 0
                        for l in range(len(bpy.data.lights)-1,-1,-1):
                            if (bpy.data.lights[l].users == 0):
                                bpy.data.lights.remove(light=bpy.data.lights[l], )
                                purge_count += 1
                                
                    if {self.type == "Light Probe"}:
                        purge_count = 0
                        for l in range(len(bpy.data.lightprobes)-1,-1,-1):
                            if (bpy.data.lightprobes[l].users == 0):
                                bpy.data.lightprobes.remove(lightprobe=bpy.data.lightprobes[l], )
                                purge_count += 1
                                
                    if {self.type == "Line Style"}:
                        purge_count = 0
                        for l in range(len(bpy.data.linestyles)-1,-1,-1):
                            if (bpy.data.linestyles[l].users == 0):
                                bpy.data.linestyles.remove(linestyle=bpy.data.linestyles[l], )
                                purge_count += 1
                                
                    if {self.type == "Mask"}:
                        purge_count = 0
                        for m in range(len(bpy.data.masks)-1,-1,-1):
                            if (bpy.data.masks[m].users == 0):
                                bpy.data.masks.remove(mask=bpy.data.masks[m], )
                                purge_count += 1
                        
                    if {self.type == "Materials"}:
                        purge_count = 0
                        for m in range(len(bpy.data.materials)-1,-1,-1):
                            if (bpy.data.materials[m].users == 0):
                                bpy.data.materials.remove(material=bpy.data.materials[m], )
                                purge_count += 1
                                
                    if {self.type == "Meshes"}:
                        purge_count = 0
                        for m in range(len(bpy.data.meshes)-1,-1,-1):
                            if (bpy.data.meshes[m].users == 0):
                                bpy.data.meshes.remove(mesh=bpy.data.meshes[m], )
                                purge_count += 1
                                
                    if {self.type == "Metaball"}:
                        purge_count = 0
                        for m in range(len(bpy.data.metaballs)-1,-1,-1):
                            if (bpy.data.metaballs[m].users == 0):
                                bpy.data.metaballs.remove(metaball=bpy.data.metaballs[m], )
                                purge_count += 1
                                
                    if {self.type == "Movie Clip"}:
                        purge_count = 0
                        for m in range(len(bpy.data.movieclips)-1,-1,-1):
                            if (bpy.data.movieclips[m].users == 0):
                                bpy.data.movieclips.remove(movieclip=bpy.data.movieclips[m], )
                                purge_count += 1
                                
                    if {self.type == "Node Groups"}:
                        purge_count = 0
                        for ng in range(len(bpy.data.node_groups)-1,-1,-1):
                            if (bpy.data.node_groups[ng].users == 0):
                                bpy.data.node_groups.remove(tree=bpy.data.node_groups[ng], )
                                purge_count += 1

                    if {self.type == "Objects"}:
                        purge_count = 0
                        for o in range(len(bpy.data.objects)-1,-1,-1):
                            if (bpy.data.objects[o].users == 0):
                                bpy.data.objects.remove(object=bpy.data.objects[o], )
                                purge_count += 1
                                
                    if {self.type == "Paint Curve"}:
                        purge_count = 0
                        for pc in range(len(bpy.data.paint_curves)-1,-1,-1):
                            if (bpy.data.paint_curves[pc].users == 0):
                                bpy.data.paint_curves.remove(paint_curve=bpy.data.paint_curves[pc], )
                                purge_count += 1
                                
                    if {self.type == "Palette"}:
                        purge_count = 0
                        for p in range(len(bpy.data.palettes)-1,-1,-1):
                            if (bpy.data.palettes[p].users == 0):
                                bpy.data.palettes.remove(palette=bpy.data.palettes[p], )
                                purge_count += 1
                                
                    if {self.type == "Particle"}:
                        purge_count = 0
                        for p in range(len(bpy.data.particles)-1,-1,-1):
                            if (bpy.data.particles[p].users == 0):
                                bpy.data.particles.remove(particle=bpy.data.particles[p], )
                                purge_count += 1
                                
                    if {self.type == "Point Cloud"}:
                        purge_count = 0
                        for p in range(len(bpy.data.pointclouds)-1,-1,-1):
                            if (bpy.data.pointclouds[p].users == 0):
                                bpy.data.pointclouds.remove(pointcloud=bpy.data.pointclouds[p], )
                                purge_count += 1
                                
                    if {self.type == "Scene"}:
                        purge_count = 0
                        for s in range(len(bpy.data.scenes)-1,-1,-1):
                            if (bpy.data.scenes[s].users == 0):
                                bpy.data.scenes.remove(scene=bpy.data.scenes[s], )
                                purge_count += 1
                                
                    # if {self.type == "Simulation"}:
                    #     purge_count = 0
                    #     for s in range(len(bpy.data.simulations)-1,-1,-1):
                    #         if (bpy.data.simulations[s].users == 0):
                    #             bpy.data.simulations.remove(simulation=bpy.data.simulations[s], )
                    #             purge_count += 1
                                
                    if {self.type == "Sound"}:
                        purge_count = 0
                        for s in range(len(bpy.data.sounds)-1,-1,-1):
                            if (bpy.data.sounds[s].users == 0):
                                bpy.data.sounds.remove(sound=bpy.data.sounds[s], )
                                purge_count += 1
                                
                    if {self.type == "Speaker"}:
                        purge_count = 0
                        for s in range(len(bpy.data.speakers)-1,-1,-1):
                            if (bpy.data.speakers[s].users == 0):
                                bpy.data.speakers.remove(speaker=bpy.data.speakers[s], )
                                purge_count += 1
                                
                    if {self.type == "Text"}:
                        purge_count = 0
                        for txt in range(len(bpy.data.texts)-1,-1,-1):
                            if (bpy.data.texts[txt].users == 0):
                                bpy.data.texts.remove(text=bpy.data.texts[txt], )
                                purge_count += 1
                                
                    if {self.type == "Texture"}:
                        purge_count = 0
                        for tex in range(len(bpy.data.textures)-1,-1,-1):
                            if (bpy.data.textures[tex].users == 0):
                                bpy.data.textures.remove(texture=bpy.data.textures[tex], )
                                purge_count += 1
                                
                    if {self.type == "Volume"}:
                        purge_count = 0
                        for v in range(len(bpy.data.volumes)-1,-1,-1):
                            if (bpy.data.volumes[v].users == 0):
                                bpy.data.volumes.remove(volume=bpy.data.volumes[v], )
                                purge_count += 1
                                
                    if {self.type == "Window Manager"}:
                        purge_count = 0
                        for wm in range(len(bpy.data.window_managers)-1,-1,-1):
                            if (bpy.data.window_managers[wm].users == 0):
                                bpy.data.window_managers.remove(window_manager=bpy.data.window_managers[wm], )
                                purge_count += 1
                                
                    if {self.type == "Workspace"}:
                        purge_count = 0
                        for ws in range(len(bpy.data.workspaces)-1,-1,-1):
                            if (bpy.data.workspaces[ws].users == 0):
                                bpy.data.workspaces.remove(workspace=bpy.data.workspaces[ws], )
                                purge_count += 1
                                
                    if {self.type == "World"}:
                        purge_count = 0
                        for w in range(len(bpy.data.worlds)-1,-1,-1):
                            if (bpy.data.worlds[w].users == 0):
                                bpy.data.worlds.remove(world=bpy.data.worlds[w], )
                                purge_count += 1

                    {self.indent(self.outputs[0].python_value, 5)}
        """
        self.outputs[1].python_value = f"purge_count"

    def draw_node(self, context, layout):
        layout.prop(self, "type", text="Type")
