from django.urls import path

from advanced_pdf_examples.views import ExampleIndex, PrintingTemplateModal, ViewPDF

app_name = 'advanced_pdf_examples'


urlpatterns = [
    path('', ExampleIndex.as_view(), name='index'),
    path('<str:slug>/modal/', PrintingTemplateModal.as_view(), name='printing_template_modal'),
    path('view/<int:pk>/', ViewPDF.as_view(), name='view_pdf'),


]
