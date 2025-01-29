"""
Tests for wxvx.net.
"""

# pylint: disable=invalid-name,protected-access

from pytest import mark

from wxvx import variables

# Tests


def test_variables_Var_no_level():
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


def test_variables_Var_with_level():
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


def test_variables_GFSVar():
    keys = {"name", "levtype", "firstbyte", "lastbyte"}
    var = variables.GFSVar(name="TMP", levstr="900 mb", firstbyte=1, lastbyte=2)
    assert var.levtype == "isobaricInhPa"
    assert var.level == "900"
    assert var.firstbyte == 1
    assert var.lastbyte == 2
    assert var._keys == {*keys, "level"}
    assert variables.GFSVar(name="TMP", levstr="surface", firstbyte=1, lastbyte=2)._keys == keys


@mark.parametrize(("expected", "name"), [("TMP", "t"), (variables.UNKNOWN, "foo")])
def test_variables_GFSVar_gfsvar(expected, name):
    # NB: 't' => 'TMP', not T2M, which is potentially a problem.
    assert variables.GFSVar.gfsvar(name) == expected


@mark.parametrize(("expected", "name"), [("t", "TMP"), ("t", "T2M"), (variables.UNKNOWN, "FOO")])
def test_variables_GFSVar_stdvar(expected, name):
    assert variables.GFSVar.stdvar(name) == expected


@mark.parametrize(
    ("expected", "levstr"), [("900", "900 mb"), ("1013.1", "1013.1 mb"), (None, "surface")]
)
def test_variables_GFSVar__level_pressure(expected, levstr):
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
def test_variables_GFSVar__levinfo(expected, levstr):
    assert variables.GFSVar._levinfo(levstr) == expected


def test_variables_set_cf_metadata(da, check_cf_metadata):
    variables.set_cf_metadata(da=da, taskname="test")
    check_cf_metadata(da)
