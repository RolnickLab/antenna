import hashlib
import logging
from datetime import datetime

from PIL import Image
from PIL.ExifTags import TAGS

from ami.utils.dates import get_image_timestamp_from_filename

logger = logging.getLogger(__name__)


def extract_timestamp_from_exif(image: Image.Image) -> datetime | None:
    """
    Extract timestamp from EXIF data using existing Pillow image object.

    NOTE: This function explicitly strips timezone information and returns
    naive datetime objects representing the local time when the photo was taken.
    We only care about the local timestamp, not the timezone.

    Args:
        image: PIL Image object

    Returns:
        datetime: Naive datetime parsed from EXIF DateTimeOriginal (timezone stripped),
                 or None if not found
    """
    try:
        image.seek(0)  # Ensure we read from the start of the image file
        exif_data = image.getexif()

        if not exif_data:
            logger.info("No EXIF data found in image")
            return None

        # Convert tag IDs to readable names
        exif_dict = {}
        for tag_id, value in exif_data.items():
            tag_name = TAGS.get(tag_id, tag_id)
            exif_dict[tag_name] = value

        # Try multiple timestamp fields in order of preference
        timestamp_fields = [
            "DateTimeOriginal",  # When photo was taken (preferred)
            "DateTime",  # When file was last modified
        ]

        for field in timestamp_fields:
            if field in exif_dict:
                timestamp_str = exif_dict[field]
                logger.debug(f"Found EXIF timestamp in {field}: {timestamp_str}")

                try:
                    # Parse EXIF datetime format: "YYYY:MM:DD HH:MM:SS"
                    # Note: EXIF timestamps are typically timezone-naive anyway,
                    # but we explicitly ensure we return a naive datetime
                    parsed_timestamp = datetime.strptime(timestamp_str, "%Y:%m:%d %H:%M:%S")

                    # Explicitly strip timezone if somehow present (should be rare)
                    naive_timestamp = parsed_timestamp.replace(tzinfo=None)

                    logger.info(f"Successfully parsed EXIF timestamp (timezone stripped): {naive_timestamp}")
                    return naive_timestamp

                except ValueError as e:
                    logger.warning(f"Failed to parse timestamp '{timestamp_str}' from {field}: {e}")
                    continue

        logger.info("No valid EXIF timestamp found in image")
        return None

    except Exception as e:
        logger.error(f"Error extracting EXIF timestamp: {e}")
        return None


def extract_timestamp(filename: str, image: Image.Image | None = None) -> datetime | None:
    """
    Extract timestamp from filename or EXIF data of an image.

    Args:
        filename: Name of the file to extract timestamp from
        image: Optional PIL Image object to extract EXIF timestamp from

    Returns:
        datetime: Naive datetime object representing the timestamp, or None if not found
    """
    # First try to get timestamp from filename
    timestamp = get_image_timestamp_from_filename(filename)
    if timestamp:
        logger.info(f"Extracted timestamp from filename: {timestamp}")
        return timestamp

    # If no valid timestamp from filename, try EXIF data if image is provided
    if image:
        exif_timestamp = extract_timestamp_from_exif(image)
        if exif_timestamp:
            logger.info(f"Extracted timestamp from EXIF data: {exif_timestamp}")
            return exif_timestamp

    logger.warning("No valid timestamp found in filename or EXIF data")
    return None


def calculate_file_checksum(file_content: bytes, algorithm: str = "md5") -> tuple[str, str]:
    """
    Calculate checksum for file content.

    Args:
        file_content: Raw file bytes
        algorithm: Hash algorithm to use ("md5", "sha256", etc.)

    Returns:
        tuple: (checksum_hex_string, algorithm_name)
    """
    if algorithm.lower() == "md5":
        checksum = hashlib.md5(file_content).hexdigest()
    elif algorithm.lower() == "sha256":
        checksum = hashlib.sha256(file_content).hexdigest()
    else:
        raise ValueError(f"Unsupported hash algorithm: {algorithm}")

    logger.debug(f"Calculated {algorithm} checksum: {checksum}")
    return checksum, algorithm.lower()
