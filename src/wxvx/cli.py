import json
import logging
import sys
from argparse import ArgumentParser, HelpFormatter, Namespace
from pathlib import Path
from typing import Optional

import xarray as xr
import zarr
from uwtools.api.config import get_yaml_config, validate
from uwtools.api.logging import use_uwtools_logger
from warnings import catch_warnings, simplefilter
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
    workflow.grib_messages(config=config, threads=4)
    with catch_warnings():
        simplefilter("ignore")
        ds = xr.open_dataset(config["forecast"])
    # if not (ds := _ds(path=Path(config["forecast"]))):
    #     sys.exit(1)
    breakpoint()
    return


# Private


def _ds(path: Path) -> Optional[xr.Dataset]:
    engines = ("netcdf4", "zarr")
    for engine in engines:
        try:
            ds = xr.open_dataset(path, engine=engine)
        except OSError as e:
            if not "NetCDF: Unknown file format" in str(e):
                raise
        except zarr.errors._BaseZarrError:
            pass
        else:
            logging.info("Opened %s as %s", path, engine)
            return ds
    logging.error("Could not open %s as %s", path, ", ".join(engines))
    return None


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
