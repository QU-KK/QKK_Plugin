from os.path import dirname, abspath, join, basename, normpath


class RBDLabPaths:
    # antes cuando estaba en el raiz:
    # ROOT = (dirname(abspath(__file__)))
    # pero ahora esta en la carpeta addon por lo tanto subimos un directorio:
    ROOT = normpath(join(dirname(abspath(__file__)), ".."))
    ROOT_BASENAME = basename(ROOT)
    LIBS = join(ROOT, "libs")
    LIBS_ICONS = join(LIBS, "icons")


class RBDLabPreferences:
    def get_prefs(context):
        return context.preferences.addons[RBDLabPaths.ROOT_BASENAME].preferences
