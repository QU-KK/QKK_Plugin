import os
import pickle
import bpy
import sys
try:
    from BakeWrangler.nodes.node_tree import _print
except:
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    from nodes.node_tree import _print


# Complete process of putting baked verts into a temp file ready for reimport
def bake_verts(verts=None, object=None, name=None, type=None, domain=None):
    # Create temp file
    err = 0
    fd, fname = next_pickle_jar()
    if fd:
        # Export vert data to python list
        vcols = export_verts(name=name, cols=verts)
        # Add object name and data type to data list
        vcols.insert(0, [object, type, domain])
        if vcols:
            # Pickle the vcols in the jar, this also closes the file
            err = pickle_verts(file=fd, verts=vcols)
            if err:
                _print(" Error - Pickling failed.", tag=True, wrap=True)
        else:
            _print(" Error - Exporting data failed.", tag=True, wrap=True)
            err = 1
    else:
        _print(" Error - Creating temp file failed.", tag=True, wrap=True)
        err = 1
    if err:
        return 1, None
    _print(" Done", tag=True)
    return 0, fname


# Import vertex colors into currently open blend find, returns 0 on success else 1
def import_verts(cols=None):
    object = name = type = domain = None
    try:
        objinfo = cols.pop(0)
        object = objinfo[0]
        type = objinfo[1]
        domain = objinfo[2]
        name = cols.pop(0)
        blend_obj = bpy.data.objects[object]
        # See if the object already has data with the provided name, adding if needed
        if name not in blend_obj.data.color_attributes.keys():
            blend_obj.data.color_attributes.new(name, type, domain)
        elif blend_obj.data.color_attributes[name].domain != domain or blend_obj.data.color_attributes[name].data_type != type:
            blend_obj.data.color_attributes.remove(blend_obj.data.color_attributes[name])
            blend_obj.data.color_attributes.new(name, type, domain)
        # Use internal setter function to apply array
        obj_cols = blend_obj.data.color_attributes[name]
        obj_cols.data.foreach_set('color', cols)

    except:
        return 1, "Object: %s, Data: %s, Type %s, Domain %s" % (object, name, type, domain)
    else:
        return 0, "Object: %s, Data: %s, Type %s, Domain %s" % (object, name, type, domain)


# Extract vertex colors into a py list and return it or None on error
def export_verts(name=None, cols=None):
    # List needs to be set to the correct size first, which is the length of the data * 4
    vlist = [0.0] * (len(cols.data) * 4)
    try:
        # Use internal foreach get function on the data
        cols.data.foreach_get('color', vlist)
    except:
        return None
    else:
        # Insert the color data name at the front of the list and return it
        vlist.insert(0, name)
        return vlist


# Pickle vertex color dict, return 1 on error, else 0
def pickle_verts(file=None, verts=None):
    try:
        pickle.dump(verts, file, pickle.HIGHEST_PROTOCOL)
        file.close()
    except:
        return 1
    else:
        return 0


# Depickle vertex color dict from file, return None on error, else verts
def depickle_verts(file=None):
    try:
        verts = pickle.load(file)
    except:
        return None
    else:
        return verts


# Create temp file to hold pickle, return None, filename on error, else opened file, filename
def next_pickle_jar():
    blend = bpy.data.filepath
    pickl = blend + ".vert"
    fd = None
    # Find free file name by adding numbers
    if os.path.exists(pickl):
        fno = 1
        while os.path.exists(pickl):
            fno = fno + 1
            pickl = pickl + "_%03i" % (fno)
    # Open the file for binary write
    try:
        fd = open(pickl, "wb")
    except:
        return None, pickl
    else:
        return fd, pickl


# Open pickled temp, return None on error, else opened file
def open_pickle_jar(file=None):
    #Open the file for binary read
    try:
        fd = open(file, 'rb')
    except:
        return None
    else:
        return fd


if __name__ == "__main__":
    pass
