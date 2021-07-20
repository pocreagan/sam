import time

import click

from src import __RESOURCE__
from src.base import loggers
from src.build.exceptions import PackageFailure
from src.build.exceptions import ParseFailure
from src.build.package import package
from src.build.parse import Parser

__all__ = []

BUILD_DIR = __RESOURCE__.PROJECT_ROOT / 'build'

# noinspection SpellCheckingInspection
API_KEY = r'IAq4gn3KahA24GAAeEOZLNO6ghwzTWWtU7awLFw5'
USDA_URL = f'https://api.nal.usda.gov/fdc/v1/foods/search?api_key={API_KEY}'
CONN_STRING = 'sqlite:///' + __RESOURCE__.db('backend.db')
DIST_PATH = __RESOURCE__.PROJECT_ROOT / 'dist'
DAT_PATH = __RESOURCE__.PROJECT_ROOT / 'dat'

SPEC_CHANGES = {
    '__ICON_PATH__': __RESOURCE__.img('android-chrome-512x512_trans.ico'),
    '__ENTRY_POINT__': __RESOURCE__.PROJECT_ROOT / 'src' / 'app.py',
    '__ROOT_DIR__': __RESOURCE__.PROJECT_ROOT, '__DIST_PATH__': DIST_PATH,
    '__DAT_PATH__': __RESOURCE__.PROJECT_ROOT / 'build', '__APP_NAME__': 'Sam',
}


@click.command()
@click.option('--debug', is_flag=True)
@click.option('--release', is_flag=True)
def main(debug: bool, release: bool) -> None:
    import kivy
    log = loggers.Logger('Build', kivy.Logger)

    ti = time.perf_counter()
    log.info('Initiating parse...')
    # noinspection PyBroadException
    try:
        Parser(log).run(DAT_PATH / 'Data.xlsx',
                        DAT_PATH / 'Agile.xlsx',
                        USDA_URL, CONN_STRING, )
        log.info('Parse successful' + '\n\n\n')

        if debug or release:
            package(log, debug, release, SPEC_CHANGES)
            log.info('Packaging successful')

        else:
            log.warning('Packaging was not requested')

    except ParseFailure:
        log.error('Data validation failed - build aborted')
        exit(1)

    except PackageFailure as e:
        log.error(f'Packaging failed')
        try:
            exit(int(str(e)))
        except ValueError:
            exit(1)

    except Exception:
        log.error(f'Build failed', exc_info=True)
        exit(1)

    if release:
        log.error('No release action at this time', exc_info=False)

    else:
        log.warning('Release was not requested')

    log.info(f'Exiting after {loggers.format_time(time.perf_counter() - ti)}')


if __name__ == '__main__':
    main()
