"""Public surface of the DwC-A export package.

Re-exports keep existing imports (format_types.py, tests) working unchanged
while internal code is organized by responsibility.
"""

from ami.exports.dwca.eml import generate_eml_xml
from ami.exports.dwca.fields import DC, DWC, ECO, EVENT_FIELDS, MULTIMEDIA_FIELDS, OCCURRENCE_FIELDS, DwCAField
from ami.exports.dwca.helpers import (
    _format_coord,
    _format_datetime,
    _format_duration,
    _format_event_date,
    _format_time,
    _get_rank_from_parents,
    _get_verification_status,
    get_specific_epithet,
)
from ami.exports.dwca.meta import generate_meta_xml
from ami.exports.dwca.tsv import write_tsv
from ami.exports.dwca.zip import create_dwca_zip

__all__ = [
    "DC",
    "DWC",
    "ECO",
    "DwCAField",
    "EVENT_FIELDS",
    "MULTIMEDIA_FIELDS",
    "OCCURRENCE_FIELDS",
    "create_dwca_zip",
    "generate_eml_xml",
    "generate_meta_xml",
    "get_specific_epithet",
    "write_tsv",
    "_format_coord",
    "_format_datetime",
    "_format_duration",
    "_format_event_date",
    "_format_time",
    "_get_rank_from_parents",
    "_get_verification_status",
]
