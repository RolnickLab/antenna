import json
import pathlib
import time

from django.core.management.base import BaseCommand, CommandError  # noqa

from ...models import TaxaList, Taxon


class Command(BaseCommand):
    r"""
    Import taxa from a JSON file. Assign their rank, parent taxa, gbif_taxon_key, and accepted_name.

    This is a very specific command for importing taxa from an exiting format. A more general
    import command with support for all taxon ranks & fields should be written.



    Example taxa.json
    [
        {
            "species": "Epimartyria auricrinella",
            "genus": "Epimartyria",
            "family": "Micropterigidae",
            "gbif_taxon_key": 12345,
            "synonym_of": "Genus species"
        },
        {
            "species": "Dyseriocrania griseocapitella",
            "genus": "Dyseriocrania",
            "family": "Eriocraniidae",
            "gbif_taxon_key": 12346
        }
    ]
    """

    help = "Import taxa from a JSON file. Assign their rank and parent taxon."

    def add_arguments(self, parser):
        parser.add_argument("taxa", type=str, help="Path to taxa JSON file")
        parser.add_argument("--list", type=str, help="Name of taxa list to add taxa to")
        # Boolean argument to purge all taxa from the database before importing
        parser.add_argument("--purge", action="store_true", help="Purge all taxa from the database before importing.")

    def handle(self, *args, **options):
        fname: str = options["taxa"]
        taxa = json.load(open(fname))
        if options["list"]:
            list_name = options["list"]
        else:
            list_name = pathlib.Path(fname).stem

        if options["purge"]:
            self.stdout.write(self.style.WARNING("Purging all taxa from the database in 5 seconds..."))
            time.sleep(5)
            self.stdout.write("Purging...")
            Taxon.objects.all().delete()

        taxalist, created = TaxaList.objects.get_or_create(name=list_name)
        if created:
            self.stdout.write(self.style.SUCCESS('Successfully created taxa list "%s"' % taxalist))

        root_taxon_parent, created = Taxon.objects.get_or_create(
            name="Lepidoptera", rank="ORDER", defaults={"ordering": 0}
        )

        for taxon in taxa:
            # Add all entries to taxalist
            created_taxa = self.create_taxon(taxon, root_taxon_parent)
            taxalist.taxa.add(*created_taxa)

    def create_taxon(self, taxon_data: dict, root_taxon_parent: Taxon) -> list[Taxon]:
        created_taxa = []

        species = taxon_data["species"]
        genus = taxon_data.get("genus", None)
        family = taxon_data.get("family", None)
        accepted_name = taxon_data.get("synonym_of", None)

        # Get or create family
        if family:
            family_taxon, created = Taxon.objects.get_or_create(name=family, rank="FAMILY")
            if root_taxon_parent and (family_taxon.parent != root_taxon_parent):
                family_taxon.parent = root_taxon_parent  # type: ignore
                if not created:
                    self.stdout.write(
                        self.style.WARNING(f"Reassigning parent of {family_taxon} to {root_taxon_parent}")
                    )
                family_taxon.save()
            if created:
                self.stdout.write(self.style.SUCCESS('Successfully created taxon "%s"' % family_taxon))
            created_taxa.append(family_taxon)
        else:
            family_taxon = None

        if genus:
            # Get or create genus
            genus_taxon, created = Taxon.objects.get_or_create(name=genus, rank="GENUS")
            if family_taxon and (genus_taxon.parent != family_taxon):
                genus_taxon.parent = family_taxon  # type: ignore
                if not created:
                    self.stdout.write(self.style.WARNING(f"Reassigning parent of {genus_taxon} to {family_taxon}"))
                genus_taxon.save()
            if created:
                self.stdout.write(self.style.SUCCESS('Successfully created taxon "%s"' % genus_taxon))
            created_taxa.append(genus_taxon)

        else:
            genus_taxon = None

        if accepted_name:
            accepted_taxon, created = Taxon.objects.get_or_create(
                name=accepted_name,
                rank="SPECIES",
                defaults={"parent": genus_taxon},
            )
        else:
            accepted_taxon = None

        # Get or create species
        species_taxon, created = Taxon.objects.get_or_create(
            name=species,
            rank="SPECIES",
            defaults={
                "parent": genus_taxon,
                "synonym_of": accepted_taxon,
                "gbif_taxon_key": taxon_data.get("gbif_taxon_key", None),
            },
        )
        if genus_taxon and (species_taxon.parent != genus_taxon):
            species_taxon.parent = genus_taxon  # type: ignore
            if not created:
                self.stdout.write(self.style.WARNING(f"Reassigning parent of {species_taxon} to {genus_taxon}"))
            species_taxon.save()
        if created:
            self.stdout.write(self.style.SUCCESS('Successfully created taxon "%s"' % species_taxon))

        return created_taxa
