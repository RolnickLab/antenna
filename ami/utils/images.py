import io

import PIL.Image
import requests


def get_image_from_url(url):
    """
    Get an image from a URL.

    :param url: URL of the image.
    :return: PIL.Image.Image object.
    """
    response = requests.get(url)
    return PIL.Image.open(io.BytesIO(response.content))
