import os
import pathlib
import unittest
from pathlib import Path
import fitz
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import TableStyle, Table, Image as RLImage

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
