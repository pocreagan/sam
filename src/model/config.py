import datetime
from dataclasses import dataclass
from dataclasses import InitVar

__all__ = [
    'Model',
    'Build',
]


@dataclass
class Model:
    USDA_API_KEY: str
    USDA_REST_ENDPOINT: str
    AGILE_FILE_PATH: str
    DATA_FILE_PATH: str
    CONNECTION_STRING_SUFFIX: str
    BUILD_VERSION: datetime.datetime = datetime.datetime.now()
    APP_VERSION: datetime.datetime = datetime.datetime.now()


@dataclass
class Build:
    commit: str
    timestamp: InitVar[str]
    app_version: datetime.datetime = None

    def __post_init__(self, timestamp: str) -> None:
        self.app_version = datetime.datetime.strptime(timestamp, '%Y%m%d-%H%M%S')
