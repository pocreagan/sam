import datetime
import os
import subprocess
from operator import attrgetter
from pathlib import Path
from typing import List
from typing import Tuple

from xlsxwriter import Workbook as xlsxWorkbook
from xlsxwriter.worksheet import Worksheet as xlsxWorksheet

from src import __RESOURCE__
from src.model.enums import NutrientLimitType
from src.output.objects import *
from src.output.spreadsheet.format import Format
from src.previous.constants import *

__all__ = [
    'write_spreadsheet',
]


def start_sheet(wb: xlsxWorkbook, name: str,
                col_widths: List[Tuple[int, int, int]],
                row_heights: List[Tuple[int, int]],
                zoom: int = None,
                password: str = None) -> xlsxWorksheet:
    ws = wb.add_worksheet(name)
    if password:
        ws.protect(password)

    for row, height in row_heights:
        ws.set_row(row, height=height)

    for col, width in col_widths:
        ws.set_column(col, col, width=width)

    if zoom:
        ws.set_zoom(zoom)

    return ws


def write_metadata(ws: xlsxWorksheet, app_version: datetime.datetime) -> int:
    ws.insert_image(1, 1, __RESOURCE__.img('spreadsheet-header.png'))

    with Format.white_background():
        row = 2
        for label, timestamp in [('App Version:', app_version), ('Performed:', datetime.datetime.now())]:
            ws.write_string(row, 4, label, Format().bold().right()())
            ws.merge_range(row, 5, row, 6, timestamp.strftime('%m/%d/%Y'), Format().left()())
            row += 1

        ws.conditional_format(1, 1, row+1, 6, {'type': 'blanks', 'format': Format()()})

    return row + 3


def write_sums(ws: xlsxWorksheet, row: int, output: Output) -> int:
    ws.write_string(row, 4, CalcHeaders.SUM, Format().right().bold().border_right()())
    for col, nutrient in enumerate(output.nutrients, start=5):
        ws.write_number(row, col, nutrient.sum, Format()())

    return row + 1


def write_regions(ws: xlsxWorksheet, row: int, output: Output) -> int:
    for region in output.regions:
        top, bottom = row, row + 1

        fmt = Format().center().size(16).border_left().border_top()
        if region.any_guidance_level_exceeded:
            fmt.bold().fail_fg()

        ws.merge_range(top, 1, bottom, 2, region.obj.name, fmt())
        ws.write_string(top, 3, '', Format().border_top()())
        ws.merge_range(
            top, 3, top, 4, CalcHeaders.GUIDANCE_LEVEL, Format().border_top().border_right().bold().right()()
        )
        ws.merge_range(bottom, 3, bottom, 4, CalcHeaders.PERCENT_OF_LIMIT, Format().border_right().bold().right()())

        col = 5
        for nutrient in output.nutrients:
            fmt = Format()

            nutrient_result = nutrient.results[region.obj.name]
            if nutrient_result.is_limited:
                if nutrient_result.guidance_level_exceeded:
                    fmt.bold().fail_bg()
                ws.write_number(top, col, nutrient_result.guidance_level, fmt.copy().border_top()())
                ws.write_number(bottom, col, nutrient_result.percent_of_guidance_level, fmt.copy().percentage()())

            else:
                top_s = ''
                if nutrient_result.guidance_level == NutrientLimitType.ND:
                    top_s = nutrient_result.guidance_level.name

                ws.write_string(top, col, top_s, fmt.copy().border_top()())
                ws.write_string(bottom, col, '', fmt.copy()())

            col += 1

        ws.write_string(top, col, '', Format().border_left()())
        ws.write_string(bottom, col, '', Format().border_left()())

        row += 2

    return row


def write_headers(ws: xlsxWorksheet, row: int, output: Output) -> int:
    ws.write_string(row, 1, FoodHeaders.FOOD_ID, Format().border_top().border_bottom().bold().right().bottom()())
    ws.write_string(row, 2, FoodHeaders.DESCRIPTION, Format().border_top().border_bottom().bold().bottom().left()())
    ws.write_string(row, 3, FoodHeaders.NUM_SERVINGS, Format().border_top().border_bottom().rotated().bottom()())
    ws.write_string(row, 4, FoodHeaders.QTY_PER_SERVING,
                    Format().border_top().border_bottom().rotated().bottom().border_right()())

    for col, nutrient in enumerate(output.nutrients, start=5):
        ws.write_string(row, col, nutrient.canonical.name, Format().border_top().border_bottom().rotated().center()())

    return row + 1


def write_foods(ws: xlsxWorksheet, row: int, output: Output) -> None:
    col = 5
    for food in output.foods:
        ws.write_string(row, 1, food.food_id, Format().bold().right().border_left()())
        ws.write_string(row, 2, food.description, Format().left()())
        ws.write_number(row, 3, food.num_servings, Format()())
        ws.write_string(row, 4, food.qty_per_serving or 'NA', Format().border_right()())

        col = 5
        for nutrient in output.nutrients:
            value = nutrient.amount_per_food[food.food_id]
            (ws.write_string if isinstance(value, str) else ws.write_number)(row, col, value, Format()())
            col += 1

        ws.write_string(row, col, '', Format().border_left()())
        row += 1

    for _col in range(1, col):
        ws.write_string(row, _col, '', Format().border_top()())


def write_spreadsheet(output: Output, directory: Path, file_name: str, app_version: datetime.datetime) -> None:
    output.regions.sort(key=attrgetter('bad_first_then_alphabetical'))
    output.nutrients.sort(key=attrgetter('bad_first_then_canonical_order'))

    os.makedirs(directory, exist_ok=True)
    output_file_path = directory / f'{file_name}.xlsx'
    if output_file_path.exists():
        os.remove(output_file_path)

    try:
        with xlsxWorkbook(str(output_file_path)) as wb:
            Format.wb = wb

            ws = start_sheet(wb, 'Sam', COL_WIDTHS, [], 130, None)
            row = write_metadata(ws, app_version)
            row = write_sums(ws, row, output)
            row = write_regions(ws, row, output)
            row = write_headers(ws, row, output)
            write_foods(ws, row, output)

    except Exception:
        os.remove(output_file_path)
        raise

    else:
        subprocess.Popen(f'"{output_file_path}"', shell=True)
