import re
import warnings
from lxml import etree
from reportlab.lib.units import inch, mm, cm


class SVGScaler:
    __slots__ = ['_ratio',
                 '_ratio_pattern',
                 '_path_pattern',
                 '_transform_pattern',
                 '_point_pattern',
                 '_units',
                 '_svg_tag',
                 '_dropped_attributes',
                 '_standard_attributes',
                 '_other_attributes',
                 '_attributes',
                 '_removed_attrs',
                 '_attr_handler']

    def __init__(self):
        self._ratio = None
        self._ratio_pattern = r'^1:(\d+(\.\d+)?)$'
        self._path_pattern = r'-?\d*\.?\d+'
        self._transform_pattern = r'translate\(([-\d.]+),\s*([-\d.]+)\)'
        self._point_pattern = r'-?\d+(\.\d+)?'
        self._units = None
        self._svg_tag = None
        self._dropped_attributes = ['viewBox']
        self._standard_attributes = ['width', 'height', 'x', 'y', 'x1', 'y1', 'x2', 'y2', 'stroke-width', 'text']
        self._other_attributes = ['style', 'transform', 'd', 'points']
        self._attributes = self._standard_attributes + self._other_attributes
        self._removed_attrs = None
        self._attr_handler = {**{attr: self._set_scaled_value for attr in self._standard_attributes},
                              **{attr: self._match_other_attributes for attr in self._other_attributes}}

    @property
    def ratio(self):
        return self._ratio

    @ratio.setter
    def ratio(self, value: str):
        if isinstance(value, float): self._ratio = value
        else:
            match = re.fullmatch(self._ratio_pattern, value)
            if not match:
                raise ValueError('format must be 1:n where 1 unit on a scale drawing represents float n real-life units')
            if (n := float(match.group(1))) <= 0:
                raise ValueError('the ratio 1:n must have n greater than 0')
            self._ratio = 1/n

    @property
    def units(self):
        return self._units

    @units.setter
    def units(self, value: str):
        if isinstance(value, float):
            self._units = value
        else:
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

    def _coerce_and_scale_value(self, value):
        if isinstance(value, str):
            value = self._strip_units(value)
        scaled_value = self.rnd(float(value) * self.scaling_factor)
        return f'{scaled_value}'

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
        scaled_path = ' '.join(re.sub(self._path_pattern, handler, value).split())
        element.set('d', f'{scaled_path}')

    def _set_scaled_transform(self, element, value):
        handler = lambda match: f'translate({self._coerce_and_scale_value(match.group(1))}, \
                                            {self._coerce_and_scale_value(match.group(2))})'
        scaled_transform = re.sub(self._transform_pattern, handler, value).replace(' ', '')

        if any(unhandled_transform in scaled_transform for unhandled_transform in ['skew', 'scale']):
            warnings.warn('your SVG uses "skew" or "scale" in transform, this is unsupported with class SVGScaler')
        element.set('transform', scaled_transform)

    def _set_scaled_point(self, element, value):
        handler = lambda match: self._coerce_and_scale_value(match.group(0))
        scaled_points = re.sub(self._point_pattern, handler, value)
        element.set('points', scaled_points)

    def _match_other_attributes(self, element, attr, value):
        kwargs = {'element': element, 'value': value}
        match attr:
            case 'style':
                self._set_scaled_style(**kwargs)
            case 'transform':
                self._set_scaled_transform(**kwargs)
            case 'd':
                self._set_scaled_path(**kwargs)
            case 'points':
                self._set_scaled_point(**kwargs)

    def _set_scaled_value(self, element, attr, value):
        units = ['%', 'mm', 'in', 'cm']
        if any(unit in value for unit in units):
            warnings. \
                warn( f'skipped scaling element: {element.tag} with attribute: {attr} and value: {value} has units.')
            return None
        scaled_value = self._coerce_and_scale_value(value)
        element.set(attr, scaled_value)

    def _map_attribute_to_function(self, element, attr, value):
        handler = self._attr_handler.get(attr)
        if handler:
            handler(element=element, attr=attr, value=value)

    def _open_element(self, element):
        for attr in self._attributes:
            value = element.attrib.get(attr)
            if value: self._map_attribute_to_function(element=element, attr=attr, value=value)

    def _match_element_tag(self, element):
        self.svg_tag = element.tag
        match self.svg_tag:
            case 'g':
                self._open_element(element=element)
                for child_element in element.iterchildren():
                    self._match_element_tag(element=child_element)
            case _:
                self._open_element(element=element)

    def _drop_attr(self, svg):
        self._removed_attrs = {key: svg.attrib.pop(key) for key in self._dropped_attributes if key in svg.attrib}

    def _restore_attrs(self, svg):
        for key, value in self._removed_attrs.items():
            svg.attrib[key] = value

    def scale(self, ratio: str, units: str, svg: etree.Element):
        self.ratio = ratio
        self.units = units
        self._match_element_tag(svg)
        for element in svg.iterchildren():
            self._match_element_tag(element=element)
        scaled_width, scaled_height = float(svg.attrib['width']), float(svg.attrib['height'])
        return scaled_width, scaled_height
