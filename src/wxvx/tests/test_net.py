"""
Tests for wxvx.net.
"""

from pathlib import Path
from unittest.mock import patch, Mock
from pytest import fixture, mark
from wxvx import net

# Fixtures

@fixture
def response():
    response = Mock()
    response.status_code = 200
    response.content = bytes("foo", encoding="utf-8")
    return response


# Tests

def test_fetch_fail(fs, response):
    response.status_code = 404
    path = Path(fs.create_file("f").path)
    url = "https://some.url"
    with patch.object(net.requests, "get", return_value=response) as get:
        assert net.fetch(taskname="task", url=url, path=path) is False
    get.assert_called_once_with(url, allow_redirects=True, timeout=3, headers={})
    assert path.read_text() == ""


def test_fetch_ok_basic(fs, response):
    path = Path(fs.create_file("f").path)
    url = "https://some.url"
    with patch.object(net.requests, "get", return_value=response) as get:
        assert net.fetch(taskname="task", url=url, path=path) is True
    get.assert_called_once_with(url, allow_redirects=True, timeout=3, headers={})
    assert path.read_text() == "foo"
    

def test_fetch_ok_range(fs, response):
    response.status_code = 206
    path = Path(fs.create_file("f").path)
    url = "https://some.url"
    headers = {"Range": "bytes=1-2"}
    with patch.object(net.requests, "get", return_value=response) as get:
        assert net.fetch(taskname="task", url=url, path=path, headers=headers) is True
    get.assert_called_once_with(url, allow_redirects=True, timeout=3, headers=headers)
    assert path.read_text() == "foo"
    
