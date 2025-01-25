import json
import sys
from argparse import Action, ArgumentParser, HelpFormatter, Namespace
from pathlib import Path

from uwtools.api.config import get_yaml_config, validate
from uwtools.api.logging import use_uwtools_logger

from wxvx import workflow
from wxvx.util import pkgname, resource, resource_path

# Public


def main() -> None:
    args = _parse_args(sys.argv)
    use_uwtools_logger(verbose=args.debug)
    config = get_yaml_config(args.config)
    config.dereference()
    if not validate(schema_file=resource_path("config.jsonschema"), config_data=config):
        sys.exit(1)
    workflow.run_directory(config=config, threads=config["threads"])


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
        "-s",
        "--show",
        action=ShowConfig,
        help="Show a pro-forma config and exit",
        nargs=0,
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


class ShowConfig(Action):
    def __init__(self, option_strings, dest, **kwargs):
        super().__init__(option_strings, dest, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        with resource("config.yaml") as f:
            print(f.read().strip())
        sys.exit(0)
