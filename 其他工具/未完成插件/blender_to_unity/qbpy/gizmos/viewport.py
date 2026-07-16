import bpy
import gpu
from bpy.types import GizmoGroup, Gizmo
from mathutils import Matrix, Vector

# from ... qbpy.gizmo import Gizmo


class CP_GT_custom_shape(Gizmo):
    bl_idname = "CP_GT_custom_shape"

    __slots__ = (
        "custom_shape",
        "init_mouse_y",
        "init_value",
    )

    def setup(self):
        custom_shape_verts = (
            (0, 0),
            (1, 0),
            (1, 1),
            (0, 0),
            (0, 1),
            (1, 1),
        )
        if not hasattr(self, "custom_shape"):
            self.custom_shape = self.new_custom_shape("TRIS", custom_shape_verts)

    def draw(self, context):
        self.draw_custom_shape(self.custom_shape)

    def draw_select(self, context, select_id):
        self.draw_custom_shape(self.custom_shape, select_id=select_id)

    # def test_select(self, context, location=[100, 100]):
    #     custom_shape_verts = (
    #         (0, 0), (1, 0), (1, 1),
    #         (0, 0), (0, 1), (1, 1),
    #     )
    #     if not hasattr(self, 'custom_shape'):
    #         self.custom_shape = self.new_custom_shape('TRIS', custom_shape_verts)
    #         self.draw_custom_shape(self.custom_shape, select_id=0)


class CP_GG_viewport(GizmoGroup):
    bl_label = "Viewport Gizmo"
    bl_idname = "CP_GG_viewport"
    bl_space_type = "VIEW_3D"
    bl_region_type = "WINDOW"
    bl_options = {"3D", "PERSISTENT"}

    def setup(self, context):
        gizmo = self.gizmos.new("CP_GT_custom_shape")

        gizmo.color = 0, 0, 0
        gizmo.alpha = 0.5

        gizmo.color_highlight = 0.5, 0.5, 0.5
        gizmo.alpha_highlight = 0.5

        # gizmo.scale_basis = 140

    # def setup(self, context):
    #     self.gizmo_actions = []
    #     self.gizmo_2d('screen.screen_full_area', 'FULLSCREEN_EXIT', 'FULLSCREEN_ENTER', context.screen, 'show_fullscreen')
    #     # self.gizmo_2d('screen.region_quadview', 'IMGDISPLAY', 'MESH_PLANE', context.space_data, 'region_quadviews')

    # def draw_prepare(self, context):
    #     region = context.region
    #     region_dimension = Vector((region.width, region.height))
    #     self.check_object_mode(context)
    #     gizmos = self.get_gizmos()
    #     position = self.gizmo_position(region_dimension)
    #     offset = 0
    #     gap = 2.2

    #     for gizmo in gizmos:
    #         gizmo.matrix_basis = Matrix.Translation(position[0] + Vector(position[1]) * offset)
    #         offset += gizmo.scale_basis * 2 + gap
    #         if not context.space_data.show_gizmo_navigate:
    #             gizmo.hide = True
