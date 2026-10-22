import importlib

from django.apps import apps
from django.test import TestCase
from django.urls import reverse
from guardian.models import GroupObjectPermission

from ami.base.model_references import resolve_model_references
from ami.main.models import Occurrence, OccurrenceSet, Project, Taxon
from ami.main.models_future.enums import TaxonRank
from ami.main.models_future.saved_set import SetRefused
from ami.tests.fixtures.main import (
    create_captures,
    create_occurrences,
    create_taxa,
    group_images_into_events,
    setup_test_project,
)
from ami.users.models import User
from ami.users.roles import BasicMember, Identifier, MLDataManager, ProjectManager, Researcher


class OccurrenceSetTestCase(TestCase):
    """A project with seven occurrences, and a second project with two occurrences."""

    @classmethod
    def setUpTestData(cls):
        cls.project, cls.deployment = setup_test_project(reuse=False)
        create_captures(deployment=cls.deployment, num_nights=1, images_per_night=4, interval_minutes=1)
        group_images_into_events(cls.deployment)
        create_taxa(cls.project)
        taxon = Taxon.objects.filter(projects=cls.project, rank=TaxonRank.SPECIES.name).order_by("name").first()
        create_occurrences(deployment=cls.deployment, num=7, taxon=taxon)
        cls.occurrence_ids = sorted(cls.project.occurrences.values_list("pk", flat=True))

        cls.other_project, other_deployment = setup_test_project(reuse=False)
        create_captures(deployment=other_deployment, num_nights=1, images_per_night=2, interval_minutes=1)
        group_images_into_events(other_deployment)
        create_occurrences(deployment=other_deployment, num=2, taxon=taxon)
        cls.other_occurrence_ids = sorted(cls.other_project.occurrences.values_list("pk", flat=True))

        cls.ml_data_manager = cls.create_member("occsets-mldm@insectai.org", MLDataManager)
        cls.project_manager = cls.create_member("occsets-pm@insectai.org", ProjectManager)
        cls.basic_member = cls.create_member("occsets-basic@insectai.org", BasicMember)
        cls.non_member = User.objects.create_user(email="occsets-outsider@insectai.org")

    @classmethod
    def create_member(cls, email: str, role) -> User:
        user = User.objects.create_user(email=email)
        cls.project.members.add(user)
        role.assign_user(user, cls.project)
        return user

    def create_set(self, **fields) -> OccurrenceSet:
        fields.setdefault("name", "Flagged")
        fields.setdefault("project", self.project)
        return OccurrenceSet.objects.create(**fields)

    def create_frozen_set(self) -> OccurrenceSet:
        occurrence_set = self.create_set()
        occurrence_set.occurrences.add(*self.occurrence_ids[:2])
        occurrence_set.freeze(self.ml_data_manager)
        return occurrence_set

    def member_ids(self, occurrence_set: OccurrenceSet) -> list[int]:
        return sorted(occurrence_set.occurrences.values_list("pk", flat=True))


class TestOccurrenceSetLifecycle(OccurrenceSetTestCase):
    def test_new_set_is_manual_with_no_arguments_and_not_frozen(self):
        occurrence_set = self.create_set()
        self.assertEqual((occurrence_set.method, occurrence_set.kwargs), ("manual", {}))
        self.assertEqual(
            (occurrence_set.populated_at, occurrence_set.frozen_at, occurrence_set.copied_from), (None,) * 3
        )

    def test_add_and_remove_members(self):
        occurrence_set = self.create_set()
        occurrence_set.add_occurrences(self.occurrence_ids[:3])
        occurrence_set.add_occurrences(self.occurrence_ids[2:4])
        occurrence_set.remove_occurrences([self.occurrence_ids[0], self.other_occurrence_ids[0]])
        self.assertEqual(self.member_ids(occurrence_set), self.occurrence_ids[1:4])

    def test_freeze_records_when_and_by_whom_and_cannot_repeat(self):
        occurrence_set = self.create_set()
        occurrence_set.freeze(self.ml_data_manager)
        occurrence_set.refresh_from_db()
        self.assertIsNotNone(occurrence_set.frozen_at)
        self.assertEqual(occurrence_set.frozen_by, self.ml_data_manager)
        with self.assertRaises(SetRefused):
            occurrence_set.freeze(self.project_manager)

    def test_frozen_set_members_cannot_change(self):
        occurrence_set = self.create_frozen_set()
        for change in (occurrence_set.add_occurrences, occurrence_set.remove_occurrences):
            with self.subTest(change=change.__name__), self.assertRaises(SetRefused):
                change(self.occurrence_ids[:3])
        self.assertEqual(self.member_ids(occurrence_set), self.occurrence_ids[:2])

    def test_frozen_state_is_read_again_before_an_edit(self):
        # Another request froze the set after this instance was loaded.
        occurrence_set = self.create_set()
        OccurrenceSet.objects.get(pk=occurrence_set.pk).freeze(self.project_manager)
        with self.assertRaises(SetRefused):
            occurrence_set.add_occurrences(self.occurrence_ids[:1])
        self.assertEqual(self.member_ids(occurrence_set), [])

    def test_copy_has_the_same_fields_and_members_and_is_not_frozen(self):
        original = self.create_frozen_set()
        original.description = "Hard identifications"
        original.save()

        copy = original.copy()
        copy.refresh_from_db()
        self.assertEqual(copy.name, "Copy of Flagged")
        self.assertEqual(
            (copy.project_id, copy.description, copy.method, copy.kwargs, copy.copied_from_id),
            (original.project_id, original.description, original.method, original.kwargs, original.pk),
        )
        self.assertFalse(copy.is_frozen)
        self.assertEqual(self.member_ids(copy), self.member_ids(original))
        # The copy can change; the frozen original does not.
        copy.add_occurrences(self.occurrence_ids)
        self.assertEqual(self.member_ids(original), self.occurrence_ids[:2])
        self.assertEqual(original.copy(name="Benchmark v2").name, "Benchmark v2")


class TestOccurrenceSetModel(OccurrenceSetTestCase):
    def test_draft_project_sets_are_visible_to_members_only(self):
        Project.objects.filter(pk=self.project.pk).update(draft=True)
        occurrence_set = self.create_set()
        visible = OccurrenceSet.objects.visible_for_user
        self.assertNotIn(occurrence_set, visible(self.non_member))
        self.assertIn(occurrence_set, visible(self.basic_member))

    def test_occurrences_count_is_not_multiplied_by_project_members(self):
        occurrence_set = self.create_set()
        occurrence_set.occurrences.add(*self.occurrence_ids[:3])
        counted = OccurrenceSet.objects.visible_for_user(self.basic_member).with_occurrences_count()
        self.assertEqual(counted.get(pk=occurrence_set.pk).occurrences_count, 3)

    def test_deleting_a_project_deletes_its_sets(self):
        occurrence_set = self.create_set(project=self.other_project)
        self.other_project.delete()
        self.assertFalse(OccurrenceSet.objects.filter(pk=occurrence_set.pk).exists())

    def test_deleting_an_occurrence_removes_it_from_the_set(self):
        occurrence_set = self.create_set()
        occurrence_set.occurrences.add(*self.occurrence_ids[:2])
        Occurrence.objects.filter(pk=self.occurrence_ids[0]).delete()
        self.assertEqual(self.member_ids(occurrence_set), self.occurrence_ids[1:2])

    def test_permissions_are_checked_against_the_set_project(self):
        occurrence_set = self.create_set()
        self.assertEqual(occurrence_set.get_project(), self.project)
        for action in ("update", "add", "remove", "freeze", "copy"):
            with self.subTest(action=action):
                self.assertTrue(occurrence_set.check_permission(self.ml_data_manager, action))
                self.assertFalse(occurrence_set.check_permission(self.basic_member, action))

    def test_jobs_and_results_can_refer_to_a_set(self):
        occurrence_set = self.create_set(name="Favourites")
        ref = resolve_model_references([("occurrence_set", occurrence_set.pk)])[("occurrence_set", occurrence_set.pk)]
        self.assertEqual(ref.name, "Favourites")

    def test_str_does_not_query(self):
        occurrence_set = self.create_set()
        with self.assertNumQueries(0):
            str(occurrence_set)

    def test_admin_changelist_shows_member_counts(self):
        self.create_set().occurrences.add(*self.occurrence_ids[:2])
        self.create_frozen_set()
        self.client.force_login(User.objects.create_superuser(email="occsets-admin@insectai.org", password="x"))
        response = self.client.get(reverse("admin:main_occurrenceset_changelist"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual([row.occurrences_count for row in response.context["cl"].result_list], [2, 2])


class TestOccurrenceSetPermissions(OccurrenceSetTestCase):
    def test_roles_that_curate_occurrence_sets(self):
        curating = {
            Project.Permissions.CREATE_OCCURRENCE_SET,
            Project.Permissions.UPDATE_OCCURRENCE_SET,
            Project.Permissions.DELETE_OCCURRENCE_SET,
        }
        for role in (MLDataManager, ProjectManager):
            self.assertLessEqual(curating, role.permissions, role)
        for role in (BasicMember, Researcher, Identifier):
            self.assertFalse(curating & role.permissions, role)

    def test_migration_grants_the_permissions_to_existing_role_groups(self):
        migration = importlib.import_module("ami.main.migrations.0101_grant_occurrence_set_permissions")
        GroupObjectPermission.objects.filter(
            object_pk=str(self.project.pk), permission__codename__in=migration.PERMISSIONS
        ).delete()
        self.assertFalse(User.objects.get(pk=self.ml_data_manager.pk).has_perm("create_occurrenceset", self.project))

        migration.grant_occurrence_set_permissions(apps, None)

        for user in (self.ml_data_manager, self.project_manager):
            user = User.objects.get(pk=user.pk)  # Guardian caches permissions on the user object.
            for codename in migration.PERMISSIONS:
                self.assertTrue(user.has_perm(codename, self.project), (user, codename))
        self.assertFalse(User.objects.get(pk=self.basic_member.pk).has_perm("create_occurrenceset", self.project))
