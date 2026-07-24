import os.path
import bpy


# Get current path of blend file
def get_blend_path():
    return os.path.dirname(bpy.data.filepath)


# Add tiles from list to image data block
def create_tiles(img, tiles):
    img.source = 'TILED'
    udim = img.tiles
    for tile in tiles:
        udim.new(tile)
    
    # Now all the tiles need to be initialzed and there is no python api other than the ops call
    # so the annoying context override stuff has to be done
    context = bpy.context
    context_overridden = context.copy()
    context_overridden['area'] = context.screen.areas[0]
    context_overridden['area'].ui_type = 'UV'
    context_overridden['area'].spaces.active.image = img
    context_overridden['screen'] = context.screen
    context_overridden['region'] = context_overridden['area'].regions[0]
    
    for tile_index, tile in enumerate(img.tiles):
        # setting active tile and filling it
        img.tiles.active_index = tile_index
        with context.temp_override(**context_overridden):
            bpy.ops.image.tile_fill(width=img.size[0], height=img.size[1])
    img.update()
        

# Take a UV map and split it into UDIM tiles using standard format
def uv_to_udim(solution, key, uvmap):
    tiles = solution.baketile[key]
    udim = []
    # TODO: Check fastest way to get all the uvs
    uvs = [uvmap.data[i].uv[:] for i in range(len(uvmap.data.values()))]
    for u, v in uvs:
        if int(u) == u and u > 0: u -= 1
        if int(v) == v and v > 0: v -= 1
        tile_no = (int(v) * 10) + int(u) + 1001
        if tile_no not in tiles:
            tiles[tile_no] = []
        if tile_no not in udim:
            udim.append(tile_no)
    udim.sort()
    return udim


# Generate short path for tile output
def make_tile_path():
    # Make a short filename for tiles
    tileFilePrefix = os.path.join(get_blend_path(), "BW_T")
    if os.path.exists(tileFilePrefix):
        fno = 1
        while os.path.exists(tileFilePrefix + "%03i" % (fno)):
            fno = fno + 1
        tileFilePrefix = tileFilePrefix + "%03i" % (fno)
    pre = open(tileFilePrefix, "w", encoding="utf-8", errors="replace")
    pre.close()
    return tileFilePrefix
    
    
# Separate a tiled image into individual data blocks
def separate_tiles(src=None, tiles=None, index=0):
    # Save out the tiles
    filep = make_tile_path()    
    src.save_render(filep + ".<UDIM>")
    
    # Load the tiles into the separate data blocks
    for tile in tiles.keys():
        img = tiles[tile][index]
        img.source = 'FILE'
        img.filepath = filep + "." + str(tile)
        img.update()
    

if __name__ == '__main__':
    pass