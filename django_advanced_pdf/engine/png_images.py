import base64
import pickle

from reportlab.lib.units import mm
from reportlab.platypus import Image
from io import BytesIO  # for Python 3


def insert_image(tag):
    image_data = BytesIO(base64.b64decode(tag.text))
    image = Image(image_data)
    if tag.get('width') is not None:
        image.drawWidth = float(tag.get('width')) * mm
    if tag.get('height') is not None:
        image.drawHeight = float(tag.get('height')) * mm
    return image


def insert_obj(tag):
    data = tag.text
    if data is not None:
        enc_data = data.encode('ascii')
        object_data = base64.urlsafe_b64decode(enc_data)
        report_object = pickle.loads(object_data)
        return report_object
    return None
