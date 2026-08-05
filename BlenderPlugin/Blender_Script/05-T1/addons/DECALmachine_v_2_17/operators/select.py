import bpy
from bpy.props import BoolProperty, EnumProperty
from .. items import select_mode_items

class Select(bpy.types.Operator):
    bl_idname = "machin3.select_decals"
    bl_label = "MACHIN3: Select Decals"
    bl_description = "Select Decals"
    bl_options = {'REGISTER', 'UNDO'}

    select_by_uuid: BoolProperty(name="Select by UUID", default=False)
    select_mode: EnumProperty(name='Select Mode', items=select_mode_items, default='COMMONPARENT')
    select_simple: BoolProperty(name="Select Simple Decals", default=True)
    select_subset: BoolProperty(name="Select Subset Decals", default=True)
    select_panel: BoolProperty(name="Select Panel Decals", default=True)
    select_info: BoolProperty(name="Select Info Decals", default=True)
    keep_parents_selected: BoolProperty(name="Keep Decal Parents Selected", default=False)
    def draw(self, context):
        layout = self.layout
        column = layout.column(align=True)

        if self.select_by_uuid:
            row = column.row()
            row.prop(self, "select_mode", expand=True)

        else:
            row = column.row(align=True)
            row.prop(self, 'select_simple', text="Simple", toggle=True)
            row.prop(self, 'select_subset', text="Subset", toggle=True)
            row.prop(self, 'select_panel', text="Panel", toggle=True)
            row.prop(self, 'select_info', text="Info", toggle=True)

            column.prop(self, "keep_parents_selected", toggle=True)

    @classmethod
    def poll(cls, context):
        return context.selected_objects

    def execute(self, context):
        sel = context.selected_objects

        if all(obj.DM.isdecal for obj in sel):
            self.select_by_uuid = True

            sel_decals = [obj for obj in sel if obj.DM.isdecal]
            all_decals = [obj for obj in context.visible_objects]

            decaluuids = {obj.DM.uuid for obj in sel_decals}

            if self.select_mode == 'ALL':
                for obj in all_decals:
                    if obj.DM.uuid in decaluuids:
                        obj.select_set(True)

            elif self.select_mode == 'COMMONPARENT':
                parents = {obj.parent for obj in sel_decals if obj.parent}

                for obj in all_decals:
                    if obj.DM.uuid in decaluuids and obj.parent in parents:
                        obj.select_set(True)

        else:
            self.select_by_uuid = False

            decals = [obj for obj in context.visible_objects if obj.DM.isdecal and obj.parent in sel]

            if decals:
                if not self.keep_parents_selected:
                    for obj in sel:
                        obj.select_set(False)

                if not any([self.select_simple, self.select_subset, self.select_panel, self.select_info]):
                    self.select_simple = True
                    self.select_subset = True
                    self.select_panel = True
                    self.select_info = True

                for decal in decals:
                    if decal.DM.decaltype == 'SIMPLE' and self.select_simple:
                        decal.select_set(True)

                    elif decal.DM.decaltype == 'SUBSET' and self.select_subset:
                        decal.select_set(True)

                    elif decal.DM.decaltype == 'PANEL' and self.select_panel:
                        decal.select_set(True)

                    elif decal.DM.decaltype == 'INFO' and self.select_info:
                        decal.select_set(True)

                context.view_layer.objects.active = decals[0]
        return {'FINISHED'}



#   lsy