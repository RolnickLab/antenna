from django.core.management.base import BaseCommand

from ami.main.models import SourceImageCollection
from ami.ml.models import Algorithm


class Command(BaseCommand):
    help = """
    Filter classifications by a provided taxa list

    # Usage:
    docker compose run --rm django python manage.py test_class_masking --project 1 --taxa-list 1" \
    """

    def add_arguments(self, parser):
        parser.add_argument("--project", type=int, help="Project ID to process")
        parser.add_argument("--collection", type=int, help="Source image collection ID to process")
        parser.add_argument("--taxa-list", type=int, help="Taxa list ID to filter by")
        parser.add_argument(
            "--algorithm", type=int, help="Algorithm ID to use for filtering classifications (e.g. the global model)"
        )
        parser.add_argument("--dry-run", action="store_true", help="Don't make any changes")

    def handle(self, *args, **options):
        project_id = options["project"]
        collection_id = options["collection"]
        taxa_list_id = options["taxa_list"]
        algorithm_id = options["algorithm"]

        from ami.main.models import Project, TaxaList
        from ami.ml.post_processing.class_masking import update_occurrences_in_collection

        try:
            project = Project.objects.get(id=project_id)
            taxa_list = TaxaList.objects.get(id=taxa_list_id)
            collection = SourceImageCollection.objects.get(id=collection_id)
            algorithm = Algorithm.objects.get(id=algorithm_id)
        except (Project.DoesNotExist, TaxaList.DoesNotExist) as e:
            self.stdout.write(f"Error: {e}")
            return

        self.stdout.write(f"Processing project: {project.name}, taxa list: {taxa_list.name}")
        self.stdout.write("Filtering classifications based on the taxa list...")
        # Log collection
        self.stdout.write(f"Collection: {collection.name} (ID: {collection.pk})")

        update_occurrences_in_collection(
            collection=collection,
            taxa_list=taxa_list,
            algorithm=algorithm,
            params={},
            job=None,
        )
