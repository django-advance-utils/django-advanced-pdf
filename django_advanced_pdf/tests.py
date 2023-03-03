import pathlib
import unittest
from pathlib import Path
import fitz
from reportlab.lib import colors
from reportlab.platypus import TableStyle, Table

from django_advanced_pdf.engine.report_xml import ReportXML
from PIL import Image, ImageChops


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

    def test_hidden(self):
        self.run_report(name='hidden')

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

        return {'sample': table}