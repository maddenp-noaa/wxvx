"""
Granular tests of config.schema.
"""

# pylint: disable=redefined-outer-name

import json
import re
from copy import deepcopy
from typing import Any, Callable

from pyfakefs.fake_filesystem import FakeFilesystem
from pytest import fixture
from uwtools.api.config import validate

from wxvx.util import resource_path

# Helpers


def validator(fs: FakeFilesystem, *args: Any) -> Callable:
    """
    Returns a lambda that validates an eventual config argument.

    :param args: Keys leading to sub-schema to be used to validate config.
    """
    with resource_path("config.jsonschema") as path:
        fs.add_real_file(path)
        with open(path, "r", encoding="utf-8") as f:
            schema = json.load(f)
    defs = schema.get("$defs", {})
    for arg in args:
        schema = schema[arg]
    schema.update({"$defs": defs})
    schema_file = str(fs.create_file("test.schema", contents=json.dumps(schema)).path)
    return lambda config: validate(schema_file=schema_file, config=config)


def with_del(d: dict, *args: Any) -> dict:
    """
    Delete a value at a given chain of keys in a dict.

    :param d: The dict to update.
    :param args: One or more keys navigating to the value to delete.
    """
    new = deepcopy(d)
    p = new
    for key in args[:-1]:
        p = p[key]
    del p[args[-1]]
    return new


def with_set(d: dict, val: Any, *args: Any) -> dict:
    """
    Set a value at a given chain of keys in a dict.

    :param d: The dict to update.
    :param val: The value to set.
    :param args: One or more keys navigating to the value to set.
    """
    new = deepcopy(d)
    p = new
    if args:
        for key in args[:-1]:
            p = p[key]
        p[args[-1]] = val
    return new


# Fixtures


@fixture
def config():
    return {
        "baseline": "/".join(
            [
                "https://noaa-hrrr-bdp-pds.s3.amazonaws.com",
                "hrrr.{yyyymmdd}",
                "conus",
                "hrrr.t{hh}z.wrfprsf{ff}.grib2",
            ]
        ),
        "cycles": {
            "start": "2024-04-01T01:00:00",
            "step": "01:00:00",
            "stop": "2024-04-07T22:00:00",
        },
        "leadtimes": {
            "start": "01:00:00",
            "step": "01:00:00",
            "stop": "01:00:00",
        },
        "outdir": "/tmp/outdir",
        "variables": [
            {"id": "q", "level": 1000, "type": "pressure"},
            {"id": "t", "level": None, "type": "surface"},
        ],
    }


@fixture
def logged(caplog):
    def logged_(s: str):
        found = any(re.match(rf"^.*{s}.*$", message) for message in caplog.messages)
        caplog.clear()
        return found

    return logged_


# Tests


def test_schema(logged, config, fs):
    ok = validator(fs)
    # Basic correctness:
    assert ok(config)
    # Certain top-level keys are required:
    for key in ["baseline", "cycles", "leadtimes", "outdir"]:
        assert not ok(with_del(config, key))
        assert logged(f"'{key}' is a required property")
    # Addional keys are not allowed:
    assert not ok(with_set(config, 42, "n"))
    assert logged("'n' was unexpected")
    # Some keys have dict values:
    for key in ["cycles", "leadtimes"]:
        assert not ok(with_set(config, None, key))
        assert logged("None is not of type 'object'")
    # Some keys have str values:
    for key in ["baseline", "outdir"]:
        assert not ok(with_set(config, None, key))
        assert logged("None is not of type 'string'")


def test_schema_cycles(logged, config, fs):
    ok = validator(fs, "properties", "cycles")
    config = config["cycles"]
    # Basic correctness:
    assert ok(config)
    # Certain top-level keys are required:
    for key in ["start", "step", "stop"]:
        assert not ok(with_del(config, key))
        assert logged(f"'{key}' is a required property")
    # Addional keys are not allowed:
    assert not ok(with_set(config, 42, "n"))
    assert logged("'n' was unexpected")
    # Some keys must match a certain regex:
    for key in ["start", "step", "stop"]:
        assert not ok(with_set(config, "foo", key))
        assert logged("'foo' does not match")


def test_schema_leadtimes(logged, config, fs):
    ok = validator(fs, "properties", "leadtimes")
    config = config["leadtimes"]
    # Basic correctness:
    assert ok(config)
    # Certain top-level keys are required:
    for key in ["start", "step", "stop"]:
        assert not ok(with_del(config, key))
        assert logged(f"'{key}' is a required property")
    # Addional keys are not allowed:
    assert not ok(with_set(config, 42, "n"))
    assert logged("'n' was unexpected")
    # Some keys must match a certain regex:
    for key in ["start", "step", "stop"]:
        assert not ok(with_set(config, "foo", key))
        assert logged("'foo' does not match")


def test_schema_variables(logged, config, fs):
    ok = validator(fs, "properties", "variables")
    config = config["variables"]
    # Basic correctness:
    assert ok(config)
