import bpy
import os
from bpy.types import Operator
from ...addon.naming import RBDLabNaming
from ...addon.paths import RBDLabPreferences


class RBDLAB_OT_assign_materials(Operator):
    bl_idname = "rbdlab.assign_materials"
    bl_label = "Assign Material"
    bl_description = "Assign Material"
    bl_options = {'REGISTER', 'UNDO'}

    @staticmethod
    def add_material(self, context, rbdlab, filename_without_extension, target_mat_per_obj):

        addon_preferences = RBDLabPreferences.get_prefs(context)
        materials_path = addon_preferences.materials_path

        if not materials_path:
            materials_path = "/home/zebus3d/github/PolyHeavenDownloader/2k/selection/"

        category = rbdlab.thumbnails.categories
        final_path = os.path.join(materials_path, category.lower(), filename_without_extension)

        diff_file = None
        ao_file = None
        rough = None
        nomral_map = None
        disp_file = None

        diff_image_node = None
        ao_image_node = None
        rough_image_node = None
        normal_image_node = None
        disp_image_node = None

        for filename in os.scandir(final_path):
            if filename.is_file():

                # get diffuse file:
                if "_diff_" in filename.path or "_diffuse_" in filename.path or "_col_" in filename.path or "_col1_" in filename.path or "_albedo_" in filename.path:
                    diff_file = filename.path

                # get ao file:
                if "_ao_" in filename.path:
                    ao_file = filename.path

                # get roughness file:
                if "_rough_" in filename.path:
                    rough_file = filename.path

                # normal map
                if "_nor_gl" in filename.path:
                    normal_map = filename.path

                # displace
                if "_disp_" in filename.path:
                    disp_file = filename.path

        if target_mat_per_obj:

            if target_mat_per_obj not in bpy.data.materials:
                mat = bpy.data.materials.new(name=target_mat_per_obj)
                mat.use_nodes = True
            else:
                mat = bpy.data.materials[target_mat_per_obj]

            # setup material pbr:
            all_nodes_created = []
            node_tree = mat.node_tree
            Principled = node_tree.nodes[RBDLabNaming.PRINCIPLED]
            all_nodes_created.append(Principled)
            Material_Output = node_tree.nodes["Material Output"]
            all_nodes_created.append(Material_Output)

            # diff #####################################################################################
            if diff_file:
                diff_image = bpy.data.images.load(diff_file, check_existing=True)

                # Add a diffuse shader and set its location:
                diff_image_node = node_tree.nodes.new("ShaderNodeTexImage")
                all_nodes_created.append(diff_image_node)
                x = -637
                y = 500
                diff_image_node.location = (x, y)
                diff_image_node.image = diff_image

                hue_diff_node = node_tree.nodes.new("ShaderNodeHueSaturation")
                all_nodes_created.append(hue_diff_node)
                x = -366
                y = 360
                hue_diff_node.location = (x, y)

            # end diff #################################################################################

                # ao #######################################################################################
                if ao_file:
                    ao_image = bpy.data.images.load(ao_file, check_existing=True)

                    # Add a diffuse shader and set its location:
                    ao_image_node = node_tree.nodes.new("ShaderNodeTexImage")
                    all_nodes_created.append(ao_image_node)
                    ao_image.colorspace_settings.name = "Non-Color"
                    x = -637
                    y = 200
                    ao_image_node.location = (x, y)
                    ao_image_node.image = ao_image

                    mixrgb_node = node_tree.nodes.new("ShaderNodeMixRGB")
                    all_nodes_created.append(mixrgb_node)
                    x = -185
                    y = 322
                    mixrgb_node.location = (x, y)
                    mixrgb_node.blend_type = 'MULTIPLY'
                    mixrgb_node.inputs[0].default_value = 1

                    node_tree.links.new(Principled.inputs["Base Color"], mixrgb_node.outputs["Color"])
                    node_tree.links.new(mixrgb_node.inputs["Color1"], hue_diff_node.outputs["Color"])
                    node_tree.links.new(hue_diff_node.inputs["Color"], diff_image_node.outputs["Color"])
                    node_tree.links.new(mixrgb_node.inputs["Color2"], ao_image_node.outputs["Color"])
                else:
                    node_tree.links.new(Principled.inputs["Base Color"], hue_diff_node.outputs["Color"])
                    node_tree.links.new(hue_diff_node.inputs["Color"], diff_image_node.outputs["Color"])
                # end ao ###################################################################################

            # rough #######################################################################################
            if rough_file:
                rough_image = bpy.data.images.load(rough_file, check_existing=True)

                # Add a diffuse shader and set its location:
                rough_image_node = node_tree.nodes.new("ShaderNodeTexImage")
                all_nodes_created.append(rough_image_node)
                rough_image.colorspace_settings.name = "Non-Color"
                x = -637
                y = -100
                rough_image_node.location = (x, y)
                rough_image_node.image = rough_image

                polished_node = node_tree.nodes.new("ShaderNodeMath")
                all_nodes_created.append(polished_node)
                polished_node.use_clamp = True
                polished_node.operation = 'SUBTRACT'
                polished_node.inputs[1].default_value = 0
                x = -185
                y = -20
                polished_node.location = (x, y)

                node_tree.links.new(Principled.inputs["Roughness"], polished_node.outputs["Value"])
                node_tree.links.new(polished_node.inputs[0], rough_image_node.outputs["Color"])
            # end rough ###################################################################################

            # normal map ##################################################################################
            if normal_map:
                normal_image = bpy.data.images.load(normal_map, check_existing=True)

                # Add a diffuse shader and set its location:
                normal_image_node = node_tree.nodes.new("ShaderNodeTexImage")
                all_nodes_created.append(normal_image_node)
                normal_image.colorspace_settings.name = "Non-Color"
                x = -637
                y = -400
                normal_image_node.location = (x, y)
                normal_image_node.image = normal_image

                nmap_node = node_tree.nodes.new("ShaderNodeNormalMap")
                all_nodes_created.append(nmap_node)
                x = -185
                y = -299
                nmap_node.location = (x, y)

                node_tree.links.new(Principled.inputs["Normal"], nmap_node.outputs["Normal"])
                node_tree.links.new(nmap_node.inputs["Color"], normal_image_node.outputs["Color"])
            # end normal map ##############################################################################

            # displace map ################################################################################
            if disp_file:
                disp_image = bpy.data.images.load(disp_file, check_existing=True)

                # Add a diffuse shader and set its location:
                disp_image_node = node_tree.nodes.new("ShaderNodeTexImage")
                all_nodes_created.append(disp_image_node)
                disp_image.colorspace_settings.name = "Non-Color"
                x = -637
                y = -700
                disp_image_node.location = (x, y)
                disp_image_node.image = disp_image

                disp_node = node_tree.nodes.new("ShaderNodeDisplacement")
                all_nodes_created.append(disp_node)
                x = 110
                y = -380
                disp_node.location = (x, y)
                disp_node.mute = True

                node_tree.links.new(Material_Output.inputs["Displacement"], disp_node.outputs["Displacement"])
                node_tree.links.new(disp_node.inputs["Height"], disp_image_node.outputs["Color"])

            # end displace map ############################################################################

            # Vector Mapping
            vector_mapping_node = node_tree.nodes.new("ShaderNodeMapping")
            all_nodes_created.append(vector_mapping_node)
            x = -927
            y = -28
            vector_mapping_node.location = (x, y)
            # end Vector Mapping

            # Texture Coordinates
            text_coord_node = node_tree.nodes.new("ShaderNodeTexCoord")
            all_nodes_created.append(text_coord_node)
            x = -1157
            y = -38
            text_coord_node.location = (x, y)

            if diff_image_node:
                node_tree.links.new(vector_mapping_node.outputs["Vector"], diff_image_node.inputs["Vector"])

            if ao_image_node:
                node_tree.links.new(vector_mapping_node.outputs["Vector"], ao_image_node.inputs["Vector"])

            if rough_image_node:
                node_tree.links.new(vector_mapping_node.outputs["Vector"], rough_image_node.inputs["Vector"])

            if normal_image_node:
                node_tree.links.new(vector_mapping_node.outputs["Vector"], normal_image_node.inputs["Vector"])

            if disp_image_node:
                node_tree.links.new(vector_mapping_node.outputs["Vector"], disp_image_node.inputs["Vector"])

            node_tree.links.new(vector_mapping_node.inputs["Vector"], text_coord_node.outputs['UV'])
            # End Texture Coordinates

            # deselect all nodes created:
            for node in all_nodes_created:
                node.select = False

            return mat

    @staticmethod
    def get_high_collection_by_name(coll_name):
        if RBDLabNaming.SUFIX_LOW in coll_name:
            coll_high_name = coll_name.replace(RBDLabNaming.SUFIX_LOW, RBDLabNaming.SUFIX_HIGH)
        else:
            coll_high_name = coll_name + RBDLabNaming.SUFIX_HIGH

        if coll_high_name in bpy.data.collections:
            return bpy.data.collections[coll_high_name]
        else:
            return None

    def check_condition(self, context, mat):
        rbdlab = context.scene.rbdlab

        if rbdlab.thumbnails.inner_or_outer == 'OUTER':
            return RBDLabNaming.INNER_MAT_TAG not in mat

        elif rbdlab.thumbnails.inner_or_outer == 'INNER':
            return RBDLabNaming.INNER_MAT_TAG in mat

    def execute(self, context):
        scn = context.scene
        rbdlab = scn.rbdlab

        current_mode = rbdlab.low_or_high_visibility_viewport

        # without file extension:
        filename = os.path.basename(rbdlab.thumbnails.active)
        filename_without_extension = os.path.splitext(filename)[0]

        coll_high_name = None
        valid_objects = None

        if rbdlab.thumbnails.by_selection == 'SELECTION':
            valid_objects = [obj for obj in context.selected_objects if obj.type == 'MESH']
            if not valid_objects:
                self.report({'WARNING'}, "Not valid objects in selection!")
                return {'CANCELLED'}

            # incluimos los high por seleccion:
            all_rbdlab_froms_to_work = [obj[RBDLabNaming.FROM] for obj in valid_objects if RBDLabNaming.FROM in obj]
            for rbdlab_from in all_rbdlab_froms_to_work:
                for ob in bpy.data.objects:

                    if RBDLabNaming.FROM not in ob:
                        continue

                    if ob[RBDLabNaming.FROM] != rbdlab_from:
                        continue

                    if ob.parent:
                        if ob.parent.type == 'MESH':
                            if ob.parent.select_get() or ob.select_get():
                                if ob not in valid_objects:
                                    valid_objects.append(ob)
                                if ob.parent not in valid_objects:
                                    valid_objects.append(ob.parent)
                    else:
                        if ob.select_get():
                            if ob not in valid_objects:
                                valid_objects.append(ob)

        else:

            collections = rbdlab.materials.get_selected_work_group_collections()

            if not collections:
                self.report({'WARNING'}, "Not valid Collections to work!")
                return {'CANCELLED'}

            valid_objects = []
            for coll in collections:

                low_objects = coll.objects
                {valid_objects.append(obj) for obj in low_objects if obj.type == 'MESH'}

                coll_high_name = self.get_high_collection_by_name(coll.name)

                if coll_high_name:
                    for obj in coll_high_name.objects:
                        if obj.type != 'MESH':
                            continue
                        valid_objects.append(obj)

        if valid_objects:

            for obj in valid_objects:

                if len(obj.material_slots) == 0 and rbdlab.thumbnails.inner_or_outer == 'OUTER':
                    if RBDLabNaming.TMP_MAT_NAME not in bpy.data.materials:
                        tmp_mat = bpy.data.materials.new(name=RBDLabNaming.TMP_MAT_NAME)
                    else:
                        tmp_mat = bpy.data.materials[RBDLabNaming.TMP_MAT_NAME]

                    obj.data.materials.append(tmp_mat)

                for i, mat_slot in enumerate(obj.material_slots):

                    new_mat = None

                    # con esta condicion decidimos si va a aplicarse a inner o outers:
                    if self.check_condition(context, mat_slot.material):

                        if rbdlab.thumbnails.inner_or_outer == 'INNER':
                            sufix = RBDLabNaming.SUFIX_INNER_MAT
                        else:
                            sufix = RBDLabNaming.SUFIX_OUTER_MAT

                        if RBDLabNaming.FROM in obj:
                            target_mat_per_obj = obj[RBDLabNaming.FROM] + "_" + filename_without_extension.title() + sufix
                        else:
                            target_mat_per_obj = obj.name + "_" + filename_without_extension.title() + sufix

                        if target_mat_per_obj not in bpy.data.materials:
                            new_mat = self.add_material(
                                self,
                                context,
                                rbdlab,
                                filename_without_extension,
                                target_mat_per_obj
                            )
                        else:
                            new_mat = bpy.data.materials[target_mat_per_obj]

                        if new_mat:

                            obj.active_material_index = i
                            mat_slot.material = new_mat

                            if rbdlab.thumbnails.inner_or_outer == 'INNER':
                                new_mat[RBDLabNaming.INNER_MAT_TAG] = True

            if RBDLabNaming.TMP_MAT_NAME in bpy.data.materials:
                tmp_mat = bpy.data.materials[RBDLabNaming.TMP_MAT_NAME]
                bpy.data.materials.remove(tmp_mat)

            # restore el mode en el que estuviera el usuario
            if rbdlab.low_or_high_visibility_viewport != current_mode:
                rbdlab.low_or_high_visibility_viewport = current_mode

        else:
            self.report({'WARNING'}, "You did not select a valid object!")

        return {'FINISHED'}


class RBDLAB_OT_set_current_material_to_rbdlab_inner_mat(Operator):
    bl_idname = "rbdlab.set_current_material_to_rbdlab_inner_mat"
    bl_label = "Set Current Material to Inner Mat"
    bl_description = "Set Current Material to RBDLab Inner Mat"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):

        obj = context.object
        if obj.type == 'MESH':
            current_mat = obj.active_material
            current_mat_name = current_mat.name

            for mat in obj.material_slots:

                if mat.name == current_mat_name:
                    if RBDLabNaming.INNER_MAT_TAG not in mat.material:
                        mat.material[RBDLabNaming.INNER_MAT_TAG] = True

                if RBDLabNaming.INNER_MAT_TAG in mat.material and mat.name != current_mat_name:
                    del mat.material[RBDLabNaming.INNER_MAT_TAG]

            self.report({'INFO'}, current_mat_name + " as set to RBDLab Inner Mat Now!")

            return {'FINISHED'}
        else:
            return {'CANCELLED'}
