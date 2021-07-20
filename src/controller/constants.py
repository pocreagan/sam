FONT_NAME = 'Corbel Light'
NUTRIENT_FAIL_COLOR_FG = '#FF0000'
NUTRIENT_FAIL_COLOR_BG = '#FF9999'
INGREDIENT_DISPLAY_NAME_MAX_WIDTH_PX = 345
STANDARD_COLUMN_WIDTH_CHAR_UNITS = 68
BORDER_CELLS_SPAN_CHAR_UNITS = 28

GUIDANCE_LEVEL_EXCEEDED_HEADER_STRING = 'Guidance Level(s) Exceeded'

SUMMARY_RESULT_HEADER = 'Result:'

# noinspection SpellCheckingInspection
SUMMARY_BLURB = 'This analysis was performed using Agile data, tolerable upper intake limits and USDA food data ' \
                'current as of the date listed above as the app version date. You are invited to review the exact ' \
                'data used in the Sam project folder. If you encounter an error or an anomalous result, or want to ' \
                'request additional foods be added to the USDA foods list, please contact Caroline Ingles. '

SUMMARY_RESULT_STRINGS = {
    True: GUIDANCE_LEVEL_EXCEEDED_HEADER_STRING,
    False: 'OK'
}

SUMMARY_COL_WIDTHS_CHAR = [
    (0, 2.),
    (1, 12.),
    (2, 20.),
    (3, 15.),
    (4, 10.),
]

for i in range(5, 50):
    SUMMARY_COL_WIDTHS_CHAR.append((i, 10.))

SUMMARY_ROW_HEIGHTS_CHAR = [
    (0, 14.)
]

REGION_COL_WIDTHS_CHAR = [
    (0, 2.),
    (1, 14.),
    (2, 24.),
]
for i in range(3, 100):
    REGION_COL_WIDTHS_CHAR.append((i, 7.))

REGION_ROW_HEIGHTS_CHAR = [
    (0, 14.),
    (1, 31.),
    (2, 31.),
]

REGION_HEADER_ROW_HEIGHT = 83.


class RegionWidths:
    STANDARD = 68
    COL_B = 122
    COL_C = 345


class FontSizes:
    STANDARD = 11
    REGION_NAME = 24


class FoodHeaders:
    FOOD_ID = 'ID'
    DESCRIPTION = 'Description'
    NUM_SERVINGS = '# of Servings'
    QTY_PER_SERVING = 'Quantity / Serving'


class CalcHeaders:
    SUM = 'Sum'
    GUIDANCE_LEVEL = 'Guidance Level ({region_name})'
    PERCENT_OF_LIMIT = '% of Guidance Level'
