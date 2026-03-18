[![PyPI version](https://badge.fury.io/py/django-advanced-pdf.svg)](https://badge.fury.io/py/django-advanced-pdf)


# django-advanced-pdf

`django-advanced-pdf` is a Django app for building PDFs from XML templates (with Django template syntax), powered by ReportLab.

This repository contains:

- the reusable package: `django_advanced_pdf/`
- a runnable Django demo project: `django_examples/`

---

## What this project does

You can generate PDFs by:

1. **Rendering XML stored in the database** (`PrintingTemplate`)
2. **Rendering XML files from templates**
3. **Rendering in background tasks** (Celery helper included)

The XML supports rich layout features such as:

- tables, row/column spans, nested tables
- custom style blocks and inline style attributes
- page borders and page-level pager/header/footer blocks
- conditional/hidden rows/columns
- overflow handling for long cells
- embedded PNG/SVG and object injection

---

## Quick start (Docker, easiest)

From repository root:

```bash
docker compose up --build
```

Then open:

- `http://localhost:8012/` (example app)

The compose stack includes:

- Django app
- Postgres (`db_pdf`)
- Redis (`redis`)
- Celery worker

---

## Local setup (without Docker)

### 1) Install dependencies

```bash
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 2) Configure database/cache for the demo app

The example project settings are in:

- `django_examples/django_examples/settings.py`

By default, the demo uses Postgres + Redis hostnames intended for Docker:

- DB host: `db_pdf`
- Redis host: `redis` on port `6380`

If running fully local, update these to your local services.

### 3) Run migrations and start server

```bash
cd django_examples
python manage.py migrate
python manage.py runserver 0.0.0.0:8012
```

### 4) (Optional) load sample data

```bash
python manage.py import_advanced_pdf
```

---

## Integrate into your own Django project

### 1) Install package

```bash
pip install django-advanced-pdf
```

### 2) Add app

```python
INSTALLED_APPS = [
    # ...
    "django_advanced_pdf",
]
```

### 3) Include URLs (for task PDF download/modal helpers)

```python
from django.urls import include, path

urlpatterns = [
    # ...
    path("pdf/", include("django_advanced_pdf.urls", namespace="django_advanced_pdf")),
]
```

---

## Common usage patterns

### A) Render from a database template (`PrintingTemplate`)

```python
from django_advanced_pdf.models import PrintingTemplate

template = PrintingTemplate.objects.get(name="invoice")
result = template.make_pdf(context={"invoice": invoice})

pdf_bytes = result["pdf_data"].getvalue()
has_xml_warnings = result["has_potential_xml_errors"]
```

### B) Render XML directly with `ReportXML`

```python
from django_advanced_pdf.engine.report_xml import ReportXML

xml = """
<document title="Example" page_size="A4">
  <table>
    <tr><td>Hello world</td></tr>
  </table>
</document>
"""

report = ReportXML()
buffer = report.load_xml_and_make_pdf(xml)
pdf_bytes = buffer.getvalue()
```

### C) Class-based view for database templates

Inherit from `django_advanced_pdf.views.standard.DatabasePDFView` and set the model instance.

---

## XML template quick reference

### Root element

```xml
<document
    title="My report"
    page_size="A4"
    page_orientation="portrait"
    page_style="borders"
    border_top_first="10"
    border_bottom_first="10"
    border_left_first="10"
    border_right_first="10">
    ...
</document>
```

### Frequently used tags

- `<style>...</style>`: define reusable classes
- `<table>`, `<tr>`, `<td>`: table layout
- `<header>`, `<footer>` inside table
- `<keep>` wrapper for “keep-with-next” row groups
- `<p>`: paragraph block
- `<spacer style="height:10">`
- `<page_break/>`
- `<obj ...>`: inject Python objects from `object_lookup`
- `<pagers><pager ...>...</pager></pagers>`: page-level fixed blocks

### Styling

Styles are CSS-like but mapped to ReportLab table/paragraph options.
Examples seen in this repository:

- `inner_grid:0.25,#000000`
- `box:0.5,#000000`
- `text_color:#0000FF`
- `background:#F0F0F0`
- `line_below:0.5,#000000`
- `left_padding:1`

Reference examples:

- `django_examples/advanced_pdf_examples/templates/file_examples/basic.xml`
- `.../border.xml`
- `.../pager.xml`
- `.../hidden.xml`

---

## Background task flow (Celery)

The helper base class is:

- `django_advanced_pdf.tasks.TaskProcessPDFHelper`

Typical flow:

1. build PDF in task (`build_pdf`)
2. save bytes + filename to Django cache
3. redirect user to `django_advanced_pdf:view_task_pdf` for download
4. or open modal via `django_advanced_pdf:view_task_pdf_modal`

Example task implementation:

- `django_examples/advanced_pdf_examples/tasks.py`

---

## Demo routes worth checking

From the demo project root URL:

- `/` database templates demo
- `/files/` file-based XML demos
- `/view/companies/` context-driven companies PDF
- `/report/example/` merged report sample
- `/report/headed-notepaper/` background image example
- `/tasks/<slug>/` task/modal examples

---

## Running tests

Package tests live in:

- `django_advanced_pdf/tests.py`

Run:

```bash
python -m unittest django_advanced_pdf.tests
```

---

## Troubleshooting

- **Blank/failed output**: check malformed XML and inspect `has_potential_xml_errors`.
- **Task PDF not downloadable**: verify cache backend + Redis connectivity.
- **Demo app DB errors**: ensure Postgres connection values match your environment.
- **Missing static/demo assets**: run from repo layout expected by `django_examples`.

---

## License

MIT (see `LICENSE`).
