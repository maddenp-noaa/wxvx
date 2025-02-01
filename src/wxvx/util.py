from __future__ import annotations

from importlib import resources
from pathlib import Path
from typing import cast

pkgname = __name__.split(".", maxsplit=1)[0]


class WXVXError(Exception): ...


def resource(relpath: str | Path) -> str:
    with resource_path(relpath).open("r") as f:
        return f.read()


def resource_path(relpath: str | Path) -> Path:
    return cast(Path, resources.files(f"{pkgname}.resources").joinpath(str(relpath)))
