# Demo video

This directory contains an automated demo recording of the example app:

- `django-advanced-pdf-demo.mp4`
- `django-advanced-pdf-demo-preview.jpg` (6-frame storyboard preview)

To regenerate the video from the repository root:

```bash
pip3 install -r requirements.txt
pip3 install playwright
python3 -m playwright install chromium
python3 scripts/create_demo_video.py
```
