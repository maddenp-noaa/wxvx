"""
Tests for wxvx.util.
"""

from pathlib import Path
from unittest.mock import patch

from wxvx import util

# Tests


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
