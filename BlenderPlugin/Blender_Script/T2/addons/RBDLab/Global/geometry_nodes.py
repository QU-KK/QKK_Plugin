from typing import Union
from bpy.types import NodeGroup, Node


def add_node(in_node_group:NodeGroup, coords:tuple, node_type:str, sel:bool) -> Node:
    node = in_node_group.nodes.new(node_type)
    node.select = sel
    node.location = coords
    return node 


def get_gn_index_or_identifier_by(mode:str, search_type:str, socket_type:str, node:Node, search_type_name:str, debug:bool) -> Union[int, str]:
    
    """
        INFO: \n
        mode = puede ser "index" o "identifier" \n
        search_type = puede ser "name" o "type" para compararlos con search_type_name (por ejemplo Radius). \n
        socket_type = puede ser "inputs" o "outputs"
    """
 
    # NOTA: ¿Que significa que estén los sockets enabled?, algunos nodos tienen varios "estados" y por cada estado cambian sus sockets visibles.
    # Con .enabled nos aseguramos de que solo usemos los sockets que se están viendo el el nodo en ese momento, independientemente del 
    # resto de sockets ocultos que tenga el nodo.
    
    if mode == "index":
        result = next((i for i, socket in enumerate(getattr(node, socket_type)) if socket.enabled and getattr(socket, search_type) == search_type_name), None)
    
    elif mode == "identifier":
        result = next((socket.identifier for socket in getattr(node, socket_type) if socket.enabled and getattr(socket, search_type) == search_type_name), None)
            
    if debug:
        print("---------------------------------")
        print("node.name:", node.name)
        print("search_type:", search_type)
        print("socket_type:", socket_type)
        print("search_type_name:", search_type_name)
        print("result:", result)

    return result


def connect_nodes(node_group:NodeGroup, node_1:Node, name_1:str, node_2:Node, name_2:str, debug:bool) -> None:
    idx_socket_n1 = get_gn_index_or_identifier_by("index", "name", "outputs", node_1, name_1, debug=debug)
    idx_socket_n2 = get_gn_index_or_identifier_by("index", "name", "inputs", node_2, name_2, debug=debug)
    if idx_socket_n1 is not None and idx_socket_n2 is not None:
        node_group.links.new(node_1.outputs[idx_socket_n1], node_2.inputs[idx_socket_n2])


def set_exposed_attributes_of_gn(gn_mod:NodeGroup, target_name:str, value, debug:bool) -> None:
    group_input = gn_mod.node_group.nodes.get("Group Input")
    if group_input:
        identifier = get_gn_index_or_identifier_by("identifier", "name", "outputs", group_input, target_name, debug=debug)
        if identifier is not None:
           gn_mod[identifier] = value