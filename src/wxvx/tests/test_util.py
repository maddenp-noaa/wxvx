"""
Tests for wxvx.util.
"""

from pathlib import Path
from unittest.mock import patch

from wxvx import util


def test_util_resource(fs):
    expected = "bar"
    path = Path(fs.create_file("/path/to/foo", contents=expected).path)
    with patch.object(util.resources, "as_file", return_value=path.parent):
        with util.resource(path.name) as f:
            assert f.read() == expected


def test_util_resource_path():
    with util.resource_path("foo") as path:
        assert str(path).endswith("%s/resources/foo" % util.pkgname)
