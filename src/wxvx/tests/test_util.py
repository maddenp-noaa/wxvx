"""
Tests for wxvx.util.
"""

import logging
from pathlib import Path
from unittest.mock import patch

from pytest import raises

from wxvx import util

# Tests


def test_atomic(fakefs):
    path = fakefs / "greeting"
    assert not path.is_file()
    msg = "hello"
    with util.atomic(path) as tmp:
        tmp.write_text(msg)
        assert tmp.is_file()
    assert not tmp.is_file()
    assert path.read_text() == msg


def test_fail(caplog):
    caplog.set_level(logging.INFO)
    with raises(SystemExit) as e:
        util.fail()
    assert not caplog.messages
    with raises(SystemExit) as e:
        util.fail("foo")
    assert "foo" in caplog.messages
    with raises(SystemExit) as e:
        util.fail("foo %s", "bar")
    assert "foo bar" in caplog.messages
    assert e.value.code == 1


def test_util_mpexec(tmp_path):
    path = tmp_path / "out"
    cmd = "echo $PI >%s" % path
    expected = "3.14"
    util.mpexec(cmd=cmd, rundir=tmp_path, taskname="foo", env={"PI": expected})
    assert path.read_text().strip() == expected


def test_util_resource(fs):
    expected = "bar"
    path = Path(fs.create_file("/path/to/foo", contents=expected).path)
    with patch.object(util.resources, "as_file", return_value=path.parent):
        assert util.resource(path) == expected


def test_util_resource_path():
    assert str(util.resource_path("foo")).endswith("%s/resources/foo" % util.pkgname)
