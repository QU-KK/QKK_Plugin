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

""" Zen UV Stack System Extra Utils """


from .utils import get_island_sim_index, distance_vec

from ZenUV.utils.vlog import Log


class StackedCluster:

    def __init__(
        self,
        context,
        uv_layer,
        object_name: str = '',
        # island_name: str = '',
        faces: list = [],
    ) -> None:

        self.object_name: str = object_name
        self.island_name: str = None
        self.faces_ids: list = [face.index for face in faces]
        self.sim_index: float = self._get_sim_index(faces, uv_layer)
        self.sim_index_no_area: int = int(self.sim_index)
        self.selected: bool = self._is_selected(context, uv_layer, faces)

    def _is_selected(self, context, uv_layer, faces):
        if context.area.type == 'IMAGE_EDITOR' and not context.scene.tool_settings.use_uv_select_sync:
            return True in [loop[uv_layer].select for face in faces for loop in face.loops if face.select]
        else:
            return True in [f.select for f in faces]

    def _get_sim_index(self, island, uv_layer):
        sim_index, _ = get_island_sim_index(island, uv_layer)
        # Log.debug(f"Detected Sim Index --> {sim_index}")
        if len(island) == 1 and len(list(island)[0].verts) == 4:
            Log.debug("Island is Quad. Use improver")
            _island = list(island)[0]
            improver = (
                distance_vec(_island.loops[0].vert.co, _island.loops[2].vert.co) +
                distance_vec(_island.loops[1].vert.co, _island.loops[3].vert.co)
            )
            sim_index += round(improver, 3)
            Log.debug(f"Sim Index was changed by Improver --> {sim_index}")
        return sim_index


class Stack:

    def __init__(self, clusters) -> None:

        self.sim_index: float = clusters[0].sim_index
        self.clusters: list = clusters
        self.count: int = len(clusters)
        self.master: StackedCluster = None

    def show_stack(self):
        for cl in self.clusters:
            print(f"\t{cl}")


class StacksStorage:

    # scope: list = []  # Temporary scope of unclassified data
    storage: list = []
    stacks: list = []
    singles: list = []

    @classmethod
    def get_legacy_data(cls):
        import pprint
        out = dict()
        for stack in cls.stacks:
            out.update({stack.sim_index: {'objs': {}}})
            objs_data = {cl.object_name: {cl.island_name: cl.faces_ids for cl in stack.clusters} for cl in stack.clusters}
            out[stack.sim_index]['objs'].update(objs_data)
            is_select = [cl.island_name for cl in stack.clusters if cl.selected]
            out[stack.sim_index].update({'select': is_select[0] if is_select else False})
            out[stack.sim_index].update({'sim_index': stack.sim_index})
            out[stack.sim_index].update({'count': stack.count})
        pprint.pprint(out, depth=4)
        return out

    @classmethod
    def clear(cls):
        cls.storage.clear()
        cls.stacks.clear()
        cls.singles.clear()

    @classmethod
    def append(cls, cluster: StackedCluster):
        prefix = "s_" if cluster.selected else ""
        cluster.island_name = f'{prefix}island_{len(cls.storage)}'
        cls.storage.append(cluster)

    @classmethod
    def show_storage(cls):
        print(f"Stacks Storage count --> {len(cls.storage)}")
        for i in cls.storage:
            print("\n", "-" * 30, 'Cluster ', i.island_name)
            print(
                f'Sim Index --> {i.sim_index}\n \
                No Area sim index --> {i.sim_index_no_area}\n \
                Object Name --> {i.object_name}\n \
                Island Name --> {i.island_name}\n \
                Faces --> {i.faces_ids}\n \
                Selected --> {i.selected}'
                )

    @classmethod
    def show_stacks(cls, is_simple: bool = False):
        print("\n", "-" * 20, "Singles")
        if len(cls.singles) == 0:
            print("There is no Singles")
        if is_simple:
            print(f'singles total: {len(cls.singles)}')
        else:
            for st in cls.singles:
                print(st)
                st.show_stack()

        print("\n", "-" * 20, "Stacks")
        if len(cls.stacks) == 0:
            print("There is no Stacks")
        if is_simple:
            stacks = [st.count for st in cls.stacks]
            print(stacks)
            print(f'total stacks: {sum(stacks)}')
        else:
            for st in cls.stacks:
                print(st)
                st.show_stack()

    @classmethod
    def classify(cls):
        sim_indexes = {i.sim_index for i in cls.storage}
        cls.stacks.clear()
        cls.singles.clear()
        for sidx in sim_indexes:
            stack = Stack([cl for cl in cls.storage if cl.sim_index == sidx])
            if stack.count > 1:
                cls.stacks.append(stack)
            else:
                cls.singles.append(stack)

    @classmethod
    def get_all_obj_names(cls):
        p_n_sin = {cl.object_name for st in cls.singles for cl in st.clusters}
        p_n_sin.update({cl.object_name for st in cls.stacks for cl in st.clusters})
        return p_n_sin

    @classmethod
    def get_faces_ids_by_objects(cls):
        if not len(cls.stacks) and not len(cls.singles):
            cls.classify()

        p_output = dict()
        for p_obj_name in cls.get_all_obj_names():
            if p_obj_name is None:
                continue
            p_idxs = sum([cl.faces_ids for st in cls.singles for cl in st.clusters if cl.object_name == p_obj_name], [])
            p_idxs.extend(sum([cl.faces_ids for st in cls.stacks for cl in st.clusters if cl.object_name == p_obj_name], []))
            p_output.update({p_obj_name: p_idxs})
        return p_output

    @classmethod
    def get_stacked_clusters_by_objects(cls):
        if not len(cls.stacks) and not len(cls.singles):
            cls.classify()

        p_output = dict()
        for p_obj_name in cls.get_all_obj_names():
            if p_obj_name is None:
                continue
            p_idxs = sum([cl for st in cls.singles for cl in st.clusters if cl.object_name == p_obj_name], [])
            p_idxs.extend(sum([cl for st in cls.stacks for cl in st.clusters if cl.object_name == p_obj_name], []))
            p_output.update({p_obj_name: p_idxs})
        return p_output

    @classmethod
    def get_unique_clusters_face_ids_by_object(cls):
        if not len(cls.stacks) and not len(cls.singles):
            cls.classify()

        p_output = dict()
        for p_obj_name in cls.get_all_obj_names():
            if p_obj_name is None:
                continue

            p_idxs = sum([cl.faces_ids for st in cls.singles for cl in st.clusters if cl.object_name == p_obj_name], [])

            p_clusters = [st.clusters[0] for st in cls.stacks]
            p_idxs.extend(sum([cl.faces_ids for cl in p_clusters if cl.object_name == p_obj_name], []))
            p_output.update({p_obj_name: p_idxs})
        return p_output
