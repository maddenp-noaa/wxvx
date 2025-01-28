from contextlib import contextmanager
from importlib import resources
from pathlib import Path
from typing import Generator, TextIO

pkgname = __name__.split(".", maxsplit=1)[0]


class WXVXError(Exception): ...


@contextmanager
def resource(relpath: str) -> Generator[TextIO, None, None]:
    with resource_path(relpath).open("r") as f:
        yield f


def resource_path(relpath: str) -> Path:
    with resources.as_file(resources.files(f"{pkgname}.resources")) as prefix:
        return prefix / relpath
