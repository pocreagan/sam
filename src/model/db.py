from typing import Dict
from typing import Iterator
from typing import List
from typing import Optional
from typing import Tuple
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

from src.model.connection import Session_t
from src.model.enums import FoodSource
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
    def as_list(cls, session: Session_t) -> List['Nutrient']:
        return session.query(cls) \
            .order_by(cls.name_id) \
            .all()


class Region(Schema):
    _repr_fields = ['name', 'source']
    name = Column(String(32), nullable=False)
    source = Column(String(256), nullable=False)
    _nutrient_data: 'NutrientData' = region_to_blob_relationship.parent

    def set_id(self, pk: int, nut_pk: int) -> None:
        # noinspection PyAttributeOutsideInit
        self.id = self._nutrient_data.region_id = pk
        self._nutrient_data.id = nut_pk

    @property
    def limits(self) -> Dict[int, Union[int, float]]:
        return self._nutrient_data.data

    @limits.setter
    def limits(self, data: 'NutrientData') -> None:
        self._nutrient_data = data

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
    num_servings: float = 1.0

    @classmethod
    def search(cls, session: Session_t, term: str) -> List[int]:
        split_terms = term.split()

        q = session.query(cls)
        if len(split_terms) == 1 and term[-1].isdigit():
            first = term[0]

            if first.upper() == 'F':
                q = q.filter(cls.food_id == term.upper())

            elif first.isdigit():
                # noinspection PyUnresolvedReferences
                q = q.filter(cls.food_id.ilike(f'{term}%'))

            else:
                return []

        else:
            for t in split_terms:
                # noinspection PyUnresolvedReferences
                q = q.filter(cls.description.ilike(f'%{t}%'))

        return q.all()

    def set_id(self, pk: int, nut_pk: int) -> None:
        # noinspection PyAttributeOutsideInit
        self.id = self._nutrient_data.food_id = pk
        self._nutrient_data.id = nut_pk

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
        data: Tuple[str] = tuple(d.get(k, '') for k in canonical_ids)  # type: ignore
        return cls.make_naive(data)

    @classmethod
    def make_naive(cls, t: Tuple[str]) -> 'NutrientData':
        return cls(_data=','.join(t))

    @property
    def data(self) -> Dict[int, Union[int, float]]:
        return {i: float(self._lookup.get(v, v)) for i, v in enumerate(self._data.split(','))}


_T = TypeVar('_T')


def get_from_ids(session: Session_t, objects: List[_T]) -> List[_T]:
    cla = type(objects[0])
    # noinspection PyProtectedMember
    output = session.query(cla) \
        .filter(cla.id.in_([r.id for r in objects])) \
        .options(joinedload(cla._nutrient_data)) \
        .all()
    output_d = {m.id: m for m in output}
    return [output_d[o.id] for o in objects]
