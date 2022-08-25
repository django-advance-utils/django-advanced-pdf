from django.contrib import admin
from advanced_pdf_examples.models import Company, Person, Tags, Sector, Tally, Payment,\
    CompanyInformation, CompanyCategory
from django.contrib.auth.admin import UserAdmin

from advanced_pdf_examples.models import UserProfile


@admin.register(Sector)
class SectorAdmin(admin.ModelAdmin):
    list_display = ('name',
                    'type',
                    )


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ('name',
                    'active',
                    'importance',
                    'modified',
                    'user_profile')
    search_fields = ('name',
                     )


@admin.register(CompanyInformation)
class CompanyInformation(admin.ModelAdmin):
    list_display = ('value',
                    'incorporated_date')


@admin.register(Person)
class PersonAdmin(admin.ModelAdmin):
    list_display = ('title',
                    'first_name',
                    'surname',
                    'company',
                    'date_entered'
                    )


@admin.register(Tags)
class TagsAdmin(admin.ModelAdmin):
    list_display = ('tag',
                    )


@admin.register(Tally)
class TallyAdmin(admin.ModelAdmin):
    list_display = ('date',
                    'cars',
                    'vans',
                    'buses',
                    'lorries',
                    'motor_bikes',
                    'push_bikes',
                    'tractors')


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('date',
                    'company',
                    'amount',
                    'quantity',
                    'received',
                    'user_profile')


admin.site.register(UserProfile, UserAdmin)


@admin.register(CompanyCategory)
class CompanyCategoryAdmin(admin.ModelAdmin):
    list_display = ('name',
                    )
