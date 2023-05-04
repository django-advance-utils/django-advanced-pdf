import uuid

from ajax_helpers.utils import ajax_command
from ajax_helpers.websockets.tasks import TaskHelper
from django.core.cache import caches
from django.urls import reverse

from django_advanced_pdf.engine.report_xml import ReportXML


class TaskProcessPDFHelper(TaskHelper):
    cache_key = 'default'

    def update_progress(self, message):
        self.update_state(state='PROGRESS', meta={'message': message})

    def get_xml_and_filename(self, slug):
        xml = '''
                    <document title="My test printout" page_size="A4">
                    <table><tr><td>Hello world</td></tr></table>
                    </document>
                '''
        return xml, 'hello world.pdf'

    def build_pdf(self, slug):
        xml, filename = self.get_xml_and_filename(slug)
        report_xml = ReportXML(status_method=self.update_progress)
        result = report_xml.load_xml_and_make_pdf(xml)
        return result, filename

    def get_config(self):
        return {'progress': False, 'message': 'initial', 'title': 'Processing....'}

    def pre_process(self, slug, **kwargs):
        pass  # can load user / set tenant here etc

    def process(self, config=False, slug=None, **kwargs):
        if config:
            return self.get_config()

        self.pre_process(slug=slug, **kwargs)
        result, filename = self.build_pdf(slug)
        hash_key = str(uuid.uuid4().hex)
        caches[self.cache_key].set(hash_key, {'file': result.getvalue(), 'filename': filename})
        return self.post_process(file_key=hash_key, slug=slug, **kwargs)

    def post_process(self, file_key, slug, **kwargs):
        # noinspection PyNoneFunctionAssignment
        urlconf = self.get_urlconf()
        if slug is not None and slug.get('modal') == '1':
            url = reverse('django_advanced_pdf:view_task_pdf_modal',
                          kwargs={'slug': f'file_key-{file_key}'},
                          urlconf=urlconf)
            return {'commands': [ajax_command('close'),
                                 ajax_command('show_modal', modal=url)]}
        else:
            url = reverse('django_advanced_pdf:view_task_pdf',
                          kwargs={'file_key': file_key},
                          urlconf=urlconf)
            return {'commands': [ajax_command('close'),
                                 ajax_command('redirect', url=url)]}

    def get_urlconf(self):
        return None
