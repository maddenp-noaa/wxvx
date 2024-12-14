"""
Command-line interface.
"""

import json
import logging
import sys
import yaml
from argparse import ArgumentParser, HelpFormatter, Namespace
from importlib import resources
from pathlib import Path

PKGNAME = __name__.split(".", maxsplit=1)[0]


def main() -> None:
    args = _parse_args(sys.argv[1:])
    _setup_logging(debug=args.debug)


def _parse_args(raw: list[str]) -> Namespace:
    parser = ArgumentParser(
        description=PKGNAME,
        add_help=False,
        formatter_class=lambda prog: HelpFormatter(prog, max_help_position=6),
    )
    optional = parser.add_argument_group("Optional arguments")
    optional.add_argument(
        "-c",
        "--config",
        help="Configuration file",
        metavar="FILE",
    )
    optional.add_argument(
        "-d",
        "--debug",
        action="store_true",
        help="Print all logging messages",
    )
    optional.add_argument(
        "-h",
        "--help",
        action="help",
        help="Show help and exit",
    )
    optional.add_argument(
        "-v",
        "--version",
        action="version",
        help="Show version and exit",
        version=f"{Path(sys.argv[0]).name} {_version()}",
    )
    return parser.parse_args(raw)


def _setup_logging(debug: bool = False) -> None:
    logging.basicConfig(
        datefmt="%Y-%m-%dT%H:%M:%S",
        format="[%(asctime)s] %(levelname)8s %(message)s",
        level=logging.DEBUG if debug else logging.INFO,
    )


def _version() -> str:
    with resources.as_file(resources.files(f"{PKGNAME}.resources")) as prefix:
        with open(prefix / "info.json", "r", encoding="utf-8") as f:
            info = json.load(f)
    return "version %s build %s" % (info["version"], info["buildnum"])
