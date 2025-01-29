"""
Tests for wxvx.net.
"""

# pylint: disable=invalid-name,protected-access

import numpy as np
import xarray as xr
from pytest import mark, raises

from wxvx import variables

# Tests


def test_Var_no_level():
    var = variables.Var(name="foo", levtype="surface")
    assert var.name == "foo"
    assert var.levtype == "surface"
    assert var.level is None
    assert var._keys == {"name", "levtype"}
    assert var == variables.Var("foo", "surface")
    assert var != variables.Var("bar", "surface")
    assert hash(var) == hash(("foo", "surface", None))
    assert var < variables.Var("qux", "surface")
    assert var > variables.Var("bar", "surface")
    assert repr(var) == "Var(levtype=surface, name=foo)"
    assert str(var) == "foo-surface"


def test_Var_with_level():
    var = variables.Var(name="foo", levtype="isobaricInhPa", level="1000")
    assert var.name == "foo"
    assert var.levtype == "isobaricInhPa"
    assert var.level == "1000"
    assert var._keys == {"name", "levtype", "level"}
    assert var == variables.Var("foo", "isobaricInhPa", "1000")
    assert var != variables.Var("bar", "isobaricInhPa", "1000")
    assert hash(var) == hash(("foo", "isobaricInhPa", "1000"))
    assert var < variables.Var("qux", "isobaricInhPa", "1000")
    assert var > variables.Var("foo", "isobaricInhPa", "900")
    assert repr(var) == "Var(level=1000, levtype=isobaricInhPa, name=foo)"
    assert str(var) == "foo-isobaricInhPa-1000"


def test_GFSVar():
    keys = {"name", "levtype", "firstbyte", "lastbyte"}
    var = variables.GFSVar(name="TMP", levstr="900 mb", firstbyte=1, lastbyte=2)
    assert var.levtype == "isobaricInhPa"
    assert var.level == "900"
    assert var.firstbyte == 1
    assert var.lastbyte == 2
    assert var._keys == {*keys, "level"}
    assert variables.GFSVar(name="TMP", levstr="surface", firstbyte=1, lastbyte=2)._keys == keys


def test_GFSVar_fail():
    with raises(ValueError) as e:
        variables.GFSVar(name="FOO", levstr="surface", firstbyte=1, lastbyte=2)
    assert str(e.value) == "Unknown GFS variable name 'FOO'"


@mark.parametrize(("expected", "name"), [("TMP", "t"), (variables.UNKNOWN, "foo")])
def test_GFSVar_gfsvar(expected, name):
    # NB: 't' => 'TMP', not T2M, which is potentially a problem.
    assert variables.GFSVar.gfsvar(name) == expected


@mark.parametrize(("expected", "name"), [("t", "TMP"), ("t", "T2M"), (variables.UNKNOWN, "FOO")])
def test_GFSVar_stdvar(expected, name):
    assert variables.GFSVar.stdvar(name) == expected


@mark.parametrize(
    ("expected", "levstr"), [("900", "900 mb"), ("1013.1", "1013.1 mb"), (None, "surface")]
)
def test_GFSVar__level_pressure(expected, levstr):
    assert variables.GFSVar._level_pressure(levstr) == expected


@mark.parametrize(
    ("expected", "levstr"),
    [
        (("atmosphere", None), "entire atmosphere"),
        (("isobaricInhPa", "900"), "900 mb"),
        (("surface", None), "surface"),
        ((variables.UNKNOWN, None), "something else"),
    ],
)
def test_GFSVar__levinfo(expected, levstr):
    assert variables.GFSVar._levinfo(levstr) == expected


def test_set_cf_metadata():
    da = xr.DataArray(
        name="HGT",
        data=np.zeros((1, 1, 1, 1, 1)),
        dims=["latitude", "longitude", "level", "time", "lead_time"],
        coords=dict(
            latitude=(["latitude", "longitude"], np.zeros((1, 1))),
            longitude=(["latitude", "longitude"], np.zeros((1, 1))),
            level=(["level"], np.zeros((1,))),
            time=np.zeros((1,)),
            lead_time=np.zeros((1,)),
        ),
    )
    variables.set_cf_metadata(da=da, taskname="test")
    for k, v in [
        ("Conventions", "CF-1.8"),
        ("grid_mapping", "latitude_longitude"),
        ("long_name", "Geopotential Height"),
        ("standard_name", "geopotential_height"),
        ("units", "m"),
    ]:
        assert da.attrs[k] == v
    for k, v in [
        ("long_name", "latitude"),
        ("standard_name", "latitude"),
        ("units", "degrees_north"),
    ]:
        assert da.latitude.attrs[k] == v
    for k, v in [
        ("long_name", "pressure level"),
        ("standard_name", "air_pressure"),
        ("units", "hPa"),
    ]:
        assert da.level.attrs[k] == v
    for k, v in [
        ("long_name", "longitude"),
        ("standard_name", "longitude"),
        ("units", "degrees_east"),
    ]:
        assert da.longitude.attrs[k] == v
    for k, v in [("long_name", "Forecast Period"), ("standard_name", "forecast_period")]:
        assert da.lead_time.attrs[k] == v
    for k, v in [
        ("long_name", "Forecast Reference Time"),
        ("standard_name", "forecast_reference_time"),
    ]:
        assert da.time.attrs[k] == v
