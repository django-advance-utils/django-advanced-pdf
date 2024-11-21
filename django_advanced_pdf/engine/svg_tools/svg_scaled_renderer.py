from reportlab.graphics.shapes import Drawing
from svglib.svglib import SvgRenderer, NodeTracker, Box, logger


class SvgScaledRenderer(SvgRenderer):
    def __init__(self, path, units, width, height):
        super().__init__(path)
        self.units = units
        self.width = width
        self.height = height

    def render(self, svg_node):
        node = NodeTracker.from_xml_root(svg_node)
        view_box = Box(0, 0, self.width, self.height)
        main_group = self.renderSvg(node, outermost=True)
        for xlink in self.waiting_use_nodes.keys():
            logger.debug("Ignoring unavailable object width ID '%s'." % xlink)
        main_group.translate(0 - view_box.x, -view_box.height - view_box.y)
        drawing = Drawing(self.width, self.height)
        drawing.add(main_group)
        return drawing
