"""GBIF-backed RegionalSpeciesSource: species recorded in a GADM region, via GBIF's
occurrence search faceted by species.

Endpoints and parameters were exercised live against the GBIF API in the #1364 Phase 0
spike (region: Vermont, scope: Lepidoptera) — see docs/claude/analysis in the planning
branch for the findings. Unit tests for this module stub `create_session()`; nothing
here is exercised against the network in CI.
"""

from __future__ import annotations

from ...utils.requests import create_session
from ..models import RegionSource
from .regional_taxa import SourceSpecies, TaxonScope

GBIF_API_BASE = "https://api.gbif.org/v1"

# Species-key facets are paginated; a hard cap keeps a pathological region (or a
# scope too broad for faceting) from looping forever. Not a product requirement —
# just a safety net.
DEFAULT_MAX_SPECIES = 5000
DEFAULT_FACET_PAGE_SIZE = 1000
DEFAULT_TIMEOUT_SECONDS = 60


class GBIFRegionalSource:
    source_key = RegionSource.GBIF_GADM.value

    def __init__(
        self,
        facet_page_size: int = DEFAULT_FACET_PAGE_SIZE,
        max_species: int = DEFAULT_MAX_SPECIES,
        timeout: int = DEFAULT_TIMEOUT_SECONDS,
    ):
        self.facet_page_size = facet_page_size
        self.max_species = max_species
        self.timeout = timeout

    def fetch_species(self, region_code: str, taxon_scope: TaxonScope) -> list[SourceSpecies]:
        if taxon_scope.gbif_taxon_key is None:
            raise ValueError(f"GBIFRegionalSource requires a gbif_taxon_key on the taxon scope {taxon_scope.label!r}")

        session = create_session()
        counts_by_key = self._fetch_species_counts(session, region_code, taxon_scope.gbif_taxon_key)
        return self._resolve_species(session, counts_by_key)

    def _fetch_species_counts(self, session, region_code: str, gbif_taxon_key: int) -> dict[int, int]:
        """Page through the speciesKey facet for the region, returning
        {speciesKey: occurrence count}. Terminates when a page comes back shorter
        than requested or the species cap is hit."""
        counts_by_key: dict[int, int] = {}
        offset = 0
        while True:
            response = session.get(
                f"{GBIF_API_BASE}/occurrence/search",
                params={
                    "taxonKey": gbif_taxon_key,
                    "gadmGid": region_code,
                    "hasCoordinate": "true",
                    "facet": "speciesKey",
                    "facetLimit": self.facet_page_size,
                    "facetOffset": offset,
                    "limit": 0,
                },
                timeout=self.timeout,
            )
            response.raise_for_status()
            facets = response.json().get("facets", [])
            counts = facets[0]["counts"] if facets else []
            if not counts:
                break
            for entry in counts:
                counts_by_key[int(entry["name"])] = entry.get("count", 0)
            offset += self.facet_page_size
            if len(counts) < self.facet_page_size or len(counts_by_key) >= self.max_species:
                break
        return counts_by_key

    def _resolve_species(self, session, counts_by_key: dict[int, int]) -> list[SourceSpecies]:
        """Resolve each speciesKey to a scientific name (and, when available, its
        rank and rank-hierarchy fields) via GBIF's species-by-key endpoint."""
        species: list[SourceSpecies] = []
        for key, count in counts_by_key.items():
            response = session.get(f"{GBIF_API_BASE}/species/{key}", timeout=self.timeout)
            if response.status_code == 404:
                continue
            response.raise_for_status()
            data = response.json()
            name = (data.get("canonicalName") or data.get("species") or data.get("scientificName") or "").strip()
            if not name:
                continue
            species.append(
                SourceSpecies(
                    source=self.source_key,
                    scientific_name=name,
                    rank=data.get("rank"),
                    gbif_taxon_key=key,
                    observation_count=count,
                    raw=data,
                )
            )
        return species


DEFAULT_GADM_LEVEL = 1


def reverse_geocode_gadm(
    latitude: float,
    longitude: float,
    level: int = DEFAULT_GADM_LEVEL,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
    session=None,
) -> str | None:
    """Resolve a point to the GADM region id that contains it, at the requested level.

    Level 1 is state/province ("USA.46_1"), level 2 is county/district
    ("USA.46.14_1"). Returns the gid, or None when no GADM polygon of that level
    contains the point. This derives a `region_code` for a project or site from a
    deployment's stored latitude/longitude, so a regional taxa list can be built
    without anyone typing a region code by hand (issue #1364, path A3).

    Matching is on the gid shape rather than the response's source string: a level-N
    GADM gid has N dot-separated segments after the country and ends with the version
    suffix "_1" (level 0, the bare country code, has no suffix and is never returned).
    """
    session = session or create_session()
    response = session.get(
        f"{GBIF_API_BASE}/geocode/reverse",
        params={"lat": latitude, "lng": longitude},
        timeout=timeout,
    )
    response.raise_for_status()
    for item in response.json():
        gid = item.get("id", "")
        segments = gid.split(".")
        if gid.endswith("_1") and len(segments) == level + 1:
            return gid
    return None
