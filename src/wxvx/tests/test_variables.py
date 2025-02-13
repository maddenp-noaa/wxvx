"""
Tests for wxvx.net.
"""

from pytest import mark, raises

from wxvx import variables
from wxvx.util import WXVXError

# Tests


@mark.parametrize("levtype", ["atmosphere", "surface"])
def test_variables_Var_no_level(levtype):
    var = variables.Var(name="foo", levtype=levtype)
    assert var.name == "foo"
    assert var.levtype == levtype
    assert var.level is None
    assert var._keys == {"name", "levtype"}
    assert var == variables.Var("foo", levtype)
    assert var != variables.Var("bar", levtype)
    assert hash(var) == hash(("foo", levtype, None))
    assert var < variables.Var("qux", levtype)
    assert var > variables.Var("bar", levtype)
    assert repr(var) == "Var(levtype='%s', name='foo')" % levtype
    assert str(var) == "foo-%s" % levtype


@mark.parametrize(("levtype", "level"), [("heightAboveGround", 2), ("isobaricInhPa", 1000)])
def test_variables_Var_with_level(levtype, level):
    var = variables.Var(name="foo", levtype=levtype, level=level)
    assert var.name == "foo"
    assert var.levtype == levtype
    assert var.level == level
    assert var._keys == {"name", "levtype", "level"}
    assert var == variables.Var("foo", levtype, level)
    assert var != variables.Var("bar", levtype, level)
    assert hash(var) == hash(("foo", levtype, level))
    assert var < variables.Var("qux", levtype, level)
    assert var > variables.Var("foo", levtype, level - 1)
    assert repr(var) == "Var(level='%s', levtype='%s', name='foo')" % (level, levtype)
    assert str(var) == "foo-%s-%04d" % (levtype, level)


def test_variables_HRRRVar():
    keys = {"name", "levtype", "firstbyte", "lastbyte"}
    var = variables.HRRRVar(name="TMP", levstr="900 mb", firstbyte=1, lastbyte=2)
    assert var.levtype == "isobaricInhPa"
    assert var.level == 900
    assert var.firstbyte == 1
    assert var.lastbyte == 2
    assert var._keys == {*keys, "level"}
    assert variables.HRRRVar(name="TMP", levstr="surface", firstbyte=1, lastbyte=2)._keys == keys


@mark.parametrize(
    ("levtype", "level", "expected"),
    [
        ("atmosphere", None, "L000"),
        ("heightAboveGround", "2", "Z002"),
        ("isobaricInhPa", "900", "P900"),
    ],
)
def test_variables_HRRRVar_metlevel(levtype, level, expected):
    assert variables.HRRRVar.metlevel(levtype=levtype, level=level) == expected


def test_variables_HRRRVar_metlevel_error():
    with raises(WXVXError) as e:
        variables.HRRRVar.metlevel(levtype="foo", level=-1)
    assert str(e.value) == "No MET level defined for level type foo"


@mark.parametrize(
    ("name", "levtype", "expected"),
    [
        ("t", "isobaricInhPa", "TMP"),
        ("2t", "heightAboveGround", "TMP"),
        ("foo", "foolev", variables.UNKNOWN),
    ],
)
def test_variables_HRRRVar_varname(name, levtype, expected):
    assert variables.HRRRVar.varname(name=name, levtype=levtype) == expected


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
    ("name", "levtype", "expected"),
    [
        ("TMP", "isobaricInhPa", "t"),
        ("TMP", "heightAboveGround", "2t"),
        ("FOO", "suface", variables.UNKNOWN),
    ],
)
def test_variables_HRRRVar__stdname(name, levtype, expected):
    assert variables.HRRRVar._stdname(name=name, levtype=levtype) == expected


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
