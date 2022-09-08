from django.db import models
from django.template import Template, Context

from django_advanced_pdf.utils import make_pdf


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
        return make_pdf(xml=xml, **kwargs)
