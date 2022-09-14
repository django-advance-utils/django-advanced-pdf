import logging

import reportlab
from reportlab.lib import colors
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4, A6, A5, A3, A2, A1, A0, LETTER, LEGAL, ELEVENSEVENTEEN, landscape, portrait
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas
from reportlab.platypus import BaseDocTemplate, Frame, PageTemplate, SimpleDocTemplate
from django.contrib.humanize.templatetags.humanize import intcomma

logger = logging.getLogger("reportlab.platypus")

GREYFILL_COLOUR = HexColor(0xe3e3e3)
PURPLE_COLOUR = HexColor(0x721472)
BLACK_COLOUR = HexColor(0x000000)


class DocTemplate(SimpleDocTemplate):
    def __init__(self, heading, pager, *args, **kwargs):
        BaseDocTemplate.__init__(self, *args, **kwargs)
        #  Create and add two page templates each comprising a single frame to handle the
        #  first and subsequent pages. Each frame spans the entire page, but has padding
        #  set corresponding to the page used by the boxes and whatnot.

        frame1 = Frame(0,
                       0,
                       self.pagesize[0],
                       self.pagesize[1],
                       pager.page_used_left(),
                       pager.page_used_bottom() + 5 * mm,
                       pager.page_used_right(),
                       pager.page_used_top() + 5 * mm)
        frame2 = Frame(0,
                       0,
                       self.pagesize[0],
                       self.pagesize[1],
                       pager.page_used_left(False),
                       pager.page_used_bottom(False) + 5 * mm,
                       pager.page_used_right(False),
                       pager.page_used_top(False) + 5 * mm)

        self.addPageTemplates([PageTemplate(id='Page1', frames=frame1), PageTemplate(id='Page2', frames=frame2)])

        self.pager = pager
        self.heading = heading

    def handle_pageEnd(self):
        #  The _nextPageTemplateIndex setting is cleared on each page so we need to
        #  force it back to one so all pages after the first get the second page
        #  template.
        self._nextPageTemplateIndex = 1
        BaseDocTemplate.handle_pageEnd(self)

    def _startBuild(self, filename=None, canvasmaker=canvas.Canvas):
        self._calc()

        #  Each distinct pass gets a sequencer
        self.seq = reportlab.lib.sequencer.Sequencer()

        self.canv = canvasmaker(
            self.heading,
            filename or self.filename,
            pagesize=self.pagesize,
            invariant=self.invariant,
            page_compression=self.pageCompression,
            enforce_color_space=self.enforceColorSpace)

        getattr(self.canv, 'setEncrypt', lambda x: None)(self.encrypt)

        self.canv._cropMarks = self.cropMarks
        self.canv.setAuthor(self.author)
        self.canv.setTitle(self.title)
        self.canv.setSubject(self.subject)
        self.canv.setCreator(self.creator)
        self.canv.setKeywords(self.keywords)

        if self._onPage:
            self.canv.setPageCallBack(self._onPage)

        self.handle_documentBegin()

    def handle_pageBegin(self):
        """Perform actions required at beginning of page.
        shouldn't normally be called directly"""
        self.page += 1
        if self._debug:
            logger.debug("beginning page %d" % self.page)

        self.before_draw_canvas(self.canv, self.page)
        self.pageTemplate.beforeDrawPage(self.canv, self)
        self.pageTemplate.checkPageSize(self.canv, self)
        self.pageTemplate.onPage(self.canv, self)
        for f in self.pageTemplate.frames:
            f._reset()
        self.beforePage()
        # keep a count of flowables added to this page.  zero indicates bad stuff
        self._curPageFlowableCount = 0
        if hasattr(self, '_nextFrameIndex'):
            del self._nextFrameIndex
        self.frame = self.pageTemplate.frames[0]
        self.frame._debug = self._debug
        self.handle_frameBegin()

    def before_draw_canvas(self, canv, page_number):
        # if page_number == 2:
        #     self.create_abs_table(canv)
        pass
    # def create_abs_table(self, canv):
    #     data = [['00', '01', '02', '03', '04'],
    #             ['10', '11', '12', '13', '14'],
    #             ['20', '21', '22', '23', '24'],
    #             ['30', '31', '32', '33', '34']]
    #
    #     t = Table(data)
    #     t.setStyle(TableStyle([('BACKGROUND', (1, 1), (-2, -2), colors.green),
    #                            ('TEXTCOLOR', (0, 0), (1, -1), colors.red)]))
    #
    #     t.wrapOn(canv, self.width - 100, self.height)
    #     t.drawOn(canv, *self.coord(100, 200, mm))

    def coord(self, x, y, unit=mm):
        """
        http://stackoverflow.com/questions/4726011/wrap-text-in-a-table-reportlab
        Helper class to help position flowables in Canvas objects
        """
        x, y = x * unit, self.height - y * unit
        return x, y




class Grouper(dict):
    """
    Ordered grouping support class. When a key/value pair is added then the value
    is appended to a list, which can later be retrieved to get the values back in
    insertion order. Note that this does not support deletion or key replacement.

    The "group" method takes a list of values on which grouping should be based.
    These are concatenated as strings, except that floating values are chopped
    at three decimal places.

    """
    def __init__(self):
        self._ordered = []

    def __setitem__(self, key, value):
        dict.__setitem__(self, key, value)
        self._ordered.append((key, value))

    def ordered(self):
        return [o[1] for o in self._ordered]

    def ordered_with_keys(self):
        return self._ordered

    @staticmethod
    def group(*args):
        bits = []
        for a in args:
            if isinstance(a, float):
                a = int(a * 1000)
            bits.append(str(a))
        return ','.join(bits)


class DecimalText(object):
        """
        Helper class to get decimal alignment in tables but with access
        to the common style settings. Note that this only works when used
        with table rows added using the L{append_table_data} method, since that automatically appends
        the relevant table style commands to make it work.
        """
        cachedWidths = {}

        def __init__(self, text, style, dp, stripped=False):
            self.m_text = text
            self.m_style = style
            self.m_dp = dp
            self.strip_trailing_zeros = stripped
            if self.strip_trailing_zeros:
                self.m_text = self.m_text.rstrip("0").rstrip(".")

        def font_name(self):
            return self.m_style.fontName

        def font_size(self):
            return self.m_style.fontSize

        def leading(self):
            return self.m_style.leading

        def right_padding(self):
            key = '%s_%s_%s' % (self.m_style.fontName, self.m_style.fontSize, self.m_dp)
            if key not in self.cachedWidths:
                if self.m_dp == 0:
                    w = 1 * mm
                else:
                    w = 1 * mm + stringWidth('.' + '0' * self.m_dp, self.m_style.fontName, self.m_style.fontSize)
                self.cachedWidths[key] = w
            return self.cachedWidths[key]

        def merge_variables(self, variables=None):
            if variables:
                self.m_text = self.m_text % variables
                if self.strip_trailing_zeros:
                    self.m_text = self.m_text.rstrip("0").rstrip(".")
            return self

        def __str__(self):
            return self.m_text


def get_page_size_from_string(page_size_string, landscape_portrait_string):
    page_size_string = page_size_string.lower()
    landscape_portrait_string = landscape_portrait_string.lower()
    if page_size_string == "a4":  # most common that why it at the top
        page_size = A4
    elif page_size_string == "a6":
        page_size = A6
    elif page_size_string == "a5":
        page_size = A5
    elif page_size_string == "a3":
        page_size = A3
    elif page_size_string == "a2":
        page_size = A2
    elif page_size_string == "a1":
        page_size = A1
    elif page_size_string == "a0":
        page_size = A0
    elif page_size_string == "leter":
        page_size = LETTER
    elif page_size_string == "legal":
        page_size = LEGAL
    elif page_size_string == "elevenseventeen":
        page_size = ELEVENSEVENTEEN
    else:
        assert False, "Unknown page type"

    if landscape_portrait_string == "landscape":
        return landscape(page_size)
    else:
        return portrait(page_size)


class PageUsed:
    def __init__(self, left, right, top, bottom):
        self.left = left
        self.right = right
        self.top = top
        self.bottom = bottom


def intcomma_currency(value, show_more_decimal_places=False):

    if show_more_decimal_places:
        display_number = "%.5f" % float(value)
        main_number = display_number[:-3]
        extra_numbers = display_number[-3:]
        extra_numbers = extra_numbers.rstrip("0")
        value = intcomma("%.2f" % float(main_number))
        if extra_numbers != '':
            value += '<span class="currency_extra_digits">%s</span>' % extra_numbers
    else:
        value = intcomma("%.2f" % float(value))
    return value


class ColumnWidthPercentage(object):
    def __init__(self, value):
        self.value = value

    def get_value(self):
        return self.value