import datetime

from rest_framework import serializers


class DateStringField(serializers.CharField):
    """
    Field that validates and stores dates as YYYY-MM-DD strings.
    Needed for storing dates as strings in JSON fields but keep validation.
    """

    def to_internal_value(self, value: str | None) -> str | None:
        if value is None:
            return None

        try:
            # Validate the date format by parsing it
            datetime.datetime.strptime(value, "%Y-%m-%d")
            return value
        except ValueError as e:
            raise serializers.ValidationError("Invalid date format. Use YYYY-MM-DD format.") from e

    @classmethod
    def to_date(cls, value: str | None) -> datetime.date | None:
        """Convert a YYYY-MM-DD string to a Python date object for ORM queries."""
        if value is None:
            return None
        return datetime.datetime.strptime(value, "%Y-%m-%d").date()
