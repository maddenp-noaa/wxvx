from __future__ import annotations

import logging
import sys
from contextlib import contextmanager
from datetime import datetime, timedelta
from functools import cache
from importlib import resources
from multiprocessing.pool import Pool
from pathlib import Path
from signal import SIG_IGN, SIGINT, signal
from subprocess import run
from typing import TYPE_CHECKING, NoReturn, cast, overload

if TYPE_CHECKING:
    from collections.abc import Iterator

pkgname = __name__.split(".", maxsplit=1)[0]

LINETYPE = {
    "FSS": "nbrcnt",
    "ME": "cnt",
    "PODY": "cts",
    "RMSE": "cnt",
}


class WXVXError(Exception): ...


@contextmanager
def atomic(path: Path) -> Iterator[Path]:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = Path("%s.tmp" % path)
    yield tmp
    tmp.rename(path)


@overload
def expand(start: datetime, step: timedelta, stop: datetime) -> list[datetime]: ...
@overload
def expand(start: timedelta, step: timedelta, stop: timedelta) -> list[timedelta]: ...
def expand(start, step, stop):
    if stop < start:
        raise WXVXError("Stop time %s precedes start time %s" % (stop, start))
    xs = [start]
    while (x := xs[-1]) < stop:
        xs.append(x + step)
    return xs


def fail(msg: str | None = None, *args) -> NoReturn:
    if msg:
        logging.error(msg, *args)
    sys.exit(1)


@cache
def get_pool():
    return Pool(initializer=signal, initargs=(SIGINT, SIG_IGN))


def mpexec(cmd: str, rundir: Path, taskname: str, env: dict | None = None) -> None:
    logging.info("%s: Running in %s: %s", taskname, rundir, cmd)
    rundir.mkdir(parents=True, exist_ok=True)
    kwargs = {"check": False, "cwd": rundir, "shell": True}
    if env:
        kwargs["env"] = env
    get_pool().apply(run, [cmd], kwargs)


def resource(relpath: str | Path) -> str:
    with resource_path(relpath).open("r") as f:
        return f.read()


def resource_path(relpath: str | Path) -> Path:
    return cast(Path, resources.files(f"{pkgname}.resources").joinpath(str(relpath)))


def to_datetime(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(value)


def to_timedelta(value: str | int) -> timedelta:
    if isinstance(value, int):
        return timedelta(hours=value)
    keys = ["hours", "minutes", "seconds"]
    args = dict(zip(keys, map(int, value.split(":"))))
    return timedelta(**args)
