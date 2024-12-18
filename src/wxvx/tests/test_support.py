"""
Tests for wxvx.support.
"""

from pathlib import Path
from unittest.mock import patch

from wxvx import support


def test_support_resource(fs):
    expected = "bar"
    path = Path(fs.create_file("/path/to/foo", contents=expected).path)
    with patch.object(support.resources, "as_file", return_value=path.parent):
        with support.resource(path.name) as f:
            assert f.read() == expected


def test_support_resource_path():
    with support.resource_path("foo") as path:
        assert str(path).endswith("%s/resources/foo" % support.pkgname)
