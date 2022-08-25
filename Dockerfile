FROM python:3.8

ENV PYTHONUNBUFFERED 1

RUN mkdir /app
WORKDIR /app
COPY requirements.txt /app/
RUN pip install --upgrade pip
RUN pip install -r /app/requirements.txt
#copy dist/*.* /app/







