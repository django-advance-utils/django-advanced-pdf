from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm


class EnhancedParagraphStyle(ParagraphStyle):

    def process_css_for_table_paragraph_style(self, css, row_count, col_count):
        for style in css:
            if row_count is not None and col_count is not None and \
                    not self.is_valid_css_row(row_count, col_count, style[1], style[2]):
                continue
            style_type = style[0].lower()

            if style_type == '' or len(style) < 4:
                continue
            style_detail = style[3]
            if style_type in ('font_name',
                              'face',
                              'font'):
                self.fontName = style_detail
            elif style_type in ('size',
                                'fontsize'):
                self.fontSize = style_detail
            elif style_type == 'leading':
                self.leading = style_detail
            elif style_type == 'textcolor':
                self.textColor = style_detail
            elif style_type == 'align':
                alignment_type = style_detail.lower()
                if alignment_type == 'left':
                    self.alignment = TA_LEFT
                elif alignment_type == 'center':
                    self.alignment = TA_CENTER
                elif alignment_type == 'right':
                    self.alignment = TA_RIGHT

    def process_raw_css(self, css):
        styles_list = css.split(';')

        for style in styles_list:
            if style == '':
                continue
            style_type, style_detail = style.split(':')
            style_type = style_type.lower().lstrip("\r\n ")

            if style_type == '':
                continue
            if style_type in ('font_name',
                              'face',
                              'font'):
                self.fontName = style_detail
            elif style_type in ('size',
                                'font_size'):
                self.fontSize = int(style_detail)
            elif style_type == 'leading':
                self.leading = int(style_detail)
            elif style_type == 'text_color':
                self.textColor = HexColor(style_detail)
            elif style_type == 'back_color':
                self.backColor = HexColor(style_detail)
            elif style_type == 'align':
                alignment_type = style_detail.lower()
                if alignment_type == 'left':
                    self.alignment = TA_LEFT
                elif alignment_type == 'center':
                    self.alignment = TA_CENTER
                elif alignment_type == 'right':
                    self.alignment = TA_RIGHT
            elif style_type == 'left_indent':
                self.leftIndent = float(style_detail) * mm
            elif style_type == 'right_indent':
                self.rightIndent = float(style_detail) * mm
            elif style_type == 'first_line_indent':
                self.firstLineIndent = float(style_detail) * mm
            elif style_type == 'space_before':
                self.spaceBefore = float(style_detail) * mm
            elif style_type == 'space_after':
                self.spaceAfter = float(style_detail) * mm
            elif style_type == 'border_width':
                self.border_width = int(style_detail)
            elif style_type == 'border_padding':
                self.borderPadding = float(style_detail) * mm
            elif style_type == 'border_color':
                self.borderColor = HexColor(style_detail)
            elif style_type == 'border_radius':
                self.borderRadius = float(style_detail)

    @staticmethod
    def is_valid_css_row(row_count, col_count, css_start, css_end):
        if css_start == (0, 0) and css_end == (-1, -1):
            return True
        if css_start[1] <= row_count <= css_end[1]:
            if css_start[0] == 0 and css_end[0] == -1:
                return True
            if css_start[0] <= col_count <= css_end[0]:
                return True
        return False
