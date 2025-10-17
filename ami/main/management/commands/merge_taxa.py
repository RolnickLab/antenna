from django.core.management.base import BaseCommand, CommandError

from ami.main.models import Taxon
from ami.tasks import merge_taxa as merge_taxa_task


class Command(BaseCommand):
    help = "Merge all data related to one taxon into another and deactivate the source taxon"

    def add_arguments(self, parser):
        parser.add_argument(
            "--target_taxon_id",
            type=int,
            help="ID of the taxon that will remain active and receive all data",
        )
        parser.add_argument(
            "--source_taxon_id",
            type=int,
            help="ID of the taxon that will be marked inactive and merged into the target",
        )
        parser.add_argument(
            "--no-confirmation",
            action="store_true",
            help="Skip confirmation prompt (use with caution)",
        )

    def handle(self, *args, **options):
        target_taxon_id = options["target_taxon_id"]
        source_taxon_id = options["source_taxon_id"]
        skip_confirmation = options["no_confirmation"]

        # Validate taxa exist
        try:
            target_taxon = Taxon.objects.get(id=target_taxon_id)
            source_taxon = Taxon.objects.get(id=source_taxon_id)
        except Taxon.DoesNotExist:
            raise CommandError(f"One or both of the taxa IDs ({target_taxon_id}, {source_taxon_id}) do not exist")

        # Display information about the taxa being merged
        self.stdout.write("\nTaxa to be merged:")
        self.stdout.write(
            f"Target Taxon (will remain): {target_taxon.display_name} "
            f"(ID: {target_taxon.id}, Rank: {target_taxon.rank})"
        )
        self.stdout.write(
            f"Source Taxon (will be merged): {source_taxon.display_name} "
            f"(ID: {source_taxon.id}, Rank: {source_taxon.rank})"
        )

        # Display counts of related objects
        self.stdout.write("\nRelated objects that will be affected:")
        self.stdout.write(f"- {source_taxon.occurrences.count()} occurrences will be reassigned")
        self.stdout.write(f"- {source_taxon.direct_children.count()} child taxa will be reparented")

        # Confirm with the user before proceeding unless --no-confirmation flag is used
        if not skip_confirmation:
            self.stdout.write(
                self.style.WARNING(
                    f"\nWARNING: This operation will merge '{source_taxon.display_name}' into "
                    f"'{target_taxon.display_name}' and cannot be undone!"
                )
            )
            self.stdout.write("The source taxon will be marked as inactive and set as a synonym of the target taxon.")

            confirm = input("\nAre you sure you want to proceed? [y/N]: ")
            if confirm.lower() not in ["y", "yes"]:
                self.stdout.write(self.style.ERROR("Operation cancelled."))
                return

        # Perform the merge using the existing task function directly (not as a task)
        try:
            # Call the merge_taxa function directly without using Celery
            # This gives immediate feedback in the management command
            merge_taxa_task(target_taxon_id=target_taxon_id, source_taxon_id=source_taxon_id)

            # Verify merge was successful
            source_taxon.refresh_from_db()
            if source_taxon.active or source_taxon.synonym_of_id != target_taxon_id:
                raise CommandError("Merge operation did not complete successfully")

            self.stdout.write(
                self.style.SUCCESS(
                    f"Successfully merged '{source_taxon.display_name}' into '{target_taxon.display_name}'"
                )
            )

            # Print summary of both taxa's attributes and relationships after the merge
            target_taxon.refresh_from_db()
            self.stdout.write(f"\nTarget Taxon ({target_taxon.display_name}) after merge:")
            self.stdout.write(
                f"- ID: {target_taxon.id}, Rank: {target_taxon.rank}, Active: {target_taxon.active}, "
                f"Synonym of: {target_taxon.synonym_of}"
            )
            self.stdout.write(f"- Search names: {', '.join(str(name) for name in target_taxon.search_names)}")
            self.stdout.write(f"- {target_taxon.direct_children.count()} child taxa")
            self.stdout.write(f"- {target_taxon.occurrences.count()} occurrences")
            self.stdout.write(f"- {target_taxon.projects.count()} projects")
            self.stdout.write(f"\nSource Taxon ({source_taxon.display_name}) after merge:")
            self.stdout.write(
                f"- ID: {source_taxon.id}, Rank: {source_taxon.rank}, Active: {source_taxon.active}, "
                f"Synonym of: {source_taxon.synonym_of}"
            )
            self.stdout.write(f"- {source_taxon.direct_children.count()} child taxa")
            self.stdout.write(f"- {source_taxon.occurrences.count()} occurrences")
            self.stdout.write(f"- {source_taxon.projects.count()} projects")

        except Exception as e:
            raise CommandError(f"Error merging taxa: {str(e)}")
