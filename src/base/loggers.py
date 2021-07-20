import contextlib
import logging
import logging.handlers
import sys
import time

from typing import Dict

__all__ = [
    'Logger',
    'format_time',
]

_trace = getattr(logging, 'TRACE', 9)


def display_time(_te: float) -> str:
    if _te < 10.:
        return f'{_te:.03f}'
    elif _te < 100.:
        return f'{_te:.02f}'
    else:
        return f'{_te:.01f}'


def format_time(_te: float) -> str:
    if _te < .001:
        return display_time(_te * 1000000.) + 'usec'
    elif _te < 1.:
        return display_time(_te * 1000.) + 'msec'
    else:
        return display_time(_te) + 'sec'


# noinspection PyProtectedMember
class Logger:
    def __init__(self, category: str, logger=None, q=None) -> None:
        self.message_start = f'{category[:12] if len(category) > 12 else category}: '
        if logger:
            self.logger = logger
        elif q is not None:
            self.logger = logging.getLogger(__name__)
            # list(map(self.logger.removeHandler, self.logger.handlers))
            ch = logging.handlers.QueueHandler(q)
            ch.setLevel(_trace)
            self.logger.addHandler(ch)
            self.logger.setLevel(_trace)
        else:
            raise TypeError('must provide @logger or @q')

    @staticmethod
    def _check_exc_info(exc_info: bool, kwargs: Dict) -> Dict:
        if exc_info and sys.exc_info() != (None, None, None):
            kwargs['exc_info'] = True
        else:
            kwargs['exc_info'] = False
        return kwargs

    # noinspection PyPep8Naming
    def isEnabledFor(self, log_level: int) -> bool:
        return self.logger.isEnabledFor(log_level)

    def handle(self, record: logging.LogRecord):
        return self.logger.handle(record)

    def log(self, level: int, *message, **kwargs) -> None:
        if self.isEnabledFor(level):
            self.logger._log(
                level, self.message_start + " ".join(list(map(str, message))), (), **kwargs,
            )

    def trace(self, *message, **kwargs) -> None:
        if self.isEnabledFor(_trace):
            self.logger._log(
                _trace, self.message_start + " ".join(list(map(str, message))), (), **kwargs,
            )

    def debug(self, *message, **kwargs) -> None:
        if self.isEnabledFor(logging.DEBUG):
            self.logger._log(
                logging.DEBUG, self.message_start + " ".join(list(map(str, message))), (), **kwargs,
            )

    def info(self, *message, **kwargs) -> None:
        if self.isEnabledFor(logging.INFO):
            self.logger._log(
                logging.INFO, self.message_start + " ".join(list(map(str, message))), (), **kwargs,
            )

    @contextlib.contextmanager
    def timer(self, string: str):
        _ti = time.perf_counter()

        try:
            yield

        except Exception:
            raise

        else:
            self.debug(f'{string} ({format_time(time.perf_counter() - _ti)})')

    def warning(self, *message, exc_info=True, **kwargs) -> None:
        if self.isEnabledFor(logging.WARNING):
            self.logger._log(
                logging.WARNING, self.message_start + " ".join(list(map(str, message))),
                (), **self._check_exc_info(exc_info, kwargs),
            )

    warn = warning

    def exception(self, *message, exc_info=True, **kwargs) -> None:
        if self.isEnabledFor(logging.ERROR):
            self.logger._log(
                logging.ERROR, self.message_start + " ".join(list(map(str, message))),
                (), **self._check_exc_info(exc_info, kwargs),
            )

    error = exception

    def critical(self, *message, exc_info=True, **kwargs) -> None:
        if self.isEnabledFor(logging.CRITICAL):
            self.logger._log(
                logging.CRITICAL, self.message_start + " ".join(list(map(str, message))),
                (), **self._check_exc_info(exc_info, kwargs),
            )

    def spawn(self, category: str) -> 'Logger':
        if len(category) > 12:
            category = category[:12]
        return type(self)(category, logger=self.logger)
