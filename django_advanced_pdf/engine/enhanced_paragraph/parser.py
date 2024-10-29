from reportlab.lib.colors import HexColor
from reportlab.platypus import ParaParser
from reportlab.platypus.paraparser import _lineRepeats, _ExValidate


class EnhancedParaParser(ParaParser):

    def __init__(self, css_classes, verbose=0, case_sensitive=0, ignore_unknown_tags=1):
        self.css_classes = css_classes
        ParaParser.__init__(self, verbose, case_sensitive, ignore_unknown_tags)

    def start_span(self, attributes):

        class_name = attributes.get('class')
        css = ""
        if class_name is not None:
            css = self.css_classes.get(class_name, '')

        css += attributes.get("style", '')
        styles_list = css.split(';')
        styles = {}
        for style in styles_list:
            if style == '':
                continue
            style_type, style_detail = style.split(':')
            style_type = style_type.lower().lstrip("\r\n ")
            if isinstance(style_detail, str):
                style_detail = style_detail.lstrip()

            if style_type in ('font',
                              'face',
                              'font_name'):
                styles['fontName'] = style_detail
            elif style_type in ('font_size',
                                'size'):
                styles['fontSize'] = int(style_detail)
            elif style_type in ('text_color',):
                styles['textColor'] = HexColor(style_detail)
            elif style_type == 'text-decoration' and 'underline' in style_detail:
                frag = self._stack[-1]
                styles['us_lines'] = [(
                    self.nlines,
                    'underline',
                    getattr(frag, 'underlineColor', None),
                    getattr(frag, 'underlineWidth', '1'),
                    getattr(frag, 'underlineOffset', self._defaultLineOffsets['underline']),
                    frag.rise,
                    _lineRepeats[getattr(frag, 'underlineKind', 'single')],
                    getattr(frag, 'underlineGap', self._defaultLineGaps['underline']),
                )]

        self._push('span', **styles)

    def end_span(self):
        self._pop('span')

    def getAttributes(self, attr, attrMap):
        # stops a error happening on thing like <u class="">

        A = {}
        for k, v in attr.items():
            if not self.caseSensitive:
                k = k.lower()
            if k in attrMap:
                j = attrMap[k]
                func = j[1]
                if func is not None:
                    #it's a function
                    v = func(self, v) if isinstance(func,_ExValidate) else func(v)
                A[j[0]] = v
        return A
