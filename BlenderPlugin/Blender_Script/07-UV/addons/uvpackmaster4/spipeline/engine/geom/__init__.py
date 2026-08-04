
from ..uc_entry import uc


class PACK_RATIO:

    ratio = 1.0

    @classmethod
    def set(cls, ratio):
        cls.ratio = ratio

    @classmethod
    def get(cls):      
        return cls.ratio
    
    @classmethod
    def apply_to_islands(cls, islands):
        if cls.get() == 1.0:
            return islands

        return islands.scale(cls.get(), 1.0)
    
    @classmethod
    def unapply_from_islands(cls, islands):
        if cls.get() == 1.0:
            return islands
        
        return islands.scale(1.0 / cls.get(), 1.0)


def islands_inside_box(islands, box, fully_inside):
    islands_inside = uc.IslandSet()
    uc_box = box.to_uc_box()

    if fully_inside:
        def inside_check(island):
            island_bbox = island.bbox()
            return island_bbox.within(uc_box)
    else:
        def inside_check(island):
            return island.overlaps(uc_box)
    
    for island in islands:
        if inside_check(island):
            islands_inside.append(island)

    return islands_inside


def uc_array_bbox(array):
    bbox = uc.Box.flipped_box()

    for elem in array:
        bbox.combine(elem.bbox())

    return bbox


def array_bbox(array):
    from .box import Box
    bbox = Box.flipped_box()

    if len(array) == 0:
        return bbox
    
    if hasattr(array[0], 'bbox'):
        f = lambda o: o.bbox()

    elif isinstance(array[0], Box):
        f = lambda o: o

    else:
        assert False

    for o in array:
        bbox.combine(f(o))

    return bbox



from ..tdensity import TDensityValue, TDensityTierValue

class IslandWrapper:

    def __init__(self, island, scale_length=1.0):
        self._island = island
        self._scale_length = scale_length

    def get(self):
        return self._island
    
    def scale(self, factor, pivot=None):
        if not pivot:
            pivot = self._island.bbox().center()

        return IslandWrapper(self._island.scale(factor, factor, pivot), scale_length=self._scale_length)

    def calc_tdensity(self, tex_size):
        tdensity = self._island.texel_density(uc.CoordSpace.GLOBAL)
        return TDensityValue.from_f(tex_size * tdensity / self._scale_length)

    def set_tdensity(self, tex_size, tdensity_value : TDensityTierValue, pivot=None):
        assert tex_size > 0
        assert tdensity_value.is_defined()

        tdensity = self.calc_tdensity(tex_size)

        if not tdensity.is_defined():
            raise ValueError()

        s_factor = tdensity_value.to_f() / tdensity.to_f()
        return self.scale(s_factor, pivot)
