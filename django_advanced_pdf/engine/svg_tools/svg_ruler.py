import io
import re
import warnings

import math
from lxml import etree
from reportlab.graphics import renderPDF
from reportlab.lib.units import mm
from svglib.svglib import svg2rlg
from xml.etree import ElementTree

from django_advanced_pdf.engine.svg_tools.svg_scaler import SVGScaler


class SVGScaledRuler(SVGScaler):
    __slots__ = ['svg',
                 'input_pattern',
                 'length',
                 'offset_y',
                 'offset_x',
                 'line_offset',
                 'inverse',
                 'minor_tick_count']

    def __init__(self):
        super().__init__()
        self.svg = None
        self.input_pattern = r'(\d+(\.\d+)?)(cm|mm|m)'
        self.length = None
        self.offset_y = None
        self.offset_x = None
        self.line_offset = None
        self.inverse = None
        self.minor_tick_count = None

    def _parse_length(self, length):
        match = re.match(self.input_pattern, length.strip())
        if not match:
            raise ValueError('please provide a valid length, say, "50cm".')
        value, units = float(match.group(1)), match.group(3)
        if (rounded_value := math.ceil(value)) != value:
            warnings.warn('value has been rounded')

        match units:
            case 'mm':
                length = rounded_value
            case 'cm':
                length = rounded_value * 10
                units = 'mm'
            case _:
                length = None

        if length is None or length < 1:
            raise ValueError('the real object length must be greater than 1cm.')
        return length, units

    def _draw_line(self, x1=0, y1=0, x2=0, y2=0):
        stroke_width = self.rnd(0.25 / self.scaling_factor)
        attrs = {'x1': f'{x1}',
                 'y1': f'{y1}',
                 'x2': f'{x2}',
                 'y2': f'{y2}',
                 'stroke': 'black',
                 'stroke-width': f'{stroke_width}'}
        etree.SubElement(self.svg,
                         _tag='line',
                         attrib=attrs)

    def _draw_text(self, text, x=0, y=0, text_anchor='middle'):
        x, y = self.rnd(x), self.rnd(y)
        attrs = {'x': f'{x}', 'y': f'{y}', 'text-anchor': text_anchor, 'font-weight': 'lighter'}
        ele = etree.SubElement(self.svg,
                               _tag='text',
                               attrib=attrs)
        ele.text = text

    def _steps(self, rule_length, n_ticks):
        if n_ticks < 2 or rule_length <= 0:
            raise ValueError("number of ticks must be >= 2 and total_distance must be > 0")
        spacing = rule_length / (n_ticks - 1)
        marker_positions = [self.rnd(i * spacing) for i in range(n_ticks)]
        return marker_positions

    def _draw_ruler(self, ratio_text):
        self._draw_line(x1=0, x2=self.length, y1=self.line_offset,  y2=self.line_offset)
        self._draw_text(text=ratio_text, text_anchor='right', x=0, y=self.offset_y)

        relative_length_from_y = lambda offset, scalar: offset - (self.offset_y*scalar)
        l_tick_sz = relative_length_from_y(offset=self.line_offset, scalar=.35)
        m_tick_sz = relative_length_from_y(offset=self.line_offset, scalar=.25)
        s_tick_sz = relative_length_from_y(offset=self.line_offset, scalar=.1)
        tick_text_offset = relative_length_from_y(offset=l_tick_sz, scalar=.1)

        lin_steps = self._steps(rule_length=self.length, n_ticks=self.minor_tick_count)
        for i in range(1, len(lin_steps) + 1, 1):
            step = lin_steps[i - 1]
            if i == 1:
                self._draw_line(x1=step, x2=step, y1=self.line_offset, y2=l_tick_sz)
                self._draw_text(x=step, y=tick_text_offset, text=f'0')
            elif i % 10 == 0:
                scaled_value = (i*self.inverse)
                tick_text = int(scaled_value)
                self._draw_line(x1=step, x2=step, y1=self.line_offset, y2=l_tick_sz)
                self._draw_text(x=step, y=tick_text_offset, text=f'{tick_text}')
            elif i % 5 == 0:
                self._draw_line(x1=step, x2=step, y1=self.line_offset, y2=m_tick_sz)
            else:
                self._draw_line(x1=step, x2=step, y1=self.line_offset, y2=s_tick_sz)

    def render(self, ratio, units='mm', offset_y=12, length=50, minor_tick_count=50):
        self.ratio = ratio
        self.units = units
        self.inverse = 1 / self.ratio
        self.length = length * self.inverse
        self.minor_tick_count = minor_tick_count

        self.offset_y = offset_y * self.inverse
        self.offset_x = self.length + 2 * self.inverse
        self.line_offset = self.offset_y - 4 * self.inverse

        self.svg = etree.Element('svg')
        self.svg.attrib['width'] = f'{self.offset_x}'
        self.svg.attrib['height'] = f'{self.offset_y}'

        self._draw_ruler(ratio_text=ratio)
        self.scale(ratio=ratio, units=units, svg=self.svg)

        return self.svg

    def draw_to_canvas(self, canvas, x, y, ratio, units='mm', offset_y=12, length=50, minor_tick_count=50):
        svg = self.render(ratio=ratio, units=units, offset_y=offset_y, length=length, minor_tick_count=minor_tick_count)
        svg_string = ElementTree.tostring(svg).decode("utf-8")
        drawing = svg2rlg(io.StringIO(svg_string))
        renderPDF.draw(drawing, canvas, x * mm, y * mm)