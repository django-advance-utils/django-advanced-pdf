from django.core.cache import caches
from django.core.files.base import ContentFile
from django.http import FileResponse, Http404
from django.views.generic.base import ContextMixin


class TaskDownloadMixin(ContextMixin):

    def get_process_pdf_url(self, slug):
        return None

    def dispatch(self, *args, **kwargs):
        self.split_slug(kwargs)
        if 'file_key' in self.slug:
            return self.download_pdf(file_key=self.slug['file_key'])
        result = super().dispatch(*args, **kwargs)
        return result

    def get_context_data(self, **kwargs):
        view_name = self.request.resolver_match.view_name
        self.slug['view_name'] = view_name
        slug = self.make_slug()
        self.add_page_command('show_modal', modal=self.get_process_pdf_url(slug))
        return super().get_context_data(**kwargs)

    def download_pdf(self, file_key):
        cache_data = caches['default'].get(file_key)
        if cache_data is not None:
            response = FileResponse(ContentFile(cache_data['file']), content_type="application/pdf")
            filename = cache_data['filename']
            response['Content-Disposition'] = f'filename={filename}'
            response['Content-Length'] = len(cache_data['file'])
            caches['default'].delete(file_key)
            return response
        else:
            raise Http404

    def make_slug(self):
        parts = []
        for k, v in self.slug.items():
            if k == 'pk' and v == '-':
                continue
            parts.append(f'{k}-{v}')
        return '-'.join(parts)

    def split_slug(self, kwargs):
        if 'slug' in kwargs:
            if not hasattr(self, 'slug'):
                self.slug = {}
            if kwargs['slug'] == '-':
                self.slug['pk'] = '-'
            else:
                s = kwargs['slug'].split('-')
                if len(s) == 1:
                    self.slug['pk'] = s[0]
                else:
                    self.slug.update({s[k]: s[k + 1] for k in range(0, int(len(s) - 1), 2)})
                if 'pk' in self.slug:
                    self.kwargs['pk'] = self.slug['pk']
