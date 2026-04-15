"""
Offline structural validator for Darwin Core Archives produced by this app.

Checks the invariants that tests and code review can't catch reliably:
zip contents, meta.xml parses and references files that actually exist,
column count matches meta.xml field declarations, core ids are unique,
every extension coreid resolves to a core id, required columns are
populated on every row, and eml.xml parses.

This is not a GBIF-compliance validator — those concerns (vocabularies,
geographic coverage, taxonomic backbone matching) require the official
GBIF validator. This catches the class of bug where meta.xml and the
TSVs drift apart, which is historically where DwC-A producers break.
"""

from __future__ import annotations

import csv
import io
import zipfile
from dataclasses import dataclass, field
from xml.etree import ElementTree as ET

META_NS = "http://rs.tdwg.org/dwc/text/"


@dataclass
class ValidationResult:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def add_error(self, msg: str) -> None:
        self.errors.append(msg)

    def add_warning(self, msg: str) -> None:
        self.warnings.append(msg)


@dataclass
class _TableSpec:
    role: str  # "core" or "extension"
    row_type: str
    filename: str
    id_index: int  # <id> for core, <coreid> for extension
    field_terms: dict[int, str]  # index -> term URI
    required: bool = False


def validate_dwca_zip(zip_path: str, required_terms: set[str] | None = None) -> ValidationResult:
    """Validate a DwC-A zip structurally.

    `required_terms` is an optional set of DwC term URIs that must be
    present AND non-empty on every row of the table that declares them.
    When omitted, the validator only checks structural invariants
    (parseable meta.xml, coreid referential integrity, consistent
    column counts, unique core ids).
    """
    result = ValidationResult()

    if not zipfile.is_zipfile(zip_path):
        result.add_error(f"Not a zip file: {zip_path}")
        return result

    with zipfile.ZipFile(zip_path, "r") as zf:
        names = set(zf.namelist())

        for required in ("meta.xml", "eml.xml"):
            if required not in names:
                result.add_error(f"Archive missing required file: {required}")

        if "meta.xml" not in names:
            return result

        meta_bytes = zf.read("meta.xml")
        try:
            meta_root = ET.fromstring(meta_bytes)
        except ET.ParseError as exc:
            result.add_error(f"meta.xml does not parse: {exc}")
            return result

        tables = _parse_meta(meta_root, result)
        if not tables:
            return result

        core_ids = _validate_core(zf, tables[0], result, required_terms or set())

        for ext in tables[1:]:
            _validate_extension(zf, ext, core_ids, result, required_terms or set())

        if "eml.xml" in names:
            try:
                ET.fromstring(zf.read("eml.xml"))
            except ET.ParseError as exc:
                result.add_error(f"eml.xml does not parse: {exc}")

    return result


def _parse_meta(meta_root: ET.Element, result: ValidationResult) -> list[_TableSpec]:
    tables: list[_TableSpec] = []

    # meta.xml uses the dwc/text namespace; handle both namespaced and
    # unqualified tags so we don't choke on hand-written meta files.
    def strip_ns(tag: str) -> str:
        return tag.split("}", 1)[-1] if "}" in tag else tag

    core_elems = [child for child in meta_root if strip_ns(child.tag) == "core"]
    ext_elems = [child for child in meta_root if strip_ns(child.tag) == "extension"]

    if len(core_elems) != 1:
        result.add_error(f"meta.xml must declare exactly one <core>, found {len(core_elems)}")
        return []

    for elem in [core_elems[0], *ext_elems]:
        role = strip_ns(elem.tag)
        id_tag = "id" if role == "core" else "coreid"
        row_type = elem.get("rowType", "")

        files = [c for c in elem if strip_ns(c.tag) == "files"]
        location = ""
        if files:
            for loc in files[0]:
                if strip_ns(loc.tag) == "location" and loc.text:
                    location = loc.text.strip()
                    break
        if not location:
            result.add_error(f"meta.xml {role} missing <files><location>")
            continue

        id_elems = [c for c in elem if strip_ns(c.tag) == id_tag]
        if len(id_elems) != 1:
            result.add_error(f"meta.xml {role} ({location}) must declare exactly one <{id_tag}>")
            continue
        try:
            id_index = int(id_elems[0].get("index", ""))
        except ValueError:
            result.add_error(f"meta.xml {role} ({location}) <{id_tag}> index is not an integer")
            continue

        field_terms: dict[int, str] = {}
        for fld in elem:
            if strip_ns(fld.tag) != "field":
                continue
            term = fld.get("term", "")
            idx_raw = fld.get("index")
            if idx_raw is None or not term:
                result.add_error(f"meta.xml {role} ({location}) <field> missing index or term")
                continue
            try:
                idx = int(idx_raw)
            except ValueError:
                result.add_error(f"meta.xml {role} ({location}) <field> index is not an integer: {idx_raw}")
                continue
            if idx in field_terms:
                result.add_error(
                    f"meta.xml {role} ({location}) duplicate <field> index {idx}: " f"{field_terms[idx]} and {term}"
                )
            field_terms[idx] = term

        tables.append(
            _TableSpec(
                role=role,
                row_type=row_type,
                filename=location,
                id_index=id_index,
                field_terms=field_terms,
            )
        )

    return tables


def _read_tsv(zf: zipfile.ZipFile, filename: str, result: ValidationResult) -> list[list[str]] | None:
    if filename not in zf.namelist():
        result.add_error(f"meta.xml references {filename} but it is missing from the archive")
        return None
    raw = zf.read(filename).decode("utf-8")
    reader = csv.reader(io.StringIO(raw), delimiter="\t", quoting=csv.QUOTE_MINIMAL)
    return list(reader)


def _validate_core(
    zf: zipfile.ZipFile, core: _TableSpec, result: ValidationResult, required_terms: set[str]
) -> set[str]:
    rows = _read_tsv(zf, core.filename, result)
    if rows is None:
        return set()
    return _validate_table(rows, core, result, required_terms, collect_ids=True)


def _validate_extension(
    zf: zipfile.ZipFile,
    ext: _TableSpec,
    core_ids: set[str],
    result: ValidationResult,
    required_terms: set[str],
) -> None:
    rows = _read_tsv(zf, ext.filename, result)
    if rows is None:
        return
    ext_ids = _validate_table(rows, ext, result, required_terms, collect_ids=False)
    # coreid referential integrity
    missing = ext_ids - core_ids
    if missing:
        sample = sorted(missing)[:5]
        result.add_error(f"{ext.filename}: {len(missing)} coreid value(s) do not exist in core. " f"First: {sample}")


def _validate_table(
    rows: list[list[str]],
    spec: _TableSpec,
    result: ValidationResult,
    required_terms: set[str],
    collect_ids: bool,
) -> set[str]:
    if not rows:
        result.add_error(f"{spec.filename}: file is empty (not even a header)")
        return set()

    header = rows[0]
    data_rows = rows[1:]
    expected_cols = max([spec.id_index, *spec.field_terms.keys()], default=-1) + 1
    if len(header) != expected_cols:
        result.add_error(f"{spec.filename}: header has {len(header)} columns but meta.xml declares {expected_cols}")

    required_indices = [i for i, term in spec.field_terms.items() if term in required_terms]

    seen_ids: set[str] = set()
    ids: set[str] = set()
    for row_num, row in enumerate(data_rows, start=2):  # 1-based + header
        if len(row) != len(header):
            result.add_error(f"{spec.filename}:L{row_num}: row has {len(row)} columns, " f"expected {len(header)}")
            continue

        id_value = row[spec.id_index].strip() if spec.id_index < len(row) else ""
        if not id_value:
            result.add_error(f"{spec.filename}:L{row_num}: empty id/coreid value")
            continue

        if collect_ids:
            if id_value in seen_ids:
                result.add_error(f"{spec.filename}:L{row_num}: duplicate core id: {id_value!r}")
            seen_ids.add(id_value)
        ids.add(id_value)

        for idx in required_indices:
            if idx >= len(row) or not row[idx].strip():
                term = spec.field_terms[idx]
                result.add_error(f"{spec.filename}:L{row_num}: required term {term} is empty")

    return ids
