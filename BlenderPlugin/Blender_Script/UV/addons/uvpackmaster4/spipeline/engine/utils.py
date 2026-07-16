import sys
from typing import Generic, TypeVar
import re

from .uc_entry import uc


UTIL_COLOR_ARRAY =  [
		(0.0,   0.0,    1.0),
        (1.0,   1.0,    0.0),
        (0.0,   1.0,    1.0),
        (0.0,   1.0,    0.0),
        (1.0,   0.25,   0.0),
        (1.0,   0.0,    0.25),
        (0.25,  0.0,    1.0),
        (0.0,   0.25,   1.0),
        (1.0,   0.0,    0.0),
        (0.5,   0.0,    0.5),
        (1.0,   0.0,    0.5),
        (1.0,   0.0,    1.0),
        (0.5,   1.0,    0.0),
    ]


UUID_REGEX = re.compile(r"^[0-9a-fA-F]{32}$")

def is_uuid_strict(s):
    return isinstance(s, str) and bool(UUID_REGEX.match(s))


def get_class_path(obj):
    t = type(obj)
    return "{}:{}".format(t.__module__, t.__qualname__)


def gather_annotations(cls):
    annotations = {}
    mro = cls.__mro__

    for base in reversed(mro):
        if base is object:
            continue

        base_ann = getattr(base, "__annotations__", {})
        annotations.update(base_ann)

    return annotations


def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


def rgb_to_rgba(rgb_color):
    return (rgb_color[0], rgb_color[1], rgb_color[2], 1.0)


def flag_islands(input_islands, flagged_islands):
    if len(flagged_islands) == 0:
        return

    input_islands.clear_flags(uc.IslandFlag.SELECTED)
    flagged_islands.set_flags(uc.IslandFlag.SELECTED)

    to_send = input_islands.clone()
    to_send += flagged_islands
    uc.packer.send_out_islands(to_send, send_flags=True)


# def box_from_coords(coords):
#     return Box(Point(coords[0], coords[1]), Point(coords[2], coords[3]))


def area_to_string(area):
    return "{:.3f}".format(area)


def split_islands(islands, pred):
    set1 = uc.IslandSet()
    set2 = uc.IslandSet()

    for island in islands:
        (set1 if pred(island) else set2).append(island)

    return set1, set2


T = TypeVar("T")

class ShadowedCollectionProperty(Generic[T]):

    def __init__(self, elem_type, factory=None, remove_callback=None):
        self.elem_type = elem_type
        self.collection = []
        self.key_id = 'name'
        self.factory = factory if factory else lambda: self.elem_type()
        self.remove_callback = remove_callback

    def copy_from(self, other):
        self.clear()
        for other_elem in other:
            new_elem = self.add()
            new_elem.copy_from(other_elem)

    def add(self):
        self.collection.append(self.factory())
        return self.collection[-1]
    
    def append(self, elem):
        self.collection.append(elem)

    def clear(self):
        if self.remove_callback:
            while len(self) > 0:
                self.remove(0)
            return
        
        self.collection.clear()

    def remove(self, idx):
        elem_to_del = self.collection[idx]
        del self.collection[idx]

        if self.remove_callback:
            self.remove_callback(elem_to_del)

    def find(self, key):
        try:
            first_idx = next(idx for idx, elem in enumerate(self) if getattr(elem, self.key_id) == key)
            return first_idx
        except StopIteration:
            pass

        return -1

    def __len__(self):
        return len(self.collection)

    def __getitem__(self, idx):
            return self.collection[idx]

    def __iter__(self):
        return iter(self.collection)
