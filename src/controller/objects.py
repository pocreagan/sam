import datetime
from dataclasses import dataclass
from operator import attrgetter
from typing import List
from typing import Optional
from typing import Tuple
from typing import Union

from src.controller.constants import *
from src.model.enums import NutrientLimitType

__all__ = [
    'Output',
    'Region',
    'Food',
    'Nutrient',
]


@dataclass
class Output:
    versions: List[Tuple[str, datetime.date]]
    regions: List['Region']

    def __post_init__(self):
        self.regions.sort(key=attrgetter('name'))


@dataclass
class Region:
    name: str
    limits_source: str
    foods: List['Food']
    nutrients: List['Nutrient']

    # def __post_init__(self):
        # self.nutrients.sort(key=attrgetter('name'))

    @property
    def exceeds_guidance_level(self) -> bool:
        return any(nut.is_limited and nut.exceeds_guidance_level for nut in self.nutrients)


@dataclass
class Food:
    food_id: str
    description: str
    num_servings: float
    qty_per_serving: Optional[str]
    nut_float: List[float]
    nut_display: List[Union[str, float]]


@dataclass
class Nutrient:
    name: str
    display_values: List[Union[float, str]]
    amounts: List[float]
    limit: Union[NutrientLimitType, float]

    @property
    def is_limited(self) -> bool:
        return isinstance(self.limit, float)

    @property
    def sum(self) -> float:
        return sum(self.amounts)

    @property
    def percent_of_limit(self) -> float:
        if self.is_limited:
            return self.sum / self.limit

    @property
    def exceeds_guidance_level(self) -> bool:
        if self.is_limited:
            return self.sum > self.limit

    @property
    def column_color(self) -> str:
        return NUTRIENT_FAIL_COLOR_BG if self.exceeds_guidance_level else None
