import re

from reportlab.graphics.shapes import Drawing
from svglib import svglib
from svglib.svglib import SvgRenderer, Svg2RlgAttributeConverter, NodeTracker, Box, logger

# svglib 2 reads a length with no unit as a CSS pixel and draws it at 0.75pt; svglib 1 drew it at 1pt.
# SVGScaler writes its lengths in points, so the scale svglib applies is undone here.
PX_TO_PT = getattr(svglib, 'PX_TO_PT', 1)
DEFAULT_FONT_SIZE = '12'


class PointLengthConverter(Svg2RlgAttributeConverter):
    """
    Reads lengths for a drawing whose user unit is a point. svglib 2 reads a length with a physical unit
    (30mm, 12pt) as pixels, which the renderer's undone pixel scale would leave a third too long.
    """
    physical_length = re.compile(r'[-+]?(\d+\.?\d*|\.\d+)([eE][-+]?\d+)?(pt|pc|mm|cm|in|q)')

    def convertLength(self, svgAttr, *args, **kwargs):
        length = super().convertLength(svgAttr, *args, **kwargs)
        # a list of lengths is read a length at a time, through this method
        if self.physical_length.fullmatch(svgAttr.strip()):
            length *= PX_TO_PT
        return length


class SvgScaledRenderer(SvgRenderer):
    def __init__(self, path, units, width, height):
        super().__init__(path)
        self.units = units
        self.width = width
        self.height = height
        if PX_TO_PT != 1:
            # keep what svglib set up on its own converter, such as the matcher for the svg's stylesheet
            converter = PointLengthConverter()
            converter.__dict__.update(vars(self.attrConverter))
            self.attrConverter = converter
            self.shape_converter.attrConverter = converter

    def render(self, svg_node):
        # svglib 2 gives text with no font size 12pt before its pixel scale, so set the size it inherits
        if svg_node.get('font-size') is None:
            svg_node.set('font-size', DEFAULT_FONT_SIZE)
        node = NodeTracker.from_xml_root(svg_node)
        if PX_TO_PT != 1:
            # rem is read against the root font size
            self._set_root_font_size(node)
        view_box = Box(0, 0, self.width, self.height)
        main_group = self.renderSvg(node, outermost=True)
        for xlink in self.waiting_use_nodes.keys():
            logger.debug("Ignoring unavailable object width ID '%s'." % xlink)
        if PX_TO_PT != 1:
            main_group.scale(1 / PX_TO_PT, 1 / PX_TO_PT)
        main_group.translate(0 - view_box.x, -view_box.height - view_box.y)
        drawing = Drawing(self.width, self.height)
        drawing.add(main_group)
        return drawing
