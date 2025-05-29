"""
Tests for wxvx.net.
"""

import numpy as np
import xarray as xr
from pytest import fixture, mark, raises

from wxvx import variables
from wxvx.util import WXVXError

# Fixtures


@fixture
def da_flat(da_with_leadtime):
    return (
        da_with_leadtime.sel(time=da_with_leadtime.time.values[0])
        .sel(lead_time=da_with_leadtime.lead_time.values[0])
        .sel(level=da_with_leadtime.level.values[0])
    )


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


@mark.parametrize(("leadtime", "validtime"), [("lead_time", None), (None, "validtime")])
def test_variables_da_construct(
    config_data, da_with_leadtime, da_with_validtime, fakefs, gen_config, leadtime, tc, validtime
):
    da = da_with_leadtime if leadtime else da_with_validtime
    time = config_data["forecast"]["coords"]["time"]
    time["leadtime"] = leadtime
    time["validtime"] = validtime
    c = gen_config(config_data, fakefs)
    var = variables.Var(name="gh", level_type="isobaricInhPa", level=900)
    selected = variables.da_select(c=c, ds=da.to_dataset(), varname="HGT", tc=tc, var=var)
    new = variables.da_construct(c=c, da=selected)
    assert new.name == da.name
    assert all(new.latitude == da.latitude)
    assert all(new.longitude == da.longitude)
    assert new.time == [np.datetime64(str(tc.validtime.isoformat()))]
    assert new.forecast_reference_time == [np.datetime64(str(tc.cycle.isoformat()))]


@mark.parametrize(("fail", "name", "varname"), [(False, "gh", "HGT"), (True, "foo", "FOO")])
def test_variables_da_select(c, da_with_leadtime, fail, name, tc, varname):
    var = variables.Var(name=name, level_type="isobaricInhPa", level=900)
    kwargs = dict(c=c, ds=da_with_leadtime.to_dataset(), varname=varname, tc=tc, var=var)
    if fail:
        with raises(WXVXError) as e:
            variables.da_select(**kwargs)
        msg = f"Variable FOO valid at {tc.validtime.isoformat()} not found in {c.forecast.path}"
        assert str(e.value) == msg
    else:
        new = variables.da_select(**kwargs)
        # latitude and longitude are unchanged
        assert all(new.latitude == da_with_leadtime.latitude)
        assert all(new.longitude == da_with_leadtime.longitude)
        # scalar level, time, and lead_time values are selected from arrays
        assert new.level.values == da_with_leadtime.level.values[0]
        assert new.time.values == da_with_leadtime.time.values[0]
        assert new.lead_time.values == da_with_leadtime.lead_time.values[0]


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


@mark.parametrize(
    ("name", "obj"), [("GFS", variables.GFS), ("HRRR", variables.HRRR), ("FOO", None)]
)
def test_variables_model_class(name, obj):
    if obj is None:
        with raises(NotImplementedError):
            variables.model_class(name)
    else:
        assert variables.model_class(name) == obj


def test_variables_model_names():
    class A: ...

    class B(A): ...

    class C1(B): ...

    class C2(B): ...

    assert variables.model_names(A) == {"B", "C1", "C2"}
    assert variables.model_names() == {"GFS", "HRRR"}


def test_variables__da_val__fail_unparesable(da_flat):
    da_flat.attrs["init"] = "foo"
    with raises(WXVXError) as e:
        variables._da_val(da=da_flat, key="init", desc="init time", t=np.datetime64)
    assert str(e.value) == "Could not parse 'foo' as init time"


def test_variables__da_val__fail_no_attr_or_coord(da_flat):
    with raises(WXVXError) as e:
        variables._da_val(da=da_flat, key="init", desc="init time", t=np.datetime64)
    assert str(e.value) == "Not found in forecast dataset coordinates or attributes: 'init'"


def test_variables__da_val__pass_attr_as_is(da_flat):
    expected = np.datetime64(0, "s")
    da_flat.attrs["init"] = expected
    actual = variables._da_val(da=da_flat, key="init", desc="init time", t=np.datetime64)
    assert actual == expected


def test_variables__da_val__pass_attr_must_parse(da_flat):
    da_flat.attrs["init"] = "1970-01-01T00:00:00"
    actual = variables._da_val(da=da_flat, key="init", desc="init time", t=np.datetime64)
    assert actual == np.datetime64(0, "s")


def test_variables__da_val__pass_coord(da_flat):
    actual = variables._da_val(da=da_flat, key="time", desc="init time", t=np.datetime64)
    assert actual == np.datetime64(0, "s")


@mark.parametrize(("s", "expected"), [("900", 900), ("1013.1", 1013.1)])
def test_variables__levelstr2num(s, expected):
    assert variables._levelstr2num(levelstr=s) == expected


def test_variables__narrow__fail():
    data = 42
    coords = {"x": 1}
    da = xr.DataArray(name="a", data=data, dims=["x"], coords=coords)
    with raises(KeyError):
        variables._narrow(da=da, key="x", value=2)


def test_variables__narrow_noop_passthrough(da_with_leadtime, logged):
    assert variables._narrow(da=da_with_leadtime, key="foo", value=None) == da_with_leadtime
    assert logged("No coordinate 'foo' found for 'HGT', ignoring")


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
