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
    # Captures per hour
    SourceImage = apps.get_model("main", "SourceImage")
    captures_per_hour = list(
        SourceImage.objects.filter(project=project_pk)
        .values("timestamp__hour")
        .annotate(num_captures=models.Count("pk"))
        .order_by("timestamp__hour")
        .exclude(timestamp=None)
    )

    if captures_per_hour:
        hours, counts = list(zip(*captures_per_hour))
        hours, counts = list(zip(*[(d["timestamp__hour"], d["num_captures"]) for d in captures_per_hour]))
        # hours = map(int, hours)
        hours, counts = shift_to_nighttime(list(hours), list(counts))
        # @TODO show a tick for every hour even if there are no captures
        hours = [datetime.datetime.strptime(str(h), "%H").strftime("%-I:00 %p") for h in hours]
        ticktext = [f"{hours[0]}:00", f"{hours[-1]}:00"]

    else:
        hours, counts = [], []
        ticktext = []

    return {
        "title": "Captures per hour",
        "data": {"x": hours, "y": counts, "ticktext": ticktext},
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
    # Detections per hour
    Detection = apps.get_model("main", "Detection")
    detections_per_hour = list(
        Detection.objects.filter(occurrence__project=project_pk)
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


def occurrences_accumulated(project_pk: int):
    # Line chart of the accumulated number of occurrnces over time throughout the season

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

    if occurrences_per_day.count():
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
    # Horiziontal bar chart of top taxa
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

    # Restrict number of top species if too many
    MAX_SPECIES = 10
    if len(taxa) > MAX_SPECIES:
        taxa = taxa[:MAX_SPECIES]
        counts = counts[:MAX_SPECIES]

    return {
        "title": "Top species",
        "data": {"x": counts, "y": taxa},
        "type": "bar",
        "orientation": "h",
    }
