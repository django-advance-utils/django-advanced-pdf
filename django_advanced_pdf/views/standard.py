from django.http import HttpResponse
from django.views.generic import DetailView

from django_advanced_pdf.models import PrintingTemplate


class DatabasePDFView(DetailView):
    model = PrintingTemplate

    def get_pager_kwargs(self):
        return {}

    def render_to_response(self, context, **kwargs):
        result = self.object.make_pdf(context=context, **self.get_pager_kwargs())
        response = HttpResponse(result.getvalue(), content_type='application/pdf')
        return response

