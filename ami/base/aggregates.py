"""Database aggregate expressions that Django does not ship."""

from django.db import models


class Percentile(models.Aggregate):
    """Continuous percentile of a numeric column, computed in PostgreSQL.

    ``Percentile("detections_count", 0.5)`` is the median. The fraction is baked into
    the SQL template, so it must be a constant between 0 and 1 chosen by the caller,
    never user input.
    """

    function = "PERCENTILE_CONT"
    name = "Percentile"
    template = "%(function)s(%(fraction)s) WITHIN GROUP (ORDER BY %(expressions)s)"
    output_field = models.FloatField()  # type: ignore[assignment]

    def __init__(self, expression, fraction: float, **extra):
        if not 0 <= fraction <= 1:
            raise ValueError("fraction must be between 0 and 1")
        super().__init__(expression, fraction=repr(float(fraction)), **extra)
