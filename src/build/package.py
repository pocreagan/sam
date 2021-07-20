import contextlib
import os
import shutil
from pathlib import Path
from typing import Any
from typing import Dict

import yaml

from src import __RESOURCE__
from src.base import loggers
from src.build.exceptions import PackageFailure

__all__ = [
    'package',
]

UPX_DIR = 'c:/upx_dir'
TEMPLATE_DIR = __RESOURCE__.PROJECT_ROOT / 'spec'
BUILD_DIR = __RESOURCE__.PROJECT_ROOT / 'build'
SPEC_DIR = BUILD_DIR / 'spec'
WARNINGS_DIR = BUILD_DIR / 'warnings'


def update_spec_file(spec_name: str, spec_data: Dict[str, Any]) -> None:
    with open(TEMPLATE_DIR / spec_name, 'r') as rf:
        spec_text = rf.read()

    for k, v in spec_data.items():
        spec_text = spec_text.replace(k, str(v))

    os.makedirs(SPEC_DIR, exist_ok=True)

    if (SPEC_DIR / spec_name).exists():
        with open(SPEC_DIR / spec_name, 'r') as existing:
            if spec_text == existing.read():
                return

    with open(SPEC_DIR / spec_name, 'w+') as wf:
        wf.write(spec_text)


@contextlib.contextmanager
def working_directory(directory: Path):
    _prev = os.getcwd()
    os.chdir(directory)
    try:
        yield
    finally:
        os.chdir(_prev)


def move_warnings(build_type: str) -> None:
    previous = BUILD_DIR / build_type
    if previous.exists():
        os.makedirs(WARNINGS_DIR, exist_ok=True)
        future = WARNINGS_DIR / build_type
        if future.exists():
            shutil.rmtree(str(future))

        shutil.move(str(previous), str(future))


def build(log: loggers.Logger, spec_data: Dict[str, Any], build_type: str, args: str) -> None:
    log.info(f'Initiating {build_type.lower()} build from `{SPEC_DIR}`')

    spec_name = f'{build_type}.spec'
    update_spec_file(spec_name, spec_data)

    with working_directory(__RESOURCE__.PROJECT_ROOT):
        try:
            system_call = f'pipenv run python -m PyInstaller "{SPEC_DIR / spec_name}" {args}'
            log.info(system_call + '\n\n\n')
            exit_code = os.system(system_call)
            if exit_code:
                raise PackageFailure(str(exit_code))

        finally:
            move_warnings(build_type)

    log.info(f'{build_type} build successful' + '\n\n\n')


def update_build_config(log: loggers.Logger) -> None:
    import datetime
    import subprocess

    log.info('Checking working tree...')
    if subprocess.check_output("git diff --stat", shell=True).decode().strip() != '':
        raise PackageFailure('DIRTY WORKING TREE. COMMIT CHANGES TO BUILD.')

    log.info('Working tree clean')

    log_data = dict(
        commit=subprocess.run(['git', 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip(),
        timestamp=datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    )

    with open(__RESOURCE__.cfg('build.yml'), 'w+') as wf:
        yaml.dump(log_data, wf)

    log.info('Updated build log')


def package(log: loggers.Logger, debug: bool, release: bool, spec_data: Dict[str, Any]) -> None:
    update_build_config(log)

    if debug:
        # noinspection SpellCheckingInspection
        build(log, spec_data, 'Debug', '--noconfirm')

    if release:
        if not Path(UPX_DIR).exists():
            raise PackageFailure('Release build cannot succeed with UPX')

        build(log, spec_data, 'Release', f'--upx-dir="{UPX_DIR}"')
