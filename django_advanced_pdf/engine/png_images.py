import base64
import pickle

from reportlab.lib.units import mm
from reportlab.platypus import Image
from io import BytesIO  # for Python 3

from django_advanced_pdf.engine.utils import get_boolean_value


def insert_image(tag):
    image_data = BytesIO(base64.b64decode(tag.text))
    image = Image(image_data)

    orig_width, orig_height = image.imageWidth, image.imageHeight
    aspect = orig_width / float(orig_height)

    width_attr = tag.get('width')
    height_attr = tag.get('height')
    fit_within_box = get_boolean_value(tag.get('fit_within_box'))

    if fit_within_box and (width_attr or height_attr):
        # Fit inside bounding box while keeping aspect ratio
        max_width = float(width_attr) * mm if width_attr else None
        max_height = float(height_attr) * mm if height_attr else None

        # Start with original size
        draw_width = orig_width
        draw_height = orig_height

        # Scale down to fit width
        if max_width and draw_width > max_width:
            draw_height = draw_height * (max_width / draw_width)
            draw_width = max_width

        # Scale down to fit height
        if max_height and draw_height > max_height:
            draw_width = draw_width * (max_height / draw_height)
            draw_height = max_height

        image.drawWidth = draw_width
        image.drawHeight = draw_height

    else:
        # Simple dimension setting (with or without aspect ratio)
        if width_attr and height_attr:
            image.drawWidth = float(width_attr) * mm
            image.drawHeight = float(height_attr) * mm
        elif width_attr:
            image.drawWidth = float(width_attr) * mm
            image.drawHeight = (float(width_attr) / aspect) * mm
        elif height_attr:
            image.drawHeight = float(height_attr) * mm
            image.drawWidth = (float(height_attr) * aspect) * mm
        # else: keep original

    return image


def insert_obj(tag):
    data = tag.text
    if data is not None:
        enc_data = data.encode('ascii')
        object_data = base64.urlsafe_b64decode(enc_data)
        report_object = pickle.loads(object_data)
        return report_object
    return None
