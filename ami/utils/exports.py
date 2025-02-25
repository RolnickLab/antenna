import json
import logging
import os
import tempfile
from collections.abc import Iterable

import pandas as pd
from dwcawriter import Archive, Table

from ami.main.models import Occurrence

logger = logging.getLogger(__name__)


def create_dwc_archive(occurrences: Iterable[Occurrence]):
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


def export_occurrences_to_json(occurrences, file_path="exported_occurrences.json"):
    occurrences_data = {
        "0": {
            "id": 33,
            "event": {"id": 6, "name": "Wednesday, Aug 10 2022", "date_label": "Aug 10 2022"},
            "deployment": {"id": 3, "name": "Test Deployment 7afa1fcf"},
            "first_appearance_timestamp": "2022-08-10T22:02:00",
            "first_appearance_time": "22:02:00",
            "duration": "5700.0",
            "duration_label": "1 hours 35 min",
            "determination": {
                "id": 3,
                "name": "Vanessa",
                "parent": {"id": 2, "name": "Nymphalidae", "rank": "FAMILY"},
                "rank": "GENUS",
            },
            "detections_count": 3,
            "detection_images": [
                "/media/detections/5/2022-08-10/session_2022-08-10_capture_20220810220200_detection_97.jpg",
                "/media/detections/5/2022-08-10/session_2022-08-10_capture_20220810224600_detection_98.jpg",
                "/media/detections/5/2022-08-10/session_2022-08-10_capture_20220810233700_detection_99.jpg",
            ],
            "determination_score": 1,
            "determination_details": {
                "taxon": {
                    "id": 3,
                    "name": "Vanessa",
                    "rank": "GENUS",
                    "parent": {"id": 2, "name": "Nymphalidae", "rank": "FAMILY"},
                    "parents": [
                        {"id": 1, "name": "Lepidoptera", "rank": "ORDER"},
                        {"id": 2, "name": "Nymphalidae", "rank": "FAMILY"},
                    ],
                },
                "identification": {
                    "id": 5,
                    "taxon": {
                        "id": 3,
                        "name": "Vanessa",
                        "rank": "GENUS",
                        "parent": {"id": 2, "name": "Nymphalidae", "rank": "FAMILY"},
                        "parents": [
                            {"id": 1, "name": "Lepidoptera", "rank": "ORDER"},
                            {"id": 2, "name": "Nymphalidae", "rank": "FAMILY"},
                        ],
                    },
                    "withdrawn": False,
                    "comment": "",
                    "created_at": "2025-02-23T00:47:30.004440",
                },
                "prediction": None,
                "score": 1,
            },
            "identifications": [
                {
                    "id": 5,
                    "taxon": {
                        "id": 3,
                        "name": "Vanessa",
                        "rank": "GENUS",
                        "parent": {"id": 2, "name": "Nymphalidae", "rank": "FAMILY"},
                        "parents": [
                            {"id": 1, "name": "Lepidoptera", "rank": "ORDER"},
                            {"id": 2, "name": "Nymphalidae", "rank": "FAMILY"},
                        ],
                    },
                    "withdrawn": False,
                    "comment": "",
                    "created_at": "2025-02-23T00:47:30.004440",
                }
            ],
            "created_at": "2025-02-23T00:41:31.394085",
            "updated_at": "2025-02-23T00:47:30.011478",
        }
    }

    # Write to JSON file
    with open(file_path, "w", encoding="utf-8") as json_file:
        json.dump(occurrences_data, json_file, indent=4)
    return file_path
