import csv
import typing

from django.core.files.base import File


def iterate_rows(file_object: typing.TextIO | File) -> typing.Generator[dict[str, str], None, None]:
    """Iterate over the rows of a CSV file.

    Args:
        file_object (file): A file object.

    Yields:
        list: A list of dictionaries.
    """

    reader = csv.DictReader(file_object)
    yield from reader
