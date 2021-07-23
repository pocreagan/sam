import datetime
from typing import List
from typing import Type
from typing import TypeVar

from kivy import Logger
from sqlalchemy.orm import joinedload

from src import __RESOURCE__
from src import model
from src.base import loggers
from src.model import db
from src.model.connection import Session_t

__all__ = []

from src.previous import spreadsheet_out

log = loggers.Logger('View', Logger)

_T = TypeVar('_T')


def get_from_values(session: Session_t, cla: Type[_T], column: str, values: List[str]) -> List[_T]:
    # noinspection PyProtectedMember
    return session.query(cla) \
        .filter(getattr(cla, column).in_(values)) \
        .options(joinedload(cla._nutrient_data)) \
        .all()


def test_consolidated() -> None:
    session_manager = model.Database(
        db.Schema, f'sqlite:///{__RESOURCE__.db("backend.db")}'
    ).connect(log.spawn('Database'))

    with session_manager() as session:
        nutrients: List[db.Nutrient] = session.query(db.Nutrient).all()
        regions = get_from_values(session, db.Region, 'name', ['US & Canada', 'EU'])
        foods = get_from_values(session, db.Food, 'food_id', ['F123', 'F124', 'F125', 'F1234', 'F1245'])

    app_version = datetime.datetime.now()
    # sheet_name = f'Sam-{app_version.strftime("%Y%m%d-%H%M%S")}'
    sheet_name = f'Sam-test_consolidated-output'

    spreadsheet_out.make_consolidated(nutrients, regions, foods, app_version, sheet_name)
