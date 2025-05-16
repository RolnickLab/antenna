from django.test import TestCase

from ami.main.models import Identification, Occurrence, Project, Taxon, TaxonRank
from ami.tasks import merge_taxa

# No longer using these fixtures


# test merging taxa
class TestTaxaMerging(TestCase):
    """Test the functionality for merging two taxa."""

    def test_merge_taxa(self):
        """Test the basic functionality of merging taxa."""
        # Create a simple project
        project = Project.objects.create(name="Test Project for Taxa Merging")

        # Create a taxonomy hierarchy
        order_taxon = Taxon.objects.create(name="Test Order", rank=TaxonRank.ORDER.name)
        family_taxon = Taxon.objects.create(name="Test Family", rank=TaxonRank.FAMILY.name, parent=order_taxon)
        genus_taxon = Taxon.objects.create(name="Test Genus", rank=TaxonRank.GENUS.name, parent=family_taxon)

        # Create two species to merge
        target_taxon = Taxon.objects.create(
            name="Target Species",
            rank=TaxonRank.SPECIES.name,
            parent=genus_taxon,
            display_name="Target Species",
            search_names=["Fuzzy moth"],
        )
        source_taxon = Taxon.objects.create(
            name="Source Species",
            rank=TaxonRank.SPECIES.name,
            parent=genus_taxon,
            display_name="Source Species",
            search_names=["Old moth"],
            gbif_taxon_key=123456,
            cover_image_url="http://example.com/image.jpg",
        )

        # Add them to the project
        order_taxon.projects.add(project)
        family_taxon.projects.add(project)
        genus_taxon.projects.add(project)
        target_taxon.projects.add(project)
        source_taxon.projects.add(project)

        # Create a child taxon for source_taxon
        subspecies = Taxon.objects.create(
            name="Source Subspecies",
            rank=TaxonRank.SPECIES.name,  # Using species rank for simplicity
            parent=source_taxon,
        )
        subspecies.projects.add(project)

        # Update parent relationships for all taxa
        for taxon in [order_taxon, family_taxon, genus_taxon, target_taxon, source_taxon, subspecies]:
            taxon.update_parents()

        # Create an identification using source_taxon
        occurrence = Occurrence.objects.create(project=project, determination=source_taxon, determination_score=0.8)
        identification = Identification.objects.create(taxon=source_taxon, occurrence=occurrence)

        # Verify initial state
        self.assertEqual(target_taxon.direct_children.count(), 0)
        self.assertEqual(source_taxon.direct_children.count(), 1)
        self.assertEqual(identification.taxon, source_taxon)
        self.assertTrue(source_taxon.active)

        # Execute the merge
        merge_taxa(target_taxon_id=target_taxon.id, source_taxon_id=source_taxon.id)

        # Refresh objects from database
        target_taxon.refresh_from_db()
        source_taxon.refresh_from_db()
        subspecies.refresh_from_db()
        identification.refresh_from_db()
        occurrence.refresh_from_db()

        # Verify merged state
        # Check that the child taxon has been reparented
        self.assertEqual(subspecies.parent, target_taxon)
        self.assertEqual(target_taxon.direct_children.count(), 1)
        self.assertEqual(source_taxon.direct_children.count(), 0)

        # Check that source_taxon is marked as inactive and is a synonym of taxon_keeper
        self.assertFalse(source_taxon.active)
        self.assertEqual(source_taxon.synonym_of, target_taxon)

        # Check that identification now points to taxon_keeper
        self.assertEqual(identification.taxon, target_taxon)

        # Check that occurrence now has taxon_keeper as its determination
        self.assertEqual(occurrence.determination, target_taxon)

        # Check that the search names have been merged
        self.assertIn("Fuzzy moth", target_taxon.search_names)
        self.assertIn("Old moth", target_taxon.search_names)

        # Check that the basic attributes have been merged
        self.assertEqual(target_taxon.gbif_taxon_key, 123456)
        self.assertEqual(target_taxon.cover_image_url, "http://example.com/image.jpg")
