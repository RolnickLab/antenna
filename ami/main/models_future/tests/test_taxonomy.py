import datetime
import typing
import uuid

from cachalot.api import cachalot_disabled
from django.contrib.auth.models import AnonymousUser
from django.db import models
from django.test import TestCase
from django.utils import timezone
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from ami.main.models import (
    Classification,
    Deployment,
    Detection,
    Event,
    Identification,
    Occurrence,
    Project,
    SourceImage,
    SourceImageCollection,
    get_media_url,
)
from ami.main.models_future.enums import TaxonRank
from ami.main.models_future.taxonomy import TaxaList, Taxon, TaxonParent, verified_taxon_counts
from ami.users.models import User


def create_taxon(name: str, rank: TaxonRank, parent: Taxon | None = None, **kwargs) -> Taxon:
    return Taxon.objects.create(name=name, rank=rank.name, parent=parent, **kwargs)


def find_node(tree: dict, taxon: Taxon) -> dict | None:
    """Depth-first search for the node of ``taxon`` in a ``tree()`` result."""
    if tree["taxon"] == taxon:
        return tree
    for child in tree["children"]:
        found = find_node(child, taxon)
        if found:
            return found
    return None


def find_name_node(tree: dict, name: str) -> dict | None:
    """Depth-first search for the node of ``name`` in a ``tree_of_names()`` result."""
    if tree["name"] == name:
        return tree
    for child in tree["children"]:
        found = find_name_node(child, name)
        if found:
            return found
    return None


class TaxonManagerTestCase(TestCase):
    """One lineage of our own: Coleoptera > Coccinellidae > Coccinella > two species."""

    def setUp(self) -> None:
        self.order = create_taxon("Coleoptera", TaxonRank.ORDER)
        self.family = create_taxon("Coccinellidae", TaxonRank.FAMILY, parent=self.order)
        self.genus = create_taxon("Coccinella", TaxonRank.GENUS, parent=self.family)
        self.magnifica = create_taxon("Coccinella magnifica", TaxonRank.SPECIES, parent=self.genus)
        self.septempunctata = create_taxon("Coccinella septempunctata", TaxonRank.SPECIES, parent=self.genus)
        self.our_taxa = [self.order, self.family, self.genus, self.magnifica, self.septempunctata]
        return super().setUp()

    def test_get_queryset_parent_is_fetched_in_the_same_query(self):
        """``get_queryset()`` select_relates the parent, so reading it costs no extra query."""
        pks = [self.magnifica.pk, self.septempunctata.pk]
        disabled = cachalot_disabled()
        disabled.__enter__()
        try:
            with self.assertNumQueries(1):
                parent_names = [taxon.parent.name for taxon in Taxon.objects.filter(pk__in=pks)]
        finally:
            # cachalot_disabled() does not restore itself when the block raises.
            disabled.__exit__(None, None, None)
        self.assertEqual(parent_names, ["Coccinella", "Coccinella"])

    def test_species_that_already_have_a_genus_parent_are_left_alone(self):
        updated = Taxon.objects.add_genus_parents()

        self.septempunctata.refresh_from_db()
        self.assertEqual(self.septempunctata.parent, self.genus)
        self.assertNotIn(self.septempunctata, updated)

    def test_missing_genus_is_created_from_the_species_name(self):
        orphan = create_taxon("Zygaena filipendulae", TaxonRank.SPECIES)

        updated = Taxon.objects.add_genus_parents()

        genus = Taxon.objects.get(name="Zygaena")
        self.assertEqual(genus.rank, TaxonRank.GENUS.name)
        orphan.refresh_from_db()
        self.assertEqual(orphan.parent, genus)
        self.assertIn(genus, updated)
        self.assertIn(orphan, updated)

    def test_existing_genus_is_reused_rather_than_duplicated(self):
        existing_genus = create_taxon("Zygaena", TaxonRank.GENUS)
        orphan = create_taxon("Zygaena filipendulae", TaxonRank.SPECIES)

        Taxon.objects.add_genus_parents()

        orphan.refresh_from_db()
        self.assertEqual(orphan.parent, existing_genus)
        self.assertEqual(Taxon.objects.filter(name="Zygaena").count(), 1)

    def test_existing_taxon_of_another_rank_is_promoted_to_genus(self):
        """Taxon names are unique, so a name collision is resolved by changing the rank."""
        mislabelled = create_taxon("Zygaena", TaxonRank.FAMILY)
        orphan = create_taxon("Zygaena filipendulae", TaxonRank.SPECIES)

        Taxon.objects.add_genus_parents()

        mislabelled.refresh_from_db()
        self.assertEqual(mislabelled.rank, TaxonRank.GENUS.name)
        orphan.refresh_from_db()
        self.assertEqual(orphan.parent, mislabelled)

    def test_non_genus_parent_is_replaced(self):
        misplaced = create_taxon("Zygaena filipendulae", TaxonRank.SPECIES, parent=self.family)

        Taxon.objects.add_genus_parents()

        misplaced.refresh_from_db()
        self.assertEqual(misplaced.parent, Taxon.objects.get(name="Zygaena"))

    def our_display_names(self) -> dict[str, str | None]:
        pks = [taxon.pk for taxon in self.our_taxa]
        return dict(Taxon.objects.filter(pk__in=pks).values_list("name", "display_name"))

    def test_queryset_limits_the_update_to_those_taxa(self):
        # NULL rather than "", so clearing them does not trip the unique constraint.
        Taxon.objects.all().update(display_name=None)
        Taxon.objects.update_display_names(Taxon.objects.filter(pk=self.genus.pk))

        display_names = self.our_display_names()
        self.assertEqual(display_names.pop("Coccinella"), "Coccinella sp.")
        self.assertEqual(set(display_names.values()), {None})

    def expected_genus_node(self) -> dict:
        return {
            "taxon": self.genus,
            "children": [
                {"taxon": self.magnifica, "children": []},
                {"taxon": self.septempunctata, "children": []},
            ],
        }

    def test_taxa_are_nested_under_their_parents(self):
        """Any parentless taxon is attached to the root, so only our own lineage is asserted."""
        tree = Taxon.objects.tree()

        self.assertEqual(
            find_node(tree, self.family),
            {"taxon": self.family, "children": [self.expected_genus_node()]},
        )

    def test_explicit_root_is_used_instead_of_looking_one_up(self):
        tree = Taxon.objects.tree(root=self.order)

        self.assertEqual(tree["taxon"], self.order)
        self.assertIn({"taxon": self.family, "children": [self.expected_genus_node()]}, tree["children"])

    def test_inactive_taxa_are_excluded(self):
        Taxon.objects.filter(pk=self.magnifica.pk).update(active=False)

        genus_node = find_node(Taxon.objects.tree(), self.genus)
        self.assertEqual([child["taxon"] for child in genus_node["children"]], [self.septempunctata])

    def test_filtered_rank_is_skipped_and_its_children_attach_to_the_nearest_kept_ancestor(self):
        filter_ranks = [TaxonRank.ORDER, TaxonRank.FAMILY, TaxonRank.SPECIES]

        tree = Taxon.objects.tree(root=self.order, filter_ranks=filter_ranks)

        family_node = find_node(tree, self.family)
        self.assertEqual(
            [child["taxon"] for child in family_node["children"]],
            [self.magnifica, self.septempunctata],
        )

    def test_filtering_out_the_root_rank_is_refused(self):
        with self.assertRaises(ValueError):
            Taxon.objects.tree(root=self.order, filter_ranks=[TaxonRank.FAMILY, TaxonRank.SPECIES])

    def test_names_are_nested_under_their_parent_names(self):
        tree = Taxon.objects.tree_of_names(root=self.order)

        self.assertEqual(
            find_name_node(tree, "Coleoptera"),
            {
                "name": "Coleoptera",
                "children": [
                    {
                        "name": "Coccinellidae",
                        "children": [
                            {
                                "name": "Coccinella",
                                "children": [
                                    {"name": "Coccinella magnifica", "children": []},
                                    {"name": "Coccinella septempunctata", "children": []},
                                ],
                            }
                        ],
                    }
                ],
            },
        )

    def test_highest_ranked_parentless_taxon_wins(self):
        """Rank order decides, not the model's default ordering by name."""
        kingdom = create_taxon("Animalia", TaxonRank.KINGDOM)

        self.assertEqual(Taxon.objects.root(), kingdom)

    def test_parentless_taxon_of_a_lower_rank_does_not_win(self):
        create_taxon("Zygaena", TaxonRank.GENUS)

        self.assertEqual(Taxon.objects.root().rank, TaxonRank.ORDER.name)

    def parents_of(self, taxon: Taxon) -> list[tuple[int, str, TaxonRank]]:
        taxon.refresh_from_db()
        return [(parent.id, parent.name, parent.rank) for parent in taxon.parents_json]

    def test_whole_ancestor_chain_is_cached_in_rank_order(self):
        Taxon.objects.update_all_parents()

        self.assertEqual(
            self.parents_of(self.septempunctata),
            [
                (self.order.pk, "Coleoptera", TaxonRank.ORDER),
                (self.family.pk, "Coccinellidae", TaxonRank.FAMILY),
                (self.genus.pk, "Coccinella", TaxonRank.GENUS),
            ],
        )
        self.assertEqual(self.parents_of(self.family), [(self.order.pk, "Coleoptera", TaxonRank.ORDER)])

    def test_taxon_without_parent_has_no_cached_parents(self):
        Taxon.objects.update_all_parents()

        self.assertEqual(self.parents_of(self.order), [])

    def test_cached_parents_are_recomputed_after_a_reparenting(self):
        # .update() bypasses save(), so parents_json is left stale on purpose.
        Taxon.objects.filter(pk=self.septempunctata.pk).update(parent=self.family)

        Taxon.objects.update_all_parents()

        self.assertEqual(
            self.parents_of(self.septempunctata),
            [
                (self.order.pk, "Coleoptera", TaxonRank.ORDER),
                (self.family.pk, "Coccinellidae", TaxonRank.FAMILY),
            ],
        )

    def test_cached_parents_are_deserialised_as_taxon_parent_objects(self):
        Taxon.objects.update_all_parents()

        self.septempunctata.refresh_from_db()
        parents = self.septempunctata.parents_json
        self.assertTrue(parents)
        self.assertTrue(all(isinstance(parent, TaxonParent) for parent in parents))
        self.assertTrue(all(isinstance(parent.rank, TaxonRank) for parent in parents))


class TaxonDisplayTestCase(TestCase):
    """Rank-dependent naming. ``display_name`` is a Label Studio choice key, so it must stay unique."""

    def test_str_includes_the_rank(self):
        taxon = create_taxon("Coccinella", TaxonRank.GENUS)

        self.assertEqual(str(taxon), "Coccinella (GENUS)")

    def test_a_genus_is_suffixed_so_it_stays_unique_against_its_own_species(self):
        genus = create_taxon("Coccinella", TaxonRank.GENUS)
        species = create_taxon("Coccinella septempunctata", TaxonRank.SPECIES, parent=genus)

        self.assertEqual(genus.get_display_name(), "Coccinella sp.")
        self.assertEqual(species.get_display_name(), "Coccinella septempunctata")

    def test_every_other_rank_displays_its_bare_name(self):
        for rank in [TaxonRank.ORDER, TaxonRank.FAMILY, TaxonRank.TRIBE, TaxonRank.UNKNOWN]:
            with self.subTest(rank=rank.name):
                taxon = create_taxon(f"Taxon {rank.name}", rank)
                self.assertEqual(taxon.get_display_name(), f"Taxon {rank.name}")

    def test_rank_is_returned_as_an_orderable_enum(self):
        taxon = create_taxon("Coccinellidae", TaxonRank.FAMILY)

        self.assertEqual(taxon.get_rank(), TaxonRank.FAMILY)
        # Broader ranks sort first, which is what orders parents_json.
        self.assertLess(taxon.get_rank(), TaxonRank.GENUS)


class TaxonCalculatedFieldsTestCase(TestCase):
    """``display_name``, ``parents_json``, and ``search_names`` are caches maintained by save()."""

    def setUp(self) -> None:
        self.order = create_taxon("Coleoptera", TaxonRank.ORDER)
        self.family = create_taxon("Coccinellidae", TaxonRank.FAMILY, parent=self.order)
        self.genus = create_taxon("Coccinella", TaxonRank.GENUS, parent=self.family)
        return super().setUp()

    def parent_names(self, taxon: Taxon) -> list[str]:
        taxon.refresh_from_db()
        return [parent.name for parent in taxon.parents_json]

    def test_saving_populates_all_three_caches(self):
        species = create_taxon(
            "Coccinella septempunctata",
            TaxonRank.SPECIES,
            parent=self.genus,
            common_name_en="Seven-spot ladybird",
        )

        species.refresh_from_db()
        self.assertEqual(species.display_name, "Coccinella septempunctata")
        self.assertEqual(
            [parent.name for parent in species.parents_json],
            ["Coleoptera", "Coccinellidae", "Coccinella"],
        )
        self.assertEqual(species.search_names, ["Seven-spot ladybird"])

    def test_saving_recalculates_a_stale_display_name(self):
        self.genus.display_name = "Stale"
        self.genus.save()

        self.genus.refresh_from_db()
        self.assertEqual(self.genus.display_name, "Coccinella sp.")

    def test_saving_can_skip_the_recalculation(self):
        """Used by update_calculated_fields() itself, and by callers that set the caches by hand."""
        self.genus.display_name = "Stale"
        self.genus.save(update_calculated_fields=False)

        self.genus.refresh_from_db()
        self.assertEqual(self.genus.display_name, "Stale")

    def test_update_calculated_fields_without_save_does_not_write(self):
        # NULL rather than "", so clearing it does not trip the unique constraint.
        Taxon.objects.filter(pk=self.genus.pk).update(display_name=None, search_names=None, parents_json=[])
        self.genus.refresh_from_db()

        self.genus.update_calculated_fields(save=False)

        self.assertEqual(self.genus.display_name, "Coccinella sp.")
        self.assertEqual([parent.name for parent in self.genus.parents_json], ["Coleoptera", "Coccinellidae"])
        self.genus.refresh_from_db()
        self.assertIsNone(self.genus.display_name)
        self.assertEqual(self.genus.parents_json, [])

    def test_cached_parents_are_rebuilt_by_following_the_parent_chain(self):
        # .update() bypasses save(), so parents_json is left stale on purpose.
        Taxon.objects.filter(pk=self.genus.pk).update(parent=self.order)
        self.genus.refresh_from_db()

        self.genus.update_parents()

        self.assertEqual(self.parent_names(self.genus), ["Coleoptera"])

    def test_update_parents_without_save_does_not_write(self):
        self.genus.parent = None

        self.assertEqual(self.genus.update_parents(save=False), [])

        self.assertEqual(self.parent_names(self.genus), ["Coleoptera", "Coccinellidae"])

    def test_common_names_are_added_to_search_names_without_duplicating_them(self):
        taxon = create_taxon("Zygaena filipendulae", TaxonRank.SPECIES, common_name_en="Six-spot burnet")

        taxon.save()

        taxon.refresh_from_db()
        self.assertEqual(taxon.search_names, ["Six-spot burnet"])

    def test_names_already_in_the_search_list_are_kept(self):
        taxon = create_taxon("Zygaena filipendulae", TaxonRank.SPECIES, common_name_en="Six-spot burnet")
        taxon.search_names = ["Sint-jansvlinder"]

        taxon.update_search_names(save=True)

        taxon.refresh_from_db()
        self.assertEqual(set(taxon.search_names), {"Sint-jansvlinder", "Six-spot burnet"})

    def test_update_search_names_does_not_write_unless_asked(self):
        """``save`` defaults to False here, unlike update_parents(), which defaults to True."""
        taxon = create_taxon("Zygaena filipendulae", TaxonRank.SPECIES)
        taxon.common_name_en = "Six-spot burnet"

        taxon.update_search_names()

        self.assertEqual(taxon.search_names, ["Six-spot burnet"])
        taxon.refresh_from_db()
        self.assertEqual(taxon.search_names, [])


class TaxonRelationsTestCase(TestCase):
    """Per-taxon rollups over children, occurrences, detections, and taxa lists.

    Lineage: Coleoptera > Coccinellidae > Coccinella > magnifica / septempunctata.
    """

    def setUp(self) -> None:
        short_id = uuid.uuid4().hex[:8]
        self.project = Project.objects.create(name=f"Taxon Relations Project {short_id}")
        self.deployment = Deployment.objects.create(name=f"Relations Station {short_id}", project=self.project)
        self.capture = SourceImage.objects.create(
            deployment=self.deployment, project=self.project, path="20230601120000-snapshot.jpg"
        )
        self.order = create_taxon("Coleoptera", TaxonRank.ORDER)
        self.family = create_taxon("Coccinellidae", TaxonRank.FAMILY, parent=self.order)
        self.genus = create_taxon("Coccinella", TaxonRank.GENUS, parent=self.family)
        self.magnifica = create_taxon("Coccinella magnifica", TaxonRank.SPECIES, parent=self.genus)
        self.septempunctata = create_taxon("Coccinella septempunctata", TaxonRank.SPECIES, parent=self.genus)
        return super().setUp()

    def create_occurrence(
        self,
        taxon: Taxon,
        *,
        created_at: datetime.datetime | None = None,
        detection_scores: tuple[float, ...] = (),
        project: Project | None = None,
    ) -> Occurrence:
        """An occurrence determined as ``taxon``, with one detection per score given."""
        occurrence = Occurrence.objects.create(
            project=project or self.project,
            deployment=self.deployment,
            determination=taxon,
            determination_score=max(detection_scores, default=None),
        )
        for index, score in enumerate(detection_scores):
            detection = Detection.objects.create(
                source_image=self.capture,
                occurrence=occurrence,
                path=f"detections/{occurrence.pk}_{index}.jpg",
                bbox=[0.1, 0.1, 0.2, 0.2],
                timestamp=self.capture.timestamp,
            )
            Classification.objects.create(detection=detection, taxon=taxon, score=score, timestamp=timezone.now())
        if created_at:
            Occurrence.objects.filter(pk=occurrence.pk).update(created_at=created_at)
            Detection.objects.filter(occurrence=occurrence).update(created_at=created_at)
        return occurrence

    def best_detection_url(self, occurrence: Occurrence, *, index: int) -> str:
        """The media URL of the detection crop created at ``index`` by create_occurrence()."""
        return get_media_url(f"detections/{occurrence.pk}_{index}.jpg")

    def test_direct_children_are_counted_one_level_deep(self):
        self.assertEqual(self.order.num_direct_children(), 1)
        self.assertEqual(self.genus.num_direct_children(), 2)
        self.assertEqual(self.magnifica.num_direct_children(), 0)

    def test_recursive_children_are_counted_from_the_cached_parents(self):
        counts = {taxon.name: taxon.num_children_recursive() for taxon in [self.order, self.genus, self.magnifica]}

        self.assertEqual(counts, {"Coleoptera": 4, "Coccinella": 2, "Coccinella magnifica": 0})

    def test_recursive_occurrence_counts_roll_up_from_descendants(self):
        self.create_occurrence(self.genus)
        self.create_occurrence(self.septempunctata)
        self.create_occurrence(self.septempunctata)

        counts = {
            taxon.name: taxon.occurrences_count_recursive() for taxon in [self.order, self.genus, self.magnifica]
        }

        self.assertEqual(counts, {"Coleoptera": 3, "Coccinella": 3, "Coccinella magnifica": 0})

    def test_latest_occurrence_is_the_most_recently_created_one(self):
        now = timezone.now()
        self.create_occurrence(self.septempunctata, created_at=now - datetime.timedelta(days=2))
        newest = self.create_occurrence(self.septempunctata, created_at=now - datetime.timedelta(days=1))

        self.assertEqual(self.septempunctata.latest_occurrence(), newest)

    def test_latest_occurrence_is_none_for_a_taxon_never_determined(self):
        self.assertIsNone(self.magnifica.latest_occurrence())

    def test_latest_detection_is_the_most_recent_one_across_occurrences(self):
        now = timezone.now()
        self.create_occurrence(
            self.septempunctata, created_at=now - datetime.timedelta(days=2), detection_scores=(0.5,)
        )
        newest = self.create_occurrence(
            self.septempunctata, created_at=now - datetime.timedelta(days=1), detection_scores=(0.6,)
        )

        self.assertEqual(self.septempunctata.latest_detection(), newest.detections.get())

    def test_latest_detection_is_none_for_a_taxon_never_determined(self):
        self.assertIsNone(self.magnifica.latest_detection())

    def test_values_supplied_by_query_annotations_are_neutral_on_a_plain_instance(self):
        """These are overridden by TaxonQuerySet annotations; unannotated they must not lie."""
        self.create_occurrence(self.septempunctata, detection_scores=(0.9,))

        taxon = self.septempunctata
        self.assertEqual(
            {
                "occurrences_count": taxon.occurrences_count(),
                "detections_count": taxon.detections_count(),
                "events_count": taxon.events_count(),
                "last_detected": taxon.last_detected(),
                "best_determination_score": taxon.best_determination_score(),
                "verified_count": taxon.verified_count(),
                "occurrence_images": taxon.occurrence_images(),
            },
            {
                "occurrences_count": 0,
                "detections_count": 0,
                "events_count": 0,
                "last_detected": None,
                "best_determination_score": None,
                "verified_count": None,
                "occurrence_images": [],
            },
        )

    def test_list_names_joins_the_taxa_lists_the_taxon_belongs_to(self):
        for name in ["Checklist A", "Checklist B"]:
            TaxaList.objects.create(name=name).taxa.add(self.septempunctata)

        self.assertEqual(set(self.septempunctata.list_names().split(", ")), {"Checklist A", "Checklist B"})

    def test_list_names_is_empty_for_a_taxon_in_no_list(self):
        self.assertEqual(self.magnifica.list_names(), "")

    def test_summary_charts_need_a_project(self):
        self.assertEqual(self.septempunctata.summary_data(), [])

    def test_summary_charts_are_returned_per_project(self):
        self.create_occurrence(self.septempunctata, detection_scores=(0.9,))

        plots = self.septempunctata.summary_data(project=self.project)

        self.assertEqual([plot["title"] for plot in plots], ["Occurrences per day", "Occurrences per month"])

    def test_occurrence_image_urls_are_the_best_scoring_detection_of_each_occurrence(self):
        first = self.create_occurrence(self.septempunctata, detection_scores=(0.4, 0.9))
        second = self.create_occurrence(self.septempunctata, detection_scores=(0.8, 0.2))

        urls = self.septempunctata.get_occurrence_images()

        self.assertEqual(
            urls,
            [
                self.best_detection_url(first, index=1),
                self.best_detection_url(second, index=0),
            ],
        )

    def test_occurrence_image_urls_are_limited(self):
        self.create_occurrence(self.septempunctata, detection_scores=(0.4,))
        best = self.create_occurrence(self.septempunctata, detection_scores=(0.9,))

        urls = self.septempunctata.get_occurrence_images(limit=1)

        self.assertEqual(urls, [self.best_detection_url(best, index=0)])

    def test_occurrence_image_urls_can_be_scoped_to_one_project(self):
        other_project = Project.objects.create(name=f"Other Relations Project {uuid.uuid4().hex[:8]}")
        mine = self.create_occurrence(self.septempunctata, detection_scores=(0.4,))
        self.create_occurrence(self.septempunctata, detection_scores=(0.9,), project=other_project)

        urls = self.septempunctata.get_occurrence_images(project_id=self.project.pk)

        self.assertEqual(urls, [self.best_detection_url(mine, index=0)])

    def test_occurrence_image_urls_are_empty_for_a_taxon_without_detections(self):
        self.create_occurrence(self.magnifica)

        self.assertEqual(self.magnifica.get_occurrence_images(), [])


class TaxonQuerySetTestCase(TestCase):
    """Shared fixture for the project-scoped annotations the taxa list builds.

    Lineage: Coleoptera > Coccinellidae > Coccinella > magnifica / septempunctata.
    The project keeps the model's default score threshold of 0.5, and the occurrence
    filters mirror the ones ``TaxonViewSet.get_occurrence_filters()`` passes in.
    """

    def setUp(self) -> None:
        short_id = uuid.uuid4().hex[:8]
        self.project = Project.objects.create(name=f"Taxon QuerySet Project {short_id}")
        self.deployment = Deployment.objects.create(name=f"QuerySet Station {short_id}", project=self.project)
        self.event = Event.objects.create(
            project=self.project,
            deployment=self.deployment,
            group_by="2023-06-01",
            start=datetime.datetime(2023, 6, 1, 20, 0),
            end=datetime.datetime(2023, 6, 2, 4, 0),
        )
        self.capture = SourceImage.objects.create(
            project=self.project,
            deployment=self.deployment,
            event=self.event,
            path="20230601200000-snapshot.jpg",
            timestamp=datetime.datetime(2023, 6, 1, 20, 0),
        )
        self.order = create_taxon("Coleoptera", TaxonRank.ORDER)
        self.family = create_taxon("Coccinellidae", TaxonRank.FAMILY, parent=self.order)
        self.genus = create_taxon("Coccinella", TaxonRank.GENUS, parent=self.family)
        self.magnifica = create_taxon("Coccinella magnifica", TaxonRank.SPECIES, parent=self.genus)
        self.septempunctata = create_taxon("Coccinella septempunctata", TaxonRank.SPECIES, parent=self.genus)
        self.our_taxa = [self.order, self.family, self.genus, self.magnifica, self.septempunctata]
        self.user = User.objects.create_user(email=f"taxa-qs-{short_id}@insectai.org", password="password123")
        return super().setUp()

    def occurrence_filters(self, accessor: str = "", collection: "SourceImageCollection | None" = None) -> models.Q:
        """The filters the taxa list builds: this project, and only grouped occurrences."""
        prefix = f"{accessor}__" if accessor else ""
        filters = models.Q(**{f"{prefix}project": self.project, f"{prefix}event__isnull": False})
        if collection:
            filters &= models.Q(**{f"{prefix}detections__source_image__collections": collection.pk})
        return filters

    def request(self, **query_params: str) -> Request:
        return Request(APIRequestFactory().get("/", query_params))

    def create_occurrence(
        self,
        taxon: Taxon,
        *,
        score: float | None = 0.9,
        detection_timestamps: tuple[datetime.datetime, ...] = (datetime.datetime(2023, 6, 1, 21, 0),),
        project: Project | None = None,
    ) -> Occurrence:
        occurrence = Occurrence.objects.create(
            project=project or self.project,
            deployment=self.deployment,
            event=self.event,
            determination=taxon,
            determination_score=score,
        )
        for index, timestamp in enumerate(detection_timestamps):
            Detection.objects.create(
                source_image=self.capture,
                occurrence=occurrence,
                path=f"detections/{occurrence.pk}_{index}.jpg",
                bbox=[0.1, 0.1, 0.2, 0.2],
                timestamp=timestamp,
            )
        return occurrence

    def verify(self, occurrence: Occurrence, *, withdrawn: bool = False) -> Identification:
        """Verify an occurrence as its own determination, so the determination does not move."""
        return Identification.objects.create(
            occurrence=occurrence,
            taxon=occurrence.determination,
            user=self.user,
            withdrawn=withdrawn,
        )

    def collection_of_the_capture(self) -> "SourceImageCollection":
        collection = SourceImageCollection.objects.create(
            project=self.project, name=f"Collection {uuid.uuid4().hex[:8]}", method="manual"
        )
        collection.images.add(self.capture)
        return collection

    def annotated(self, queryset: models.QuerySet, field: str) -> dict[str, typing.Any]:
        """Read one annotation off our own taxa, keyed by name."""
        our_taxa = queryset.filter(pk__in=[taxon.pk for taxon in self.our_taxa])
        return {taxon.name: getattr(taxon, field) for taxon in our_taxa}

    def observation_counts(self, **kwargs) -> models.QuerySet:
        return Taxon.objects.with_observation_counts_subqueries(
            self.project, kwargs.pop("request", None), occurrence_filters=self.occurrence_filters(), **kwargs
        )


class TaxonObservationCountTestCase(TaxonQuerySetTestCase):
    """``occurrences_count`` / ``best_determination_score`` / ``last_detected``, both SQL shapes."""

    def test_occurrences_are_counted_per_taxon(self):
        self.create_occurrence(self.septempunctata)
        self.create_occurrence(self.septempunctata)
        self.create_occurrence(self.magnifica)

        counts = self.annotated(self.observation_counts(), "occurrences_count")

        self.assertEqual(counts["Coccinella septempunctata"], 2)
        self.assertEqual(counts["Coccinella magnifica"], 1)

    def test_counts_do_not_roll_up_to_ancestor_taxa(self):
        """Only verified_count rolls up; the value columns match the exact determination."""
        self.create_occurrence(self.septempunctata)

        counts = self.annotated(self.observation_counts(), "occurrences_count")

        # Coalesced to 0 rather than NULL, so the column is always a number.
        self.assertEqual(counts["Coccinella"], 0)
        self.assertEqual(counts["Coleoptera"], 0)

    def test_best_score_and_last_detection_are_annotated(self):
        self.create_occurrence(
            self.septempunctata, score=0.6, detection_timestamps=(datetime.datetime(2023, 6, 1, 21, 0),)
        )
        self.create_occurrence(
            self.septempunctata, score=0.8, detection_timestamps=(datetime.datetime(2023, 6, 1, 23, 30),)
        )

        qs = self.observation_counts()

        self.assertEqual(self.annotated(qs, "best_determination_score")["Coccinella septempunctata"], 0.8)
        self.assertEqual(
            self.annotated(qs, "last_detected")["Coccinella septempunctata"],
            datetime.datetime(2023, 6, 1, 23, 30),
        )

    def test_values_are_null_for_a_taxon_without_occurrences(self):
        qs = self.observation_counts()

        self.assertIsNone(self.annotated(qs, "best_determination_score")["Coccinella magnifica"])
        self.assertIsNone(self.annotated(qs, "last_detected")["Coccinella magnifica"])

    def test_occurrences_below_the_project_score_threshold_are_not_counted(self):
        self.create_occurrence(self.septempunctata, score=0.4)

        counts = self.annotated(self.observation_counts(), "occurrences_count")

        self.assertEqual(counts["Coccinella septempunctata"], 0)

    def test_the_score_threshold_can_be_skipped_by_the_caller(self):
        self.create_occurrence(self.septempunctata, score=0.4)

        counts = self.annotated(self.observation_counts(apply_default_score_filter=False), "occurrences_count")

        self.assertEqual(counts["Coccinella septempunctata"], 1)

    def test_apply_defaults_false_in_the_request_bypasses_the_threshold(self):
        self.create_occurrence(self.septempunctata, score=0.4)

        counts = self.annotated(
            self.observation_counts(request=self.request(apply_defaults="false")), "occurrences_count"
        )

        self.assertEqual(counts["Coccinella septempunctata"], 1)

    def test_occurrences_of_an_excluded_taxon_are_not_counted(self):
        """Excluding the genus also excludes its species, via determination__parents_json."""
        self.project.default_filters_exclude_taxa.add(self.genus)
        self.create_occurrence(self.septempunctata)

        counts = self.annotated(self.observation_counts(), "occurrences_count")

        self.assertEqual(counts["Coccinella septempunctata"], 0)

    def test_occurrences_outside_the_included_taxa_are_not_counted(self):
        other_order = create_taxon("Hymenoptera", TaxonRank.ORDER)
        self.project.default_filters_include_taxa.add(other_order)
        self.create_occurrence(self.septempunctata)

        counts = self.annotated(self.observation_counts(), "occurrences_count")

        self.assertEqual(counts["Coccinella septempunctata"], 0)

    def test_the_default_taxa_filter_can_be_skipped_by_the_caller(self):
        """The taxon detail view skips it so an excluded taxon can still be opened."""
        self.project.default_filters_exclude_taxa.add(self.genus)
        self.create_occurrence(self.septempunctata)

        counts = self.annotated(self.observation_counts(apply_default_taxa_filter=False), "occurrences_count")

        self.assertEqual(counts["Coccinella septempunctata"], 1)

    def test_occurrences_of_another_project_are_not_counted(self):
        other_project = Project.objects.create(name=f"Other QuerySet Project {uuid.uuid4().hex[:8]}")
        self.create_occurrence(self.septempunctata, project=other_project)

        counts = self.annotated(self.observation_counts(), "occurrences_count")

        self.assertEqual(counts["Coccinella septempunctata"], 0)

    def aggregated_counts(self, collection=None, **kwargs) -> models.QuerySet:
        return Taxon.objects.with_observation_counts_aggregated(
            self.project,
            kwargs.pop("request", None),
            relation_occurrence_filters=self.occurrence_filters(accessor="occurrences", collection=collection),
            **kwargs,
        )

    def test_the_aggregated_shape_agrees_with_the_subquery_shape(self):
        self.create_occurrence(
            self.septempunctata, score=0.6, detection_timestamps=(datetime.datetime(2023, 6, 1, 21, 0),)
        )
        self.create_occurrence(
            self.septempunctata, score=0.8, detection_timestamps=(datetime.datetime(2023, 6, 1, 23, 30),)
        )
        self.create_occurrence(self.magnifica, score=0.4)

        fields = ["occurrences_count", "best_determination_score", "last_detected"]
        subqueries = self.observation_counts()
        aggregated = self.aggregated_counts()

        for field in fields:
            with self.subTest(field=field):
                self.assertEqual(self.annotated(aggregated, field), self.annotated(subqueries, field))

    def test_the_detections_join_does_not_inflate_the_aggregated_count(self):
        """A collection filter joins detections, so one occurrence yields a row per detection."""
        collection = self.collection_of_the_capture()
        self.create_occurrence(
            self.septempunctata,
            detection_timestamps=(datetime.datetime(2023, 6, 1, 21, 0), datetime.datetime(2023, 6, 1, 22, 0)),
        )

        counts = self.annotated(self.aggregated_counts(collection=collection), "occurrences_count")

        self.assertEqual(counts["Coccinella septempunctata"], 1)

    def test_the_aggregated_shape_leaves_the_default_taxa_filter_to_the_row_filter(self):
        """Deliberate: the parents_json join inside the aggregate cost 0.3s -> 182s. See the docstring."""
        self.project.default_filters_exclude_taxa.add(self.genus)
        self.create_occurrence(self.septempunctata)

        counts = self.annotated(self.aggregated_counts(), "occurrences_count")

        self.assertEqual(counts["Coccinella septempunctata"], 1)
        # The exclusion is enforced a row at a time instead.
        self.assertNotIn(
            self.septempunctata,
            Taxon.objects.filter_by_project_default_taxa(self.project),
        )


class TaxonObservedInProjectTestCase(TaxonQuerySetTestCase):
    """``observed_in_project_subqueries`` narrows the list to taxa actually determined."""

    def observed(self, **kwargs) -> list[str]:
        queryset = Taxon.objects.observed_in_project_subqueries(
            self.project, kwargs.pop("request", None), occurrence_filters=self.occurrence_filters(), **kwargs
        )
        return sorted(taxon.name for taxon in queryset)

    def test_only_taxa_with_a_matching_occurrence_are_kept(self):
        self.create_occurrence(self.septempunctata)

        self.assertEqual(self.observed(), ["Coccinella septempunctata"])

    def test_ancestors_of_an_observed_taxon_are_not_kept(self):
        """Membership matches the exact determination, like the value columns."""
        self.create_occurrence(self.septempunctata)

        self.assertNotIn("Coccinella", self.observed())

    def test_taxa_whose_occurrences_fall_below_the_threshold_are_dropped(self):
        self.create_occurrence(self.septempunctata, score=0.4)

        self.assertEqual(self.observed(), [])
        self.assertEqual(self.observed(apply_default_score_filter=False), ["Coccinella septempunctata"])

    def test_excluded_taxa_are_dropped(self):
        self.project.default_filters_exclude_taxa.add(self.genus)
        self.create_occurrence(self.septempunctata)

        self.assertEqual(self.observed(), [])
        self.assertEqual(self.observed(apply_default_taxa_filter=False), ["Coccinella septempunctata"])


class TaxonVerificationCountTestCase(TaxonQuerySetTestCase):
    """``verified_count`` is the one column that rolls up to ancestors."""

    def verified_counts(self, **kwargs) -> dict[str, typing.Any]:
        queryset = Taxon.objects.with_verification_counts(
            self.project, kwargs.pop("request", None), occurrence_filters=self.occurrence_filters(), **kwargs
        )
        return self.annotated(queryset, "verified_count")

    def test_verifying_a_species_also_counts_towards_every_ancestor(self):
        self.verify(self.create_occurrence(self.septempunctata))

        self.assertEqual(
            self.verified_counts(),
            {
                "Coleoptera": 1,
                "Coccinellidae": 1,
                "Coccinella": 1,
                "Coccinella magnifica": 0,
                "Coccinella septempunctata": 1,
            },
        )

    def test_an_unverified_occurrence_does_not_count(self):
        self.create_occurrence(self.septempunctata)

        self.assertEqual(self.verified_counts()["Coccinella septempunctata"], 0)

    def test_a_withdrawn_identification_does_not_count(self):
        self.verify(self.create_occurrence(self.septempunctata), withdrawn=True)

        self.assertEqual(self.verified_counts()["Coccinella septempunctata"], 0)

    def test_an_empty_rollup_annotates_zero_for_every_row(self):
        """The CASE degenerates to a constant when no occurrence is verified."""
        self.assertEqual(set(self.verified_counts(verified_counts={}).values()), {0})

    def test_a_precomputed_rollup_is_used_as_given(self):
        """The view computes the rollup once and passes it to both consumers."""
        counts = self.verified_counts(verified_counts={self.magnifica.pk: 7})

        self.assertEqual(counts["Coccinella magnifica"], 7)
        self.assertEqual(counts["Coccinella septempunctata"], 0)

    def test_verified_true_keeps_only_taxa_with_a_verified_occurrence(self):
        self.verify(self.create_occurrence(self.septempunctata))
        self.create_occurrence(self.magnifica)

        counts = self.verified_counts(verified=True)

        self.assertEqual(sorted(counts), ["Coccinella", "Coccinella septempunctata", "Coccinellidae", "Coleoptera"])

    def test_verified_false_excludes_them(self):
        self.verify(self.create_occurrence(self.septempunctata))
        self.create_occurrence(self.magnifica)

        counts = self.verified_counts(verified=False)

        self.assertEqual(sorted(counts), ["Coccinella magnifica"])

    def test_the_detections_join_does_not_inflate_the_rollup(self):
        """.distinct() on the occurrence pk absorbs the per-detection fan-out."""
        collection = self.collection_of_the_capture()
        occurrence = self.create_occurrence(
            self.septempunctata,
            detection_timestamps=(datetime.datetime(2023, 6, 1, 21, 0), datetime.datetime(2023, 6, 1, 22, 0)),
        )
        self.verify(occurrence)

        counts = verified_taxon_counts(
            self.project, None, occurrence_filters=self.occurrence_filters(collection=collection)
        )

        self.assertEqual(counts[self.septempunctata.pk], 1)

    def test_the_rollup_respects_the_score_threshold(self):
        occurrence = self.create_occurrence(self.septempunctata)
        self.verify(occurrence)
        # Identification.save() raises the determination score to 1.0, so the low score has
        # to be written afterwards, bypassing save().
        Occurrence.objects.filter(pk=occurrence.pk).update(determination_score=0.4)

        self.assertEqual(self.verified_counts()["Coccinella septempunctata"], 0)
        self.assertEqual(
            self.verified_counts(apply_default_score_filter=False)["Coccinella septempunctata"],
            1,
        )


class TaxonExampleOccurrenceTestCase(TaxonQuerySetTestCase):
    """The Example / Last-seen / Best-score deep links (#1320)."""

    def setUp(self) -> None:
        super().setUp()
        self.best = self.create_occurrence(
            self.septempunctata, score=0.9, detection_timestamps=(datetime.datetime(2023, 6, 1, 21, 0),)
        )
        self.latest = self.create_occurrence(
            self.septempunctata, score=0.6, detection_timestamps=(datetime.datetime(2023, 6, 2, 1, 0),)
        )

    def example_ids(self, field: str, *, verified_taxon_ids: set[int] = set(), **kwargs) -> typing.Any:
        queryset = Taxon.objects.with_example_occurrence_ids(
            self.project,
            kwargs.pop("request", None),
            occurrence_filters=self.occurrence_filters(),
            verified_taxon_ids=verified_taxon_ids,
            **kwargs,
        )
        return self.annotated(queryset, field)["Coccinella septempunctata"]

    def test_the_best_scoring_occurrence_is_annotated(self):
        self.assertEqual(self.example_ids("best_scoring_occurrence_id"), self.best.pk)

    def test_the_last_detected_occurrence_is_annotated(self):
        self.assertEqual(self.example_ids("last_detected_occurrence_id"), self.latest.pk)

    def test_a_verified_taxon_is_shown_its_latest_occurrence(self):
        """ "Is this taxon still showing up?" rather than "what should I confirm?\" """
        example = self.example_ids("example_occurrence_id", verified_taxon_ids={self.septempunctata.pk})

        self.assertEqual(example, self.latest.pk)

    def test_an_unverified_taxon_is_shown_its_best_unverified_occurrence(self):
        self.verify(self.best)

        example = self.example_ids("example_occurrence_id")

        self.assertEqual(example, self.latest.pk, "The already-verified best-scoring occurrence should be skipped")

    def test_a_null_score_never_wins_the_best_score_ordering(self):
        """nulls_last: without it a NULL score sorts first under DESC."""
        self.create_occurrence(self.septempunctata, score=None)

        best = self.example_ids("best_scoring_occurrence_id", apply_default_score_filter=False)

        self.assertEqual(best, self.best.pk)

    def test_taxa_without_their_own_occurrences_are_annotated_null(self):
        queryset = Taxon.objects.with_example_occurrence_ids(
            self.project,
            None,
            occurrence_filters=self.occurrence_filters(),
            verified_taxon_ids=set(),
        )

        self.assertIsNone(self.annotated(queryset, "example_occurrence_id")["Coccinella"])


class TaxonDefaultTaxaFilterTestCase(TestCase):
    """``filter_by_project_default_taxa`` filters the Taxon rows themselves, not occurrences."""

    def setUp(self) -> None:
        self.project = Project.objects.create(name=f"Default Taxa Project {uuid.uuid4().hex[:8]}")
        self.order = create_taxon("Coleoptera", TaxonRank.ORDER)
        self.family = create_taxon("Coccinellidae", TaxonRank.FAMILY, parent=self.order)
        self.genus = create_taxon("Coccinella", TaxonRank.GENUS, parent=self.family)
        self.other_order = create_taxon("Hymenoptera", TaxonRank.ORDER)
        self.our_taxa = [self.order, self.family, self.genus, self.other_order]
        return super().setUp()

    def filtered(self, project: Project | None = None, request: Request | None = None) -> list[str]:
        """Names kept by the filter, limited to our own taxa: the method filters globally."""
        queryset = Taxon.objects.filter_by_project_default_taxa(project, request)
        ours = queryset.filter(pk__in=[taxon.pk for taxon in self.our_taxa])
        return sorted(ours.values_list("name", flat=True))

    def test_an_included_taxon_keeps_itself_and_its_descendants(self):
        self.project.default_filters_include_taxa.add(self.order)

        self.assertEqual(self.filtered(self.project), ["Coccinella", "Coccinellidae", "Coleoptera"])

    def test_an_excluded_taxon_removes_itself_and_its_descendants(self):
        self.project.default_filters_exclude_taxa.add(self.family)

        self.assertEqual(self.filtered(self.project), ["Coleoptera", "Hymenoptera"])

    def test_without_a_project_nothing_is_filtered(self):
        self.project.default_filters_exclude_taxa.add(self.family)

        self.assertIn("Coccinellidae", self.filtered())

    def test_apply_defaults_false_bypasses_the_filter(self):
        """Unlike the Occurrence queryset, this one checks the flag itself."""
        self.project.default_filters_exclude_taxa.add(self.family)
        request = Request(APIRequestFactory().get("/", {"apply_defaults": "false"}))

        self.assertIn("Coccinellidae", self.filtered(self.project, request))


class TaxonVisibilityTestCase(TestCase):
    """``visible_for_user``: a draft project's taxa must not leak to non-members."""

    def setUp(self) -> None:
        short_id = uuid.uuid4().hex[:8]
        self.owner = User.objects.create_user(email=f"owner-{short_id}@insectai.org", password="password123")
        self.member = User.objects.create_user(email=f"member-{short_id}@insectai.org", password="password123")
        self.outsider = User.objects.create_user(email=f"outsider-{short_id}@insectai.org", password="password123")
        self.superuser = User.objects.create_user(
            email=f"super-{short_id}@insectai.org", password="password123", is_superuser=True
        )
        self.public_project = Project.objects.create(name=f"Public Project {short_id}", draft=False)
        self.draft_project = Project.objects.create(name=f"Draft Project {short_id}", draft=True, owner=self.owner)
        self.draft_project.members.add(self.member)

        self.public_taxon = create_taxon("Hymenoptera", TaxonRank.ORDER)
        self.public_taxon.projects.add(self.public_project)
        self.draft_taxon = create_taxon("Coleoptera", TaxonRank.ORDER)
        self.draft_taxon.projects.add(self.draft_project)
        self.unlinked_taxon = create_taxon("Zygaena", TaxonRank.GENUS)
        self.our_taxa = [self.public_taxon, self.draft_taxon, self.unlinked_taxon]
        return super().setUp()

    def visible(self, user) -> list[str]:
        """Visible names, limited to our own taxa: other projects' taxa are visible too."""
        ours = Taxon.objects.visible_for_user(user).filter(pk__in=[taxon.pk for taxon in self.our_taxa])
        return sorted(ours.values_list("name", flat=True))

    def test_anonymous_users_see_only_taxa_of_published_projects(self):
        self.assertEqual(self.visible(AnonymousUser()), ["Hymenoptera"])

    def test_a_non_member_does_not_see_draft_project_taxa(self):
        self.assertEqual(self.visible(self.outsider), ["Hymenoptera"])

    def test_the_owner_and_members_see_draft_project_taxa(self):
        for user, label in [(self.owner, "owner"), (self.member, "member")]:
            with self.subTest(user=label):
                self.assertEqual(self.visible(user), ["Coleoptera", "Hymenoptera"])

    def test_a_superuser_sees_every_taxon_including_unlinked_ones(self):
        self.assertEqual(self.visible(self.superuser), ["Coleoptera", "Hymenoptera", "Zygaena"])

    def test_a_taxon_is_visible_through_an_occurrence_in_a_published_project(self):
        """The second branch: taxa reachable by determination, without a projects row."""
        Occurrence.objects.create(project=self.public_project, determination=self.unlinked_taxon)

        self.assertIn("Zygaena", self.visible(self.outsider))

    def test_an_occurrence_in_a_draft_project_does_not_expose_its_taxon(self):
        Occurrence.objects.create(project=self.draft_project, determination=self.unlinked_taxon)

        self.assertNotIn("Zygaena", self.visible(self.outsider))
