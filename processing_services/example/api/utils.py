import base64
import binascii
import io
import logging
import pathlib
import re
import tempfile
from urllib.parse import urlparse

import PIL.Image
import PIL.ImageFile
import requests
import torch

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


PIL.ImageFile.LOAD_TRUNCATED_IMAGES = True

# This is polite and required by some hosts
# see: https://foundation.wikimedia.org/wiki/Policy:User-Agent_policy
USER_AGENT = "AntennaInsectDataPlatform/1.0 (https://insectai.org)"

# -----------
# File handling functions
# -----------


def is_url(path: str) -> bool:
    return path.startswith("http://") or path.startswith("https://")


def is_base64(s: str) -> bool:
    try:
        # Check if string can be decoded from base64
        return base64.b64encode(base64.b64decode(s)).decode() == s
    except Exception:
        return False


# (connect, read) timeouts in seconds. The read timeout applies between received chunks, not to the whole download,
# so large model weights are fine as long as data keeps arriving.
DOWNLOAD_TIMEOUT = (10, 60)

# Log download progress roughly this often (in bytes) instead of once per chunk.
DOWNLOAD_LOG_INTERVAL_BYTES = 10 * 1024 * 1024


def get_cache_root() -> pathlib.Path:
    """Directory holding downloaded model files and other cached downloads."""
    return pathlib.Path("/app/cache") if pathlib.Path("/app").exists() else pathlib.Path.home() / ".antenna_cache"


def get_or_download_file(path_or_url, tempdir_prefix="antenna") -> pathlib.Path:
    """
    Fetch a file from a URL or local path.

    A local path is returned as-is (and must exist). A URL is downloaded into the cache directory under
    `tempdir_prefix`, or reused if a file with the same name was already downloaded. The download is streamed to a
    temporary file and renamed into place, so an interrupted download never leaves a truncated file in the cache.

    >>> filepath = get_or_download_file("https://example.uk/images/31-20230919033000-snapshot.jpg?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=451d406b7eb1113e1bb05c083ce51481%2F20240429%2F") # noqa: E501
    >>> filepath.name
    '31-20230919033000-snapshot.jpg'
    >>> filepath = get_or_download_file("/home/user/images/31-20230919033000-snapshot.jpg")
    >>> filepath.name
    '31-20230919033000-snapshot.jpg'
    """
    if not path_or_url:
        raise ValueError("Specify a URL or path to fetch file from.")

    path_or_url = str(path_or_url)
    if not is_url(path_or_url):
        local_path = pathlib.Path(path_or_url)
        if not local_path.exists():
            raise FileNotFoundError(f"Local file does not exist: {local_path}")
        logger.info(f"Using local file: {local_path}")
        return local_path

    destination_dir = get_cache_root() / tempdir_prefix
    destination_dir.mkdir(parents=True, exist_ok=True)
    local_filepath = destination_dir / pathlib.Path(urlparse(path_or_url).path).name

    if local_filepath.exists():
        logger.info(f"Using cached file: {local_filepath}")
        return local_filepath

    logger.info(f"Downloading {path_or_url} to {local_filepath}")
    response = requests.get(path_or_url, stream=True, headers={"User-Agent": USER_AGENT}, timeout=DOWNLOAD_TIMEOUT)
    response.raise_for_status()
    total_size = int(response.headers.get("content-length", 0))

    with tempfile.NamedTemporaryFile(dir=destination_dir, prefix=".download-", delete=False) as partial_file:
        partial_path = pathlib.Path(partial_file.name)
        try:
            downloaded = 0
            next_log_at = DOWNLOAD_LOG_INTERVAL_BYTES
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                partial_file.write(chunk)
                downloaded += len(chunk)
                if downloaded >= next_log_at:
                    percent = f" ({downloaded / total_size:.0%})" if total_size else ""
                    logger.info(f"   Downloaded {downloaded // (1024 * 1024)} MB{percent}")
                    next_log_at += DOWNLOAD_LOG_INTERVAL_BYTES
            if total_size and downloaded != total_size:
                raise OSError(f"Incomplete download of {path_or_url}: got {downloaded} of {total_size} bytes")
        except BaseException:
            partial_path.unlink(missing_ok=True)
            raise

    partial_path.replace(local_filepath)
    logger.info(f"Download completed: {local_filepath.resolve()}")
    return local_filepath.resolve()


def get_best_device() -> str:
    """
    Returns the best available device for running the model.
    MPS is not supported by the current algorithms.
    """
    if torch.cuda.is_available():
        return f"cuda:{torch.cuda.current_device()}"
    else:
        return "cpu"


def open_image(fp: str | bytes | pathlib.Path | io.BytesIO, raise_exception: bool = True) -> PIL.Image.Image | None:
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
