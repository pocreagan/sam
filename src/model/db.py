import datetime
from typing import Dict
from typing import Iterator
from typing import List
from typing import Optional
from typing import Type
from typing import TypeVar
from typing import Union

from sqlalchemy import Column
from sqlalchemy import Enum
from sqlalchemy import Float
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy.orm import DeclarativeMeta
from sqlalchemy.orm import joinedload

from src.controller import objects
from src.model.connection import Session_t
from src.model.enums import FoodSource
from src.model.enums import NutrientLimitType
from src.model.meta import declarative_base_factory
from src.model.meta import Relationship
from src.model.meta import TableMixin

__all__ = []

Schema: Union[DeclarativeMeta, Type[TableMixin]] = declarative_base_factory('model')

food_to_blob_relationship = Relationship.one_to_one('Food', '_nutrient_data', 'NutrientData', 'food')
region_to_blob_relationship = Relationship.one_to_one('Region', '_nutrient_data', 'NutrientData', 'region')


class Nutrient(Schema):
    _repr_fields = ['name']
    name_id = Column(Integer, nullable=False, index=True)  # the keys in decompressed NutrientData._data
    name = Column(String(128), nullable=False)  # canonical name for the nutrient

    @classmethod
    def all(cls, session: Session_t) -> Dict[int, str]:
        nutrients = session.query(cls) \
            .order_by(cls.name_id) \
            .all()
        return {nut.name_id: nut.name for nut in nutrients}


class Region(Schema):
    _repr_fields = ['name', 'source']
    name = Column(String(32), nullable=False)
    source = Column(String(256), nullable=False)
    _nutrient_data: 'NutrientData' = region_to_blob_relationship.parent

    def set_id(self, pk: int, nut_pk: int) -> None:
        self.id = self._nutrient_data.region_id = pk
        self._nutrient_data.id = nut_pk

    @property
    def limits(self) -> Dict[int, Union[int, float]]:
        return self._nutrient_data.data

    @limits.setter
    def limits(self, data: 'NutrientData') -> None:
        self._nutrient_data = data

    @property
    def limits_display(self) -> List[Union[NutrientLimitType, float]]:
        return [
            v if v > 0. else NutrientLimitType['ND' if v == -1. else 'NL'] for v in self.limits.values()
        ]

    @classmethod
    def all(cls, session: Session_t) -> Dict[str, 'Region']:
        regions = session.query(cls) \
            .all()
        return {region.name: region for region in regions}


class Food(Schema):
    _repr_fields = ['food_id', 'description', 'source', '_qty_per_serving']
    food_id = Column(String(32), nullable=False, index=True)
    description = Column(String(256), nullable=False)
    source = Column(Enum(FoodSource), nullable=False)
    _qty_per_serving = Column(Float)
    _nutrient_data: 'NutrientData' = food_to_blob_relationship.parent

    def set_id(self, pk: int, nut_pk: int) -> None:
        self.id = self._nutrient_data.food_id = pk
        self._nutrient_data.id = nut_pk

    def nutrients_float(self, num_servings: float) -> List[float]:
        return [0. if v <= 0. else (v * num_servings) for v in self.nutrients.values()]

    def nutrients_display(self, num_servings: float) -> List[Union[str, float]]:
        return ['NL' if v <= 0. else (v * num_servings) for v in self.nutrients.values()]

    def to_spreadsheet(self, num_servings: float) -> objects.Food:
        return objects.Food(self.food_id, self.description, num_servings, self.qty_per_serving,
                            self.nutrients_float(num_servings), self.nutrients_display(num_servings))

    @property
    def nutrients(self) -> Dict[int, Union[int, float]]:
        return self._nutrient_data.data

    @nutrients.setter
    def nutrients(self, data: 'NutrientData') -> None:
        self._nutrient_data = data

    @property
    def qty_per_serving(self) -> str:
        return f'{self._qty_per_serving} g' if self.source == FoodSource.USDA else 'NA'

    @qty_per_serving.setter
    def qty_per_serving(self, grams: float) -> None:
        self._qty_per_serving = grams

    @classmethod
    def get(cls, session: Session_t, food_id: str) -> Optional['Food']:
        return session.query(cls) \
            .filter_by(food_id=food_id) \
            .one_or_none()


class NutrientData(Schema):
    _repr_fields = []
    _data = Column(String(256), nullable=False)
    food_id = Food.id_fk()
    food = food_to_blob_relationship.child
    region_id = Region.id_fk()
    region = region_to_blob_relationship.child

    _lookup = {'': 0., '-1': -1}

    @classmethod
    def make(cls, d: Dict[int, str], canonical_ids: Iterator[int]) -> 'NutrientData':
        return cls(_data=','.join(d.get(k, '') for k in canonical_ids))

    @property
    def data(self) -> Dict[int, Union[int, float]]:
        return {i: float(self._lookup.get(v, v)) for i, v in enumerate(self._data.split(','))}


_T = TypeVar('_T')


def get_from_ids(session: Session_t, objects: List[_T]) -> List[_T]:
    cla = type(objects[0])
    return session.query(cla) \
        .filter(cla.id.in_([r.id for r in objects])) \
        .options(joinedload(cla._nutrient_data)) \
        .all()


class Stack:
    def __init__(self, regions: List[Region], foods: List[Food],
                 nutrients_map: Dict[int, str], foods_servings: Dict[str, float]) -> None:
        self._regions = regions
        self._nutrients_map = nutrients_map
        self._foods = [food.to_spreadsheet(foods_servings[food.food_id]) for food in foods]

    def for_spreadsheet(self, app_version: datetime.datetime) -> objects.Output:
        _regions = []
        _amounts_h = [list(t) for t in zip(*[food.nut_float for food in self._foods])]
        _display_val_h = [list(t) for t in zip(*[food.nut_display for food in self._foods])]

        for region in self._regions:
            _nutrients = []
            for name, display, amount, limit in zip(
                    self._nutrients_map.values(), _display_val_h, _amounts_h, region.limits_display
            ):
                _nutrients.append(objects.Nutrient(name, display, amount, limit))

            _regions.append(objects.Region(region.name, region.source, self._foods, _nutrients))

        return objects.Output([('Performed', datetime.datetime.now()), ('App Version:', app_version)], _regions)

    @classmethod
    def from_gui(cls, session: Session_t, regions: List[Region],
                 foods: List[Food], food_servings: Dict[str, float]) -> 'Stack':
        return cls(get_from_ids(session, regions), get_from_ids(
            session, foods,
        ), Nutrient.all(session), food_servings)
