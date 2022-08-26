from django.contrib import admin

from django_advanced_pdf.models import PrintingTemplate


@admin.register(PrintingTemplate)
class PrintingTemplateAdmin(admin.ModelAdmin):
    list_display = ('name',
                    )
