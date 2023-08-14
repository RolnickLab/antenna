import json
import pathlib
import time

from django.core.management.base import BaseCommand, CommandError  # noqa

from ...models import TaxaList, Taxon


class Command(BaseCommand):
    r"""Import taxa from a JSON file. Assign their rank and parent taxon.

    Example taxa.json
    [
        {
            "species": "Epimartyria auricrinella",
            "genus": "Epimartyria",
            "family": "Micropterigidae"
        },
        {
            "species": "Dyseriocrania griseocapitella",
            "genus": "Dyseriocrania",
            "family": "Eriocraniidae"
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

        root_taxon_parent, created = Taxon.objects.get_or_create(name="Lepidoptera", rank="ORDER", ordering=0)
        for taxon in taxa:
            species = taxon["species"]
            genus = taxon["genus"]
            family = taxon["family"]

            # Get or create family
            family_taxon, created = Taxon.objects.get_or_create(name=family, rank="FAMILY")
            if family_taxon.parent != root_taxon_parent:
                family_taxon.parent = root_taxon_parent
                if not created:
                    self.stdout.write(
                        self.style.WARNING(f"Reassigning parent of {family_taxon} to {root_taxon_parent}")
                    )
                family_taxon.save()
            if created:
                self.stdout.write(self.style.SUCCESS('Successfully created taxon "%s"' % family_taxon))

            # Get or create genus
            genus_taxon, created = Taxon.objects.get_or_create(name=genus, rank="GENUS")
            if genus_taxon.parent != family_taxon:
                genus_taxon.parent = family_taxon
                if not created:
                    self.stdout.write(self.style.WARNING(f"Reassigning parent of {genus_taxon} to {family_taxon}"))
                genus_taxon.save()
            if created:
                self.stdout.write(self.style.SUCCESS('Successfully created taxon "%s"' % genus_taxon))

            # Get or create species
            species_taxon, created = Taxon.objects.get_or_create(name=species, rank="SPECIES")
            if species_taxon.parent != genus_taxon:
                species_taxon.parent = genus_taxon
                if not created:
                    self.stdout.write(self.style.WARNING(f"Reassigning parent of {species_taxon} to {genus_taxon}"))
                species_taxon.save()
            if created:
                self.stdout.write(self.style.SUCCESS('Successfully created taxon "%s"' % species_taxon))

            # Add all entries to taxalist
            taxalist.taxa.add(species_taxon, genus_taxon, family_taxon)
