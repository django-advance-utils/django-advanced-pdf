import contextlib
import io
import os
import pathlib
import re
import signal
import threading
import unittest
from pathlib import Path
import fitz
from lxml import etree
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import (BaseDocTemplate, Frame, PageBreak, PageTemplate, SimpleDocTemplate, TableStyle, Table,
                                Image as RLImage)
from reportlab.platypus.doctemplate import LayoutError

from django_advanced_pdf.engine.enhanced_table.enhanced_tables import (EnhancedTable, KEEP_TYPE_END, KEEP_TYPE_NA,
                                                                     KEEP_TYPE_START)
from django_advanced_pdf.engine.report_xml import ReportXML
from django_advanced_pdf.engine.utils import ColumnWidthPercentage
from PIL import ImageChops, Image


class PDFTests(unittest.TestCase):

    def setUp(self):
        pass

    @staticmethod
    def get_test_folder():
        return Path(Path(__file__).resolve().parent, 'test_data')

    def run_report(self, name, object_lookup=None):
        test_folder = self.get_test_folder()
        temp_folder = Path(test_folder, 'temp', name)

        pathlib.Path(temp_folder).mkdir(parents=True, exist_ok=True)

        png_files = list(temp_folder.glob("*.png"))

        # Delete each PNG file
        for png_file in png_files:
            png_file.unlink()

        with open(Path(test_folder, 'reports', f'{name}.xml')) as f:
            xml = f.read()

        report_xml = ReportXML(test_mode=True, object_lookup=object_lookup)
        result = report_xml.load_xml_and_make_pdf(xml=xml)
        matrix = fitz.Matrix(300 / 72, 300 / 72)

        with fitz.open("pdf", result) as doc:
            for page_number, page in enumerate(doc, 1):
                output_file = Path(temp_folder, f'{page_number}.png')

                pix = page.get_pixmap(matrix=matrix)
                pix.pil_save(output_file, format="PNG", dpi=(300, 300))

            page_count = len(doc)

            with open(Path(temp_folder, 'page_count.txt'), 'w') as w:
                w.write(str(page_count))

        self.check_report(name=name, new_page_count=page_count)

    def check_report(self, name, new_page_count):
        test_folder = self.get_test_folder()
        temp_folder = Path(test_folder, 'temp', name)
        held_folder = Path(test_folder, 'held', name)

        with open(Path(held_folder, 'page_count.txt'), 'r') as f:
            self.assertEqual(int(f.read()), new_page_count, msg='Pages count not equal')

        for page_number in range(1, new_page_count+1):

            # Load the two images
            image1 = Image.open(Path(held_folder, f'{page_number}.png'))
            image2 = Image.open(Path(temp_folder, f'{page_number}.png'))

            # Check if the images are the same
            if ImageChops.difference(image1, image2).getbbox() is not None:

                # Create a new image showing the difference
                diff_image = ImageChops.difference(image1, image2)
                # Save the difference image

                error_folder = Path(test_folder, 'errors')
                pathlib.Path(error_folder).mkdir(parents=True, exist_ok=True)

                diff_image.save(Path(error_folder, f'{name}.png'))
                self.assertTrue(False, f'Page {page_number} is different')

    def test_keep_with_next(self):
        self.run_report(name='keep_with_next')

    def test_basic(self):
        self.run_report(name='basic')

    def test_change_header(self):
        self.run_report(name='change_header')

    def test_border(self):
        self.run_report(name='border')

    def test_background_colour(self):
        self.run_report(name='background_colour')

    def test_abs2(self):
        self.run_report(name='abs2')

    def test_abs3(self):
        self.run_report(name='abs3')

    def test_overflow_gt_height(self):
        self.run_report(name='overflow_gt_height', object_lookup=self.get_sample_objects())

    def test_overflow_gt_height_spaces(self):
        self.run_report(name='overflow_gt_height_spaces')

    def test_hidden(self):
        self.run_report(name='hidden')

    def test_estimate(self):
        self.run_report(name='estimate')

    def test_cdata_user_html(self):
        self.run_report(name='cdata_user_html')

    def test_label(self):
        self.run_report(name='label', object_lookup=self.get_sample_objects())

    @staticmethod
    def column_widths(table_xml, table_width=180 * mm):
        """
        Build a single table and return the column widths it ends up with.  _argW is where
        reportlab keeps the colWidths it was handed, and is the only way to see the column
        geometry without falling back on comparing rendered pixels.
        """
        report_xml = ReportXML(test_mode=True)
        table = report_xml.process_table(etree.fromstring(table_xml), table_width)
        return table._argW

    def test_cell_width_under_rowspan(self):
        """
        A width on a td belongs to the column the cell is actually placed in.  A rowspan
        started in an earlier row pushes the cell along, and the width has to follow it.
        """
        with_rowspan = self.column_widths("""
            <table>
                <tr><td rowspan="2">a</td><td>b</td><td>c</td></tr>
                <tr><td width="80">d</td><td>e</td></tr>
            </table>""")

        # the same grid, with the cell written out in full instead of covered by the rowspan
        without_rowspan = self.column_widths("""
            <table>
                <tr><td>a</td><td>b</td><td>c</td></tr>
                <tr><td>a2</td><td width="80">d</td><td>e</td></tr>
            </table>""")

        self.assertEqual(without_rowspan, with_rowspan,
                         msg='rowspan moved the column width onto the wrong column')
        self.assertEqual(80 * mm, with_rowspan[1], msg='width did not land on column 1')

    def test_cell_width_after_colspan(self):
        """A colspan earlier in the same row pushes later cells along in the same way."""
        widths = self.column_widths("""
            <table>
                <tr><td colspan="2">a</td><td width="60">b</td><td>c</td></tr>
                <tr><td>1</td><td>2</td><td>3</td><td>4</td></tr>
            </table>""")

        self.assertEqual(4, len(widths), msg='table should be four columns wide')
        self.assertEqual(60 * mm, widths[2], msg='width did not land on column 2')

    def test_svg_width_under_rowspan(self):
        """
        A ratio scaled svg sizes the column it sits in off its own scaled width, so that
        column has to be the one the cell is placed in once a rowspan has pushed it along.
        """
        svg = ('<svg data-ratio="1:1" data-units="mm" width="50" height="50">'
               '<rect width="50" height="50"/></svg>')

        with_rowspan = self.column_widths(f"""
            <table>
                <tr><td rowspan="2">a</td><td>b</td></tr>
                <tr><td>{svg}</td></tr>
            </table>""")

        # the same grid, with the cell written out in full instead of covered by the rowspan
        without_rowspan = self.column_widths(f"""
            <table>
                <tr><td>a</td><td>b</td></tr>
                <tr><td>a2</td><td>{svg}</td></tr>
            </table>""")

        self.assertEqual(without_rowspan, with_rowspan,
                         msg='rowspan moved the svg width onto the wrong column')
        self.assertLess(with_rowspan[1], with_rowspan[0],
                        msg='column 1 was not sized from the svg')

    def test_ruler_width_after_colspan(self):
        """A ruler sizes its column the same way, and a colspan pushes it along the same way."""
        ruler = '<ruler data-ratio="1:10"/>'

        after_colspan = self.column_widths(f"""
            <table>
                <tr><td colspan="2">a</td><td>{ruler}</td></tr>
            </table>""")

        # the same grid, with the colspan written out as two separate cells
        without_colspan = self.column_widths(f"""
            <table>
                <tr><td>a</td><td>a2</td><td>{ruler}</td></tr>
            </table>""")

        self.assertEqual(without_colspan, after_colspan,
                         msg='colspan moved the ruler width onto the wrong column')
        self.assertLess(after_colspan[2], after_colspan[0],
                        msg='column 2 was not sized from the ruler')

    def test_spanned_columns_get_their_own_width(self):
        """
        Columns only ever reached by a colspan still need a width of their own.  When they are
        missing reportlab quietly pads the list out with copies of the last width, which is how
        cells sitting in those columns end up pushed off the edge of the table.
        """
        widths = self.column_widths("""
            <table>
                <tr><td width="20">a</td><td width="100">b</td></tr>
                <tr><td colspan="4">wide</td></tr>
            </table>""")

        self.assertEqual(4, len(widths), msg='spanned columns missing from the column widths')
        self.assertEqual(20 * mm, widths[0])
        self.assertEqual(100 * mm, widths[1])
        self.assertEqual(widths[2], widths[3], msg='both spanned columns should share what is left')
        self.assertNotEqual(widths[1], widths[2],
                            msg='spanned columns just repeated the last explicit width')

    def test_header_wider_than_body_does_not_narrow_it(self):
        """
        Header and footer rows share the body's col_widths list but are laid out as their own
        data.  One reaching further across than the body must not take a share of the width
        away from the columns the body actually has.
        """
        body = '<tr><td>a</td><td>b</td></tr>'
        on_its_own = self.column_widths(f'<table>{body}</table>')

        with_wide_header = self.column_widths(
            f'<table><header><tr><td colspan="4">Title</td></tr></header>{body}</table>')
        with_wide_footer = self.column_widths(
            f'<table><footer><tr><td colspan="4">Total</td></tr></footer>{body}</table>')

        self.assertEqual(on_its_own, with_wide_header,
                         msg='the header added columns the body does not have')
        self.assertEqual(on_its_own, with_wide_footer,
                         msg='the footer added columns the body does not have')

    def test_full_width_header_over_a_hidden_column(self):
        """A hidden column leaves the body narrower than the header that spans it."""
        body = '<tr><td>a</td><td hidden_column="1">b</td><td>c</td></tr>'

        with_header = self.column_widths(
            f'<table><header><tr><td colspan="3">Title</td></tr></header>{body}</table>')
        without_header = self.column_widths(f'<table>{body}</table>')

        self.assertEqual(2, len(with_header), msg='the hidden column should be gone')
        self.assertEqual(without_header, with_header,
                         msg='the header narrowed the body columns')

    def test_watermark_from_xml(self):
        xml = """
        <document title="Watermark Test" page_size="A4">
            <watermark rotation="45" font_size="80">DRAFT</watermark>
            <table>
                <tr>
                    <td>Hello world</td>
                </tr>
            </table>
        </document>
        """
        report_xml = ReportXML(test_mode=True)
        result = report_xml.load_xml_and_make_pdf(xml=xml)

        with fitz.open("pdf", result) as doc:
            self.assertIn("DRAFT", doc[0].get_text(), msg='Watermark text missing from generated PDF')

    @staticmethod
    def get_sample_objects():
        # Define the data for the table
        data = [['Name', 'Age'],
                ['John', 25],
                ['Mary', 30],
                ['Bob', 20],
                ]

        # Define the table style
        table_style = TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.gray),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 14),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
            ('ALIGN', (0, 1), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 12),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
            ('TOPPADDING', (0, 1), (-1, -1), 6),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.whitesmoke, colors.white])
        ])

        # Create the table object
        table = Table(data)

        # Apply the table style
        table.setStyle(table_style)

        path = os.path.join(Path(__file__).resolve().parent, 'test_data/images')

        sample_label = RLImage(os.path.join(path, 'sample_label.png'), width=50 * mm, height=200 * mm)
        small_image = RLImage(os.path.join(path, 'small_image.png'), width=20 * mm, height=20 * mm)

        return {'sample': table,
                'sample_label': sample_label,
                'small_image': small_image}


@contextlib.contextmanager
def no_runaway_build(seconds=5):
    """
    Fail with TimeoutError rather than hang if a build never finishes. SIGALRM only exists on
    some platforms and only works on the main thread; elsewhere this does nothing.
    """
    if not hasattr(signal, 'SIGALRM') or threading.current_thread() is not threading.main_thread():
        yield
        return

    def timed_out(*_):
        raise TimeoutError('the build did not finish: a table was probably split forever')

    previous = signal.signal(signal.SIGALRM, timed_out)
    signal.alarm(seconds)
    try:
        yield
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, previous if previous is not None else signal.SIG_DFL)


class TableSplitTests(unittest.TestCase):
    """Where a table may break across pages. A4 portrait has a 277mm frame with 10mm borders."""

    KEPT_HEADER = '<tr row_height="20" keep_header_for_split="true"><td colspan="2">Kept</td></tr>'
    HEADER = '<header><tr row_height="10"><td>Head</td><td>h</td></tr></header>'
    FOOTER = '<footer><tr row_height="10"><td>Total</td><td>t</td></tr></footer>'

    @staticmethod
    def row(height, name):
        return f'<tr row_height="{height}"><td>{name}</td><td>x</td></tr>'

    @classmethod
    def rows(cls, *heights):
        """Rows named r1, r2, ... with the given heights in mm."""
        return ''.join(cls.row(height, f'r{number}') for number, height in enumerate(heights, 1))

    @staticmethod
    def words(table_xml, table_attributes='', before='', top_first=10, top_continuation=10, left_first=10,
              left_continuation=10):
        """Build a document holding one table, and return each page's words with their tops in mm."""
        xml = f"""
        <document title="Split Test" page_size="A4" page_orientation="portrait" page_style="blank"
                  border_top_first="{top_first}" border_bottom_first="10"
                  border_top_continuation="{top_continuation}" border_bottom_continuation="10"
                  border_left_first="{left_first}" border_left_continuation="{left_continuation}">
            {before}<table {table_attributes}>{table_xml}</table>
        </document>
        """
        with no_runaway_build():
            result = ReportXML(test_mode=True).load_xml_and_make_pdf(xml=xml)
        with fitz.open("pdf", result) as doc:
            return [[(word[4], word[1] / mm) for word in page.get_text('words')] for page in doc]

    @classmethod
    def pages(cls, table_xml, **kwargs):
        """Each page's words."""
        return [[word for word, _ in page] for page in cls.words(table_xml, **kwargs)]

    @staticmethod
    def row_names(words):
        """The row names (r0, r1, ...) among a page's words."""
        return [word for word in words if re.fullmatch(r'r\d+', word)]

    @classmethod
    def rows_by_page(cls, table_xml, **kwargs):
        """The row names on each page, so tests can compare whole layouts."""
        return [cls.row_names(page) for page in cls.pages(table_xml, **kwargs)]

    # The last resort: forcing a split where nothing else can place the table

    def test_a_row_too_tall_to_share_a_page_with_the_next_gets_a_page_of_its_own(self):
        """
        Every row fits a page, but no two fit together. The rest of the table may not split
        after its own first row, so even on a fresh page it could not be placed (LayoutError).
        """
        self.assertEqual([['r1'], ['r2'], ['r3'], ['r4']], self.rows_by_page(self.rows(180, 180, 180, 180)))

    def test_rows_that_fit_together_still_share_a_page(self):
        """A table that splits as it always did is laid out as before."""
        self.assertEqual([['r1', 'r2', 'r3'], ['r4', 'r5', 'r6']],
                         self.rows_by_page(self.rows(85, 85, 85, 85, 85, 85)))

    def test_under_a_footer_each_tall_row_still_gets_the_next_page(self):
        """
        With a footer the rest of the table follows a page break, at the top of a page as tall as
        any to come, so it is split there rather than moved on past an empty page.
        """
        self.assertEqual([['r1'], ['r2'], ['r3'], ['r4']],
                         self.rows_by_page(self.FOOTER + self.rows(170, 170, 170, 170)))

    def test_after_a_page_break_the_rest_may_still_move_on_to_a_taller_frame(self):
        """
        Each page has a 120mm frame then a 277mm one. A blank row puts a page break before the rest
        of the table, which lands in the short frame. ReportLab must still be free to move it on to
        the tall frame, where r2 fits, or a keep group fits whole, rather than force it.
        """
        cases = {
            'too tall for the short frame': ([100, 5, 130, 20], [KEEP_TYPE_NA] * 4),
            'keep group': ([100, 5, 100, 50], [KEEP_TYPE_NA, KEEP_TYPE_NA, KEEP_TYPE_START, KEEP_TYPE_END]),
        }
        for name, (heights, keep_with_next) in cases.items():
            with self.subTest(name):
                table = self.blank_table(['data', 'BLANK', 'data', 'data'], heights, keep_with_next=keep_with_next)
                buffer = io.BytesIO()
                doc = BaseDocTemplate(buffer)
                width, height = doc.pagesize
                doc.addPageTemplates([PageTemplate('page', [
                    Frame(10, height - 130 * mm, 280, 120 * mm, 0, 0, 0, 0, id='short'),
                    Frame(300, 10 * mm, 280, 277 * mm, 0, 0, 0, 0, id='tall')])])

                with no_runaway_build():
                    doc.build([table])

                with fitz.open('pdf', buffer.getvalue()) as pdf:
                    frames = [[(word[4], 'short' if word[0] < 290 else 'tall') for word in page.get_text('words')]
                              for page in pdf]
                self.assertEqual([[('r0', 'short')], [('r2', 'tall'), ('r3', 'tall')]], frames)

    def test_under_a_header_tall_rows_still_raise(self):
        """
        Not covered yet: under a <header> the same rows still raise LayoutError. The first
        table's no-progress guard counts the header the rest will repeat and refuses to split
        after one row. Letting it would also leave one row at the foot of a part-filled page
        where today the whole table moves on, so it needs its own change. When it lands, this
        should give each row a page of its own.
        """
        with self.assertRaises(LayoutError):
            self.pages(self.HEADER + self.rows(170, 170, 170, 170))

    def test_a_row_span_taller_than_a_page_is_split_across_pages(self):
        """
        Two 180mm rows sharing a spanned cell cannot fit one page. That raised LayoutError; now
        the span is cut, as the no-progress guard already does for spans taller than a page.
        """
        span = ('<tr row_height="180"><td rowspan="2">span</td><td>r1</td></tr>'
                '<tr row_height="180"><td>r2</td></tr>')

        self.assertEqual([['r1'], ['r2'], ['r3']], self.rows_by_page(span + self.row(180, 'r3')))

    # Moving on, or splitting where the table is

    def test_a_table_that_fits_a_roomier_later_page_still_moves_on_whole(self):
        """
        The first page has a deeper top border. Each table fits the next page whole but not the
        first, and cannot be split, so it moves on whole rather than being cut.
        """
        span = ('<tr row_height="120"><td rowspan="2">span</td><td>r1</td></tr>'
                '<tr row_height="120"><td>r2</td></tr>')
        keep = '<keep>' + self.rows(130, 130) + '</keep>'
        cases = {
            'span': (span, ''),
            # a footer is reserved below every row, even though a table that fits whole needs none
            'footer and span': (self.FOOTER + span, ''),
            'footer and keep group': (self.FOOTER + keep, ''),
            # min_rows_bottom ties the last rows together, so there is no split position at all
            'min_rows_bottom': (self.rows(130, 130), 'min_rows_bottom="2"'),
        }
        for name, (table_xml, table_attributes) in cases.items():
            with self.subTest(name):
                self.assertEqual([[], ['r1', 'r2']],
                                 self.rows_by_page(table_xml, table_attributes=table_attributes, top_first=60))

    def test_a_keep_group_that_a_roomier_later_page_can_split_at_still_moves_on(self):
        """
        The keep group (240mm) does not fit the first page, but on the taller pages to come it fits
        and the table can split after it, so the table moves on rather than cutting the group.
        """
        rows = '<keep>' + self.rows(120, 120) + '</keep>' + self.row(120, 'r3')

        self.assertEqual([[], ['r1', 'r2'], ['r3']], self.rows_by_page(rows, top_first=60))

    def test_a_keep_group_too_tall_for_any_page_starts_on_the_first(self):
        """
        The continuation pages are taller, but the group fits none of them, so moving the table
        on would only have left the first page empty before cutting the group anyway.
        """
        rows = '<keep>' + self.rows(130, 130) + '</keep>' + self.row(130, 'r3')

        self.assertEqual([['r1'], ['r2'], ['r3']], self.rows_by_page(rows, top_first=60, top_continuation=40))

    def test_after_a_page_break_a_taller_first_page_does_not_leave_a_page_empty(self):
        """
        The span (280mm) would fit the first page, which has the shallower top border, but not a
        continuation page. The first page never recurs, so moving on cannot help.
        """
        span = ('<tr row_height="140"><td rowspan="2">span</td><td>r1</td></tr>'
                '<tr row_height="140"><td>r2</td></tr>')

        pages = self.rows_by_page(span, before=f'<table>{self.row(30, "r0")}</table><page_break/>', top_first=5)

        self.assertEqual([['r0'], ['r1'], ['r2']], pages)

    def test_a_wider_page_to_come_does_not_leave_a_page_empty(self):
        """
        Columns from XML have fixed widths, so a wider continuation page wraps no row shorter and
        cannot help the keep group fit.
        """
        rows = '<keep>' + self.rows(180, 180) + '</keep>' + self.row(180, 'r3')

        self.assertEqual([['r1'], ['r2'], ['r3']],
                         self.rows_by_page(rows, left_first=20, left_continuation=0))

    # Kept headers (keep_header_for_split)

    def test_a_kept_header_is_repeated_on_each_page(self):
        pages = self.pages(self.KEPT_HEADER + self.rows(100, 100, 100, 100))

        self.assertEqual(2, len(pages))
        for words in pages:
            self.assertIn('Kept', words)

    def test_a_kept_header_without_any_spans_is_repeated_on_each_page(self):
        """ReportLab only sets _colSpanCells on a table with spans, so splitting one without crashed."""
        header = '<tr row_height="20" keep_header_for_split="true"><td>Kept</td><td>k</td></tr>'

        pages = self.pages(header + self.rows(100, 100, 100, 100))

        self.assertEqual(2, len(pages))
        for words in pages:
            self.assertIn('Kept', words)

    def test_a_row_too_tall_to_sit_under_a_kept_header_raises_rather_than_looping(self):
        """
        A row cannot share a page with the kept header. These raise LayoutError on 0.2.25 too, but
        with the last resort, splitting after the kept header alone gives a rest that is the same
        table again; unguarded, that made pages holding only the header until memory ran out.
        """
        cases = [
            self.rows(100, 100, 270, 100),
            self.rows(270, 270, 270),
            # 255mm fits under the kept header alone, but not with the footer as well
            self.FOOTER + self.rows(100, 100, 255, 100),
        ]
        for rows in cases:
            with self.subTest(rows=rows):
                with self.assertRaises(LayoutError):
                    self.pages(self.KEPT_HEADER + rows)

    def test_a_kept_header_that_breaks_to_a_new_page_still_builds(self):
        """
        The kept header row itself has break="true", so it starts the rest of the table. That rest
        is as long as the table it came from, but its first row is a plain copy of the kept header,
        so it is not the same table again, and the progress guard must not refuse it.
        """
        kept = '<tr row_height="20" keep_header_for_split="true" break="true"><td colspan="2">Kept</td></tr>'

        pages = self.rows_by_page(self.row(265, 'r1') + kept + self.row(100, 'r2') + self.row(100, 'r3') +
                                  self.row(100, 'r4') + self.row(100, 'r5'))

        self.assertEqual([['r1'], ['r2', 'r3'], ['r4', 'r5']], pages)

    def test_a_kept_header_above_a_keep_group_taller_than_a_page_is_left_alone(self):
        """
        Only the kept header fits the first page, and the group then splits as it did on 0.2.25.
        The rest has as many rows as the table but is not the same table, so it is not refused.
        """
        rows = '<keep>' + self.rows(60, 180, 60) + '</keep>'

        pages = self.pages(self.KEPT_HEADER + rows)

        self.assertEqual([[], ['r1', 'r2'], ['r3']], [self.row_names(page) for page in pages])
        for words in pages:
            self.assertIn('Kept', words)

    def test_a_kept_header_under_a_header_keeps_its_own_height_and_style(self):
        """
        A table's rest gains the header rows and the kept header, and puts the header first. Its
        style commands always did, but its rows, heights and cell styles put the kept header first,
        so on continuation pages each took the other's height, background and lines. Its kept header
        markers also skipped the header rows, so splitting it again ran off the end (IndexError).
        """
        header = '<header><tr row_height="10" style="background:#ff0000"><td>Head</td><td>h</td></tr></header>'
        kept = ('<tr row_height="20" style="background:#0000ff" keep_header_for_split="true">'
                '<td colspan="2">Kept</td></tr>')
        xml = f"""
        <document title="Split Test" page_size="A4" page_orientation="portrait" page_style="blank"
                  border_top_first="10" border_bottom_first="10"
                  border_top_continuation="10" border_bottom_continuation="10">
            <table>{header}{kept}{self.rows(60, 60, 180, 240, 180)}</table>
        </document>
        """
        with no_runaway_build():
            result = ReportXML(test_mode=True).load_xml_and_make_pdf(xml=xml)

        with fitz.open("pdf", result) as doc:
            pages = [([(word[4], word[1] / mm) for word in page.get_text('words')],
                      {self.colour(drawing['fill']): (drawing['rect'].y0 / mm, drawing['rect'].y1 / mm)
                       for drawing in page.get_drawings() if drawing.get('fill')})
                     for page in doc]
        self.assertEqual([['r1', 'r2'], ['r3'], ['r4'], ['r5']],
                         [self.row_names(word for word, _ in words) for words, _ in pages])
        for number, (words, bands) in enumerate(pages[1:], 2):
            with self.subTest(page=number):
                tops = dict(words)
                self.assertEqual(['Head', 'h', 'Kept'], [word for word, _ in words][:3])
                self.assertEqual((10, 20), tuple(round(y) for y in bands['ff0000']))
                self.assertEqual((20, 40), tuple(round(y) for y in bands['0000ff']))
                self.assertTrue(20 < tops['Kept'] < 40)

    @staticmethod
    def colour(rgb):
        return ''.join(f'{round(channel * 255):02x}' for channel in rgb)

    def test_a_kept_header_after_a_header_is_repeated_in_place_of_the_row_before(self):
        """
        On 0.2.25 the third page repeated row r6 where the kept header belongs, as the rest's
        kept header markers did not line up with its rows.
        """
        rows = self.rows(60, 60, 60, 60, 60, 60) + self.KEPT_HEADER + ''.join(
            self.row(60, f'r{number}') for number in range(7, 11))

        pages = self.pages(self.HEADER + rows)

        self.assertEqual(3, len(pages))
        self.assertEqual(['Head', 'Kept', 'r9', 'r10'],
                         [word for word in pages[2] if word in ('Kept', 'Head') or re.fullmatch(r'r\d+', word)])

    def test_under_a_header_a_keep_group_still_moves_on_whole(self):
        """
        The first table's rest gains the header rows, so it has as many rows as the table though
        it is not the same table. The progress guard took that for no progress and raised.
        """
        header = self.HEADER.replace('</header>', '<tr row_height="10"><td>Head2</td><td>h</td></tr></header>')
        rows = self.row(100, 'r1') + '<keep>' + self.row(150, 'r2') + self.row(100, 'r3') + '</keep>' + self.row(100, 'r4')

        pages = self.pages(header + rows)

        self.assertEqual([['r1', 'r2'], ['r3', 'r4']], [self.row_names(page) for page in pages])
        self.assertIn('Head2', pages[1])

    def test_a_header_that_grows_part_way_through_still_splits(self):
        """
        The header changes to a two row one for r4. The rest after r3 is then as long as the table
        it came from, though r3 was placed, so the progress guards took it for no progress.
        """
        header = self.HEADER.replace('<header>', '<header output="0">')
        longer = ('<header output="0"><tr row_height="10"><td>HeadA</td><td>h</td></tr>'
                  '<tr row_height="10"><td>HeadB</td><td>h</td></tr></header>')

        pages = self.pages(header + self.KEPT_HEADER + self.rows(100, 100, 100) + longer +
                           self.row(150, 'r4') + self.row(60, 'r5'))

        self.assertEqual([['r1', 'r2'], ['r3'], ['r4', 'r5']], [self.row_names(page) for page in pages])
        self.assertEqual(['HeadA', 'HeadB', 'Kept'], [word for word in pages[2] if word in ('HeadA', 'HeadB', 'Kept')])

    def test_a_keep_group_under_a_header_and_a_taller_kept_header_is_cut_rather_than_raise(self):
        """
        The keep group (260mm) cannot sit under the 6mm header and 30mm kept header on any page.
        0.2.25 only fitted it by drawing that header band 12mm tall; at the right height the split
        falls back to the largest position that fits, as it does for any group too tall for a page.
        """
        header = '<header><tr row_height="6"><td>Head</td><td>h</td></tr></header>'
        kept = '<tr row_height="30" keep_header_for_split="true"><td colspan="2">Kept</td></tr>'
        rows = self.rows(200, 200) + '<keep>' + self.row(130, 'r3') + self.row(130, 'r4') + '</keep>'

        self.assertEqual([['r1'], ['r2'], ['r3'], ['r4']], self.rows_by_page(header + kept + rows))

    def test_a_row_span_cut_under_a_kept_header_starts_below_it(self):
        """
        The rest of a cut row span was not moved down for the kept header put back above it, so the
        span took in the kept header's row and drew "Kept" inside it.
        """
        span = ('<tr row_height="200"><td rowspan="3">span</td><td>r1</td></tr>'
                '<tr row_height="60"><td>r2</td></tr><tr row_height="60"><td>r3</td></tr>')

        words = self.words(self.KEPT_HEADER + span + self.row(60, 'r4'))

        last = dict(words[-1])
        self.assertEqual(['r2', 'r3', 'r4'], self.row_names(word for word, _ in words[-1]))
        self.assertLess(last['Kept'], 30)  # the kept header's own 20mm row at the top of the page

    def test_a_kept_header_is_not_repeated_straight_under_itself(self):
        """
        Only the kept header fits under itself before a row span taller than the rest of the page.
        The rest of the table is not forced part way down the first page, which would print the
        kept header twice in a row; it moves on.
        """
        span = ('<tr row_height="200"><td rowspan="3">span</td><td>r1</td></tr>'
                '<tr row_height="60"><td>r2</td></tr><tr row_height="60"><td>r3</td></tr>')

        pages = self.pages(self.KEPT_HEADER + span)

        self.assertEqual([1, 1, 1], [page.count('Kept') for page in pages])

    def test_auto_height_rows_do_not_count_as_fitting_a_later_page(self):
        """
        With auto row heights and a row span, ReportLab marks rows past the frame with negative
        placeholder heights. Summed, they read as fitting a taller page to come, so the table was
        moved on past an empty first page before being split all the same.
        """
        rows = ('<tr><td rowspan="2">sp</td><td>r1</td></tr><tr><td>r2</td></tr>' + self.row(140, 'r3') +
                self.row(140, 'r4') + ''.join(f'<tr><td>r{number}</td><td>x</td></tr>' for number in range(5, 8)))

        pages = self.rows_by_page(rows, table_attributes='min_rows_top="4"', top_first=60)

        self.assertEqual([['r1', 'r2', 'r3'], ['r4', 'r5', 'r6', 'r7']], pages)

    # BLANK rows (row types cannot be set from XML, so these build tables directly)

    @staticmethod
    def blank_table(row_types, heights, repeat_rows=0, keep_with_next=None, keep_header_rows=()):
        count = len(row_types)
        return EnhancedTable({'row_data': [[f'r{number}' if row_type != 'BLANK' else '']
                                           for number, row_type in enumerate(row_types)],
                              'row_properties': [{'row_type': row_type} for row_type in row_types],
                              'keep_with_next': keep_with_next or [KEEP_TYPE_NA] * count,
                              'headers_index': [None] * count,
                              'footers_index': [None] * count},
                             headers=[], footers=[],
                             keep_header_rows=[None] * count if keep_header_rows == () else keep_header_rows,
                             row_heights=[height * mm for height in heights], repeat_rows=repeat_rows,
                             initial=True)

    def test_a_forced_split_after_a_blank_first_row_keeps_the_row(self):
        """
        No two rows fit a page, so the split goes after the first row. That row is blank, and
        dropping blank rows at a split left the first part with no rows, which ReportLab refused.
        """
        table = self.blank_table(['BLANK', 'data', 'data', 'data'], [180, 180, 180, 180])
        buffer = io.BytesIO()

        with no_runaway_build():
            SimpleDocTemplate(buffer, topMargin=10 * mm, bottomMargin=10 * mm).build([table])

        with fitz.open('pdf', buffer.getvalue()) as doc:
            pages = [page.get_text().split() for page in doc]
        self.assertEqual([[], ['r1'], ['r2'], ['r3']], pages)

    @staticmethod
    def build_pages(table):
        """Build a table on A4 with 10mm top and bottom margins, and return each page's words."""
        buffer = io.BytesIO()
        with no_runaway_build():
            SimpleDocTemplate(buffer, topMargin=10 * mm, bottomMargin=10 * mm).build([table])
        with fitz.open('pdf', buffer.getvalue()) as doc:
            return [page.get_text().split() for page in doc]

    def test_a_kept_header_before_a_blank_row_split_is_the_kept_header(self):
        """
        The split falls after a blank row, which the first part drops. The kept header was then
        looked up one row too far down, so the data row r1 was repeated in its place.
        """
        table = self.blank_table(['data', 'data', 'data', 'BLANK', 'data', 'data'], [20, 100, 100, 5, 100, 100],
                                 keep_header_rows=['true', None, None, None, None, None])

        self.assertEqual([['r0', 'r1', 'r2'], ['r0', 'r4', 'r5']], self.build_pages(table))

    def test_a_table_without_kept_header_markers_still_splits(self):
        """keep_header_rows=None, as a table built directly may have, raised TypeError at any split."""
        table = self.blank_table(['data'] * 4, [100] * 4, keep_header_rows=None)

        self.assertEqual([['r0', 'r1'], ['r2', 'r3']], self.build_pages(table))

    def test_a_blank_row_after_repeated_rows_still_becomes_a_page_break(self):
        """Only a blank first row is kept at a split; after repeated rows it is dropped as before."""
        table = self.blank_table(['data', 'BLANK', 'data', 'data'], [20, 10, 100, 100], repeat_rows=1)
        table.wrap(500, 77 * mm)

        parts = table.split(500, 77 * mm)

        self.assertEqual([EnhancedTable, PageBreak, EnhancedTable], [type(part) for part in parts])
        self.assertEqual(1, len(parts[0]._rowHeights))


class ColumnWidthTests(unittest.TestCase):
    """
    Unit tests for process_column_widths, which the golden image reports barely cover -
    keep_with_next.xml is the only one using a percentage, and it is a plain 70%.
    """

    table_width = 200.0  # millimetres, the units process_column_widths expects

    def assert_widths(self, col_widths, expected_mm):
        """
        Widths come back in points, so divide by mm to compare them in millimetres.
        """
        actual = ReportXML.process_column_widths(col_widths, self.table_width)
        self.assertEqual(len(actual), len(expected_mm), msg='wrong number of columns')
        for index, (got, expected) in enumerate(zip(actual, expected_mm)):
            self.assertAlmostEqual(got / mm, expected, places=6,
                                   msg=f'column {index} is {got / mm}mm, expected {expected}mm')

    # the units contract, so that "fixing" the mm/points split fails loudly here

    def test_widths_are_returned_in_points(self):
        widths = ReportXML.process_column_widths([None, None], self.table_width)
        self.assertAlmostEqual(sum(widths), self.table_width * mm, places=6)

    # percentages over 100 used to push undefined columns negative

    def test_percentage_over_100_does_not_go_negative(self):
        self.assert_widths([ColumnWidthPercentage(120), None], [240.0, 0.0])

    def test_percentage_over_100_clamps_every_undefined_column(self):
        self.assert_widths([ColumnWidthPercentage(60), ColumnWidthPercentage(70), None, None],
                           [120.0, 140.0, 0.0, 0.0])

    def test_percentages_at_100_leave_undefined_column_empty(self):
        self.assert_widths([ColumnWidthPercentage(100), None], [200.0, 0.0])

    def test_percentages_just_under_100_are_not_clamped(self):
        self.assert_widths([ColumnWidthPercentage(99.9), None], [199.8, 0.2])

    # behaviour the clamp must leave alone

    def test_undefined_column_takes_the_remaining_percentage(self):
        self.assert_widths([ColumnWidthPercentage(70), None], [140.0, 60.0])

    def test_undefined_columns_share_the_table_equally(self):
        third = self.table_width / 3
        self.assert_widths([None, None, None], [third, third, third])

    def test_percentages_are_shares_of_what_the_fixed_columns_leave(self):
        # 70% of the remaining 150mm, not 70% of the whole 200mm table
        self.assert_widths([50.0, ColumnWidthPercentage(70), None], [50.0, 105.0, 45.0])

    def test_percentages_under_100_leave_the_table_short(self):
        self.assert_widths([ColumnWidthPercentage(70)], [140.0])

    def test_fixed_columns_wider_than_the_table_clamp_the_remainder(self):
        self.assert_widths([150.0, 100.0, None], [150.0, 100.0, 0.0])

    def test_all_fixed_columns_are_used_as_is(self):
        self.assert_widths([50.0, 50.0], [50.0, 50.0])


class ScaledSvgSizeTests(unittest.TestCase):
    """
    A ratio scaled svg and a ruler are drawn at true size: measured in the finished pdf, a line
    n units long at 1:r is n / r millimetres, whichever svglib version draws it.
    """

    @staticmethod
    def pdf_from_xml(body):
        report_xml = ReportXML(test_mode=True)
        result = report_xml.load_xml_and_make_pdf(
            f'<document page_size="A4" page_orientation="portrait">{body}</document>')
        return fitz.open('pdf', result.getvalue())

    @staticmethod
    def longest_lines_mm(document):
        """The longest horizontal and the longest vertical line on the first page, in millimetres."""
        across, down = [0.0], [0.0]
        for drawing in document[0].get_drawings():
            for item in drawing['items']:
                if item[0] != 'l':
                    continue
                start, end = item[1], item[2]
                if abs(start.y - end.y) < 0.01:
                    across.append(abs(start.x - end.x))
                if abs(start.x - end.x) < 0.01:
                    down.append(abs(start.y - end.y))
        return max(across) / mm, max(down) / mm

    @staticmethod
    def font_sizes(document):
        return [span['size'] for block in document[0].get_text('dict')['blocks']
                for line in block.get('lines', []) for span in line['spans']]

    def test_ratio_svg_is_true_size(self):
        svg = ('<svg data-ratio="1:10" data-units="mm" width="800" height="2000">'
               '<line x1="0" y1="0" x2="762" y2="0" stroke="black"/>'
               '<line x1="0" y1="0" x2="0" y2="1981" stroke="black"/></svg>')
        across, down = self.longest_lines_mm(self.pdf_from_xml(f'<table><tr><td>{svg}</td></tr></table>'))
        self.assertAlmostEqual(76.2, across, delta=0.05)
        self.assertAlmostEqual(198.1, down, delta=0.05)

    def test_ratio_svg_text_keeps_its_size(self):
        svg = ('<svg data-ratio="1:1" data-units="mm" width="100" height="50">'
               '<text x="10" y="20">no size</text>'
               '<text x="10" y="40" font-size="12">twelve</text></svg>')
        sizes = self.font_sizes(self.pdf_from_xml(f'<table><tr><td>{svg}</td></tr></table>'))
        self.assertEqual(2, len(sizes))
        for size in sizes:
            self.assertAlmostEqual(12, size, delta=0.01)

    def test_ratio_svg_keeps_explicit_units(self):
        from django_advanced_pdf.engine.svg_tools.svg_scaled_renderer import PX_TO_PT

        texts = []
        if PX_TO_PT != 1:
            # svglib 1.5.1 reads pt as 1.25pt, and svglib 1 has no rem
            texts = ['<text x="10" y="20" font-size="12pt">points</text>',
                     '<text x="10" y="40" font-size="1rem">root</text>']
        svg = ('<svg data-ratio="1:1" data-units="mm" width="100" height="50">'
               '<line x1="0" y1="0" x2="30mm" y2="0" stroke="black"/>'
               '<line x1="0" y1="0" x2="0" y2="0.5in" stroke="black"/>'
               f'{"".join(texts)}</svg>')
        document = self.pdf_from_xml(f'<table><tr><td>{svg}</td></tr></table>')
        across, down = self.longest_lines_mm(document)
        self.assertAlmostEqual(30, across, delta=0.05)
        self.assertAlmostEqual(12.7, down, delta=0.05)
        sizes = self.font_sizes(document)
        self.assertEqual(len(texts), len(sizes))
        for size in sizes:
            self.assertAlmostEqual(12, size, delta=0.01)

    def test_ratio_svg_applies_its_stylesheet(self):
        svg = ('<svg data-ratio="1:1" data-units="mm" width="100" height="50">'
               '<style>.label {font-size:24}</style>'
               '<text class="label" x="10" y="20">styled</text></svg>')
        sizes = self.font_sizes(self.pdf_from_xml(f'<table><tr><td>{svg}</td></tr></table>'))
        self.assertEqual(1, len(sizes))
        self.assertAlmostEqual(24, sizes[0], delta=0.01)

    def test_ruler_in_a_table_is_true_size(self):
        across, _ = self.longest_lines_mm(self.pdf_from_xml('<table><tr><td><ruler data-ratio="1:10"/></td></tr></table>'))
        self.assertAlmostEqual(50, across, delta=0.05)

    def test_ruler_drawn_to_a_canvas_is_true_size(self):
        from io import BytesIO
        from reportlab.pdfgen.canvas import Canvas
        from django_advanced_pdf.engine.svg_tools.svg_ruler import SVGScaledRuler

        buffer = BytesIO()
        canvas = Canvas(buffer)
        SVGScaledRuler().draw_to_canvas(canvas=canvas, x=20, y=20, ratio='1:20')
        canvas.save()
        document = fitz.open('pdf', buffer.getvalue())
        across, _ = self.longest_lines_mm(document)
        self.assertAlmostEqual(50, across, delta=0.05)
        for size in self.font_sizes(document):
            self.assertAlmostEqual(12, size, delta=0.01)
