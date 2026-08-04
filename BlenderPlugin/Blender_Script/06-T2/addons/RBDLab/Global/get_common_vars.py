class CommonVars:

    """ Clase del Objeto para obtener (ondemand) las rutas/y/o items más utilizadas en el addon, de una manera más fácil y práctica """

    def __init__(self, context):
        self.context = context

    @property
    def view_layer(self):
        return self.context.view_layer

    @property
    def scn(self):
        return self.context.scene

    @property
    def rbdlab(self):
        return self.scn.rbdlab

    @property
    def ui(self):
        return self.rbdlab.ui

    @property
    def lists(self):
        return self.rbdlab.lists

    @property
    def constraints(self):
        return self.rbdlab.constraints
    
    @property
    def tcoll_list(self):
        return self.lists.target_coll_list

    @property
    def ac_layers_list(self):
        return self.lists.ac_layers_list


def get_common_vars(context, **kwargs):
    
    """ 
    Devuelve una lista o única propiedad deseada para las variables solicitadas,
    según el contexto proporcionado a través del argumento "context".

    Ejemplos de uso:
        view_layer = get_common_vars(context, get_view_layer=True)
        scn, rbdlab = get_common_vars(context, get_scn=True, get_rbdlab=True)
    """

    cv = CommonVars(context)

    # Creamos una lista de propiedades permitidas, y en el orden que se solicitarían, excepto user_item que es la ultima.
    allowed_props = ["view_layer", "scn", "rbdlab", "ui", "lists", "constraints", "tcoll_list", "ac_layers_list"]

    # Limpiamos los prefijos "get_" de los argumentos.
    kwargs_clean = {k.replace("get_", ""): v for k, v in kwargs.items()}

    # Creamos un diccionario solo con las propiedades permitidas y sus valores recopilados.
    props = {k: getattr(cv, k) for k in allowed_props if k in kwargs_clean and kwargs_clean[k]}

    # si hay flag del usuario de debug:
    debug = kwargs.get("debug")
    if debug:
        # print("[DEBUG] Input User:", kwargs)
        print("[DEBUG] Output:", props)

    # Devolvemos los valores solicitados:
    if kwargs.get("get_all"):
        return [v for v in props.values()]
    else:
        # Con el popitem, si el len es igual a 1, devolvemos (del par k,v del diccionario) el value, y sino devolvemos la lista entera de valores.
        return list(props.values())[0] if len(props.values()) == 1 else list(props.values())
