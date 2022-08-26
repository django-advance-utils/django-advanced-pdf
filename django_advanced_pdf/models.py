from io import StringIO, BytesIO

from django.db import models
from django.template import Template, Context
from lxml import etree

from django_advanced_pdf.engine.report_xml import ReportXML


class PrintingTemplate(models.Model):
    name = models.CharField(max_length=128, unique=True)
    xml = models.TextField()

    def __str__(self):
        return self.name

    def make_pdf(self, context=None, **kwargs):
        if context is None:
            xml = self.xml
        else:
            t = Template(self.xml)
            c = Context(context)
            xml = t.render(c)

        parser = etree.XMLParser(remove_blank_text=True, resolve_entities=False)
        tree = etree.parse(StringIO(xml), parser)
        root = tree.getroot()
        report_xml = ReportXML(pager_kwargs=kwargs)
        result = BytesIO()
        report_xml.make_pdf(root, result)
        result.seek(0)
        return result
