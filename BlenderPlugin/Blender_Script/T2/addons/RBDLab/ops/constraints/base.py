from typing import List, Set
from bpy.types import Object, Collection


class BaseConstraintOperator:
    base__get_const_objects_from_chunks: bool = False    

    @classmethod
    def poll(cls, context):
        # Si hay un grupo activo.
        return context.scene.rbdlab.constraints.get_active_group is not None
    
    def get_filtered_chunks(self, context) -> Set[Object]:
        return None

    def execute(self, context):
        from ...props.constraints.constraints import ConstraintGroup, RBDLab_PG_Constraints

        rbdlab_const: RBDLab_PG_Constraints = context.scene.rbdlab.constraints
        active_group: ConstraintGroup = rbdlab_const.get_active_group

        if not active_group:
            print("No Group")
            return {'CANCELLED'}

        if not active_group.collection:
            print("No Group Collection")
            return {'CANCELLED'}

        #if group.type == 'CLUSTER':
        #    chunks: List[Object] = group.get_chunks_from_selected_cluster()
        #else:
        #    chunks: List[Object] = group.get_chunks()
        
        chunks, const_objects = active_group.get_constraint_objects(
            from_chunks=self.base__get_const_objects_from_chunks,
            get_const_from_all_groups=False,
            filtered_chunks=self.get_filtered_chunks(context))
        
        if not chunks or not const_objects:
            print("No Group Chunks or Const objects")
            return {'CANCELLED'}
        
        self.action(context, rbdlab_const, active_group, active_group.collection, chunks, const_objects)
        return {'FINISHED'}

    def action(self, context, rbdlab_const, group, collection: Collection, chunks: List[Object], const_objects: List[Object]):
        pass
