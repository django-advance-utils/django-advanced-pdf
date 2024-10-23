import logging
import re
from collections import deque
from html.parser import HTMLParser, starttagopen, charref, entityref, incomplete

import reportlab
from django.contrib.humanize.templatetags.humanize import intcomma
from reportlab.lib import colors
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4, A6, A5, A3, A2, A1, A0, LETTER, LEGAL, ELEVENSEVENTEEN, landscape, portrait
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas
from reportlab.platypus import BaseDocTemplate, Frame, PageTemplate, SimpleDocTemplate, Flowable, Table, TableStyle

logger = logging.getLogger("reportlab.platypus")

GREYFILL_COLOUR = HexColor(0xe3e3e3)
PURPLE_COLOUR = HexColor(0x721472)
BLACK_COLOUR = HexColor(0x000000)


class ReportXMLError(Exception):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)

    def value(self):
        return self.value


class ObjectPosition(Flowable):
    _ZEROSIZE = 1

    def __init__(self, content, pos_x=None, pos_y=None):
        self.content = content
        self.pos_x = pos_x
        self.pos_y = pos_y
        Flowable.__init__(self)

    def wrap(self, availableWidth, availableHeight):
        self.width = availableWidth
        self.height = availableHeight
        return self.width, self.height

    def draw(self):
        pos_x = 0
        pos_y = 0
        if self.pos_x is not None:
            pos_x = float(self.pos_x)
        if self.pos_y is not None:
            pos_y = float(self.pos_y)
        for flowable in self.content:
            flowable.drawOn(self.canv, pos_x, pos_y)


class DocTemplate(SimpleDocTemplate):
    def __init__(self, heading, pager, pager_blocks, *args, **kwargs):
        BaseDocTemplate.__init__(self, *args, **kwargs)
        #  Create and add two page templates each comprising a single frame to handle the
        #  first and subsequent pages. Each frame spans the entire page, but has padding
        #  set corresponding to the page used by the boxes and whatnot.
        first_margins = pager.margins()
        continuation_margins = pager.margins(first_page=False)
        self.pager_blocks = []
        pager_blocks_heights = self.prepass_pager_block(pager_blocks)
        first_page_used = pager.get_page_used()
        continuation_page_used = pager.get_page_used(first_page=False)

        frame1 = Frame(0,
                       0,
                       self.pagesize[0],
                       self.pagesize[1],
                       first_page_used['left'] + first_margins['left'],
                       first_page_used['bottom'] + first_margins['bottom'] + pager_blocks_heights['bottom'],
                       first_page_used['right'] + first_margins['right'],
                       first_page_used['top'] + first_margins['top'] + pager_blocks_heights['top'])
        frame2 = Frame(0,
                       0,
                       self.pagesize[0],
                       self.pagesize[1],
                       continuation_page_used['left'] + continuation_margins['left'],
                       continuation_page_used['bottom'] + continuation_margins['bottom'] + pager_blocks_heights['bottom'],
                       continuation_page_used['right'] + continuation_margins['right'],
                       continuation_page_used['top'] + continuation_margins['top'] + pager_blocks_heights['top'])

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

    def prepass_pager_block(self, pager_blocks):
        top_block_height = 0
        bottom_block_height = 0
        if len(pager_blocks) > 0:
            for pager_block in pager_blocks:
                display_objects = pager_block['display_objects']
                height = 0
                offsets = []
                for display_object in display_objects:
                    offsets.append(height)
                    h, _ = display_object.calc_height_of_table(self.pagesize[0], self.pagesize[1])
                    height += h
                if pager_block.get('pos_y_ref') == 'top':
                    top_block_height += height
                else:
                    bottom_block_height += height
                self.pager_blocks.append({**pager_block,
                                          'height': height / mm,
                                          'offsets': offsets[::-1]})
        return {'top': top_block_height, 'bottom': bottom_block_height}

    def before_draw_canvas(self, canv, page_number):
        if page_number == 1:
            page_used = self.pager.get_page_used()
        else:
            page_used = self.pager.get_page_used(first_page=False)
        page_height = self.pager.pagesize[1]
        if len(self.pager_blocks) > 0:
            for pager_block in self.pager_blocks:
                display_objects = pager_block['display_objects']
                offsets = pager_block['offsets']
                block_height = pager_block['height']
                pos_x = pager_block['pos_x'] + (page_used['left'] / mm)
                for display_object, offset in zip(display_objects, offsets):
                    display_object.wrapOn(canv, self.width, self.height)
                    block_pos_y = pager_block['pos_y']
                    if pager_block.get('pos_y_ref') == 'top':
                        pos_y = block_pos_y + ((page_used['top'] + offset) / mm) + block_height
                    else:
                        page_height_mm = page_height / mm
                        total_margins = (page_used['bottom'] + offset) / mm
                        pos_y = page_height_mm - block_pos_y - total_margins

                    display_object.drawOn(canv, *self.coord(pos_x, pos_y, mm, height=page_height))

    def coord(self, x, y, unit=mm, height=None):
        """
        http://stackoverflow.com/questions/4726011/wrap-text-in-a-table-reportlab
        Helper class to help position flowables in Canvas objects
        """
        if height is None:
            height = self.height
        x, y = x * unit, height - y * unit
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


def get_page_size_from_element(element):
    page_size_string = element.get('page_size', '')
    landscape_portrait_string = element.get('page_orientation', '')

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
    elif page_size_string == "letter":
        page_size = LETTER
    elif page_size_string == "legal":
        page_size = LEGAL
    elif page_size_string == "elevenseventeen":
        page_size = ELEVENSEVENTEEN
    elif page_size_string == "custom":
        page_width = float(element.get('page_width', 0))
        page_height = float(element.get('page_height', 0))
        return page_width * mm, page_height * mm
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


class MyTDUserHtmlParser(HTMLParser):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.stack = deque()
        self.repaired_html = ""
        self.ignore_tags = set()

    def handle_starttag(self, tag, attrs):
        starttag_text = self.get_starttag_text()
        self.repaired_html += starttag_text
        if not starttag_text.endswith("/>"):
            self.stack.append(tag)
        else:
            self.ignore_tags.add(tag)

    def handle_endtag(self, tag):
        buffer = ""
        if tag in self.ignore_tags:
            return
        while self.stack:
            last = self.stack[-1]
            if last == tag:
                self.stack.pop()
                break
            buffer = f"</{last}>" + buffer
            self.stack.pop()

        self.repaired_html += buffer
        self.repaired_html += f"</{tag}>"

    def handle_data(self, data):
        self.repaired_html += data

    def goahead(self, end):
        rawdata = self.rawdata
        i = 0
        n = len(rawdata)
        while i < n:
            if self.convert_charrefs and not self.cdata_elem:
                j = rawdata.find('<', i)
                if j < 0:
                    # if we can't find the next <, either we are at the end
                    # or there's more text incoming.  If the latter is True,
                    # we can't pass the text to handle_data in case we have
                    # a charref cut in half at end.  Try to determine if
                    # this is the case before proceeding by looking for an
                    # & near the end and see if it's followed by a space or ;.
                    amppos = rawdata.rfind('&', max(i, n - 34))
                    if (amppos >= 0 and
                            not re.compile(r'[\s;]').search(rawdata, amppos)):
                        break  # wait till we get all the text
                    j = n
            else:
                match = self.interesting.search(rawdata, i)  # < or &
                if match:
                    j = match.start()
                else:
                    if self.cdata_elem:
                        break
                    j = n
            if i < j:
               self.handle_data(rawdata[i:j])
            i = self.updatepos(i, j)
            if i == n: break
            startswith = rawdata.startswith
            if startswith('<', i):
                if starttagopen.match(rawdata, i):  # < + letter
                    k = self.parse_starttag(i)
                elif startswith("</", i):
                    k = self.parse_endtag(i)
                elif startswith("<!--", i):
                    k = self.parse_comment(i)
                elif startswith("<?", i):
                    k = self.parse_pi(i)
                elif startswith("<!", i):
                    k = self.parse_html_declaration(i)
                elif (i + 1) < n:
                    self.handle_data("<")
                    k = i + 1
                else:
                    break
                if k < 0:
                    if not end:
                        break
                    k = rawdata.find('>', i + 1)
                    if k < 0:
                        k = rawdata.find('<', i + 1)
                        if k < 0:
                            k = i + 1
                    else:
                        k += 1
                    self.handle_data(rawdata[i:k])
                i = self.updatepos(i, k)
            elif startswith("&#", i):
                match = charref.match(rawdata, i)
                if match:
                    name = match.group()[2:-1]
                    self.handle_charref(name)
                    k = match.end()
                    if not startswith(';', k - 1):
                        k = k - 1
                    i = self.updatepos(i, k)
                    continue
                else:
                    if ";" in rawdata[i:]:  # bail by consuming &#
                        self.handle_data(rawdata[i:i + 2])
                        i = self.updatepos(i, i + 2)
                    break
            elif startswith('&', i):
                match = entityref.match(rawdata, i)
                if match:
                    name = match.group(1)
                    self.handle_entityref(name)
                    k = match.end()
                    if not startswith(';', k - 1):
                        k = k - 1
                    i = self.updatepos(i, k)
                    continue
                match = incomplete.match(rawdata, i)
                if match:
                    # match.group() will contain at least 2 chars
                    if end and match.group() == rawdata[i:]:
                        k = match.end()
                        if k <= i:
                            k = n
                        i = self.updatepos(i, i + 1)
                    # incomplete
                    break
                elif (i + 1) < n:
                    # not the end of the buffer, and can't be confused
                    # with some other construct
                    self.handle_data("&")
                    i = self.updatepos(i, i + 1)
                else:
                    break
            else:
                assert 0, "interesting.search() lied"
        # end while
        if end and i < n and not self.cdata_elem:
            self.handle_data(rawdata[i:n])
            i = self.updatepos(i, n)
        self.rawdata = rawdata[i:]


def get_boolean_value(value, default=False):
    if value is None:
        return default
    return value.lower() in ['1', 'true', 'yes']

