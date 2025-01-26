import base64
import binascii
import io
import logging
import pathlib
import re
import tempfile
import urllib.request
from urllib.parse import urlparse

import PIL.Image

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


def get_or_download_file(path_or_url, tempdir_prefix="antenna") -> pathlib.Path:
    """
    Fetch a file from a URL or local path. If the path is a URL, download the file.
    If the URL has already been downloaded, return the existing local path.
    If the path is a local path, return the path.

    >>> filepath = get_or_download_file("https://example.uk/images/31-20230919033000-snapshot.jpg?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=451d406b7eb1113e1bb05c083ce51481%2F20240429%2F") # noqa: E501
    >>> filepath.name
    '31-20230919033000-snapshot.jpg'
    >>> filepath = get_or_download_file("/home/user/images/31-20230919033000-snapshot.jpg")
    >>> filepath.name
    '31-20230919033000-snapshot.jpg'
    """
    if not path_or_url:
        raise Exception("Specify a URL or path to fetch file from.")

    # If path is a local path instead of a URL then urlretrieve will just return that path

    destination_dir = pathlib.Path(tempfile.mkdtemp(prefix=tempdir_prefix))
    fname = pathlib.Path(urlparse(path_or_url).path).name
    if not destination_dir.exists():
        destination_dir.mkdir(parents=True, exist_ok=True)
    local_filepath = pathlib.Path(destination_dir) / fname

    if local_filepath and local_filepath.exists():
        logger.info(f"Using existing {local_filepath}")
        return local_filepath

    else:
        logger.info(f"Downloading {path_or_url} to {local_filepath}")
        try:
            resulting_filepath, _headers = urllib.request.urlretrieve(url=path_or_url, filename=local_filepath)
        except Exception as e:
            raise Exception(f"Could not retrieve {path_or_url}: {e}")

        resulting_filepath = pathlib.Path(resulting_filepath)
        logger.info(f"Downloaded to {resulting_filepath}")
        return resulting_filepath


def open_image(fp: str | bytes | pathlib.Path, raise_exception: bool = True) -> PIL.Image.Image | None:
    """
    Wrapper from PIL.Image.open that handles errors and converts to RGB.
    """
    img = None
    try:
        img = PIL.Image.open(fp)
    except PIL.UnidentifiedImageError:
        logger.warn(f"Unidentified image: {str(fp)[:100]}...")
        if raise_exception:
            raise
    except OSError:
        logger.warn(f"Could not open image: {str(fp)[:100]}...")
        if raise_exception:
            raise
    else:
        # Convert to RGB if necessary
        if img.mode != "RGB":
            img = img.convert("RGB")

    return img


def decode_base64_string(string) -> io.BytesIO:
    image_data = re.sub("^data:image/.+;base64,", "", string)
    decoded = base64.b64decode(image_data)
    buffer = io.BytesIO(decoded)
    buffer.seek(0)
    return buffer


def get_image(
    url: str | None = None,
    filepath: str | pathlib.Path | None = None,
    b64: str | None = None,
    raise_exception: bool = True,
) -> PIL.Image.Image | None:
    """
    Given a URL, local file path or base64 image, return a PIL image.
    """

    if url:
        logger.info(f"Fetching image from URL: {url}")
        tempdir = tempfile.TemporaryDirectory(prefix="ami_images")
        img_path = get_or_download_file(url, tempdir_prefix=tempdir.name)
        return open_image(img_path, raise_exception=raise_exception)

    elif filepath:
        logger.info(f"Loading image from local filesystem: {filepath}")
        return open_image(filepath, raise_exception=raise_exception)

    elif b64:
        logger.info(f"Loading image from base64 string: {b64[:30]}...")
        try:
            buffer = decode_base64_string(b64)
        except binascii.Error as e:
            logger.warn(f"Could not decode base64 image: {e}")
            if raise_exception:
                raise
            else:
                return None
        else:
            return open_image(buffer, raise_exception=raise_exception)

    else:
        raise Exception("Specify a URL, path or base64 image.")
