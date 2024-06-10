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
    >>> # Snapshot date format from Wingscape camera from Newfoundland
    >>> get_image_timestamp_from_filename("Project_20230801023001_4393.JPG").strftime(out_fmt)
    '2023-08-01 02:30:01'

    """
    name = pathlib.Path(img_path).stem
    date = None

    # Extract date from a filename using regex in the format %Y%m%d%H%M%S
    matches = re.search(r"(\d{14})", name)
    if matches:
        try:
            date = datetime.datetime.strptime(matches.group(), "%Y%m%d%H%M%S")
        except ValueError:
            pass

    if not date:
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
    ...     datetime.datetime(2021, 1, 1, 0, 10, 0), # @TODO confirm the first gap is having an effect
    ...     datetime.datetime(2021, 1, 1, 0, 19, 0),
    ...     datetime.datetime(2021, 1, 1, 1, 20, 0),
    ...     datetime.datetime(2021, 1, 1, 1, 30, 0),
    ...     datetime.datetime(2021, 1, 2, 0, 10, 0),
    ...     datetime.datetime(2021, 1, 2, 1, 29, 0),
    ...     datetime.datetime(2021, 1, 2, 1, 30, 0),
    ...     datetime.datetime(2021, 1, 2, 1, 31, 0),
    ...     datetime.datetime(2021, 1, 2, 1, 32, 0),
    ...     datetime.datetime(2021, 1, 2, 1, 40, 0),]
    >>> result = group_datetimes_by_gap(timestamps, max_time_gap=datetime.timedelta(minutes=120))
    >>> len(result)
    2
    >>> result = group_datetimes_by_gap(timestamps, max_time_gap=datetime.timedelta(minutes=60))
    >>> len(result)
    4
    >>> result = group_datetimes_by_gap(timestamps, max_time_gap=datetime.timedelta(minutes=11))
    >>> len(result)
    4
    >>> result = group_datetimes_by_gap(timestamps, max_time_gap=datetime.timedelta(minutes=10))
    >>> len(result)
    5
    >>> result = group_datetimes_by_gap(timestamps, max_time_gap=datetime.timedelta(minutes=9))
    >>> len(result)
    6
    >>> result = group_datetimes_by_gap(timestamps, max_time_gap=datetime.timedelta(minutes=1))
    >>> len(result)
    10
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


def group_datetimes_by_shifted_day(timestamps: list[datetime.datetime]) -> list[list[datetime.datetime]]:
    """
    @TODO: Needs testing

    Images are captured from Evening to Morning the next day.
    Assume that the first image is taken after noon and the last image is taken before noon.
    In that case, we can shift the timestamps so that the x-axis is centered around 12PM.
    then group the images by day.

    One way to do this directly in postgres is to use the following query:
    SELECT date_trunc('day', timestamp + interval '12 hours') as day, count(*)
    FROM images
    GROUP BY day

    >>> timestamps = [
    ...     datetime.datetime(2021, 1, 1, 0, 0, 0),
    ...     datetime.datetime(2021, 1, 1, 0, 1, 0),
    ...     datetime.datetime(2021, 1, 1, 0, 2, 0),
    ...     datetime.datetime(2021, 1, 2, 0, 0, 0),
    ...     datetime.datetime(2021, 1, 2, 0, 1, 0),
    ...     datetime.datetime(2021, 1, 2, 0, 2, 0),]
    >>> result = group_datetimes_by_shifted_day(timestamps)
    >>> len(result)
    2
    """

    # Shift hours so that the x-axis is centered around 12PM.
    time_delta = datetime.timedelta(hours=12)
    timestamps = [timestamp - time_delta for timestamp in sorted(timestamps)]

    # Group the timestamps by their day value:
    groups = {}
    for timestamp in timestamps:
        day = timestamp.date()
        if day not in groups:
            groups[day] = []
        groups[day].append(timestamp)

    # Convert the dictionary to a list of lists
    return list(groups.values())


def shift_to_nighttime(hours: list[int], values: list) -> tuple[list[int], list]:
    """Another strategy to shift hours so that the x-axis is centered around 12PM."""

    split_index = 0
    for i, hour in enumerate(hours):
        if hour > 12:
            split_index = i
            break

    hours = hours[split_index:] + hours[:split_index]
    values = values[split_index:] + values[:split_index]

    return hours, values
