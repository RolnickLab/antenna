"""
Enumerations shared across the ``main`` models.

Kept free of model imports so that model modules can import it without creating
a cycle.
"""

from ami.utils.schemas import OrderedEnum


class TaxonRank(OrderedEnum):
    KINGDOM = "KINGDOM"
    PHYLUM = "PHYLUM"
    CLASS = "CLASS"
    ORDER = "ORDER"
    SUPERFAMILY = "SUPERFAMILY"
    FAMILY = "FAMILY"
    SUBFAMILY = "SUBFAMILY"
    TRIBE = "TRIBE"
    SUBTRIBE = "SUBTRIBE"
    GENUS = "GENUS"
    SPECIES = "SPECIES"
    UNKNOWN = "UNKNOWN"


DEFAULT_RANKS = sorted(
    [
        TaxonRank.KINGDOM,
        TaxonRank.PHYLUM,
        TaxonRank.CLASS,
        TaxonRank.ORDER,
        TaxonRank.FAMILY,
        TaxonRank.SUBFAMILY,
        TaxonRank.TRIBE,
        TaxonRank.GENUS,
        TaxonRank.SPECIES,
    ]
)
