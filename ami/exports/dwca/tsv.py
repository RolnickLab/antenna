"""TSV writing for DwC-A text files."""

from __future__ import annotations

import csv

from ami.exports.dwca.fields import DwCAField


def write_tsv(
    filepath: str,
    fields: list[DwCAField],
    queryset,
    project_slug: str,
    progress_callback=None,
):
    """Write a tab-delimited file from a queryset using field definitions.

    Returns the number of records written.
    """
    headers = [f.header for f in fields]
    records_written = 0

    with open(filepath, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter="\t", quoting=csv.QUOTE_MINIMAL, lineterminator="\n")
        writer.writerow(headers)

        for obj in queryset.iterator(chunk_size=500):
            row = [field.extract(obj, project_slug) for field in fields]
            writer.writerow(row)
            records_written += 1
            if progress_callback and records_written % 500 == 0:
                progress_callback(records_written)

    return records_written
