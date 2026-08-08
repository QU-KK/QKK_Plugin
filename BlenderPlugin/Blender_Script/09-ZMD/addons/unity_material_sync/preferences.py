try:
    import bpy
except ImportError:
    bpy = None

try:
    from . import unity_client
except ImportError:
    unity_client = None

try:
    from . import documentation
except ImportError:
    documentation = None

DEFAULT_ENDPOINT = (
    unity_client.DEFAULT_NATS_URL
    if unity_client
    else "nats://127.0.0.1:14222"
)


if bpy is not None:
    class UnityMaterialSyncPreferences(bpy.types.AddonPreferences):
        bl_idname = __package__

        endpoint: bpy.props.StringProperty(
            name="通信地址",
            description="本地 NATS 服务地址",
            default=DEFAULT_ENDPOINT,
        )
        timeout: bpy.props.FloatProperty(
            name="超时时间",
            description="请求 Unity 材质数据时的超时时间（秒）",
            default=5.0,
            min=0.1,
        )

        def draw(self, context):
            layout = self.layout
            endpoint_row = layout.row()
            endpoint_row.enabled = False
            endpoint_row.prop(self, "endpoint")
            layout.prop(self, "timeout")
            if documentation and documentation.WM_OT_open_unity_material_sync_docs:
                layout.operator(
                    documentation.WM_OT_open_unity_material_sync_docs.bl_idname,
                    text="打开文档",
                    icon="HELP",
                )
else:
    UnityMaterialSyncPreferences = None


classes = tuple(
    cls for cls in (UnityMaterialSyncPreferences,)
    if cls is not None
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
