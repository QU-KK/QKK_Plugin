

def reorder_list(target_list, direction:str) -> None:
    """ 
        Metodo para Reordenar listados 
        Es necesario que el target_list teng dentro un .list y un .list_index
    """

    if not target_list:
        print("[reorder list]: Invalid input list!, exit")
        return

    if direction not in ('UP', 'DOWN'):
        print("[reorder list]: Invalid direction!, exit")
        return

    index = target_list.list_index

    # move item:
    neighbor = index + (-1 if direction == 'UP' else 1)
    target_list.list.move(neighbor, index)

    # re set active item in the list:
    list_length = len(target_list.list) - 1
    target_list.list_index = max(0, min(neighbor, list_length))