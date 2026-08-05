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

""" Zen UV Relax system """

import bmesh
import bpy
from mathutils import Matrix
import numpy as np
import random
from ZenUV.prop.zuv_preferences import get_prefs
from ZenUV.utils.base_clusters.base_cluster import (
    TransformCluster,
    ProjectCluster,
)
from ZenUV.utils.base_clusters.zen_cluster import ZenCluster
# from ZenUV.utils.base_clusters.base_elements import UvVertex
# from ZenUV.utils.base_clusters.diagnostic_clusters import CheckerZcluster
from ZenUV.utils.base_clusters.stripes import UvStripes
from ZenUV.utils.transform import UvTransformUtils
from mathutils import Vector
# from ZenUV.ui.labels import ZuvLabels
from ZenUV.utils.generic import (
    resort_by_type_mesh_in_edit_mode_and_sel,
    resort_objects_by_selection,
    get_mesh_data,
    verify_uv_layer
)
from ZenUV.utils import get_uv_islands as island_util

from ZenUV.utils.clib.lib_init import get_zen_relax2_app
from ZenUV.ui.third_party_popups import draw_zensets_popup
from ZenUV.ui.pie import ZsPieFactory
from ZenUV.utils.progress import ProgressBar, ProgressCancelException
from ZenUV.ops.zen_unwrap.props import ZenUnwrapProps


LITERAL_CANCELLED_BY_USER = 'Cancelled by user'


class OriginVector:

    def __init__(self, head_uv_co: Vector, tail_uv_co: Vector) -> None:

        self.pivot_location = head_uv_co
        self.tail_location = tail_uv_co
        self.direction = self.tail_location - self.pivot_location


class rCluster():

    def __init__(self, context, obj, island):
        super().__init__(context, obj, island)

        self.init_r_cluster()

    def init_r_cluster(self):
        self.pydata = []
        self.pivot_vert_index, self.tail_vert_index = self._get_origin_points_idxs()

    def to_mesh(self, with_injection=False, with_uv=True):
        """ Testing purposes ONLY!!! """
        reindex, verts, faces = self.get_zen_pydata(for_OBJ=False, compensate=False)
        if with_injection:
            solver = UvStripes(self.get_bound_edges(), self.uv_layer)
            solver.for_obj = False
            if solver.is_cluster_holed():
                injectors = solver.get_injectors(len(self.uv_verts))
                for injector in injectors:
                    verts.append(injector[0])
                    faces.extend(injector[1])
        new_mesh = bpy.data.meshes.new('Cluster_mesh')
        new_mesh.from_pydata(verts, [], faces)
        new_mesh.update()
        new_object = bpy.data.objects.new('Cluster_object', new_mesh)
        new_collection = bpy.data.collections.new('ZenClusters')
        bpy.context.scene.collection.children.link(new_collection)
        new_collection.objects.link(new_object)

        if with_uv and self.uvs:
            bm = bmesh.new()
            bm.from_mesh(new_object.data)
            uv_layer = verify_uv_layer(bm)
            for v in bm.verts:
                for loop in v.link_loops:
                    loop[uv_layer].uv = self.uvs[v.index]
            bm.to_mesh(new_object.data)
            bm.free()

        return new_mesh

    def get_zen_pydata(self, for_OBJ=False, compensate=True, _print=False):
        faces = []
        reindex = dict()
        offset = 0
        if for_OBJ:
            offset = 1
        for face in self.uv_faces:
            face_verts = [v for v in face.uv_verts]
            face_verts_ids = [v.index + offset for v in face_verts]
            for vert in face_verts:
                reindex.update({vert.mesh_vert.index: vert.index})
            faces.append(face_verts_ids)
        verts = [v.mesh_vert.co + (Vector(np.random.rand(3, 1)) * 0.0000001) for v in self.uv_verts]

        if _print:
            print("\nZEN Pydata: --------------------------\n")
            print(f"Faces: {faces}")
            print(f"Verts: {len(verts)}\n {verts}")
            print(f"Reindex: {reindex}")

        self.pydata = [verts, [], faces]
        return reindex, verts, faces

    def zen_relax(self, props, Progress):

        addon_prefs = get_prefs()

        reindex, verts, faces = self.get_zen_pydata(for_OBJ=False, compensate=False)
        boundary = self.get_bound_edges()
        if not boundary:
            return False, "The island has no boundaries."
        solver = UvStripes(boundary, self.uv_layer)
        solver.for_obj = False
        if solver.is_cluster_holed():
            injectors = solver.get_injectors(len(self.uv_verts))
            for injector in injectors:
                verts.append(injector[0])
                faces.extend(injector[1])

        import subprocess

        s_relax_app = get_zen_relax2_app()

        e_msg = None

        try:
            i_empties = 0

            uvs = []

            with subprocess.Popen(
                    s_relax_app,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE, shell=addon_prefs.use_relax_in_shell) as proc:

                # print('Successfully started:', s_relax_app)

                i_iter_count = 20 - 1
                Progress.iterations = i_iter_count

                state = "init"
                i_step = 0

                i_step_vlist = 0
                i_step_flist = 0

                e_msg = None

                while state != "quit":
                    if state == "init":
                        state = "idle"
                        proc.stdin.write(f'vs {len(verts)}\n'.encode('utf-8'))
                        proc.stdin.flush()
                    elif state == "out.vlist":
                        state = "idle"
                        v = verts[i_step_vlist]
                        proc.stdin.write(f'v {i_step_vlist} {v[0]} {v[1]} {v[2]}\n'.encode('utf-8'))
                        proc.stdin.flush()

                        i_step_vlist += 1

                    elif state == "out.fsize":
                        state = "idle"
                        proc.stdin.write(f'fs {len(faces)}\n'.encode('utf-8'))
                        proc.stdin.flush()
                    elif state == "out.flist":
                        state = "idle"
                        it_face = ' '.join([str(nf) for nf in faces[i_step_flist]])
                        proc.stdin.write(f'f {i_step_flist} {it_face}\n'.encode('utf-8'))
                        proc.stdin.flush()
                        i_step_flist += 1
                    elif state == "out.precalc":
                        state = "idle"
                        proc.stdin.write('p\n'.encode('utf-8'))
                        proc.stdin.flush()
                    elif state == "out.step":
                        state = "idle"

                        if not Progress.update():
                            proc.stdin.write('q\n'.encode('utf-8'))
                            e_msg = LITERAL_CANCELLED_BY_USER
                        else:
                            if i_step == i_iter_count:
                                proc.stdin.write('u\n'.encode('utf-8'))
                            else:
                                proc.stdin.write('s\n'.encode('utf-8'))
                        i_step += 1
                        proc.stdin.flush()
                    elif state.startswith("_u:"):
                        uvs.append(tuple(map(float, state[3:].split(' '))))
                        state = "idle"
                    elif state.startswith("ERROR>"):
                        e_msg = state
                        state = "idle"

                    cppMessage = proc.stdout.readline()
                    state = cppMessage.decode('utf-8').strip()
                    # print("CPP -> " + state)
                    if state == '':
                        i_empties += 1

                    # Force Quit
                    if i_empties > 5:
                        print("FORCE_QUIT !!!")
                        proc.stdin.write('q\n'.encode('utf-8'))
                        proc.stdin.flush()

                    # abnormal termination
                    if i_empties > 10:
                        break

            if len(uvs):
                uvs = UvTransformUtils.fit_uvs(self.match_to_init_location(uvs), self.bbox, 'MAX')

                if props.correct_aspect and self.image_aspect != 1.0:
                    from ZenUV.utils.bounding_box import BoundingBox2d
                    p_bbox = BoundingBox2d(points=uvs)
                    if self.image_aspect > 1.0:
                        p_bbox.scale(Vector((1.0, 1.0 / self.image_aspect)))
                    else:
                        p_bbox.scale(Vector((self.image_aspect, 1.0)))

                    uvs = UvTransformUtils.fit_uvs(self.match_to_init_location(uvs), p_bbox, 'MAX', keep_proportion=False)

                for vert, uv in zip(self.uv_verts, uvs):
                    vert.set_position(Vector(uv))

                e_msg = "Done"

                return True, e_msg

        except Exception as e:
            e_msg = str(e) + ". Full path:" + s_relax_app
            raise RuntimeError(e_msg)

        # ERROR> We come here only in critical ZenRelax errors
        return False, e_msg

    def _get_origin_points_idxs(self):

        near_dict = {abs((self.bbox.center - uv_vert.uv_co).magnitude): uv_vert for uv_vert in self.uv_verts}
        origin_vert = near_dict[min(near_dict.keys())]
        origin_vert.origin = True

        angles = {}
        for edge in origin_vert.link_uv_edges:
            for axis in (Vector((1.0, 0.0)), Vector((-1.0, 0.0)), Vector((0.0, 1.0)), Vector((0.0, -1.0))):
                angles.update({axis.angle(edge.other_vert.uv_co - edge.vert.uv_co): edge.verts})

        tail_vert = [v for v in angles[min(angles.keys())] if v.index != origin_vert.index][0]

        return origin_vert.index, tail_vert.index

    def match_to_init_location(self, uvs):
        origin_vector = OriginVector(self.uv_verts[self.pivot_vert_index].uv_co, self.uv_verts[self.tail_vert_index].uv_co)
        matched_vector = OriginVector(Vector(uvs[self.pivot_vert_index]), Vector(uvs[self.tail_vert_index]))
        return self.match_uvs_by_vectors(
            uvs,
            origin_vector,
            matched_vector
        )

    def match_uvs_by_vectors(
        self,
        uvs: list,
        origin: OriginVector,
        matched: OriginVector,
        p: int = 1
    ) -> None:

        origin_pivot = origin.pivot_location
        origin_vec = origin.direction
        matched_pivot = matched.pivot_location
        matched_vec = matched.direction

        delta = origin_pivot - matched_pivot
        angle = origin_vec.angle_signed(matched_vec, 0.0)

        R = Matrix(
            (
                (np.cos(angle), np.sin(angle) / p),
                (-p * np.sin(angle), np.cos(angle)),
            )
        )
        try:
            S = Matrix.Diagonal(Vector.Fill(2, origin_vec.magnitude / matched_vec.magnitude))
        except ZeroDivisionError:
            S = Matrix.Diagonal(Vector.Fill(2, origin_vec.magnitude))

        return np.dot((np.array(uvs).reshape((-1, 2)) + delta) - origin_pivot, R @ S) + origin_pivot


class ZSTsSubCollector:
    # Switch Zen Sets to Face Sets Mode.
    # ('vert', 'edge', 'face', 'vert_u', 'edge_u', 'face_u')
    # context.scene.zen_sets_unique_mode = 'SETS'
    # 'SETS', 'PARTS'
    index = None
    obj_name = None
    isl_name = None
    assign_to_group = False
    passed = True
    mode = None
    sys_message = ""
    adapted_message = ""
    indexes = None
    color = (0.5, 0.5, 0.5)

    def random_color(self):
        r, g, b = [random.random() for i in range(3)]
        # self.color = (r, g, b)
        return (r, g, b)

    def show_data(self):
        attrs = vars(self)
        print('--> '.join("%s: %s\n" % item for item in attrs.items()))

    def set_inform_level(self, level):
        """ level from {'WARNING', 'INFO', 'ERROR','RANDOM'}
        """
        if level in self.inf_levels.keys():
            self.color = self.inf_levels[level]
        else:
            print(f"Level must be in {self.self.inf_levels.keys()}")

    def append_sys_message(self, msg):
        self.sys_message = msg
        if 'Check Edge manifold' in msg:
            msg = 'Edge manifold'
        elif 'topology' in msg:
            msg = 'Disk topology'
        elif 'Multiple Components' in msg:
            msg = 'Multiple Components'
        elif 'Multiple loops' in msg:
            msg = 'Multiple faces'
        elif 'Zero Area Faces' in msg:
            msg = 'Zero Area Faces'

        self.adapted_message = msg


class RelaxCluster(
    # BaseCluster,
    ZenCluster,
    rCluster,
    ProjectCluster,
    TransformCluster,
    ZSTsSubCollector,
):
    def __init__(self, context, obj, island, bm, uv_layer) -> None:
        super().__init__(context, obj, island, bm)
        self.name = ''
        self.uv_layer = uv_layer
        # self.init_cycles = 0
        # ZenCluster.__init__(self)
        rCluster.init_r_cluster(self)
        self.inf_levels = {
            'WARNING': (1.0, 1.0, 0.0),
            'INFO': (0.0, 0.0, 1.0),
            'ERROR': (1.0, 0.0, 0.0),
            'RANDOM': self.random_color()
        }

        from ZenUV.utils.generic import UvImage
        self.image_aspect = UvImage.get_aspect(context)


class ZUV_OT_Relax(bpy.types.Operator):
    bl_idname = "uv.zenuv_relax"
    bl_label = "Relax"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = "Relax selected islands"

    method: bpy.props.EnumProperty(
        name="Method",
        description="Unwrapping method",
        items=[("ZENRELAX", "Zen Relax", "")] + ZenUnwrapProps.UNWRAP_METHOD_ITEMS,
        default="ZENRELAX")

    select: bpy.props.BoolProperty(
        name="Select",
        description="Select relaxed Island",
        default=False)

    relax: bpy.props.BoolProperty(
        name="Relax",
        description="Relax",
        default=True,
        options={'HIDDEN'})

    show_log: bpy.props.BoolProperty(
        name="Show Log",
        description="Show Log",
        default=True,
        options={'HIDDEN'})

    correct_aspect: bpy.props.BoolProperty(
        name="Correct Aspect",
        description="Taking image aspect ratio into accaunt",
        default=True)

    relax_mode: bpy.props.StringProperty(options={'HIDDEN', 'SKIP_SAVE'})
    use_zensets: bpy.props.BoolProperty(options={'HIDDEN', 'SKIP_SAVE'})

    @classmethod
    def poll(cls, context):
        """ Validate context """
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH'

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "method")
        layout.prop(self, "select")
        row = layout.row()
        row.enabled = self.method == 'ZENRELAX'
        row.prop(self, "correct_aspect")

    def check_zen_sets(self, context, show_popup=False):

        if get_prefs().use_zensets:
            if not hasattr(bpy.types, bpy.ops.zsts.assign_to_group.idname()):
                if show_popup:
                    context.window_manager.popup_menu(draw_zensets_popup, title="Zen UV", icon='INFO')
                self.use_zensets = False
            else:
                self.use_zensets = True
        else:
            self.use_zensets = False

    def execute(self, context):

        ZsPieFactory.mark_pie_cancelled()

        self.check_zen_sets(context)
        objs = resort_by_type_mesh_in_edit_mode_and_sel(context)
        objs = resort_objects_by_selection(context, objs)
        if not objs:
            self.report({'WARNING'}, "Zen UV: Select something.")
            return {'CANCELLED'}

        if self.method == "ZENRELAX":
            self._zen_relax(context, objs)
            self.check_zen_sets(context, True)
        elif self.method in {"ANGLE_BASED", "CONFORMAL", "MINIMUM_STRETCH"}:
            self.relax_mode = self.method
            self._relax_native(context, self.select)
        else:
            return {'CANCELLED'}

        return {'FINISHED'}

    def _show_log(self, use_zensets, skip_done, results):
        islands_total = sum([len(data) for data in results.values()])
        g_errors = 0
        l_errors = 0
        info_scope = []
        insertion = "s " if islands_total != 1 else " "
        print("\nZen UV Relax log:", "-" * 25)
        print(f"Total {islands_total} Island{insertion}processed.")
        for obj_name, data in results.items():
            print(f"\n    Object: {obj_name}\n")
            for c_name, info in data.items():
                if not skip_done:
                    print(f"      {c_name} --> {info[1]}")
                else:
                    if not info[0]:
                        print(f"      {c_name} --> {info[1]}")
                if not info[0]:
                    g_errors += 1
                    l_errors += 1
                    info_scope.append(({"WARNING"}, f"{obj_name}[{c_name}] --> {info[1]}"))
                    # self.report({'WARNING'}, f"{obj_name}[{c_name}] --> {info[1]}")
                    # self.report(info_scope[-1][0], info_scope[-1][1])
            if not l_errors:
                print("    Result --> Finished.")
            else:
                print("    Result --> Errors occured.")
            l_errors = 0
        print("\n")
        if g_errors == 1:
            self.report(info_scope[-1][0], info_scope[-1][1])

        elif g_errors > 1:
            insertion = "s " if g_errors != 1 else " "
            self.report(
                {'WARNING'},
                f"Zen UV: In the process of Relaxation {g_errors} error*occurred.".replace("*", insertion) +
                " Look at the system console."
            )
            print("Some islands data inconsistent. Need to be fixed.")
            if use_zensets:
                print("Check Zen Sets Groups.\n")

        else:
            self.report({'INFO'}, f"Zen UV: Relaxation completed. {islands_total} Island{insertion}processed")

    def assign_to_ZSGroups(self, context, c):
        group = f'{c.obj_name} {c.name}-{c.adapted_message}'
        context.scene.zen_sets_active_mode = c.mode
        # Del previous Group if exist.
        if 'FINISHED' in bpy.ops.zsts.set_active_group(mode='GROUP_NAME', group=group):
            bpy.ops.zsts.del_group()
        # Assign to Group
        bpy.ops.zsts.assign_to_group(
            group_mode='INDICES',
            group_indices=tuple({'item': index, 'name': c.obj_name} for index in c.indexes),
            group_name=group, group_color=c.color)

    def convert_clusters_to_log(self, collectors):
        log = {}
        for c in collectors:
            if c.obj_name not in log:
                log.update({c.obj_name: {c.name: [c.passed, c.adapted_message]}})
            else:
                log[c.obj_name].update({c.name: [c.passed, c.adapted_message]})
        return log

    def _relax_native(self, context, _select):
        init_select_mode = context.tool_settings.mesh_select_mode[:]
        objs = list(context.objects_in_mode_unique_data)
        view_layer = context.view_layer
        active_obj = view_layer.objects.active

        bpy.ops.object.mode_set(mode='OBJECT')
        for obj in objs:
            obj.select_set(state=False)

        for obj in objs:
            view_layer.objects.active = obj
            obj.select_set(state=True)
            bpy.ops.object.mode_set(mode='EDIT')

            me = obj.data
            bm = bmesh.from_edit_mesh(me)
            uv_layer = verify_uv_layer(bm)
            sync_uv = context.scene.tool_settings.use_uv_select_sync

            init_pins = []
            init_selection = set()

            sync_mode = context.space_data.type == 'IMAGE_EDITOR' and sync_uv or context.space_data.type == 'VIEW_3D'
            loops = {loop: loop[uv_layer] for face in bm.faces for loop in face.loops if not face.hide}

            for loop, uv_loop in loops.items():
                if uv_loop.pin_uv:
                    init_pins.append(uv_loop)
                    uv_loop.pin_uv = False
                if not sync_mode and uv_loop.select:
                    init_selection.add(loop)
                if sync_mode and loop.vert.select:
                    init_selection.add(loop.vert)
                uv_loop.pin_uv = True

            bm.faces.ensure_lookup_table()

            islands = island_util.get_island(context, bm, uv_layer)

            p_loops = [loop[uv_layer] for island in islands for f in island for loop in f.loops]

            for island in islands:
                p_loops = [loop[uv_layer] for f in island for loop in f.loops]
                for i in range(len(p_loops) - 1):
                    p_loops[i].pin_uv = False

            if not sync_mode:
                for loop in p_loops:
                    loop.select = True
            else:
                for face in [f for i in islands for f in i]:
                    face.select = True

            if bpy.ops.uv.unwrap.poll():
                bpy.ops.uv.unwrap(
                    method=self.relax_mode,
                    # fill_holes=self.fill_holes,
                    # correct_aspect=self.correct_aspect,
                    # ue_subsurf_data=self.use_subsurf_data,
                    margin=0
                )

            for loop in loops.values():
                loop.pin_uv = False

            for loop in init_pins:
                loop.pin_uv = True

            # Restore Init Selection
            if not _select:
                if not sync_mode:
                    for loop, uv_loop in loops.items():
                        if loop not in init_selection:
                            uv_loop.select = False
                else:
                    context.tool_settings.mesh_select_mode = [True, False, False]
                    bmesh.select_mode = {'VERT'}
                    for v in bm.verts:
                        v.select = v in init_selection
                    bm.select_flush_mode()

            bpy.ops.object.mode_set(mode='OBJECT')
            obj.select_set(state=False)

        for obj in objs:
            obj.select_set(state=True)
        view_layer.objects.active = active_obj
        bpy.ops.object.mode_set(mode='EDIT')
        context.tool_settings.mesh_select_mode = init_select_mode

    def _zen_relax(self, context, objs):
        skip_done = True
        clusters = []
        progress = ProgressBar(context, 100, text_only=True)

        try:

            for obj in objs:
                me, bm = get_mesh_data(obj)
                uv_layer = verify_uv_layer(bm)
                islands = island_util.get_island(context, bm, uv_layer)
                for idx, island in enumerate(islands):
                    cl = RelaxCluster(context, obj, island, bm, uv_layer)
                    cl.obj_name = obj.name
                    cl.name = f"Island {idx}"
                    cl.index = idx
                    progress.set_text_relax(obj_name=cl.obj_name if len(objs) > 1 else "", cluster_name=cl.name, preposition=" of")
                    progress.current_step = 0

                    m_loops = cl.check_multiple_loops()
                    if m_loops:
                        message = "Multiple Loops"
                        cl.append_sys_message("Multiple Loops")
                        cl.indexes = m_loops
                        cl.mode = 'edge'
                        cl.passed = False
                        cl.set_inform_level('ERROR')
                        cl.assign_to_group = True

                    if cl.passed:
                        if self.relax:
                            result, message = cl.zen_relax(self, progress)
                            cl.append_sys_message(message)
                            cl.indexes = [f.index for f in cl.island]
                            cl.mode = 'face'
                            cl.passed = True
                            cl.set_inform_level('RANDOM')
                            cl.assign_to_group = False
                        else:
                            result = True
                            message = "Test Mode"

                        if not result:
                            if message == LITERAL_CANCELLED_BY_USER:
                                raise ProgressCancelException()

                            cl.append_sys_message(message)
                            cl.indexes = [f.index for f in cl.island]
                            cl.mode = 'face'
                            cl.passed = False
                            cl.set_inform_level('RANDOM')
                            cl.assign_to_group = True
                            cl.reset()
                    clusters.append(cl)

                    if self.select:
                        cl.select(context, state=True)

                bm.select_flush_mode()
                bmesh.update_edit_mesh(me)

            if self.use_zensets:
                for cl in clusters:
                    if cl.assign_to_group:
                        self.assign_to_ZSGroups(context, cl)
        except ProgressCancelException:
            pass
        except Exception as e:
            self.report({'ERROR'}, str(e))
            return
        finally:
            # this will be executed even after return !
            progress.finish()

        if self.show_log:
            self._show_log(self.use_zensets, skip_done, self.convert_clusters_to_log(clusters))


relax_classes = (
    ZUV_OT_Relax,
)


if __name__ == "__main__":
    pass
