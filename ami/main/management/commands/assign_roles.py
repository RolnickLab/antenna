import csv
import logging
import tempfile
from urllib.parse import urlparse

import requests
from django.core.management.base import BaseCommand, CommandError
from guardian.shortcuts import get_user_perms, remove_perm

from ami.main.models import Project
from ami.users.models import User
from ami.users.roles import BasicMember, Identifier, ProjectManager

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Reset permissions, remove staff status from non-superusers, and assign roles.

    Provide a CSV file to assign specific roles (ProjectManager, Identifier).

    **Expected CSV Format:**
        Name,Email,Projects by ID,Projects by name,User type,Comments,New project role
        John Doe,johndoe@insectai.org,"1, 2, 3",
        "Vermont Atlas of Life, Insectarium de Montréal","Internal","Some comment","ProjectManager"

    **Usage:**
        python manage.py assign_roles --source roles.csv
        python manage.py assign_roles --source "https://example.com/roles.csv"
    """

    help = "Assign roles, reset permissions, and remove staff status from non-superusers."

    def add_arguments(self, parser):
        parser.add_argument("--source", type=str, required=False, help="Path to the CSV file or a URL")

    def handle(self, *args, **options):
        source = options.get("source")

        # Reset permissions for all non-superusers
        self.remove_non_superuser_permissions()

        # Remove staff status from non-superusers
        self.remove_non_superuser_staff()

        # Assign default roles (BasicMember for existing project members & ProjectManager for project owners)
        self.assign_project_roles()

        # Assign roles from CSV file
        if source:
            self.assign_roles_from_csv(source)

        self.stdout.write(
            self.style.SUCCESS("Role assignment, staff status cleanup, and permission reset completed successfully.")
        )

    def remove_non_superuser_permissions(self):
        """Remove all permissions and group memberships from non-superusers."""
        users = User.objects.filter(is_superuser=False)
        for user in users:
            for project in Project.objects.all():
                # Remove all object-level permissions
                for perm in get_user_perms(user, project):
                    remove_perm(perm, user, project)

                # Remove user from all groups
                user.groups.clear()
                logger.info(f"Removed all permissions and groups for {user.email} on {project.name}")

    def remove_non_superuser_staff(self):
        """Remove is_staff status from all users who are not superusers."""
        users = User.objects.filter(is_staff=True, is_superuser=False)
        count = users.update(is_staff=False)
        logger.info(f"Removed staff status from {count} non-superuser users.")

    def assign_project_roles(self):
        """Assign BasicMember and ProjectManager roles based on project memberships."""
        for project in Project.objects.all():
            # Assign "Basic Member" role to all project members
            for member in project.members.all():
                BasicMember.assign_user(user=member, project=project)
                logger.info(f"Assigned BasicMember role to {member.email} in project {project.name}")

            # Assign "Project Manager" role to project owner
            if project.owner:
                ProjectManager.assign_user(user=project.owner, project=project)
                logger.info(f"Assigned ProjectManager role to {project.owner.email} in project {project.name}")

    def assign_roles_from_csv(self, source):
        """Assign roles to users for specific projects using a CSV file."""
        try:
            # Determine if source is a URL or file path
            file_path = self.download_csv(source) if self.is_url(source) else source

            with open(file_path, newline="", encoding="utf-8") as csvfile:
                reader = csv.DictReader(csvfile)

                for row in reader:
                    email = row.get("Email")
                    project_ids = row.get("Projects by ID")
                    role_name = row.get("New project role", "").strip()  # Read the role

                    if not email or not project_ids:
                        logger.warning(f"Skipping row with missing data: {row}")
                        continue

                    # Determine the role class to assign
                    role_class = None
                    if role_name == "ProjectManager":
                        role_class = ProjectManager
                    elif role_name == "Identifier":
                        role_class = Identifier
                    else:
                        logger.info(f"No role specified for {email}, skipping.")
                        continue  # Skip if role column is empty

                    # Fetch user
                    try:
                        user = User.objects.get(email=email)
                    except User.DoesNotExist:
                        logger.warning(f"User with email '{email}' not found. Skipping.")
                        continue

                    # Convert project IDs into a list
                    project_ids = [int(pid.strip()) for pid in project_ids.split(",") if pid.strip().isdigit()]

                    for project_id in project_ids:
                        try:
                            project = Project.objects.get(id=project_id)
                        except Project.DoesNotExist:
                            logger.warning(f"Project ID '{project_id}' not found. Skipping.")
                            continue

                        # Assign the selected role
                        try:
                            role_class.assign_user(user, project)
                            logger.info(f"Assigned {role_name} role to {email} in project {project.name}")

                        except Exception as e:
                            logger.error(f"Error assigning {role_name} role to {email} in project {project.name}: {e}")

            self.stdout.write(self.style.SUCCESS("Successfully assigned roles from CSV."))

        except FileNotFoundError:
            raise CommandError(f"File '{source}' not found.")
        except Exception as e:
            raise CommandError(f"An error occurred: {str(e)}")

    def is_url(self, path):
        """Check if the provided path is a URL."""
        return bool(urlparse(path).scheme in ("http", "https"))

    def download_csv(self, url):
        """Download CSV from a URL and save it as a temporary file."""
        logger.info(f"Downloading CSV file from {url}...")
        response = requests.get(url, stream=True)
        if response.status_code == 200:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".csv", mode="wb") as temp_file:
                for chunk in response.iter_content(chunk_size=8192):
                    temp_file.write(chunk)
                logger.info(f"Downloaded CSV file to {temp_file.name}")
                return temp_file.name
        else:
            raise CommandError(f"Failed to download CSV file. HTTP Status: {response.status_code}")
