from time import strftime, localtime

from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth

from django_advanced_pdf.engine.utils import GREYFILL_COLOUR, BLACK_COLOUR
from django_advanced_pdf.pagers.base import BasePager


class BorderPager(BasePager):
    def __init__(self, heading, filename, footer_field=None, pagesize=None, bottom_up=1, page_compression=None,
                 invariant=None, verbosity=0, encrypt=None, crop_marks=None, pdf_version=None, enforce_color_space=None,
                 bottom_text=None, test_mode=False, status_method=None, **kwargs):
        BasePager.__init__(self, heading=heading, filename=filename, pagesize=pagesize,
                           bottom_up=bottom_up, page_compression=page_compression,
                           invariant=invariant, verbosity=verbosity, encryp=encrypt,
                           crop_marks=crop_marks, pdf_version=pdf_version,
                           enforce_color_space=enforce_color_space, test_mode=test_mode,
                           status_method=status_method,
                           **kwargs)

        self._saved_page_states = []
        self.bottom_text = bottom_text

        self.set_page_used(top=self.page_height() - (self.border_top() - 5 * mm),
                           bottom=(self.border_bottom() + 7 * mm),
                           left=self.border_left(),
                           right=self.page_width() - (self.border_right()))
        self.footer_field = footer_field

    def draw_borders(self, page_count):
        self.setFont("Helvetica", 7)

        border_left = self.border_left()
        border_right = self.border_right()
        border_top = self.border_top()
        border_bottom = self.border_bottom()

        bottom_base = border_bottom - 7 * mm
        bottom_centre = border_bottom - 5 * mm

        self.setStrokeColor(GREYFILL_COLOUR)
        self.setFillColor(GREYFILL_COLOUR)

        text_width = stringWidth(self.heading, "Helvetica", 14)
        if text_width * mm < 30 * mm:
            text_width = 30 * mm
        box_left = (border_right - 5 * mm) - text_width

        self.rect(border_left, border_top - 5 * mm, box_left - border_left, 10 * mm, fill=1)
        self.setStrokeColor(BLACK_COLOUR)
        self.setFillColor(BLACK_COLOUR)
        self.line(border_left, bottom_base, border_right, bottom_base)  # bottom
        self.line(border_right, bottom_base, border_right, border_top + 5 * mm)  # right
        self.line(border_left, bottom_base, border_left, border_top + 5 * mm)  # left
        self.line(border_left, border_top + 5 * mm, border_right, border_top + 5 * mm)  # top
        self.line(border_left, border_top - 5 * mm, border_right, border_top - 5 * mm)  # top lower

        # the left point of the top box

        self.line(box_left, border_top + 5 * mm, box_left, border_top - 5 * mm)  # left
        mid_box = (border_right + 2 * mm - box_left) / 2
        self.setFont("Helvetica", 14)
        self.drawCentredString(border_right - mid_box, border_top - 2 * mm, self.heading)

        # page totals

        of_width = stringWidth(" of ", "Helvetica", 12)
        current_page_width = stringWidth("%d" % self._pageNumber, "Helvetica-Bold", 14)
        total_page_number_width = stringWidth("%d" % page_count, "Helvetica-Bold", 14)

        total_width = current_page_width + of_width + total_page_number_width + (2 * mm)

        mid_point = (of_width / 2) + total_page_number_width + (1 * mm)

        self.setFont("Helvetica", 10)
        self.drawCentredString(border_right - mid_point, bottom_centre, " of ")

        self.setFont("Helvetica-Bold", 12)
        self.drawRightString(border_right - (of_width / 2) - mid_point, bottom_centre, "%d" % self._pageNumber)
        self.drawString(border_right - mid_point + (of_width / 2), bottom_centre, "%d" % page_count)

        self.setFont("Helvetica", 10)

        time_str = self.get_time_string()
        time_width = stringWidth(time_str, "Helvetica", 10) + 4 * mm

        self.line(border_right - total_width, border_bottom, border_right - total_width, bottom_base)  # mid line
        self.line(border_right - (total_width + time_width), border_bottom,
                  border_right - (total_width + time_width), bottom_base)  # left line

        self.line(border_left, border_bottom, border_right, border_bottom)  # top line

        self.drawCentredString(border_right - (total_width + (time_width / 2)), bottom_centre, time_str)

        self.setFont("Helvetica-Bold", 12)
        if self.footer_field is not None:
            self.drawString(border_left + 2 * mm, border_top - 2 * mm, self.footer_field)
        # end page totals

        if self.bottom_text is not None:
            self.setFont("Helvetica", 10)
            self.drawString(border_left + 2 * mm, bottom_centre, self.bottom_text)

        self.display_program_name()

    def get_time_string(self):

        if self.test_mode:
            return "12:28 23-02-23"

        return strftime("%H:%M %d-%m-%y", localtime())