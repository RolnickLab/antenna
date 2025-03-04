import json
import logging
import os
import tempfile
from collections.abc import Iterable

import pandas as pd
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models
from django.db.models import QuerySet
from dwcawriter import Archive, Table
from rest_framework import serializers

from ami.exports.serializers import OccurrenceExportSerializer
from ami.main.models import Occurrence

logger = logging.getLogger(__name__)


def export_occurrences_to_dwc(occurrences: Iterable[Occurrence]):
    """
    Creates a Darwin Core Archive (DwC-A) for the given occurrences.

    Args:
        occurrences: Queryset of Occurrence objects.

    Returns:
        Path to the generated Darwin Core Archive file.
    """
    # ===========================
    # OCCURRENCE CORE TABLE
    # ===========================
    df_occurrence = pd.DataFrame(
        [
            {
                "occurrenceID": occurrence.id,
                "scientificName": occurrence.determination.name if occurrence.determination else None,
                "eventDate": occurrence.first_appearance_timestamp,
                "eventTime": occurrence.first_appearance_time,
                "decimalLatitude": occurrence.deployment.latitude if occurrence.deployment else None,
                "decimalLongitude": occurrence.deployment.longitude if occurrence.deployment else None,
                "basisOfRecord": "HumanObservation",
                "individualCount": occurrence.detections_count,
                "associatedMedia": (
                    "; ".join(list(occurrence.detection_images())) if occurrence.detection_images else None
                ),
                "identificationVerificationStatus": occurrence.determination_score,
                "dateIdentified": occurrence.created_at,
                "modified": occurrence.updated_at,
                "occurrenceRemarks": "Occurrence Remarks ",
            }
            for occurrence in occurrences
        ]
    )

    # ===========================
    #  MEASUREMENT OR FACT TABLE
    # ===========================
    # df_measurement = pd.DataFrame(
    #     [
    #         {
    #             "occurrenceID": occurrence.id,
    #             "measurementType": "Detection Count",
    #             "measurementValue": occurrence.detections_count,
    #         }
    #         for occurrence in occurrences
    #     ]
    # )

    # ===========================
    # EVENT TABLE (Sampling Details)
    # ===========================
    df_event = pd.DataFrame(
        [
            {
                "eventID": occurrence.event.id if occurrence.event else None,
                "samplingProtocol": "Automated Camera Trap",
                "eventDate": occurrence.event.date_label if occurrence.event else None,
                "samplingEffort": occurrence.duration if occurrence.duration else None,
            }
            for occurrence in occurrences
        ]
    )

    # ===========================
    #  TAXON TABLE (Taxonomic Hierarchy)
    # ===========================
    df_taxon = pd.DataFrame(
        [
            {
                "taxonID": occurrence.determination.id if occurrence.determination else None,
                "scientificName": occurrence.determination.name if occurrence.determination else None,
                "taxonRank": occurrence.determination.rank if occurrence.determination else None,
                "family": (
                    occurrence.determination.parent.name
                    if occurrence.determination and occurrence.determination.parent
                    else None
                ),
                "genus": occurrence.determination.name if occurrence.determination.rank == "GENUS" else None,
            }
            for occurrence in occurrences
        ]
    )
    df_identification = pd.DataFrame(
        [
            {
                "identificationID": identification.id,
                "occurrenceID": occurrence.id,
                "verbatimIdentification": identification.taxon.name if identification.taxon else None,
                "identifiedBy": identification.user.name if identification.user else None,
                "identifiedByID": identification.user.id if identification.user else None,
                "dateIdentified": identification.created_at,
                "identificationReferences": "identificationReferences",
                "identificationVerificationStatus": "verified" if not identification.withdrawn else "withdrawn",
                "identificationRemarks": identification.comment,
            }
            for occurrence in occurrences
            for identification in occurrence.identifications.all()
        ]
    )

    # ===========================
    # CREATE THE DWCA ARCHIVE
    # ===========================
    archive = Archive()
    archive.eml_text = "Meta Data for Exported Occurrences"

    # OCCURRENCE CORE
    core_table = Table(
        spec="https://rs.gbif.org/core/dwc_occurrence_2022-02-02.xml",
        data=df_occurrence,
        id_index=0,
        only_mapped_columns=False,
    )
    archive.core = core_table

    # EXTENSION TABLES (Optional but useful)
    extension_tables = [
        (df_event, "measurements_or_facts_2022-02-02.xml"),
        (df_identification, "identification.xml"),
        (df_taxon, "identification.xml"),
    ]

    for df, name in extension_tables:
        if not df.empty:
            table = Table(
                spec=f"https://rs.gbif.org/extension/dwc/{name}",
                data=df,
                id_index=0,
                only_mapped_columns=False,
            )
            archive.extensions.append(table)

    # ===========================
    #  SAVE TO TEMP FILE
    # ===========================
    temp_dir = tempfile.mkdtemp()
    archive_path = os.path.join(temp_dir, "dwca.zip")
    archive.export(archive_path)

    logger.info(f"create_dwc_archive: {archive_path}")
    return archive_path


def export_occurrences_to_json(occurrences: QuerySet, job, batch_size=1000):
    """
    Export occurrences to a JSON file
    """

    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".json", mode="w", encoding="utf-8")

    with open(temp_file.name, "w", encoding="utf-8") as f:
        total = occurrences.count()
        first = True
        i = 0

        for i, batch in enumerate(
            get_data_in_batches(QuerySet=occurrences, Serializer=OccurrenceExportSerializer, batch_size=batch_size)
        ):
            json_data = json.dumps(batch, cls=DjangoJSONEncoder)

            # Write JSON object with correct formatting
            f.write(",\n" if not first else "")  # Add comma except for the first item
            f.write(json_data)
            first = False  # Update flag after first iteration
            i += batch_size
            job.progress.update_stage("occurrence_export", progress=round(i / total, 2))
            job.save()

    return temp_file.name  # Return file path


def export_occurrences_to_csv(occurrences, job):
    """
    Export occurrences to a CSV file.
    """
    pass


def get_data_in_batches(QuerySet: models.QuerySet, Serializer: type[serializers.Serializer], batch_size=1000):
    """
    Yield batches of serialized data from a queryset efficiently.
    """
    items = QuerySet.iterator(chunk_size=batch_size)  # Efficient iteration to avoid memory issues
    batch = []

    for i, item in enumerate(items):
        try:
            # Serialize the occurrence object
            serializer = Serializer(item)
            item_data = serializer.data
            batch.append(item_data)

            # Yield batch once it reaches batch_size
            if len(batch) >= batch_size:
                yield batch
                batch = []  # Reset batch
        except Exception as e:
            logger.warning(f"Error processing occurrence {item.id}: {str(e)}")
            raise e

    # Yield the remaining batch
    if batch:
        yield batch
