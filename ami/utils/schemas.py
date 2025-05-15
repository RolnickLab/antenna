from enum import Enum


class OrderedEnum(Enum):
    """
    An Enum where the order of the values is significant.

    The order is determined by the order in which the values are defined in the class definition.
    This allows for comparisons between values of the same Enum class.
    For example TaxonRank.SPECIES > TaxonRank.GENUS is True and TaxonRank.SPECIES < TaxonRank.FAMILY is False.
    (The higher the rank, the lower the value).

    This also implements a case-insensitive lookup for values.

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

    def __eq__(self, other) -> bool:
        """
        If comparing to a string, convert the string to the OrderedEnum type and compare.
        """
        if self.__class__ is other.__class__:
            return super().__eq__(other)
        elif isinstance(other, str):
            other = self.__class__(other)
            return super().__eq__(other)
        else:
            raise NotImplementedError(f"Cannot compare {self.__class__} to {other.__class__}")

    def __hash__(self) -> int:
        return hash(self.value)

    @classmethod
    def _missing_(cls, value: str):
        """Allow case-insensitive lookups."""
        for member in cls:
            if member.value.upper() == value.upper():
                return member
        return None

    @classmethod
    def choices(cls):
        """For use in Django text fields with choices."""
        return tuple((i.name, i.value) for i in cls)

    def __str__(self):
        return self.value
