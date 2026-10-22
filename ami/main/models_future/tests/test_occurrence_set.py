import importlib

from django.apps import apps
from django.db import IntegrityError, transaction
from django.test import TestCase
from guardian.models import GroupObjectPermission

from ami.base.sets.models import SetRefused
from ami.main.models import OccurrenceSet, OccurrenceSetMember, Project, Taxon
from ami.main.models_future.enums import TaxonRank
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
    """A project with five occurrences, and a second project with two occurrences."""

    @classmethod
    def setUpTestData(cls):
        cls.project, deployment = setup_test_project(reuse=False)
        create_captures(deployment=deployment, num_nights=1, images_per_night=3, interval_minutes=1)
        group_images_into_events(deployment)
        create_taxa(cls.project)
        taxon = Taxon.objects.filter(projects=cls.project, rank=TaxonRank.SPECIES.name).order_by("name").first()
        create_occurrences(deployment=deployment, num=5, taxon=taxon)
        cls.occurrence_ids = sorted(cls.project.occurrences.values_list("pk", flat=True))

        cls.other_project, other_deployment = setup_test_project(reuse=False)
        create_captures(deployment=other_deployment, num_nights=1, images_per_night=2, interval_minutes=1)
        group_images_into_events(other_deployment)
        create_occurrences(deployment=other_deployment, num=2, taxon=taxon)
        cls.other_occurrence_ids = sorted(cls.other_project.occurrences.values_list("pk", flat=True))

    def setUp(self):
        self.occurrence_set = OccurrenceSet.objects.create(name="Flagged", project=self.project)

    def member_ids(self) -> list[int]:
        return sorted(self.occurrence_set.occurrences.values_list("pk", flat=True))


class TestOccurrenceSetMembers(OccurrenceSetTestCase):
    def test_new_set_is_manually_curated(self):
        self.assertEqual(self.occurrence_set.method, "curated")

    def test_add_and_remove_members(self):
        self.assertEqual(self.occurrence_set.add_members(self.occurrence_ids[:3]), 3)
        # Adding a member again leaves it once.
        self.assertEqual(self.occurrence_set.add_members(self.occurrence_ids[2:4]), 1)
        self.assertEqual(self.occurrence_set.remove_members([self.occurrence_ids[0]]), 1)
        self.assertEqual(self.member_ids(), self.occurrence_ids[1:4])
        self.assertEqual(self.occurrence_set.member_count(), 3)
        self.assertTrue(
            all(m.added_at for m in OccurrenceSetMember.objects.filter(occurrence_set=self.occurrence_set))
        )

    def test_occurrences_from_another_project_are_refused_and_nothing_is_added(self):
        with self.assertRaises(SetRefused) as refused:
            self.occurrence_set.add_members([self.occurrence_ids[0], self.other_occurrence_ids[0]])
        self.assertIn(str(self.other_occurrence_ids[0]), str(refused.exception))
        self.assertEqual(self.member_ids(), [])

    def test_removing_an_occurrence_that_is_not_a_member_is_ignored(self):
        self.occurrence_set.add_members(self.occurrence_ids[:1])
        self.assertEqual(self.occurrence_set.remove_members(self.occurrence_ids[1:3]), 0)
        self.assertEqual(self.member_ids(), self.occurrence_ids[:1])

    def test_an_occurrence_is_a_member_once(self):
        self.occurrence_set.add_members(self.occurrence_ids[:1])
        with self.assertRaises(IntegrityError), transaction.atomic():
            OccurrenceSetMember.objects.create(
                occurrence_set=self.occurrence_set, occurrence_id=self.occurrence_ids[0]
            )


class TestOccurrenceSetProject(OccurrenceSetTestCase):
    def test_for_project_returns_the_project_sets_only(self):
        OccurrenceSet.objects.create(name="Other", project=self.other_project)
        self.assertEqual(list(OccurrenceSet.objects.for_project(self.project)), [self.occurrence_set])

    def test_project_cannot_change(self):
        occurrence_set = OccurrenceSet.objects.get(pk=self.occurrence_set.pk)
        occurrence_set.project = self.other_project
        with self.assertRaises(SetRefused):
            occurrence_set.save()
        occurrence_set.refresh_from_db()
        self.assertEqual(occurrence_set.project, self.project)
        # Other fields can still change.
        occurrence_set.name = "Favourites"
        occurrence_set.save()


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
        manager = User.objects.create_user(email="occsets-mldm@insectai.org")
        self.project.members.add(manager)
        MLDataManager.assign_user(manager, self.project)
        migration = importlib.import_module("ami.main.migrations.0101_grant_occurrence_set_permissions")
        GroupObjectPermission.objects.filter(
            object_pk=str(self.project.pk), permission__codename__in=migration.PERMISSIONS
        ).delete()
        self.assertFalse(User.objects.get(pk=manager.pk).has_perm("create_occurrenceset", self.project))

        migration.grant_occurrence_set_permissions(apps, None)

        manager = User.objects.get(pk=manager.pk)  # Guardian caches permissions on the user object.
        for codename in migration.PERMISSIONS:
            self.assertTrue(manager.has_perm(codename, self.project), codename)
