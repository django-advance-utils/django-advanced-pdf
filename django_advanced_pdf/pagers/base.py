from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from django_advanced_pdf.engine.utils import PageUsed


class BasePager(canvas.Canvas):

    def __init__(self, heading, filename, pagesize=None, bottom_up=1,
                 page_compression=None, invariant=None, verbosity=0,
                 encrypt=None, crop_marks=None, pdf_version=None, enforce_color_space=None,
                 border_left_first=0, border_right_first=0,
                 border_top_first=0, border_bottom_first=0,
                 border_left_continuation=0, border_right_continuation=0,
                 border_top_continuation=0, border_bottom_continuation=0,
                 program_name=None,
                 background_image_first=None, background_image_remaining=None,
                 background_image_footer=None, **kwargs):

        self.heading = heading
        self.pagesize = pagesize
        self.drawmethods = []
        self.image2 = None
        self._saved_page_states = []

        self.pageused = PageUsed(left=border_left_first,
                                 right=border_right_first,
                                 top=border_top_first,
                                 bottom=border_bottom_first)
        self.pageused2 = PageUsed(left=border_left_continuation,
                                  right=border_right_continuation,
                                  top=border_top_continuation,
                                  bottom=border_bottom_continuation)
        self.program_name = program_name

        canvas.Canvas.__init__(self, filename, pagesize, bottom_up, page_compression, invariant, verbosity, encrypt,
                               crop_marks, pdf_version, enforce_color_space)

        self.background_images = None
        if (background_image_first is not None or
                background_image_remaining is not None or
                background_image_footer is not None):
            self.add_background_images(first=background_image_first,
                                       remaining=background_image_remaining,
                                       footer=background_image_footer)

    def inkAnnotation(self, contents, ink_list=None, rect=None, add_to_page=1, name=None, relative=0, **kw):
        pass

    def add_background_images(self, first, remaining, footer):
        self.background_images = {'first': first, 'remaining': remaining, 'footer': footer}
        self.draw_first_page_background()
        self.draw_footer_image_block()

    def add_draw_method(self, method):

        """
        Add a drawing method

        @type   method  : Bound method
        @param  method  : Drawing method
        """

        self.drawmethods.append(method)

    def set_page_used(self, left=0, right=0, top=0, bottom=0):
        if left > self.pageused.left:
            self.pageused.left = left
            self.pageused2.left = left
        if right > self.pageused.right:
            self.pageused.right = right
            self.pageused2.right = right
        if top > self.pageused.top:
            self.pageused.top = top
            self.pageused2.top = top
        if bottom > self.pageused.bottom:
            self.pageused.bottom = bottom
            self.pageused2.bottom = bottom

    def page_used_left(self, first_page=True):
        return self.pageused.left if first_page else self.pageused2.left

    def page_used_right(self, first_page=True):
        return self.pageused.right if first_page else self.pageused2.right

    def page_used_top(self, first_page=True):
        return self.pageused.top if first_page else self.pageused2.top

    def page_used_bottom(self, first_page=True):
        return self.pageused.bottom if first_page else self.pageused2.bottom

    def page_width(self):
        return self.pagesize[0]

    def page_height(self):
        return self.pagesize[1]

    def border_left(self, first_page=True):
        return self.page_used_left(first_page)

    def border_right(self, first_page=True):
        return self.page_width() - self.page_used_right(first_page)

    def border_top(self, first_page=True):
        return self.page_height() - self.page_used_top(first_page)

    def border_bottom(self, first_page=True):
        return self.page_used_bottom(first_page)

    def draw_borders(self, page_count):
        """
        Draw the footer block.
        numbers.

        @type   page_count  : int
        @param  page_count  : Total number of pages
        """
        self.display_program_name()

        self.setFont("Helvetica", 10)

        self.drawRightString(self.border_right(self._pageNumber == 1),
                             self.border_bottom(self._pageNumber == 1) - 4 * mm,
                             "Page %d of %d" %
                             (self._pageNumber, page_count))

    def display_program_name(self):
        if self.program_name is not None:
            border_left = 15
            border_bottom = 4
            self.setFont("Helvetica", 4)

            self.drawString(border_left,
                            border_bottom,
                            self.program_name)

    def draw_page_number(self, page_count):

        """
        @type   page_count  : int
        @param  page_count  : Total number of pages
        """

        for method in self.drawmethods:
            method(page_count)
        self.draw_borders(page_count)

        #  Enable the condition below to draw a red box round the margins.
        #  Used for layout debugging.
        #
        if False:
            first_page = self._pageNumber == 1
            border_left = self.border_left(first_page)
            border_right = self.border_right(first_page)
            border_bottom = self.border_bottom(first_page)
            border_top = self.border_top(first_page)
            self.setStrokeColor(colors.red)
            self.line(border_left, border_bottom, border_right, border_bottom)  # bottom
            self.line(border_right, border_bottom, border_right, border_top)  # right
            self.line(border_left, border_bottom, border_left, border_top)  # left
            self.line(border_left, border_top, border_right, border_top)  # top
            self.setStrokeColor(colors.black)

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

        self.draw_remaining_page_background()
        self.draw_footer_image_block()

    def save(self):

        """
        Add page info to each page. Exactly what gets added will depend on which mixins
        have been added to the derived class.
        """

        num_pages = len(self._saved_page_states)

        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_footer_image_block()
            self.draw_page_number(num_pages)
            canvas.Canvas.showPage(self)

        canvas.Canvas.save(self)

    def draw_first_page_background(self):
        """
        Adds the first page background image to the printout
        """
        if self.background_images is not None and self.background_images['first'] is not None:
            self.drawImage(ImageReader(self.background_images['first']), 0, 0, self.page_width(), self.page_height())

    def draw_remaining_page_background(self):
        """
        Adds the background image for the remaining pages in the printout
        """
        if self.background_images is not None and self.background_images['remaining'] is not None:
            self.drawImage(ImageReader(self.background_images['remaining']), 0, 0, self.page_width(), self.page_height())

    def draw_footer_image_block(self):
        """
        Adds the footer image to the printout
        """
        border_bottom = self.border_bottom(True)
        page_width = self.page_width()
        if self.background_images is not None and self.background_images['footer'] is not None:
            self.drawImage(ImageReader(self.background_images['footer']), 0, 0, page_width, border_bottom)
