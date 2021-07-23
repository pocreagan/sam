import dataclasses
from typing import Dict
from typing import List
from typing import Optional
from typing import Tuple
from typing import Union

from src.model import db
from src.model.enums import NutrientLimitType

__all__ = [
    'Result',
    'Nutrient',
    'Region',
    'Output',
]


@dataclasses.dataclass
class Result:
    sum: float
    guidance_level: Union[NutrientLimitType, float]

    @property
    def is_limited(self) -> bool:
        return isinstance(self.guidance_level, float)

    @property
    def percent_of_guidance_level(self) -> Optional[float]:
        if self.is_limited:
            return self.sum / self.guidance_level

    @property
    def guidance_level_exceeded(self) -> bool:
        return self.is_limited and self.sum > self.guidance_level


@dataclasses.dataclass
class Nutrient:
    canonical: db.Nutrient
    _foods: dataclasses.InitVar[List[db.Food]]
    _regions: dataclasses.InitVar[List[db.Region]]

    sum: float = 0.
    amount_per_food: Dict[str, Union[str, float]] = dataclasses.field(default_factory=dict)
    results: Dict[str, Result] = dataclasses.field(default_factory=dict)
    any_guidance_level_exceeded: bool = False

    def __post_init__(self, _foods: List[db.Food], _regions: List['Region']) -> None:
        for food in _foods:
            _nut = food.nutrients[self.canonical.name_id]
            if _nut >= 0.:
                amount = _nut * food.num_servings
                self.sum += amount
                self.amount_per_food[food.food_id] = amount

            else:
                self.amount_per_food[food.food_id] = 'NL'

        for region in _regions:
            v = region.obj.limits[self.canonical.name_id]
            result = Result(self.sum, v if v > 0. else NutrientLimitType['ND' if v == -1. else 'NL'])
            self.any_guidance_level_exceeded |= result.guidance_level_exceeded
            region.any_guidance_level_exceeded |= result.guidance_level_exceeded
            self.results[region.obj.name] = result

    @property
    def bad_first_then_canonical_order(self) -> Tuple[int, int]:
        return int(not self.any_guidance_level_exceeded), self.canonical.id


@dataclasses.dataclass
class Region:
    obj: db.Region
    any_guidance_level_exceeded: bool = False

    @property
    def bad_first_then_alphabetical(self) -> Tuple[int, str]:
        return int(not self.any_guidance_level_exceeded), self.obj.name


@dataclasses.dataclass
class Output:
    def __init__(self, nutrients: List[db.Nutrient], regions: List[db.Region], foods: List[db.Food]) -> None:
        self.regions = [Region(r) for r in regions]
        self.foods = foods
        self.nutrients = [Nutrient(n, self.foods, self.regions) for n in nutrients]
