"""
Granular tests of config.schema.
"""

import json
import re
from copy import deepcopy
from typing import Any, Callable

from pyfakefs.fake_filesystem import FakeFilesystem
from pytest import fixture
from uwtools.api.config import validate

from wxvx.util import resource_path

# Tests


def test_schema(logged, config_data, fs):
    ok = validator(fs)
    config = config_data
    # Basic correctness:
    assert ok(config)
    # Certain top-level keys are required:
    for key in [
        "baseline",
        "cycles",
        "forecast",
        "leadtimes",
        "paths",
        "variables",
    ]:
        assert not ok(with_del(config, key))
        assert logged(f"'{key}' is a required property")
    # Additional keys are not allowed:
    assert not ok(with_set(config, 42, "n"))
    assert logged("'n' was unexpected")
    # Some keys have object values:
    for key in ["cycles", "leadtimes", "paths", "variables"]:
        assert not ok(with_set(config, None, key))
        assert logged("None is not of type 'object'")


def test_schema_baseline(logged, config_data, fs):
    ok = validator(fs, "properties", "baseline")
    config = config_data["baseline"]
    # Basic correctness:
    assert ok(config)
    # Certain top-level keys are required:
    for key in ["compare", "name", "template"]:
        assert not ok(with_del(config, key))
        assert logged(f"'{key}' is a required property")
    # Additional keys are not allowed:
    assert not ok(with_set(config, 42, "n"))
    assert logged("'n' was unexpected")
    # Some keys have bool values:
    for key in ["compare"]:
        assert not ok(with_set(config, None, key))
        assert logged("None is not of type 'boolean'")
    # Some keys have string values:
    for key in ["name", "template"]:
        assert not ok(with_set(config, None, key))
        assert logged("None is not of type 'string'")


def test_schema_cycles(logged, config_data, fs):
    ok = validator(fs, "properties", "cycles")
    config = config_data["cycles"]
    # Basic correctness:
    assert ok(config)
    # Certain top-level keys are required:
    for key in ["start", "step", "stop"]:
        assert not ok(with_del(config, key))
        assert logged(f"'{key}' is a required property")
    # Additional keys are not allowed:
    assert not ok(with_set(config, 42, "n"))
    assert logged("'n' was unexpected")
    # Some keys must match a certain regex:
    for key in ["start", "step", "stop"]:
        assert not ok(with_set(config, "foo", key))
        assert logged("'foo' does not match")


def test_schema_forecast(logged, config_data, fs):
    ok = validator(fs, "properties", "forecast")
    config = config_data["forecast"]
    # Basic correctness:
    assert ok(config)
    # Certain top-level keys are required:
    for key in ["name", "path", "projection"]:
        assert not ok(with_del(config, key))
        assert logged(f"'{key}' is a required property")
    # Additional keys are not allowed:
    assert not ok(with_set(config, 42, "n"))
    assert logged("'n' was unexpected")
    # Some keys have object values:
    for key in ["projection"]:
        assert not ok(with_set(config, None, key))
        assert logged("None is not of type 'object'")
    # Some keys have string values:
    for key in ["name", "path"]:
        assert not ok(with_set(config, None, key))
        assert logged("None is not of type 'string'")
    # Optional 'mask' key must match its schema:
    assert ok(with_set(config, [[1.1, 2], [3.3, 4], [5.5, 6], [7.7, 8]], "mask"))
    assert ok(with_del(config, "mask"))
    assert not ok(with_set(config, "string", "mask"))
    assert logged("'string' is not of type 'array'")
    assert not ok(with_set(config, ["foo"], "mask"))
    assert logged("'foo' is not of type 'array'")


def test_schema_forecast_projection(logged, config_data, fs):
    ok = validator(fs, "properties", "forecast", "properties", "projection")
    config = config_data["forecast"]["projection"]
    # Basic correctness:
    assert ok(config)
    # Certain top-level keys are required:
    for key in ["proj"]:
        assert not ok(with_del(config, key))
        assert logged("'proj' is a required property")
    # Additional keys are not allowed:
    assert not ok(with_set(config, 42, "foo"))
    assert logged("'foo' was unexpected")
    # Some keys have enum values:
    for key in ["proj"]:
        assert not ok(with_set(config, "foo", key))
        assert logged(r"'foo' is not one of \['latlon', 'lcc'\]")
    # For proj latlon:
    config_latlon = {"proj": "latlon"}
    assert ok(config_latlon)
    assert not ok(with_set(config_latlon, 42, "foo"))
    assert logged("'foo' was unexpected")
    # For proj lcc (default in fixture):
    assert config["proj"] == "lcc"
    for key in ["a", "b", "lat_0", "lat_1", "lat_2", "lon_0"]:
        assert not ok(with_del(config, key))
        assert logged(f"'{key}' is a required property")
        assert not ok(with_set(config, None, key))
        assert logged("None is not of type 'number'")


def test_schema_leadtimes(logged, config_data, fs):
    ok = validator(fs, "properties", "leadtimes")
    config = config_data["leadtimes"]
    # Basic correctness:
    assert ok(config)
    # Certain top-level keys are required:
    for key in ["start", "step", "stop"]:
        assert not ok(with_del(config, key))
        assert logged(f"'{key}' is a required property")
    # Additional keys are not allowed:
    assert not ok(with_set(config, 42, "n"))
    assert logged("'n' was unexpected")
    # Some keys must match a certain regex:
    for key in ["start", "step", "stop"]:
        assert not ok(with_set(config, "foo", key))
        assert logged("'foo' does not match")


def test_schema_meta(config_data, fs, logged):
    ok = validator(fs)
    config = config_data
    # The optional top-level "meta" key must have a object value:
    assert ok(with_set(config, {}, "meta"))
    assert not ok(with_set(config, [], "meta"))
    assert logged("is not of type 'object'")


def test_schema_paths(config_data, fs, logged):
    ok = validator(fs, "properties", "paths")
    config = config_data["paths"]
    # Basic correctness:
    assert ok(config)
    # Certain top-level keys are required:
    for key in ["grids", "run"]:
        assert not ok(with_del(config, key))
        assert logged(f"'{key}' is a required property")
    # Additional keys are not allowed:
    assert not ok(with_set(config, 42, "n"))
    # Some keys have object values:
    for key in ["grids"]:
        assert not ok(with_set(config, None, key))
        assert logged("None is not of type 'object'")
    # Some keys have string values:
    for key in ["run"]:
        assert not ok(with_set(config, None, key))
        assert logged("None is not of type 'string'")


def test_schema_paths_grids(config_data, fs, logged):
    ok = validator(fs, "properties", "paths", "properties", "grids")
    config = config_data["paths"]["grids"]
    # Basic correctness:
    assert ok(config)
    # Certain top-level keys are required:
    for key in ["baseline", "forecast"]:
        assert not ok(with_del(config, key))
        assert logged(f"'{key}' is a required property")
    # Additional keys are not allowed:
    assert not ok(with_set(config, 42, "n"))
    # Some keys have string values:
    for key in ["baseline", "forecast"]:
        assert not ok(with_set(config, None, key))
        assert logged("None is not of type 'string'")


def test_schema_variables(logged, config_data, fs):
    ok = validator(fs, "properties", "variables")
    config = config_data["variables"]
    one = config["T2M"]
    # Basic correctness:
    assert ok(config)
    # Must be an object:
    assert not ok([])
    assert logged("is not of type 'object'")
    # Array entries must have the correct keys:
    for key in ("level_type", "levels", "name"):
        assert not ok(with_del({"X": one}, "X", key))
        assert logged(f"'{key}' is a required property")
    # Additional keys in entries are not allowed:
    assert not ok({"X": {**one, "foo": "bar"}})
    assert logged("Additional properties are not allowed")
    # The "levels" key is required for some level types, forbidden for others:
    for level_type in ("heightAboveGround", "isobaricInhPa"):
        assert not ok({"X": {"name": "foo", "level_type": level_type}})
        assert logged("'levels' is a required property")
    for level_type in ("atmosphere", "surface"):
        assert not ok({"X": {"name": "foo", "level_type": level_type, "levels": [1000]}})
        assert logged("should not be valid")
    # Some keys have enum values:
    for key in ["level_type"]:
        assert not ok({"X": {**one, key: None}})
        assert logged("None is not one of")
    # Some keys have string values:
    for key in ["name"]:
        assert not ok({"X": {**one, key: None}})
        assert logged("None is not of type 'string'")


# Fixtures


@fixture
def logged(caplog):
    def logged_(s: str):
        found = any(re.match(rf"^.*{s}.*$", message) for message in caplog.messages)
        caplog.clear()
        return found

    return logged_


# Helpers


def validator(fs: FakeFilesystem, *args: Any) -> Callable:
    """
    Returns a lambda that validates an eventual config argument.

    :param args: Keys leading to sub-schema to be used to validate config.
    """
    schema_path = resource_path("config.jsonschema")
    fs.add_real_file(schema_path)
    with schema_path.open() as f:
        schema = json.load(f)
    defs = schema.get("$defs", {})
    for arg in args:
        schema = schema[arg]
    schema.update({"$defs": defs})
    schema_file = str(fs.create_file("test.schema", contents=json.dumps(schema)).path)
    return lambda c: validate(schema_file=schema_file, config_data=c)


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
