from bpy.types import PropertyGroup
# from ....addon.naming import RBDLabNaming
from bpy.props import BoolProperty, IntProperty, EnumProperty

class RBDLAB_PG_rbd_animations(PropertyGroup):
    """ context.scene.rbdlab.physics.rigidbodies.animations.x """

    by_selection: BoolProperty(default=False)
    
    add_mode: EnumProperty(
        name="Choose Mode",
        description="Choose Mode to add keyframes",
        items=[
                ('OFF/ON',  "OFF/ON",   "", 0),
                ('OFF',     "OFF",      "", 1),
                ('ON',      "ON",       "", 2),
               ],
    )
    
    def offset_update(self, context):

        scn = context.scene
        rbdlab = scn.rbdlab

        tcoll_list = rbdlab.lists.target_coll_list
        tcoll = tcoll_list.active
        if not tcoll:
            return
        
        dynamic_list = tcoll.rbdlab.dynamic_list
        item = dynamic_list.active
        if item:

            frames = [int(item_frame.frame) for item_frame in item.stored_keyframes]
            chunks = [item_chunk.chunk for item_chunk in item.stored_chunks]

            # los dos ultimos keyframes guardados en el item:
            last_keyframes = [frames[-2], frames[-1]]

            if item.id not in rbdlab:
                # guardo los keyframes originales en wm:
                rbdlab[item.id] = {
                                "penult_kf": frames[-2],
                                "last_kf": frames[-1],
                            }
            
            if chunks and frames:
                
                dpath="rigid_body.enabled"

                # desde la coordenada x que se genero en la creación del slot/item lo offseteamos:
                org_offseted_1 = rbdlab[item.id]["penult_kf"] + self.offset_duration
                org_offseted_2 = rbdlab[item.id]["last_kf"] + self.offset_duration
                item.offseted = self.offset_duration

                # para sobreescribir los frames luego con la nueva data:
                stored_keyframes1 = item.stored_keyframes[-2]
                stored_keyframes2 = item.stored_keyframes[-1]

                last_chunk = chunks[-1]

                axis = 0 # X
                for chunk in chunks:
                    if not chunk.animation_data:
                        continue

                    if not chunk.animation_data.action:
                        continue

                    if not chunk.animation_data.action.fcurves:
                        continue

                    if not chunk.animation_data.action.fcurves.find(dpath):
                        continue

                    action = chunk.animation_data.action
                    fcurve = action.fcurves.find(data_path=dpath, index=axis)
                    if fcurve:

                        for p in fcurve.keyframe_points:
                            if int(p.co.x) == last_keyframes[0]:
                                p.co.x = org_offseted_1
                                p.handle_left.x = org_offseted_1
                                p.handle_right.x = org_offseted_1

                                if chunk == last_chunk:
                                    stored_keyframes1.frame = int(org_offseted_1)

                            elif int(p.co.x) == last_keyframes[1]:
                                p.co.x = org_offseted_2
                                p.handle_left.x = org_offseted_2
                                p.handle_right.x = org_offseted_2

                                if chunk == last_chunk:
                                    stored_keyframes2.frame = int(org_offseted_2)
            
                # si el offset es 0, lo podemos quitar de wm y asi sabemos
                # los que estan realmente offseteados:
                if item.id in rbdlab and self.offset_duration == 0:
                    del rbdlab[item.id]

    offset_duration: IntProperty(
        name="Offset Duration",
        description="Offset keyframes",
        soft_min=0,
        update=offset_update
    )

    # substeps per frame:
    substeps_frame: IntProperty(
        default=1
    )
    substeps_from: IntProperty(
        default=1
    )
    substeps_to: IntProperty(
        default=8
    )
    substeps_animated: BoolProperty(default=False)
    # solver iterations:
    s_iterations_frame: IntProperty(
        default=1
    )
    s_iterations_from: IntProperty(
        default=1
    )
    s_iterations_to: IntProperty(
        default=10
    )
    s_iterations_animated: BoolProperty(default=False)
    # World Speed:
    world_speed_frame: IntProperty(
        default=1
    )
    world_speed_from: IntProperty(
        default=1
    )
    world_speed_to: IntProperty(
        default=10
    )
    world_speed_animated: BoolProperty(default=False)