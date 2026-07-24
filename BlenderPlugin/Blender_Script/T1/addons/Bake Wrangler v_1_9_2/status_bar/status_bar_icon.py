import bpy


# An operator to open a new window and display the text log when you click on the icon
class click_bw_icon(bpy.types.Operator):
    '''Open baking log'''
    bl_idname = "bake_wrangler.open_log"
    bl_label = ""
    
    @classmethod
    def poll(type, context):
        return getattr(bpy.context.window_manager, 'bw_status', -1) > -1
        
    def invoke(self, context, event):
        text = None
        if event.alt and event.ctrl:
            file = getattr(bpy.context.window_manager, 'bw_lastfile', "")
            if file:
                import subprocess
                sub = subprocess.Popen([bpy.path.abspath(bpy.app.binary_path), file])
        elif event.ctrl:
            log = getattr(bpy.context.window_manager, 'bw_lastlog', "")
            if log: text = bpy.data.texts.load(log)
        else:
            if "BakeWrangler" in bpy.data.texts: text = bpy.data.texts["BakeWrangler"]
        if text:
            bpy.ops.wm.window_new()
            log_win = context.window_manager.windows[-1]
            log_ed = log_win.screen.areas[0]
            log_ed.type = 'TEXT_EDITOR'
            log_ed.spaces[0].text = text
            log_ed.spaces[0].show_line_numbers = False
            log_ed.spaces[0].show_syntax_highlight = False
            bpy.ops.text.move(type='FILE_TOP')
        return {'FINISHED'}


# Draw a different icon depending on the current bake state
def draw_bw_icon(self, context):
    row = self.layout.row(align=True)
    bake_status = getattr(bpy.context.window_manager, 'bw_status', -1)
    if bake_status == 0: #Good (green)
        row.operator("bake_wrangler.open_log", text="", icon_value=status_icons['main']['bw_good'].icon_id)
    elif bake_status == 1: #Baking (blue)
        row.operator("bake_wrangler.open_log", text="", icon_value=status_icons['main']['bw_working'].icon_id)
    elif bake_status == 2: #Error (red)
        row.operator("bake_wrangler.open_log", text="", icon_value=status_icons['main']['bw_error'].icon_id)


# Make the status bar redraw itself
def redraw_status_bar(context):
    # This causes the status bar to redraw without deleting any custom drawing fns appended to it
    context.workspace.status_text_set_internal(None)
    
    
# Remove and then re-add icon draw function to the status bar to make sure it's there
def ensure_bw_icon():
    bpy.types.STATUSBAR_HT_header.remove(draw_fn)
    bpy.types.STATUSBAR_HT_header.append(draw_fn)
    
    
# Remove the icon if it is turned off
def disable_bw_icon():
    bpy.types.STATUSBAR_HT_header.remove(draw_fn)
    

# Classes to register
classes = (
    click_bw_icon,
)

draw_fn = draw_bw_icon
status_icons = {}

def register():
    # Set up custom status icon collection
    import os
    import bpy.utils.previews
    icons_col = bpy.utils.previews.new()
    icons_dir = os.path.join(os.path.dirname(__file__), "icons")
    # Load icons in
    icons_col.load("bw_good", os.path.join(icons_dir, "bw_good.png"), 'IMAGE')
    icons_col.load("bw_working", os.path.join(icons_dir, "bw_working.png"), 'IMAGE')
    icons_col.load("bw_error", os.path.join(icons_dir, "bw_error.png"), 'IMAGE')
    status_icons["main"] = icons_col
    from bpy.utils import register_class
    for cls in classes:
        register_class(cls)
    # Add the icon drawing function to the status bar
    bpy.types.STATUSBAR_HT_header.append(draw_fn)
   
   
def unregister():
    # Remove the icon drawing function from the status bar
    bpy.types.STATUSBAR_HT_header.remove(draw_fn)
    from bpy.utils import unregister_class
    for cls in reversed(classes):
        unregister_class(cls)
    # Remove custom icons
    for icon_col in status_icons.values():
        bpy.utils.previews.remove(icon_col)
    status_icons.clear()


if __name__ == "__main__":
    register()
