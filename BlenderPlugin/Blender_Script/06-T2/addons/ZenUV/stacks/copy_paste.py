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

"""
    Zen UV Copy / Paste uv coordinates system
"""


import bpy
import bmesh

from mathutils import Vector
from bpy.props import BoolProperty, EnumProperty

import ast
import array

from ..utils.uv_factory import UvIslandUtils, SelectionUtils
from ..utils.loops_factory import LoopsFactory
from ..utils.iter_utils import IterUtils
from ..utils.generic import ResortObjects, verify_uv_layer
from ..stacks.utils import Cluster
from ..ui.labels import ZuvLabels
from ..utils.clib.lib_init import StackSolver
from ..utils.constants import ZUV_STORED
from ..utils.vlog import Log


class ZUV_OT_UV_Copy_Param(bpy.types.Operator):
    ''' Store selected UV island to mesh data '''
    bl_idname = "uv.zenuv_copy_param"
    bl_label = ZuvLabels.OT_COPY_PARAM_LABEL
    bl_description = ZuvLabels.OT_COPY_PARAM_DESC
    bl_options = {'REGISTER', 'UNDO'}

    st_store_mode: EnumProperty(
        name=ZuvLabels.PREF_OT_COPY_MODE_LABEL,
        description=ZuvLabels.PREF_OT_COPY_MODE_DESC,
        items=[
            (
                "ISLAND",
                ZuvLabels.PREF_OT_COPY_MODE_ISLAND_LABEL,
                ZuvLabels.PREF_OT_COPY_MODE_ISLAND_DESC
            ),
            (
                "FACES",
                ZuvLabels.PREF_OT_COPY_MODE_FACES_LABEL,
                ZuvLabels.PREF_OT_COPY_MODE_FACES_DESC
            ),
        ],
        default="ISLAND"
    )

    desc: bpy.props.StringProperty(name="Description", default=ZuvLabels.OT_COPY_PARAM_DESC, options={'HIDDEN'})

    @classmethod
    def description(cls, context, properties):
        if properties:
            return properties.desc
        else:
            return cls.bl_description

    uv_copy_dict = dict()
    objs = None

    @classmethod
    def poll(cls, context):
        """ Validate context """
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH'

    def invoke(self, context, event):
        scene = context.scene
        objs = ResortObjects.resort_by_type_mesh_in_edit_mode_and_sel(context, require_active_uv=True)

        if not objs:
            self.report({'WARNING'}, "No objects selected.")
            return {'CANCELLED'}

        self.objs = ResortObjects.resort_objects_by_selection(context, objs)
        if not self.objs:
            self.check_copy_conditions(scene)
            self.report({'WARNING'}, "No selection.")
            return {"CANCELLED"}

        return self.execute(context)

    def execute(self, context):
        scene = context.scene

        if not self.objs:
            objs = ResortObjects.resort_by_type_mesh_in_edit_mode_and_sel(context, require_active_uv=True)
            if not objs:
                self.report({'WARNING'}, "No objects selected. Or no active UV Map.")
                return {'CANCELLED'}

            self.objs = ResortObjects.resort_objects_by_selection(context, objs)
            if not self.objs:
                self.report({'WARNING'}, "No selection.")
                return {'CANCELLED'}

        for obj, bm, uv_layer in IterUtils.iter_objs_with_bmesh_uv(self.objs, context, skip_obj_if_no_uv=True):
            self.uv_copy_dict = dict()

            if self.st_store_mode == "ISLAND":
                islands_for_process = UvIslandUtils.get_selected_uv_islands(context, bm, uv_layer)
            else:
                islands_for_process = [SelectionUtils.get_faces_by_any_init_selection(context, bm, uv_layer), ]

            self.uv_copy_dict.update({obj.name: {"faces": [face.index for island in islands_for_process for face in island], "uv_layer": uv_layer.name}})
        total = sum([len(faces) for name, faces in self.uv_copy_dict.items()])
        if total:
            # store loops in scene data
            scene.zen_uv[ZUV_STORED] = self.uv_copy_dict
            self.report({"INFO"}, "Zen UV: Data stored.")
            return {"FINISHED"}
        else:
            self.check_copy_conditions(scene)
            return {"CANCELLED"}

    def check_copy_conditions(self, scene):
        if scene.zen_uv.get(ZUV_STORED, None):
            del scene.zen_uv[ZUV_STORED]
        self.report({"WARNING"}, "No selection in objects.")


class ZUV_OT_UV_Paste_Param(bpy.types.Operator):
    ''' Paste selected Island to stored position '''
    bl_idname = "uv.zenuv_paste_param"
    bl_label = ZuvLabels.OT_PASTE_PARAM_LABEL
    bl_description = ZuvLabels.OT_PASTE_PARAM_DESC
    bl_options = {'REGISTER', 'UNDO'}

    use_stack_offset: BoolProperty(
        name="Stack Offset",
        default=False,
        description="Use Stack Offset",
    )
    fit_proportional: BoolProperty(
        name="Keep Proportion",
        default=True,
        description="Preserve proportion of the island",
    )
    st_fit_mode: EnumProperty(
        name=ZuvLabels.PREF_OT_PASTE_MATCH_LABEL,
        description=ZuvLabels.PREF_OT_PASTE_MATCH_DESC,
        items=[
            (
                "tc",
                ZuvLabels.PREF_OT_PASTE_MATCH_HOR_LABEL,
                ZuvLabels.PREF_OT_PASTE_MATCH_HOR_DESC
            ),
            (
                "lc",
                ZuvLabels.PREF_OT_PASTE_MATCH_VERT_LABEL,
                ZuvLabels.PREF_OT_PASTE_MATCH_VERT_LABEL
            ),
        ],
        default="tc"
    )
    st_store_mode: EnumProperty(
        name=ZuvLabels.PREF_OT_PASTE_TYPE_LABEL,
        description=ZuvLabels.PREF_OT_PASTE_TYPE_DESC,
        items=[
            (
                "ISLAND",
                ZuvLabels.PREF_OT_PASTE_TYPE_ISLAND_LABEL,
                ZuvLabels.PREF_OT_PASTE_TYPE_ISLAND_DESC
            ),
            (
                "FACES",
                ZuvLabels.PREF_OT_PASTE_TYPE_FACES_LABEL,
                ZuvLabels.PREF_OT_PASTE_TYPE_FACES_DESC
            ),
        ],
        default="ISLAND"
    )
    MatchMode: EnumProperty(
        name=ZuvLabels.PREF_OT_PASTE_MATCH_LABEL,
        description=ZuvLabels.PREF_OT_PASTE_MATCH_DESC,
        items=[
            (
                "TD",
                ZuvLabels.PREF_OT_PASTE_MATCH_TD_LABEL,
                ZuvLabels.PREF_OT_PASTE_MATCH_TD_DESC
            ),
            (
                "FIT",
                ZuvLabels.PREF_OT_PASTE_MATCH_FIT_LABEL,
                ZuvLabels.PREF_OT_PASTE_MATCH_FIT_DESC
            ),
            (
                "NOTHING",
                ZuvLabels.PREF_OT_PASTE_MATCH_NOTHING_LABEL,
                ZuvLabels.PREF_OT_PASTE_MATCH_NOTHING_DESC
            ),
        ],
        default="TD"
    )
    silent: BoolProperty(
        default=False,
        description="Show stacking report",
        options={'HIDDEN'}
    )
    TransferMode: EnumProperty(
        name=ZuvLabels.PREF_OT_PASTE_TRANS_MODE_LABEL,
        description=ZuvLabels.PREF_OT_PASTE_TRANS_MODE_DESC,
        items=[
            (
                "STACK",
                ZuvLabels.PREF_OT_PASTE_TRANS_MODE_STACK_LABEL,
                ZuvLabels.PREF_OT_PASTE_TRANS_MODE_STACK_DESC
            ),
            (
                "TRANSFER",
                ZuvLabels.PREF_OT_PASTE_TRANS_MODE_TRANS_LABEL,
                ZuvLabels.PREF_OT_PASTE_TRANS_MODE_TRANS_DESC
            ),
        ],
        default="STACK"
    )
    AreaMatch: BoolProperty(
        name=ZuvLabels.PREF_OT_AREA_MATCH_LABEL,
        default=True,
        description=ZuvLabels.PREF_OT_AREA_MATCH_DESC,
        # options={'HIDDEN'}
    )
    move: BoolProperty(
        name=ZuvLabels.PREF_OT_PASTE_MOVE_LABEL,
        default=False,
        description=ZuvLabels.PREF_OT_PASTE_MOVE_DESC,
        # options={'HIDDEN'}
    )
    master_data = None
    master = None
    # clusters = []
    objs = None

    def invoke(self, context, event):
        self.objs = ResortObjects.resort_by_type_mesh_in_edit_mode_and_sel(context)

        if not self.objs:
            self.report({'WARNING'}, "No objects selected.")
            return {'CANCELLED'}

        self.master_data = context.scene.zen_uv.get(ZUV_STORED).to_dict()
        return self.execute(context)

    def draw(self, context):
        layout = self.layout
        # layout.prop(self, "st_store_mode")
        # layout.separator_spacer()
        main_box = layout.box()
        main_box.label(text="Main Settings:")
        row = main_box.row(align=False)
        # row.label(text="Use Stack Offset")
        row.prop(self, "st_store_mode")
        # row.prop(self, "use_stack_offset")
        main_box.prop(self, "TransferMode")
        if self.TransferMode == 'TRANSFER':
            self.AreaMatch = True
            box = layout.box()
            self.draw_prop_on_right(layout=box, props="use_stack_offset", text="Stack Offset:")
            self.draw_prop_on_right(layout=box, props="move", text='Position:')
            r = box.row(align=True)
            r.label(text="Size:")
            r.prop(self, "MatchMode", text="")

            if self.MatchMode == 'FIT':
                box = box.box()
                box.label(text="Fit Settings:")
                box.prop(self, "fit_proportional")
                if self.fit_proportional:
                    row = box.row(align=True)
                    row.prop(self, "st_fit_mode", expand=True)

        if self.TransferMode == 'STACK':
            box = layout.box()
            box.label(text="Stacking Options:")
            box.prop(self, "use_stack_offset")
            box.prop(self, "AreaMatch")

    def draw_prop_on_right(self, layout=None, props=None, text=""):
        r = layout.row(align=True)
        r1 = r.row(align=True)
        r1.label(text=text)
        r2 = r.row(align=True)
        r2.alignment = 'RIGHT'
        r2.prop(self, props, text="")

    @classmethod
    def poll(cls, context):
        """ Validate context """
        active_object = context.active_object
        return (active_object is not None
                and active_object.type == 'MESH'
                and context.mode == 'EDIT_MESH'
                and context.scene.zen_uv.get(ZUV_STORED, False)
                )

    def execute(self, context):
        if not StackSolver() and self.TransferMode == 'STACK':
            self.report(
                {'WARNING'},
                "Zen UV Library is not installed! Install Library for activate Stack mode."
            )
            self.TransferMode = 'TRANSFER'
        self.objs = ResortObjects.resort_by_type_mesh_in_edit_mode_and_sel(context)

        if not self.objs:
            self.report({'WARNING'}, "No objects selected.")
            return {'CANCELLED'}

        faces_mode = self.st_store_mode == 'FACES'

        for master_obj_name, data in self.master_data.items():
            self.master = Cluster(context, master_obj_name, data["faces"])
            self.master.set_uv_layer(data["uv_layer"])
            if not self.AreaMatch:
                self.master.sim_index = int(self.master.sim_index)

        clusters = []
        for obj, bm, uv_layer in IterUtils.iter_objs_with_bmesh_uv(self.objs, context, skip_obj_if_no_uv=False):
            if not uv_layer:
                uv_layer = verify_uv_layer(bm)
            if self.st_store_mode == "ISLAND":
                islands_for_process = UvIslandUtils.get_selected_uv_islands(context, bm, uv_layer)
            else:
                p_faces = SelectionUtils.get_faces_by_any_init_selection(context, bm, uv_layer)
                if not p_faces:
                    continue
                islands_for_process = [p_faces, ]

            if not islands_for_process:
                continue

            for island in islands_for_process:
                cluster = Cluster(context, obj, island)
                if not self.AreaMatch:
                    cluster.sim_index = int(cluster.sim_index)
                clusters.append(cluster)

        if not clusters:
            self.report({'WARNING'}, "No selection")
            return {'FINISHED'}

        for cl in clusters:
            cl.mode = faces_mode
            if not self.use_stack_offset:
                cl.offset = Vector((0.0, 0.0))
            cl.remap(
                self.master,
                transfer_params=self.TransferMode == "TRANSFER",
                match_position=self.move,
                match_mode=self.MatchMode,
                st_fit_mode=self.st_fit_mode,
                keep_proportion=self.fit_proportional
            )
            cl.update_mesh()
        context.scene.zen_uv[ZUV_STORED] = self.master_data
        # del self.master
        return {"FINISHED"}


class ZUV_OT_Copy_UV(bpy.types.Operator):
    bl_idname = "uv.zenuv_copy_uv"
    bl_label = "Copy UV from Map"
    bl_description = ZuvLabels.OT_COPY_UV_DESC
    bl_options = {'REGISTER', 'UNDO'}

    LITERAL_ZENUV_COPY = "ZENUV_COPY_UV"

    @classmethod
    def get_zenuv_copy_literal(cls, context: bpy.types.Context):
        return cls.LITERAL_ZENUV_COPY + "." + context.mode

    @classmethod
    def poll(cls, context):
        """ Validate context """
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH' and context.mode in {'EDIT_MESH'}

    def execute(self, context: bpy.types.Context):
        uv_copy_dict = dict()

        objs = context.objects_in_mode
        for obj, bm, uv_layer in IterUtils.iter_objs_with_bmesh_uv(objs, context, skip_obj_if_no_uv=True):

            p_loops = [lp.index for lp in LoopsFactory.get_loops_by_sel_mode(context, bm, uv_layer)]

            if p_loops:
                uv_copy_dict[obj.name] = {
                    "loops": [lp.index for lp in LoopsFactory.get_loops_by_sel_mode(context, bm, uv_layer)],
                    "uv_layer": uv_layer.name,
                    "data_type": None
                }

        if uv_copy_dict:
            # NOTE: we created dictionary with root node "ZENUV_COPY_UV" for faster clipboard paste detection!
            t_output = {
                ZUV_OT_Copy_UV.get_zenuv_copy_literal(context): uv_copy_dict
            }

            context.window_manager.clipboard = str(t_output)

            t_objects = list(uv_copy_dict.keys())
            n_count = len(t_objects)
            if n_count > 1:
                s_msg = f"{t_objects[0]}: {uv_copy_dict[t_objects[0]]['uv_layer']} and more {n_count - 1} object(s)"
            else:
                s_msg = f"{t_objects[0]}: {uv_copy_dict[t_objects[0]]['uv_layer']}"

            self.report({"INFO"}, f"Object: {s_msg} - UV data stored.")
            return {"FINISHED"}
        else:
            self.report({'WARNING'}, "No UV coordinates selected!")
            return {"CANCELLED"}


class ZUV_OT_Paste_UV(bpy.types.Operator):
    bl_idname = "uv.zenuv_paste_uv"
    bl_label = "Paste UV to Map"
    bl_description = ZuvLabels.OT_PASTE_UV_DESC
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def description(cls, context: bpy.types.Context, properties: bpy.types.OperatorProperties):
        # NOTE: use this fast detection that format is valid !
        s_literal = ZUV_OT_Copy_UV.get_zenuv_copy_literal(context)
        if s_literal in context.window_manager.clipboard:
            try:
                t_uv_copy_data: dict = ast.literal_eval(context.window_manager.clipboard)[s_literal]
                t_msg = ["Transfer UV coordinates:"]

                t_errors = []

                p_objs = ResortObjects.resort_by_type_mesh_in_edit_mode_and_sel(context)

                i_processed = 0

                for idx, (s_obj_name, v) in enumerate(t_uv_copy_data.items()):
                    source_layer_name = v["uv_layer"]
                    target_layer_name = "UNDEFINED"

                    p_obj: bpy.types.Object = bpy.data.objects.get(s_obj_name, None)
                    if p_obj and p_obj in p_objs:
                        me: bpy.types.Mesh = p_obj.data

                        p_source_layer = me.uv_layers.get(source_layer_name, None)
                        if p_source_layer:
                            p_target_layer = me.uv_layers.active
                            if p_target_layer:
                                target_layer_name = me.uv_layers.active.name

                                if source_layer_name == target_layer_name:
                                    t_errors.append(f"* Change active UV map in: {s_obj_name}")
                            else:
                                t_errors.append(f"* No active UV map in: {s_obj_name}")
                        else:
                            t_errors.append(f"* Source UV map not found in: {s_obj_name}")
                    else:
                        t_errors.append(f"* Object: {s_obj_name} - is not editable")

                    if idx < 3:
                        t_msg.append(f"* {s_obj_name}: {source_layer_name} -> {target_layer_name}")

                if i_processed != idx:
                    n_diff = idx - i_processed
                    t_msg.append(f"** and more {n_diff} object(s)")

                n_err_count = len(t_errors)
                if n_err_count:
                    t_msg.append("")
                    t_msg.append("Action required:")
                    if n_err_count > 3:
                        n_diff = n_err_count - 3
                        t_msg.extend(t_errors[:3])
                        t_msg.append(f"** and more {n_diff} action(s)")
                    else:
                        t_msg.extend(t_errors)

                return "\n".join(t_msg)
            except Exception as e:
                Log.error("PASTE UV:", e)

        return cls.bl_description

    @classmethod
    def poll(cls, context: bpy.types.Context):
        if context.mode in {'EDIT_MESH'}:
            # NOTE: use this fast detection that format is valid !
            s_literal = ZUV_OT_Copy_UV.get_zenuv_copy_literal(context)
            return s_literal in context.window_manager.clipboard
        return False

    def execute(self, context: bpy.types.Context):
        try:
            p_objs = ResortObjects.resort_by_type_mesh_in_edit_mode_and_sel(context)
            if not p_objs:
                raise RuntimeError("There are no selected objects!")

            s_literal = ZUV_OT_Copy_UV.get_zenuv_copy_literal(context)
            t_dict = ast.literal_eval(context.window_manager.clipboard)
            t_uv_copy_data: dict = t_dict.get(s_literal, None)
            if not t_uv_copy_data:
                raise RuntimeError("Invalid UV data clipboard format!")

            for s_obj_name, v in t_uv_copy_data.items():
                source_layer_name = v["uv_layer"]

                try:
                    p_obj: bpy.types.Object = bpy.data.objects.get(s_obj_name, None)
                    if not p_obj or p_obj not in p_objs:
                        raise RuntimeError("Object is not editable!")

                    # NOTE: if UV map was copied in Object mode then copy all loops
                    source_loops_idxs = v.get("loops", None)

                    bm = bmesh.from_edit_mesh(p_obj.data)

                    dest_layer = bm.loops.layers.uv.active
                    if not dest_layer:
                        raise RuntimeError("No active UV map!")

                    source_layer = bm.loops.layers.uv.get(source_layer_name, None)
                    if not source_layer:
                        raise RuntimeError("UV map is not found!")

                    if source_layer_name == dest_layer.name:
                        raise RuntimeError("Same destination!")

                    self.paste_uv(bm, source_layer, source_loops_idxs, dest_layer)

                    bmesh.update_edit_mesh(p_obj.data, loop_triangles=False, destructive=False)
                except Exception as e:
                    self.report({'WARNING'}, f"Can not paste UV to - {s_obj_name}: {source_layer_name} - {str(e)}")

            return {'FINISHED'}
        except Exception as e:
            Log.error("PASTE UV:", e)
            self.report({'WARNING'}, str(e))

        return {"CANCELLED"}

    def paste_uv(self, bm: bmesh.types.BMesh, source_layer, source_loops_idxs, dest_layer):
        in_loops = [loop for f in bm.faces for loop in f.loops]

        loops = [in_loops[idx] for idx in source_loops_idxs] if source_loops_idxs is not None else in_loops

        for loop in loops:
            loop[dest_layer].uv = loop[source_layer].uv


class ZUV_OT_CopyObjectUV(bpy.types.Operator):
    bl_idname = "uv.zenuv_copy_object_uv"
    bl_label = "Copy UV from Active"
    bl_description = "Copy active UV map of the active object to clipboard"
    bl_options = {'REGISTER', 'UNDO'}

    LITERAL_ZENUV_COPY = "ZENUV_COPY_UV"

    @classmethod
    def get_zenuv_copy_literal(cls, context: bpy.types.Context):
        return cls.LITERAL_ZENUV_COPY + "." + context.mode

    @classmethod
    def poll(cls, context):
        """ Validate context """
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH' and context.mode in {'OBJECT'}

    def execute(self, context: bpy.types.Context):
        uv_copy_dict = dict()

        obj = context.active_object
        if obj and obj.type == 'MESH':
            me: bpy.types.Mesh = obj.data

            if me.uv_layers.active:
                uv_copy_dict[obj.name] = {
                    "uv_layer": me.uv_layers.active.name
                }
        else:
            self.report({'WARNING'}, "Active object is not a mesh!")
            return {'CANCELLED'}

        if uv_copy_dict:
            # NOTE: we created dictionary with root node "ZENUV_COPY_UV" for faster clipboard paste detection!
            t_output = {
                ZUV_OT_CopyObjectUV.get_zenuv_copy_literal(context): uv_copy_dict
            }

            context.window_manager.clipboard = str(t_output)

            t_objects = list(uv_copy_dict.keys())
            n_count = len(t_objects)
            if n_count > 1:
                s_msg = f"{t_objects[0]}: {uv_copy_dict[t_objects[0]]['uv_layer']} and more {n_count - 1} object(s)"
            else:
                s_msg = f"{t_objects[0]}: {uv_copy_dict[t_objects[0]]['uv_layer']}"

            self.report({"INFO"}, f"Object: {s_msg} - UV data stored.")
            return {"FINISHED"}
        else:
            self.report({'WARNING'}, "No UV coordinates selected!")
            return {"CANCELLED"}


class ZUV_OT_PasteObjectUV(bpy.types.Operator):
    bl_idname = "uv.zenuv_paste_object_uv"
    bl_label = "Paste UV to Selected"
    bl_description = ZuvLabels.OT_PASTE_UV_DESC
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def description(cls, context: bpy.types.Context, properties: bpy.types.OperatorProperties):
        # NOTE: use this fast detection that format is valid !
        s_literal = ZUV_OT_CopyObjectUV.get_zenuv_copy_literal(context)
        if s_literal in context.window_manager.clipboard:
            try:
                t_uv_copy_data: dict = ast.literal_eval(context.window_manager.clipboard)[s_literal]
                t_msg = ["Transfer UV coordinates:"]

                t_errors = []

                s_obj_name = next(iter(t_uv_copy_data))
                p_obj = bpy.data.objects.get(s_obj_name, None)
                idx = 0
                i_processed = 0
                if p_obj and p_obj in context.visible_objects:
                    source_layer_name = t_uv_copy_data[s_obj_name]["uv_layer"]
                    t_msg.append(f"* {s_obj_name}: {source_layer_name}:")
                    p_objs = ResortObjects.resort_by_type_mesh_in_edit_mode_and_sel(context)
                    for obj in p_objs:
                        if idx < 3:
                            p_target_layer = obj.data.uv_layers.active
                            s_uv_layer = p_target_layer.name if p_target_layer else "NEW"
                            t_msg.append(f"* -> {obj.name}: {s_uv_layer}")
                            i_processed += 1
                        idx += 1

                if i_processed == 0:
                    t_msg.append("* -> UNDEFINED")
                    t_errors.append("* Select objects with the same topology")
                elif i_processed != idx:
                    n_diff = idx - i_processed
                    t_msg.append(f"** and more {n_diff} object(s)")

                if i_processed != idx:
                    n_diff = idx - i_processed
                    t_msg.append(f"** and more {n_diff} object(s)")

                n_err_count = len(t_errors)
                if n_err_count:
                    t_msg.append("")
                    t_msg.append("Action required:")
                    if n_err_count > 3:
                        n_diff = n_err_count - 3
                        t_msg.extend(t_errors[:3])
                        t_msg.append(f"** and more {n_diff} action(s)")
                    else:
                        t_msg.extend(t_errors)

                return "\n".join(t_msg)
            except Exception as e:
                Log.error("PASTE UV:", e)

        return cls.bl_description

    @classmethod
    def poll(cls, context: bpy.types.Context):
        if context.mode in {'OBJECT'}:
            # NOTE: use this fast detection that format is valid !
            s_literal = ZUV_OT_CopyObjectUV.get_zenuv_copy_literal(context)
            return s_literal in context.window_manager.clipboard
        return False

    def execute(self, context: bpy.types.Context):
        try:
            p_objs = ResortObjects.resort_by_type_mesh_in_edit_mode_and_sel(context)
            if not p_objs:
                raise RuntimeError("There are no selected objects!")

            s_literal = ZUV_OT_CopyObjectUV.get_zenuv_copy_literal(context)
            t_dict = ast.literal_eval(context.window_manager.clipboard)
            t_uv_copy_data: dict = t_dict.get(s_literal, None)
            if not t_uv_copy_data:
                raise RuntimeError("Invalid UV data clipboard format!")

            for s_obj_name, v in t_uv_copy_data.items():
                source_layer_name = v["uv_layer"]

                p_obj: bpy.types.Object = bpy.data.objects.get(s_obj_name, None)
                if p_obj:
                    try:
                        p_obj: bpy.types.Object = bpy.data.objects.get(s_obj_name, None)
                        if not p_obj:
                            raise RuntimeError("Object is not available!")

                        me: bpy.types.Mesh = p_obj.data
                        nbr_loops = len(me.loops)
                        uv_array = array.array("f", [0.0] * 2) * nbr_loops

                        source_layer: bpy.types.MeshUVLoopLayer = me.uv_layers.get(source_layer_name, None)
                        if not source_layer:
                            raise RuntimeError("UV map is not found!")

                        source_layer.data.foreach_get("uv", uv_array)

                        for obj_other in p_objs:
                            me_other: bpy.types.Mesh = obj_other.data
                            if len(me_other.loops) != nbr_loops:
                                self.report(
                                    {'WARNING'},
                                    f"Object: {obj_other.name} has: {len(me.loops)} loops (for: {len(me.polygons)} faces), expected: {nbr_loops}")
                            else:
                                uv_other = me_other.uv_layers.active
                                if not uv_other:
                                    uv_other = me_other.uv_layers.new()

                                if uv_other:
                                    uv_other.data.foreach_set("uv", uv_array)
                                    me_other.update()

                    except Exception as e:
                        self.report({'WARNING'}, f"Can not paste UV to - {s_obj_name}: {source_layer_name} - {str(e)}")
                    break

            return {'FINISHED'}
        except Exception as e:
            Log.error("PASTE UV:", e)
            self.report({'WARNING'}, str(e))

        return {"CANCELLED"}
