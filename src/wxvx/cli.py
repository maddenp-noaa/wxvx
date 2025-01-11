import json
import sys
from argparse import ArgumentParser, HelpFormatter, Namespace
from pathlib import Path

import yaml
from uwtools.api.config import validate
from uwtools.api.logging import use_uwtools_logger

from wxvx import workflow
from wxvx.util import pkgname, resource, resource_path

# Public


def main() -> None:
    args = _parse_args(sys.argv)
    use_uwtools_logger(verbose=args.debug)
    with open(args.config, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f.read())
    if not validate(schema_file=resource_path("config.jsonschema"), config_path=config):
        sys.exit(1)
    workflow.go(config)


# Private


def _parse_args(argv: list[str]) -> Namespace:
    parser = ArgumentParser(
        description=pkgname,
        add_help=False,
        formatter_class=lambda prog: HelpFormatter(prog, max_help_position=6),
    )
    required = parser.add_argument_group("Required arguments")
    required.add_argument(
        "-c",
        "--config",
        help="Configuration file",
        metavar="FILE",
        required=True,
        type=Path,
    )
    optional = parser.add_argument_group("Optional arguments")
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
        version=f"{Path(argv[0]).name} {_version()}",
    )
    return parser.parse_args(argv[1:])


def _version() -> str:
    with resource("info.json") as f:
        info = json.load(f)
    return "version %s build %s" % (info["version"], info["buildnum"])
