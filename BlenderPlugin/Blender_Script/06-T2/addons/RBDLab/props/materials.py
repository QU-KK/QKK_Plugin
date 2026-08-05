import os
from bpy.types import PropertyGroup, Collection, Object
from typing import List
from bpy.utils import previews
from bpy.props import EnumProperty, IntProperty, BoolProperty, PointerProperty, CollectionProperty, StringProperty

from ..addon.paths import RBDLabPreferences


class RBDLab_PG_thumbnails(PropertyGroup):

    # categories:
    def categories_update(self, context):
        valid_items = self.generate_previews(self, context)
        for item in valid_items:
            target = item[0]

            if not target:
                continue

            self.active = target
            break

    @staticmethod
    def add_item(self, context):
        addon_preferences = RBDLabPreferences.get_prefs(context)
        materials_path = addon_preferences.materials_path

        if not materials_path:
            materials_path = "/home/zebus3d/github/PolyHeavenDownloader/2k/selection/"

        cats = []
        if os.path.isdir(materials_path):

            subfolders_cats = [os.path.basename(os.path.normpath(f.path))
                               for f in os.scandir(materials_path) if f.is_dir()]
            subfolders_cats.sort()

            for i, category_str in enumerate(subfolders_cats):
                cat = []
                cat.append(category_str.upper())
                cat.append(category_str.capitalize())
                cat.append("")
                cat.append("")
                cat.append(i)
                cats.append(tuple(cat))

        return cats

    categories: EnumProperty(
        name="Categories",
        items=lambda self, context: self.add_item(self, context),
        update=categories_update
    )

    # thumbnails:

    img_preview_collection = previews.new()

    by_selection: EnumProperty(
        name="Asign to",
        items=(
            ('SELECTION',   "Selection",    "Apply to selected objects", 0),
            ('COLLECTION',  "Collection",   "Apply to Target Collection", 1),
        ),
        default='SELECTION'
    )

    inner_or_outer: EnumProperty(
        name="Work with",
        items=(
            ('OUTER',  "Outer",   "Assing materials to inner parts of chunks", 0),
            ('INNER',   "Inner",    "Assing materials to inner parts of chunks", 1),
        ),
        default='OUTER',
    )

    @staticmethod
    def generate_previews(self, context):
        addon_preferences = RBDLabPreferences.get_prefs(context)
        img_preview_collection = self.img_preview_collection

        enum_items = []
        materials_path = addon_preferences.materials_path

        if not materials_path:
            materials_path = "/home/zebus3d/github/PolyHeavenDownloader/2k/selection/"

        category = self.categories

        # se pueden crear carpetas hermanas de all para crear nuevas categorias pero en minuscula.

        base_path = os.path.join(materials_path, category.lower())

        thumbnails_paths = []
        for base_folder in os.scandir(base_path):
            # print("base_folder:", base_folder.path)
            if os.path.isdir(base_folder.path):
                for sub_folder in os.scandir(base_folder.path):
                    folder_name = os.path.basename(os.path.normpath(sub_folder.path))
                    if folder_name == "thumbnails":
                        # print(sub_folder.path)
                        if sub_folder.path not in thumbnails_paths:
                            thumbnails_paths.append(sub_folder.path)

        for i, thumb_path in enumerate(thumbnails_paths):
            if os.path.isdir(thumb_path):
                image_name = os.path.basename(os.path.normpath(thumb_path.replace(os.path.basename(thumb_path), "")))

                image = os.path.join(thumb_path, image_name + ".png")
                if os.path.isfile(image):
                    if image not in img_preview_collection:
                        thumb = img_preview_collection.load(image, image, 'IMAGE')
                    else:
                        thumb = img_preview_collection[image]

                    if thumb:
                        item = (image, image, "", thumb.icon_id, i)
                        if item not in enum_items:
                            enum_items.append(item)

        if len(enum_items) == 0:
            enum_items = [('NONE', "None", "", "", 0)]
        
        previews.remove(self.img_preview_collection)
        return enum_items

    active: EnumProperty(
        name="Thumbnails",
        items=lambda self, context: self.generate_previews(self, context),
    )


class MaterialCollListItem(PropertyGroup):
    # name: StringProperty(default="")

    def update_data(self, context):
        scn = context.scene
        rbdlab = scn.rbdlab
        # self.name = self.data.name
        print("UPDATE DATA COLLECTION", self.data.name)
        if not self.data:
            rbdlab.materials.remove_coll_list(self)

        # self.selected_name = rbdlab.materials.list[rbdlab.materials.list_index].name

    def do_remove(self, context):
        if not self.remove:
            return
        self.remove = False
        context.scene.rbdlab.materials.remove_coll_list(self)

    remove: BoolProperty(default=False, update=do_remove)
    selected: BoolProperty(default=False)
    data: PointerProperty(type=Collection, update=update_data)
    # all_names: StringProperty(default="")


class RBDLab_PG_Materials(PropertyGroup):
    ''' Materials Work-Groups.
        ++++++++++++++++++++++++++++++++++++++++ '''
    list_index: IntProperty(default=0)
    list: CollectionProperty(type=MaterialCollListItem)

    def init_coll_list(self, context):
        saved_collections = self.get_selected_work_group_collections()

        self.list.clear()
        rbdlab = context.scene.rbdlab
        if not rbdlab.root_collection:
            return
        target_collection = rbdlab.filtered_target_collection

        def add_collections(collections):
            for coll in collections:
                if 'RBDLAB' not in coll:
                    continue
                coll_list_item = self.list.add()
                coll_list_item.data = coll
                if saved_collections:
                    # Cuando hace un RELOAD.
                    # Para recuperar la seleccion anterior.
                    if coll in saved_collections:
                        coll_list_item.selected = True
                elif coll == target_collection:
                    # Cuando se inicializa por primera vez.
                    # Para al menos tener una coleccion seleccionada.
                    coll_list_item.selected = True
                add_collections(coll.children)
        add_collections(rbdlab.root_collection.children)

    def remove_coll_list(self, target_coll_list_item: MaterialCollListItem):
        coll_index = -1
        for i, coll_list_item in enumerate(self.list):
            if target_coll_list_item == coll_list_item:
                coll_index = i
                break
        if coll_index != -1:
            self.list.remove(coll_index)

    def get_selected_work_group_collections(self) -> List[Collection]:
        return [list_item.data for list_item in self.list if list_item.selected]

    def get_all_collections(self) -> List[Collection]:
        return [list_item.data for list_item in self.list]

    def get_default_properties(self, target_prop):
        for prop in self.bl_rna.properties:
            if prop.identifier == target_prop:
                if hasattr(prop, "default"):
                    return prop.default
