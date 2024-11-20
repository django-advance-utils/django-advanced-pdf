import re
import warnings

import math
from lxml import etree

from django_advanced_pdf.engine.svg_scaler import SVGScaler


class SVGScaledRuler(SVGScaler):
    __slots__ = ['svg', 'input_pattern', 'length']

    def __init__(self):
        super().__init__()
        self.svg = None
        self.input_pattern = r'(\d+(\.\d+)?)(cm|mm|m)'
        self.length = None

    def _parse_length(self, length):
        match = re.match(self.input_pattern, length.strip())
        print(match.group(1))
        if not match:
            raise ValueError('please provide a valid length, say, "50cm".')
        value, units = float(match.group(1)), match.group(3)
        if (rounded_value := math.ceil(value)) != value:
            warnings.warn('value has been rounded')

        match units:
            case 'mm':
                length = rounded_value * 0.1
                units = 'cm'
            case 'cm':
                length = rounded_value * 1
            case _:
                length = None

        if length is None or length < 1:
            raise ValueError('the real object length must be greater than 1cm.')
        return length, units

    def _draw_line(self, x1="0", y1="0", x2="0", y2="0"):
        stroke_width = 5 / self.units
        attrs = {'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2, 'stroke': 'black', 'stroke-width': f'{stroke_width}'}
        etree.SubElement(self.svg,
                         _tag='line',
                         attrib=attrs)

    def _draw_text(self, text, x="0", y="0"):
        attrs = {'x': x, 'y': y, 'text-anchor': 'middle', 'font-weight': 'lighter'}
        ele = etree.SubElement(self.svg,
                               _tag='text',
                               attrib=attrs)
        ele.text = text

    def _steps(self, rule_length, n_ticks):
        if n_ticks < 2 or rule_length <= 0:
            raise ValueError("number of ticks must be >= 2 and total_distance must be > 0")
        spacing = rule_length / (n_ticks - 1)
        marker_positions = [f'{self.rnd(i * spacing)}' for i in range(n_ticks)]
        return marker_positions

    def _draw_ruler(self, scaled_length, ratio_text):
        ticks = int(scaled_length * 10)
        lin_steps = self._steps(rule_length=self.length, n_ticks=ticks)
        tick_size_factor = -0.5 / self.ratio
        l_tick_size = str(tick_size_factor)
        m_tick_size = str(tick_size_factor * 0.75)
        s_tick_size = str(tick_size_factor * 0.35)

        marker_location = str(-1 * (0.6 / self.ratio))
        x_ratio_location, y_ratio_location = str(0.3 / self.ratio), str(0.4 / self.ratio)

        self._draw_line(x2=f'{self.length}')
        self._draw_text(x=x_ratio_location, y=y_ratio_location, text=ratio_text)

        counter = 1
        for i in range(1, len(lin_steps) + 1, 1):
            step = lin_steps[i - 1]
            if i == 1:
                self._draw_line(x1=step, x2=step, y2=l_tick_size)
                self._draw_text(x=step, y=marker_location, text=f'0')
            elif i % 10 == 0:
                self._draw_line(x1=step, x2=step, y2=l_tick_size)
                if counter % 2 == 0:
                    self._draw_text(x=step, y=marker_location, text=f'{i * 10}')
                counter += 1
            elif i % 5 == 0:
                self._draw_line(x1=step, x2=step, y2=m_tick_size)
            else:
                self._draw_line(x1=step, x2=step, y2=s_tick_size)


    def render(self, ratio, real_length):
        self.ratio = ratio
        self.length, self.units = self._parse_length(length=real_length)

        if (scaled_length := self.ratio * self.length) < 1:
            raise ValueError('ruler not within size constraint of ratio * length.')
        elif (rounded_scaled_length := math.ceil(scaled_length)) != scaled_length:
            scaled_length = rounded_scaled_length
            warnings.warn('the value had to be rounded because length * ratio was not a multiple of 10')

        self.svg = etree.Element('svg', nsmap={'svg': 'http://www.w3.org/2000/svg'})

        self._draw_ruler(scaled_length=scaled_length, ratio_text=ratio)

        self.scale(ratio=self.ratio, units=self.units, svg=self.svg)
        return self.svg
