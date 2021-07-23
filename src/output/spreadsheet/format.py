import contextlib
from typing import Dict
from typing import Tuple

from xlsxwriter import Workbook as xlsxWorkbook
from xlsxwriter.format import Format as xlsxFormat

from src.output.spreadsheet.constants import FONT_NAME
from src.output.spreadsheet.constants import NUTRIENT_FAIL_COLOR_BG
from src.output.spreadsheet.constants import NUTRIENT_FAIL_COLOR_FG

__all__ = [
    'Format',
]


class Format:
    wb: xlsxWorkbook
    _cache: Dict[Tuple, xlsxFormat] = {}
    _default = {
        'font_name': FONT_NAME, 'valign': 'vcenter', 'align': 'center'
    }

    def __init__(self) -> None:
        self.d = type(self)._default.copy()

    def copy(self) -> 'Format':
        _f = type(self)()
        _f.d = self.d.copy()
        return _f

    def _update(self, k, v):
        self.d[k] = v
        return self

    def date(self):
        return self.num_format('m/d/yyyy')

    def size(self, pt: int):
        return self._update('font_size', pt)

    def fail_fg(self):
        return self.font_color(NUTRIENT_FAIL_COLOR_FG)

    def fail_bg(self):
        return self.bg_color(NUTRIENT_FAIL_COLOR_BG)

    def font_color(self, color: str):
        return self._update('font_color', color)

    def bg_color(self, color: str):
        return self._update('bg_color', color)

    def white(self):
        return self.bg_color('white')

    def border_right(self):
        return self._update('right', 1)

    def border_left(self):
        return self._update('left', 1)

    def border_top(self):
        return self._update('top', 1)

    def border_bottom(self, apply: bool = True):
        if apply:
            return self._update('bottom', 1)
        return self

    def bold(self):
        return self._update('bold', True)

    def align(self, alignment: str):
        return self._update('align', alignment)

    def num_format(self, format_string: str):
        return self._update('num_format', format_string)

    def percentage(self):
        return self.num_format('0%')

    def left(self):
        return self.align('left')

    def center(self):
        return self.align('center')

    def right(self):
        return self.align('right')

    def top(self):
        return self._update('valign', 'top')

    def bottom(self):
        return self._update('valign', 'vbottom')

    def rotated(self):
        return self._update('rotation', -90)

    def render(self) -> xlsxFormat:
        cla = type(self)
        frozen_d = tuple(sorted(self.d.items()))
        _fmt = cla._cache.get(frozen_d)
        if not _fmt:
            _fmt = cla.wb.add_format(self.d)
            cla._cache[frozen_d] = _fmt
        return _fmt

    @classmethod
    def start(cls, wb: xlsxWorkbook) -> None:
        cls._cache.clear()
        cls.wb = wb

    @classmethod
    @contextlib.contextmanager
    def white_background(cls):
        cls._default['bg_color'] = 'white'
        try:
            yield
        finally:
            cls._default.pop('bg_color')

    def __call__(self) -> xlsxFormat:
        return self.render()
