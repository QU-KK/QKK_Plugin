import bpy
from bpy.types import PropertyGroup
from bpy.props import IntProperty, BoolProperty, FloatProperty, EnumProperty
from ..Global.basics import select_object, set_active_object, deselect_all_objects


# Quick Rigidbodies properties.


class RBDLab_PG_motion(PropertyGroup):

    offset_amount: IntProperty(
        default=1,
        min=0
    )
    # RBD Settings:

    @staticmethod
    def get_coll(context):
        obj_active = context.active_object
        coll_name = None

        if "rbdlab_motion_collection_id" in obj_active:
            for coll in bpy.data.collections:
                if "rbdlab_motion_collection_id" in coll:
                    if obj_active["rbdlab_motion_collection_id"] == coll["rbdlab_motion_collection_id"]:
                        coll_name = coll.name
        if coll_name:
            return bpy.data.collections[coll_name]
        else:
            print("No match collection for " + obj_active.name)
            return None

    def mass_update(self, context):
        collection = self.get_coll(context)
        if collection:
            for obj in collection.objects:
                if obj.type == 'MESH':
                    obj.rigid_body.mass = self.mass

    mass: FloatProperty(
        default=1,
        unit='MASS',
        update=mass_update
    )

    def collision_shape_update(self, context):
        collection = self.get_coll(context)
        if collection:
            for obj in collection.objects:
                if obj.type == 'MESH':
                    obj.rigid_body.collision_shape = self.collision_shape

    # Motion > Particles to Rigidbodies:
    collision_shape: EnumProperty(
        name="Shape",
        items=(
            ('BOX',         "Box",          "", 'MESH_CUBE', 0),
            ('SPHERE',      "Sphere",       "", 'MESH_UVSPHERE', 1),
            ('CAPSULE',     "Capsule",      "", 'MESH_CAPSULE', 2),
            ('CYLINDER',    "Cylinder",     "", 'MESH_CYLINDER', 3),
            # ('CONE',        "Cone",         "", 'MESH_CONE', 4),
            ('CONVEX_HULL', "Convex Hull",  "", 'MESH_ICOSPHERE', 5),
            ('MESH',        "Mesh",         "", 'MESH_MONKEY', 6),
            # ('COMPOUND',    "Compound",     "", 'MESH_DATA', 7),
        ),
        default='CONVEX_HULL',
        update=collision_shape_update
    )

    def friction_update(self, context):
        collection = self.get_coll(context)
        if collection:
            for obj in collection.objects:
                if obj.type == 'MESH':
                    obj.rigid_body.friction = self.friction

    friction: FloatProperty(
        name="Friction",
        default=0.5,
        min=0,
        max=1,
        precision=3,
        update=friction_update
    )

    def restitution_update(self, context):
        collection = self.get_coll(context)
        if collection:
            for obj in collection.objects:
                if obj.type == 'MESH':
                    obj.rigid_body.restitution = self.restitution

    restitution: FloatProperty(
        name="Bounciness",
        default=0,
        min=0,
        max=1,
        precision=3,
        update=restitution_update
    )

    def use_margin_update(self, context):
        collection = self.get_coll(context)
        if collection:
            for obj in collection.objects:
                if obj.type == 'MESH':
                    obj.rigid_body.use_margin = self.use_margin

    use_margin: BoolProperty(
        name="Use margin",
        default=False,
        update=use_margin_update
    )

    def collision_margin_update(self, context):
        collection = self.get_coll(context)
        if collection:
            for obj in collection.objects:
                if obj.type == 'MESH':
                    obj.rigid_body.collision_margin = self.collision_margin

    collision_margin: FloatProperty(
        name="Collision Margin",
        default=0.04,
        min=0,
        max=1,
        subtype='DISTANCE',
        update=collision_margin_update
    )

    def encode_string(text):
        return text.replace(" ", "#").upper()

    string_items = [
        "Air",
        "Acrylic",
        "Asphalt (Crushed)",
        "Bark",
        "Beans (Cocoa)",
        "Beans (Soy)",
        "Brick (Pressed)",
        "Brick (Common)",
        "Brick (Soft)",
        "Brass",
        "Bronze",
        "Carbon (Solid)",
        "Cardboard",
        "Cast Iron",
        "Chalk (Solid)",
        "Concrete",
        "Charcoal",
        "Cork",
        "Copper",
        "Garbage",
        "Glass (Broken)",
        "Glass (Solid)",
        "Gold",
        "Granite (Broken)",
        "Granite (Solid)",
        "Gravel",
        "Ice (Crushed)",
        "Ice (Solid)",
        "Iron",
        "Lead",
        "Limestone (Broken)",
        "Limestone (Solid)",
        "Marble (Broken)",
        "Marble (Solid)",
        "Paper",
        "Peanuts (Shelled)",
        "Peanuts (Not Shelled)",
        "Plaster",
        "Plastic",
        "Polystyrene",
        "Rubber",
        "Silver",
        "Steel",
        "Stone",
        "Stone (Crushed)",
        "Timber",
    ]

    items = []
    for i, item in enumerate(string_items):
        row = (encode_string(item), item, "", i)
        items.append(row)

    def get_default_properties(self, target_prop):
        for prop in self.bl_rna.properties:
            if prop.identifier == target_prop:
                if hasattr(prop, "default"):
                    return prop.default
