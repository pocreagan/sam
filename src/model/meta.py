"""
performs instrument_setup on declarative_base factory
declares mixin class that handles repr, time created, and primary key id: int
Make contains convenience relationship instantiating to be used in db.py
"""

import datetime
import json
from dataclasses import dataclass
from typing import *

import sqlalchemy as sa
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.declarative import DeclarativeMeta
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.orm import relationship
from sqlalchemy.orm.relationships import RelationshipProperty

__all__ = [
    'declarative_base_factory',
    'TableMixin',
    'Relationship',
    'JSONEncodedDict',
]


def metadata_kwargs() -> Dict[str, Dict[str, str]]:
    """
    builds naming convention for indices, constraints, and keys
    """
    # ? https://docs.sqlalchemy.org/en/13/core/metadata.html#sqlalchemy.schema.MetaData.params.info
    named_keys = {'col_0_label': '__%(column_0_label)s',
                  'col_0': '__%(column_0_name)s',
                  'table': '__%(table_name)s',
                  'referred_table': '__%(referred_table_name)s',
                  'constraint': '__%(constraint_name)s', }
    named_items = {'ix': '{col_0_label}',
                   'uq': '{table}{col_0}',
                   'ck': '{table}{col_0}',
                   'fk': '{table}{col_0}{referred_table}',
                   'pk': '{table}', }
    return {'naming_convention': {k: f'{k}{v.format(**named_keys)}' for k, v in named_items.items()}}


metadata = metadata_kwargs()


def declarative_base_factory(name: str) -> DeclarativeMeta:
    r = declarative_base(metadata=sa.MetaData(**metadata), cls=TableMixin, name=f'{name}_schema')
    r.connection_name = name
    return r


class TableMixin:
    """
    all tables have id and created_at columns
    also specifies __repr__ for instrument_debug print
    models should inherit from (Base, TableMixin)
    """
    __abstract__ = True

    # ? https://docs.sqlalchemy.org/en/13/orm/extensions/declarative/mixins.html

    @classmethod
    def id_fk(cls) -> sa.Column:
        return sa.Column(sa.Integer, sa.ForeignKey(cls.__name__ + '.id'))

    @declared_attr
    def __tablename__(self) -> str:
        return self.__name__

    id = sa.Column(sa.Integer, primary_key=True, autoincrement=True)

    __table__ = None
    _repr_fields: Optional[List[str]] = None

    def _format_one(self, k: str):
        v = getattr(self, k, None)
        if isinstance(v, datetime.datetime):
            return v.strftime(r'%Y%m%d:%H%M%S')
        return v

    def _repr(self, fields: List[str] = None) -> str:
        # ? https://stackoverflow.com/a/55749579
        field_strings, attached, _t = [], 0, type(self)
        for key in fields or _t.__table__.c.keys():
            try:
                field_strings.append(f'{key}={self._format_one(key)!r}')
            except sa.orm.exc.DetachedInstanceError:
                field_strings.append(f'{key}=detached')
            else:
                attached += 1
        if attached:
            return f"< {_t.__name__}({','.join(field_strings)}) >"
        return f"< {_t.__name__} py_id={id(self)} >"

    def __str__(self) -> str:
        return repr(self)

    def __repr__(self) -> str:
        return self._repr(self._repr_fields)


class Relationship:
    # ? https://docs.sqlalchemy.org/en/13/orm/relationship_api.html?highlight=lazy
    @dataclass
    class _TwoWayRelationship:
        parent: RelationshipProperty
        child: RelationshipProperty

    @staticmethod
    def one_to_many(parent_table, parent_col, child_table, child_col) -> _TwoWayRelationship:
        """
        makes both ends of a one-to-many relationship
        the foreign order_key still needs to be specified on the child table first
        """
        # noinspection PyCallByClass
        return Relationship._TwoWayRelationship(
            parent=relationship(child_table, back_populates=child_col, lazy='select',
                                cascade='all, delete-orphan', single_parent=True, enable_typechecks=False),
            child=relationship(parent_table, back_populates=parent_col, lazy='select',
                               enable_typechecks=False)
        )

    @staticmethod
    def one_to_one(parent_table, parent_col, child_table, child_col) -> _TwoWayRelationship:
        """
        makes both ends of a one-to-one relationship
        the foreign key still needs to be specified on the child table first
        """
        # noinspection PyCallByClass
        return Relationship._TwoWayRelationship(
            parent=relationship(child_table, back_populates=child_col, uselist=False, lazy='select',
                                cascade='all, delete-orphan', single_parent=True, enable_typechecks=False),
            child=relationship(parent_table, back_populates=parent_col, lazy='select',
                               enable_typechecks=False)
        )

    @staticmethod
    def association(schema: DeclarativeMeta,
                    first_t: str, first_c: str, second_t: str, second_c: str) -> Tuple[_TwoWayRelationship, sa.Table]:
        # noinspection PyUnresolvedReferences
        table = sa.Table(
            f'association_{first_t}_{second_t}', schema.metadata,
            sa.Column(f'parent_id', sa.Integer, sa.ForeignKey(f'{first_t}.id')),
            sa.Column(f'child_id', sa.Integer, sa.ForeignKey(f'{second_t}.id'))
        )
        return Relationship._TwoWayRelationship(
            parent=relationship(second_t, secondary=table, back_populates=second_c, enable_typechecks=False),
            child=relationship(first_t, secondary=table, back_populates=first_c, enable_typechecks=False),
        ), table

    @staticmethod
    def child_to_parent(other):
        """
        use only when left outer join is not needed
        use when lazy loading is acceptable
        """
        return relationship(other, lazy='select', innerjoin=True, enable_typechecks=False)

    @staticmethod
    def last_modified():
        return sa.Column(sa.DateTime, onupdate=sa.func.now())


# SUPPRESS-LINTER <this is the exact proto given in the docs>
# noinspection PyAbstractClass
class JSONEncodedDict(sa.TypeDecorator):
    # ? https://docs.sqlalchemy.org/en/14/core/custom_types.html#marshal-json-strings
    """
    Represents an immutable structure as a json-encoded string.
        ex: JSONEncodedDict(255)
    """

    impl = sa.VARCHAR

    def process_bind_param(self, value, dialect):
        if isinstance(value, str):
            raise ValueError(f'{type(self).__name__} columns must be set with py objects')
        return json.dumps(value) if value else '{}'

    def process_result_value(self, value, dialect):
        return json.loads(value) if value else {}
