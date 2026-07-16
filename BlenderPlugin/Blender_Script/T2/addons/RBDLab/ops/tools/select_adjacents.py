import bpy
from typing import List
from collections import defaultdict
from bpy.types import Operator, Object


class RECALCULATE_OT_select_acjacents(Operator):
    bl_idname = "rbdlab.select_acjacents"
    bl_label = "Select Adjacents"
    bl_description = "Select Adjacents"
    bl_options = {'REGISTER', 'UNDO'}


    def find_closest_objects(self, obj_dict):
            closest_objects = []
            min_distance = float('inf')
            closest_objects = []
            
            for key, objects_list in obj_dict.items():

                for obj1 in objects_list:
                    
                    for other_key, other_objects_list in obj_dict.items():
                        
                        if key != other_key:
                            
                            for obj2 in other_objects_list:
                                
                                distance = (obj1.location - obj2.location).length
                                if distance < min_distance:
                                    min_distance = distance
                                    #min_distance = 3
                                    closest_objects.append([obj1, obj2])
            
            return closest_objects, min_distance


    def execute(self, context):
        scn = context.scene
        rbdlab = scn.rbdlab
        tcoll_list = rbdlab.lists.target_coll_list
        tcoll = tcoll_list.active

        if not tcoll:
            self.report({'ERROR'}, "Invalid target collection!")
            return {'CANCELLED'}
        
        # vertex_distance_threshold: float = 0.001
        chunks = tcoll_list.get_current_active_tcoll_valild_objects(context)

        if not chunks:
            self.report({'ERROR'}, "Chunks could not be obtained from target collection!")
            return {'CANCELLED'}

        ###################################################################################
        bpy.ops.object.select_all(action='DESELECT')

        # Guardo un diccionario con cada froms como keys y una lista con sus chunks correspondientes:
        ob_by_from: dict[str, List[Object]] = defaultdict(list)

        for ob in chunks:
            from_name = ob.get("rbdlab_from")
            if from_name:
                ob_by_from[from_name].append(ob)

        # Calculo los vecinos con mi metodo por distancia:
        closest_objects, min_distance = self.find_closest_objects(ob_by_from)
        if closest_objects:
            for l in closest_objects:
                print("Objetos más cercanos entre sí:")
                for ob in l:
                    print(ob.name)
                    ob.select_set(True)
            print("Distancia mínima:", min_distance)
        else:
            print("No se encontraron objetos en el diccionario para comparar.")

        return {'FINISHED'}