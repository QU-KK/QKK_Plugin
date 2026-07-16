# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####

INSIDE_APP = True

try:
    import bpy
except ModuleNotFoundError:
    INSIDE_APP = False


if INSIDE_APP:
    import bpy
    import bmesh
    import blf
    from bpy_extras.io_utils import ImportHelper, ExportHelper
    from bl_ui.utils import PresetPanel

    from bpy.app.handlers import persistent as persistent_handler

    from bpy.props import (
        IntProperty,
        FloatProperty,
        BoolProperty,
        StringProperty,
        EnumProperty,
        CollectionProperty,
        PointerProperty,
        FloatVectorProperty
    )

    from bpy.types import (
        PropertyGroup,
        Operator,
        Menu,
        SpaceImageEditor,
        UIList,
        Panel,
        AddonPreferences,
        Window
    )


    class VertexColorLayerBlend32:

        def __init__(self, obj, bm):
            active_color = obj.data.color_attributes.active_color

            if not active_color:
                raise AttributeError()

            domain = 'loops' if active_color.domain == 'CORNER' else 'verts'
            data_type = 'float_color' if active_color.data_type == 'FLOAT_COLOR' else 'color'

            self.color_layer = getattr(getattr(bm, domain).layers, data_type).get(active_color.name)
            self.domain = domain
            self.data_type = data_type

        def get_color(self, face):
            color = tuple(getattr(face, self.domain)[0][self.color_layer][0:3])

            if self.data_type == 'float_color':
                color = tuple(round(255 * c) / 255.0 for c in color)

            return color


    class VertexColorLayerBlend28:

        def __init__(self, bm):
            self.color_layer = bm.loops.layers.color.active

            if not self.color_layer:
                raise AttributeError()

        def get_color(self, face):
            return tuple(face.loops[0][self.color_layer][0:3])
        

    class MeshWrapper:

        @staticmethod
        def get_topo_analysis_config(context):
            from .spipeline.engine.types import TopoAnalysisConfig

            scene_props = get_scene_props(context)
            if AppInterface.HIGHPREC_TOPO_ANALYSIS_SUPPORTED and scene_props.highprec_topo_analysis:
                return TopoAnalysisConfig(uv_coord_prec=None, uv_connect_limit=0.0001)
            
            return TopoAnalysisConfig(uv_coord_prec=5, uv_connect_limit=None)

        @staticmethod
        def obj_is_mesh(obj):
            return obj.type == 'MESH'
        
        @staticmethod
        def objs_equal(obj1, obj2):
            return obj1.data == obj2.data

        @staticmethod
        def get_vcolor(iparam_info, vcolor_layer, face):
            return iparam_info.post_get_convert(face[vcolor_layer])

        @staticmethod
        def set_vcolor(iparam_info, vcolor_layer, face, value):
            face[vcolor_layer] = iparam_info.pre_set_convert(value)

        @staticmethod
        def update_meshes(p_context):
            for p_obj in p_context.p_objects:
                p_obj.mw.update_mesh()

        def refresh_bmesh(self, force=False):
            if force:
                refresh_required = True
            else:
                try:
                    refresh_required = not self.bm.is_valid
                except:
                    refresh_required = True

            if not refresh_required:
                return False

            self.bm = bmesh.from_edit_mesh(self.p_obj.obj.data)

            from .pack_context import PackContext
            if PackContext.NEW_SELECT_API and self.uv_select_sync():
                self.bm.uv_select_sync_from_mesh()

            self.bm.verts.ensure_lookup_table()
            self.bm.faces.ensure_lookup_table()

            return True

        def __init__(self, p_obj):
            self.p_obj = p_obj
            self.refresh_bmesh(force=True)

        def get_vertex_color_layer(self):
            try:
                if AppInterface.APP_VERSION >= (3,2):
                    return VertexColorLayerBlend32(obj=self.p_obj.obj, bm=self.bm)
                
                return VertexColorLayerBlend28(bm=self.bm)
            
            except AttributeError:
                return None

        def get_uv_layer(self):
            return self.bm.loops.layers.uv.verify()
        
        def update_mesh(self):
            from .pack_context import PackContext
            if PackContext.NEW_SELECT_API and self.uv_select_sync():
                self.bm.uv_select_sync_to_mesh()
                
            bmesh.update_edit_mesh(self.p_obj.obj.data)

        def loop_vertex_index(self, loop):
            return loop.vert.index

        def pre_uv_self_modification(self):
            pass

        def loop_uv_is_self_modified(self, loop):
            return False
        
        def get_or_create_vcolor_layer(self, iparam_info):
            vcolor_chname = iparam_info.get_vcolor_chname()
            default_value = iparam_info.default_value

            from .pack_context import IPARAM_TYPE_METADATA

            layer_container = getattr(self.bm.faces.layers, IPARAM_TYPE_METADATA[iparam_info.PARAM_TYPE].layer_container)
            if vcolor_chname not in layer_container:
                vcolor_layer = layer_container.new(vcolor_chname)

                for face in self.bm.faces:
                    self.set_vcolor(iparam_info, vcolor_layer, face, default_value)

                self.p_obj.invalidate_faces_stored()

            else:
                vcolor_layer = layer_container[vcolor_chname]

            return vcolor_layer
        
        def uv_select_sync(self):
            return self.p_obj.p_context.context.tool_settings.use_uv_select_sync
        
        def view_to_region(self, coords):
            return self.p_obj.p_context.context.region.view2d.view_to_region(coords[0], coords[1])
        
        @property
        def faces(self):
            return self.bm.faces
        
        @property
        def verts(self):
            return self.bm.verts
        

    class ContextWrapper:

        def __init__(self, context):
            self.context = context

        def get_edit_objects(self):
            return [obj for obj in self.context.scene.objects if obj.mode == 'EDIT' and obj.visible_get()]


    class UVPM4_OT_SaveBlenderPreferences(Operator):

        bl_label = 'Save Blender Preferences'
        bl_idname = 'uvpackmaster4.save_blender_preferences'
        bl_description = 'Save Blender preferences. Note it will save all Blender preferences, not only UVPackmaster-related'


        def execute(self, context):
            bpy.ops.wm.save_userpref()
            self.report({'INFO'}, 'Preferences saved')
            return {'FINISHED'}


    from .spipeline.engine.props import AppStateBase

    class AppState(AppStateBase):

        @staticmethod
        def get_active_image_size(context):
            img = None
            for area in context.screen.areas:
                if area.type == 'IMAGE_EDITOR':
                    img = area.spaces.active.image

            if img is None:
                return (-1, -1)
                # raise RuntimeError("Non-Square Packing: active texture required for the operation")

            if img.size[0] == 0 or img.size[1] == 0:
                return (-1, -1)
                # raise RuntimeError("Non-Square Packing: active texture has invalid dimensions")

            return (img.size[0], img.size[1])

        def __init__(self, context):
            self.scale_length = context.scene.unit_settings.scale_length
            self.editor_tile_grid = context.space_data.uv_editor.tile_grid_shape
            self.active_image_size = self.get_active_image_size(context)


    class AppInterface:

        APP_ID = 'blender'
        APP_NAME = 'Blender'
        APP_VERSION = bpy.app.version

        REGISTER_AUTO_REPACK = True
        HIGHPREC_TOPO_ANALYSIS_SUPPORTED = True

        TEXEL_DENSITY_UNIT = 'px/m'
        TEXEL_DENSITY_UNIT_SHORT = 'p/m'
        TEXEL_DENSITY_UNIT_DESC = 'pixels per meter'

        CONTEXT_STRING_SET_VERSION = (4, 2)
        ISOLATED_ENGINE_PATH = None

        additional_classes = [UVPM4_OT_SaveBlenderPreferences]
        registered_classes = []

        @classmethod
        def register(cls, classes, scripted_operators_classes):
            cls.registered_classes = list(scripted_operators_classes)
            cls.registered_classes += classes
            cls.registered_classes += cls.additional_classes

            for c in cls.registered_classes:
                bpy.utils.register_class(c)

            from .prefs import UVPM4_SceneProps
            bpy.types.Scene.uvpm4_props = PointerProperty(type=UVPM4_SceneProps)

            if cls.REGISTER_AUTO_REPACK:
                from .repack.props import UVPM4_ObjectProps
                bpy.types.Object.uvpm4_props = PointerProperty(type=UVPM4_ObjectProps)

                from .repack.props import UVPM4_MeshProps
                bpy.types.Mesh.uvpm4_props = PointerProperty(type=UVPM4_MeshProps)
            
        @classmethod
        def unregister(cls):
            for c in reversed(cls.registered_classes):
                bpy.utils.unregister_class(c)

            cls.registered_classes = []

            del bpy.types.Scene.uvpm4_props

            if cls.REGISTER_AUTO_REPACK:
                del bpy.types.Object.uvpm4_props
                del bpy.types.Mesh.uvpm4_props

        @staticmethod
        def object_property_data(obj):
            if hasattr(obj, 'bl_rna'):
                return obj.bl_rna.properties
            
            return obj._pg_cls.bl_rna.properties
        
        @staticmethod
        def up_axis():
            from .spipeline.engine.types import UvpmAxis
            return UvpmAxis.Z
        
        @staticmethod
        def save_preferences_operator():
            return UVPM4_OT_SaveBlenderPreferences
        
        @classmethod
        def auto_repack_not_supported_msg(cls, context):
            if cls.APP_VERSION < cls.CONTEXT_STRING_SET_VERSION:
                from .utils import version_to_str
                return 'Requires Blender {} or later'.format(version_to_str(cls.CONTEXT_STRING_SET_VERSION))
            
            from .repack.cluster import RepackClusterAccess
            try:
                RepackClusterAccess(context, ui_drawing=True)

            except AssertionError:
                return 'Restart Blender once to enable the feature'
            
            return None

        @staticmethod
        def debug():
            return bpy.app.debug
        
        @staticmethod
        def debug_value():
            return bpy.app.debug_value
        
        @staticmethod
        def exec_operator(op_idname, **attrs):
            id_split = op_idname.split('.')

            op_callable = bpy.ops
            for s in id_split:
                op_callable = getattr(op_callable, s)

            op_callable(**attrs)


    def addon_preferences(cls):
        return type(cls.__name__, (AddonPreferences,) + cls.__bases__, dict(cls.__dict__))

    def get_prefs():
        return bpy.context.preferences.addons[__package__].preferences

    def get_scene_props(context):
        return context.scene.uvpm4_props

    def get_main_props(context, main_props_uuid=None):
        scene_props = get_scene_props(context)
        if not scene_props.main_prop_sets_enable:
            return scene_props.default_main_props

        access_desc = None
        if main_props_uuid is not None:
            from .id_collection import UVPM4_IdCollectionAccessDescriptor
            access_desc = UVPM4_IdCollectionAccessDescriptor.SA(active_item_uuid=main_props_uuid)

        from .id_collection.main_props import MainPropSetAccess
        return MainPropSetAccess(context, desc=access_desc).get_active_item_safe()
        
    def append_load_post_handler(handler):
        bpy.app.handlers.load_post.append(handler)

    def app_texts():
        return bpy.data.texts
