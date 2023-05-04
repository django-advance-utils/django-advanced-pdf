from django.core.cache import caches
from django.core.files.base import ContentFile
from django.http import FileResponse, Http404
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.views import View
from django.views.decorators.clickjacking import xframe_options_exempt
from django_modals.modals import Modal


class ViewTaskPDF(View):
    cache_key = 'default'

    @xframe_options_exempt
    def get(self, request, file_key):
        cache_data = caches[self.cache_key].get(file_key)
        if cache_data is not None:
            response = FileResponse(ContentFile(cache_data['file']), content_type="application/pdf")
            filename = cache_data['filename']
            response['Content-Disposition'] = f'filename={filename}'
            response['Content-Length'] = len(cache_data['file'])
            caches[self.cache_key].delete(file_key)
            return response
        else:
            raise Http404


class PrintReportModal(Modal):
    button_container_class = 'text-center'
    size = 'xl'

    def get_url(self):
        file_key = self.slug.get('file_key')
        return reverse('django_advanced_pdf:view_task_pdf', kwargs={'file_key': file_key})

    def modal_content(self):
        url = self.get_url()
        html = mark_safe(f"""<iframe src="{url}" style="height:80vh; width:100%"></iframe>""")
        return html
