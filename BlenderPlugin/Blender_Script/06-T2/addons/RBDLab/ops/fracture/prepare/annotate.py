import bpy
from bpy.types import Operator, Area, Context
from ....addon.naming import RBDLabNaming
from ....Global.get_common_vars import get_common_vars
from ....Global.basics import context_override



class RBDLAB_anotation_paint(Operator):
    bl_idname = "rbdlab.goto_annotation"
    bl_label = "Go to Anotation Paint"
    bl_description = "To paint where your object will have the most detail with annotation tool"
    bl_options = {'REGISTER', 'UNDO'}


    def run_tool_set_by_id(self, context: Context, wm, target: str) -> None:
        """ Ejecuta una herramienta por ID en el área VIEW_3D """

        def callback(context) -> None:
            area = context.area  # Accedemos al área desde el contexto
            bpy.ops.wm.tool_set_by_id(name=target)
            area.tag_redraw()
        context_override(context=context, area_type='VIEW_3D', callback=callback)


    def execute(self, context):

        rbdlab = get_common_vars(context, get_rbdlab=True)

        wm = context.window_manager
        workspace = context.workspace

        if "Annotations" not in bpy.data.grease_pencils:
            bpy.ops.gpencil.annotation_add()
            annotations = bpy.data.grease_pencils.get("Annotations") 
            layers = annotations.layers
            default_layer = layers.get('Note') 
            if default_layer:
                layers.remove(default_layer)
                # bpy.ops.gpencil.layer_annotation_remove()

        annotations = bpy.data.grease_pencils.get("Annotations") 
        layers = annotations.layers

        if annotations:
            annotation_layer = layers.get(RBDLabNaming.ANNOTATION_LAYER) 


            # Si no existe mi annotation layer la creo:
            if not annotation_layer:
                bpy.ops.gpencil.layer_annotation_add()
                my_layer = layers.active
                my_layer.info = RBDLabNaming.ANNOTATION_LAYER

        layers = annotations.layers

        if not rbdlab.in_annotation_mode:

            rbdlab.in_annotation_mode = True
            las_active_tool = workspace.tools.from_space_view3d_mode(context.mode, create=False).idname
            if las_active_tool:
                rbdlab.las_active_tool = las_active_tool

            self.run_tool_set_by_id(context, wm, "builtin.annotate")

            context.scene.tool_settings.annotation_stroke_placement_view3d = 'SURFACE'

            # pongo todos los objetos seleccionados en solid mode
            [setattr(ob, "display_type", 'TEXTURED') for ob in context.selected_objects]
                
        else:
            
            rbdlab.in_annotation_mode = False

            self.run_tool_set_by_id(context, wm, rbdlab.las_active_tool)

            if len(layers) > 0:
            
                items = list(rbdlab.rbdlab_cf_source)
                if 'PENCIL' not in items:
                    items.append('PENCIL')
                rbdlab.rbdlab_cf_source = set(items)
            
            else:
            
                items = list(rbdlab.rbdlab_cf_source)
                if 'PENCIL' in items:
                    items.remove('PENCIL')
                rbdlab.rbdlab_cf_source = set(items)

        return {'FINISHED'}
