import contextlib
import dataclasses
import functools
import io
import time
from collections import defaultdict
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from itertools import count
from pathlib import Path
from typing import ContextManager
from typing import DefaultDict
from typing import Deque
from typing import Dict
from typing import Iterator
from typing import List
from typing import Optional
from typing import Tuple
from typing import Type
from typing import TypeVar
from typing import Union

import pandas as pd
from requests_toolbelt import threaded

from src.base import loggers
from src.base.loggers import format_time
from src.build.exceptions import ParseFailure
from src.model import Database
from src.model import db
from src.model import SessionManager
from src.model.enums import FoodSource
from src.model.enums import NutrientLimitType

NUTRIENT_START_COLUMN_INDEX = 3


@dataclasses.dataclass(eq=True)
class CanonicalNameRatio:
    name_id: int
    ratio: float

    @classmethod
    @functools.lru_cache(maxsize=256)
    def make(cls, name_id: int, ratio: float) -> 'CanonicalNameRatio':
        return cls(name_id, ratio)


@dataclasses.dataclass(eq=True)
class USDANutrient:
    name_id: int
    multiplier: float


@dataclasses.dataclass
class USDA:
    foods: Dict[int, float] = dataclasses.field(default_factory=dict)
    nutrients: Dict[int, USDANutrient] = dataclasses.field(default_factory=dict)


@dataclasses.dataclass
class Model:
    _nutrients: dataclasses.InitVar[Deque[db.Nutrient]]
    canonical_ids: List[int] = dataclasses.field(default_factory=list)
    canonical_names: List[str] = dataclasses.field(default_factory=list)
    canonical_name_to_nutrient: Dict[str, db.Nutrient] = dataclasses.field(default_factory=dict)
    id_to_nutrient: Dict[int, db.Nutrient] = dataclasses.field(default_factory=dict)
    aliases: Dict[str, CanonicalNameRatio] = dataclasses.field(default_factory=dict)
    agile_column_multipliers: Dict[str, float] = dataclasses.field(default_factory=dict)
    usda: USDA = dataclasses.field(default_factory=USDA)

    def __post_init__(self, _nutrients: Deque[db.Nutrient]) -> None:
        for nut in _nutrients:
            self.canonical_ids.append(nut.name_id)
            self.canonical_names.append(nut.name)
            self.id_to_nutrient[nut.name_id] = nut
            self.canonical_name_to_nutrient[nut.name] = nut

    def check_is_aliased(self, i: int, k: str) -> None:
        if k not in self.aliases:
            raise ParseFailure(f'row#{i} nutrient name `{k}` not aliased')

    def check_is_canonical(self, i: int, k: Union[float, str]) -> None:
        if isinstance(k, (int, float)):
            if k not in self.id_to_nutrient:
                raise ParseFailure(
                    f'row#{i} canonical name `{self.id_to_nutrient[int(k)].name}` not in CanonicalNames')
        elif k not in self.canonical_name_to_nutrient:
            raise ParseFailure(f'row#{i} canonical name `{k}` not in CanonicalNames')


DATABASE_COMPLETE = object()


@contextlib.contextmanager
def worksheet(log: loggers.Logger, wb: Dict[str, pd.DataFrame], name: str,
              columns: Optional[List[str]]) -> ContextManager['WorkSheet']:
    ti = time.perf_counter()
    ws: pd.DataFrame = wb[name]
    if columns:
        ws.drop(columns=ws.columns.difference(columns), inplace=True)
    try:
        yield WorkSheet(ws)
    except Exception as e:
        if isinstance(e, ParseFailure):
            raise ParseFailure(f'{name} {str(e)}').with_traceback(e.__traceback__)
        raise ParseFailure(f'{name}') from e
    else:
        log.debug(f'Parsed {name} ({format_time(time.perf_counter() - ti)})')


def read_workbook(logger: loggers.Logger, fp: Path, sheets: List[str]) -> Dict[str, pd.DataFrame]:
    log = logger.spawn(fp.name)
    ti = time.perf_counter()
    log.debug(f'Loading `{fp.name}`...')
    wb = pd.read_excel(fp, sheet_name=sheets)
    log.info(f'Loaded {fp.name} ({format_time(time.perf_counter() - ti)})')
    return wb


def read_workbook_buffer(logger: loggers.Logger, fp: Path, sheets: List[str]) -> Dict[str, pd.DataFrame]:
    log = logger.spawn(fp.name)
    ti = time.perf_counter()
    with io.BytesIO() as buffer, open(fp, 'rb') as f:
        buffer.write(f.read())
        log.debug(f'Loading `{fp.name}`...')
        wb = pd.read_excel(buffer, sheet_name=sheets)
        log.info(f'Loaded {fp.name} ({format_time(time.perf_counter() - ti)})')
    return wb


@contextlib.contextmanager
def workbook(
        log: loggers.Logger, wb: Union[Dict[str, pd.DataFrame], pd.DataFrame]
) -> ContextManager[Dict[str, pd.DataFrame]]:
    ti = time.perf_counter()
    log.debug(f'Parsing...')

    try:
        yield wb
    except Exception:
        raise
    else:
        log.info(f'Finished parsing ({format_time(time.perf_counter() - ti)})')


@dataclasses.dataclass
class WorkSheet:
    df: pd.DataFrame

    @property
    def enum(self) -> Iterator[Tuple[int, Tuple]]:
        return enumerate(self.df.itertuples(index=False, name=None), start=2)  # type: ignore

    @property
    def d_l(self) -> List[Dict]:
        return self.df.to_dict('records')


_K = TypeVar('_K')
_V = TypeVar('_V')


def check_and_insert(log: loggers.Logger, row_num: int, d: Dict[_K, _V], k: _K, v: _V, err_s: str) -> None:
    existing_value = d.get(k)
    if existing_value is None:
        d[k] = v
    elif existing_value == v:
        log.warning(f'row#{row_num} {err_s} duplicated')
    else:
        raise ParseFailure(f'row#{row_num} {err_s} duplicated with different value')


def resolve(future):
    e = future.exception()
    if e:
        raise e
    return future.result()


class Parser:
    log: loggers.Logger
    model: Model
    session_manager: SessionManager
    threads: ThreadPoolExecutor

    def __init__(self, root_logger: loggers.Logger) -> None:
        self.log = root_logger.spawn('Parser')
        self.q = deque()

    def run(self, dat_fp: Path, agile_fp: Path, usda_url: str, connection_string: str) -> None:
        ti = time.perf_counter()
        self.log.info('Building app backend...')

        with ThreadPoolExecutor(max_workers=4) as self.threads:
            dat_future = self.threads.submit(read_workbook_buffer, self.log, dat_fp,
                                             ['CanonicalNames', 'NutrientAliases', 'Limits',
                                              'AgileColumnMultipliers', 'USDAFoods', 'USDANutrients', ])
            agile_future = self.threads.submit(read_workbook_buffer, self.log, agile_fp,
                                               ['Sheet1'])
            db_future = self.threads.submit(self.init_database, connection_string)

            model: Model = self.parse_dat(resolve(dat_future))
            # usda_future = self.threads.submit(self.get_usda_data, usda_url, model)

            self.parse_agile(resolve(agile_future), model)

            # resolve(usda_future)

            resolve(db_future)
            self.persist_records()

        self.log.info(f'Built app backend ({format_time(time.perf_counter() - ti)})')

    def get_usda_data(self, _url: str, model: Model):
        log = self.log.spawn('USDAFoods')
        ti = time.perf_counter()

        requests = [{'url': _url, 'method': 'POST', 'json': {
            "query": food_id
        }} for food_id in model.usda.foods.keys()]

        log.debug(f'Requesting data from USDA Food Center...')
        responses, exceptions = threaded.map(requests, num_processes=20)

        for e in exceptions:
            raise ParseFailure('HTTP exception') from e

        log.info(f'Received data from USDA Food Center ({format_time(time.perf_counter() - ti)})')

        log.debug(f'Parsing responses...')
        ti = time.perf_counter()

        is_error = False
        food_nutrients: Dict[int, str] = {}
        staged: Deque[db.Food] = deque()

        for response in responses:
            _json = response.json()
            foods = _json['foods']
            num_foods = len(foods)

            if num_foods != 1:
                is_error = True
                query_term = _json['foodSearchCriteria']['query']
                log.error(f'Request for food_id {query_term} returned {num_foods or "no"} results', exc_info=False)
                continue

            response = foods[0]
            food_id = response['fdcId']
            description = response['description']
            food_nutrients.clear()

            for d in response['foodNutrients']:
                nutrient_id = d['nutrientId']

                usda_nutrient = model.usda.nutrients.get(nutrient_id)
                if not usda_nutrient:
                    continue

                value = round(usda_nutrient.multiplier * float(d['value']) * model.usda.foods[food_id] * .01, 6)
                if value:
                    food_nutrients[usda_nutrient.name_id] = str(value)

            if not food_nutrients:
                is_error = True
                log.error(f'Request for food_id {food_id} returned no nutrients of interest', exc_info=False)

            staged.append(db.Food(
                food_id=str(food_id), source=FoodSource.USDA,
                description=description, qty_per_serving=model.usda.foods[food_id],
                nutrients=db.NutrientData.make(food_nutrients, model.canonical_ids),
            ))

        if is_error:
            raise ParseFailure('USDA bad response(s)')

        if len(staged) != len(model.usda.foods):
            raise ParseFailure('No response to request for USDA food(s)')

        self.q.append(list(staged))

        log.info(f'Parsed USDA food data ({format_time(time.perf_counter() - ti)})')

    def parse_agile(self, wb: Dict[str, pd.DataFrame], model: Model) -> None:
        log = self.log.spawn('Agile Data')

        with workbook(log, wb) as wb:
            with worksheet(log, wb, 'Sheet1', None) as ws:
                result = ws.df.drop(columns=ws.df.columns.difference(['FormulaID', 'FormulaName']))

                with log.timer('Checking for duplicated formula IDs'):
                    duplicates = list(result['FormulaID'][result['FormulaID'].duplicated(keep='first')])
                    if duplicates:
                        for duplicate in duplicates:
                            log.error(f'formulaID `{duplicate}` duplicated', exc_info=False)
                        raise ParseFailure('One or more formulaIDs are duplicated')

                with log.timer('Filling result table with initial values'):
                    result[model.canonical_names] = 0.

                with log.timer('Merging aliases to canonical columns'):
                    for column_name in ws.df.columns[NUTRIENT_START_COLUMN_INDEX:]:
                        model.check_is_aliased(1, column_name)
                        multiplier = model.agile_column_multipliers.get(column_name)
                        if multiplier:
                            ws.df[column_name] *= multiplier
                        canonical_name = model.id_to_nutrient[model.aliases[column_name].name_id].name
                        result[canonical_name] += ws.df[column_name]

                with log.timer('Rounding'):
                    result[model.canonical_names] = result[model.canonical_names].round(9)

                with log.timer('Convert to string'):
                    string_convert_columns = ['FormulaID'] + model.canonical_names
                    result[string_convert_columns] = result[string_convert_columns].astype(str)

                with log.timer('Zeros to empty strings'):
                    result.replace(to_replace='0.0', value='', inplace=True)

                staged: Deque[db.Food] = deque()
                canonical_ids = model.canonical_ids
                with log.timer('Iterating through rows'):
                    for food_id, desc, *values in result.itertuples(index=False, name=None):
                        staged.append(db.Food(food_id=food_id,
                                              description=desc, source=FoodSource.HLF,
                                              nutrients=db.NutrientData.make(dict(zip(
                                                  canonical_ids, values)
                                              ), canonical_ids)))

                self.q.append(list(staged))

    def parse_dat(self, wb: Dict[str, pd.DataFrame]) -> Model:
        log = self.log.spawn('Data Sheet')

        staged: Deque = deque()

        with workbook(log, wb) as wb:

            with worksheet(log, wb, 'CanonicalNames', ['CanonicalName']) as ws:
                canonical_names = list(ws.df['CanonicalName'].unique())
                for i, k in enumerate(canonical_names):
                    nut = db.Nutrient(name_id=i, name=k)
                    staged.append(nut)
                model = Model(staged)

            self.q.append(list(staged))
            staged.clear()

            with worksheet(log, wb, 'USDAFoods', ['FoodID', 'QTY (g)']) as ws:
                for row_num, (food_id, qty) in ws.enum:
                    check_and_insert(log, row_num, model.usda.foods, int(food_id),
                                     round(float(qty), 6), f'qty for `{food_id}`')

            with worksheet(log, wb, 'USDANutrients', ['CanonicalName', 'NutrientID', 'Multiplier']) as ws:
                ws.df.sort_values('NutrientID', axis=0, ascending=True, inplace=True)
                for row_num, (canonical, nutrient_id, multiplier) in ws.enum:
                    model.check_is_canonical(row_num, canonical)
                    check_and_insert(log, row_num, model.usda.nutrients, int(nutrient_id),
                                     USDANutrient(name_id=model.canonical_name_to_nutrient[canonical].name_id,
                                                  multiplier=round(float(multiplier), 6)),
                                     f'canonical name `{canonical}`')

            with worksheet(log, wb, 'NutrientAliases', ['Alias', 'CanonicalName', 'Ratio']) as ws:
                for row_num, r in enumerate(ws.d_l, start=2):  # type: int, Dict[str, Union[str, float]]
                    alias = r['Alias']
                    canonical = r['CanonicalName']
                    model.check_is_canonical(row_num, canonical)
                    check_and_insert(log, row_num, model.aliases, alias, CanonicalNameRatio.make(
                        model.canonical_name_to_nutrient[canonical].name_id, r['Ratio']
                    ), f'alias `{alias}`')

            with worksheet(log, wb, 'Limits', [
                'RegionName', 'Source', 'Nutrient', 'Daily Intake', 'GuidanceLevel'
            ]) as ws:

                region_nutrient_limits: DefaultDict[str, Dict[int, str]] = defaultdict(dict)
                regions: Dict[str, db.Region] = {}

                for row_num, (region_name, nutrient_alias, daily_intake, source, limit) in ws.enum:
                    if region_name not in regions:
                        regions[region_name] = db.Region(name=region_name, source=source)

                    if isinstance(daily_intake, str):
                        try:
                            _ = NutrientLimitType[daily_intake.upper()]
                            v = -1
                        except KeyError:
                            raise ParseFailure(f'row#{row_num} Non-number DailyIntake must be ND (case insensitive)')
                    else:
                        v = round(float(limit), 6)

                    model.check_is_aliased(row_num, nutrient_alias)
                    canonical_name_id = model.aliases[nutrient_alias].name_id
                    check_and_insert(
                        log, row_num, region_nutrient_limits[region_name], canonical_name_id, str(v),
                        f'{region_name} limit for `{model.id_to_nutrient[canonical_name_id].name}`'
                    )

                for region_name, region in regions.items():
                    region.limits = db.NutrientData.make(region_nutrient_limits[region_name], model.canonical_ids)
                    staged.append(region)

            with worksheet(log, wb, 'AgileColumnMultipliers', ['ColumnName', 'Multiplier']) as ws:
                for row_num, (name, multiplier) in ws.enum:
                    model.check_is_aliased(row_num, name)
                    check_and_insert(log, row_num, model.agile_column_multipliers, name,
                                     round(float(multiplier), 6), f'column name `{name}`')

            self.q.append(list(staged))

        return model

    def init_database(self, connection_string: str) -> None:
        log = self.log.spawn('Database')

        log.debug(f'Building {connection_string}...')

        with log.timer('Built database'):
            self.session_manager = Database(db.Schema, connection_string).connect(log, False, True)

    # noinspection PyProtectedMember
    def persist_records(self) -> None:
        log = self.log.spawn('Database')
        last_pk_d: DefaultDict[Type, int] = defaultdict(lambda: 0)

        with log.timer('Persisted records'):

            with self.session_manager() as session:
                for records in self.q:
                    with log.timer(f'Added {len(records)} records'):
                        cla = type(records[-1])
                        if cla is db.Nutrient:
                            for pk, record in enumerate(records, start=last_pk_d[cla] + 1):
                                record.id = pk

                        else:
                            for (pk, record), pk_nut in zip(enumerate(records, start=last_pk_d[cla] + 1),
                                                            count(last_pk_d[db.NutrientData] + 1)):
                                record.set_id(pk, pk_nut)

                            last_pk_d[db.NutrientData] = records[-1]._nutrient_data.id
                            session.bulk_save_objects([r._nutrient_data for r in records], return_defaults=False)

                        last_pk_d[cla] = records[-1].id

                        session.bulk_save_objects(records, return_defaults=False)
