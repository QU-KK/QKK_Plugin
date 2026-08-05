import bpy

from .trimsheet_utils import ZuvTrimsheetUtils

from ZenUV.utils.blender_zen_utils import setnameex
from ZenUV.ui.ui_call import popup_areas


TRIM_TAGS_LITERALS = {
    "USER": (
        'Wall', 'Wood', 'Concrete', 'Bricks'
    ),
    "HOTSPOT": (
        'Radial',
    ),
}


class TrimTagTemplates:
    def update_tags_categories(self, context: bpy.types.Context):
        self.category = self.tags_categories
        t_cat = TRIM_TAGS_LITERALS.get(self.category, None)
        if t_cat is not None:
            if self.value not in t_cat:
                self.value = t_cat[0]
        context.area.tag_redraw()

    tags_categories = bpy.props.EnumProperty(
        name='Tags Categories',
        description='Tags template categories',
        items=[(k, k, '') for k in TRIM_TAGS_LITERALS.keys()],
        options={'HIDDEN', 'SKIP_SAVE'},
        update=update_tags_categories
    )

    def get_tags_values_items(self, context):
        t_cat = TRIM_TAGS_LITERALS.get(self.tags_categories, None)
        if t_cat:
            return [(item, item, '') for item in t_cat]
        return []

    def update_tags_values(self, context: bpy.types.Context):
        self.value = self.tags_values
        context.area.tag_redraw()

    tags_values = bpy.props.EnumProperty(
        name='Tags Values',
        description='Tags template values',
        items=get_tags_values_items,
        options={'HIDDEN', 'SKIP_SAVE'},
        update=update_tags_values
    )


class ZuvTrimTag(bpy.types.PropertyGroup):
    category: bpy.props.StringProperty(
        name='Tag Category',
        default=''
    )

    value: bpy.props.StringProperty(
        name='Tag Value',
        default=''
    )

    name_ex: bpy.props.StringProperty(
        name='Name',
        description='Tag name',
        get=lambda self: getattr(self, 'name', ''),
        set=setnameex,
        options={'HIDDEN', 'SKIP_SAVE'}
    )

    tags_categories: TrimTagTemplates.tags_categories

    tags_values: TrimTagTemplates.tags_values


class ZUV_UL_TrimTagsList(bpy.types.UIList):
    ''' Zen Trimsheet Groups UIList '''
    def draw_item(self, context, layout: bpy.types.UILayout, data, item, icon, active_data, active_propname, index):
        ''' @Draw Trimsheet Groups UIList '''
        act_idx = getattr(active_data, active_propname)
        b_active = index == act_idx

        b_emboss = (context.area.as_pointer() in popup_areas) and b_active

        row = layout.row()
        row.prop(item, 'name', text='', emboss=b_emboss)
        row.prop(item, 'category', text='', emboss=True)
        row.prop(item, 'value', text='', emboss=True)


class ZUV_OT_TrimTagAddItem(bpy.types.Operator):
    bl_idname = "uv.zuv_trim_tag_add"
    bl_label = 'Add Tag to Trim'
    bl_description = 'Add tag to the active trim'
    bl_options = {'REGISTER', 'UNDO'}

    category: bpy.props.StringProperty(
        name='Tag Category',
        description='Adds category to the new tag',
        default='USER'
    )

    value: bpy.props.StringProperty(
        name='Tag Value',
        description='Adds value to the new tag',
        default=''
    )

    tags_categories: TrimTagTemplates.tags_categories

    tags_values: TrimTagTemplates.tags_values

    @classmethod
    def poll(self, context: bpy.types.Context):
        return ZuvTrimsheetUtils.isTrimsheetEditable(context)

    def draw(self, context: bpy.types.Context):
        layout = self.layout
        layout.use_property_split = True

        row = layout.row(align=True)
        row.prop(self, 'category')
        r = row.row(align=True)
        r.scale_x = 0.75
        r.prop(self, 'tags_categories', icon='NONE', text='', icon_only=True)

        row = layout.row(align=True)
        row.prop(self, 'value')
        r = row.row(align=True)
        r.scale_x = 0.75
        r.prop(self, 'tags_values', icon='NONE', text='', icon_only=True)

    def execute(self, context: bpy.types.Context):
        p_trim = ZuvTrimsheetUtils.getActiveTrim(context)
        if p_trim is not None:
            p_trim.tags.add()
            n_count = len(p_trim.tags)
            p_trim.tags[-1].name_ex = 'Tag'
            p_trim.tags[-1].category = self.category
            p_trim.tags[-1].value = self.value
            p_trim.tags_index = n_count - 1

            ZuvTrimsheetUtils.fix_undo()
            ZuvTrimsheetUtils.update_imageeditor_in_all_screens()

            return {'FINISHED'}
        else:
            return {'CANCELLED'}


class ZUV_OT_TrimTagRemoveItem(bpy.types.Operator):
    bl_idname = "uv.zuv_trim_tag_remove"
    bl_label = 'Remove Tag'
    bl_description = 'Removes tag from the active trim'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(self, context: bpy.types.Context):
        return (
            ZuvTrimsheetUtils.isTrimsheetEditable(context) and
            ZuvTrimsheetUtils.getActiveTrim(context) is not None)

    def execute(self, context: bpy.types.Context):
        p_trim = ZuvTrimsheetUtils.getActiveTrim(context)
        if p_trim is not None:
            n_count = len(p_trim.tags)
            idx = p_trim.tag_index
            if idx in range(0, n_count):
                p_trim.tags.remove(idx)
                p_trim.tag_index = n_count - 2

                ZuvTrimsheetUtils.fix_undo()
                ZuvTrimsheetUtils.update_imageeditor_in_all_screens()

                return {'FINISHED'}

        return {'CANCELLED'}


class ZUV_OT_TrimTagDeleteAll(bpy.types.Operator):
    bl_idname = "uv.zuv_trim_tag_delete_all"
    bl_label = 'Delete All Tags'
    bl_description = 'Delete all tags of the active trim'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(self, context: bpy.types.Context):
        return (
            ZuvTrimsheetUtils.isTrimsheetEditable(context) and
            ZuvTrimsheetUtils.getActiveTrim(context) is not None)

    def execute(self, context: bpy.types.Context):
        p_trim = ZuvTrimsheetUtils.getActiveTrim(context)
        if p_trim is not None:
            p_tags = p_trim.tags
            n_count = len(p_tags)
            if n_count > 0:
                p_tags.clear()

                p_trim.tag_index = -1

                ZuvTrimsheetUtils.fix_undo()
                ZuvTrimsheetUtils.update_imageeditor_in_all_screens()

                return {'FINISHED'}

        return {'CANCELLED'}


class ZUV_OT_TrimTagMoveItem(bpy.types.Operator):
    bl_idname = "uv.zuv_trim_tag_move"
    bl_label = 'Move Up|Down'
    bl_description = 'Move tag up | down in the trim tags'
    bl_options = {'REGISTER', 'UNDO'}

    direction: bpy.props.EnumProperty(
        items=(
            ('NONE', 'None', ""),
            ('UP', 'Up', ""),
            ('DOWN', 'Down', "")
        ),
        options={'HIDDEN', 'SKIP_SAVE'},
        default='NONE'
    )

    @classmethod
    def poll(cls, context: bpy.types.Context):
        if ZuvTrimsheetUtils.isTrimsheetEditable(context):
            p_trim = ZuvTrimsheetUtils.getActiveTrim(context)
            if p_trim:
                if len(p_trim.tags) > 1:
                    return True
        return False

    def move_index(self, context):
        """ Move index of an item render queue while clamping it. """
        p_data = ZuvTrimsheetUtils.getActiveTrim(context)
        if p_data is not None:
            index = p_data.tag_index
            list_length = len(p_data.tags) - 1
            # (index starts at 0)
            new_index = index + (-1 if self.direction == 'UP' else 1)
            i_new_index = max(0, min(new_index, list_length))
            if i_new_index != p_data.tag_index:
                p_data.tag_index = i_new_index

    def execute(self, context):
        p_data = ZuvTrimsheetUtils.getActiveTrim(context)
        if p_data is not None:
            p_list = p_data.tags
            index = p_data.tag_index
            neighbor = index + (-1 if self.direction == 'UP' else 1)
            p_list.move(neighbor, index)
            self.move_index(context)

            ZuvTrimsheetUtils.fix_undo()

            return {'FINISHED'}

        return {'CANCELLED'}


class ZUV_MT_TrimTagMenu(bpy.types.Menu):
    bl_label = "Trim Tag Templates"

    def draw(self, context: bpy.types.Context):
        layout = self.layout
        from .trimsheet import ZuvTrimsheetGroup
        p_trim: ZuvTrimsheetGroup = ZuvTrimsheetUtils.getActiveTrim(context)
        if p_trim:
            p_tag = p_trim.get_active_tag()
            if p_tag:
                grid = layout.grid_flow(columns=2, align=False)
                grid.label(text='Category')
                grid.label(text='Value')
                grid.prop(p_tag, 'tags_categories', text='')
                grid.prop(p_tag, 'tags_values', text='')
