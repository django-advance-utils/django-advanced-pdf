import os

from advanced_pdf_examples.models import Company
from celery import shared_task
from django.conf import settings
from django.template.loader import get_template

from django_advanced_pdf.engine.report_xml import ReportXML
from django_advanced_pdf.tasks import TaskProcessPDFHelper


class TaskProcessPDFExample(TaskProcessPDFHelper):

    def get_image_path(self, filename):
        return os.path.join(settings.BASE_DIR, 'advanced_pdf_examples/static/pdf_examples', filename)

    def get_xml_and_filename(self, slug):
        template = get_template(f'file_examples/headed_notepaper/headed_notepaper.xml')
        xml = template.render({'companies': Company.objects.all()})
        return xml, 'companies.pdf'

    def build_pdf(self, slug):
        xml, filename = self.get_xml_and_filename(slug)
        report_xml = ReportXML(status_method=self.update_progress)
        result = report_xml.load_xml_and_make_pdf(
            xml,
            background_image_first=self.get_image_path('headed_paper.jpg'),
            background_image_remaining=self.get_image_path('headed_paper_remaining.jpg'),)
        return result, filename


@shared_task(bind=True, base=TaskProcessPDFExample)
def process_pdf(self, config=False, slug=None, **kwargs):
    return self.process(config=config, slug=slug, **kwargs)
