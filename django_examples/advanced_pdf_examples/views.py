import base64

from ajax_helpers.mixins import AjaxHelpers
from django.shortcuts import get_object_or_404
from django_datatables.columns import MenuColumn
from django_datatables.datatables import DatatableView
from django_datatables.helpers import DUMMY_ID
from django_menus.menu import MenuMixin, MenuItem, HtmlMenu, AjaxButtonMenuItem
from django_modals.modals import ModelFormModal

from django_advanced_pdf.models import PrintingTemplate
from django_advanced_pdf.views import DatabasePDFView


class MainMenu(AjaxHelpers, MenuMixin):
    def setup_menu(self):
        # noinspection PyUnresolvedReferences
        self.add_menu('main_menu').add_items(
            ('advanced_pdf_examples:index', 'Home'),
            MenuItem(url='admin:index',
                     menu_display='Admin',
                     visible=self.request.user.is_superuser),

        )


class ExampleIndex(MainMenu, DatatableView):
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

    def button_download_pdf(self, *args, **kwargs):
        printing_template = get_object_or_404(PrintingTemplate, pk=kwargs['pk'])
        result = printing_template.make_pdf()
        return self.command_response('save_file', data=base64.b64encode(result.read()).decode('ascii'),
                                     filename=f'{printing_template.name}.pdf', type='application/pdf')


class PrintingTemplateModal(ModelFormModal):
    size = 'xl'
    model = PrintingTemplate
    form_fields = ['name', 'xml']


class ExampleDatabasePDFView(DatabasePDFView):
    def get_pager_kwargs(self):
        return {'program_name': 'Django Advanced PDF Viewer'}


