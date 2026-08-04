import bpy
from bpy.props import BoolProperty, IntProperty
import bmesh
import math
import mathutils
from .. utils.collection import sort_into_collections
from .. utils.decal import get_panel_width, create_float_slice_geometry, create_panel_uvs, finish_panel_decal
from .. utils.draw import draw_point, draw_points
from .. utils.object import is_obj_smooth, update_local_view
from .. utils.raycast import find_nearest_normals
from .. utils.raycast import get_closest

class GPanel(bpy.types.Operator):
    bl_idname = "machin3.gpanel"
    bl_label = "MACHIN3: Grease Panel"
    bl_description = "Turns Grease Pencil Strokes into a Panel Decal.\nSHIFT: Connected Panels\nCTRL: Connected Cyclic Panel"
    bl_options = {'REGISTER', 'UNDO'}

    connect: BoolProperty(name="Connect Strokes", default=False)
    segments: IntProperty(name="Segments", default=4, min=0)
    make_cyclic: BoolProperty(name="Make Cyclic", default=False)
    def draw(self, context):
        layout = self.layout

        column = layout.column()

        row = column.row(align=True)
        row.prop(self, "connect", toggle=True)
        if self.connect:
            row.prop(self, "segments")
            row.prop(self, "make_cyclic", toggle=True)

    @classmethod
    def poll(cls, context):
        active = context.active_object
        return (active and active.type in ['GPENCIL', 'GREASEPENCIL']) or (active and active.DM.decaltype == "PANEL" and not active.DM.decalbackup)

    def invoke(self, context, event):
        self.dg = context.evaluated_depsgraph_get()

        gp = context.active_object
        layer = gp.data.layers.active

        if layer and not layer.hide:
            target = gp.parent if gp.parent else self.find_nearest_surface(context, gp, layer)

            if target:
                self.connect = True if event.shift else True if event.ctrl else False
                self.make_cyclic = True if event.ctrl else False

                self.gpanel(context, gp, layer, target, self.connect, self.segments, self.make_cyclic)

                return {'FINISHED'}
        return {'CANCELLED'}

    def execute(self, context):
        self.dg = context.evaluated_depsgraph_get()

        gp = context.active_object
        layer = gp.data.layers.active

        if layer and not layer.hide:
            target = gp.parent if gp.parent else self.find_nearest_surface(context, gp, layer)

            if target:
                self.gpanel(context, gp, layer, target, self.connect, self.segments, self.make_cyclic)

                return {'FINISHED'}
        return {'CANCELLED'}

    def find_nearest_surface(self, context, gp, layer, debug=False):
        if debug:
            print("GP is not parented, finding target by surface proximity to first point in first stroke.")

        if bpy.app.version < (4, 3, 0):
            frame = layer.active_frame
        else:
            frame = layer.current_frame()

        if frame is None:
            frame = layer.frames.new(0)

        if bpy.app.version < (4, 3, 0):
            try:
                point = frame.strokes[0].points[0]
            except:
                point = None

                if debug:
                    print("Active GP layer has no strokes or stroke has no points.")

        else:
            drawing = frame.drawing

            try:
                point = drawing.strokes[0].points[0]
            except:
                point = None

                if debug:
                    print("Active GP layer has no strokes or stroke has no points.")

        if point:
            if bpy.app.version < (4, 3, 0):
                origin = gp.matrix_world @ point.co
            else:
                origin = gp.matrix_world @ point.position

            if debug:
                draw_point(origin, color=(1, 0, 0), modal=False)

            visible = [obj for obj in context.visible_objects if not obj.DM.isdecal]
            target, _, _, _, _, _ = get_closest(self.dg, visible, origin, debug=debug)

            return target

    def create_vert_sequences(self, mesh, psequences, mx):
        bm = bmesh.new()
        bm.from_mesh(mesh)

        sequences = []
        intersection = []

        for sidx, pseq in enumerate(psequences):
            seq = []

            for pidx, co in enumerate(pseq):

                if 'nan' in str(co):
                    print(f"WARNING: skipping grease pencil point in sequence {sidx} with index {pidx} and coords {co}")
                    continue

                v = bm.verts.new()
                v.co = mx @ co
                seq.append(v)
                intersection.append(v)

            sequences.append((seq, False))

        bm.verts.index_update()

        return bm, sequences, intersection

    def create_edges_from_strokes(self, bm, sequences):
        for verts, _ in sequences:
            for idx, v in enumerate(verts):
                if idx < len(verts) - 1:
                    bm.edges.new([v, verts[idx +1]])

    def gpanel(self, context, gp, layer, target, connect=False, segments=4, make_cyclic=True, debug=False):
        mcol = context.collection

        layer.hide = True

        if bpy.app.version < (4, 3, 0):
            frame = layer.active_frame
        else:
            frame = layer.current_frame()

        psequences = []

        if bpy.app.version < (4, 3, 0):
            for stroke in frame.strokes:
                pseq = []
                for point in stroke.points:
                    pseq.append(point.co)

                psequences.append(pseq)

        else:
            for stroke in frame.drawing.strokes:
                pseq = []

                for point in stroke.points:
                    pseq.append(point.position)

                psequences.append(pseq)

        panel = bpy.data.objects.new("Panel Decal", bpy.data.meshes.new("Panel Decal"))

        panel.matrix_world = target.matrix_world

        mcol.objects.link(panel)
        mx = panel.matrix_world
        mxi = panel.matrix_world.inverted_safe() @ gp.matrix_world

        bm, sequences, intersection = self.create_vert_sequences(panel.data, psequences, mxi)

        if connect and len(sequences) > 1:
            if make_cyclic:
                sequences.append(sequences[0])

            connected_sequence = []

            for idx, (verts, _) in enumerate(sequences):
                if idx < len(sequences) - 1:

                    v_end = verts[-1]
                    v_end_remote = verts[-2]
                    end_dir = v_end_remote.co - v_end.co

                    v_start = sequences[idx + 1][0][0]
                    v_start_remote = sequences[idx + 1][0][1]
                    start_dir = v_start_remote.co - v_start.co

                    connection_angle = math.degrees(end_dir.angle(start_dir))

                    ico = mathutils.geometry.intersect_line_line(v_start.co, v_start_remote.co, v_end.co, v_end_remote.co)

                    if ico is None or 178 <= connection_angle <= 182:  # if the edge and both loop egdes are on the same line or are parallel: _._._ or  _./'¯¯

                        connected_sequence.extend(verts)

                    else:

                        if debug:
                            draw_point(ico[0], mx=mx, color=(1, 0, 0), modal=False)
                            draw_point(ico[1], mx=mx, color=(0, 1, 0), modal=False)

                        handle_end = v_end.co + (ico[0] - v_end.co) * 0.7
                        handle_start = v_start.co + (ico[1] - v_start.co) * 0.7

                        beziercos = mathutils.geometry.interpolate_bezier(v_end.co, handle_end, handle_start, v_start.co, segments + 2)

                        connected_sequence.extend(verts)

                        for co in beziercos[1:-1]:
                            if debug:
                                draw_point(co, mx=mx, color=(1, 1, 1), modal=False)

                            v = bm.verts.new()
                            v.co = co

                            connected_sequence.append(v)
                            intersection.append(v)

                elif not make_cyclic:
                    connected_sequence.extend(verts)

            sequences = [(connected_sequence, make_cyclic)]

        if debug:
            for verts, cyclic in sequences:
                print()
                print(cyclic)
                print([v.index for v in verts])

                for v in verts:
                    print("", v.co)

                draw_points([v.co.copy() for v in verts[1:]], mx=mx, modal=False)

            context.area.tag_redraw()

        normals, bmt = find_nearest_normals(bm, target.evaluated_get(self.dg).to_mesh(), debug=debug)

        self.create_edges_from_strokes(bm, sequences)

        width = get_panel_width(panel, context.scene)

        use_smooth = is_obj_smooth(target)

        geo = create_float_slice_geometry(bm, panel.matrix_world, sequences, normals, width=width, smooth=use_smooth)

        bmesh.ops.delete(bm, geom=intersection, context="VERTS")

        bmt.free()

        create_panel_uvs(bm, geo, panel, width=width)

        finish_panel_decal(self.dg, context, panel, target, None, smooth=use_smooth)

        sort_into_collections(context, panel)

        gp.select_set(False)
        panel.select_set(True)
        context.view_layer.objects.active = panel

        update_local_view(context.space_data, [(panel, True)])
