import base64
import os
import pathlib

from PyPDF2 import PdfWriter, PdfReader
from advanced_pdf_examples.models import Company
from ajax_helpers.mixins import AjaxHelpers
from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.template.loader import get_template
from django.urls import reverse
from django.views import View
from django.views.generic import TemplateView
from django_datatables.columns import MenuColumn
from django_datatables.datatables import DatatableView
from django_datatables.helpers import DUMMY_ID
from django_menus.menu import MenuMixin, MenuItem, HtmlMenu, AjaxButtonMenuItem
from django_modals.modals import ModelFormModal
from django_modals.processes import PERMISSION_OFF
from reportlab.lib import colors
from reportlab.platypus import Table, TableStyle

from django_advanced_pdf.engine.report_xml import ReportXML
from django_advanced_pdf.mixins import TaskDownloadMixin
from django_advanced_pdf.models import PrintingTemplate
from django_advanced_pdf.views import DatabasePDFView


class MainMenu(AjaxHelpers, MenuMixin):
    def setup_menu(self):
        # noinspection PyUnresolvedReferences
        self.add_menu('main_menu').add_items(
            ('advanced_pdf_examples:from_database_example', 'From Database Example'),
            ('advanced_pdf_examples:from_file_example', 'From File Example'),
            ('advanced_pdf_examples:view_companies_pdf', 'View Companies PDF'),
            ('advanced_pdf_examples:view_report_pdf', 'View Report'),
            ('advanced_pdf_examples:view_headed_notepaper_pdf', 'View Headed Notepaper PDF'),
            ('advanced_pdf_examples:process_pdf,-', 'Process PDF Via Celery'),
            MenuItem(url='admin:index',
                     menu_display='Admin',
                     visible=self.request.user.is_superuser),
        )


class FromDatabaseExampleIndex(MainMenu, DatatableView):
    template_name = 'advanced_pdf_examples/index.html'

    model = PrintingTemplate

    def setup_menu(self):
        super().setup_menu()

        self.add_menu('print_template', 'button_group').add_items(
            MenuItem(url='advanced_pdf_examples:printing_template_modal',
                     url_kwargs={'slug': '-'},
                     menu_display='Add',
                     font_awesome='fa fa-plus'),

        )

    def setup_table(self, table):
        table.add_columns(
            ('id', {'column_defs': {'width': '30px'}}),
            'name',
            MenuColumn(column_name='menu', field='id', menu=HtmlMenu(self.request, 'button_group').add_items(
                MenuItem(url='advanced_pdf_examples:printing_template_modal',
                         url_kwargs={'slug': DUMMY_ID},
                         css_classes='btn btn-sm btn-outline-dark',
                         menu_display='',
                         font_awesome='fa fa-edit'),

                AjaxButtonMenuItem(button_name='duplicate_pdf',
                                   css_classes='btn btn-sm btn-outline-dark',
                                   menu_display='',
                                   ajax_kwargs={'pk': DUMMY_ID},
                                   font_awesome='fa fa-clone'),
                AjaxButtonMenuItem(button_name='download_pdf',
                                   css_classes='btn btn-sm btn-outline-dark',
                                   menu_display='',
                                   ajax_kwargs={'pk': DUMMY_ID},
                                   font_awesome='fa fa-download'),
                MenuItem(url='advanced_pdf_examples:view_example_database_pdf',
                         url_kwargs={'pk': DUMMY_ID},
                         css_classes='btn btn-sm btn-outline-dark',
                         menu_display='',
                         font_awesome='far fa-file-pdf'),
                )),
        )

    def button_duplicate_pdf(self, *args, **kwargs):
        printing_template = get_object_or_404(PrintingTemplate, pk=kwargs['pk'])
        printing_template.pk = None
        printing_template.name += ' (Copy)'
        printing_template.save()
        return self.command_response('reload')

    def button_download_pdf(self, *args, **kwargs):
        printing_template = get_object_or_404(PrintingTemplate, pk=kwargs['pk'])
        result = printing_template.make_pdf()
        return self.command_response('save_file', data=base64.b64encode(result.read()).decode('ascii'),
                                     filename=f'{printing_template.name}.pdf', type='application/pdf')


class PrintingTemplateModal(ModelFormModal):
    size = 'xl'
    model = PrintingTemplate

    permission_delete = PERMISSION_OFF

    form_fields = ['name', 'xml']


class ExampleDatabasePDFView(DatabasePDFView):
    def get_pager_kwargs(self):
        return {'program_name': 'Django Advanced PDF Viewer'}


class FromFileExampleIndex(MainMenu, DatatableView):
    template_name = 'advanced_pdf_examples/index.html'

    @staticmethod
    def get_table_query(table, **kwargs):
        data = []
        path = os.path.join(settings.BASE_DIR, 'advanced_pdf_examples/templates/file_examples/')
        for xml_file in pathlib.Path(path).glob('*.xml'):
            name = os.path.basename(xml_file).split('.')[0]
            data.append({'id': name, 'name': name})
        return data

    def setup_table(self, table):
        table.add_columns(
            '.id',
            'name',
            MenuColumn(column_name='menu', field='id', menu=HtmlMenu(self.request, 'button_group').add_items(
                MenuItem(url='advanced_pdf_examples:view_example_file_pdf',
                         url_kwargs={'filename': DUMMY_ID},
                         css_classes='btn btn-sm btn-outline-dark',
                         menu_display='',
                         font_awesome='far fa-file-pdf'),
            )),
        )


class ExampleFilePDFView(View):
    def get(self, request, filename):
        template = get_template(f'file_examples/{filename}.xml')
        xml = template.render({})

        object_lookup = self.get_sample_objects()
        report_xml = ReportXML(object_lookup=object_lookup)
        result = report_xml.load_xml_and_make_pdf(xml)
        response = HttpResponse(result.getvalue(), content_type='application/pdf')
        return response

    @staticmethod
    def get_sample_objects():
        # Define the data for the table
        data = [['Name', 'Age'],
                ['John', 25],
                ['Mary', 30],
                ['Bob', 20],
                ]

        data2 = [['Name', 'Age'],
                 ['John', 25],
                 ['Mary', 30],
                 ['Bob', 20],
                 ['Barry', 42],
                 ['Adam', 18],
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

        sample_table = Table(data)
        sample_table.setStyle(table_style)

        sample_table2 = Table(data2)
        sample_table2.setStyle(table_style)

        return {'sample': sample_table,
                'sample1': sample_table,
                'sample2': sample_table2,
                'default': sample_table2
                }


class CompaniesPDFView(View):
    def get(self, request):
        template = get_template(f'file_examples/with_context/companies.xml')
        xml = template.render({'companies': Company.objects.all()})
        report_xml = ReportXML()
        result = report_xml.load_xml_and_make_pdf(xml)
        response = HttpResponse(result.getvalue(), content_type='application/pdf')
        return response


class ReportExampleView(View):
    def get(self, request):
        output = PdfWriter()
        template_files = ['basic', 'border']
        response = HttpResponse(content_type='application/pdf')
        for template_file in template_files:
            template = get_template(f'file_examples/{template_file}.xml')
            xml = template.render({})
            report_xml = ReportXML()
            result = report_xml.load_xml_and_make_pdf(xml)
            current_pdf = PdfReader(result)
            for x in range(0, len(current_pdf.pages)):
                output.add_page(current_pdf.pages[x])

        output.write(response)
        return response


class HeadedNotepaperView(View):

    @staticmethod
    def get_image_path(filename):
        return os.path.join(settings.BASE_DIR, 'advanced_pdf_examples/static/pdf_examples', filename)

    def get(self, request):
        template = get_template(f'file_examples/headed_notepaper/headed_notepaper.xml')
        xml = template.render({'companies': Company.objects.all()})
        report_xml = ReportXML()
        result = report_xml.load_xml_and_make_pdf(
            xml,
            background_image_first=self.get_image_path('headed_paper.jpg'),
            background_image_remaining=self.get_image_path('headed_paper_remaining.jpg'),
        )
        response = HttpResponse(result.getvalue(), content_type='application/pdf')
        return response


class ProcessTaskPDF(MainMenu, TaskDownloadMixin, TemplateView):
    template_name = 'advanced_pdf_examples/view_task_pdf.html'

    def get_process_pdf_url(self, slug):
        return reverse('advanced_pdf_examples:process_task_pdf', kwargs={'slug': slug})
