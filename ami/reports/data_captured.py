import pandas as pd
from django.db import models

from ami.main.models import SourceImage


def average_captures_per_month(as_dataframe=True):
    # Calculate average number of captures per month from all sources.
    # Exlude months with no captures.
    # Group by month and year
    captures = (
        SourceImage.objects.values("deployment__name", "timestamp__month", "timestamp__year")
        .annotate(num_captures=models.Count("pk"))
        .filter(num_captures__gt=0)
        # .aggregate(models.Avg("num_captures"))
    )

    if as_dataframe:
        df = pd.DataFrame(captures)
        return df
    else:
        return captures
