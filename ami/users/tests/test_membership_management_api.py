from guardian.shortcuts import assign_perm
from rest_framework.test import APITestCase

from ami.main.models import Project, UserProjectMembership
from ami.tests.fixtures.main import setup_test_project
from ami.users.models import User
from ami.users.roles import BasicMember, Identifier, ProjectManager, Researcher, Role, create_roles_for_project


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

    def create_membership(self, user=None):
        """
        Create a membership for a user in this project.
        Used in tests to guarantee isolation.
        """
        if user is None:
            user = self.user1

        membership = UserProjectMembership.objects.create(
            project=self.project,
            user=user,
        )
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
        self.assertEqual(updated["role"], ProjectManager.__name__)

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


class TestMembersApiDraftProjectAccess(APITestCase):
    """
    Verify that members added via the Members API can access draft project details.
    Regression tests for the BasicMember manual-assign fix.
    """

    def setUp(self):
        self.project, _ = setup_test_project()
        self.project.draft = True
        self.project.save()
        create_roles_for_project(self.project)

        self.superuser = User.objects.create_superuser(email="super@insectai.org", password="x")
        self.user_basic = User.objects.create_user(email="basic@insectai.org")
        self.user_identifier = User.objects.create_user(email="identifier@insectai.org")
        self.user_researcher = User.objects.create_user(email="researcher@insectai.org")
        self.user_project_manager = User.objects.create_user(email="manager@insectai.org")
        self.outsider = User.objects.create_user(email="outsider@insectai.org")

        self.members_url = f"/api/v2/projects/{self.project.pk}/members/"
        self.detail_url = f"/api/v2/projects/{self.project.pk}/"

    def _add_member_and_assert_can_access_draft(self, user, role_id: str) -> None:
        """Add user as role via API, then assert they can GET draft project details."""
        self.client.force_authenticate(self.superuser)
        resp = self.client.post(
            self.members_url,
            {"email": user.email, "role_id": role_id},
            format="json",
        )
        self.assertEqual(resp.status_code, 201, f"Failed to add {role_id}: {resp.json()}")
        self.client.force_authenticate(user)
        detail_resp = self.client.get(self.detail_url)
        self.assertEqual(
            detail_resp.status_code,
            200,
            f"{role_id} member should access draft project, got {detail_resp.status_code}",
        )

    def test_member_added_via_api_can_access_draft_project_basic_member(self):
        self._add_member_and_assert_can_access_draft(self.user_basic, BasicMember.__name__)

    def test_member_added_via_api_can_access_draft_project_identifier(self):
        self._add_member_and_assert_can_access_draft(self.user_identifier, Identifier.__name__)

    def test_member_added_via_api_can_access_draft_project_researcher(self):
        self._add_member_and_assert_can_access_draft(self.user_researcher, Researcher.__name__)

    def test_member_added_via_api_can_access_draft_project_manager(self):
        self._add_member_and_assert_can_access_draft(self.user_project_manager, ProjectManager.__name__)

    def test_non_member_cannot_access_draft_project(self):
        self.client.force_authenticate(self.outsider)
        detail_resp = self.client.get(self.detail_url)
        self.assertIn(
            detail_resp.status_code,
            (403, 404),
            "Non-member should not access draft project",
        )
