
from bpy.types import PropertyGroup, Object, Collection
from bpy.props import PointerProperty, StringProperty


# Clase para almacenar objetos:
class StoredObjects(PropertyGroup):
    ob: PointerProperty(type=Object)

    @property
    def get_ob(self):
        return self.ob
    
# Clase para almacenar collections:
class StoredCollections(PropertyGroup):
    collection: PointerProperty(type=Collection)

    @property
    def get_collection(self):
        return self.collection

# Clase para almacenar una cadena de texto
class SoredStrings(PropertyGroup):
    string: StringProperty(name="Name")
