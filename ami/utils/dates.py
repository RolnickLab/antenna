import datetime
import logging
import pathlib
import re

import dateutil.parser

logger = logging.getLogger(__name__)


def get_image_timestamp_from_filename(img_path, raise_error=False) -> datetime.datetime | None:
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
        try:
            date = dateutil.parser.parse(name, fuzzy=False)  # Fuzzy will interpret "DSC_1974" as 1974-01-01
        except dateutil.parser.ParserError:
            pass

    if not date and raise_error:
        raise ValueError(f"Could not parse date from filename '{img_path}'")
    else:
        return date


def format_timedelta(duration: datetime.timedelta | None) -> str:
    """Format the duration for display.
    @TODO try the humanize library
    # return humanize.naturaldelta(self.duration())

    Examples:
    5 minutes
    2 hours 30 min
    2 days 5 hours
    """
    if not duration:
        return ""
    if duration < datetime.timedelta(hours=1):
        return f"{duration.seconds // 60} minutes"
    if duration < datetime.timedelta(days=1):
        return f"{duration.seconds // 3600} hours {duration.seconds % 3600 // 60} min"
    else:
        return f"{duration.days} days {duration.seconds // 3600} hours"


def group_datetimes_by_gap(
    timestamps: list[datetime.datetime],
    max_time_gap=datetime.timedelta(minutes=120),
) -> list[list[datetime.datetime]]:
    """
    Divide a list of timestamps into groups based on a maximum time gap.

    >>> timestamps = [
    ...     datetime.datetime(2021, 1, 1, 0, 0, 0),
    ...     datetime.datetime(2021, 1, 1, 0, 1, 0),
    ...     datetime.datetime(2021, 1, 1, 0, 2, 0),
    ...     datetime.datetime(2021, 1, 2, 0, 0, 0),
    ...     datetime.datetime(2021, 1, 2, 0, 1, 0),
    ...     datetime.datetime(2021, 1, 2, 0, 2, 0),]
    >>> result = group_dates_by_gap(timestamps, max_time_gap=datetime.timedelta(minutes=120))
    >>> len(result)
    2
    >>> result = group_dates_by_gap(timestamps, max_time_gap=datetime.timedelta(minutes=1))
    >>> len(result)
    6
    >>> result = group_dates_by_gap(timestamps, max_time_gap=datetime.timedelta(minutes=60))
    >>> len(result)
    4
    """
    timestamps.sort()
    prev_timestamp: datetime.datetime | None = None
    current_group: list[datetime.datetime] = []
    groups: list[list[datetime.datetime]] = []

    for timestamp in timestamps:
        if prev_timestamp:
            delta = timestamp - prev_timestamp
        else:
            delta = datetime.timedelta(0)

        if delta >= max_time_gap:
            groups.append(current_group)
            current_group = []

        current_group.append(timestamp)
        prev_timestamp = timestamp

    groups.append(current_group)

    return groups


def shift_to_nighttime(hours: list[int], values: list) -> tuple[list[int], list]:
    """Shift hours so that the x-axis is centered around 12PM."""

    split_index = 0
    for i, hour in enumerate(hours):
        if hour > 12:
            split_index = i
            break

    hours = hours[split_index:] + hours[:split_index]
    values = values[split_index:] + values[:split_index]

    return hours, values
