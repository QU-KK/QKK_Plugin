import bpy
from typing import List
from itertools import chain
from .....addon.naming import RBDLabNaming
from ...base import BaseConstraintOperator
from .....Global.get_common_vars import get_common_vars
from ..check_previous_keyframes import check_keyframes
from bpy.types import Context, Operator, Object, Collection
from bpy.props import IntProperty, FloatProperty, EnumProperty, BoolProperty



class SPRINGS_OT_set_springs_keyframes(Operator, BaseConstraintOperator):
    bl_idname = "rbdlab.const_set_springs_keyframes"
    bl_label = "Springs Animation"
    bl_description = "Add keyframes in Springs"
    bl_options = {'REGISTER', 'UNDO'}

    modes: EnumProperty(
        items=[
            ('ANGLE',   "Angle",         ""), 
            ('LINEAR',  "Limit Linear",  ""),
        ],
        options={'ENUM_FLAG'},
        default={'ANGLE'}
    )

    anim_stiffness_ang: BoolProperty(default=False)
    anim_damping_ang: BoolProperty(default=False)
    anim_stiffness_lin: BoolProperty(default=False)
    anim_damping_lin: BoolProperty(default=False)

    # STIFFNESS:
    # Angle props:
    stiffness_anim_frame_initial_ang: IntProperty(
        default=10,
        description="The initial frame where the first keyframe will be placed."
    )
    stiffness_initial_ang: FloatProperty(
        default=10
    )
    stiffness_anim_frame_end_ang: IntProperty(
        default=11,
        description="The last frame where the end keyframe will be placed."
    )
    stiffness_end_ang: FloatProperty(
        default=0.0
    )

    # Linear props:
    stiffness_anim_frame_initial_lin: IntProperty(
        default=10,
        description="The initial frame where the first keyframe will be placed."
    )
    stiffness_initial_lin: FloatProperty(
        default=10
    )
    stiffness_anim_frame_end_lin: IntProperty(
        default=11,
        description="The last frame where the end keyframe will be placed."
    )
    stiffness_end_lin: FloatProperty(
        default=0.0
    )

    # DAMPING:
    # Angle props:
    damping_anim_frame_initial_ang: IntProperty(
        default=10,
        description="The initial frame where the first keyframe will be placed."
    )
    damping_initial_ang: FloatProperty(
        default=1
    )
    damping_anim_frame_end_ang: IntProperty(
        default=11,
        description="The last frame where the end keyframe will be placed."
    )
    damping_end_ang: FloatProperty(
        default=0.0
    )

    # Linear props:
    damping_anim_frame_initial_lin: IntProperty(
        default=10,
        description="The initial frame where the first keyframe will be placed."
    )
    damping_initial_lin: FloatProperty(
        default=1
    )
    damping_anim_frame_end_lin: IntProperty(
        default=11,
        description="The last frame where the end keyframe will be placed."
    )
    damping_end_lin: FloatProperty(
        default=0.0
    )

    def set_keyframes(self, const: Object, dpaths:List, target_prop:str, frame:int, value) -> None:
        
        for dpath in dpaths:
            setattr(const.rigid_body_constraint, dpath, value)
            const.keyframe_insert(
                data_path="rigid_body_constraint." + dpath,
                frame=frame
            )


    def procesar(self, target_prop:str, frame_initial:int, frame_end:int, value_initial:float, value_end:float, rbdlab_const, valid_chunks:List, springs_list, active_group, constraints_to_work) -> None:
        
        procesados = []
        axis = ("x", "y", "z")
        dpaths = []
        full_dpaths = []
        dpaths = [target_prop + "_" + xyz for xyz in axis]
        
        # Chequeo los keyframes y por tyipo de dpaths:
        frame_range = [frame_initial, frame_end]
        check = check_keyframes(self, active_group, springs_list, frame_range, constraints_to_work, dpaths)
        if check:
            if 'CANCELLED' in check:
                return {'CANCELLED'}

        # por cada constraint:
        for const in constraints_to_work:
            
            # Los adjacents al estar unidos a varios chunks les afectaba los keyfraemes y no queremos eso:
            from_valid_coll = [coll.name for coll in const.users_collection if active_group.name in coll.name]
            # Chequeo si el constraint actual es de la collection correspondiente al active group con el que se esta trabajando:
            if not from_valid_coll:
                # si no está en la collection con la que se está trabajando lo skipeamos: 
                continue
            
            # si voy a meterle keyframes descarto que este ya muteado:
            if "rbdlab_const_muted" in const:
                del const["rbdlab_const_muted"]

            if not const.rigid_body_constraint:
                continue

            # Seteamos los keyframes, el array inicial y final son solo para comprobar si ya se le metieron keyframes ahí, de ser así
            # no se vuelven a meter keyframes de nuevo:
            array_inicial = [const, target_prop, frame_initial, value_initial] 
            array_final = [const, target_prop, frame_end, value_end]

            if array_inicial not in procesados:
                self.set_keyframes(const, dpaths, target_prop, frame=frame_initial, value=value_initial)
                procesados.append([const, target_prop, frame_initial, value_initial])

            if array_final not in procesados:
                self.set_keyframes(const, dpaths, target_prop, frame=frame_end, value=value_end)
                procesados.append([const, target_prop, frame_end, value_end])

            full_dpaths = ["rigid_body_constraint." + target_prop + "_" + xyz for xyz in axis]


        if len(procesados) > 0:
            
            # print(dpaths)

            # agregamos el nuevo item con toda la info que nos hace falta:
            springs_list.add_item(
                rbdlab_const=rbdlab_const,
                from_active_group=active_group.idname, 
                label_txt=" From: " + str(frame_initial) + " To: " + str(frame_end) + " " + target_prop.replace("spring_", "") + " " + "{0:0.2f}".format(value_initial) + " To: " + "{0:0.2f}".format(value_end), 
                keyframes=[frame_initial, frame_end], 
                chunks=valid_chunks,
                constraints=constraints_to_work,
                dpaths=full_dpaths
            )

    def action(self, context:Context, rbdlab_const, group, collection:Collection, chunks:List[Object], const_objects:List[Object]) -> set:

        if collection.name not in bpy.data.collections:
            self.report({'WARNING'}, "No GlueConstraints collection in the scene!")
            return {'CANCELLED'}
        
        tcoll_list = get_common_vars(context, get_tcoll_list=True)
        tcoll = tcoll_list.active
        
        if not tcoll:
            return {'CANCELLED'}
        
        rbdlab_const_active = rbdlab_const.group_active
        springs_list = rbdlab_const_active.springs_list

        active_group = rbdlab_const.get_active_group
        chunks_group_const:List[Object] = rbdlab_const.get_chunks_from_group()

        if rbdlab_const.springs_anim_by_selection:
            valid_chunks = [ob for ob in context.selected_objects if ob.type == 'MESH' and ob.visible_get() and RBDLabNaming.GROUND not in ob]
            all_const_names_stored_in_chunk:List[str] = [ob[RBDLabNaming.CONSTRAINTS].split() for ob in valid_chunks if RBDLabNaming.CONSTRAINTS in ob]
        else:
            valid_chunks = [ob for ob in chunks_group_const if ob.type == 'MESH' and ob.visible_get() and RBDLabNaming.GROUND not in ob]
            all_const_names_stored_in_chunk:List[str] = [ob[RBDLabNaming.CONSTRAINTS].split() for ob in valid_chunks if RBDLabNaming.CONSTRAINTS in ob]
        
        # print("valid_chunks", valid_chunks)
        # print("all_const_names_stored_in_chunk", all_const_names_stored_in_chunk)
        # Nota: con list(chain.from_iterable(all_const_names_stored_in_chunk))) hacemos flatten la lista 2d a 1d
        real_const_obs:List[Object] = [context.scene.objects.get(const_name) for const_name in list(chain.from_iterable(all_const_names_stored_in_chunk)) if context.scene.objects.get(const_name)]
        #print("real_const_obs", real_const_obs)
        
        constraints_to_work:List[Object] = [const for const in real_const_obs if const.type == RBDLabNaming.CONST_TYPE]
        # print("constraints_to_work", constraints_to_work)

        if not constraints_to_work:
            if rbdlab_const.springs_anim_by_selection:
                self.report({'WARNING'}, "No Selected valid Chunks!1")
            else:
                self.report({'WARNING'}, "No valid Constraints in the collection!")
            return {'CANCELLED'}

        # remove doubles/duplicates in list:
        constraints_to_work = list(set(constraints_to_work))

        # Procedemos por cada una de las posibles opciones:
        posible_modes = { 'LINEAR': "_lin", 'ANGLE': "_ang" }
        for pm in posible_modes.keys():

            # Si está opción está seleccionada por el usuario:
            if pm in self.modes:
                # seteamos el sufix correspondiente a cada opción:
                sufix_mode = posible_modes[pm]
                
                # Propiedades con las que quire trabajar el usuario (el stiffnes o el damping o ambos)
                posible_props = { "stiffness": getattr(self, "anim_stiffness" + sufix_mode), "damping": getattr(self, "anim_damping" + sufix_mode) }
                
                # por cada propiedad:
                for p, anim in posible_props.items():
                        
                    # si el usuario quiere animarla:
                    if anim:

                        # pasamos los valores de cada opcion y propiedad de forma generica para que funcione con todas las opciones:
                        target_prop =  p
                        self.procesar(
                                        target_prop="spring_" + target_prop if sufix_mode == "_lin" else "spring_" + target_prop + sufix_mode,

                                        frame_initial=getattr(self, target_prop + "_anim_frame_initial" + sufix_mode),
                                        frame_end=getattr(self, target_prop + "_anim_frame_end" + sufix_mode),

                                        value_initial=getattr(self, target_prop + "_initial" + sufix_mode),
                                        value_end=getattr(self, target_prop + "_end" + sufix_mode),
                                        
                                        rbdlab_const=rbdlab_const, 
                                        valid_chunks=valid_chunks, 
                                        springs_list=springs_list, 
                                        active_group=active_group, 
                                        constraints_to_work=constraints_to_work
                                    )

        return {'FINISHED'}


    def invoke(self, context, event):
        wm = context.window_manager

        # leyendo del streng del usuario:
        scn, rbdlab_const = get_common_vars(context, get_scn=True, get_constraints=True)
        
        # active_group = rbdlab_const.active
        active_group = rbdlab_const.get_active_group

        # Sugerimos los settings (por ahora solo los uniq, si se usa los 3 valores nose....):

        if active_group.spring_stiffness_uniq > 0:
            self.stiffness_initial_lin = active_group.spring_stiffness_uniq        

        if active_group.spring_damping_uniq > 0:
            self.damping_initial_lin = active_group.spring_damping_uniq

        if active_group.spring_stiffness_ang_uniq > 0:
            self.stiffness_initial_ang = active_group.spring_stiffness_ang_uniq

        # print(active_group.spring_damping_ang_uniq)
        if active_group.spring_damping_ang_uniq > 0:
            self.damping_initial_ang = active_group.spring_damping_ang_uniq
        
        # los start y ends:
        self.stiffness_anim_frame_initial_lin = scn.frame_current
        self.stiffness_anim_frame_end_lin = scn.frame_current +1

        self.damping_anim_frame_initial_lin = scn.frame_current
        self.damping_anim_frame_end_lin = scn.frame_current +1

        self.stiffness_anim_frame_initial_ang = scn.frame_current
        self.stiffness_anim_frame_end_ang = scn.frame_current +1

        self.damping_anim_frame_initial_ang = scn.frame_current
        self.damping_anim_frame_end_ang = scn.frame_current +1

        return wm.invoke_props_dialog(self, width=250)


    def draw(self, context):
        layout = self.layout

        main_col = layout.column(align=True)
        modes = main_col.row(align=True)
        modes.scale_y = 1.3
        modes.prop(self, "modes", expand=True)

        main_col.separator()

        if 'ANGLE' in self.modes:
                
            # Stiffness Angle
            stiffness_angle = main_col.box().column(align=True)
            stiffness_angle.prop(self, "anim_stiffness_ang", text="Stiffness Angle")
            main_col_angle = main_col.box().column(align=True)

            row = main_col_angle.row(align=True)
            initial = row.column(align=True)
            initial.prop(self, "stiffness_anim_frame_initial_ang", text="Frame Start")
            initial.prop(self, "stiffness_initial_ang", text="Stiffness", expand=True)

            final = row.column(align=True)
            final.prop(self, "stiffness_anim_frame_end_ang", text="Frame End", expand=True)
            final.prop(self, "stiffness_end_ang", text="Stiffness", expand=True)

            # Damping Angle
            if 'ANGLE' in self.modes and 'LINEAR' in self.modes:
                damping_angle = main_col.box().column(align=True)
            else:
                main_col = layout.column(align=True)
                damping_angle = main_col.box().column(align=True)
            
            damping_angle.prop(self, "anim_damping_ang", text="Damping Angle")
            main_col = main_col.box().column(align=True)

            row = main_col.row(align=True)
            initial = row.column(align=True)
            initial.prop(self, "damping_anim_frame_initial_ang", text="Frame Start")
            initial.prop(self, "damping_initial_ang", text="Damping", expand=True)

            final = row.column(align=True)
            final.prop(self, "damping_anim_frame_end_ang", text="Frame End", expand=True)
            final.prop(self, "damping_end_ang", text="Damping", expand=True)
    
            if {'LINEAR'} == self.modes:
                main_col = layout.column(align=True)
        
        
        if 'LINEAR' in self.modes:

            if 'ANGLE' in self.modes:
                main_col = layout.column(align=True)

            # Stiffness Linear
            linear = main_col.box().column(align=True)
            linear.prop(self, "anim_stiffness_lin", text="Stiffness Linear")
            main_col_linear = main_col.box().column(align=True)

            row = main_col_linear.row(align=True)
            initial = row.column(align=True)
            initial.prop(self, "stiffness_anim_frame_initial_lin", text="Frame Start")
            initial.prop(self, "stiffness_initial_lin", text="Stiffness", expand=True)

            final = row.column(align=True)
            final.prop(self, "stiffness_anim_frame_end_lin", text="Frame End", expand=True)
            final.prop(self, "stiffness_end_lin", text="Stiffness", expand=True)

            # Damping Linear

            if 'ANGLE' in self.modes and 'LINEAR' in self.modes:
                linear = main_col.box().column(align=True)
            else:
                main_col = layout.column(align=True)
                linear = main_col.box().column(align=True)
                
            linear.prop(self, "anim_damping_lin", text="Damping Linear")
            main_col = main_col.box().column(align=True)

            row = main_col.row(align=True)
            initial = row.column(align=True)
            initial.prop(self, "damping_anim_frame_initial_lin", text="Frame Start")
            initial.prop(self, "damping_initial_lin", text="Damping", expand=True)

            final = row.column(align=True)
            final.prop(self, "damping_anim_frame_end_lin", text="Frame End", expand=True)
            final.prop(self, "damping_end_lin", text="Damping", expand=True)