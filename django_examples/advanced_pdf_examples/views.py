import base64
import os
import pathlib

from PyPDF2 import PdfFileReader, PdfFileWriter
from advanced_pdf_examples.models import Company
from ajax_helpers.mixins import AjaxHelpers
from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.template.loader import get_template
from django.views import View
from django_datatables.columns import MenuColumn
from django_datatables.datatables import DatatableView
from django_datatables.helpers import DUMMY_ID
from django_menus.menu import MenuMixin, MenuItem, HtmlMenu, AjaxButtonMenuItem
from django_modals.modals import ModelFormModal
from django_modals.processes import PERMISSION_OFF

from django_advanced_pdf.engine.report_xml import ReportXML
from django_advanced_pdf.models import PrintingTemplate
from django_advanced_pdf.views import DatabasePDFView


class MainMenu(AjaxHelpers, MenuMixin):
    def setup_menu(self):
        # noinspection PyUnresolvedReferences
        self.add_menu('main_menu').add_items(
            ('advanced_pdf_examples:from_database_example', 'From Database Example'),
            ('advanced_pdf_examples:from_file_example', 'From File Example'),
            ('advanced_pdf_examples:view_companies_pdf', 'View Companies PDF'),
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
        report_xml = ReportXML()
        result = report_xml.load_xml_and_make_pdf(xml)
        response = HttpResponse(result.getvalue(), content_type='application/pdf')
        return response


class CompaniesPDFView(View):
    def get(self, request):
        template = get_template(f'file_examples/with_context/companies.xml')
        xml = template.render({'companies': Company.objects.all()})
        xml = template.render({})
        report_xml = ReportXML()
        result = report_xml.load_xml_and_make_pdf(xml) # background_image_remaining=os.path.join(settings.BASE_DIR, 'test.jpg')
        response = HttpResponse(result.getvalue(), content_type='application/pdf')
        return response


class ReportExampleView(View):
    def get(self, request):
        output = PdfFileWriter()
        template_files = ['basic', 'border']
        response = HttpResponse(content_type='application/pdf')
        for template_file in template_files:
            template = get_template(f'file_examples/{template_file}.xml')
            xml = template.render({})
            report_xml = ReportXML()
            result = report_xml.load_xml_and_make_pdf(xml)
            current_pdf = PdfFileReader(result)
            for x in range(0, current_pdf.getNumPages()):
                output.addPage(current_pdf.getPage(x))

        output.write(response)
        return response

