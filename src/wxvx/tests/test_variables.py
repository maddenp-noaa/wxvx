"""
Tests for wxvx.net.
"""

# pylint: disable=invalid-name,protected-access

from wxvx import variables

# Tests


def test_Var_no_level():
    var = variables.Var(name="foo", levtype="surface")
    assert var.name == "foo"
    assert var.levtype == "surface"
    assert var.level is None
    assert var._keys == ["name", "levtype"]
    assert var == variables.Var("foo", "surface")
    assert var != variables.Var("bar", "surface")
    assert hash(var) == hash(("foo", "surface", None))
    assert var < variables.Var("qux", "surface")
    assert var > variables.Var("bar", "surface")
    assert repr(var) == "Var(name=foo, levtype=surface)"
    assert str(var) == "foo-surface"


def test_Var_with_level():
    var = variables.Var(name="foo", levtype="isobaricInhPa", level="1000")
    assert var.name == "foo"
    assert var.levtype == "isobaricInhPa"
    assert var.level == "1000"
    assert var._keys == ["name", "levtype", "level"]
    assert var == variables.Var("foo", "isobaricInhPa", "1000")
    assert var != variables.Var("bar", "isobaricInhPa", "1000")
    assert hash(var) == hash(("foo", "isobaricInhPa", "1000"))
    assert var < variables.Var("qux", "isobaricInhPa", "1000")
    assert var > variables.Var("foo", "isobaricInhPa", "900")
    assert repr(var) == "Var(name=foo, levtype=isobaricInhPa, level=1000)"
    assert str(var) == "foo-isobaricInhPa-1000"


def test_GFSVar():
    pass
