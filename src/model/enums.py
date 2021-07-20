from enum import auto
from enum import Enum

__all__ = [
    'FoodSource',
    'NutrientLimitType',
]


class FoodSource(Enum):
    USDA = auto()
    HLF = auto()


class NutrientLimitType(Enum):
    STD = auto()
    NL = auto()
    ND = auto()
