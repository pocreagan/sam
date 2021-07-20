__all__ = [
    'ParseFailure',
    'PackageFailure',
]


class ParseFailure(Exception):
    pass


class PackageFailure(Exception):
    pass
