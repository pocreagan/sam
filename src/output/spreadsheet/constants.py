FONT_NAME = 'Corbel Light'
NUTRIENT_FAIL_COLOR_FG = '#FF0000'
NUTRIENT_FAIL_COLOR_BG = '#FF9999'

COL_WIDTHS = [
    (0, 2.),
    (1, 14.),
    (2, 24.),
]
for i in range(3, 200):
    COL_WIDTHS.append((i, 7.))


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
    GUIDANCE_LEVEL = 'Guidance Level'
    PERCENT_OF_LIMIT = '% of GL'
