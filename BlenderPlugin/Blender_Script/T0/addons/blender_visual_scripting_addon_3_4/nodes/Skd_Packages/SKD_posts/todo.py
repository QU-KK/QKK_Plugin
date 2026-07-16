import bpy
import textwrap
from ...base_node import SN_ScriptingBaseNode

class SKD_AddTodoItemOperator(bpy.types.Operator):
    """Add a new todo item"""
    bl_idname = "skd.add_todo_item"
    bl_label = "Add Todo Item"

    item_text: bpy.props.StringProperty()  # This will store the text to add

    def execute(self, context):
        node = context.node
        if node and hasattr(node, 'add_item'):
            node.add_item(self.item_text, context)
        return {'FINISHED'}


class SKD_RemoveTodoItemOperator(bpy.types.Operator):
    """Remove a todo item"""
    bl_idname = "skd.remove_todo_item"
    bl_label = "Remove Todo Item"

    item_index: bpy.props.IntProperty()  # This defines the property to store the index

    def execute(self, context):
        node = context.node
        if node and hasattr(node, 'remove_item'):
            node.remove_item(self.item_index, context)
        return {'FINISHED'}


class SKD_MoveTodoItemUpOperator(bpy.types.Operator):
    """Move a todo item up"""
    bl_idname = "skd.move_todo_item_up"
    bl_label = "Move Todo Item Up"

    item_index: bpy.props.IntProperty()  # This defines the property to store the index

    def execute(self, context):
        node = context.node
        if node and hasattr(node, 'move_item_up'):
            node.move_item_up(self.item_index, context)
        return {'FINISHED'}


class SKD_MoveTodoItemDownOperator(bpy.types.Operator):
    """Move a todo item down"""
    bl_idname = "skd.move_todo_item_down"
    bl_label = "Move Todo Item Down"

    item_index: bpy.props.IntProperty()  # This defines the property to store the index

    def execute(self, context):
        node = context.node
        if node and hasattr(node, 'move_item_down'):
            node.move_item_down(self.item_index, context)
        return {'FINISHED'}


class TodoItem(bpy.types.PropertyGroup):
    text: bpy.props.StringProperty()
    show_update_button: bpy.props.BoolProperty(default=False)  # Property to toggle the visibility of the update button


class SKD_PrintTodoItemTextOperator(bpy.types.Operator):
    """Print the text of the current todo item and load it into String input"""
    bl_idname = "skd.print_todo_item_text"
    bl_label = "Print Todo Item Text"

    item_index: bpy.props.IntProperty()  # This defines the property to store the index

    def execute(self, context):
        node = context.node
        if node and hasattr(node, 'todo_items') and 0 <= self.item_index < len(node.todo_items):
            item_text = node.todo_items[self.item_index].text
            node.inputs["String"].default_value = item_text
            # Set the property to show the "Update" button
            node.todo_items[self.item_index].show_update_button = True
            # Set other items to hide the "Update" button
            for idx, item in enumerate(node.todo_items):
                if idx != self.item_index:
                    item.show_update_button = False
            return {'FINISHED'}
        return {'CANCELLED'}


class SKD_UpdateTodoItemOperator(bpy.types.Operator):
    """Update the selected todo item"""
    bl_idname = "skd.update_todo_item"
    bl_label = "Update Todo Item"

    item_index: bpy.props.IntProperty()  # This defines the property to store the index

    def execute(self, context):
        node = context.node
        if node and hasattr(node, 'todo_items') and 0 <= self.item_index < len(node.todo_items):
            # Perform update operation here
            item_text = node.inputs["String"].default_value
            node.todo_items[self.item_index].text = item_text
            # Set the property to hide the "Update" button after it was pressed
            node.todo_items[self.item_index].show_update_button = False
            node.inputs["String"].default_value = ""
            return {'FINISHED'}
        return {'CANCELLED'}


class SN_SKD_todoNode(SN_ScriptingBaseNode, bpy.types.Node):

    bl_idname = "SN_SKD_todoNode"
    bl_label = "Todo"
    bl_width_default = 300
    node_color = (0.331545, 0.327661, 0.325938)

    todo_items: bpy.props.CollectionProperty(type=TodoItem)

    def on_create(self, context):
        self.add_string_input("String").set_hide(True)

    def add_item(self, item_text, context):
        if item_text:  # Check if the text is not empty
            todo_item = self.todo_items.add()
            todo_item.text = item_text.replace("'", "")
            self.inputs["String"].default_value = ""  # Reset input field to an empty string
            self._evaluate(context)

    def remove_item(self, item_index, context):
        if item_index >= 0 and item_index < len(self.todo_items):
            self.todo_items.remove(item_index)
            self._evaluate(context)

    def move_item_up(self, item_index, context):
        if item_index > 0:
            self.todo_items.move(item_index, item_index - 1)
            self._evaluate(context)

    def move_item_down(self, item_index, context):
        if item_index < len(self.todo_items) - 1:
            self.todo_items.move(item_index, item_index + 1)
            self._evaluate(context)

    def draw_node(self, context, layout):
        row = layout.row()
        row.prop(self.inputs["String"], "default_value", text="")

        # Determine whether to show "Add Item" or "Update" button
        show_add_item = True
        for todo_item in self.todo_items:
            if todo_item.show_update_button:
                show_add_item = False
                break

        # Add button for adding a new todo item or updating existing one
        if show_add_item:
            add_op = row.operator(SKD_AddTodoItemOperator.bl_idname, text="Add Item", icon='NONE')
            add_op.item_text = self.inputs["String"].default_value  # Pass the current input text to the operator
        else:
            update_op = row.operator(SKD_UpdateTodoItemOperator.bl_idname, text="Update", icon='NONE')
            update_op.item_index = [idx for idx, item in enumerate(self.todo_items) if item.show_update_button][0]

        num_items = len(self.todo_items)
        for index, todo_item in enumerate(self.todo_items):
            row = layout.row(align=True)  # Ensure alignment
            col = row.column()
            box = col.box()
            texters = todo_item.text
            width = self.width
            threshold = (int(width / 12) if int(width <= 150) else int(width / 9))
            textTowrap = texters      
            wrapp = textwrap.TextWrapper(width=threshold)       
            wList = wrapp.wrap(text=textTowrap)
            for item in wList:
                box.label(text=item)

            # Button to print item text
            print_op = row.operator(SKD_PrintTodoItemTextOperator.bl_idname, text="", icon='CURRENT_FILE')
            print_op.item_index = index

            # Button to move item up
            if index > 0:
                up_op = row.operator(SKD_MoveTodoItemUpOperator.bl_idname, text="", icon='TRIA_UP', emboss=True)
                up_op.item_index = index
            else:
                up_op = row.operator(SKD_MoveTodoItemUpOperator.bl_idname, text="", icon='TRIA_UP', emboss=False)
                up_op.item_index = index

            # Button to move item down
            if index < num_items - 1:
                down_op = row.operator(SKD_MoveTodoItemDownOperator.bl_idname, text="", icon='TRIA_DOWN', emboss=True)
                down_op.item_index = index
            else:
                down_op = row.operator(SKD_MoveTodoItemDownOperator.bl_idname, text="", icon='TRIA_DOWN', emboss=False)
                down_op.item_index = index

            # Button to remove item
            remove_op = row.operator(SKD_RemoveTodoItemOperator.bl_idname, text="", icon='X', emboss=False)
            remove_op.item_index = index
