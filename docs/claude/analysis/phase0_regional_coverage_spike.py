"""Phase 0 spike (#1364) — verify GBIF/iNat regional endpoints and measure real
classifier label coverage. Throwaway measurement script, run inside the django
container so it has DB + network + the repo's create_session().

    docker compose exec -T django python docs/claude/analysis/phase0_regional_coverage_spike.py

Region: Vermont (matches the Quebec & Vermont classifier). Taxon scope: Lepidoptera.
Nothing is written to the DB. Output is a coverage report on stdout.
"""

from __future__ import annotations

import concurrent.futures
import sys
import time

from ami.ml.models.algorithm import Algorithm
from ami.utils.requests import create_session

GBIF = "https://api.gbif.org/v1"
INAT = "https://api.inaturalist.org/v1"
LEP_GBIF = 797  # Lepidoptera, GBIF backbone taxonKey
LEP_INAT = 47157  # Lepidoptera, iNaturalist taxon_id
VT_POINT = (44.26, -72.58)  # Montpelier, VT — for reverse-geocode (also exercises A3)
QV_ALGORITHM_PK = 10  # "Quebec & Vermont Species Classifier - Apr 2024" (2497 labels)


def norm(name: str) -> str:
    return (name or "").strip()


def load_classifier_labels() -> set[str]:
    algo = Algorithm.objects.get(pk=QV_ALGORITHM_PK)
    labels = algo.category_map.labels or []
    print(f"[classifier] {algo.name!r} — {len(labels)} labels")
    return {norm(x) for x in labels if norm(x)}


def gbif_reverse_gadm1(session, lat, lng) -> str | None:
    """A3 check: reverse-geocode a point to its GADM level-1 gid."""
    r = session.get(f"{GBIF}/geocode/reverse", params={"lat": lat, "lng": lng}, timeout=30)
    r.raise_for_status()
    gadm1 = None
    for item in r.json():
        gid = item.get("id", "")
        # GADM level-1 ids look like "USA.46_1"; level-0 "USA", level-2 "USA.46.14_1"
        if item.get("source", "").lower().find("gadm") >= 0 or gid.startswith("USA"):
            parts = gid.split(".")
            if len(parts) == 2 and gid.endswith("_1"):
                gadm1 = gid
                print(f"[gbif] reverse-geocode {lat},{lng} -> GADM1 {gid} ({item.get('title')})")
    return gadm1


def gbif_vt_species(session, gadm_gid: str, cap: int = 3000) -> set[str]:
    """Distinct Lepidoptera species in the region via speciesKey facet, resolved to names."""
    keys: list[int] = []
    offset = 0
    page = 1000
    while True:
        r = session.get(
            f"{GBIF}/occurrence/search",
            params={
                "taxonKey": LEP_GBIF,
                "gadmGid": gadm_gid,
                "hasCoordinate": "true",
                "facet": "speciesKey",
                "facetLimit": page,
                "facetOffset": offset,
                "limit": 0,
            },
            timeout=60,
        )
        r.raise_for_status()
        facets = r.json().get("facets", [])
        counts = facets[0]["counts"] if facets else []
        if not counts:
            break
        keys.extend(int(c["name"]) for c in counts)
        offset += page
        if len(counts) < page or len(keys) >= cap:
            break
    keys = keys[:cap]
    print(f"[gbif] {len(keys)} distinct Lepidoptera speciesKeys in {gadm_gid} (cap={cap}); resolving names...")

    def resolve(key: int) -> str | None:
        s = create_session()
        try:
            rr = s.get(f"{GBIF}/species/{key}", timeout=30)
            if rr.status_code != 200:
                return None
            d = rr.json()
            return norm(d.get("canonicalName") or d.get("species") or d.get("scientificName"))
        except Exception:
            return None

    names: set[str] = set()
    t0 = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as ex:
        for nm in ex.map(resolve, keys):
            if nm:
                names.add(nm)
    print(f"[gbif] resolved {len(names)} species names in {time.time() - t0:.0f}s")
    return names


def inat_place_id(session, q: str) -> int | None:
    r = session.get(f"{INAT}/places/autocomplete", params={"q": q, "per_page": 10}, timeout=30)
    r.raise_for_status()
    results = r.json().get("results", [])
    # admin_level 10 == state/province in iNat
    for p in results:
        if p.get("admin_level") == 10 and norm(p.get("name")) == q:
            print(f"[inat] place {q!r} -> place_id {p['id']} (admin_level 10)")
            return p["id"]
    if results:
        p = results[0]
        print(f"[inat] place {q!r} -> place_id {p['id']} ({p.get('name')}, admin_level {p.get('admin_level')}) [fallback]")
        return p["id"]
    return None


def inat_vt_species(session, place_id: int) -> set[str]:
    """Species-level Lepidoptera in the place; names come back inline (fast)."""
    names: set[str] = set()
    page = 1
    while True:
        r = session.get(
            f"{INAT}/observations/species_counts",
            params={
                "place_id": place_id,
                "taxon_id": LEP_INAT,
                "quality_grade": "research",
                "hrank": "species",
                "per_page": 500,
                "page": page,
            },
            timeout=60,
        )
        r.raise_for_status()
        data = r.json()
        results = data.get("results", [])
        for row in results:
            t = row.get("taxon", {})
            if t.get("rank") == "species" and t.get("name"):
                names.add(norm(t["name"]))
        total = data.get("total_results", 0)
        if page * 500 >= total or not results:
            break
        page += 1
    print(f"[inat] {len(names)} species-rank Lepidoptera in place {place_id}")
    return names


def pct(a: int, b: int) -> str:
    return f"{(100.0 * a / b):.1f}%" if b else "n/a"


def main() -> int:
    session = create_session()
    labels = load_classifier_labels()

    gadm1 = gbif_reverse_gadm1(session, *VT_POINT)
    gbif_names: set[str] = set()
    if gadm1:
        gbif_names = gbif_vt_species(session, gadm1)
    else:
        print("[gbif] could not resolve GADM1 gid; skipping GBIF")

    place = inat_place_id(session, "Vermont")
    inat_names = inat_vt_species(session, place) if place else set()

    union = gbif_names | inat_names
    print("\n==================== COVERAGE REPORT ====================")
    print(f"Q&V classifier labels        : {len(labels)}")
    print(f"GBIF VT Lepidoptera species  : {len(gbif_names)}")
    print(f"iNat VT Lepidoptera species  : {len(inat_names)}")
    print(f"Region union (GBIF ∪ iNat)   : {len(union)}")
    print("--------------------------------------------------------")
    cov_g = labels & gbif_names
    cov_i = labels & inat_names
    cov_u = labels & union
    print(f"Q&V ∩ GBIF   : {len(cov_g):5d}  ({pct(len(cov_g), len(labels))} of labels)")
    print(f"Q&V ∩ iNat   : {len(cov_i):5d}  ({pct(len(cov_i), len(labels))} of labels)")
    print(f"Q&V ∩ union  : {len(cov_u):5d}  ({pct(len(cov_u), len(labels))} of labels)  <-- default masking-list size")
    print("--------------------------------------------------------")
    only_region = union - labels
    print(f"Region species NOT in Q&V labels (no-model-coverage bucket): {len(only_region)}")
    print(f"  ({pct(len(only_region), len(union))} of the regional union — these are the include_uncovered opt-in rows)")
    print("========================================================")
    # A few examples of the intersection and the uncovered set for eyeballing name-match quality.
    print("sample Q&V∩union :", sorted(list(cov_u))[:8])
    print("sample region-only:", sorted(list(only_region))[:8])
    return 0


if __name__ == "__main__":
    sys.exit(main())
