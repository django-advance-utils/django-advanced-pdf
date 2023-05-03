import uuid

from ajax_helpers.utils import ajax_command
from ajax_helpers.websockets.tasks import TaskHelper
from django.core.cache import caches
from django.urls import reverse

from django_advanced_pdf.engine.report_xml import ReportXML


class TaskProcessPDFHelper(TaskHelper):

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

    def process(self, config=False, slug=None, **kwargs):
        message = 'initial'
        if config:
            return {'progress': False, 'message': message, 'title': 'Processing....'}

        result, filename = self.build_pdf(slug)
        hash_key = str(uuid.uuid4().hex)
        caches['default'].set(hash_key, {'file': result.getvalue(), 'filename': filename})
        url = reverse(slug['view_name'], kwargs={'slug': f'file_key-{hash_key}'})
        return {'commands': [ajax_command('close'),
                             ajax_command('redirect', url=url)]}
