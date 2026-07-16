import colorsys
import bpy
import gpu
import numpy as np
from random import random
from gpu_extras.batch import batch_for_shader
import time
from colorsys import hsv_to_rgb
from mathutils import Matrix
from bpy.types import Object

from .math import map_value_from_range_to_range


INITIAL_OPACITY = 0.7

if bpy.app.version < (4, 0, 0):
    _shader_unif_color_idname = '3D_UNIFORM_COLOR'
else:
    _shader_unif_color_idname = 'UNIFORM_COLOR'

SHADER_UNIF_COLOR = gpu.shader.from_builtin(_shader_unif_color_idname)


class TempDrawMeshGroupsManager:
    _instance = None
    
    @staticmethod
    def draw_cluster(ctx, time_to_die: float, clusters):
        if not clusters:
            return
        if isinstance(clusters, list):
            if len(clusters) == 1:
                # Si solo es 1... pues hazlo normal...
                clusters = clusters[0]
            else:
                cluster_colors = [[*cluster.color, 1] for cluster in clusters]
                TempDrawMeshGroupsManager(ctx, time_to_die, cluster_colors, *(cluster.get_chunk_objects() for cluster in clusters))
                return
        TempDrawMeshGroupsManager(ctx, time_to_die, [*clusters.color, 1.0], clusters.get_chunk_objects())

    @classmethod
    def get(cls) -> "TempDrawMeshGroupsManager" or None:
        return cls._instance

    '''
    @classmethod
    def stop(cls) -> bool:
        draw_manager = cls.get()
        if not draw_manager:
            return False
        #if bpy.app.timers.is_registered(cls.stop):
        #    bpy.app.timers.unregister(cls.stop)
        bpy.types.SpaceView3D.draw_handler_remove(draw_manager._handler, 'WINDOW')
        # draw_manager._handler = None
        del draw_manager
        cls._instance = None
        print('STOP')
        return True
    '''

    def stop(self):
        if not hasattr(self, "_handler") or not self._handler:
            return
        self.region.tag_redraw()
        #print('STOP')
        if bpy.app.timers.is_registered(self.stop):
            #print("\t>> stop timer old")
            bpy.app.timers.unregister(self.stop)

        #print("\t>> ", id(self))
        try:
            bpy.types.SpaceView3D.draw_handler_remove(self._handler, 'WINDOW')
            self._handler = None
        except ValueError as e:
            print(e)
        # draw_manager._handler = None
        #if self.__class__._instance and self != self.__class__._instance:
        #    self.__class__._instance.stop()
        #self.__class__._instance = None
        #del self

    def __init__(self, context, time_to_die: None or float or int = None, colors = None, *mesh_groups):
        #print('INIT')
        if self.__class__._instance:
            self.__class__._instance.stop()
        self.__class__._instance = self

        self.shader = SHADER_UNIF_COLOR
        self.batch_groups = []
        self.use_custom_color = colors is not None
        self.colors = colors if colors else []
        self.ease_out_time = None
        self.ease_out_start_time = None
        self.time = time_to_die

        if mesh_groups:
            for i, mesh_group in enumerate(mesh_groups):
                self.add_mesh_group(mesh_group)

        # Save a reference of the region where we are drawing.
        if context:
            for reg in context.area.regions:
                if reg.type == 'WINDOW':
                    self.region = reg
                    break
        else:
            context = bpy.context
            for area in context.window.screen.areas:
                if area.type != 'VIEW_3D':
                    continue
                for reg in area.regions:
                    if reg.type == 'WINDOW':
                        self.region = reg
                        break

        self.start_timer(time_to_die)


    def start_timer(self, time_to_die: None or float or int = 5):
        if time_to_die and isinstance(time_to_die, (float, int)):
            count = len(self.batch_groups)
            if count == 0:
                return

            if not self.colors:
                col_factor = 1/count
                for i in range(count):
                    co = hsv_to_rgb(i * col_factor, .8, .9)
                    self.colors.append( [*co, INITIAL_OPACITY] )

            #print('START')
            self.region.tag_redraw()
            self._handler = bpy.types.SpaceView3D.draw_handler_add(self.draw, (), 'WINDOW', 'POST_VIEW')

            if bpy.app.timers.is_registered(self.stop):
                #print("\t>> stop timer old")
                bpy.app.timers.unregister(self.stop)
            self.time = time_to_die
            self.ease_in_end_time = time_to_die * .09
            self.ease_out_time = time_to_die * .85
            self.start_time = time.time()
            bpy.app.timers.register(self.stop, first_interval=time_to_die)
            bpy.app.timers.register(self.ease_in) # , first_interval=0)
            bpy.app.timers.register(self.ease_out, first_interval=self.ease_out_time)

    def add_mesh_group(self, object_group: list[Object]):
        #print("ADD MESHES")
        #vertices_count = 0
        #looptri_count = 0
        #all_vertices = np.empty((0, 3), "f")
        #all_indices  = np.empty((0, 3), "i")
        batch_group = []
        for ob in object_group:
            mesh = ob.data
            if not mesh.loop_triangles:
                mesh.calc_loop_triangles()

            #totvert = len(mesh.vertices)
            totlooptri = len(mesh.loop_triangles)

            #vertices = np.empty((totvert, 3), "f")
            indices = np.empty((totlooptri, 3), "i")

            #mesh.vertices.foreach_get(
            #    "co", np.reshape(vertices, totvert * 3))
            mesh.loop_triangles.foreach_get(
                "vertices", np.reshape(indices, totlooptri * 3))

            #loc = np.array(ob.location, "f")
            #vertices *= np.reshape(loc, 3)

            #vertices_count += totvert
            #looptri_count += totlooptri
            mw: Matrix = ob.matrix_world
            t = ob.location
            vertices = [mw@v.co for v in mesh.vertices]
            
            # offset de dibujado:
            # off = 0.001
            off = 0.01
            
            vertices = [co + (co - t).normalized() * off for co in vertices] # Scale a little bit.

            batch_group.append(batch_for_shader(
                self.shader, 'TRIS',
                {"pos": vertices},
                indices=indices
            ))

        self.batch_groups.append(batch_group)

        # store current color cluster in chunks
        #for obj in object_group:
        #    obj["cluster_color"] = color

    def ease_out(self):
        if not self._handler:
            return None
        if time.time() - self.start_time > self.time:
            return None
        #print("Ease-Out Refresh -> ", time.time())
        self.region.tag_redraw()
        return 0.01

    def ease_in(self):
        if not self._handler:
            return None
        if time.time() - self.start_time > self.ease_in_end_time:
            return None
        #print("Ease-In Refresh -> ", time.time())
        self.region.tag_redraw()
        return 0.01

    def draw(self):
        #print("Drawing... - %s" % time.time())
        gpu.state.blend_set('ALPHA')
        gpu.state.depth_test_set('LESS_EQUAL')
        gpu.state.depth_mask_set(True)
        for idx, batch_group in enumerate(self.batch_groups):
            if self.use_custom_color and len(self.batch_groups) == 1:
                color = self.colors
            else:
                color = self.colors[idx]
            diff_time = min(self.start_time, time.time() - self.start_time)
            if diff_time < self.ease_in_end_time:
                alpha = map_value_from_range_to_range(diff_time, (0, self.ease_in_end_time), (0, INITIAL_OPACITY))
                color[3] = round(float(alpha), 4)
            elif diff_time > self.ease_out_time:
                alpha = map_value_from_range_to_range(diff_time, (self.ease_out_time, self.time), (INITIAL_OPACITY, 0))
                #print("Alpha >> ", round(float(alpha), 4))
                color[3] = round(float(alpha), 4)
            else:
                color[3] = INITIAL_OPACITY
            self.shader.bind()
            self.shader.uniform_float("color", color)

            #print("Color: ", color)
            #print("Batches: ", batch_group)

            for batch in batch_group:
                batch.draw(self.shader)

        gpu.state.depth_mask_set(False)
        gpu.state.blend_set('NONE')
