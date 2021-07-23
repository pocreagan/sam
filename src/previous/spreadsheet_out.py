import os
import subprocess
from pathlib import Path
from typing import List
from typing import Tuple

from xlsxwriter import Workbook as xlsxWorkbook
from xlsxwriter.worksheet import Worksheet as xlsxWorksheet

from src import __RESOURCE__
from src.output.spreadsheet.format import Format
from src.model.enums import NutrientLimitType
from src.previous.constants import *
from src.previous.objects import *

WORKSHEET_PROTECTION_PASSWORD = 'sam'


def start_sheet(wb: xlsxWorkbook, name: str,
                col_widths: List[Tuple[int, int, int]],
                row_heights: List[Tuple[int, int]], zoom: int = None) -> xlsxWorksheet:
    ws = wb.add_worksheet(name)
    if WORKSHEET_PROTECTION_PASSWORD:
        ws.protect(WORKSHEET_PROTECTION_PASSWORD)

    for row, height in row_heights:
        ws.set_row(row, height=height)

    for col, width in col_widths:
        ws.set_column(col, col, width=width)

    if zoom:
        ws.set_zoom(zoom)

    return ws


def make_region(wb: xlsxWorkbook, region: Region) -> None:
    bad_nutrients = [nut for nut in region.nutrients if nut.exceeds_guidance_level]

    # row_heights = REGION_ROW_HEIGHTS_CHAR + [(6 + min(1, len(bad_nutrients)), REGION_HEADER_ROW_HEIGHT)]
    ws = start_sheet(wb, region.name, REGION_COL_WIDTHS_CHAR, REGION_ROW_HEIGHTS_CHAR, 100)

    with Format.white_background():
        # write region info at the top left
        row = 1
        ws.merge_range(row, 1, row, 4, region.name, Format().size(FontSizes.REGION_NAME)())
        row += 1
        fmt = Format()()
        fmt.set_text_wrap()
        ws.merge_range(row, 1, row, 4, region.limits_source, fmt)
        row += 2

        # write bad nutrients summary
        ws.merge_range(row, 1, row, 4, GUIDANCE_LEVEL_EXCEEDED_HEADER_STRING, Format().border_bottom()())
        row += 1
        if bad_nutrients:
            for nut in bad_nutrients:
                ws.merge_range(row, 1, row, 4, nut.name, Format().fail_fg()())
                row += 1

        else:
            ws.merge_range(row, 1, row, 4, 'NONE', Format()())
            row += 1

        ws.conditional_format(1, 1, row, 4, {'type': 'blanks', 'format': Format()()})

    row += 1

    # write food headers
    ws.write_string(row, 1, FoodHeaders.FOOD_ID, Format().bold().right().bottom().border_bottom()())
    ws.write_string(row, 2, FoodHeaders.DESCRIPTION, Format().bold().bottom().border_bottom()())
    ws.write_string(row, 3, FoodHeaders.NUM_SERVINGS, Format().rotated().bottom().border_bottom()())
    ws.write_string(row, 4, FoodHeaders.QTY_PER_SERVING, Format().rotated().bottom().border_right().border_bottom()())

    # write nutrient headers
    for i, nut in enumerate(region.nutrients):
        fmt = Format().rotated().bottom().border_bottom()
        if nut.exceeds_guidance_level:
            fmt.fail_bg().bold()
        ws.merge_range(1, 5 + i, row, 5 + i, nut.name, fmt())

    row += 1
    for i, food in enumerate(region.foods):
        is_last_row = i == (len(region.foods) - 1)

        # write food metadata
        ws.write_string(row, 1, food.food_id, Format().bold().right().border_left().border_bottom(is_last_row)())
        ws.write_string(row, 2, food.description, Format().left().border_bottom(is_last_row)())
        ws.write_number(row, 3, food.num_servings, Format().border_bottom(is_last_row)())
        ws.write_string(row, 4, food.qty_per_serving or 'NA', Format().border_right().border_bottom(is_last_row)())

        # write /nutrient amount for one food
        for j, nut in enumerate(region.nutrients):

            fmt = Format().border_bottom(is_last_row)
            if nut.exceeds_guidance_level:
                fmt.fail_bg().bold()
            if j == (len(region.nutrients) - 1):
                fmt.border_right()

            amount = nut.amounts[i]
            if amount is None:
                ws.write_string(row, 5 + j, 'NL', fmt())
            else:
                ws.write_number(row, 5 + j, nut.amounts[i], fmt())

        row += 1

    # write calculation rows
    ws.write_string(row, 4, CalcHeaders.SUM, Format().bold().right().border_right()())
    ws.write_string(row + 1, 4, CalcHeaders.GUIDANCE_LEVEL.format(
        region_name=region.name,
    ), Format().bold().right().border_right()())
    ws.write_string(row + 2, 4, CalcHeaders.PERCENT_OF_LIMIT, Format().bold().right().border_right()())

    for i, nut in enumerate(region.nutrients):

        cells = [(Format(), nut.sum)]
        if nut.is_limited:
            cells.extend([(Format(), nut.limit), (Format().percentage(), nut.percent_of_limit)])
        elif nut.limit == NutrientLimitType.ND:
            cells.extend([(Format(), 'ND'), (Format(), '')])

        for j, (fmt, num) in enumerate(cells):
            if nut.exceeds_guidance_level:
                fmt.fail_bg().bold()

            if isinstance(num, str):
                ws.write_string(row + j, 5 + i, num, fmt())

            else:
                ws.write_number(row + j, 5 + i, num, fmt())


def make_summary(wb: xlsxWorkbook, output: Output) -> None:
    ws = start_sheet(wb, 'Summary', SUMMARY_COL_WIDTHS_CHAR, SUMMARY_ROW_HEIGHTS_CHAR, 130)
    ws.insert_image(1, 1, __RESOURCE__.img('summary_logo.png'))

    with Format.white_background():

        row = 10
        for label, timestamp in output.versions:
            ws.write_string(row, 1, label, Format().bold().right()())
            ws.write_datetime(row, 2, timestamp, Format().date().left()())
            row += 1

        row += 1
        ws.write_string(row, 1, SUMMARY_RESULT_HEADER, Format().bold().right()())
        for region in output.regions:
            ws.write_string(row, 2, region.name, Format().right()())
            is_bad = region.exceeds_guidance_level
            fmt = Format().left()
            if is_bad:
                fmt.fail_fg().bold()

            ws.write_string(row, 3, SUMMARY_RESULT_STRINGS[is_bad], fmt())
            row += 1

        row += 1
        fmt = Format().top()()
        fmt.set_text_wrap()
        ws.merge_range(row, 1, row + 6, 3, SUMMARY_BLURB, fmt)

        ws.conditional_format(1, 1, row + 6, 4, {'type': 'blanks', 'format': Format()()})

    ws.set_first_sheet()


def make(output: Output, name: str) -> None:
    output_dir = Path(os.path.expanduser("~/Desktop/Sam/Results"))
    os.makedirs(output_dir, exist_ok=True)
    output_file_path = output_dir / f'{name}.xlsx'
    if output_file_path.exists():
        os.remove(output_file_path)

    try:
        with xlsxWorkbook(str(output_file_path)) as wb:
            Format.wb = wb

            make_summary(wb, output)
            for region in output.regions:
                make_region(wb, region)

    except Exception:
        os.remove(output_file_path)
        raise

    else:
        subprocess.Popen(f'"{output_file_path}"', shell=True)
