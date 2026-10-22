import dataclasses
import datetime

from django.http import QueryDict
from rest_framework import exceptions as api_exceptions
from rest_framework.test import APITestCase

from ami.jobs.models import Job
from ami.main.models import (
    Deployment,
    Detection,
    Device,
    Event,
    Identification,
    Occurrence,
    Project,
    Site,
    SourceImage,
    SourceImageCollection,
    TaxaList,
    Taxon,
    TaxonRank,
)
from ami.main.occurrence_filters import (
    DEFAULT_FILTER_PARAMS,
    PARAMETER_ALIASES,
    USER_DEPENDENT_PARAMS,
    OccurrenceFilterSet,
    clean_saved_filters,
    describe_saved_filters,
    filter_occurrences,
    saved_filter_params,
)
from ami.ml.models.algorithm import Algorithm
from ami.tests.fixtures.queries import no_query_cache
from ami.users.models import User

DAY_1 = datetime.date(2024, 1, 1)
DAY_2 = datetime.date(2024, 1, 2)


@dataclasses.dataclass
class FilterFixture:
    """A small project where every occurrence-list filter keeps some occurrences and drops others."""

    project: Project
    user: User
    refs: dict[str, int | str]  # Fixture names mapped to record ids, for building query strings.
    labels: dict[int, str]  # Occurrence ids mapped to fixture names, for readable assertions.

    def query(self, template: str) -> str:
        return template.format(**self.refs)


def build_filter_fixture() -> FilterFixture:
    user = User.objects.create(email="filters-owner@insectai.org")
    other_user = User.objects.create(email="filters-other@insectai.org")
    project = Project.objects.create(name="Occurrence Filters Project", owner=user)
    project.default_filters_score_threshold = 0.5
    project.save()

    device = Device.objects.create(name="Filters Device", project=project)
    dep_a = Deployment.objects.create(name="Filters Deployment A", project=project, device=device)
    site = Site.objects.create(name="Filters Site", project=project)
    dep_b = Deployment.objects.create(name="Filters Deployment B", project=project, research_site=site)

    def event(deployment, day):
        return Event.objects.create(
            project=project,
            deployment=deployment,
            group_by=day.isoformat(),
            start=datetime.datetime.combine(day, datetime.time(22, 0)),
        )

    def image(deployment, ev, day, name):
        return SourceImage.objects.create(
            deployment=deployment,
            project=project,
            event=ev,
            path=f"filters-{name}.jpg",
            timestamp=datetime.datetime.combine(day, datetime.time(22, 30)),
        )

    event_a1, event_a2, event_b1 = event(dep_a, DAY_1), event(dep_a, DAY_2), event(dep_b, DAY_1)
    img_a1 = image(dep_a, event_a1, DAY_1, "a1")
    img_a2 = image(dep_a, event_a2, DAY_2, "a2")
    img_b1 = image(dep_b, event_b1, DAY_1, "b1")

    capture_set_1 = SourceImageCollection.objects.create(project=project, name="Filters capture set 1")
    capture_set_1.images.set([img_a1, img_b1])
    capture_set_2 = SourceImageCollection.objects.create(project=project, name="Filters capture set 2")
    capture_set_2.images.set([img_a2])

    order = Taxon.objects.create(name="Filters Order", rank=TaxonRank.ORDER.name)
    genus = Taxon.objects.create(name="Filters Genus", rank=TaxonRank.GENUS.name, parent=order)
    species_1 = Taxon.objects.create(name="Filters species one", rank=TaxonRank.SPECIES.name, parent=genus)
    species_2 = Taxon.objects.create(name="Filters species two", rank=TaxonRank.SPECIES.name, parent=genus)
    other_order = Taxon.objects.create(name="Filters Other Order", rank=TaxonRank.ORDER.name)
    species_3 = Taxon.objects.create(name="Filters species three", rank=TaxonRank.SPECIES.name, parent=other_order)

    genus_list = TaxaList.objects.create(name="Filters genus list")
    genus_list.taxa.set([genus])
    genus_list.projects.add(project)
    other_list = TaxaList.objects.create(name="Filters other list")
    other_list.taxa.set([species_3])
    other_list.projects.add(project)

    detector = Algorithm.objects.create(name="Filters detector", version=1, task_type="localization")
    classifier_1 = Algorithm.objects.create(name="Filters classifier 1", version=1, task_type="classification")
    classifier_2 = Algorithm.objects.create(name="Filters classifier 2", version=1, task_type="classification")

    job_1 = Job.objects.create(project=project, name="Filters job 1")
    job_2 = Job.objects.create(project=project, name="Filters job 2")

    labels: dict[int, str] = {}

    def occurrence(label, deployment, ev, taxon, score, detections, identified_by=None):
        """``detections`` is a list of (image, detector, [(classifier, classification job)], detection job)."""
        occ = Occurrence.objects.create(
            project=project, event=ev, deployment=deployment, determination=taxon, determination_score=score
        )
        for img, detection_algorithm, classifications, detection_job in detections:
            detection = Detection.objects.create(
                source_image=img,
                timestamp=img.timestamp,
                bbox=[0.0, 0.0, 1.0, 1.0],
                detection_algorithm=detection_algorithm,
                occurrence=occ,
                job=detection_job,
            )
            for algorithm, classification_job in classifications:
                detection.classifications.create(
                    taxon=taxon, algorithm=algorithm, score=score, timestamp=img.timestamp, job=classification_job
                )
        if identified_by:
            Identification.objects.create(user=identified_by, occurrence=occ, taxon=taxon)
        # An identification can change the determination; restore the values the filters are tested on.
        Occurrence.objects.filter(pk=occ.pk).update(determination=taxon, determination_score=score)
        labels[occ.pk] = label

    occurrence("o1", dep_a, event_a1, species_1, 0.9, [(img_a1, detector, [(classifier_1, None)], job_1)], user)
    occurrence("o2", dep_a, event_a1, species_2, 0.8, [(img_a1, None, [(classifier_2, job_2)], None)])
    occurrence("o3", dep_a, event_a2, genus, 0.95, [(img_a2, None, [(classifier_1, None)], None)], other_user)
    occurrence("o4", dep_a, event_a2, species_3, 0.3, [(img_a2, None, [(classifier_2, None)], None)])
    occurrence("o5", dep_b, event_b1, species_3, 0.85, [(img_b1, None, [(classifier_1, job_1)], None)])
    # Two detections on two nights, by two classifiers: one occurrence that a join can repeat.
    occurrence(
        "o6",
        dep_a,
        event_a1,
        species_1,
        0.7,
        [(img_a1, None, [(classifier_1, None)], None), (img_a2, None, [(classifier_2, None)], None)],
        user,
    )
    occurrence("o7", dep_b, event_b1, order, 0.6, [(img_b1, None, [], None)])

    refs: dict[str, int | str] = {
        "dep_b": dep_b.pk,
        "device": device.pk,
        "site": site.pk,
        "event_a1": event_a1.pk,
        "img_a2": img_a2.pk,
        "capture_set_1": capture_set_1.pk,
        "capture_set_2": capture_set_2.pk,
        "order": order.pk,
        "genus": genus.pk,
        "species_3": species_3.pk,
        "genus_list": genus_list.pk,
        "other_list": other_list.pk,
        "detector": detector.pk,
        "classifier_1": classifier_1.pk,
        "classifier_2": classifier_2.pk,
        "job_1": job_1.pk,
        "job_2": job_2.pk,
        "day_1": DAY_1.isoformat(),
        "day_2": DAY_2.isoformat(),
    }
    return FilterFixture(project=project, user=user, refs=refs, labels=labels)


# Query strings the occurrence list accepted before its filters moved into one FilterSet, with the
# occurrences each one returned then (measured on the previous filter backends). Placeholders name
# fixture records; o4 is below the project's score threshold, so only apply_defaults=false shows it.
LIST_QUERIES = {
    "": {"o1", "o2", "o3", "o5", "o6", "o7"},
    "apply_defaults=false": {"o1", "o2", "o3", "o4", "o5", "o6", "o7"},
    "taxon={genus}": {"o1", "o2", "o3", "o6"},
    "determination={genus}": {"o1", "o2", "o3", "o6"},
    "taxon={species_3}&apply_defaults=false": {"o4", "o5"},
    "determination={order}&taxon={species_3}": {"o1", "o2", "o3", "o6", "o7"},
    "collection_id={capture_set_1}": {"o1", "o2", "o5", "o6", "o7"},
    "collection={capture_set_2}": {"o3", "o6"},
    "collection_id={capture_set_1}&collection={capture_set_2}": {"o1", "o2", "o5", "o6", "o7"},
    "algorithm={classifier_1}": {"o1", "o3", "o5", "o6"},
    "algorithm={classifier_1}&algorithm={classifier_2}": {"o1", "o2", "o3", "o5", "o6"},
    "algorithm={detector}": {"o1"},
    "not_algorithm={classifier_2}": {"o1", "o3", "o5", "o7"},
    "algorithm={classifier_1}&not_algorithm={classifier_2}": {"o1", "o3", "o5"},
    "not_algorithm={classifier_1}&not_algorithm={classifier_2}&apply_defaults=false": {"o7"},
    "job={job_1}": {"o1", "o5"},
    "job={job_2}": {"o2"},
    "date_start={day_2}": {"o3", "o6"},
    "date_end={day_1}": {"o1", "o2", "o5", "o6", "o7"},
    "date_start={day_1}&date_end={day_2}": {"o1", "o2", "o3", "o5", "o6", "o7"},
    "verified=true": {"o1", "o3", "o6"},
    "verified=false": {"o2", "o5", "o7"},
    "verified=1": {"o1", "o3", "o6"},
    "verified=0": {"o2", "o5", "o7"},
    "verified_by_me=true": {"o1", "o6"},
    "verified_by_me=false": {"o2", "o3", "o5", "o7"},
    "taxa_list_id={genus_list}": {"o1", "o2", "o3", "o6"},
    "not_taxa_list_id={genus_list}": {"o5", "o7"},
    "taxa_list_id={other_list}&not_taxa_list_id={genus_list}&apply_defaults=false": {"o4", "o5"},
    "taxa_list_id=999999999": {"o1", "o2", "o3", "o5", "o6", "o7"},
    "event={event_a1}": {"o1", "o2", "o6"},
    "deployment={dep_b}": {"o5", "o7"},
    "deployment__device={device}": {"o1", "o2", "o3", "o6"},
    "deployment__research_site={site}": {"o5", "o7"},
    "determination__rank=SPECIES": {"o1", "o2", "o5", "o6"},
    "detections__source_image={img_a2}": {"o3", "o6"},
    "taxa_list_id={genus_list}&date_start={day_2}&algorithm={classifier_1}&apply_defaults=false": {"o3", "o6"},
    "collection_id={capture_set_1}&verified=false&not_algorithm={classifier_2}": {"o5", "o7"},
    "job={job_1}&taxon={order}&ordering=-determination_score": {"o1"},
    "date_start={day_1}&verified_by_me=true&ordering=determination_score": {"o1", "o6"},
}

# Malformed values. Each must be refused with a 400, never a 500.
BAD_QUERIES = [
    "job=abc",
    "job=0",
    "date_start=2024-01-03&date_end=2024-01-01",
    "date_start=notadate",
    "taxon=999999999",
    "taxon=abc",
    "determination=abc",
    "collection_id=abc",
    "collection=abc",
    "algorithm=abc",
    "not_algorithm=1.5",
    "taxa_list_id=abc",
    "not_taxa_list_id=abc",
    "verified=abc",
]


# Query parameters of the occurrence list that choose the page or its order, not the occurrences.
NOT_FILTER_PARAMS = ("ordering",)


def saved_filters_from_query(query: str) -> dict:
    """A query string as saved filters: one value for each parameter, a list for a repeated one."""
    return {
        key: values if len(values) > 1 else values[0]
        for key, values in QueryDict(query).lists()
        if key not in NOT_FILTER_PARAMS
    }


class OccurrenceFiltersTest(APITestCase):
    """The occurrence list, its stats and saved filters all select occurrences through ``OccurrenceFilterSet``."""

    @classmethod
    def setUpTestData(cls):
        cls.fx = build_filter_fixture()

    def setUp(self):
        self.client.force_authenticate(self.fx.user)

    def _get(self, path: str, query: str):
        return self.client.get(f"/api/v2/{path}?project_id={self.fx.project.pk}&limit=100&{self.fx.query(query)}")

    def _list_labels(self, query: str) -> set[str]:
        response = self._get("occurrences/", query)
        self.assertEqual(response.status_code, 200, response.content)
        ids = [row["id"] for row in response.json()["results"]]
        self.assertEqual(len(ids), len(set(ids)), "an occurrence is listed twice")
        self.assertEqual(response.json()["count"], len(ids))
        return {self.fx.labels[pk] for pk in ids}

    def _labels(self, queryset) -> list[str]:
        return [self.fx.labels[pk] for pk in queryset.values_list("pk", flat=True)]

    def test_list_returns_the_same_occurrences_as_before(self):
        for query, expected in LIST_QUERIES.items():
            with self.subTest(query=query):
                self.assertEqual(self._list_labels(query), expected)

    def test_saved_filters_select_what_the_list_shows(self):
        for query, expected in LIST_QUERIES.items():
            if any(param in query for param in USER_DEPENDENT_PARAMS):
                continue
            saved = saved_filters_from_query(self.fx.query(query))
            with self.subTest(query=query):
                labels = self._labels(filter_occurrences(self.fx.project, saved))
                self.assertEqual(len(labels), len(set(labels)), "an occurrence is returned twice")
                self.assertEqual(set(labels), expected)
                normal = clean_saved_filters(saved)
                self.assertEqual(set(self._labels(filter_occurrences(self.fx.project, normal))), expected)

    def test_bad_values_are_refused_with_400(self):
        for query in BAD_QUERIES:
            param = query.split("=")[0]
            with self.subTest(query=query):
                for path in ("occurrences/", "occurrences/stats/model-agreement/"):
                    response = self._get(path, query)
                    self.assertEqual(response.status_code, 400, (path, response.content))
                    self.assertIn(param, response.json())
                with self.assertRaises(api_exceptions.ValidationError) as raised:
                    clean_saved_filters(saved_filters_from_query(query))
                self.assertIn(param, raised.exception.detail)

    def test_stats_count_the_occurrences_the_list_shows(self):
        for query, expected in LIST_QUERIES.items():
            with self.subTest(query=query):
                response = self._get("occurrences/stats/model-agreement/", query)
                self.assertEqual(response.status_code, 200, response.content)
                self.assertEqual(response.json()["total_occurrences"], len(expected))

    def test_saved_filters_accept_exactly_the_filterset_parameters(self):
        """Fails when a parameter is added to the list without deciding whether it can be saved."""
        filterset_params = set(OccurrenceFilterSet.base_filters)
        self.assertEqual(
            saved_filter_params(), (filterset_params | set(DEFAULT_FILTER_PARAMS)) - set(USER_DEPENDENT_PARAMS)
        )
        self.assertTrue(set(USER_DEPENDENT_PARAMS) <= filterset_params)
        self.assertTrue(set(PARAMETER_ALIASES) | set(PARAMETER_ALIASES.values()) <= filterset_params)
        used = {key for query in LIST_QUERIES for key in QueryDict(query).keys()}
        self.assertEqual(used - set(NOT_FILTER_PARAMS), filterset_params | set(DEFAULT_FILTER_PARAMS))

    def test_clean_saved_filters_returns_one_normal_form(self):
        refs = self.fx.refs
        as_strings = {
            "taxon": str(refs["genus"]),
            "collection": str(refs["capture_set_1"]),
            "algorithm": [str(refs["classifier_1"]), str(refs["classifier_2"])],
            "date_start": refs["day_1"],
            "verified": "false",
            "job": "",
            "taxa_list_id": None,
            "event": str(refs["event_a1"]),
        }
        as_values = {
            "event": refs["event_a1"],
            "determination": refs["genus"],
            "collection_id": refs["capture_set_1"],
            "algorithm": [refs["classifier_1"], refs["classifier_2"]],
            "date_start": refs["day_1"],
            "verified": False,
            "apply_defaults": True,
        }
        self.assertEqual(clean_saved_filters(as_strings), as_values)
        self.assertEqual(clean_saved_filters(as_values), as_values)
        self.assertEqual(clean_saved_filters(None), {"apply_defaults": True})
        self.assertEqual(clean_saved_filters({"apply_defaults": "false"}), {"apply_defaults": False})

    def test_clean_saved_filters_refuses_unknown_and_user_dependent_parameters(self):
        for saved, key in [
            ({"limit": 10}, "limit"),
            ({"project_id": self.fx.project.pk}, "project_id"),
            ({"verified_by_me": True}, "verified_by_me"),
            ({"apply_defaults": "maybe"}, "apply_defaults"),
            ({"job": [1, 2]}, "job"),
            ({"verified": 1}, "verified"),
        ]:
            with self.subTest(saved=saved):
                with self.assertRaises(api_exceptions.ValidationError) as raised:
                    clean_saved_filters(saved)
                self.assertIn(key, raised.exception.detail)
        with self.assertRaises(api_exceptions.ValidationError):
            clean_saved_filters(["collection_id", 1])

    def test_filter_occurrences_queries_do_not_grow_with_rows(self):
        """One statement selects the occurrences; the others read the project defaults and the taxa list.

        Two for the project's default taxa, two for the taxa list and its taxa, one for the occurrences.
        Cachalot is off so every query counts.
        """
        saved = self.fx.query("taxa_list_id={genus_list}&date_start={day_1}&algorithm={classifier_1}")
        with no_query_cache():
            with self.assertNumQueries(5):
                labels = self._labels(filter_occurrences(self.fx.project, saved_filters_from_query(saved)))
        self.assertEqual(set(labels), {"o1", "o3", "o6"})

    def test_describe_saved_filters_names_each_record(self):
        refs = self.fx.refs
        saved = {
            "collection_id": refs["capture_set_1"],
            "algorithm": [refs["classifier_1"], refs["classifier_2"]],
            "determination": refs["genus"],
            "taxa_list_id": 999999999,
            "verified": False,
            "apply_defaults": True,
        }
        with no_query_cache():
            # One query for each type of record: capture set, algorithm, taxon and taxa list.
            with self.assertNumQueries(4):
                display = describe_saved_filters(saved)
        self.assertEqual(
            display,
            {
                "collection": {"type": "capture_set", "id": refs["capture_set_1"], "name": "Filters capture set 1"},
                "algorithm": [
                    {"type": "algorithm", "id": refs["classifier_1"], "name": "Filters classifier 1"},
                    {"type": "algorithm", "id": refs["classifier_2"], "name": "Filters classifier 2"},
                ],
                "determination": {"type": "taxon", "id": refs["genus"], "name": "Filters Genus"},
                "taxa_list": {"type": "taxa_list", "id": 999999999, "name": None},
                "verified": False,
                "apply_defaults": True,
            },
        )
        # Exports saved before their filters were validated can hold ids as strings.
        self.assertEqual(
            describe_saved_filters({"collection_id": str(refs["capture_set_2"])}),
            {"collection": {"type": "capture_set", "id": refs["capture_set_2"], "name": "Filters capture set 2"}},
        )
