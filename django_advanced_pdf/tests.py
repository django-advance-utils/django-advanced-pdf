import io
import os
import pathlib
import signal
import unittest
from pathlib import Path
import fitz
from lxml import etree
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, TableStyle, Table, Image as RLImage
from reportlab.platypus.doctemplate import LayoutError

from django_advanced_pdf.engine.enhanced_table.enhanced_tables import EnhancedTable
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


class TableSplitTests(unittest.TestCase):
    """Where a table may break across pages."""

    @staticmethod
    def pages(rows_xml):
        xml = f"""
        <document title="Split Test" page_size="A4" page_orientation="portrait" page_style="blank"
                  border_top_first="10" border_bottom_first="10"
                  border_top_continuation="10" border_bottom_continuation="10">
            <table>{rows_xml}</table>
        </document>
        """
        result = ReportXML(test_mode=True).load_xml_and_make_pdf(xml=xml)
        with fitz.open("pdf", result) as doc:
            return [page.get_text() for page in doc]

    def test_a_row_too_tall_to_share_a_page_with_the_next_gets_a_page_of_its_own(self):
        """
        Every row (180mm) fits a page (277mm), but no two fit together. The first page took one row; the
        rest of the table could not be split after its own first row, so after being moved to
        a fresh page it still could not be placed and the build raised a LayoutError.
        """
        rows = ''.join(f'<tr row_height="180"><td>row {number}</td></tr>' for number in range(1, 5))

        pages = self.pages(rows)

        self.assertEqual(4, len(pages))
        for number, text in enumerate(pages, 1):
            self.assertIn(f'row {number}', text)

    def test_under_a_footer_each_tall_row_still_gets_the_next_page(self):
        """
        With a footer the split puts a page break before the rest of the table, so the rest
        starts on a fresh page without ReportLab having moved it there. Unmarked, it was refused
        once and moved on, leaving an empty page before every row after the first.
        """
        rows = ''.join(f'<tr row_height="170"><td>row {number}</td></tr>' for number in range(1, 5))

        pages = self.pages(f'<footer><tr><td>Total</td></tr></footer>{rows}')

        self.assertEqual([[f'row {number}'] for number in range(1, 5)],
                         [[line for line in text.splitlines() if line.startswith('row')] for text in pages])

    def test_under_a_header_tall_rows_still_raise(self):
        """
        Not covered yet: under a <header> the same rows still raise LayoutError. The first
        table's no-progress guard counts the header the rest will repeat and refuses to split
        after one row. Letting it would also leave one row at the foot of a part-filled page
        where today the whole table moves on, so it needs its own change. When it lands, this
        should give each row a page of its own.
        """
        rows = ''.join(f'<tr row_height="170"><td>row {number}</td></tr>' for number in range(1, 5))

        with self.assertRaises(LayoutError):
            self.pages(f'<header><tr><td>Head</td></tr></header>{rows}')

    def test_a_row_span_taller_than_a_page_is_split_across_pages(self):
        """
        Two 180mm rows sharing a spanned cell cannot fit one page. That raised LayoutError; now
        the span is cut, as the no-progress guard already does for spans taller than a page.
        The first page is left empty: the table cannot split there, so ReportLab moves it on
        before the last resort applies.
        """
        rows = ('<tr row_height="180"><td rowspan="2">span</td><td>s1</td></tr>'
                '<tr row_height="180"><td>s2</td></tr>'
                '<tr row_height="180"><td>after</td><td>a</td></tr>')

        pages = [text for text in self.pages(rows) if 'Page 1 of' not in text]

        self.assertEqual(3, len(pages))
        self.assertIn('s1', pages[0])
        self.assertIn('s2', pages[1])
        self.assertIn('after', pages[2])

    def test_rows_that_fit_together_still_share_a_page(self):
        """The last resort is taken only where the table could not otherwise be placed."""
        rows = ''.join(f'<tr row_height="85"><td>row {number}</td></tr>' for number in range(1, 7))

        pages = self.pages(rows)

        self.assertEqual(['row 1', 'row 2', 'row 3'], [line for line in pages[0].splitlines() if line.startswith('row')])
        self.assertEqual(['row 4', 'row 5', 'row 6'], [line for line in pages[1].splitlines() if line.startswith('row')])


    KEPT_HEADER = '<tr row_height="20" keep_header_for_split="true"><td colspan="2">Kept</td></tr>'

    def kept_header_pages(self, heights, footer=''):
        """
        Build a two column table under a kept header, failing rather than hanging if the build
        does not finish.
        """
        rows = ''.join(f'<tr row_height="{height}"><td>row {number}</td><td>x</td></tr>'
                       for number, height in enumerate(heights, 1))

        def timed_out(*_):
            raise TimeoutError('the table was split forever')

        previous = signal.signal(signal.SIGALRM, timed_out)
        signal.alarm(20)
        try:
            return self.pages(footer + self.KEPT_HEADER + rows)
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, previous)

    @unittest.skipUnless(hasattr(signal, 'SIGALRM'), 'needs SIGALRM to stop a runaway build')
    def test_a_row_too_tall_to_sit_under_a_kept_header_raises_rather_than_looping(self):
        """
        The 270mm row cannot share a page with the 20mm kept header. Splitting after the kept
        header alone gave a remainder that was the same table again, so the build made pages
        holding only the header until it ran out of memory.
        """
        footer = '<footer><tr><td>Total</td><td>t</td></tr></footer>'
        cases = [
            ([100, 100, 270, 100], ''),
            ([270, 270, 270], ''),
            # 255mm fits under the kept header alone, but not with the footer as well
            ([100, 100, 255, 100], footer),
        ]
        for heights, table_footer in cases:
            with self.subTest(heights=heights, footer=bool(table_footer)):
                with self.assertRaises(LayoutError):
                    self.kept_header_pages(heights, table_footer)

    @unittest.skipUnless(hasattr(signal, 'SIGALRM'), 'needs SIGALRM to stop a runaway build')
    def test_a_kept_header_is_repeated_on_each_page(self):
        pages = self.kept_header_pages([100, 100, 100, 100])

        self.assertEqual(2, len(pages))
        for text in pages:
            self.assertIn('Kept', text)

    def test_a_kept_header_without_any_spans_is_repeated_on_each_page(self):
        """ReportLab only sets _colSpanCells on a table with spans, so splitting one without crashed."""
        header = '<tr row_height="20" keep_header_for_split="true"><td>Kept</td><td>k</td></tr>'
        rows = ''.join(f'<tr row_height="100"><td>row {number}</td><td>x</td></tr>' for number in range(1, 5))

        pages = self.pages(header + rows)

        self.assertEqual(2, len(pages))
        for text in pages:
            self.assertIn('Kept', text)

    def test_a_forced_split_after_a_blank_first_row_keeps_the_row(self):
        """
        Row types are not settable from XML, so build the table directly. No two rows fit a
        page, so the split goes after the first row. That row is blank, and dropping blank rows
        at a split left the first part with no rows, which ReportLab refused to build. As with
        a row span, the first page is left empty before the last resort applies.
        """
        rows = 4
        table = EnhancedTable({'row_data': [['']] + [[f'row {number}'] for number in range(1, rows)],
                               'row_properties': [{'row_type': 'BLANK'}] + [{} for _ in range(1, rows)],
                               'headers_index': [None] * rows,
                               'footers_index': [None] * rows},
                              headers=[], footers=[], keep_header_rows=[None] * rows,
                              row_heights=[180 * mm] * rows)
        buffer = io.BytesIO()

        SimpleDocTemplate(buffer, topMargin=10 * mm, bottomMargin=10 * mm).build([table])

        with fitz.open('pdf', buffer.getvalue()) as doc:
            pages = [page.get_text() for page in doc]
        self.assertEqual(rows + 1, len(pages))
        self.assertEqual(['', ''], [text.strip() for text in pages[:2]])
        for number in range(1, rows):
            self.assertIn(f'row {number}', pages[number + 1])


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
