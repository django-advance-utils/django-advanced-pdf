from io import StringIO, BytesIO

from lxml import etree

from django_advanced_pdf.engine.report_xml import ReportXML


def make_pdf(xml, **kwargs):
    parser = etree.XMLParser(remove_blank_text=True, resolve_entities=False)
    tree = etree.parse(StringIO(xml), parser)
    root = tree.getroot()
    report_xml = ReportXML(pager_kwargs=kwargs)
    result = BytesIO()
    report_xml.make_pdf(root, result)
    result.seek(0)
    return result
