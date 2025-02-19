"""
Tests for wxvx.net.
"""

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
def test_variables_Var_with_level(level_type, level):
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
    assert repr(var) == "Var(level='%s', level_type='%s', name='foo')" % (level, level_type)
    assert str(var) == "foo-%s-%04d" % (level_type, level)


def test_variables_HRRRVar():
    keys = {"name", "level_type", "firstbyte", "lastbyte"}
    var = variables.HRRRVar(name="TMP", levstr="900 mb", firstbyte=1, lastbyte=2)
    assert var.level_type == "isobaricInhPa"
    assert var.level == 900
    assert var.firstbyte == 1
    assert var.lastbyte == 2
    assert var._keys == {*keys, "level"}
    assert variables.HRRRVar(name="TMP", levstr="surface", firstbyte=1, lastbyte=2)._keys == keys


@mark.parametrize(
    ("level_type", "level", "expected"),
    [
        ("atmosphere", None, "L000"),
        ("heightAboveGround", "2", "Z002"),
        ("isobaricInhPa", "900", "P900"),
    ],
)
def test_variables_HRRRVar_metlevel(level_type, level, expected):
    assert variables.HRRRVar.metlevel(level_type=level_type, level=level) == expected


def test_variables_HRRRVar_metlevel_error():
    with raises(WXVXError) as e:
        variables.HRRRVar.metlevel(level_type="foo", level=-1)
    assert str(e.value) == "No MET level defined for level type foo"


@mark.parametrize(
    ("name", "level_type", "expected"),
    [
        ("t", "isobaricInhPa", "TMP"),
        ("2t", "heightAboveGround", "TMP"),
        ("foo", "foolev", variables.UNKNOWN),
    ],
)
def test_variables_HRRRVar_varname(name, level_type, expected):
    assert variables.HRRRVar.varname(name=name, level_type=level_type) == expected


@mark.parametrize(
    ("expected", "levstr"),
    [
        (2, "2 m above ground"),
        (900, "900 mb"),
        (1013.1, "1013.1 mb"),
        (None, "surface"),
    ],
)
def test_variables_HRRRVar__level_pressure(expected, levstr):
    assert variables.HRRRVar._level_pressure(levstr) == expected


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
def test_variables_HRRRVar__levinfo(expected, levstr):
    assert variables.HRRRVar._levinfo(levstr) == expected


@mark.parametrize(
    ("name", "level_type", "expected"),
    [
        ("TMP", "isobaricInhPa", "t"),
        ("TMP", "heightAboveGround", "2t"),
        ("FOO", "suface", variables.UNKNOWN),
    ],
)
def test_variables_HRRRVar__stdname(name, level_type, expected):
    assert variables.HRRRVar._stdname(name=name, level_type=level_type) == expected


def test_variables_cf_compliant_dataset(da, check_cf_metadata):
    variables.cf_compliant_dataset(da=da, taskname="test")
    ds = da.to_dataset()
    ds.attrs["Conventions"] = "CF-1.8"
    check_cf_metadata(ds=ds, name="HGT")


def test_forecast_var_units():
    assert variables.forecast_var_units(name="REFC") == "dBZ"


@mark.parametrize(("s", "expected"), [("900", 900), ("1013.1", 1013.1)])
def test__levelstr2num(s, expected):
    assert variables._levelstr2num(levelstr=s) == expected
