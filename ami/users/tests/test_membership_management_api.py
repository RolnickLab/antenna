from guardian.shortcuts import assign_perm
from rest_framework.test import APITestCase

from ami.main.models import Project, UserProjectMembership
from ami.tests.fixtures.main import setup_test_project
from ami.users.models import User
from ami.users.roles import BasicMember, ProjectManager, Role


class TestUserProjectMembershipAPI(APITestCase):
    def setUp(self):
        # Create project
        self.project, _ = setup_test_project()

        # Users
        self.superuser = User.objects.create_superuser(email="super@insectai.org", password="x")
        self.user1 = User.objects.create_user(email="user1@insectai.org")
        self.user2 = User.objects.create_user(email="user2@insectai.org")
        self.other = User.objects.create_user(email="other@insectai.org")

        # Endpoints
        self.roles_url = "/api/v2/users/roles/"
        self.members_url = f"/api/v2/projects/{self.project.pk}/members/"

    def create_membership(self, user=None, role_cls=None):
        """
        Create a membership for a user in this project with a role assigned.

        Args:
            user: User to add as member (defaults to self.user1)
            role_cls: Role class to assign (defaults to BasicMember)

        Returns:
            UserProjectMembership instance with role assigned
        """
        if user is None:
            user = self.user1
        if role_cls is None:
            role_cls = BasicMember  # Default role for test memberships

        membership = UserProjectMembership.objects.create(
            project=self.project,
            user=user,
        )
        # Assign role to ensure membership is valid
        role_cls.assign_user(user, self.project)
        return membership

    def auth_super(self):
        self.client.force_authenticate(self.superuser)

    def auth(self, user):
        self.client.force_authenticate(user)

    def test_roles_list_functionality(self):
        self.auth_super()

        resp = self.client.get(self.roles_url)
        self.assertEqual(resp.status_code, 200)

        returned = resp.json()
        expected_roles = Role.get_supported_roles()

        # Check IDs match Role class names
        returned_ids = {r["id"] for r in returned}
        expected_ids = {cls.__name__ for cls in expected_roles}
        self.assertSetEqual(returned_ids, expected_ids)

        # Structure check
        for r in returned:
            self.assertIn("id", r)
            self.assertIn("name", r)
            self.assertIn("description", r)

    def test_list_members_functionality(self):
        self.auth_super()

        self.create_membership(self.user1)

        resp = self.client.get(self.members_url)
        self.assertEqual(resp.status_code, 200)

        body = resp.json()
        self.assertIn("results", body)

        results = body["results"]
        project_members_count = UserProjectMembership.objects.filter(project=self.project).count()
        self.assertEqual(len(results), project_members_count)

    def test_create_membership_functionality(self):
        """
        Ensure that a membership is actually created and belongs to the project+user.
        """
        self.auth_super()

        payload = {
            "email": self.user2.email,
            "role_id": ProjectManager.__name__,
        }

        resp = self.client.post(self.members_url, payload, format="json")
        self.assertEqual(resp.status_code, 201)

        # Retrieve membership using project + user
        membership = UserProjectMembership.objects.get(
            project=self.project,
            user__email=self.user2.email,
        )

        self.assertEqual(membership.user, self.user2)
        self.assertEqual(membership.project, self.project)

    def test_update_membership_functionality(self):
        self.auth_super()

        membership = self.create_membership(self.user1)
        url = f"{self.members_url}{membership.pk}/"

        payload = {"role_id": ProjectManager.__name__}

        resp = self.client.patch(url, payload, format="json")
        self.assertEqual(resp.status_code, 200)

        updated = resp.json()
        self.assertEqual(updated["role"]["id"], ProjectManager.__name__)
        self.assertEqual(updated["role"]["name"], ProjectManager.display_name)
        self.assertEqual(updated["role"]["description"], ProjectManager.description)

        membership = UserProjectMembership.objects.get(
            project=self.project,
            user__email=self.user1.email,
        )

        # Verify role
        assigned_role = Role.get_primary_role(self.project, membership.user)
        self.assertEqual(assigned_role.__name__, ProjectManager.__name__)

    def test_delete_membership_functionality(self):
        self.auth_super()

        membership = self.create_membership(self.user1)
        url = f"{self.members_url}{membership.pk}/"

        resp = self.client.delete(url)
        self.assertEqual(resp.status_code, 204)

        self.assertFalse(
            UserProjectMembership.objects.filter(
                project=self.project,
                user__email=self.user1.email,
            ).exists()
        )

        self.assertNotIn(self.user1, self.project.members.all())

    def test_list_requires_view_permission(self):
        self.create_membership(self.user1)
        self.auth(self.other)

        resp = self.client.get(self.members_url)
        self.assertEqual(resp.status_code, 403)

        assign_perm(Project.Permissions.VIEW_USER_PROJECT_MEMBERSHIP, self.other, self.project)
        resp = self.client.get(self.members_url)
        self.assertEqual(resp.status_code, 200)

    def test_create_requires_create_permission(self):
        self.auth(self.other)

        payload = {"email": self.user2.email, "role_id": BasicMember.__name__}

        resp = self.client.post(self.members_url, payload)
        self.assertEqual(resp.status_code, 403)

        assign_perm(Project.Permissions.CREATE_USER_PROJECT_MEMBERSHIP, self.other, self.project)
        resp = self.client.post(self.members_url, payload)
        self.assertEqual(resp.status_code, 201)

    def test_update_requires_update_permission(self):
        membership = self.create_membership(self.user1)
        url = f"{self.members_url}{membership.pk}/"

        self.auth(self.other)

        resp = self.client.patch(url, {"role_id": ProjectManager.__name__})
        self.assertEqual(resp.status_code, 403)

        assign_perm(Project.Permissions.UPDATE_USER_PROJECT_MEMBERSHIP, self.other, self.project)
        resp = self.client.patch(url, {"role_id": ProjectManager.__name__})
        self.assertEqual(resp.status_code, 200)

    def test_delete_requires_delete_permission(self):
        membership = self.create_membership(self.user1)
        url = f"{self.members_url}{membership.pk}/"

        self.auth(self.other)

        resp = self.client.delete(url)
        self.assertEqual(resp.status_code, 403)

        assign_perm(Project.Permissions.DELETE_USER_PROJECT_MEMBERSHIP, self.other, self.project)
        resp = self.client.delete(url)
        self.assertEqual(resp.status_code, 204)

    def test_user_can_delete_their_own_membership(self):
        membership = self.create_membership(self.user1)
        url = f"{self.members_url}{membership.pk}/"

        self.auth(self.user1)

        resp = self.client.delete(url)
        self.assertEqual(resp.status_code, 204)

        self.assertFalse(
            UserProjectMembership.objects.filter(
                project=self.project,
                user__email=self.user1.email,
            ).exists()
        )

    # Validation error tests

    def test_create_membership_with_invalid_role_id(self):
        """POST with non-existent role_id should return 400."""
        self.auth_super()
        payload = {"email": self.user2.email, "role_id": "NonExistentRole"}
        resp = self.client.post(self.members_url, payload, format="json")
        self.assertEqual(resp.status_code, 400)

    def test_create_membership_with_nonexistent_email(self):
        """POST with unknown email should return 400."""
        self.auth_super()
        payload = {"email": "nonexistent@example.com", "role_id": BasicMember.__name__}
        resp = self.client.post(self.members_url, payload, format="json")
        self.assertEqual(resp.status_code, 400)

    def test_create_duplicate_membership(self):
        """POST for user already in project should return 400."""
        self.auth_super()
        self.create_membership(self.user1)
        payload = {"email": self.user1.email, "role_id": BasicMember.__name__}
        resp = self.client.post(self.members_url, payload, format="json")
        self.assertEqual(resp.status_code, 400)

    def test_create_membership_missing_email(self):
        """POST without email should return 400."""
        self.auth_super()
        payload = {"role_id": BasicMember.__name__}
        resp = self.client.post(self.members_url, payload, format="json")
        self.assertEqual(resp.status_code, 400)

    def test_create_membership_missing_role_id(self):
        """POST without role_id should return 400."""
        self.auth_super()
        payload = {"email": self.user2.email}
        resp = self.client.post(self.members_url, payload, format="json")
        self.assertEqual(resp.status_code, 400)
