"""
declarative base class must be imported in order:
    meta -> schema -> connection
session manager is defined with Session in closure and
should be imported from here but not used here
"""
from contextlib import contextmanager
from typing import Callable
from typing import ContextManager
from typing import TypeVar

import sqlalchemy as sa
from sqlalchemy.ext.declarative import DeclarativeMeta
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.session import Session

__all__ = [
    'Database',
    'SessionManager',
    'Session_t',
]

_T = TypeVar('_T')


# noinspection PyPep8Naming
class Session_t(Session):
    def make(self: Session, obj: _T) -> _T:
        self.add(obj)
        self.flush([obj])
        return obj

    def context_commit(self) -> None:
        super().commit()

    def rebind(self, record: _T) -> _T:
        return self.query(type(record)).get(record.id)

    def commit(self):
        raise Exception('must not explicitly invoke .commit()')


SessionManager = Callable[..., ContextManager[Session_t]]


class Database:
    def __init__(self, schema: DeclarativeMeta, connection_string: str) -> None:
        self.schema = schema
        self.conn_string = connection_string
        # noinspection PyUnresolvedReferences
        self.metadata = self.schema.metadata

    def connect(self, logger, echo_sql: bool = False, drop_tables: bool = False, **_kwargs) -> SessionManager:
        """
        sets up the sqlalchemy connection and declares a transaction factory context manager
        """

        # SUPPRESS-LINTER <attr added to subclass in meta.py>
        # noinspection PyUnresolvedReferences
        _connection = self.schema.connection_name

        engine = sa.create_engine(self.conn_string, echo=echo_sql)
        logger.debug(f'Created engine')

        session_constructor: Callable[[], Session_t] = sessionmaker(bind=engine, class_=Session_t)
        logger.debug(f'Bound session constructor')

        if drop_tables:
            # if input('ARE YOU SURE YOU WANT TO DROP TABLES? -> ').lower() != 'yes':
            #     exit(1)

            self.metadata.drop_all(engine)
            logger.warning(f'Dropped tables')

        self.metadata.create_all(engine)
        logger.debug(f'Mapped schema')

        @contextmanager
        def session_manager_f(expire: bool = False) -> ContextManager[Session_t]:
            """
            provide a transactional scope around a series of operations
            """
            # ? https://docs.sqlalchemy.org/en/13/orm/session_basics.html

            session = session_constructor()
            session.expire_on_commit = expire

            try:
                yield session

            except Exception as e:
                session.rollback()
                raise e

            else:
                session.context_commit()

            finally:
                session.close()

        return session_manager_f
