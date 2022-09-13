from io import StringIO, BytesIO

from lxml import etree

from django_advanced_pdf.engine.report_xml import ReportXML


def make_pdf(xml, **kwargs):

    report_xml = ReportXML(pager_kwargs=kwargs)


