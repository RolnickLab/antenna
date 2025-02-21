import csv
import logging
import tempfile
from urllib.parse import urlparse

import requests
from django.core.management.base import BaseCommand, CommandError
from users.roles import Identifier

from ami.main.models import Project
from ami.users.models import User

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Assign Identifier role to users for specific projects based on a CSV file.

    Expected CSV Format:
        Name,Email,Projects by ID,Projects by name,User type,Comments
        John Doe,email@insectai.org,"1, 2, 3",
        "Vermont Atlas of Life, Insectarium de Montréal","Internal","Some comment"

    Usage:
        python manage.py assign_identifiers --source roles.csv
        python manage.py assign_identifiers --source "https://example.com/roles.csv"
    """

    help = "Assign the Identifier role to users for specific projects using a CSV file (from a URL or local file)."

    def add_arguments(self, parser):
        parser.add_argument("--source", type=str, required=True, help="Path to the CSV file or a URL")

    def handle(self, *args, **options):
        source = options["source"]

        try:
            # Determine if source is a URL or file path
            if self.is_url(source):
                file_path = self.download_csv(source)
            else:
                file_path = source  # Local file path

            with open(file_path, newline="", encoding="utf-8") as csvfile:
                reader = csv.DictReader(csvfile)

                for row in reader:
                    email = row.get("Email")
                    project_ids = row.get("Projects by ID")

                    if not email or not project_ids:
                        logger.warning(f"Skipping row with missing data: {row}")
                        continue

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

                        # Assign the Identifier role
                        try:
                            Identifier.assign_user(user, project)
                            logger.info(f"Assigned Identifier role to {email} in project {project_id}")

                        except Exception as e:
                            logger.error(f"Error assigning Identifier role to {email} in project {project_id}: {e}")

            self.stdout.write(self.style.SUCCESS("Successfully assigned Identifier roles to users."))

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
