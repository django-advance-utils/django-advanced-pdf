from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models

from time_stamped_model.models import TimeStampedModel


class UserProfile(AbstractUser):
    pass


class Sector(TimeStampedModel):
    name = models.CharField(max_length=80)
    type = models.PositiveSmallIntegerField(default=1)

    def __str__(self):
        return self.name


class CompanyCategory(TimeStampedModel):
    name = models.CharField(max_length=80)

    def __str__(self):
        return self.name


class Company(TimeStampedModel):
    name = models.CharField(max_length=80)
    active = models.BooleanField(default=False)
    number = models.CharField(max_length=128, blank=True)
    importance = models.IntegerField(null=True)
    sectors = models.ManyToManyField(Sector, blank=True, related_name='companysectors')
    background_colour = models.CharField(max_length=8, default='90EE90')
    text_colour = models.CharField(max_length=8, default='454B1B')
    user_profile = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, blank=True, null=True)
    company_category = models.ForeignKey(CompanyCategory, on_delete=models.CASCADE, blank=True, null=True)

    class Meta:
        verbose_name_plural = 'Companies'

    def __str__(self):
        return self.name


class CompanyInformation(models.Model):
    company = models.OneToOneField(Company, primary_key=True,
                                   related_name='companyinformation', on_delete=models.CASCADE)
    value = models.IntegerField()
    incorporated_date = models.DateField()


class Person(models.Model):

    title_choices = ((0, 'Mr'), (1, 'Mrs'), (2, 'Miss'))
    title = models.IntegerField(choices=title_choices, null=True)
    company = models.ForeignKey(Company,  on_delete=models.CASCADE, null=True, blank=True)
    first_name = models.CharField(max_length=80)
    surname = models.CharField(max_length=80)
    date_entered = models.DateField(auto_now_add=True)


class Tags(models.Model):
    tag = models.CharField(max_length=40)
    company = models.ManyToManyField(Company, blank=True)

    class Meta:
        verbose_name_plural = 'Tags'


class Note(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    date = models.DateField()
    notes = models.TextField()


class Tally(models.Model):
    date = models.DateField()
    cars = models.IntegerField()
    vans = models.IntegerField()
    buses = models.IntegerField()
    lorries = models.IntegerField()
    motor_bikes = models.IntegerField()
    push_bikes = models.IntegerField()
    tractors = models.IntegerField()
    user_profile = models.ForeignKey(UserProfile, on_delete=models.CASCADE, null=True, blank=True)

    class Meta:
        verbose_name_plural = 'Tallies'


class Payment(TimeStampedModel):
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    date = models.DateField()
    amount = models.IntegerField()
    quantity = models.IntegerField()
    received = models.BooleanField(default=False)
    user_profile = models.ForeignKey(UserProfile, on_delete=models.CASCADE, null=True, blank=True)
