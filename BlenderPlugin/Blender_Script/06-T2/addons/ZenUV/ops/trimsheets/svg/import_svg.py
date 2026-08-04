# SPDX-License-Identifier: GPL-2.0-or-later
# taken from: https://github.com/blender/blender-addons/blob/master/io_curve_svg/import_svg.py
# "author": "JM Soler, Sergey Sharybin"
# "author of trim import": "Alex Zhornyak"

# Copyright 2022, Alex Zhornyak

import re
import xml.dom.minidom
from math import tan, pi
import json

import bpy
from mathutils import Vector, Matrix
from bpy.app.translations import pgettext_tip as tip_
from ZenUV.utils.blender_zen_utils import ZenPolls

from . import svg_colors
from .svg_util import (
    units,
    srgb_to_linearrgb,
    parse_array_of_floats,
    read_float)

from ..trimsheet_utils import ZuvTrimsheetUtils

# ## Common utilities ##

REGEX_DATA_URL = re.compile(r"^data:([^,]*),(.*)")


SVGEmptyStyles = {
    'useFill': None,
    'fill': None,
    'stroke': None}


def SVGCreateTrim(p_data):
    """
    Create new Trim
    """
    p_data = p_data.get("trim_data")
    p_data.trimsheet.add()
    p_data.trimsheet[-1].create_uuid()

    return p_data.trimsheet[-1]


def SVGFinishTrim():
    """
    Finish trim creation
    """

    pass


def SVGFlipHandle(x, y, x1, y1):
    """
    Flip handle around base point
    """

    x = x + (x - x1)
    y = y + (y - y1)

    return x, y


def SVGParseCoord(coord, size):
    """
    Parse coordinate component to common basis

    Needed to handle coordinates set in cm, mm, inches.
    """

    token, last_char = read_float(coord)
    val = float(token)
    unit = coord[last_char:].strip()  # strip() in case there is a space

    if unit == '%':
        return float(size) / 100.0 * val
    return val * units[unit]


def SVGRectFromNode(node, p_data):
    """
    Get display rectangle from node
    """

    w = p_data['rect'][0]
    h = p_data['rect'][1]

    if node.getAttribute('viewBox'):
        viewBox = node.getAttribute('viewBox').replace(',', ' ').split()
        w = SVGParseCoord(viewBox[2], w)
        h = SVGParseCoord(viewBox[3], h)
    else:
        if node.getAttribute('width'):
            w = SVGParseCoord(node.getAttribute('width'), w)

        if node.getAttribute('height'):
            h = SVGParseCoord(node.getAttribute('height'), h)

    return (w, h)


def SVGMatrixFromNode(node, p_data):
    """
    Get transformation matrix from given node
    """

    tagName = node.tagName.lower()
    tags = ['svg:svg', 'svg:use', 'svg:symbol']

    if tagName not in tags and 'svg:' + tagName not in tags:
        return Matrix()

    rect = p_data['rect']
    has_user_coordinate = (len(p_data['rects']) > 1)

    m = Matrix()
    x = SVGParseCoord(node.getAttribute('x') or '0', rect[0])
    y = SVGParseCoord(node.getAttribute('y') or '0', rect[1])
    w = SVGParseCoord(node.getAttribute('width') or str(rect[0]), rect[0])
    h = SVGParseCoord(node.getAttribute('height') or str(rect[1]), rect[1])

    m = Matrix.Translation(Vector((x, y, 0.0)))
    if has_user_coordinate:
        if rect[0] != 0 and rect[1] != 0:
            m = m @ Matrix.Scale(w / rect[0], 4, Vector((1.0, 0.0, 0.0)))
            m = m @ Matrix.Scale(h / rect[1], 4, Vector((0.0, 1.0, 0.0)))

    if node.getAttribute('viewBox'):
        viewBox = node.getAttribute('viewBox').replace(',', ' ').split()
        vx = SVGParseCoord(viewBox[0], w)
        vy = SVGParseCoord(viewBox[1], h)
        vw = SVGParseCoord(viewBox[2], w)
        vh = SVGParseCoord(viewBox[3], h)

        if vw == 0 or vh == 0:
            return m

        if has_user_coordinate or (w != 0 and h != 0):
            sx = w / vw
            sy = h / vh
            scale = min(sx, sy)
        else:
            scale = 1.0
            w = vw
            h = vh

        tx = (w - vw * scale) / 2
        ty = (h - vh * scale) / 2
        m = m @ Matrix.Translation(Vector((tx, ty, 0.0)))

        m = m @ Matrix.Translation(Vector((-vx, -vy, 0.0)))
        m = m @ Matrix.Scale(scale, 4, Vector((1.0, 0.0, 0.0)))
        m = m @ Matrix.Scale(scale, 4, Vector((0.0, 1.0, 0.0)))

    return m


def SVGParseTransform(transform):
    """
    Parse transform string and return transformation matrix
    """

    m = Matrix()
    r = re.compile(r'\s*([A-z]+)\s*\((.*?)\)')

    for match in r.finditer(transform):
        func = match.group(1)
        params = match.group(2)
        params = params.replace(',', ' ').split()

        proc = SVGTransforms.get(func)
        if proc is None:
            raise Exception('Unknown transform function: ' + func)

        m = m @ proc(params)

    return m


def SVGGetMaterial(color, p_data):
    """
    Get material for specified color
    """

    materials = p_data['materials']
    rgb_re = re.compile(r'^\s*rgb\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)\s*$')

    if color in materials:
        return materials[color]

    diff = None
    if color.startswith('#'):
        color = color[1:]

        if len(color) == 3:
            color = color[0] * 2 + color[1] * 2 + color[2] * 2

        diff = (int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16))
    elif color in svg_colors.SVGColors:
        diff = svg_colors.SVGColors[color]
    elif rgb_re.match(color):
        c = rgb_re.findall(color)[0]
        diff = (float(c[0]), float(c[1]), float(c[2]))
    else:
        return None

    diffuse_color = ([x / 255.0 for x in diff])

    if p_data['do_colormanage']:
        diffuse_color[0] = srgb_to_linearrgb(diffuse_color[0])
        diffuse_color[1] = srgb_to_linearrgb(diffuse_color[1])
        diffuse_color[2] = srgb_to_linearrgb(diffuse_color[2])

    materials[color] = diffuse_color.copy()

    return materials[color]


def SVGTransformTranslate(params):
    """
    translate SVG transform command
    """

    tx = float(params[0])
    ty = float(params[1]) if len(params) > 1 else 0.0

    return Matrix.Translation(Vector((tx, ty, 0.0)))


def SVGTransformMatrix(params):
    """
    matrix SVG transform command
    """

    a = float(params[0])
    b = float(params[1])
    c = float(params[2])
    d = float(params[3])
    e = float(params[4])
    f = float(params[5])

    return Matrix(((a, c, 0.0, e),
                   (b, d, 0.0, f),
                   (0, 0, 1.0, 0),
                   (0, 0, 0.0, 1)))


def SVGTransformScale(params):
    """
    scale SVG transform command
    """

    sx = float(params[0])
    sy = float(params[1]) if len(params) > 1 else sx

    m = Matrix()

    m = m @ Matrix.Scale(sx, 4, Vector((1.0, 0.0, 0.0)))
    m = m @ Matrix.Scale(sy, 4, Vector((0.0, 1.0, 0.0)))

    return m


def SVGTransformSkewY(params):
    """
    skewY SVG transform command
    """

    ang = float(params[0]) * pi / 180.0

    return Matrix(((1.0, 0.0, 0.0),
                  (tan(ang), 1.0, 0.0),
                  (0.0, 0.0, 1.0))).to_4x4()


def SVGTransformSkewX(params):
    """
    skewX SVG transform command
    """

    ang = float(params[0]) * pi / 180.0

    return Matrix(((1.0, tan(ang), 0.0),
                  (0.0, 1.0, 0.0),
                  (0.0, 0.0, 1.0))).to_4x4()


def SVGTransformRotate(params):
    """
    skewX SVG transform command
    """

    ang = float(params[0]) * pi / 180.0
    cx = cy = 0.0

    if len(params) >= 3:
        cx = float(params[1])
        cy = float(params[2])

    tm = Matrix.Translation(Vector((cx, cy, 0.0)))
    rm = Matrix.Rotation(ang, 4, Vector((0.0, 0.0, 1.0)))

    return tm @ rm @ tm.inverted()


SVGTransforms = {'translate': SVGTransformTranslate,
                 'scale': SVGTransformScale,
                 'skewX': SVGTransformSkewX,
                 'skewY': SVGTransformSkewY,
                 'matrix': SVGTransformMatrix,
                 'rotate': SVGTransformRotate}


def SVGParseStyles(node, p_data):
    """
    Parse node to get different styles for displaying geometries
    (materials, filling flags, etc..)
    """

    styles = SVGEmptyStyles.copy()

    style = node.getAttribute('style')
    if style:
        elems = style.split(';')
        for elem in elems:
            s = elem.split(':')

            if len(s) != 2:
                continue

            name = s[0].strip().lower()
            val = s[1].strip()

            if name == 'fill':
                val = val.lower()
                if val == 'none':
                    styles['useFill'] = False
                else:
                    styles['useFill'] = True
                    styles['fill'] = SVGGetMaterial(val, p_data)
            elif name == 'stroke':
                styles['stroke'] = SVGGetMaterial(val, p_data)

    else:
        if styles['useFill'] is None:
            fill = node.getAttribute('fill')
            if fill:
                fill = fill.lower()
                if fill == 'none':
                    styles['useFill'] = False
                else:
                    styles['useFill'] = True
                    styles['fill'] = SVGGetMaterial(fill, p_data)

        if styles['useFill'] is None and p_data['style']:
            styles = p_data['style'].copy()

        p_stroke = node.getAttribute('stroke')
        if p_stroke:
            styles['stroke'] = SVGGetMaterial(p_stroke, p_data)

    return styles


def id_names_from_node(node):
    if node.getAttribute('id'):
        return node.getAttribute('id')
    return ''


class SVGGeometry:
    """
    Abstract SVG geometry
    """

    __slots__ = ('_node',       # XML node for geometry
                 '_data',    # Global SVG context (holds matrices stack, i.e.)
                 '_creating')   # Flag if geometry is already creating

    def __init__(self, node, p_data):
        """
        Initialize SVG geometry
        """

        self._node = node
        self._data = p_data
        self._creating = False

        if hasattr(node, 'getAttribute'):
            defs = self._data['defines']

            attr_id = node.getAttribute('id')
            if attr_id and defs.get('#' + attr_id) is None:
                defs['#' + attr_id] = self

            className = node.getAttribute('class')
            if className and defs.get(className) is None:
                defs[className] = self

    def _pushRect(self, rect):
        """
        Push display rectangle
        """

        self._data['rects'].append(rect)
        self._data['rect'] = rect

    def _popRect(self):
        """
        Pop display rectangle
        """

        self._data['rects'].pop()
        self._data['rect'] = self._data['rects'][-1]

    def _pushMatrix(self, matrix):
        """
        Push transformation matrix
        """

        current_matrix = self._data['matrix']
        self._data['matrix_stack'].append(current_matrix)
        self._data['matrix'] = current_matrix @ matrix

    def _popMatrix(self):
        """
        Pop transformation matrix
        """

        old_matrix = self._data['matrix_stack'].pop()
        self._data['matrix'] = old_matrix

    def _pushStyle(self, style):
        """
        Push style
        """

        self._data['styles'].append(style)
        self._data['style'] = style

    def _popStyle(self):
        """
        Pop style
        """

        self._data['styles'].pop()
        self._data['style'] = self._data['styles'][-1]

    def _transformCoord(self, point):
        """
        Transform SVG-file coords
        """

        v = Vector((point[0], point[1], 0.0))

        return self._data['matrix'] @ v

    def getNodeMatrix(self):
        """
        Get transformation matrix of node
        """

        return SVGMatrixFromNode(self._node, self._data)

    def parse(self, context: bpy.types.Context):
        """
        Parse XML node to memory
        """

        pass

    def _doCreateGeom(self, instancing):
        """
        Internal handler to create real geometries
        """

        pass

    def getTransformMatrix(self):
        """
        Get matrix created from "transform" attribute
        """

        transform = self._node.getAttribute('transform')

        if transform:
            return SVGParseTransform(transform)

        return None

    def createGeom(self, instancing):
        """
        Create real geometries
        """

        if self._creating:
            return

        self._creating = True

        matrix = self.getTransformMatrix()
        if matrix is not None:
            self._pushMatrix(matrix)

        self._doCreateGeom(instancing)

        if matrix is not None:
            self._popMatrix()

        self._creating = False


class SVGGeometryContainer(SVGGeometry):
    """
    Container of SVG geometries
    """

    __slots__ = ('_geometries',  # List of chold geometries
                 '_styles')  # Styles, used for displaying

    def __init__(self, node, p_data):
        """
        Initialize SVG geometry container
        """

        super().__init__(node, p_data)

        self._geometries = []
        self._styles = SVGEmptyStyles

    def parse(self, context: bpy.types.Context):
        """
        Parse XML node to memory
        """

        if type(self._node) is xml.dom.minidom.Element:
            self._styles = SVGParseStyles(self._node, self._data)

        self._pushStyle(self._styles)

        for node in self._node.childNodes:
            if type(node) is not xml.dom.minidom.Element:
                continue

            ob = parseAbstractNode(node, self._data, context)
            if ob is not None:
                self._geometries.append(ob)

        self._popStyle()

    def _doCreateGeom(self, instancing):
        """
        Create real geometries
        """

        for geom in self._geometries:
            geom.createGeom(instancing)

    def getGeometries(self):
        """
        Get list of parsed geometries
        """

        return self._geometries


class SVGGeometryImage(SVGGeometryContainer):
    """
    SVG Image
    """

    def __init__(self, node, p_data):
        """
        Initialize new Image
        """

        super().__init__(node, p_data)

        self._url = None
        self._media_type = None
        self._image_data = None
        self._id = None

    def parse(self, context: bpy.types.Context):
        if self._data['do_loadimage']:
            if not ZuvTrimsheetUtils.isImageEditorSpace(context):
                raise RuntimeError("Can load SVG image only in Image Editor !")

            if not self._url:
                self._url = self._node.getAttribute("href")

            if not self._url:
                self._url = self._node.getAttribute("xlink:href")

            if self._url:
                match = REGEX_DATA_URL.match(self._url)
                if match:
                    self._media_type = match.group(1).split(";")
                    self._image_data = match.group(2)
                    if 'base64' in self._media_type:
                        from base64 import b64decode
                        self._image_data = b64decode(self._image_data)
                    else:
                        from urllib.parse import unquote_to_bytes
                        self._image_data = unquote_to_bytes
                else:
                    if ZenPolls.internet_enabled():
                        import urllib.request
                        self._image_data = urllib.request.urlopen(self._url).read()
                    else:
                        raise RuntimeError("Can not load image in Blender offline mode!")

            self._id = id_names_from_node(self._node)
            if self._id:
                p_image = bpy.data.images.get(self._id)
                if p_image is None:
                    p_image = bpy.data.images.new(self._id, 8, 8)

                    p_image.pack(data=self._image_data, data_len=len(self._image_data))

                    p_image.source = 'FILE'
                    p_image.update()

                p_data = self._data.get('trim_data')
                if p_data != p_image.zen_uv:
                    self._data['trim_data'] = p_image.zen_uv

                if context.space_data.image != p_image:
                    context.space_data.image = p_image

                from ZenUV.prop.zuv_preferences import get_prefs
                addon_prefs = get_prefs()
                if addon_prefs.trimsheet.mode != 'IMAGE':
                    addon_prefs.trimsheet.mode = 'IMAGE'


class SVGGeometryDEFS(SVGGeometryContainer):
    """
    Container for referenced elements
    """

    def createGeom(self, instancing):
        """
        Create real geometries
        """

        pass


class SVGGeometryG(SVGGeometryContainer):
    """
    Geometry group
    """

    pass


class SVGGeometryRECT(SVGGeometry):
    """
    SVG rectangle
    """

    __slots__ = ('_rect',  # coordinate and dimensions of rectangle
                 '_styles')  # Styles, used for displaying

    def __init__(self, node, p_data):
        """
        Initialize new rectangle
        """

        super().__init__(node, p_data)

        self._rect = ('0', '0', '0', '0')
        self._styles = SVGEmptyStyles

    def parse(self, context: bpy.types.Context):
        """
        Parse SVG rectangle node
        """

        self._styles = SVGParseStyles(self._node, self._data)

        rect = []
        for attr in ['x', 'y', 'width', 'height']:
            val = self._node.getAttribute(attr)
            rect.append(val or '0')

        self._rect = (rect)

    def _doCreateGeom(self, instancing):
        """
        Create real geometries
        """

        # Run-time parsing -- percents would be correct only if
        # parsing them now
        crect = self._data['rect']
        rect = []

        for i in range(4):
            rect.append(SVGParseCoord(self._rect[i], crect[i % 2]))

        # Geometry creation
        t_trim_dict = {}

        x, y = rect[0], rect[1]
        w, h = rect[2], rect[3]

        pt1 = self._transformCoord((x, y))
        pt2 = self._transformCoord((x + w, y + h))

        maxY = self._data.get('_maxY', 0)
        if maxY == 0:
            raise RuntimeError('SVG viewbox height is not defined!')

        maxX = self._data.get('_maxX', 0)
        if maxX == 0:
            raise RuntimeError('SVG viewbox width is not defined!')

        p_trim_name = None

        def get_node_name(node):
            name = node.tagName.lower()

            if name.startswith('svg:'):
                name = name[4:]

            return name

        for node in self._node.parentNode.childNodes:
            if node == self._node:
                continue

            if node.nodeType != node.ELEMENT_NODE:
                continue

            if p_trim_name:
                break

            name = get_node_name(node)

            if name == 'text':
                for subnode in node.childNodes:
                    if p_trim_name:
                        break

                    if subnode.nodeType == subnode.TEXT_NODE:
                        p_trim_name = subnode.nodeValue
                        break

                    if subnode.nodeType == subnode.ELEMENT_NODE:
                        name = get_node_name(subnode)
                        if name == 'tspan':
                            for subspan in subnode.childNodes:
                                if p_trim_name:
                                    break
                                if subspan.nodeType == subspan.TEXT_NODE:
                                    p_trim_name = subspan.nodeValue
                                    break
            elif name == 'trim:trim':
                for subnode in node.childNodes:
                    if subnode.nodeType == subnode.TEXT_NODE:
                        if subnode.nodeValue:
                            t_trim_dict = json.loads(subnode.nodeValue)
                        break

        t_trim_dict['rect'] = (pt1[0] / maxX, (maxY - pt1[1]) / maxY, pt2[0] / maxX, (maxY - pt2[1]) / maxY)

        if p_trim_name is None:
            p_trim_name = id_names_from_node(self._node)

        p_trim = None

        if p_trim_name:
            if self._data['do_mode'] == 'REPLACE':
                p_trim = self._data['trim_name_table'].get(p_trim_name, None)
                if p_trim:
                    # allow replace only once !
                    del self._data['trim_name_table'][p_trim_name]
        else:
            p_trim_name = 'Trim'

        b_has_color = False
        if self._styles.get('useFill', None):
            p_fill = self._styles.get('fill', None)
            if p_fill is not None:
                b_has_color = True
                t_trim_dict['color'] = p_fill

        p_stroke = self._styles.get('stroke')
        if p_stroke:
            t_trim_dict['border_color'] = p_stroke
            if not b_has_color:
                t_trim_dict['color'] = p_stroke

        if p_trim is None:
            p_trim = SVGCreateTrim(self._data)
            p_trim.name_ex = p_trim_name

            if 'color' not in t_trim_dict:
                p_trim.color = ZuvTrimsheetUtils.getTrimsheetGeneratedColor(self._data.get("trim_data"))

        p_trim.from_dict(t_trim_dict)

        if self._data['do_select']:
            p_trim.selected = True

        SVGFinishTrim()


class SVGGeometrySVG(SVGGeometryContainer):
    """
    Main geometry holder
    """

    def _doCreateGeom(self, instancing):
        """
        Create real geometries
        """

        rect = SVGRectFromNode(self._node, self._data)

        matrix = self.getNodeMatrix()

        # Better SVG compatibility: match svg-document units
        # with blender units

        viewbox = []
        unit = ''

        if self._node.getAttribute('height'):
            raw_height = self._node.getAttribute('height')
            token, last_char = read_float(raw_height)
            unit = raw_height[last_char:].strip()

        if self._node.getAttribute('viewBox'):
            viewbox = parse_array_of_floats(self._node.getAttribute('viewBox'))

            if len(viewbox) == 4:
                if unit in ('cm', 'mm', 'in', 'pt', 'pc'):
                    # convert units to BU:
                    unitscale = units[unit] / 90 * 1000 / 39.3701

                    # apply blender unit scale:
                    unitscale = unitscale / bpy.context.scene.unit_settings.scale_length

                    matrix = matrix @ Matrix.Scale(unitscale, 4, Vector((1.0, 0.0, 0.0)))
                    matrix = matrix @ Matrix.Scale(unitscale, 4, Vector((0.0, 1.0, 0.0)))

                if '_maxY' not in self._data:
                    self._data['_maxY'] = viewbox[3] - viewbox[1]
                    self._data['_maxX'] = viewbox[2] - viewbox[0]

        # match document origin with 3D space origin.
        # if self._node.getAttribute('viewBox'):
            # viewbox = parse_array_of_floats(self._node.getAttribute('viewBox'))
            # matrix = matrix @ matrix.Translation([0.0, - viewbox[1] - viewbox[3], 0.0])

        self._pushMatrix(matrix)
        self._pushRect(rect)

        super()._doCreateGeom(False)

        self._popRect()
        self._popMatrix()


class SVGLoader(SVGGeometryContainer):
    """
    SVG file loader
    """

    def getTransformMatrix(self):
        """
        Get matrix created from "transform" attribute
        """

        # SVG document doesn't support transform specification
        # it can't even hold attributes

        return None

    def __init__(self, context: bpy.types.Context, filepath, p_props):
        """
        Initialize SVG loader
        """
        node = xml.dom.minidom.parse(filepath)

        m = Matrix()
        # m = m @ Matrix.Scale(1.0 / 90.0 * 0.3048 / 12.0, 4, Vector((1.0, 0.0, 0.0)))
        # m = m @ Matrix.Scale(-1.0 / 90.0 * 0.3048 / 12.0, 4, Vector((0.0, 1.0, 0.0)))

        rect = (0, 0)

        self._data = {
            'defines': {},
            'rects': [rect],
            'rect': rect,
            'matrix_stack': [],
            'matrix': m,
            'materials': {},
            'styles': [None],
            'style': None,
            'do_colormanage':  getattr(p_props, 'colormanage', False),
            'do_loadimage': getattr(p_props, 'load_image', True),
            'do_mode': getattr(p_props, 'mode', 'ADD'),
            'do_select': getattr(p_props, 'select', True),
            'trim_data': None,
            'trim_active_name': None}

        super().__init__(node, self._data)

    def prepare(self, context: bpy.types.Context):
        # data could be set by image insed
        p_trim_data = self._data.get('trim_data', None)
        if p_trim_data is None:
            # let's set by the current active Image or Scene
            p_trim_data = ZuvTrimsheetUtils.getTrimsheetOwner(context)

        if p_trim_data is None:
            raise RuntimeError('No active Trim instance!')

        was_active_name = None
        if p_trim_data.trimsheet_index in range(0, len(p_trim_data.trimsheet)):
            was_active_name = p_trim_data.trimsheet[p_trim_data.trimsheet_index].name

        self._data['trim_data'] = p_trim_data
        self._data['trim_active_name'] = was_active_name

        p_mode = self._data['do_mode']
        if p_mode == 'CLEAR':
            p_trim_data.trimsheet.clear()
            p_trim_data.trimsheet_index = -1
        elif p_mode == 'REPLACE':
            self._data['trim_name_table'] = {p_trim.name: p_trim for p_trim in p_trim_data.trimsheet}

    def finalize(self):
        p_data = self._data.get('trim_data', None)
        if p_data:
            was_active_name = self._data.get("trim_active_name", None)
            i_new_index = min(0, len(p_data.trimsheet) - 1)
            if was_active_name:
                for idx, p_trim in enumerate(p_data.trimsheet):
                    if was_active_name == p_trim.name:
                        i_new_index = idx
                        break

            if p_data.trimsheet_index != i_new_index:
                p_data.trimsheet_index = i_new_index

            p_data.trimsheet_mark_geometry_update()

            ZuvTrimsheetUtils.auto_highlight_trims(bpy.context)

            ZuvTrimsheetUtils.fix_undo()
            ZuvTrimsheetUtils.update_imageeditor_in_all_screens()


svgGeometryClasses = {
    'svg': SVGGeometrySVG,
    'defs': SVGGeometryDEFS,
    'rect': SVGGeometryRECT,
    'g': SVGGeometryG,
    'image': SVGGeometryImage
}


def parseAbstractNode(node, data, context: bpy.types.Context):
    name = node.tagName.lower()

    if name.startswith('svg:'):
        name = name[4:]

    geomClass = svgGeometryClasses.get(name)

    if geomClass is not None:
        ob = geomClass(node, data)
        ob.parse(context)

        return ob

    return None


def load_svg(context: bpy.types.Context, filepath, p_props):
    """
    Load specified SVG file
    """

    loader = SVGLoader(context, filepath, p_props)
    loader.parse(context)
    loader.prepare(context)
    loader.createGeom(False)
    loader.finalize()


def load(operator: bpy.types.Operator, context: bpy.types.Context, filepath=""):

    # error in code should raise exceptions but loading
    # non SVG files can give useful messages.
    p_props = operator.properties
    p_props['colormanage'] = False

    try:
        load_svg(context, filepath, p_props)
    except (xml.parsers.expat.ExpatError, UnicodeEncodeError) as e:
        import traceback
        traceback.print_exc()

        operator.report({'WARNING'}, tip_("Unable to parse XML, %s:%s for file %r") % (type(e).__name__, e, filepath))
        return {'CANCELLED'}
    except Exception as e:
        operator.report({'WARNING'}, str(e))
        return {'CANCELLED'}

    return {'FINISHED'}
