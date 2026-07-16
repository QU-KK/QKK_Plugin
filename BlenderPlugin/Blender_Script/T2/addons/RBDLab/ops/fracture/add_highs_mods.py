import bpy
from datetime import datetime

from bpy.types import Operator
from ...Global.functions import (
    set_active_collection_to_master_coll,
    create_modifier,
    set_active_collection_by_name,
    hide_collection_in_viewport,
    unhide_collection_in_viewport,
    move_objects_to_collection,
    remove_collection_if_is_empty
)
from ...Global.basics import set_active_object, deselect_all_objects
from ...addon.naming import RBDLabNaming

boolean_mod_name = RBDLabNaming.BOOLEAN_MOD
boolean_mod_name_up = RBDLabNaming.BOOLEAN_MOD_UP


class SET_OT_inner_detail(Operator):
    bl_idname = "rbdlab.add_highs_mods"
    bl_label = "RBDLab Set inner detail"
    bl_description = "Add more manual-details to Fracture, then apply when desired"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.scene.rbdlab.filtered_target_collection is not None and context.scene.rbdlab.filtered_target_collection.name

    @classmethod
    def description(cls, context, _properties):
        if not context.scene.rbdlab.filtered_target_collection:
            return "You need to select a target collection"
        return cls.bl_description

    def execute(self, context):
        start = datetime.now()
        rbdlab = context.scene.rbdlab

        rbdlab.working_in_inner_details = True
        rbdlab.ui.show_fracture_details_extras = True

        # Restore ui defaults:
        rbdlab.remesh_mode = rbdlab.get_default_properties("remesh_mode")
        rbdlab.range_min = rbdlab.get_default_properties("range_min")
        rbdlab.range_max = rbdlab.get_default_properties("range_max")
        rbdlab.octree_depth = rbdlab.get_default_properties("octree_depth")
        rbdlab.remesh_scale = rbdlab.get_default_properties("remesh_scale")
        rbdlab.use_smooth_shade = rbdlab.get_default_properties("use_smooth_shade")
        rbdlab.external_roughness = rbdlab.get_default_properties("external_roughness")
        rbdlab.voxel_size = rbdlab.get_default_properties("voxel_size")
        rbdlab.remesh_voxel_adaptivity = rbdlab.get_default_properties("remesh_voxel_adaptivity")
        # restore ui visible:
        rbdlab.remesh_or_subdivision = rbdlab.get_default_properties("remesh_or_subdivision")
        rbdlab.inner_subdivision = rbdlab.get_default_properties("inner_subdivision")
        rbdlab.clouds_size = rbdlab.get_default_properties("clouds_size")
        rbdlab.displace_strength = rbdlab.get_default_properties("displace_strength")

        target_collections = rbdlab.filtered_target_collection[RBDLabNaming.LAST_CREATED_COLLS]
        if target_collections:
            for target_coll in target_collections:
                coll_name = target_coll.name

                target_coll[RBDLabNaming.USE_HIGHS] = True

                if RBDLabNaming.SUFIX_LOW in coll_name:
                    coll_high_name = coll_name.replace(RBDLabNaming.SUFIX_LOW, RBDLabNaming.SUFIX_HIGH)
                else:
                    coll_low_name = coll_name + RBDLabNaming.SUFIX_LOW
                    coll_high_name = coll_name + RBDLabNaming.SUFIX_HIGH

                    if coll_low_name not in bpy.data.collections:
                        bpy.data.collections[coll_name].name = coll_low_name
                    else:
                        move_objects_to_collection(context, bpy.data.collections[coll_name].objects, coll_low_name)
                        remove_collection_if_is_empty(context, coll_name)
                        rbdlab.filtered_target_collection = bpy.data.collections[coll_low_name]

                    coll_name = coll_low_name

                # Create collection if doesn't exist.
                if coll_high_name not in bpy.data.collections:
                    new_coll = bpy.data.collections.new(coll_high_name)

                    if not rbdlab.root_collection:
                        set_active_collection_to_master_coll(context)

                    rbdlab.root_collection.children.link(new_coll)
                    print("we create the collection:", coll_high_name)
                else:
                    unhide_collection_in_viewport(context, coll_high_name)
                    # rbdlab.low_or_high_visibility_viewport = "High"

                set_active_collection_by_name(context, coll_high_name)

                deselect_all_objects(context)

                chunks = bpy.data.collections[coll_name].objects
                if not chunks:
                    return {'CANCELLED'}

                chunk_prefix_name = chunks[0].name.split("_")[0]

                for chunk_low in chunks:
                    if "rbdlab_have_high" in chunk_low:
                        continue

                    if "rbdlab_modifiers_applied" in chunk_low:
                        continue

                    chunk_high = chunk_low.copy()
                    chunk_high.data = chunk_low.data.copy()
                    chunk_low["rbdlab_have_high"] = True

                    chunk_high[RBDLabNaming.STORED_LOW_CHUNK_RELATION] = chunk_low.name

                    chunk_high.name = "%s_high_%s" % (chunk_prefix_name, chunk_low.name.split("_")[-1])

                    if chunk_high.name not in bpy.data.collections[coll_high_name].objects:
                        context.collection.objects.link(chunk_high)
                    else:
                        # NOTE: Aunque sea remoto. Habrá que hacer algo si hay conflicto?
                        print("[FRACTURE] rbdlab.add_highs_mods : Chunk '%s' already in collection!" % chunk_high.name)

                    # # fast parent:
                    # chunk_high.parent = chunk_low
                    # # chunk_high.matrix_world = chunk_low.matrix_world.copy()
                    # chunk_high.matrix_parent_inverse = chunk_low.matrix_world.inverted()

                deselect_all_objects(context)

                coll_high_name_valid_objects = [
                    obj for obj in bpy.data.collections[coll_high_name].objects
                    if obj.type == 'MESH' and obj.visible_get() and "rbdlab_high"
                    not in obj and "rbdlab_modifiers_applied" not in obj]

                if coll_high_name_valid_objects:
                    first_chunk = coll_high_name_valid_objects[0]
                else:
                    print("no first chunk get!")
                    return {'CANCELLED'}

                set_active_object(context, first_chunk)

                # setear modifiers para la rugosidad
                if first_chunk:

                    decimate_name = RBDLabNaming.DECIMATE
                    modifier_type = 'DECIMATE'
                    position = 0
                    modifier = create_modifier(first_chunk, decimate_name, modifier_type, position)
                    modifier.decimate_type = 'DISSOLVE'

                    # weld_name = "RBDLab_Weld"
                    # modifier_type = 'WELD'
                    # position = 1
                    # modifier = create_modifier(first_chunk, weld_name, modifier_type, position)

                    # displace_name = "RBDLab_Dilate"
                    # modifier_type = 'DISPLACE'
                    # position = 1
                    # modifier = create_modifier(first_chunk, displace_name, modifier_type, position)
                    # modifier.strength = 0.0

                    subsurf_name = RBDLabNaming.SUBSURF_MOD
                    subsurf_level = 2
                    modifier_type = 'SUBSURF'
                    position = 1
                    modifier = create_modifier(first_chunk, subsurf_name, modifier_type, position)
                    modifier.levels = subsurf_level
                    modifier.render_levels = subsurf_level
                    modifier.subdivision_type = 'SIMPLE'

                    # Boolean up
                    modifier_type = 'BOOLEAN'
                    position = 2
                    modifier = create_modifier(first_chunk, boolean_mod_name_up, modifier_type, position)
                    modifier.operation = 'INTERSECT'
                    modifier.solver = rbdlab.rbdlab_cf_fast_exact
                    modifier.show_viewport = False
                    modifier.show_render = False

                    remesh_name = RBDLabNaming.REMESH
                    modifier_type = 'REMESH'
                    position = 3
                    modifier = create_modifier(first_chunk, remesh_name, modifier_type, position)
                    # modifier.mode = 'SHARP'
                    modifier.mode = 'VOXEL'
                    modifier.show_viewport = False
                    modifier.show_render = False
                    modifier.use_smooth_shade = True

                    triangulate_name = "RBDLab_Triangulate"
                    modifier_type = 'TRIANGULATE'
                    position = 4
                    modifier = create_modifier(first_chunk, triangulate_name, modifier_type, position)

                    # create the texture for displace
                    texture_displace_name = coll_high_name + "_Clouds"

                    if texture_displace_name not in bpy.data.textures:
                        bpy.ops.texture.new()
                        texture = bpy.data.textures[-1]
                        texture.type = 'CLOUDS'
                        texture.name = texture_displace_name
                        bpy.data.textures[texture_displace_name].cloud_type = 'COLOR'
                        bpy.data.textures[texture_displace_name].noise_depth = 5
                    else:
                        texture = bpy.data.textures[texture_displace_name]

                    displace_name = RBDLabNaming.DISPLACE
                    modifier_type = 'DISPLACE'
                    position = 5
                    modifier = create_modifier(first_chunk, displace_name, modifier_type, position)
                    modifier.direction = 'RGB_TO_XYZ'
                    modifier.texture = bpy.data.textures[texture_displace_name]
                    modifier.texture_coords = 'GLOBAL'
                    modifier.strength = 0.1

                    # Decimate Collapse
                    # decimate_collapse_name = "RBDLab_Decimate_collapse"
                    # modifier_type = 'DECIMATE'
                    # position = 6
                    # modifier = create_modifier(first_chunk, decimate_collapse_name, modifier_type, position)
                    # modifier.decimate_type = 'COLLAPSE'
                    # rbdlab.ratio = 0.5
                    # modifier.ratio = 0.5

                    laplaciansmooth_name = RBDLabNaming.LAPLACIAN_MOD
                    modifier_type = 'LAPLACIANSMOOTH'
                    position = 7
                    modifier = create_modifier(first_chunk, laplaciansmooth_name, modifier_type, position)
                    modifier.show_viewport = False
                    modifier.show_render = False

                    # en multi objeto habia booleans sin su correspondiente nombre
                    # [setattr(m, "name", boolean_mod_name) for m in first_chunk.modifiers if m.type == 'BOOLEAN' and "RBDLab" not in m.name]

                    # bajamos el boolean modifier:
                    # cuando se usa un cancel puede no haber boolean
                    for mod in first_chunk.modifiers:
                        if mod.type == 'BOOLEAN' and RBDLabNaming.FROM in first_chunk:
                            mod.object = bpy.data.objects[first_chunk[RBDLabNaming.FROM]]

                    if len(first_chunk.modifiers) > 0 and boolean_mod_name in first_chunk.modifiers:
                        current_index_mod1 = first_chunk.modifiers.find(boolean_mod_name)
                        first_chunk.modifiers.move(current_index_mod1, len(first_chunk.modifiers)-1)
                        # bpy.ops.object.modifier_move_to_index(modifier=boolean_mod_name, index=len(first_chunk.modifiers)-1)

                    # fix movemos el decimate arriba
                    current_index_mod2 = first_chunk.modifiers.find(decimate_name)
                    first_chunk.modifiers.move(current_index_mod2, 0)
                    # bpy.ops.object.modifier_move_to_index(modifier=decimate_name, index=0)

                    # deselect_all_objects(context)

                    # seleccionamos todos los high
                    for obj in coll_high_name_valid_objects:
                        obj.select_set(True)

                    # copiamos los modifiers:
                    bpy.ops.object.make_links_data(type='MODIFIERS')

                    # les agrego la propiedad "rbdlab_high" para saber que ya fueros agregados los high a estos chunks
                    # y no volver a agregarles highs nuevamente cuando usamos single output collection
                    for obj in coll_high_name_valid_objects:
                        obj["rbdlab_high"] = True
                        # for mod in obj.modifiers:
                        #     obj[mod.name + "_hash_id"] = str(hash(mod))

                    # restautamos los bolean a sus correspondientes from:
                    boolena_objects = [obj for obj in coll_high_name_valid_objects
                                       if boolean_mod_name in obj.modifiers and RBDLabNaming.FROM in obj]
                    if boolena_objects:
                        [(setattr(obj.modifiers[boolean_mod_name], "object", bpy.data.objects[obj[RBDLabNaming.FROM]]), setattr(
                            obj.modifiers[boolean_mod_name_up], "object", bpy.data.objects[obj[RBDLabNaming.FROM]])) for obj in boolena_objects]
                else:
                    return {'CANCELLED'}

                # bump al segundo slot de material, ahora al ultimo slot:
                processed_materials = []
                for chunk in coll_high_name_valid_objects:

                    total_mats = len(chunk.material_slots)
                    if total_mats > 0:
                        
                        slot_index = total_mats-1
                        name_mat = chunk.material_slots[slot_index].name

                        if name_mat in processed_materials:
                            continue

                        if name_mat.endswith(RBDLabNaming.SUFIX_INNER_MAT):
                            # first_chunk.active_material_index = 1
                            chunk.active_material_index = slot_index
                            node_tree = chunk.active_material.node_tree

                            principled_node = node_tree.nodes[RBDLabNaming.PRINCIPLED]

                            bump_node = node_tree.nodes.new("ShaderNodeBump")
                            bump_node.location = (-250, -160)

                            noise_node = node_tree.nodes.new("ShaderNodeTexNoise")
                            noise_node.location = (-450, -160)
                            noise_node.inputs["Scale"].default_value = 4
                            noise_node.inputs["Detail"].default_value = 8

                            text_coordinate_node = node_tree.nodes.new("ShaderNodeTexCoord")
                            text_coordinate_node.location = (-650, -160)

                            # conexiones
                            node_tree.links.new(
                                bump_node.outputs["Normal"],
                                principled_node.inputs["Normal"]
                            )
                            node_tree.links.new(
                                noise_node.outputs["Fac"],
                                bump_node.inputs["Height"]
                            )
                            node_tree.links.new(
                                text_coordinate_node.outputs["Object"],
                                noise_node.inputs["Vector"]
                            )
                            processed_materials.append(name_mat)
                    
                    else:
                        print(chunk.name, "Without material_slots!!")

                hide_collection_in_viewport(context, coll_name)
                deselect_all_objects(context)

        rbdlab.remove_loose_verts = rbdlab.get_default_properties("remove_loose_verts")
        rbdlab.filtered_target_collection["fracture_applied"] = 0
        print("End add highs mods: " + str(datetime.now() - start))
        return {'FINISHED'}
