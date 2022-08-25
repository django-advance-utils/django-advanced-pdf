import csv
import datetime
import random

from date_offset.date_offset import DateOffset
from advanced_pdf_examples import models


def import_data(path):
    import_companies(path)
    import_tallies(path)


def random_date(start, end):
    """
    This function will return a random datetime between two datetime
    objects.
    """
    delta = end - start
    int_delta = (delta.days * 24 * 60 * 60) + delta.seconds
    random_second = random.randrange(int_delta)
    return start + datetime.timedelta(seconds=random_second)


def import_companies(path):
    # if models.Company.objects.all().count() > 0:
    #     return
    models.Payment.objects.all().delete()
    random.seed(a='import_companies', version=2)

    date_offset = DateOffset()

    start_date = date_offset.get_offset('-1y', include_time=True)
    end_date = date_offset.get_offset('1m', include_time=True)
    print(start_date)
    with open(path + '/data/test_data.csv', 'r') as f:
        titles = {c[1]: c[0] for c in models.Person.title_choices}
        csv_reader = csv.DictReader(f)
        for r in csv_reader:

            companies = models.Company.objects.filter(name=r['Company'])
            if len(companies) > 1:
                for c in companies[1:]:
                    c.delete()

            company = models.Company.objects.get_or_create(name=r['Company'],
                                                           importance=random.randrange(0, 10))[0]
            models.Person.objects.get_or_create(company=company,
                                                first_name=r['First Name'],
                                                surname=r['Surname'],
                                                title=titles.get(r['Title'], None),
                                                date_entered=datetime.datetime.strptime(r['date_entered'],
                                                                                        '%d/%m/%Y'))
            for _ in range(random.randrange(10)):
                date = random_date(start_date, end_date)
                amount = random.randrange(1000, 10000)
                quantity = random.randrange(1, 15)
                models.Payment(company=company,
                               date=date,
                               amount=amount,
                               quantity=quantity).save()

            for tag in r['tags'].split(','):
                if tag != '':
                    tag = models.Tags.objects.get_or_create(tag=tag)[0]
                    tag.company.add(company)


def import_tallies(path):
    with open(path + '/data/test_tallies_data.csv', 'r') as f:
        csv_reader = csv.DictReader(f)
        for r in csv_reader:
            models.Tally.objects.get_or_create(date=datetime.datetime.strptime(r['Date'], '%d/%m/%Y'),
                                               cars=int(r['Cars']),
                                               vans=int(r['Vans']),
                                               buses=int(r['Buses']),
                                               lorries=int(r['Lorries']),
                                               motor_bikes=int(r['Motor Bikes']),
                                               push_bikes=int(r['Push Bikes']),
                                               tractors=int(r['Tractors']))
