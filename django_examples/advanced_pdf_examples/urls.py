from django.urls import path

from advanced_pdf_examples.views import FromDatabaseExampleIndex, FromFileExampleIndex, PrintingTemplateModal,\
    ExampleDatabasePDFView, ExampleFilePDFView, CompaniesPDFView, ReportExampleView

app_name = 'advanced_pdf_examples'


urlpatterns = [
    path('', FromDatabaseExampleIndex.as_view(), name='from_database_example'),
    path('files/', FromFileExampleIndex.as_view(), name='from_file_example'),
    path('<str:slug>/modal/', PrintingTemplateModal.as_view(), name='printing_template_modal'),
    path('view/database/<int:pk>/', ExampleDatabasePDFView.as_view(), name='view_example_database_pdf'),
    path('view/file/<str:filename>/', ExampleFilePDFView.as_view(), name='view_example_file_pdf'),
    path('view/companies/', CompaniesPDFView.as_view(), name='view_companies_pdf'),
    path('report/example/', ReportExampleView.as_view(), name='view_report_pdf'),

]
