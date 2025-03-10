"""
Data prepared for rendering charts with plotly.js

const EXAMPLE_DATA = {
    y: [18, 45, 98, 120, 109, 113, 43],
    x: ['8PM', '9PM', '10PM', '11PM', '12PM', '13PM', '14PM'],
    tickvals: ['8PM', '', '', '', '', '', '14PM'],
}

const EXAMPLE_PLOTS = [
{ title: '19 Jun', data: EXAMPLE_DATA, type: 'bar' },
{ title: '20 Jun', data: EXAMPLE_DATA, type: 'scatter' },
{
    title: '21 Jun',
    data: EXAMPLE_DATA,
    type: 'scatter',
    showRangeSlider: true,
}
"""

import datetime
import itertools

from django.apps import apps
from django.db import models

from ami.utils.dates import shift_to_nighttime


def captures_per_hour(project_pk: int):
    # Average captures per hour across all days
    SourceImage = apps.get_model("main", "SourceImage")

    # First get captures per hour per day
    captures_by_day_hour = (
        SourceImage.objects.filter(project=project_pk)
        .exclude(timestamp=None)
        .values("timestamp__date", "timestamp__hour")
        .annotate(count=models.Count("pk"))
        .order_by("timestamp__date", "timestamp__hour")
    )

    # Calculate average per hour
    hour_totals = {}
    hour_counts = {}

    for entry in captures_by_day_hour:
        hour = entry["timestamp__hour"]
        count = entry["count"]

        if hour not in hour_totals:
            hour_totals[hour] = 0
            hour_counts[hour] = 0

        hour_totals[hour] += count
        hour_counts[hour] += 1

    # Calculate averages
    avg_captures_per_hour = [
        {"hour": hour, "avg_captures": round(hour_totals[hour] / hour_counts[hour], 0)} for hour in hour_totals.keys()
    ]
    avg_captures_per_hour.sort(key=lambda x: x["hour"])

    if avg_captures_per_hour:
        hours = [entry["hour"] for entry in avg_captures_per_hour]
        avgs = [entry["avg_captures"] for entry in avg_captures_per_hour]

        hours, avgs = shift_to_nighttime(hours, avgs)
        hours = [datetime.datetime.strptime(str(h), "%H").strftime("%-I:00 %p") for h in hours]
        ticktext = [f"{hours[0]}", f"{hours[-1]}"]
    else:
        hours, avgs = [], []
        ticktext = []

    return {
        "title": "Average captures per hour",
        "data": {"x": hours, "y": avgs, "ticktext": ticktext},
        "type": "bar",
    }


def captures_per_day(project_pk: int):
    # Capture counts per day
    SourceImage = apps.get_model("main", "SourceImage")
    captures_per_date = list(
        SourceImage.objects.filter(project=project_pk)
        .values_list("timestamp__date")
        .annotate(num_captures=models.Count("pk"))
        .order_by("timestamp__date")
        .distinct()
    )

    if captures_per_date:
        days, counts = list(zip(*captures_per_date))
        days = [day for day in days if day]
        # tickvals_per_month = [f"{d:%b}" for d in days]
        tickvals = [f"{days[0]:%b %d}", f"{days[-1]:%b %d}"]
        labels = [f"{d:%b %d}" for d in days]
    else:
        labels, counts = [], []
        tickvals = []

    return {
        "title": "Captures per day",
        "data": {"x": labels, "y": counts, "tickvals": tickvals},
        "type": "bar",
    }


def captures_per_month(project_pk: int):
    # Capture counts per month
    SourceImage = apps.get_model("main", "SourceImage")
    captures_per_month = list(
        SourceImage.objects.filter(project=project_pk)
        .values_list("timestamp__month")
        .annotate(num_captures=models.Count("pk"))
        .order_by("timestamp__month")
        .exclude(timestamp=None)
    )

    if captures_per_month:
        months, counts = list(zip(*captures_per_month))
        # tickvals_per_month = [f"{d:%b}" for d in days]
        tickvals = [f"{months[0]}", f"{months[-1]}"]
        # labels = [f"{d}" for d in months]
        labels = [datetime.date(3000, month, 1).strftime("%b") for month in months]
    else:
        labels, counts = [], []
        tickvals = []

    return {
        "title": "Captures per month",
        "data": {"x": labels, "y": counts, "tickvals": tickvals},
        "type": "bar",
    }


def events_per_week(project_pk: int):
    # Events per week
    Event = apps.get_model("main", "Event")
    captures_per_week = list(
        Event.objects.filter(project=project_pk)
        .values_list("start__week")
        .annotate(num_captures=models.Count("id"))
        .order_by("start__week")
    )

    if captures_per_week:
        weeks, counts = list(zip(*captures_per_week))
        # tickvals_per_month = [f"{d:%b}" for d in days]
        tickvals = [f"{weeks[0]}", f"{weeks[-1]}"]
        labels = [f"{d}" for d in weeks]
    else:
        labels, counts = [], []
        tickvals = []

    return {
        "title": "Sessions per week",
        "data": {"x": labels, "y": counts, "tickvals": tickvals},
        "type": "bar",
    }


def events_per_month(project_pk: int):
    # Events per month
    Event = apps.get_model("main", "Event")
    captures_per_month = list(
        Event.objects.filter(project=project_pk)
        .values_list("start__month")
        .annotate(num_captures=models.Count("id"))
        .order_by("start__month")
    )

    if captures_per_month:
        months, counts = list(zip(*captures_per_month))
        # tickvals_per_month = [f"{d:%b}" for d in days]
        tickvals = [f"{months[0]}", f"{months[-1]}"]
        # labels = [f"{d}" for d in months]
        labels = [datetime.date(3000, month, 1).strftime("%b") for month in months]
    else:
        labels, counts = [], []
        tickvals = []

    return {
        "title": "Sessions per month",
        "data": {"x": labels, "y": counts, "tickvals": tickvals},
        "type": "bar",
    }


def detections_per_hour(project_pk: int):
    # Average detections per hour across all days
    Detection = apps.get_model("main", "Detection")

    # First get detections per hour per day
    detections_by_day_hour = (
        Detection.objects.filter(occurrence__project=project_pk)
        .exclude(source_image__timestamp=None)
        .values("source_image__timestamp__date", "source_image__timestamp__hour")
        .annotate(count=models.Count("id"))
        .order_by("source_image__timestamp__date", "source_image__timestamp__hour")
    )

    # Calculate average per hour
    hour_totals = {}
    hour_counts = {}

    for entry in detections_by_day_hour:
        hour = entry["source_image__timestamp__hour"]
        count = entry["count"]

        if hour not in hour_totals:
            hour_totals[hour] = 0
            hour_counts[hour] = 0

        hour_totals[hour] += count
        hour_counts[hour] += 1

    # Calculate averages
    avg_detections_per_hour = [
        {"hour": hour, "avg_detections": round(hour_totals[hour] / hour_counts[hour], 0)}
        for hour in hour_totals.keys()
    ]
    avg_detections_per_hour.sort(key=lambda x: x["hour"])

    if avg_detections_per_hour:
        hours = [entry["hour"] for entry in avg_detections_per_hour]
        avgs = [entry["avg_detections"] for entry in avg_detections_per_hour]

        hours, avgs = shift_to_nighttime(hours, avgs)
        hours = [datetime.datetime.strptime(str(h), "%H").strftime("%-I:00 %p") for h in hours]
        ticktext = [f"{hours[0]}", f"{hours[-1]}"]
    else:
        hours, avgs = [], []
        ticktext = []

    return {
        "title": "Average detections per hour",
        "data": {"x": hours, "y": avgs, "ticktext": ticktext},
        "type": "bar",
    }


def occurrences_accumulated(project_pk: int):
    # Line chart of the accumulated number of occurrences over time throughout the season

    Occurrence = apps.get_model("main", "Occurrence")
    occurrences_per_day = (
        Occurrence.objects.filter(project=project_pk)
        .values_list("event__start")
        .exclude(event=None)
        .exclude(event__start=None)
        .exclude(detections=None)
        .annotate(num_occurrences=models.Count("id"))
        .order_by("event__start")
    )

    occurrences_exist = Occurrence.objects.filter(project=project_pk).exists()
    if occurrences_exist:
        days, counts = list(zip(*occurrences_per_day))
        # Accumulate the counts
        counts = list(itertools.accumulate(counts))
        # tickvals = [f"{d:%b %d}" for d in days]
        tickvals = [f"{days[0]:%b %d, %Y}", f"{days[-1]:%b %d, %Y}"]
        days = [f"{d:%b %d, %Y}" for d in days]
    else:
        days, counts = [], []
        tickvals = []

    return {
        "title": "Accumulation of occurrences",
        "data": {"x": days, "y": counts, "tickvals": tickvals},
        "type": "line",
    }


def event_detections_per_hour(event_pk: int):
    # Detections per hour
    Detection = apps.get_model("main", "Detection")
    detections_per_hour = (
        Detection.objects.filter(source_image__event=event_pk)
        .values("source_image__timestamp__hour")
        .annotate(num_detections=models.Count("id"))
        .order_by("source_image__timestamp__hour")
        .exclude(source_image__timestamp=None)
    )

    # hours, counts = list(zip(*detections_per_hour))
    if detections_per_hour:
        hours, counts = list(
            zip(*[(d["source_image__timestamp__hour"], d["num_detections"]) for d in detections_per_hour])
        )
        hours, counts = shift_to_nighttime(list(hours), list(counts))
        # @TODO show a tick for every hour even if there are no detections
        hours = [datetime.datetime.strptime(str(h), "%H").strftime("%-I:00 %p") for h in hours]
        ticktext = [f"{hours[0]}:00", f"{hours[-1]}:00"]
    else:
        hours, counts = [], []
        ticktext = []

    return {
        "title": "Detections per hour",
        "data": {"x": hours, "y": counts, "ticktext": ticktext},
        "type": "bar",
    }


def event_top_taxa(event_pk: int, top_n: int = 10):
    # Horizontal bar chart of top taxa
    Taxon = apps.get_model("main", "Taxon")
    top_taxa = (
        Taxon.objects.filter(occurrences__event=event_pk)
        .values("name")
        # .annotate(num_detections=models.Count("occurrences__detections"))
        .annotate(num_detections=models.Count("occurrences"))
        .order_by("-num_detections")[:top_n]
    )

    if top_taxa:
        taxa, counts = list(zip(*[(t["name"], t["num_detections"]) for t in reversed(top_taxa)]))
        taxa = [t or "Unknown" for t in taxa]
        counts = [c or 0 for c in counts]
    else:
        taxa, counts = [], []

    return {
        "title": "Top species",
        "data": {"x": counts, "y": taxa},
        "type": "bar",
        "orientation": "h",
    }


def project_top_taxa(project_pk: int, top_n: int = 10):
    Taxon = apps.get_model("main", "Taxon")
    top_taxa = (
        Taxon.objects.all()
        .with_occurrence_counts(project=project_pk)  # type: ignore
        .order_by("-occurrence_count")[:top_n]
    )

    if top_taxa:
        taxa, counts = list(zip(*[(t.name, t.occurrence_count) for t in reversed(top_taxa)]))
    else:
        taxa, counts = [], []

    return {
        "title": "Top species observed",
        "data": {"x": counts, "y": taxa},
        "type": "bar",
        "orientation": "h",
    }


def unique_species_per_month(project_pk: int):
    # Unique species per month
    Occurrence = apps.get_model("main", "Occurrence")
    unique_species_per_month = (
        Occurrence.objects.filter(project=project_pk)
        .values_list("event__start__month")
        .annotate(num_species=models.Count("determination_id", distinct=True))
        .order_by("event__start__month")
    )

    # Create a dictionary mapping month numbers to species counts
    month_to_count = {month: count for month, count in unique_species_per_month}

    # Create lists for all 12 months, using 0 for months with no data
    all_months = list(range(1, 13))  # 1-12 for January-December
    counts = [month_to_count.get(month, 0) for month in all_months]

    # Generate labels for all months
    labels = [datetime.date(3000, month, 1).strftime("%b") for month in all_months]

    # Show all months as tick values
    tickvals = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

    return {
        "title": "Unique species per month",
        "data": {"x": labels, "y": counts, "tickvals": tickvals},
        "type": "bar",
    }


def average_occurrences_per_month(project_pk: int):
    # Average occurrences per month
    Occurrence = apps.get_model("main", "Occurrence")
    occurrences_per_month = (
        Occurrence.objects.filter(project=project_pk)
        .values_list("event__start__month")
        .annotate(num_occurrences=models.Count("id"))
        .order_by("event__start__month")
    )

    # Create a dictionary mapping month numbers to occurrence counts
    month_to_count = {month: count for month, count in occurrences_per_month}

    # Create lists for all 12 months, using 0 for months with no data
    all_months = list(range(1, 13))  # 1-12 for January-December
    counts = [month_to_count.get(month, 0) for month in all_months]

    # Generate labels for all months
    labels = [datetime.date(3000, month, 1).strftime("%b") for month in all_months]

    # Show all months as tick vals
    tickvals = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

    return {
        "title": "Average occurrences per month",
        "data": {"x": labels, "y": counts, "tickvals": tickvals},
        "type": "bar",
    }
