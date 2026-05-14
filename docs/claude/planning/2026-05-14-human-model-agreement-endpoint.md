# `/occurrences/stats/human-model-agreement/` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a project-scoped stats endpoint that returns verified-occurrence and human↔model-agreement rates over the same filter set the `/occurrences/` list view accepts.

**Architecture:**
- Pure aggregation function in `ami/main/models_future/occurrence.py` operating on an already-filtered `Occurrence` queryset (caller wires `apply_default_filters` + `OccurrenceFilter`).
- `@action` on existing `OccurrenceStatsViewSet`. Re-uses `OccurrenceViewSet`'s `filter_backends` + `filterset_fields` so any query param valid on the list view is valid here.
- LCA computed in Python via `Taxon.parents_json`. Rank ordering via existing `TaxonRank(OrderedEnum)`. No DB schema changes.

**Tech Stack:** Django 4.2, DRF, django-filter, drf-spectacular. Python 3.11.

**Spec reference:** `docs/claude/prompts/human-model-agreement-endpoint.md` (lives in sibling `user-leaderboard` worktree). Stats convention: `docs/claude/reference/api-stats-pattern.md`.

**Open questions resolved during planning** (cite as evidence in PR description):

- **"Verified"** = occurrence has ≥1 non-withdrawn `Identification`. Matches `OccurrenceVerified` filter at `ami/main/api/views.py:1032` (which doesn't filter `withdrawn`), with `withdrawn=False` added for stats — consistent with `OccurrenceQuerySet.with_verification_info()` at `ami/main/models.py:3032`.
- **"Model prediction"** = `Classification` chosen by `BEST_MACHINE_PREDICTION_ORDER = ("-terminal", "-score", "-pk")` at `ami/main/models.py:61`. NOT `Occurrence.determination` (user-overridable). Use existing `OccurrenceQuerySet.with_best_machine_prediction()` at `ami/main/models.py:2998` which exposes `best_machine_prediction_taxon_id`.
- **"Under order"** inclusive: a taxon's rank qualifies iff `TaxonRank(rank) >= TaxonRank.ORDER`. `OrderedEnum.__ge__` at `ami/utils/schemas.py:51`. So ORDER, SUPERFAMILY, FAMILY, SUBFAMILY, TRIBE, SUBTRIBE, GENUS, SPECIES all count. CLASS, PHYLUM, KINGDOM do not.

---

## File Structure

```
ami/
  main/
    models_future/
      occurrence.py            # ADD: human_model_agreement_for_project()
                               # ADD: _lca_rank_of() helper
    api/
      views.py                 # MODIFY: add human_model_agreement @action to OccurrenceStatsViewSet
      serializers.py           # ADD: HumanModelAgreementSerializer
    tests.py                   # MODIFY: extend TestOccurrenceStatsViewSet
ui/
  src/
    data-services/
      hooks/
        occurrences/
          stats/
            useHumanModelAgreement.ts   # ADD: typed React Query hook
```

No new files in backend (helpers live next to siblings). One new file frontend-side.

---

## Task 1: LCA helper + rank check (unit-test only, no DB)

**Files:**
- Modify: `ami/main/models_future/occurrence.py`
- Test: `ami/main/tests.py` (new class `TestHumanModelAgreementHelpers`)

The LCA helper takes two `parents_json` lists (plus each taxon's own `(id, rank)` since `parents_json` excludes self) and returns the most-specific shared ancestor's `TaxonRank`, or `None`. Pure function; no DB.

- [ ] **Step 1.1: Write failing unit tests**

Add to `ami/main/tests.py` (above `class TestOccurrenceStatsViewSet`):

```python
from ami.main.models import TaxonRank
from ami.main.models_future.occurrence import lca_rank_between


class TestLcaRankBetween(TestCase):
    """Pure-Python LCA over (taxon_id, rank, parents_json) tuples.

    Inputs encode each taxon as ``(id, rank_str, [{"id": int, "rank": str}, ...])``
    where the parents list is ordered root → immediate-parent (matches
    Taxon.parents_json layout).
    """

    GENUS_NOCTUA = (101, "GENUS", [
        {"id": 1, "rank": "KINGDOM"},
        {"id": 4, "rank": "ORDER"},
        {"id": 30, "rank": "FAMILY"},
    ])
    SPECIES_NOCTUA_PRONUBA = (201, "SPECIES", [
        {"id": 1, "rank": "KINGDOM"},
        {"id": 4, "rank": "ORDER"},
        {"id": 30, "rank": "FAMILY"},
        {"id": 101, "rank": "GENUS"},
    ])
    SPECIES_NOCTUA_FIMBRIATA = (202, "SPECIES", [
        {"id": 1, "rank": "KINGDOM"},
        {"id": 4, "rank": "ORDER"},
        {"id": 30, "rank": "FAMILY"},
        {"id": 101, "rank": "GENUS"},
    ])
    SPECIES_DIFFERENT_FAMILY = (301, "SPECIES", [
        {"id": 1, "rank": "KINGDOM"},
        {"id": 4, "rank": "ORDER"},
        {"id": 99, "rank": "FAMILY"},
    ])
    SPECIES_DIFFERENT_ORDER = (401, "SPECIES", [
        {"id": 1, "rank": "KINGDOM"},
        {"id": 5, "rank": "ORDER"},
    ])

    def test_identical_taxa_lca_is_self_rank(self):
        rank = lca_rank_between(self.SPECIES_NOCTUA_PRONUBA, self.SPECIES_NOCTUA_PRONUBA)
        self.assertEqual(rank, TaxonRank.SPECIES)

    def test_sister_species_share_genus(self):
        rank = lca_rank_between(self.SPECIES_NOCTUA_PRONUBA, self.SPECIES_NOCTUA_FIMBRIATA)
        self.assertEqual(rank, TaxonRank.GENUS)

    def test_genus_vs_species_in_same_genus(self):
        rank = lca_rank_between(self.GENUS_NOCTUA, self.SPECIES_NOCTUA_PRONUBA)
        # GENUS itself is on the species' ancestor chain, so LCA = GENUS.
        self.assertEqual(rank, TaxonRank.GENUS)

    def test_different_family_same_order(self):
        rank = lca_rank_between(self.SPECIES_NOCTUA_PRONUBA, self.SPECIES_DIFFERENT_FAMILY)
        self.assertEqual(rank, TaxonRank.ORDER)

    def test_different_order_same_kingdom(self):
        rank = lca_rank_between(self.SPECIES_NOCTUA_PRONUBA, self.SPECIES_DIFFERENT_ORDER)
        self.assertEqual(rank, TaxonRank.KINGDOM)

    def test_no_shared_ancestor_returns_none(self):
        rootless = (501, "SPECIES", [])
        rank = lca_rank_between(rootless, self.SPECIES_NOCTUA_PRONUBA)
        self.assertIsNone(rank)
```

- [ ] **Step 1.2: Run tests, confirm they fail (import error)**

```bash
docker compose run --rm django python manage.py test \
  ami.main.tests.TestLcaRankBetween -v 2 --keepdb
```
Expected: `ImportError: cannot import name 'lca_rank_between'`.

- [ ] **Step 1.3: Implement `lca_rank_between`**

Append to `ami/main/models_future/occurrence.py`:

```python
from ami.main.models import TaxonRank

TaxonTuple = tuple[int, str, list[dict]]


def lca_rank_between(a: TaxonTuple, b: TaxonTuple) -> TaxonRank | None:
    """Most-specific shared ancestor rank between two taxa.

    Inputs are ``(taxon_id, rank_str, parents_json)`` triples where
    ``parents_json`` is ordered root → immediate parent (Taxon.parents_json layout).

    The taxon itself counts as part of its own ancestor chain — passing the
    same taxon twice returns that taxon's rank. Returns ``None`` when the two
    chains share no ancestor (e.g. one has an empty parents_json and the other
    doesn't include it).
    """
    chain_a = [(p["id"], TaxonRank(p["rank"])) for p in a[2]] + [(a[0], TaxonRank(a[1]))]
    chain_b_ids = {p["id"] for p in b[2]} | {b[0]}

    deepest: TaxonRank | None = None
    for tid, rank in chain_a:
        if tid in chain_b_ids:
            if deepest is None or rank > deepest:
                deepest = rank
    return deepest
```

- [ ] **Step 1.4: Run tests, confirm all pass**

```bash
docker compose run --rm django python manage.py test \
  ami.main.tests.TestLcaRankBetween -v 2 --keepdb
```
Expected: `OK (6 tests)`.

- [ ] **Step 1.5: Commit**

```bash
git add ami/main/models_future/occurrence.py ami/main/tests.py
git commit -m "feat(occurrence-stats): add lca_rank_between helper

Pure-Python LCA over (taxon_id, rank, parents_json) tuples. Returns
the deepest shared TaxonRank or None. Used by the upcoming
human-model-agreement stat to bucket agreement at-or-finer-than ORDER.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 2: Aggregation function over a filtered queryset

**Files:**
- Modify: `ami/main/models_future/occurrence.py`
- Test: `ami/main/tests.py` (new class `TestHumanModelAgreementForProject`)

The function takes a filtered `Occurrence` queryset and returns a serializer-ready dict. Caller is responsible for wiring `apply_default_filters` + `OccurrenceFilter` upstream; the function adds the prefetches/annotations it needs and does the bucketing.

- [ ] **Step 2.1: Write failing test**

Add to `ami/main/tests.py`:

```python
class TestHumanModelAgreementForProject(APITestCase):
    """Aggregation function. DB-level. Covers the four bucket transitions:
    unverified, verified+exact-agreed, verified+under-order-agreed,
    verified+disagreed-above-order.
    """

    def setUp(self) -> None:
        project, deployment = setup_test_project()
        create_taxa(project=project)
        create_captures(deployment=deployment)
        create_occurrences(deployment=deployment, num=4)
        self.project = project
        # Need a couple of taxa at known ranks; create_taxa builds a small tree
        # rooted in a Kingdom -> Order -> Family -> Genus -> Species chain.
        self.species_a = Taxon.objects.get(name="Vanessa atalanta", projects=project)
        self.species_b = Taxon.objects.get(name="Vanessa cardui", projects=project)  # same genus
        self.species_c = Taxon.objects.get(name="Apis mellifera", projects=project)  # different family
        self.user = User.objects.create_user(email="ider@insectai.org")

    def _attach_machine_prediction(self, occurrence, taxon, score=0.9):
        # Picks up the existing detection on this occurrence and adds a Classification.
        detection = occurrence.detections.first()
        Classification.objects.create(
            detection=detection,
            taxon=taxon,
            score=score,
            terminal=True,
            algorithm=detection.detection_algorithm,
        )

    def _identify(self, occurrence, taxon):
        return Identification.objects.create(user=self.user, occurrence=occurrence, taxon=taxon)

    def test_empty_project_returns_zeros_not_nans(self):
        empty_project = Project.objects.create(name="empty")
        result = human_model_agreement_for_project(Occurrence.objects.filter(project=empty_project))
        self.assertEqual(result["total_occurrences"], 0)
        self.assertEqual(result["verified_count"], 0)
        self.assertEqual(result["verified_pct"], 0.0)
        self.assertEqual(result["agreed_exact_pct"], 0.0)
        self.assertEqual(result["agreed_under_order_pct"], 0.0)

    def test_buckets_four_canonical_cases(self):
        occurrences = list(Occurrence.objects.filter(project=self.project)[:4])
        # 0: verified, machine == user (exact agreement)
        self._attach_machine_prediction(occurrences[0], self.species_a)
        self._identify(occurrences[0], self.species_a)
        # 1: verified, machine sister-species (agreement at GENUS, under ORDER)
        self._attach_machine_prediction(occurrences[1], self.species_a)
        self._identify(occurrences[1], self.species_b)
        # 2: verified, machine different family but same ORDER (still under-order)
        # NOTE: requires species_c to share an order with species_a in the fixture.
        # If create_taxa() does not put Apis + Vanessa under the same ORDER,
        # construct a sibling-order test taxon here. See follow-up note below.
        # 3: unverified (no identification)
        self._attach_machine_prediction(occurrences[3], self.species_a)

        result = human_model_agreement_for_project(Occurrence.objects.filter(project=self.project))
        self.assertEqual(result["total_occurrences"], 4)
        self.assertEqual(result["verified_count"], 2)  # occurrences 0, 1
        self.assertEqual(result["agreed_exact_count"], 1)  # occurrence 0
        self.assertEqual(result["agreed_under_order_count"], 2)  # both — exact is a subset
        self.assertAlmostEqual(result["verified_pct"], 0.5)
        self.assertAlmostEqual(result["agreed_exact_pct"], 0.5)
        self.assertAlmostEqual(result["agreed_under_order_pct"], 1.0)
```

Note on `species_c`: if `create_taxa()` doesn't already place an Apis + Vanessa pair under a shared ORDER, drop that assertion and add a dedicated taxon fixture inside the test. Check `ami/main/tests.py` `create_taxa()` first.

- [ ] **Step 2.2: Run test, confirm import error**

```bash
docker compose run --rm django python manage.py test \
  ami.main.tests.TestHumanModelAgreementForProject -v 2 --keepdb
```

- [ ] **Step 2.3: Implement aggregation**

Append to `ami/main/models_future/occurrence.py`:

```python
def human_model_agreement_for_project(queryset: QuerySet[Occurrence]) -> dict:
    """Verified / agreement stats over a pre-filtered Occurrence queryset.

    The queryset MUST already be filtered down to the project + user-supplied
    filters (caller wires apply_default_filters + OccurrenceFilter). This
    function adds the prefetches/annotations it needs and returns a dict
    matching HumanModelAgreementSerializer's field set (without project_id —
    the view layer adds that).

    "Verified" means the occurrence has at least one non-withdrawn
    Identification. "Model prediction" means the Classification chosen by
    BEST_MACHINE_PREDICTION_ORDER. "Under-order" agreement means the user's
    taxon and the model's prediction share an ancestor at rank >= ORDER
    (inclusive of ORDER itself).
    """
    from ami.main.models import Classification, Taxon

    qs = (
        queryset
        .with_best_machine_prediction()  # annotates best_machine_prediction_taxon_id
        .prefetch_related(
            Prefetch(
                "identifications",
                queryset=Identification.objects.filter(withdrawn=False)
                    .select_related("taxon")
                    .order_by("-created_at", "-pk"),
                to_attr="_non_withdrawn_idents",
            )
        )
    )

    # Collect every taxon id we'll need (best-machine + best-user) to do a
    # single batched Taxon fetch for parents_json/rank.
    rows = list(qs.values(
        "pk",
        "best_machine_prediction_taxon_id",
    ))
    # NOTE: .values() drops the prefetched _non_withdrawn_idents; re-iterate qs
    # for identification access.
    occurrences = list(qs)

    needed_taxa_ids: set[int] = set()
    for occ in occurrences:
        if occ.best_machine_prediction_taxon_id:
            needed_taxa_ids.add(occ.best_machine_prediction_taxon_id)
        idents = getattr(occ, "_non_withdrawn_idents", [])
        if idents:
            needed_taxa_ids.add(idents[0].taxon_id)

    taxa_by_id: dict[int, tuple[int, str, list[dict]]] = {
        t.pk: (t.pk, t.rank, [p.dict() if hasattr(p, "dict") else p for p in t.parents_json])
        for t in Taxon.objects.filter(pk__in=needed_taxa_ids).only("pk", "rank", "parents_json")
    }

    total = len(occurrences)
    verified = 0
    agreed_exact = 0
    agreed_under_order = 0

    for occ in occurrences:
        idents = getattr(occ, "_non_withdrawn_idents", [])
        if not idents:
            continue
        verified += 1
        user_taxon_id = idents[0].taxon_id
        machine_taxon_id = occ.best_machine_prediction_taxon_id
        if not machine_taxon_id or not user_taxon_id:
            continue
        if user_taxon_id == machine_taxon_id:
            agreed_exact += 1
            agreed_under_order += 1
            continue
        user_tuple = taxa_by_id.get(user_taxon_id)
        machine_tuple = taxa_by_id.get(machine_taxon_id)
        if not user_tuple or not machine_tuple:
            continue
        lca = lca_rank_between(user_tuple, machine_tuple)
        if lca is not None and lca >= TaxonRank.ORDER:
            agreed_under_order += 1

    def _pct(num: int, denom: int) -> float:
        return round(num / denom, 4) if denom else 0.0

    return {
        "total_occurrences": total,
        "verified_count": verified,
        "verified_pct": _pct(verified, total),
        "agreed_exact_count": agreed_exact,
        "agreed_exact_pct": _pct(agreed_exact, verified),
        "agreed_under_order_count": agreed_under_order,
        "agreed_under_order_pct": _pct(agreed_under_order, verified),
    }
```

Note: `agreed_exact_count` is a subset of `agreed_under_order_count` by definition (exact match implies LCA = SPECIES which is >= ORDER). Document this in the serializer's docstring.

- [ ] **Step 2.4: Run tests; confirm pass**

```bash
docker compose run --rm django python manage.py test \
  ami.main.tests.TestHumanModelAgreementForProject -v 2 --keepdb
```

- [ ] **Step 2.5: Commit**

```bash
git add ami/main/models_future/occurrence.py ami/main/tests.py
git commit -m "feat(occurrence-stats): aggregate human-model agreement over filtered queryset

Pure aggregation; caller wires apply_default_filters + OccurrenceFilter.
Annotates best machine prediction, prefetches non-withdrawn identifications,
batches Taxon fetch for parents_json, buckets exact / under-order / above-order.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 3: Response serializer

**Files:**
- Modify: `ami/main/api/serializers.py`

- [ ] **Step 3.1: Add serializer**

Locate the existing stats serializers (search for `TopIdentifiersResponseSerializer`) and add below:

```python
class HumanModelAgreementSerializer(serializers.Serializer):
    """Verified / agreement rates over the filtered Occurrence set.

    `agreed_exact_count` is a subset of `agreed_under_order_count` by
    construction — an exact match implies an LCA at SPECIES, which is
    deeper than ORDER. `*_pct` percentages are 0.0..1.0 (not 0..100).
    """
    project_id = serializers.IntegerField()
    total_occurrences = serializers.IntegerField()
    verified_count = serializers.IntegerField()
    verified_pct = serializers.FloatField(help_text="verified_count / total_occurrences")
    agreed_exact_count = serializers.IntegerField()
    agreed_exact_pct = serializers.FloatField(help_text="agreed_exact_count / verified_count")
    agreed_under_order_count = serializers.IntegerField()
    agreed_under_order_pct = serializers.FloatField(help_text="agreed_under_order_count / verified_count")
```

- [ ] **Step 3.2: Commit**

```bash
git add ami/main/api/serializers.py
git commit -m "feat(occurrence-stats): add HumanModelAgreementSerializer

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 4: Action on `OccurrenceStatsViewSet` with filter wiring

**Files:**
- Modify: `ami/main/api/views.py`

Pull `OccurrenceViewSet`'s filter backend + filterset_fields list into a module-level tuple so both viewsets share it without `OccurrenceStatsViewSet` having to inherit from `DefaultViewSet` (it stays a plain `GenericViewSet`).

- [ ] **Step 4.1: Extract shared filter config**

Above `class OccurrenceViewSet(DefaultViewSet, ProjectMixin):` at `ami/main/api/views.py:1171`, add:

```python
OCCURRENCE_FILTER_BACKENDS = (
    CustomOccurrenceDeterminationFilter,
    OccurrenceCollectionFilter,
    OccurrenceAlgorithmFilter,
    OccurrenceDateFilter,
    OccurrenceVerified,
    OccurrenceVerifiedByMeFilter,
    OccurrenceTaxaListFilter,
)

OCCURRENCE_FILTERSET_FIELDS = (
    "event",
    "deployment",
    "determination__rank",
    "detections__source_image",
)
```

Then replace the literal lists in `OccurrenceViewSet`:

```python
    filter_backends = DefaultViewSetMixin.filter_backends + list(OCCURRENCE_FILTER_BACKENDS)
    filterset_fields = list(OCCURRENCE_FILTERSET_FIELDS)
```

- [ ] **Step 4.2: Wire filter machinery onto `OccurrenceStatsViewSet`**

In `OccurrenceStatsViewSet` at `ami/main/api/views.py:1268`, add (above `permission_classes`):

```python
    queryset = Occurrence.objects.none()  # hint for filterset introspection
    filter_backends = list(OCCURRENCE_FILTER_BACKENDS)
    filterset_fields = list(OCCURRENCE_FILTERSET_FIELDS)
```

(DRF's `filter_queryset` is only called when an action invokes it — `top_identifiers` doesn't, so no behavior change there.)

- [ ] **Step 4.3: Add `human_model_agreement` action**

Add to `OccurrenceStatsViewSet`, below `top_identifiers`:

```python
    @extend_schema(
        parameters=[project_id_doc_param],
        responses=HumanModelAgreementSerializer,
    )
    @action(detail=False, methods=["get"], url_path="human-model-agreement")
    def human_model_agreement(self, request):
        """Verified / human↔model agreement rates over the filtered occurrence set.

        Accepts every query param the `/occurrences/` list endpoint accepts.
        Reuses `apply_default_filters` so `apply_defaults=false` bypasses
        project default taxa lists + score thresholds.
        """
        project = self.get_active_project()
        assert project is not None  # require_project=True
        if not Project.objects.visible_for_user(request.user).filter(pk=project.pk).exists():
            raise NotFound("Project not found.")

        base_qs = (
            Occurrence.objects.filter(project=project)
            .valid()
            .apply_default_filters(project, request)
        )
        filtered_qs = self.filter_queryset(base_qs)
        payload = human_model_agreement_for_project(filtered_qs)
        payload["project_id"] = project.pk
        return Response(
            HumanModelAgreementSerializer(payload, context={"request": request}).data
        )
```

Add the import at the top of `ami/main/api/views.py`:

```python
from ami.main.models_future.occurrence import (
    human_model_agreement_for_project,
    top_identifiers_for_project,
)
```

And the serializer import:

```python
from ami.main.api.serializers import (
    ...,
    HumanModelAgreementSerializer,
)
```

- [ ] **Step 4.4: Lint + spectacular**

```bash
docker compose run --rm django flake8 ami/main/api/views.py ami/main/api/serializers.py
docker compose run --rm django python manage.py spectacular --api-version 'api' --format openapi --file /tmp/schema.yaml
```
Expected: lint clean. spectacular emits no new warnings about the new action.

- [ ] **Step 4.5: Commit**

```bash
git add ami/main/api/views.py ami/main/api/serializers.py
git commit -m "feat(occurrence-stats): wire human-model-agreement action

Extracts the OccurrenceViewSet filter backends + filterset_fields into a
module-level tuple, then attaches them to OccurrenceStatsViewSet so the
new action can reuse OccurrenceFilter pass-through unchanged. The
top_identifiers action keeps its current behavior — filter_queryset is
only invoked by actions that opt in.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 5: Endpoint tests

**Files:**
- Modify: `ami/main/tests.py`

- [ ] **Step 5.1: Add HTTP-level tests**

Append inside `class TestOccurrenceStatsViewSet`:

```python
    agreement_url = "/api/v2/occurrences/stats/human-model-agreement/"

    def _make_machine_prediction(self, occurrence, taxon, score=0.9):
        detection = occurrence.detections.first()
        Classification.objects.create(
            detection=detection,
            taxon=taxon,
            score=score,
            terminal=True,
            algorithm=detection.detection_algorithm,
        )

    def test_agreement_no_project_id_returns_400(self):
        response = self.client.get(self.agreement_url)
        self.assertEqual(response.status_code, 400)

    def test_agreement_draft_project_404_for_anon(self):
        self.project.draft = True
        self.project.save()
        response = self.client.get(f"{self.agreement_url}?project_id={self.project.pk}")
        self.assertEqual(response.status_code, 404)

    def test_agreement_empty_returns_zero_pcts(self):
        response = self.client.get(f"{self.agreement_url}?project_id={self.project.pk}")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["project_id"], self.project.pk)
        self.assertEqual(body["total_occurrences"], 4)
        self.assertEqual(body["verified_count"], 0)
        self.assertEqual(body["verified_pct"], 0.0)
        self.assertEqual(body["agreed_exact_pct"], 0.0)
        self.assertEqual(body["agreed_under_order_pct"], 0.0)

    def test_agreement_happy_path(self):
        occurrences = list(Occurrence.objects.filter(project=self.project)[:3])
        taxon_a = Taxon.objects.get(name="Vanessa atalanta", projects=self.project)
        taxon_b = Taxon.objects.get(name="Vanessa cardui", projects=self.project)
        self._make_machine_prediction(occurrences[0], taxon_a)
        self._id(self.alice, occurrences[0])  # exact agreement (taxon_a == self.taxon? confirm in fixture)
        # ... fill in remaining cases mirroring TestHumanModelAgreementForProject ...

        response = self.client.get(f"{self.agreement_url}?project_id={self.project.pk}")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["total_occurrences"], 4)
        self.assertEqual(body["verified_count"], 1)

    def test_agreement_filter_passthrough(self):
        """`?deployment=` should narrow the set."""
        other_deployment = Deployment.objects.create(name="other", project=self.project)
        response = self.client.get(
            f"{self.agreement_url}?project_id={self.project.pk}&deployment={other_deployment.pk}"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["total_occurrences"], 0)

    def test_agreement_apply_defaults_false_bypasses_project_filters(self):
        """Setting a score threshold on the project should reduce counts; apply_defaults=false restores them."""
        self.project.classification_threshold = 0.99
        self.project.save()
        gated = self.client.get(f"{self.agreement_url}?project_id={self.project.pk}").json()
        bypassed = self.client.get(
            f"{self.agreement_url}?project_id={self.project.pk}&apply_defaults=false"
        ).json()
        self.assertGreaterEqual(bypassed["total_occurrences"], gated["total_occurrences"])
```

- [ ] **Step 5.2: Run full stats viewset tests**

```bash
docker compose run --rm django python manage.py test \
  ami.main.tests.TestOccurrenceStatsViewSet \
  ami.main.tests.TestHumanModelAgreementForProject \
  ami.main.tests.TestLcaRankBetween -v 2 --keepdb
```

Expected: all pass.

- [ ] **Step 5.3: Commit**

```bash
git add ami/main/tests.py
git commit -m "test(occurrence-stats): HTTP coverage for human-model-agreement action

Covers: missing project_id 400, draft 404, empty zeros, happy path
bucket transitions, deployment filter pass-through, apply_defaults=false bypass.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 6: Frontend hook

**Files:**
- Create: `ui/src/data-services/hooks/occurrences/stats/useHumanModelAgreement.ts`

- [ ] **Step 6.1: Read the sibling hook**

```bash
cat ui/src/data-services/hooks/occurrences/stats/useTopIdentifiers.ts
```

- [ ] **Step 6.2: Write hook mirroring the pattern**

```typescript
import { useQuery } from '@tanstack/react-query'
import { axios } from 'data-services/api/axios'
import { API_ROUTES, API_URL } from 'data-services/constants'

export interface HumanModelAgreement {
  project_id: number
  total_occurrences: number
  verified_count: number
  verified_pct: number
  agreed_exact_count: number
  agreed_exact_pct: number
  agreed_under_order_count: number
  agreed_under_order_pct: number
}

export const useHumanModelAgreement = (params: Record<string, string | number | undefined>) => {
  const cleanParams = Object.fromEntries(
    Object.entries(params).filter(([, v]) => v !== undefined && v !== ''),
  )
  return useQuery<HumanModelAgreement>({
    queryKey: ['occurrences', 'stats', 'human-model-agreement', cleanParams],
    queryFn: async () => {
      const res = await axios.get<HumanModelAgreement>(
        `${API_URL}/occurrences/stats/human-model-agreement/`,
        { params: cleanParams },
      )
      return res.data
    },
    enabled: !!cleanParams.project_id,
  })
}
```

Adjust import paths/constants to match the actual `useTopIdentifiers.ts` (file uses repo-local aliases; copy them verbatim from the reference hook rather than guessing).

- [ ] **Step 6.3: Typecheck**

```bash
cd ui && yarn tsc --noEmit
```

- [ ] **Step 6.4: Commit**

```bash
git add ui/src/data-services/hooks/occurrences/stats/useHumanModelAgreement.ts
git commit -m "feat(ui): useHumanModelAgreement hook for occurrence stats

Mirrors useTopIdentifiers. Accepts arbitrary filter params so the
occurrence list page's filter state can be threaded through unchanged.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 7: Verification + PR

- [ ] **Step 7.1: Full test sweep**

```bash
docker compose run --rm django python manage.py test \
  ami.main.tests.TestOccurrenceStatsViewSet \
  ami.main.tests.TestHumanModelAgreementForProject \
  ami.main.tests.TestLcaRankBetween \
  ami.main.tests.TestOccurrenceListQueryCount -v 2 --keepdb
```

The `TestOccurrenceListQueryCount` run guards against accidentally regressing the list endpoint's prefetch contract when editing `OccurrenceViewSet` filter config.

- [ ] **Step 7.2: Manual smoke**

```bash
curl -s "http://localhost:8000/api/v2/occurrences/stats/human-model-agreement/?project_id=18" | jq
curl -s "http://localhost:8000/api/v2/occurrences/stats/human-model-agreement/?project_id=18&deployment=42" | jq
curl -s "http://localhost:8000/api/v2/occurrences/stats/human-model-agreement/?project_id=18&apply_defaults=false" | jq

# Sanity: total_occurrences should match the list endpoint's count.
curl -s "http://localhost:8000/api/v2/occurrences/?project_id=18" | jq .count
```

- [ ] **Step 7.3: Push + open PR**

```bash
git push -u origin feat/human-model-agreement-endpoint
gh pr create --title "feat(occurrence-stats): /occurrences/stats/human-model-agreement/" --body "$(cat <<'EOF'
## Summary

- New scalar stats action on `OccurrenceStatsViewSet` returning verified-occurrence and human↔model agreement rates over a filtered occurrence queryset.
- Reuses `OccurrenceViewSet`'s filter backends + `apply_default_filters` so any query param valid on `/occurrences/` is valid here.
- LCA computed in Python via `Taxon.parents_json` + `TaxonRank(OrderedEnum)`; "under-order" agreement is inclusive of ORDER itself.

## Decisions & evidence

- "Model prediction" = `BEST_MACHINE_PREDICTION_ORDER`-selected `Classification`, NOT `Occurrence.determination` (user-overridable).
- "Verified" = ≥1 non-withdrawn `Identification`. Consistent with `with_verification_info()` semantics, slightly stricter than `OccurrenceVerified` filter (which doesn't filter `withdrawn`).
- `agreed_exact_count` is a subset of `agreed_under_order_count` by construction — exact match implies LCA = SPECIES which is deeper than ORDER. Surfaced in the serializer docstring.

## Test plan

- [x] Unit: `TestLcaRankBetween` covers identical, sister-species, genus-vs-species, different-family, different-order, no-shared-ancestor.
- [x] Aggregation: `TestHumanModelAgreementForProject` covers empty project + four bucket transitions.
- [x] HTTP: `TestOccurrenceStatsViewSet.test_agreement_*` covers 400/404, empty-pct, happy path, filter pass-through, apply_defaults bypass.
- [x] Regression: `TestOccurrenceListQueryCount` still passes after filter config refactor.
- [ ] Smoke against project 18 via curl (see commands in plan).
EOF
)"
```

---

## Self-review checklist (run before declaring done)

- [ ] Every step has either code or an exact command — no "implement appropriate handling".
- [ ] Function/method names match across tasks: `lca_rank_between`, `human_model_agreement_for_project`, `HumanModelAgreementSerializer`, `human_model_agreement` action, `useHumanModelAgreement` hook.
- [ ] Test class names are unique and don't collide with existing classes in `ami/main/tests.py`.
- [ ] No new external dependencies introduced.
- [ ] Plan covers every requirement listed in `docs/claude/prompts/human-model-agreement-endpoint.md` (worktree `user-leaderboard`):
  - Response shape ✓ (Task 3)
  - OccurrenceFilter pass-through ✓ (Task 4)
  - `apply_defaults=false` ✓ (Task 4 base_qs + Task 5 test)
  - LCA via `parents_json` ✓ (Task 1)
  - Tests: happy / filter pass-through / empty / rank-LCA / draft 404 ✓ (Task 5)
  - FE hook ✓ (Task 6)

## Out of scope (deferred follow-ups)

- **Postgres-side rank ordering operator.** `TaxonRank` is `OrderedEnum` in Python; pushing rank comparisons into SQL would require materializing rank → int (e.g. a small mapping table or `CASE` expression). Useful when the stats grow to a per-rank breakdown chart, but the current LCA pass batch-fetches taxa once so it isn't on the hot path. File a follow-up ticket if a future stats kind genuinely scans more taxa than fit in one batch.
- **Disagreed-above-order breakdown.** The current response collapses "verified but no shared ancestor at-or-finer-than ORDER" into the residual `verified_count - agreed_under_order_count`. If the dashboard wants to chart that residual explicitly, expose `disagreed_above_order_count` derived in the serializer's `to_representation` (no extra compute).
- **OccurrenceFilter-driven export.** Tracked separately in `docs/claude/planning/occurrence-filter-driven-exports.md` (TBD — subagent stub).
