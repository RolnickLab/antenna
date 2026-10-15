from django.contrib.auth.models import Group, Permission
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from guardian.shortcuts import assign_perm, get_perms

from ami.main.models import Project
from ami.tests.fixtures.queries import no_query_cache
from ami.users.roles import Role, create_roles_for_project


class TestCreateRolesForProject(TestCase):
    """Each role's group holds exactly the role's permissions, both on the project and as model permissions."""

    def setUp(self):
        self.project = Project.objects.create(name="Roles Project")

    def assert_roles_match_definitions(self):
        for role in Role.__subclasses__():
            with self.subTest(role=role.__name__):
                group = Group.objects.get(name=role.get_group_name(self.project))
                self.assertEqual(set(get_perms(group, self.project)), set(role.permissions))
                self.assertEqual(set(group.permissions.values_list("codename", flat=True)), set(role.permissions))

    def test_new_project_gets_every_role_with_its_permissions(self):
        self.assert_roles_match_definitions()

    def test_rerun_removes_permissions_a_role_no_longer_has(self):
        from ami.users.roles import BasicMember

        group = Group.objects.get(name=BasicMember.get_group_name(self.project))
        stray = Project.Permissions.DELETE_PROJECT
        self.assertNotIn(stray, BasicMember.permissions)
        assign_perm(stray, group, self.project)
        group.permissions.add(Permission.objects.get(codename=stray))

        create_roles_for_project(self.project)

        self.assertNotIn(stray, get_perms(group, self.project))
        self.assert_roles_match_definitions()

    def test_rerun_does_not_touch_other_projects(self):
        other = Project.objects.create(name="Other Roles Project")
        create_roles_for_project(self.project)
        for role in Role.__subclasses__():
            group = Group.objects.get(name=role.get_group_name(other))
            self.assertEqual(set(get_perms(group, other)), set(role.permissions))

    def test_rerun_with_unchanged_roles_writes_nothing(self):
        # Runs for every project after each migration; an unchanged project should only be read.
        with CaptureQueriesContext(connection) as queries:
            create_roles_for_project(self.project)
        writes = [q["sql"] for q in queries if q["sql"].split()[0] in ("INSERT", "UPDATE", "DELETE")]
        self.assertEqual(writes, [])

    def test_query_count_does_not_grow_with_the_number_of_permissions(self):
        # Five roles hold about a hundred permissions; one query per permission took ~1,000 queries per project.
        with no_query_cache(), self.assertNumQueries(12):
            create_roles_for_project(self.project)
