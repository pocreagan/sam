import os
import sys
from pathlib import Path

import yaml

# noinspection SpellCheckingInspection
os.environ["KIVY_NO_FILELOG"] = "1"
os.environ["KIVY_NO_ARGS"] = "1"

from kivy import Config
from kivy.resources import resource_add_path

__all__ = [
    '__RESOURCE__',
]

_root_path = getattr(sys, '_MEIPASS', None)

if _root_path is None:
    source_dir = Path(__file__).absolute().parents[1]
else:
    source_dir = Path(_root_path)


class Resource:
    def __init__(self, root_path: Path) -> None:
        self.PROJECT_ROOT = root_path
        self._root_path = self.PROJECT_ROOT / 'resources'

    def __call__(self, *path) -> str:
        return str(self._root_path.joinpath(*path))

    def font(self, *path) -> str:
        return self('font', *path)

    def img(self, *path) -> str:
        return self('img', *path)

    def dat(self, *path) -> str:
        return self('dat', *path)

    def db(self, *path) -> str:
        return self('db', *path)

    def cfg(self, *path, parse: bool = False):
        _p = self('cfg', *path)
        if _p.endswith('.yml') and parse:
            with open(_p, 'r') as rf:
                return yaml.load(rf, Loader=yaml.FullLoader)
        return _p


__RESOURCE__ = Resource(source_dir)

resource_add_path(__RESOURCE__.img())
Config.read(__RESOURCE__.cfg('kivy_config.ini'))
Config.set('kivy', 'window_icon', __RESOURCE__.img('favicon_white.ico'))
Config.write()
