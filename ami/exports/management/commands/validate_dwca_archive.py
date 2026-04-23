"""Offline structural validator for DwC-A zips.

Run against a fresh export before shipping to GBIF to catch drift between
meta.xml and the TSVs. Required-term enforcement defaults to the terms
this app marks as required in its field catalogue; pass --no-required
to do only structural checks.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from ami.exports.dwca import EVENT_FIELDS, OCCURRENCE_FIELDS
from ami.exports.dwca_validator import validate_dwca_zip


class Command(BaseCommand):
    help = "Validate a Darwin Core Archive zip against structural invariants."

    def add_arguments(self, parser):
        parser.add_argument("archive", help="Path to the DwC-A zip to validate")
        parser.add_argument(
            "--no-required",
            action="store_true",
            help="Skip required-field checks (structural only)",
        )

    def handle(self, *args, **options):
        archive = options["archive"]
        required_terms: set[str] = set()
        if not options["no_required"]:
            required_terms = {f.term for f in EVENT_FIELDS if f.required}
            required_terms |= {f.term for f in OCCURRENCE_FIELDS if f.required}

        result = validate_dwca_zip(archive, required_terms=required_terms)

        for warn in result.warnings:
            self.stdout.write(self.style.WARNING(f"WARN: {warn}"))
        for err in result.errors:
            self.stdout.write(self.style.ERROR(f"FAIL: {err}"))

        if result.ok:
            self.stdout.write(self.style.SUCCESS(f"OK: {archive} passes structural validation"))
            return

        raise CommandError(f"Validation failed with {len(result.errors)} error(s)")
