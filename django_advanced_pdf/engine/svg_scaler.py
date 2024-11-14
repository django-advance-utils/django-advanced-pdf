import re

from lxml import etree
from reportlab.lib.units import inch, mm, cm


class SVGScaler:
    __slots__ = ['_ratio',
                 '_ratio_pattern',
                 '_units',
                 '_svg_tag',
                 '_standard_attributes',
                 '_other_attributes',
                 '_attributes']

    def __init__(self):
        # TODO: Handle multiple transform functions passed
        # TODO: Handle negative/float values passed to Path
        # TODO: Assume MM if data-units not provided
        # TODO: Annotations.
        # TODO: Rule.
        self._ratio = None
        self._ratio_pattern = r'^1:(\d+)$'
        self._units = None
        self._svg_tag = None
        self._standard_attributes = ['width', 'height', 'x', 'y', 'x1', 'y1', 'x2', 'y2']
        self._other_attributes = ['style', 'transform', 'd']
        self._attributes = self._standard_attributes + self._other_attributes

    @property
    def ratio(self):
        return self._ratio

    @ratio.setter
    def ratio(self, value: str):
        match =  re.fullmatch(self._ratio_pattern, value)
        if not match:
            raise ValueError('format must be "1:n" where 1 unit on the scale drawing represents integer n real units')
        n = int(match.group(1))
        if not n > 1: raise ValueError("The ratio 1:n cannot have n < 1")
        self._ratio = 1/n

    @property
    def units(self):
        return self._units

    @units.setter
    def units(self, value: str):
        lookup = {'inch': inch, 'mm': mm, 'cm': cm}
        if value not in lookup: raise ValueError('units must be string "mm", "cm" or "inch"')
        self._units = lookup[value]

    @property
    def scaling_factor(self):
        return self.ratio*self.units

    @property
    def svg_tag(self):
        return self._svg_tag

    @svg_tag.setter
    def svg_tag(self, value):
        ns_and_tag = value.split('}')
        self._svg_tag = ns_and_tag[-1]

    @staticmethod
    def rnd(value):
        result = round(value, 3)
        return result

    @staticmethod
    def _strip_units(value):
        units = ['mm', 'in', 'cm']
        for unit in units:
            if value.endswith(unit):
                value = value.replace(unit, '')
                break
        return value

    def _set_scaled_style(self, element, value):
        styles = value.split(';')
        for idx, string in enumerate(styles):
            if 'stroke-width' in string:
                txt, size = string.split(':')
                size = self._coerce_and_scale_value(size)
                styles[idx] = f'{txt}:{size}'
                break
        element.set('style', ';'.join(styles))

    def _set_scaled_path(self, element, value):
        handler = lambda match: self._coerce_and_scale_value(match.group(0))
        scaled_path = re.sub(r'-?\d*\.?\d+', handler, value)
        element.set('d', f'{scaled_path}')

    def _set_scaled_transform(self, element, value):
        start_txt = 'translate('
        end_txt = ')'
        start, end = value.find(start_txt), value.find(end_txt)
        x, y = value[start + len(start_txt): end].split(',')
        x, y = self._coerce_and_scale_value(x), self._coerce_and_scale_value(y)
        element.set('transform', f'translate({x} {y})')

    def _match_other_attributes(self, element, attr, value):
        match attr:
            case 'style':
                self._set_scaled_style(element=element, value=value)
            case 'transform':
                self._set_scaled_transform(element=element, value=value)
            case 'd':
                self._set_scaled_path(element=element, value=value)

    def _coerce_and_scale_value(self, value):
        cleaned_value = self._strip_units(value)
        scaled_value = self.rnd(float(cleaned_value) * self.scaling_factor)
        return str(scaled_value)

    def _set_scaled_value(self, element, attr, value):
        scaled_value = self._coerce_and_scale_value(value)
        element.set(attr, scaled_value)

    def _match_attribute(self, element, attr, value):
        handler = {
            **{attr: self._set_scaled_value for attr in self._standard_attributes},
            'style': self._match_other_attributes,
            'transform': self._match_other_attributes,
            'd': self._match_other_attributes,
        }.get(attr)
        # noinspection PyArgumentList
        handler(element=element, attr=attr, value=value)

    def _modify_tag(self, element):
        for attr in self._attributes:
            value = element.attrib.get(attr)
            if value: self._match_attribute(element=element, attr=attr, value=value)

    def _modify_svg_element(self, element):
        self.svg_tag = element.tag
        match self.svg_tag:
            case 'g':
                self._modify_tag(element=element)
                for child_element in element.iterchildren():
                    self._modify_svg_element(element=child_element)
            case _:
                self._modify_tag(element=element)

    def _drop_attr(self, svg): [svg.attrib.pop(key) for key in self._attributes if key in svg.attrib]

    def scale(self, ratio: str, units: str, svg: etree.Element):
        self.ratio = ratio
        self.units = units
        self._drop_attr(svg=svg)
        for element in svg.iterchildren():
            self._modify_svg_element(element=element)
