import os
import pathlib
import unittest
from pathlib import Path
import fitz
from lxml import etree
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import TableStyle, Table, Image as RLImage

from django_advanced_pdf.engine.report_xml import ReportXML
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
