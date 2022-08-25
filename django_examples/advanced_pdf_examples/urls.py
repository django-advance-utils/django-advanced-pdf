from django.urls import path

from advanced_pdf_examples.views import ExampleIndex

app_name = 'advanced_pdf_examples'


urlpatterns = [
    path('', ExampleIndex.as_view(), name='index'),

]
