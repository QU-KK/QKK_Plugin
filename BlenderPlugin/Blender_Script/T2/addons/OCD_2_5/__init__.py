#Copyright (C) 2025 vfxguide
#realvfxguide@gmail.com

#Created by VFXGuide
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.

#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.

#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.

import bpy
import os
import random
from mathutils import Vector
from bpy.types import Operator, Panel, PropertyGroup, Menu
from bpy.props import (
    IntProperty,
    FloatProperty, 
    PointerProperty, 
    BoolProperty, 
    EnumProperty, 
    StringProperty
)
from bpy.utils import register_class, unregister_class

if bpy.app.version < (4, 5, 0):
    raise Exception("This addon requires Blender 4.5 or later")

def get_addon_path():
    script_file = os.path.realpath(__file__)
    directory = os.path.dirname(script_file)
    return directory

def get_blend_file_path(filename):
    addon_path = get_addon_path()
    blend_filepath = os.path.join(addon_path, filename)
    return blend_filepath

def get_ocd_modifier_properties(mod):
    """Return a dictionary of relevant properties for an OCD_L modifier."""
    return {
        "Socket_9": mod["Socket_9"],               # String
        "Socket_5": mod["Socket_5"],               # Float
        "Socket_2": mod["Socket_2"],               # Float
        "Socket_6": mod["Socket_6"],               # Float
        "Socket_7": mod["Socket_7"],               # Float
        "Socket_3": mod["Socket_3"],               # Boolean
        "Socket_8": mod["Socket_8"],               # Object
        "Socket_16": mod["Socket_16"],             # Material
        "Socket_14": mod["Socket_14"],             # Boolean
        "Socket_18": mod["Socket_18"],             # Boolean
        "Socket_20": mod["Socket_20"],             # Float
        "Socket_21": mod["Socket_21"],             # Boolean
        "Socket_11": mod["Socket_11"],             # Array ([0], [1], [2])
        "Socket_12": mod["Socket_12"],             # Array ([0], [1], [2])
        "Socket_13": mod["Socket_13"]              # Array ([0], [1], [2])
    }


# Global variable to store removed modifier information
global_removed_modifier_info = {}

class OBJECT_OT_ocd(bpy.types.Operator):
    bl_idname = "object.ocd"
    bl_label = "OCD GN"
    bl_description = "Activate OCD Mode"
    bl_options = {'UNDO'}

    def load_node_group(self, blend_file_path):
        """ Load the node group from the specified blend file. """
        with bpy.data.libraries.load(blend_file_path) as (data_from, data_to):
            if "OCD_GN_2.5.0" in data_from.node_groups:
                data_to.node_groups = ["OCD_GN_2.5.0"]
            else:
                return None
        return bpy.data.node_groups.get("OCD_GN_2.5.0", None)

    def get_unique_modifier_name(self, obj, base_name, counter=1):
        """ Generate a unique modifier name for the given object. """
        unique_name = f"{base_name}{str(counter).zfill(2)}"
        while obj.modifiers.get(unique_name) is not None:
            counter += 1
            unique_name = f"{base_name}{str(counter).zfill(2)}"
        return unique_name

    def invoke(self, context, event):
        addon_path = os.path.dirname(os.path.realpath(__file__))
        blend_file_path = os.path.join(addon_path, 'data.blend')

        # Check if the node group "OCD_GN" is already in the scene
        node_group = bpy.data.node_groups.get("OCD_GN_2.5.0", None)

        # If the node group is not found, try loading it from the file
        if not node_group:
            if not os.path.isfile(blend_file_path):
                self.report({'ERROR'}, "data.blend file not found")
                return {'CANCELLED'}
            try:
                node_group = self.load_node_group(blend_file_path)
                if not node_group:
                    self.report({'ERROR'}, "Node group 'OCD_GN' not found or failed to load.")
                    return {'CANCELLED'}
            except Exception as e:
                self.report({'ERROR'}, str(e))
                return {'CANCELLED'}

        # Process each selected object
        for obj in context.selected_objects:
            if obj.type == 'MESH':
                # Start with OCD_L01 for each object
                mod_counter = 1
                
                # Generate a unique modifier name for the current object
                mod_name = self.get_unique_modifier_name(obj, "OCD_L", mod_counter)
                mod = obj.modifiers.new(name=mod_name, type='NODES')
                mod.node_group = node_group
                
                # Set the modifier to not show in edit mode
                mod.show_in_editmode = False
                mod.show_group_selector = False
                
                # Set a random integer for Socket_22
                random_value = random.randint(0, 100)
                mod["Socket_22"] = random_value

        # Switch to the Modifiers tab in the Properties panel
        for area in context.screen.areas:
            if area.type == 'PROPERTIES':
                for space in area.spaces:
                    if space.type == 'PROPERTIES':
                        space.context = 'MODIFIER'
                        break

        return {'FINISHED'}


class OBJECT_OT_copy_ocd_modifiers(bpy.types.Operator):
    bl_idname = "object.copy_ocd_modifiers"
    bl_label = "Copy OCD Modifiers"
    bl_description = "Copy OCD from the active object to selected object(s)."
    bl_options = {'UNDO'}

    def copy_ocd_modifiers_to_selected(self):
        # Get the active object
        active_obj = bpy.context.view_layer.objects.active
        
        # Get the list of selected objects excluding the active one, filtering by type and checking for existing OCD_L modifiers
        selected_objects = [
            obj for obj in bpy.context.selected_objects 
            if obj != active_obj and obj.type == 'MESH' and not any(mod.name.startswith("OCD_L") for mod in obj.modifiers)
        ]
        
        if not active_obj:
            self.report({'WARNING'}, "No active object found.")
            return

        # Loop through the modifiers of the active object
        for mod in active_obj.modifiers:
            if mod.type == 'NODES' and mod.name.startswith("OCD_L"):
                # Get the relevant properties using the new function
                properties = get_ocd_modifier_properties(mod)
                
                # Copy the properties to each target object
                for target_obj in selected_objects:
                    # Add a new Geometry Nodes modifier to the target object
                    new_mod = target_obj.modifiers.new(name=mod.name, type='NODES')
                    
                    # Copy the node group from the active object's modifier
                    new_mod.node_group = mod.node_group
                    
                    # Apply the stored properties to the new modifier
                    for prop, value in properties.items():
                        try:
                            new_mod[prop] = value
                        except KeyError:
                            self.report({'INFO'}, f"Property {prop} not found on the new modifier.")
                    
                    # Set a random integer for Socket_22
                    random_value = random.randint(0, 100)
                    new_mod["Socket_22"] = random_value
                    new_mod.show_group_selector = False
                    new_mod.show_in_editmode = False

    def execute(self, context):
        self.copy_ocd_modifiers_to_selected()
        return {'FINISHED'}


class OBJECT_OT_copy_from_active(bpy.types.Operator):
    bl_idname = "object.copy_from_active"
    bl_label = "Copy from Active"
    bl_description = "Sync OCD from the active object to selected objects."
    bl_options = {'UNDO'}

    def copy_modifier_properties(self):
        # Get the active object
        active_obj = bpy.context.view_layer.objects.active
        
        # Get the list of selected objects excluding the active one
        selected_objects = [
            obj for obj in bpy.context.selected_objects 
            if obj != active_obj and obj.type == 'MESH'
        ]
        
        if not active_obj:
            self.report({'WARNING'}, "No active object found.")
            return

        # Get the order and types of all modifiers on the active object
        active_modifiers = [(mod.name, mod.type) for mod in active_obj.modifiers]

        # Loop through selected objects
        for target_obj in selected_objects:
            # Store the original Socket_22 values for each existing OCD_L modifier
            original_socket_22 = {}
            for mod in target_obj.modifiers:
                if mod.name.startswith("OCD_L"):
                    original_socket_22[mod.name] = mod.get("Socket_22", 0)

            # Remove all existing OCD_L modifiers from the target object
            ocd_l_modifiers = [mod for mod in target_obj.modifiers if mod.name.startswith("OCD_L")]
            for mod in ocd_l_modifiers:
                target_obj.modifiers.remove(mod)

            # Re-add all modifiers (both OCD_L and non-OCD_L) in the correct order
            for mod_name, mod_type in active_modifiers:
                if mod_type == 'NODES' and mod_name.startswith("OCD_L"):
                    # Add a new OCD_L Geometry Nodes modifier to the target object
                    new_mod = target_obj.modifiers.new(name=mod_name, type='NODES')
                    active_mod = active_obj.modifiers.get(mod_name)
                    new_mod.node_group = active_mod.node_group
                    new_mod.show_group_selector = False
                    new_mod.show_in_editmode = False

                    # Get the relevant properties using the new function
                    properties = get_ocd_modifier_properties(active_mod)
                    
                    # Apply the stored properties to the new modifier
                    for prop, value in properties.items():
                        try:
                            new_mod[prop] = value
                        except KeyError:
                            self.report({'INFO'}, f"Property {prop} not found on the modifier in {target_obj.name}.")
                    
                    # For existing modifiers, restore the original Socket_22 value
                    if mod_name in original_socket_22:
                        new_mod["Socket_22"] = original_socket_22[mod_name]
                    else:
                        # For newly added modifiers, assign a random value to Socket_22
                        random_value = random.randint(0, 100)
                        new_mod["Socket_22"] = random_value
                    
                    # Force update by toggling the modifier visibility
                    new_mod.show_viewport = not new_mod.show_viewport
                    new_mod.show_viewport = not new_mod.show_viewport
                else:
                    # Reorder non-OCD_L modifiers to maintain their position
                    if mod_name not in [mod.name for mod in target_obj.modifiers]:
                        # Add the non-OCD_L modifier if it does not already exist
                        new_mod = target_obj.modifiers.new(name=mod_name, type=mod_type)
                    else:
                        new_mod = target_obj.modifiers.get(mod_name)
                    
                    # Move the modifier to the correct position
                    target_obj.modifiers.move(target_obj.modifiers.find(new_mod.name), len(target_obj.modifiers) - 1)

    def execute(self, context):
        self.copy_modifier_properties()
        return {'FINISHED'}


class OBJECT_OT_apply_ocd_modifiers(bpy.types.Operator):
    bl_idname = "object.apply_ocd_modifiers"
    bl_label = "Apply OCD Modifiers"
    bl_description = "Apply OCD Modifiers."
    bl_options = {'UNDO'}

    def apply_ocd_modifiers_to_selected(self):
        # Get the list of selected objects
        selected_objects = bpy.context.selected_objects

        for obj in selected_objects:
            if obj.type == 'MESH':
                # Loop through all modifiers and apply those with "OCD_" in their names
                for mod in obj.modifiers:
                    if mod.type == 'NODES' and mod.name.startswith("OCD_L"):
                        bpy.context.view_layer.objects.active = obj  # Set the object as active
                        bpy.ops.object.modifier_apply(modifier=mod.name)

    def execute(self, context):
        self.apply_ocd_modifiers_to_selected()
        return {'FINISHED'}

class OBJECT_OT_remove_ocd_modifiers(bpy.types.Operator):
    bl_idname = "object.remove_ocd_modifiers"
    bl_label = "Remove OCD Modifiers"
    bl_description = "Remove OCD Modifiers."
    bl_options = {'UNDO'}

    def remove_ocd_modifiers_from_selected(self):
        # Get the list of selected objects
        selected_objects = bpy.context.selected_objects

        for obj in selected_objects:
            if obj.type == 'MESH':
                # Remove all Geometry Nodes modifiers with "OCD_" in their names
                for mod in obj.modifiers:
                    if mod.type == 'NODES' and mod.name.startswith("OCD_L"):
                        obj.modifiers.remove(mod)

    def execute(self, context):
        self.remove_ocd_modifiers_from_selected()
        return {'FINISHED'}

class OBJECT_OT_randomize_ocd(bpy.types.Operator):
    bl_idname = "object.randomize_ocd"
    bl_label = "Randomize OCD"
    bl_description = "Randomize the OCD noise position."
    bl_options = {'UNDO'}

    def randomize_ocd(self):
        # Get the list of selected objects
        selected_objects = bpy.context.selected_objects

        for obj in selected_objects:
            if obj.type == 'MESH':
                # Loop through all modifiers to find OCD_L Geometry Nodes modifiers
                for mod in obj.modifiers:
                    if mod.type == 'NODES' and mod.name.startswith("OCD_L"):
                        # Set a random integer for Socket_22
                        random_value = random.randint(0, 100)
                        try:
                            mod["Socket_22"] = random_value
                            # Force update by toggling the modifier visibility
                            mod.show_viewport = not mod.show_viewport
                            mod.show_viewport = not mod.show_viewport
                        except KeyError:
                            pass  # Ignore if seed is not present

    def execute(self, context):
        self.randomize_ocd()
        return {'FINISHED'}

class OBJECT_OT_ocd_bake(bpy.types.Operator):
    bl_idname = "object.ocd_bake"
    bl_label = "Activate Bake"
    bl_description = "Activate Bake."
    bl_options = {'UNDO'}

    def execute(self, context):
        # Check if the blend file has been saved
        if not bpy.data.is_saved:
            self.report({'WARNING'}, "Please save your file before starting the bake.")
            return {'CANCELLED'}

        selected_objects = context.selected_objects

        for obj in selected_objects:
            if obj.type == 'MESH':
                for mod in obj.modifiers:
                    if mod.type == 'NODES' and mod.name.startswith("OCD_L"):
                        # Iterate over the bakes in the modifier
                        for bake in mod.bakes:
                            try:
                                # Obtain session_uid, node, and bake_id for the bake operation
                                session_uid = bake.id_data.session_uid
                                bake_id = bake.bake_id

                                # Use the modifier name (mod.name) in the bake operation
                                modifier_name = mod.name

                                # Trigger the bake operation
                                bpy.ops.object.geometry_node_bake_single(
                                    session_uid=session_uid,
                                    modifier_name=modifier_name,
                                    bake_id=bake_id
                                )
                                # Set a custom property to indicate the object has been baked
                                obj["is_baked"] = True
                            except Exception as e:
                                self.report({'ERROR'}, f"Failed to activate bake: {str(e)}")
                                return {'CANCELLED'}

        return {'FINISHED'}

class OBJECT_OT_delete_bake(bpy.types.Operator):
    bl_idname = "object.delete_bake"
    bl_label = "Delete Bake"
    bl_description = "Delete Bake."
    bl_options = {'UNDO'}

    def execute(self, context):
        selected_objects = context.selected_objects

        for obj in selected_objects:
            if obj.type == 'MESH':
                for mod in obj.modifiers:
                    if mod.type == 'NODES' and mod.name.startswith("OCD_L"):
                        # Iterate over the bakes in the modifier
                        for bake in mod.bakes:
                            try:
                                # Obtain session_uid and bake_id for the delete operation
                                session_uid = bake.id_data.session_uid
                                bake_id = bake.bake_id

                                # Use the modifier name (mod.name) in the delete operation
                                modifier_name = mod.name

                                # Trigger the bake delete operation
                                bpy.ops.object.geometry_node_bake_delete_single(
                                    session_uid=session_uid,
                                    modifier_name=modifier_name,
                                    bake_id=bake_id
                                )
                                # Remove the custom property indicating the object was baked
                                if "is_baked" in obj:
                                    del obj["is_baked"]
                            except Exception as e:
                                self.report({'ERROR'}, f"Failed to delete bake: {str(e)}")
                                return {'CANCELLED'}

        return {'FINISHED'}

class OBJECT_OT_turn_off_ocd(bpy.types.Operator):
    bl_idname = "object.turn_off_ocd"
    bl_label = "Turn Off OCD Modifiers"
    bl_description = "Turn off OCD for selected objects."
    bl_options = {'UNDO'}

    def execute(self, context):
        for obj in context.selected_objects:
            if obj.type == 'MESH':
                for mod in obj.modifiers:
                    if mod.name.startswith("OCD_L"):
                        mod.show_viewport = False
        return {'FINISHED'}

class OBJECT_OT_turn_on_ocd(bpy.types.Operator):
    bl_idname = "object.turn_on_ocd"
    bl_label = "Turn On OCD Modifiers"
    bl_description = "Turn on OCD for selected objects."
    bl_options = {'UNDO'}

    def execute(self, context):
        for obj in context.selected_objects:
            if obj.type == 'MESH':
                for mod in obj.modifiers:
                    if mod.name.startswith("OCD_L"):
                        mod.show_viewport = True
        return {'FINISHED'}


class OBJECT_OT_add_mask(bpy.types.Operator):
    bl_idname = "object.add_mask"
    bl_label = "Add Mask"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obj = context.active_object
        if obj:
            base_name = "OCD_Mask"
            idx = 1
            texture_name = f"{base_name}.{idx:02d}_{obj.name}"
            
            # Find a unique name for the image
            while texture_name in bpy.data.images:
                idx += 1
                texture_name = f"{base_name}.{idx:02d}_{obj.name}"
            
            # Create a new image
            new_image = bpy.data.images.new(name=texture_name, width=1024, height=1024, alpha=True)
            
            # Set the image to black
            new_image.generated_color = (0, 0, 0, 1)
            
            # Pack the image to make sure it's fully initialized
            #new_image.pack()

            # Retrieve the newly packed image from bpy.data
            packed_image = bpy.data.images[texture_name]

            # Switch to Material Preview mode
            for area in context.screen.areas:
                if area.type == 'VIEW_3D':
                    for space in area.spaces:
                        if space.type == 'VIEW_3D':
                            space.shading.type = 'MATERIAL'
                            break

            # Assign the new image to Socket_26 of the Geometry Nodes modifier starting with 'OCD_L'
            for modifier in obj.modifiers:
                if modifier.type == 'NODES' and modifier.name.startswith("OCD_L"):
                    modifier["Socket_23"] = True
                    modifier["Socket_24"] = True
                    #modifier["Socket_26"] = packed_image
                    modifier.node_group.update_tag()

            # Turn on Texture Paint mode
            bpy.ops.paint.texture_paint_toggle()
            
            # Set image paint mode to 'IMAGE' and select the created image
            context.scene.tool_settings.image_paint.mode = 'IMAGE'
            context.scene.tool_settings.image_paint.canvas = packed_image

            # Add custom properties to the object
            obj["Mask_on"] = True
            obj["Mask_Active"] = True
        else:
            self.report({'WARNING'}, "No active object found")
        
        return {'FINISHED'}

class OBJECT_OT_edit_mask(bpy.types.Operator):
    """
    Edit the mask of the selected object.
    Hold Ctrl while activating to replace the mask image with a blank one.
    """
    bl_idname = "object.edit_mask"
    bl_label = "Edit Mask"
    bl_options = {'REGISTER', 'UNDO'}

    def invoke(self, context, event):
        self.ctrl_pressed = event.ctrl
        return self.execute(context)

    def execute(self, context):
        obj = context.active_object
        if obj:
            existing_image = None
            modifier_found = False  # Flag to check if the modifier is found

            for modifier in obj.modifiers:
                if modifier.type == 'NODES' and modifier.name.startswith("OCD_L"):
                    modifier_found = True
                    # Attempt to get the image from 'Socket_26'
                    if "Socket_26" in modifier:
                        socket_value = modifier["Socket_26"]
                        if isinstance(socket_value, bpy.types.Image):
                            existing_image = socket_value
                            break
                        elif isinstance(socket_value, str):
                            # If the socket value is a string (e.g., image name), try to get the image by name
                            existing_image = bpy.data.images.get(socket_value)
                            if existing_image:
                                break
                            else:
                                self.report({'WARNING'}, f"Image '{socket_value}' not found in bpy.data.images")
                        else:
                            self.report({'WARNING'}, f"Unexpected data type in 'Socket_26': {type(socket_value)}")
                    else:
                        self.report({'WARNING'}, "'Socket_26' not found in the modifier properties")
                    break  # Exit after processing the first matching modifier

            if not modifier_found:
                self.report({'WARNING'}, "No appropriate Geometry Nodes modifier found on the active object")
                return {'CANCELLED'}

            if existing_image:
                # If Ctrl is held during activation, replace the image with the blank image
                if getattr(self, 'ctrl_pressed', False):
                    # Get the path to the add-on directory
                    addon_directory = os.path.dirname(os.path.abspath(__file__))
                    blank_image_path = os.path.join(addon_directory, "OCD_Mask_blank.png")

                    if not os.path.isfile(blank_image_path):
                        self.report({'ERROR'}, f"Blank image not found at '{blank_image_path}'")
                        return {'CANCELLED'}
                    
                    # Unpack the image if it's packed
                    if existing_image.packed_file:
                        existing_image.unpack(method='REMOVE')
                    
                    # Replace the image with the blank image
                    existing_image.filepath = blank_image_path
                    existing_image.reload()

                    # Turn off and back on the modifier visibility to force an update
                    modifier.show_viewport = False
                    modifier.show_viewport = True
                    return {'FINISHED'}

                # Proceed with normal mask editing

                # Switch to Material Preview mode
                for area in context.screen.areas:
                    if area.type == 'VIEW_3D':
                        for space in area.spaces:
                            if space.type == 'VIEW_3D':
                                space.shading.type = 'MATERIAL'
                                break

                # Turn on Texture Paint mode
                bpy.ops.paint.texture_paint_toggle()

                # Set image paint mode to 'IMAGE' and select the existing texture
                context.scene.tool_settings.image_paint.mode = 'IMAGE'
                context.scene.tool_settings.image_paint.canvas = existing_image

                # Add custom property to track masking state
                obj["Mask_Active"] = True

                # Ensure 'Socket_23' is set to True and refresh the modifier
                modifier["Socket_23"] = True
                modifier.node_group.update_tag()

                # Turn off and back on the modifier visibility
                modifier.show_viewport = False
                modifier.show_viewport = True
            else:
                self.report({'WARNING'}, "No image found in 'Socket_26' of the Geometry Nodes modifier")
        else:
            self.report({'WARNING'}, "No active object found")
        
        return {'FINISHED'}

class OBJECT_OT_finish_mask(bpy.types.Operator):
    bl_idname = "object.finish_mask"
    bl_label = "Finish Mask"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obj = context.active_object
        if obj and obj.get("Mask_Active"):
            # Switch to Solid mode
            for area in context.screen.areas:
                if area.type == 'VIEW_3D':
                    for space in area.spaces:
                        if space.type == 'VIEW_3D':
                            space.shading.type = 'SOLID'
                            break

            # Turn off Texture Paint mode
            bpy.ops.paint.texture_paint_toggle()

            # Retrieve the mask image from Socket_26 of the Geometry Nodes modifier
            mask_image = None
            for modifier in obj.modifiers:
                if modifier.type == 'NODES' and modifier.name.startswith("OCD_L"):
                    if "Socket_26" in modifier:
                        mask_image = modifier["Socket_26"]
                        break

            # Pack the image to save changes
            if mask_image and isinstance(mask_image, bpy.types.Image):
                mask_image.pack()
            else:
                self.report({'WARNING'}, "No mask image found to pack")

            # Update the modifier
            for modifier in obj.modifiers:
                if modifier.type == 'NODES' and modifier.name.startswith("OCD_L"):
                    modifier["Socket_23"] = False
                    modifier.show_viewport = False
                    modifier.show_viewport = True

            # Set object mode
            bpy.ops.object.mode_set(mode='OBJECT')

            # Remove custom property indicating active masking
            if "Mask_Active" in obj:
                del obj["Mask_Active"]
        else:
            self.report({'WARNING'}, "No active masked object found")
        
        return {'FINISHED'}

class GEONODES_MT_CustomMenu(bpy.types.Menu):
    bl_label = "Select HERO Nodes"
    bl_idname = "GEONODES_MT_CustomMenu"

    def draw(self, context):
        layout = self.layout
        node_trees = [ng for ng in bpy.data.node_groups if ng.name.startswith("OCD_Hero") and ng.name != "OCD_Hero"]

        if not node_trees:
            layout.label(text="No HERO Nodes found.")
            return 

        for nt in node_trees:
            # Add an operator for each node tree, passing the node tree's name as a parameter
            op = layout.operator("object.assign_hero_node_tree", text=nt.name)
            op.node_tree_name = nt.name

class OBJECT_OT_AssignHeroNodeTree(bpy.types.Operator):
    bl_idname = "object.assign_hero_node_tree"
    bl_label = "Assign Hero Node Tree"
    bl_description = "Assign the selected Hero node tree to the active object's OCD_HERO modifier"
    bl_options = {'UNDO'}

    node_tree_name: bpy.props.StringProperty()

    def execute(self, context):
        node_tree = bpy.data.node_groups.get(self.node_tree_name)
        if not node_tree:
            self.report({'ERROR'}, f"Node tree '{self.node_tree_name}' not found.")
            return {'CANCELLED'}

        for obj in context.selected_objects:
            if obj.type == 'MESH':
                # Find an existing OCD_HERO modifier or create a new one
                mod = next((m for m in obj.modifiers if m.type == 'NODES' and m.name == "OCD_HERO"), None)
                if not mod:
                    mod = obj.modifiers.new(name="OCD_HERO", type='NODES')
                mod.node_group = node_tree
                # Pin the modifier to the last position
                mod.use_pin_to_last = True
        return {'FINISHED'}

class OBJECT_OT_hero(bpy.types.Operator):
    bl_idname = "object.hero"
    bl_label = "OCD Hero"
    bl_description = "Activate HERO Mode"
    bl_options = {'UNDO'}

    def load_node_group(self, blend_file_path):
        """ Load the node group from the specified blend file. """
        with bpy.data.libraries.load(blend_file_path) as (data_from, data_to):
            if "OCD_Hero" in data_from.node_groups:
                data_to.node_groups = ["OCD_Hero"]
            else:
                return None
        return bpy.data.node_groups.get("OCD_Hero", None)

    def get_unique_node_group_name(self, base_name):
        """ Generate a unique node group name. """
        counter = 1
        unique_name = base_name
        while bpy.data.node_groups.get(unique_name) is not None:
            unique_name = f"{base_name}.{str(counter).zfill(3)}"
            counter += 1
        return unique_name

    def invoke(self, context, event):
        if event.ctrl:
            bpy.ops.wm.call_menu(name="GEONODES_MT_CustomMenu")
            return {'FINISHED'}
        else:
            addon_path = os.path.dirname(os.path.realpath(__file__))
            blend_file_path = os.path.join(addon_path, 'data.blend')

            # Use the existing node group if it's already in the scene
            node_group = bpy.data.node_groups.get("OCD_Hero", None)

            # If the node group is not found, try loading it from the file
            if not node_group:
                if not os.path.isfile(blend_file_path):
                    self.report({'ERROR'}, "data.blend file not found")
                    return {'CANCELLED'}
                try:
                    node_group = self.load_node_group(blend_file_path)
                    if not node_group:
                        self.report({'ERROR'}, "Node group 'OCD_Hero' not found or failed to load.")
                        return {'CANCELLED'}
                except Exception as e:
                    self.report({'ERROR'}, str(e))
                    return {'CANCELLED'}

            unique_name = self.get_unique_node_group_name("OCD_Hero")

            # Copy the node group with a unique name
            node_group_copy = node_group.copy()
            node_group_copy.name = unique_name

            for obj in context.selected_objects:
                if obj.type == 'MESH':
                    #bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY', center='MEDIAN')
                    mod = obj.modifiers.new(name="OCD_HERO", type='NODES')
                    mod.node_group = node_group_copy

                    mod.use_pin_to_last = True

            return {'FINISHED'}

is_focus_mode = False
is_local_view = False

class OBJECT_OT_focus(bpy.types.Operator):
    bl_idname = "object.focus"
    bl_label = "HERO Focus"
    bl_description = "Focus on Selected HERO object"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.active_object is not None

    def invoke(self, context, event):
        global is_local_view
        # Check if the Ctrl key was pressed during the operator's invocation
        if event.ctrl:
            # Perform focus on selected and toggle local view
            bpy.ops.view3d.localview()
            is_local_view = True
        # Proceed to execute the rest of the operator's logic
        return self.execute(context)

    def execute(self, context):
        global is_focus_mode

        selected_obj = context.active_object

        if not selected_obj:
            self.report({'WARNING'}, "No object selected")
            return {'CANCELLED'}

        # Get the node tree of the selected object's Geometry Nodes modifier
        selected_node_tree = next((mod.node_group for mod in selected_obj.modifiers if mod.type == 'NODES' and mod.node_group.name.startswith("OCD_Hero")), None)

        if not selected_node_tree:
            self.report({'WARNING'}, "Selected object does not have a 'OCD_HERO' Geometry Nodes modifier")
            return {'CANCELLED'}

        # Count objects with 'OCD_HERO' GN modifiers sharing the same node tree
        matching_objects = [obj for obj in bpy.data.objects if any(mod for mod in obj.modifiers if mod.type == 'NODES' and mod.node_group == selected_node_tree)]

        # Skip focus mode if there's only one such object
        if len(matching_objects) <= 1:
            return {'FINISHED'}

        # Toggle the focus state
        is_focus_mode = not is_focus_mode

        if is_focus_mode:
            self.apply_focus(context, selected_node_tree)
        else:
            self.clear_focus(context, selected_node_tree)

        return {'FINISHED'}

    def apply_focus(self, context, selected_node_tree):
        selected_objects = context.selected_objects
        if not selected_objects:
            return

        for obj in bpy.data.objects:
            if obj not in selected_objects:
                for mod in obj.modifiers:
                    if mod.type == 'NODES' and mod.node_group == selected_node_tree:
                        mod.show_viewport = False

    def clear_focus(self, context, selected_node_tree):
        global is_local_view
        if is_local_view:
            bpy.ops.view3d.localview()
            is_local_view = False
        for obj in bpy.data.objects:
            for mod in obj.modifiers:
                if mod.type == 'NODES' and mod.node_group == selected_node_tree:
                    mod.show_viewport = True

class OBJECT_OT_selection(bpy.types.Operator):
    bl_idname = "object.selection"
    bl_label = "HERO Select"
    bl_description = "Select similar HERO objects"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        selected_obj = context.active_object

        if not selected_obj:
            self.report({'WARNING'}, "No object selected")
            return {'CANCELLED'}

        # Get the node tree of the Geometry Nodes modifier from the selected object
        selected_node_tree = next((mod.node_group for mod in selected_obj.modifiers if mod.type == 'NODES' and mod.node_group and mod.node_group.name.startswith("OCD_Hero")), None)

        if not selected_node_tree:
            self.report({'WARNING'}, "Selected object does not have a 'OCD_HERO' Geometry Nodes modifier with a valid node tree")
            return {'CANCELLED'}

        # Also check for objects in the same collections as the selected object
        collections_containing_selected_obj = [coll for coll in bpy.data.collections if selected_obj.name in coll.objects]

        # Iterate through all collections that contain the selected object
        for coll in collections_containing_selected_obj:
            for obj in coll.objects:
                # Check each object's modifiers for a matching node tree
                for mod in obj.modifiers:
                    if mod.type == 'NODES' and mod.node_group == selected_node_tree:
                        obj.select_set(True)
        #active object remains active 
        context.view_layer.objects.active = selected_obj

        return {'FINISHED'}

copied_node_tree_name = ""

class OBJECT_OT_copy(bpy.types.Operator):
    bl_idname = "object.copy"
    bl_label = "HERO Copy"
    bl_description = "Copy HERO Nodes"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        global copied_node_tree_name
        selected_obj = context.active_object

        if not selected_obj:
            self.report({'WARNING'}, "No object selected")
            return {'CANCELLED'}

        # Find the node tree from the selected object's "OCD_HERO" modifier
        node_tree = next((mod.node_group for mod in selected_obj.modifiers if mod.type == 'NODES' and mod.node_group.name.startswith("OCD_Hero")), None)

        if not node_tree:
            self.report({'WARNING'}, "Selected object does not have a suitable 'OCD_HERO' Geometry Nodes modifier")
            return {'CANCELLED'}

        # Copy the node tree name
        copied_node_tree_name = node_tree.name
        self.report({'INFO'}, f"Copied GN tree: {copied_node_tree_name}")

        return {'FINISHED'}

class OBJECT_OT_paste(bpy.types.Operator):
    bl_idname = "object.paste"
    bl_label = "HERO Paste"
    bl_description = "Paste HERO Nodes"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        global copied_node_tree_name

        if not context.selected_objects:
            self.report({'WARNING'}, "No objects selected")
            return {'CANCELLED'}

        if not copied_node_tree_name:
            self.report({'WARNING'}, "No Geometry Nodes tree copied")
            return {'CANCELLED'}

        for obj in context.selected_objects:
            if obj.type != 'MESH':
                continue  # Skip non-mesh objects

            # Find or create the "OCD_HERO" modifier
            ocd_hero_mod = next((mod for mod in obj.modifiers if mod.type == 'NODES' and mod.node_group.name.startswith("OCD_Hero")), None)
            if not ocd_hero_mod:
                ocd_hero_mod = obj.modifiers.new(name="OCD_HERO", type='NODES')

            # Assign the copied node tree
            ocd_hero_mod.node_group = bpy.data.node_groups.get(copied_node_tree_name, None)
            if not ocd_hero_mod.node_group:
                self.report({'WARNING'}, f"Node tree '{copied_node_tree_name}' not found in this file")
                return {'CANCELLED'}
        
        return {'FINISHED'}

class OBJECT_OT_hero_to_mesh(Operator):
    """Convert selected HERO objects to Mesh"""
    bl_idname = "object.hero_to_mesh"
    bl_label = "HERO to Mesh"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        for obj in context.selected_objects:
            # Ensure the object is the active object
            context.view_layer.objects.active = obj
            bpy.ops.object.convert(target='MESH')
        return {'FINISHED'}

class OBJECT_OT_remove_ocd_hero(Operator):
    bl_idname = "object.remove_ocd_hero"
    bl_label = "Remove Modifiers with OCD Hero Node Tree"
    bl_description = "Remove HERO from selected object"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        removed_count = 0

        for obj in context.selected_objects:
            if obj.type != 'MESH':
                continue  # Skip non-mesh objects

            # Iterate over modifiers and remove those whose node tree name starts with "OCD_Hero"
            for mod in obj.modifiers:
                if mod.type == 'NODES' and mod.node_group and mod.node_group.name.startswith("OCD_Hero"):
                    obj.modifiers.remove(mod)
                    removed_count += 1

        if removed_count == 0:
            self.report({'INFO'}, "No modifiers with 'OCD_HERO' node tree found on selected objects")
        else:
            self.report({'INFO'}, f"Removed {removed_count} modifiers with 'OCD_HERO'")

        return {'FINISHED'}

class OBJECT_OT_turn_on_hero(bpy.types.Operator):
    bl_idname = "object.turn_on_hero"
    bl_label = "Turn HERO On"
    bl_description = "Turn On HERO Nodes"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        for obj in context.selected_objects:
            for mod in obj.modifiers:
                if mod.type == 'NODES' and mod.node_group and mod.node_group.name.startswith("OCD_Hero"):
                    mod.show_viewport = True  # Enable the modifier in the viewport
                    #mod.show_render = True  # Enable the modifier for rendering
        return {'FINISHED'}

class OBJECT_OT_turn_off_hero(bpy.types.Operator):
    bl_idname = "object.turn_off_hero"
    bl_label = "Turn HERO Off"
    bl_description = "Turn Off HERO Nodes"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        for obj in context.selected_objects:
            for mod in obj.modifiers:
                if mod.type == 'NODES' and mod.node_group and mod.node_group.name.startswith("OCD_Hero"):
                    mod.show_viewport = False  # Disable the modifier in the viewport
                    #mod.show_render = False  # Disable the modifier for rendering
        return {'FINISHED'}


def node_hero_add(context, filepath, node_group, ungroup, report, mouse_x, mouse_y):
    space = context.space_data
    node_tree = space.node_tree
    node_active = context.active_node
    node_selected = context.selected_nodes

    if node_tree is None:
        report({'ERROR'}, "No node tree available")
        return

    # Check if the node group is already present in the current file
    existing_node_group = bpy.data.node_groups.get(node_group)
    if existing_node_group:
        node_group = existing_node_group
    else:
        with bpy.data.libraries.load(filepath, link=False) as (data_from, data_to):
            assert(node_group in data_from.node_groups)
            data_to.node_groups = [node_group]
        node_group = data_to.node_groups[0]

    # add node!
    for node in node_tree.nodes:
        node.select = False

    node_type_string = {
        "GeometryNodeTree": "GeometryNodeGroup",
    }[type(node_tree).__name__]

    node = node_tree.nodes.new(type=node_type_string)
    node.node_tree = node_group
    node.name = node_group.name  # Set the node name to the actual group name
    node.location = Vector((mouse_x, mouse_y))

    is_fail = (node.node_tree is None)
    if is_fail:
        report({'WARNING'}, "Incompatible node type")

    node.select = True
    node_tree.nodes.active = node

    if is_fail:
        node_tree.nodes.remove(node)
    else:
        if ungroup:
            bpy.ops.node.group_ungroup()

class NODE_OT_Hero_add(Operator):
    bl_idname = "node.hero_add"
    bl_label = "Add Hero node group"
    bl_description = "Add Hero node"
    bl_options = {'REGISTER', 'UNDO'}

    filepath: StringProperty(
        subtype='FILE_PATH',
    )
    group_name: StringProperty()
    ungroup: bpy.props.BoolProperty(default=False)

    y: bpy.props.FloatProperty()
    x: bpy.props.FloatProperty()

    def execute(self, context):
        if bpy.app.version < (4, 5, 0):
            self.report({'ERROR'}, "HERO module requires Blender 4.5.0 or higher")
            return {'CANCELLED'}
        else:
            node_hero_add(context, self.filepath, self.group_name, self.ungroup, self.report, self.x, self.y)
            bpy.ops.transform.translate('INVOKE_DEFAULT')
            return {'FINISHED'}

    def invoke(self, context, event):
        region = context.region.view2d
        ui_scale = context.preferences.system.ui_scale
        x, y = region.region_to_view(event.mouse_region_x, event.mouse_region_y)
        self.x, self.y = x / ui_scale, y / ui_scale
        self.ungroup = event.shift
        return self.execute(context) 

class NODE_MT_Hero_main(Menu):
    bl_label = "OCD HERO"

    def draw(self, context):
        layout = self.layout

        mask_node_items = [("data.blend", "HERO - Noise Mask"), ("data.blend", "HERO - Gradient Mask"), ("data.blend", "HERO - Material Mask"), ("data.blend", "HERO - Direction Mask"), ("data.blend", "HERO - Obj Pos Mask")]
        utils_node_items = [("data.blend", "HERO - Texture Transform"), ("data.blend", "HERO - Trimesh"), ("data.blend", "HERO - Blur"), ("data.blend", "HERO - UV Transfer"), ("data.blend", "HERO - Mask Invert"), ("data.blend", "HERO - Mask Combine")]
        main_node_items = [("data.blend", "HERO - Start"), ("data.blend", "HERO - End"), ("data.blend", "HERO - Displace"), ("data.blend", "HERO - Scatter"), ("data.blend", "HERO - Image Displace 2.0")]
        
        main_menu = layout.menu(NODE_MT_Hero_main_nodes.__name__, text="Mains")
        mask_menu = layout.menu(NODE_MT_Hero_mask.__name__, text="Masks")
        utils_menu = layout.menu(NODE_MT_Hero_utils.__name__, text="Utils")

class NODE_MT_Hero_mask(Menu):
    bl_label = "Masks"
    def draw(self, context):
        layout = self.layout
        mask_node_items = [("data.blend", "HERO - Noise Mask"), ("data.blend", "HERO - Gradient Mask"), ("data.blend", "HERO - Material Mask"), ("data.blend", "HERO - Direction Mask"), ("data.blend", "HERO - Obj Pos Mask")]

        for blend_filename, label in mask_node_items:
            filepath = get_blend_file_path(blend_filename)
            if os.path.isfile(filepath):
                with bpy.data.libraries.load(filepath) as (data_from, data_to):
                    for group_name in data_from.node_groups:
                        if group_name == label:
                            props = layout.operator(
                                NODE_OT_Hero_add.bl_idname,
                                text=label,
                            )
                            props.filepath = filepath
                            props.group_name = group_name
            else:
                layout.label(text=f"{label}: .blend file not found", icon='ERROR')        

class NODE_MT_Hero_utils(Menu):
    bl_label = "Utils"
    def draw(self, context):
        layout = self.layout
        utils_node_items = [("data.blend", "HERO - Texture Transform"), ("data.blend", "HERO - Trimesh"), ("data.blend", "HERO - Blur"), ("data.blend", "HERO - UV Transfer"), ("data.blend", "HERO - Mask Invert"), ("data.blend", "HERO - Mask Combine")]

        for blend_filename, label in utils_node_items:
            filepath = get_blend_file_path(blend_filename)
            if os.path.isfile(filepath):
                with bpy.data.libraries.load(filepath) as (data_from, data_to):
                    for group_name in data_from.node_groups:
                        if group_name == label:
                            props = layout.operator(
                                NODE_OT_Hero_add.bl_idname,
                                text=label,
                            )
                            props.filepath = filepath
                            props.group_name = group_name
            else:
                layout.label(text=f"{label}: .blend file not found", icon='ERROR')        

class NODE_MT_Hero_main_nodes(Menu):
    bl_label = "Mains"
    def draw(self, context):
        layout = self.layout
        main_node_items = [("data.blend", "HERO - Start"), ("data.blend", "HERO - End"), ("data.blend", "HERO - Displace"), ("data.blend", "HERO - Scatter"), ("data.blend", "HERO - Image Displace 2.0")]

        for blend_filename, label in main_node_items:
            filepath = get_blend_file_path(blend_filename)
            if os.path.isfile(filepath):
                with bpy.data.libraries.load(filepath) as (data_from, data_to):
                    for group_name in data_from.node_groups:
                        if group_name == label:
                            props = layout.operator(
                                NODE_OT_Hero_add.bl_idname,
                                text=label,
                            )
                            props.filepath = filepath
                            props.group_name = group_name
            else:
                layout.label(text=f"{label}: .blend file not found", icon='ERROR')    

def add_hero_node_button(self, context):
    space = context.space_data
    if space.type == 'NODE_EDITOR' and space.tree_type == 'GeometryNodeTree':
        self.layout.menu(
            NODE_MT_Hero_main.__name__,
            text="OCD Hero",
            icon='EVENT_H',
        )

class OCDProperties(bpy.types.PropertyGroup):
    show_ocd_control_panel: bpy.props.BoolProperty(
        name="Show OCD Control Panel",
        description="Expand/Collapse the OCD Control Panel",
        default=True
    )
    show_hero_control_panel: bpy.props.BoolProperty(
        name="Show HERO Control Panel",
        description="Expand/Collapse the HERO Control Panel",
        default=True
    )

class OBJECT_PT_OCD_panel(bpy.types.Panel):
    bl_label = 'One Click Damage v2.5.0'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'OCD 2'
    
    def draw(self, context):
        layout = self.layout
        obj = context.active_object
        selected_objects = context.selected_objects

        # Access the OCD properties group
        ocd_props = context.scene.ocd_props

        ocd_box = layout.column()
        ocd_row = ocd_box.row()
        ocd_box.scale_y = 2.0

        # Determine if the button should trigger the "copy_ocd_modifiers" operator
        # Check if multiple objects are selected and if the active object has an OCD_L modifier
        if obj and any(mod.name.startswith("OCD_L") for mod in obj.modifiers) and len(selected_objects) > 1:
            target_objects = [
                o for o in selected_objects if o != obj and o.type == 'MESH' and not any(mod.name.startswith("OCD_L") for mod in o.modifiers)
            ]
            if target_objects:
                # Use the custom operator if the condition is met
                ocd_row.operator("object.copy_ocd_modifiers", text="COPY DAMAGE", depress=True)
            else:
                # Fallback to default operator if no eligible objects are found
                ocd_row.operator("object.ocd", text="MAKE DAMAGE", depress=True)
        else:
            # Default to "MAKE DAMAGE" if the conditions are not met
            ocd_row.operator("object.ocd", text="MAKE DAMAGE", depress=True)

        # Additional buttons: Only show if all selected objects have relevant OCD_L modifiers
        all_dmg = selected_objects and all(any(mod for mod in o.modifiers if mod.type == 'NODES' and mod.name.startswith("OCD_L")) for o in selected_objects)
        if all_dmg:
            # Create a box frame
            ocd_box = layout.box()
            ocd_row = ocd_box.row()

            # Create a collapsible section within the box
            ocd_row.prop(ocd_props, "show_ocd_control_panel", text="", icon="TRIA_DOWN" if ocd_props.show_ocd_control_panel else "TRIA_RIGHT", emboss=False)
            ocd_row.label(text="OCD Control Panel:", icon='PROPERTIES')

            if ocd_props.show_ocd_control_panel:
                # Add RANDOMIZE DAMAGE button below
                ocd_row = ocd_box.row()
                ocd_row.scale_y = 2.0
                ocd_row.operator("object.randomize_ocd", text="Change Pattern", depress=False)
                ocd_row.operator("object.copy_from_active", text="Sync Damage", depress=False)

                # Check if any of the selected objects have been baked
                any_baked = any("is_baked" in o for o in selected_objects)

                # Add MASK buttons depending on the state of masking
                base_name = f"{obj.name}_mask"
                existing_image = next((img for img in bpy.data.images if img.name.startswith(base_name)), None)

                # Determine if Socket_26 is not None in the OCD_L modifier
                modifier_with_socket_26 = None
                for mod in obj.modifiers:
                    if mod.type == 'NODES' and mod.name.startswith("OCD_L"):
                        if mod.get("Socket_26") is not None:
                            modifier_with_socket_26 = mod
                            break

                if obj and obj.get("Mask_Active"):
                    ocd_row = ocd_box.row()
                    ocd_row.scale_y = 1.5
                    ocd_row.operator("object.finish_mask", text="Finish Mask", depress=False)
                elif modifier_with_socket_26:
                    ocd_row = ocd_box.row()
                    ocd_row.scale_y = 1.5
                    ocd_row.operator("object.edit_mask", text="Edit Mask", depress=False)
                else:
                    ocd_row = ocd_box.row()
                    ocd_row.scale_y = 1.5
                    ocd_row.operator("object.add_mask", text="Create Mask", depress=False)

                # Place Bake and Clear Bake buttons in the same row with conditional enabling
                ocd_row = ocd_box.row()
                ocd_row.scale_y = 2.0
                ocd_row.operator("object.ocd_bake", text="Bake", depress=False)

                # Create a column for the "Clear Bake" button and set its enabled state
                clear_bake_column = ocd_row.column()
                clear_bake_column.enabled = any_baked
                clear_bake_column.operator("object.delete_bake", text="Clear Bake", depress=False)

                ocd_row = ocd_box.row()
                ocd_row.operator("object.turn_on_ocd", text="On", icon='HIDE_OFF', depress=False)
                ocd_row.operator("object.turn_off_ocd", text="Off", icon='HIDE_ON', depress=False)

                # Add APPLY and REMOVE buttons in the same row
                ocd_row = ocd_box.row()
                ocd_row.operator("object.apply_ocd_modifiers", text="Apply", icon='CHECKMARK', depress=False)
                ocd_row.operator("object.remove_ocd_modifiers", text="Remove", icon='CANCEL', depress=False)
            
        ocd_hero_mod = any(mod for obj in selected_objects for mod in obj.modifiers if mod.type == 'NODES' and mod.node_group and mod.node_group.name.startswith("OCD_Hero"))     

        # Draw the "GO HERO" button only if no HERO modifiers are present
        if not ocd_hero_mod:
            hero_box = layout.column()
            hero_row = hero_box.row()
            hero_box.scale_y = 2.0
            hero_row.operator("object.hero", text="GO HERO", depress=True)

        # Draw the HERO Control Panel if HERO modifiers are present
        if ocd_hero_mod:
            # Create a box for the HERO Control Panel
            hero_control_panel = layout.box()
            hero_row = hero_control_panel.row()

            # Create a collapsible section within the box
            hero_row.prop(ocd_props, "show_hero_control_panel", text="", icon="TRIA_DOWN" if ocd_props.show_hero_control_panel else "TRIA_RIGHT", emboss=False)
            hero_row.label(text="HERO Control Panel:", icon='PROPERTIES')

            if ocd_props.show_hero_control_panel:
                # Row with Focus and Select All buttons
                row = hero_control_panel.row()
                # Choose the icon based on is_focus_mode state
                focus_icon = 'OUTLINER_OB_LIGHT' if is_focus_mode else 'LIGHT_DATA'
                row.operator("object.focus", text="Focus", icon=focus_icon)
                row.operator("object.selection", text="Select All")

                # Separate line
                #hero_control_panel.separator()

                # Copy and Paste buttons in the same column, closer vertically
                col = hero_control_panel.column(align=False)
                col.operator("object.copy", text="Copy")
                col.operator("object.paste", text="Paste")

                # Separate line
                #hero_control_panel.separator()

                # Row with On and Off buttons
                row = hero_control_panel.row()
                row.operator("object.turn_on_hero", text="On", icon='HIDE_OFF')
                row.operator("object.turn_off_hero", text="Off", icon='HIDE_ON')
                
                # Separate line
                #hero_control_panel.separator()
                
                # To Mesh and Remove buttons in the same column, with scale_y = 2.0
                col = hero_control_panel.column(align=False)
                col.scale_y = 2.0
                col.operator("object.hero_to_mesh", text="To Mesh", icon='CHECKMARK', depress=True)
                col.operator("object.remove_ocd_hero", text="Remove", icon='CANCEL')
        
# ------------------------------------------------------------------------
#    Registration
# ------------------------------------------------------------------------

classes = [
    OBJECT_OT_ocd,
    OBJECT_OT_copy_ocd_modifiers,
    OBJECT_OT_copy_from_active,
    OBJECT_OT_apply_ocd_modifiers,
    OBJECT_OT_remove_ocd_modifiers,
    OBJECT_OT_randomize_ocd,
    OBJECT_OT_ocd_bake,
    OBJECT_OT_delete_bake,
    OBJECT_OT_turn_off_ocd,
    OBJECT_OT_turn_on_ocd,
    OBJECT_OT_add_mask,
    OBJECT_OT_edit_mask,
    OBJECT_OT_finish_mask,
    GEONODES_MT_CustomMenu,
    OBJECT_OT_AssignHeroNodeTree,
    OBJECT_OT_hero,
    OBJECT_OT_focus,
    OBJECT_OT_selection,
    OBJECT_OT_copy,
    OBJECT_OT_paste,
    OBJECT_OT_hero_to_mesh,
    OBJECT_OT_remove_ocd_hero,
    OBJECT_OT_turn_on_hero,
    OBJECT_OT_turn_off_hero,
    NODE_OT_Hero_add,
    NODE_MT_Hero_main,
    NODE_MT_Hero_mask,
    NODE_MT_Hero_utils,
    NODE_MT_Hero_main_nodes,
    OCDProperties,
    OBJECT_PT_OCD_panel,
    ]

def register():
    for cl in classes:
       register_class(cl)

    bpy.types.NODE_MT_add.append(add_hero_node_button)
    bpy.types.Scene.ocd_props = bpy.props.PointerProperty(type=OCDProperties)

def unregister():
    for cl in reversed(classes):
        unregister_class(cl)
    
    bpy.types.NODE_MT_add.remove(add_hero_node_button)
    del bpy.types.Scene.ocd_props
    