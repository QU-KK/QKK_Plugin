import bpy

def compute_mass(rbd_props, metal_props, valid_objects):

    # la masa:
    material_type = rbd_props.avalidable_mass

    # El computo custom es en base a un numero pero no es poner la masa a ese numero:
    if material_type == "Custom":
        bpy.ops.rigidbody.mass_calculate(material=material_type, density=rbd_props.custom_mass)

    else:
        # computo MetalSoft si que pone ese numero customo como masa:

        # Chequeo si usamos MetalSoft Mass:
        mass_value = rbd_props.metal_mass if metal_props.metal_soft_mass else False

        # print(mass_value)

        for ob in valid_objects:

            if not ob.rigid_body:
                continue

            # Si, usamos MetalSoft Mass:
            if mass_value:
                ob.rigid_body.mass = mass_value
            
            ob.rigid_body.mesh_source = metal_props.mesh_source
        
        # Si no usamos MetalSoft Mass entonces computamos como antes:
        if not mass_value:
            bpy.ops.rigidbody.mass_calculate(material=material_type)