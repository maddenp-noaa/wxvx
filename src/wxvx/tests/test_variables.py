"""
Tests for wxvx.net.
"""

import numpy as np
import xarray as xr
from pytest import mark, raises

from wxvx import variables
from wxvx.util import WXVXError

# Tests


@mark.parametrize("level_type", ["atmosphere", "surface"])
def test_variables_Var_no_level(level_type):
    var = variables.Var(name="foo", level_type=level_type)
    assert var.name == "foo"
    assert var.level_type == level_type
    assert var.level is None
    assert var._keys == {"name", "level_type"}
    assert var == variables.Var("foo", level_type)
    assert var != variables.Var("bar", level_type)
    assert hash(var) == hash(("foo", level_type, None))
    assert var < variables.Var("qux", level_type)
    assert var > variables.Var("bar", level_type)
    assert repr(var) == "Var(level_type='%s', name='foo')" % level_type
    assert str(var) == "foo-%s" % level_type


@mark.parametrize(("level_type", "level"), [("heightAboveGround", 2), ("isobaricInhPa", 1000)])
def test_variables_Var_with_level(level, level_type):
    var = variables.Var(name="foo", level_type=level_type, level=level)
    assert var.name == "foo"
    assert var.level_type == level_type
    assert var.level == level
    assert var._keys == {"name", "level_type", "level"}
    assert var == variables.Var("foo", level_type, level)
    assert var != variables.Var("bar", level_type, level)
    assert hash(var) == hash(("foo", level_type, level))
    assert var < variables.Var("qux", level_type, level)
    assert var > variables.Var("foo", level_type, level - 1)
    assert repr(var) == "Var(level=%s, level_type='%s', name='foo')" % (level, level_type)
    assert str(var) == "foo-%s-%04d" % (level_type, level)


def test_variables_HRRR():
    keys = {"name", "level_type", "firstbyte", "lastbyte"}
    var = variables.HRRR(name="TMP", levstr="900 mb", firstbyte=1, lastbyte=2)
    assert var.level_type == "isobaricInhPa"
    assert var.level == 900
    assert var.firstbyte == 1
    assert var.lastbyte == 2
    assert var._keys == {*keys, "level"}
    assert variables.HRRR(name="TMP", levstr="surface", firstbyte=1, lastbyte=2)._keys == keys


@mark.parametrize(("name", "expected"), [("t", "TMP"), ("2t", "TMP"), ("foo", variables.UNKNOWN)])
def test_variables_HRRR_varname(name, expected):
    assert variables.HRRR.varname(name=name) == expected


@mark.parametrize(
    ("name", "level_type", "expected"),
    [
        ("TMP", "isobaricInhPa", "t"),
        ("TMP", "heightAboveGround", "2t"),
        ("FOO", "suface", variables.UNKNOWN),
    ],
)
def test_variables_HRRR__canonicalize(name, level_type, expected):
    assert variables.HRRR._canonicalize(name=name, level_type=level_type) == expected


@mark.parametrize(
    ("expected", "levstr"),
    [
        (("atmosphere", None), "entire atmosphere"),
        (("heightAboveGround", 2), "2 m above ground"),
        (("isobaricInhPa", 900), "900 mb"),
        (("surface", None), "surface"),
        ((variables.UNKNOWN, None), "something else"),
    ],
)
def test_variables_HRRR__levinfo(expected, levstr):
    assert variables.HRRR._levinfo(levstr) == expected


def test_variables_da_construct(c, da, tc):
    var = variables.Var(name="gh", level_type="isobaricInhPa", level=900)
    selected = variables.da_select(ds=da.to_dataset(), c=c, varname="HGT", tc=tc, var=var)
    new = variables.da_construct(src=selected)
    assert new.name == da.name
    assert all(new.latitude == da.latitude)
    assert all(new.longitude == da.longitude)
    assert new.time == [np.datetime64(str(tc.validtime.isoformat()))]
    assert new.forecast_reference_time == [np.datetime64(str(tc.cycle.isoformat()))]


@mark.parametrize(("fail", "name", "varname"), [(False, "gh", "HGT"), (True, "foo", "FOO")])
def test_variables_da_select(c, da, fail, name, tc, varname):
    var = variables.Var(name=name, level_type="isobaricInhPa", level=900)
    kwargs = dict(ds=da.to_dataset(), c=c, varname=varname, tc=tc, var=var)
    if fail:
        with raises(WXVXError) as e:
            variables.da_select(**kwargs)
        msg = f"Variable FOO valid at {tc.validtime.isoformat()} not found in {c.forecast.path}"
        assert str(e.value) == msg
    else:
        new = variables.da_select(**kwargs)
        # latitude and longitude are unchanged
        assert all(new.latitude == da.latitude)
        assert all(new.longitude == da.longitude)
        # scalar level, time, and lead_time values are selected from arrays
        assert new.level.values == da.level.values[0]
        assert new.time.values == da.time.values[0]
        assert new.lead_time.values == da.lead_time.values[0]


def test_variables_ds_construct(c, check_cf_metadata):
    name = "HGT"
    one = np.array([1], dtype="float32")
    da = xr.DataArray(
        data=one.reshape((1, 1, 1, 1)),
        coords=dict(
            forecast_reference_time=np.array([0], dtype="datetime64[ns]"),
            time=np.array([1], dtype="timedelta64[ns]"),
            latitude=(["latitude", "longitude"], one.reshape((1, 1))),
            longitude=(["latitude", "longitude"], one.reshape((1, 1))),
        ),
        dims=("forecast_reference_time", "time", "latitude", "longitude"),
        name=name,
    )
    ds = variables.ds_construct(c=c, da=da, level=None, taskname="test")
    check_cf_metadata(ds=ds, name=name)


@mark.parametrize(
    ("level_type", "level", "expected"),
    [
        ("atmosphere", None, "L000"),
        ("heightAboveGround", "2", "Z002"),
        ("isobaricInhPa", "900", "P900"),
    ],
)
def test_variables_metlevel(level_type, level, expected):
    assert variables.metlevel(level_type=level_type, level=level) == expected


def test_variables_metlevel__error():
    with raises(WXVXError) as e:
        variables.metlevel(level_type="foo", level=-1)
    assert str(e.value) == "No MET level defined for level type foo"


@mark.parametrize(("s", "expected"), [("900", 900), ("1013.1", 1013.1)])
def test_variables__levelstr2num(s, expected):
    assert variables._levelstr2num(levelstr=s) == expected


def test_variables__narrow__fail():
    data = 42
    coords = {"x": 1}
    da = xr.DataArray(name="a", data=data, dims=["x"], coords=coords)
    with raises(KeyError):
        variables._narrow(da=da, key="x", value=2)


def test_variables__narrow__pass_array_to_array():
    data = [[42, 43], [44, 45]]
    coords = {"x": [1, 2], "y": [1, 2]}
    da = xr.DataArray(name="a", data=data, dims=["x", "y"], coords=coords)
    assert np.all(variables._narrow(da=da, key="x", value=1).data == [42, 43])


def test_variables__narrow__pass_array_to_scalar():
    data = [42, 43]
    coords = {"x": [1, 2]}
    da = xr.DataArray(name="a", data=data, dims=["x"], coords=coords)
    assert variables._narrow(da=da, key="x", value=1).data == 42


def test_variables__narrow__pass_scalar():
    data = 42
    coords = {"x": 1}
    da = xr.DataArray(name="a", data=data, dims=["x"], coords=coords)
    assert variables._narrow(da=da, key="x", value=1).data == 42
