[![PyPI version](https://badge.fury.io/py/django-advanced-pdf.svg)](https://badge.fury.io/py/django-advanced-pdf)


# django-advanced-pdf
django-advanced-pdf

## Demo video

An automated demo recording script is included at:

`scripts/create_demo_video.py`

It starts the Django example project with demo-friendly settings
(`django_examples.settings_demo`), walks through a few routes, and saves a
video to `demo/django-advanced-pdf-demo.mp4`.

### Generate locally

```bash
pip3 install -r requirements.txt
pip3 install playwright
python3 -m playwright install chromium
python3 scripts/create_demo_video.py
```
