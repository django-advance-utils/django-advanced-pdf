import re
import warnings
from lxml import etree
from reportlab.lib.units import inch, mm, cm
import math


class SVGScaler:
    __slots__ = ['_ratio',
                 '_ratio_pattern',
                 '_path_pattern',
                 '_transform_pattern',
                 '_point_pattern',
                 '_units',
                 '_svg_tag',
                 '_standard_attributes',
                 '_other_attributes',
                 '_attributes',
                 '_attr_handler']

    def __init__(self):
        # TODO: Rule.
        self._ratio = None
        self._ratio_pattern = r'^1:(\d+(\.\d+)?)$'
        self._path_pattern = r'-?\d*\.?\d+'
        self._transform_pattern = r'translate\(([-\d.]+),\s*([-\d.]+)\)'
        self._point_pattern = r'-?\d+(\.\d+)?'
        self._units = None
        self._svg_tag = None
        self._standard_attributes = ['width', 'height', 'x', 'y', 'x1', 'y1', 'x2', 'y2', 'stroke-width', 'text']
        self._other_attributes = ['style', 'transform', 'd', 'points']
        self._attributes = self._standard_attributes + self._other_attributes
        self._attr_handler = {**{attr: self._set_scaled_value for attr in self._standard_attributes},
                              **{attr: self._match_other_attributes for attr in self._other_attributes}}

    @property
    def ratio(self):
        return self._ratio

    @ratio.setter
    def ratio(self, value: str):
        if isinstance(value, float):
            self._ratio = value
        else:
            match = re.fullmatch(self._ratio_pattern, value)
            if not match:
                raise ValueError('format must be "1:n" where 1 unit on a scale drawing represents float n real-life units')
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

    def _drop_attr(self, svg): [svg.attrib.pop(key) for key in self._attributes if key in svg.attrib]

    def scale(self, ratio: str, units: str, svg: etree.Element):
        self.ratio = ratio
        self.units = units
        print(ratio)
        self._drop_attr(svg=svg)
        for element in svg.iterchildren():
            self._match_element_tag(element=element)


class SVGScaledRuler(SVGScaler):
    __slots__ = ['input_pattern', 'length']
    def __init__(self):
        super().__init__()
        self.input_pattern = r'(\d+(\.\d+)?)(cm|mm|m)'
        self.length = None

    def _parse_length(self, length):
        match = re.match(self.input_pattern, length.strip())
        if not match:
            raise ValueError('please provide a valid length, say, "50cm".')
        value, units = float(match.group(1)), match.group(3)
        if (rounded_value := math.ceil(value)) != value:
            warnings.warn('value has been rounded')

        match units:
            case 'mm':
                length = rounded_value * 0.1
            case 'cm':
                length = rounded_value * 1
            case _:
                length = None

        if length is None or length < 1:
            raise ValueError('the real object length must be greater than 1cm.')
        return length, units

    def _draw_line(self, element, x1="0", y1="0", x2="0", y2="0"):
        attrib = {'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2, 'stroke': 'black', 'stroke-width': str(0.1/self.units)}
        etree.SubElement(element,
                         _tag='line',
                         attrib=attrib)

    def _draw_text(self, element, text, x="0", y="0"):
        attrib = {'x': x, 'y': y, 'text-anchor': 'middle'}
        ele = etree.SubElement(element,
                        _tag='text',
                        attrib=attrib)
        ele.text = text

    def steps(self, total_distance, num_markers):
        if num_markers < 2 or total_distance <= 0:
            raise ValueError("num_markers must be >= 2 and total_distance must be > 0")
        spacing = total_distance / (num_markers - 1)
        marker_positions = [f'{self.rnd(i * spacing)}' for i in range(num_markers)]
        return marker_positions

    def render(self, ratio, real_length):
        self.ratio = ratio
        self.length, self.units = self._parse_length(length=real_length)
        if (scaled_length := self.ratio * self.length) < 1:
            raise ValueError('ruler not within size constraint of ratio * length.')
        elif (rounded_scaled_length := math.ceil(scaled_length)) != scaled_length:
            scaled_length = rounded_scaled_length
            warnings.warn('the value had to be rounded because length * ratio was not a multiple of 10')

        svg = etree.Element('svg', nsmap={'svg': 'http://www.w3.org/2000/svg'})
        ticks = int(scaled_length*10)
        lin_steps = self.steps(self.length, ticks)
        tick_size_factor = -0.5 / self.ratio
        l_tick_size = str(tick_size_factor)
        m_tick_size = str(tick_size_factor * 0.75)
        s_tick_size = str(tick_size_factor * 0.35)
        marker_location = str(-1*(0.6/self.ratio))
        ratio_location = str(0.4/self.ratio)

        self._draw_line(element=svg, x2=f'{self.length}')
        self._draw_text(element=svg, y=ratio_location, text=ratio)
        counter = 1
        for i in range(1, len(lin_steps) + 1, 1):
            step = lin_steps[i - 1]
            if i == 1:
                self._draw_line(element=svg, x1=step, x2=step, y2=l_tick_size)
                self._draw_text(element=svg, x=step, y=marker_location, text=f'0')

            elif i % 10 == 0:
                self._draw_line(element=svg, x1=step, x2=step, y2=l_tick_size)
                if counter % 2 == 0:
                    self._draw_text(element=svg, x=step, y=marker_location, text=f'{i*10}')
                counter += 1
            elif i % 5 == 0:
                self._draw_line(element=svg, x1=step, x2=step, y2=m_tick_size)
            else:
                self._draw_line(element=svg, x1=step, x2=step, y2=s_tick_size)
        self.scale(ratio=self.ratio, units=self.units, svg=svg)
        return svg

