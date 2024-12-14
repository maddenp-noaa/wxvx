"""
Command-line interface.
"""

import json
import logging
import sys
from argparse import ArgumentParser, HelpFormatter, Namespace
from importlib import resources
from pathlib import Path

PKGNAME = __name__.split(".")[0]


def main() -> None:
    """
    The main entry point.
    """
    args = _parse_args(sys.argv[1:])
    _setup_logging(debug=args.debug)
    logging.info(args)


def _parse_args(raw: list[str]) -> Namespace:
    """
    Return parsed command-line arguments.

    :param raw: The raw command-line arguments to parse.
    """
    parser = ArgumentParser(
        description=PKGNAME,
        add_help=False,
        formatter_class=lambda prog: HelpFormatter(prog, max_help_position=6),
    )
    optional = parser.add_argument_group("Optional arguments")
    optional.add_argument("-d", "--debug", action="store_true", help="Print all logging messages")
    optional.add_argument("-h", "--help", action="help", help="Show help and exit")
    optional.add_argument(
        "-v",
        "--version",
        action="version",
        help="Show version and exit",
        version=f"{Path(sys.argv[0]).name} {_version()}",
    )
    return parser.parse_args(raw)


def _setup_logging(quiet: bool = False, debug: bool = False) -> None:
    """
    Set up logging.

    :param debug: Log all messages.
    """
    logging.basicConfig(
        datefmt="%Y-%m-%dT%H:%M:%S",
        format="[%(asctime)s] %(levelname)8s %(message)s",
        level=logging.DEBUG if debug else logging.INFO,
    )


def _version() -> str:
    """
    Return version information.
    """
    with resources.as_file(resources.files(f"{PKGNAME}.resources")) as prefix:
        with open(prefix / "info.json", "r", encoding="utf-8") as f:
            info = json.load(f)
    return "version %s build %s" % (info["version"], info["buildnum"])
