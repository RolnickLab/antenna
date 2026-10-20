from django.contrib.auth.models import AnonymousUser
from django.test import TestCase
from django.urls import reverse

from ami.main.models import Occurrence, OccurrenceSet, Project
from ami.users.models import User
from ami.users.roles import BasicMember, MLDataManager, ProjectManager


def make_occurrences(project: Project, count: int) -> list[Occurrence]:
    # Built directly: the capture fixtures read the clock and storage, which makes them
    # non-deterministic, and a set only needs occurrence rows to point at.
    return Occurrence.objects.bulk_create([Occurrence(project=project) for _ in range(count)])


def make_set(name: str, projects: list[Project], occurrences: list[Occurrence] | None = None) -> OccurrenceSet:
    occurrence_set = OccurrenceSet.objects.create(name=name)
    occurrence_set.projects.set(projects)
    occurrence_set.occurrences.set(occurrences or [])
    return occurrence_set


class OccurrenceSetQuerySetTestCase(TestCase):
    def setUp(self) -> None:
        self.owner = User.objects.create_user(email="owner@example.com")
        self.member = User.objects.create_user(email="member@example.com")
        self.outsider = User.objects.create_user(email="outsider@example.com")
        self.superuser = User.objects.create_superuser(email="admin@example.com", password="x")

        self.project = Project.objects.create(name="Open project", owner=self.owner)
        self.other_project = Project.objects.create(name="Other project", owner=self.owner)
        self.draft_project = Project.objects.create(name="Draft project", owner=self.owner, draft=True)
        BasicMember.assign_user(self.member, self.draft_project)

        self.own_set = make_set("own", [self.project])
        self.other_set = make_set("other", [self.other_project])
        self.draft_set = make_set("draft", [self.draft_project])
        self.public_set = make_set("public", [])

    def test_for_project_includes_own_and_public_sets_only(self):
        names = list(OccurrenceSet.objects.for_project(self.project).values_list("name", flat=True))
        self.assertEqual(sorted(names), ["own", "public"])

    def test_for_project_lists_a_shared_set_once(self):
        self.own_set.projects.add(self.other_project)
        names = list(OccurrenceSet.objects.for_project(self.project).values_list("name", flat=True))
        self.assertEqual(sorted(names), ["own", "public"])

    def test_visible_for_user_hides_draft_project_sets_from_non_members(self):
        for user in (AnonymousUser(), self.outsider):
            with self.subTest(user=user):
                visible = set(OccurrenceSet.objects.visible_for_user(user).values_list("name", flat=True))
                self.assertEqual(visible, {"own", "other", "public"})

    def test_visible_for_user_shows_draft_project_sets_to_members_and_superusers(self):
        for user in (self.member, self.owner, self.superuser):
            with self.subTest(user=user):
                visible = set(OccurrenceSet.objects.visible_for_user(user).values_list("name", flat=True))
                self.assertEqual(visible, {"own", "other", "draft", "public"})

    def test_occurrences_count_is_not_multiplied_by_shared_projects(self):
        self.own_set.occurrences.set(make_occurrences(self.project, 3))
        self.own_set.projects.add(self.other_project)
        counts = dict(
            OccurrenceSet.objects.for_project(self.project)
            .with_occurrences_count()
            .values_list("name", "occurrences_count")
        )
        self.assertEqual(counts, {"own": 3, "public": 0})


class OccurrenceSetModelTestCase(TestCase):
    def setUp(self) -> None:
        self.owner = User.objects.create_user(email="owner@example.com")
        self.project = Project.objects.create(name="Project", owner=self.owner)

    def test_public_set_has_no_project_to_check_permissions_against(self):
        public_set = make_set("public", [])
        project_set = make_set("own", [self.project])
        self.assertTrue(public_set.is_public)
        self.assertIsNone(public_set.get_project())
        self.assertFalse(public_set.check_permission(self.owner, "update"))
        self.assertFalse(project_set.is_public)
        self.assertEqual(project_set.get_project(), self.project)

    def test_str_does_not_query(self):
        occurrence_set = make_set("own", [self.project], make_occurrences(self.project, 2))
        with self.assertNumQueries(0):
            str(occurrence_set)

    def test_deleting_an_occurrence_removes_it_from_the_set(self):
        # Pins documented behaviour: membership is not frozen against deletes or merges.
        kept, deleted = make_occurrences(self.project, 2)
        occurrence_set = make_set("own", [self.project], [kept, deleted])
        deleted.delete()
        self.assertEqual(list(occurrence_set.occurrences.values_list("pk", flat=True)), [kept.pk])


class OccurrenceSetPermissionTestCase(TestCase):
    def setUp(self) -> None:
        self.owner = User.objects.create_user(email="owner@example.com")
        self.project = Project.objects.create(name="Project", owner=self.owner)

    def test_curating_roles_can_manage_sets_and_basic_members_cannot(self):
        permissions = [
            Project.Permissions.CREATE_OCCURRENCE_SET,
            Project.Permissions.UPDATE_OCCURRENCE_SET,
            Project.Permissions.DELETE_OCCURRENCE_SET,
        ]
        cases = [(MLDataManager, True), (ProjectManager, True), (BasicMember, False)]
        for role, expected in cases:
            user = User.objects.create_user(email=f"{role.__name__}@example.com")
            role.assign_user(user, self.project)
            for permission in permissions:
                with self.subTest(role=role.__name__, permission=permission):
                    self.assertEqual(user.has_perm(permission, self.project), expected)


class OccurrenceSetAdminTestCase(TestCase):
    def test_changelist_shows_counts_for_project_and_public_sets(self):
        owner = User.objects.create_user(email="owner@example.com")
        project = Project.objects.create(name="Project", owner=owner)
        other_project = Project.objects.create(name="Other project", owner=owner)
        make_set("shared", [project, other_project], make_occurrences(project, 3))
        make_set("public", [])
        superuser = User.objects.create_superuser(email="admin@example.com", password="x")
        self.client.force_login(superuser)

        response = self.client.get(reverse("admin:main_occurrenceset_changelist"))

        self.assertEqual(response.status_code, 200)
        rows = {row.name: row for row in response.context["cl"].result_list}
        self.assertEqual((rows["shared"].project_count, rows["shared"].occurrences_count), (2, 3))
        self.assertEqual((rows["public"].project_count, rows["public"].occurrences_count), (0, 0))
