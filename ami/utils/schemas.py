from enum import Enum


class OrderedEnum(Enum):
    """
    An Enum where the order of the values is significant.

    The order is determined by the order in which the values are defined in the class definition.
    This allows for comparisons between values of the same Enum class.
    For example TaxonRank.SPECIES > TaxonRank.GENUS is True and TaxonRank.SPECIES < TaxonRank.FAMILY is False.
    (The higher the rank, the lower the value).

    Source https://stackoverflow.com/a/58367726/966058
    """

    def __init__(self, value, *args, **kwds):
        super().__init__(*args, **kwds)
        self.__order = len(self.__class__)

    def __ge__(self, other):
        if self.__class__ is other.__class__:
            return self.__order >= other.__order
        return NotImplemented

    def __gt__(self, other):
        if self.__class__ is other.__class__:
            return self.__order > other.__order
        return NotImplemented

    def __le__(self, other):
        if self.__class__ is other.__class__:
            return self.__order <= other.__order
        return NotImplemented

    def __lt__(self, other):
        if self.__class__ is other.__class__:
            return self.__order < other.__order
        return NotImplemented
