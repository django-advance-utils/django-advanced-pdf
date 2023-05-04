from django.urls import path

from django_advanced_pdf.views.tasks import ViewTaskPDF, PrintReportModal

app_name = 'django_advanced_pdf'

urlpatterns = [
    path('download/<str:file_key>/', ViewTaskPDF.as_view(), name='view_task_pdf'),
    path('download/<str:slug>/modal/', PrintReportModal.as_view(), name='view_task_pdf_modal'),
]
