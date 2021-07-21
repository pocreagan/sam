import datetime
from typing import Type
from typing import Union

from sqlalchemy import Column
from sqlalchemy import DateTime
from sqlalchemy import func
from sqlalchemy import String
from sqlalchemy.orm import DeclarativeMeta

from src.model.meta import declarative_base_factory
from src.model.meta import JSONEncodedDict
from src.model.meta import TableMixin

__all__ = []

Schema: Union[DeclarativeMeta, Type[TableMixin]] = declarative_base_factory('model')


class Stack(Schema):
    _repr_fields = ['name', 'created_at']
    name = Column(String(32), nullable=False)
    _created_at: datetime.datetime = Column(DateTime, server_default=func.now())
    foods = Column(JSONEncodedDict, nullable=False)

    @property
    def created_at(self) -> datetime.datetime:
        return self._created_at.replace(tzinfo=datetime.timezone.utc).astimezone(tz=None)
