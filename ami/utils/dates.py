import datetime
import pathlib
import re

import dateutil.parser


def get_image_timestamp_from_filename(img_path) -> datetime.datetime:
    """
    Parse the date and time a photo was taken from its filename.

    The timestamp must be in the format `YYYYMMDDHHMMSS` but can be
    preceded or followed by other characters (e.g. `84-20220916202959-snapshot.jpg`).

    >>> out_fmt = "%Y-%m-%d %H:%M:%S"
    >>> # Aarhus date format
    >>> get_image_timestamp_from_filename("20220810231507-00-07.jpg").strftime(out_fmt)
    '2022-08-10 23:15:07'
    >>> # Diopsis date format
    >>> get_image_timestamp_from_filename("20230124191342.jpg").strftime(out_fmt)
    '2023-01-24 19:13:42'
    >>> # Snapshot date format in Vermont traps
    >>> get_image_timestamp_from_filename("20220622000459-108-snapshot.jpg").strftime(out_fmt)
    '2022-06-22 00:04:59'
    >>> # Snapshot date format in Cyprus traps
    >>> get_image_timestamp_from_filename("84-20220916202959-snapshot.jpg").strftime(out_fmt)
    '2022-09-16 20:29:59'

    """
    name = pathlib.Path(img_path).stem
    date = None

    # Extract date from a filename using regex in the format %Y%m%d%H%M%S
    matches = re.search(r"(\d{14})", name)
    if matches:
        date = datetime.datetime.strptime(matches.group(), "%Y%m%d%H%M%S")
    else:
        date = dateutil.parser.parse(name, fuzzy=False)  # Fuzzy will interpret "DSC_1974" as 1974-01-01

    if date:
        return date
    else:
        raise ValueError(f"Could not parse date from filename '{img_path}'")
