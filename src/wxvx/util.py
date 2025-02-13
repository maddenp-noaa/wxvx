from __future__ import annotations

import logging
from importlib import resources
from multiprocessing import Process
from pathlib import Path
from subprocess import run
from typing import cast

pkgname = __name__.split(".", maxsplit=1)[0]


class WXVXError(Exception): ...


def mpexec(cmd: str, rundir: Path, taskname: str, env: dict | None = None) -> None:
    logging.info("%s: Running in %s: %s", taskname, rundir, cmd)
    rundir.mkdir(parents=True, exist_ok=True)
    kwargs = {"check": False, "cwd": rundir, "shell": True}
    if env:
        kwargs["env"] = env
    p = Process(target=run, args=[cmd], kwargs=kwargs)
    p.start()
    p.join()


def resource(relpath: str | Path) -> str:
    with resource_path(relpath).open("r") as f:
        return f.read()


def resource_path(relpath: str | Path) -> Path:
    return cast(Path, resources.files(f"{pkgname}.resources").joinpath(str(relpath)))
