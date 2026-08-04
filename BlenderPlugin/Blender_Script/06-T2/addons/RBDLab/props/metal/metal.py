import bpy
from bpy.types import PropertyGroup, Object
from bpy.props import BoolProperty, PointerProperty, EnumProperty
from ...addon.naming import RBDLabNaming
from ...Global.get_common_vars import get_common_vars


class RBDLabMetalData(PropertyGroup):

    """ collection.rbdlab.metal.x """

    other_original: BoolProperty(name="Other Original", description="Use Other Original or Automatic", default=False)
    use_multiple_proxys: BoolProperty(name="Use Multiple Proxys", description="Use Multiple proxy objects", default=False)

    def filter_ob_original(self, ob):
        if RBDLabNaming.ORIGINALS in bpy.data.collections:
            return ob.name in bpy.data.collections[RBDLabNaming.ORIGINALS].objects
        else:
            return False
        
    ob_original_selector: PointerProperty(name="Other Original", description="Use Other Original or Automatic", type=Object, poll=filter_ob_original)

    # para el clean:
    metal_decimate_planar: BoolProperty(default=True)
    metal_triangulate: BoolProperty(default=True)

    use_multi_face: BoolProperty(default=True)
    use_boundary: BoolProperty(default=True)
    use_non_contiguous: BoolProperty(default=True)

    metal_remove_doulbes: BoolProperty(default=True)

    # para poner masa custom, (MetalSoft Mass)
    def metal_soft_mass_update(self, context):

        if self.metal_soft_mass:

            rbdlab, ui = get_common_vars(context, get_rbdlab=True, get_ui=True)
            rbdlab_constraints = rbdlab.constraints
            
            # Si vamos a usar metal:
            if ui.active_const_tab == 'CREATE':
                rbdlab_constraints.breakable = False
                rbdlab_constraints.constraint_type = 'GENERIC_SPRING'
                rbdlab_constraints.limit_neighbor_constraints = False
                rbdlab_constraints.constraints_between_chunks = True


    metal_soft_mass: BoolProperty(
                                    name="MetalSoft",
                                    description="MetalSoft Mass",
                                    default=False, 
                                    update=metal_soft_mass_update
                                )
    
    mesh_source: EnumProperty(
        items=[
            ('BASE',    "Base",     "", 0),
            ('DEFORM',  "Deform",   "", 1),
            ('FINAL',   "Final",    "", 2)
        ],
        default='BASE'
    )