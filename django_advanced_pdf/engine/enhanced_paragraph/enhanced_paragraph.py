from reportlab.platypus import Paragraph
from reportlab.platypus.paragraph import textTransformFrags

from django_advanced_pdf.engine.enhanced_paragraph.parser import EnhancedParaParser


class EnhancedParagraph(Paragraph):
    # bulletText needs to be camelcase as it is referenced internally by the reportlab code and will break if changed
    def __init__(self, text, style, bulletText=None, frags=None, case_sensitive=1,
                 encoding='utf8', css_classes=None):
        if css_classes is None:
            self.css_classes = {}
        else:
            self.css_classes = css_classes
        Paragraph.__init__(self, text, style, bulletText, frags, case_sensitive, encoding)

    def _setup(self, text, style, bullet_text, frags, cleaner):
        if frags is None:
            text = cleaner(text)
            _parser = EnhancedParaParser(self.css_classes)
            _parser.caseSensitive = self.caseSensitive
            style, frags, bullet_text_frags = _parser.parse(text, style)
            if frags is None:
                raise ValueError("xml parser error (%s) in paragraph beginning\n'%s'"
                                 % (_parser.errors[0], text[:min(30, len(text))]))
            textTransformFrags(frags, style)
            if bullet_text_frags:
                bullet_text = bullet_text_frags

        # AR hack
        self.text = text
        self.frags = frags
        self.style = style
        self.bulletText = bullet_text
        self.debug = 0

    def calc_text_height(self, avail_width):
        # work out widths array for breaking
        style = self.style
        left_indent = style.leftIndent
        first_line_width = avail_width - (left_indent + style.firstLineIndent) - style.rightIndent
        later_widths = avail_width - left_indent - style.rightIndent
        _wrapWidths = [first_line_width, later_widths]
        if style.wordWrap == 'CJK':
            # use Asian text wrap algorithm to break characters
            bl_para = self.breakLinesCJK(_wrapWidths)
        else:
            bl_para = self.breakLines(_wrapWidths)
        auto_leading = getattr(self, 'autoLeading', getattr(style, 'autoLeading', ''))
        leading = style.leading
        if bl_para.kind == 1:
            if auto_leading not in ('', 'off'):
                height = 0
                if auto_leading == 'max':
                    for l in bl_para.lines:
                        height += max(l.ascent - l.descent, leading)
                elif auto_leading == 'min':
                    for l in bl_para.lines:
                        height += l.ascent - l.descent
                else:
                    raise ValueError('invalid autoLeading value %r' % auto_leading)
            else:
                height = len(bl_para.lines) * leading
        else:
            if auto_leading == 'max':
                leading = max(leading, bl_para.ascent - bl_para.descent)
            elif auto_leading == 'min':
                leading = bl_para.ascent - bl_para.descent
            height = len(bl_para.lines) * leading
        return height
