def name_increment(bfracture_gn_list) -> str:
    
    # si ya existe el nombre lo incrementamos con 0x:

    all_previous_items_names = bfracture_gn_list.get_all_items_names

    total = [name for name in all_previous_items_names if name.startswith("Boolfracture")]
    iter = len(total)
    
    if iter == 0:
        new_name = "Boolfracture_00"
    else:

        new_name = "Boolfracture_" + str(iter).zfill( len(str(iter))+1 )
        # cuando era Boolfracture_01 no agregaba más al ya existir en el listado, por lo tanto 
        # intento incrementar de 1 en 1 hasta 100 intentos más:
        all_previous_items_names = bfracture_gn_list.get_all_items_names
        i = 0
        while new_name in all_previous_items_names and i < 100:
            new_name = "Boolfracture_" + str(iter+i).zfill( len(str(iter))+1 )
            i += 1

    return new_name