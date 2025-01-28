"""
Tests for wxvx.net.
"""

from pathlib import Path
from unittest.mock import Mock, patch

from pytest import mark

from wxvx import net

# Tests


@mark.parametrize(
    ("code", "out", "byterange", "ret"),
    [(200, "foo", False, True), (206, "foo", True, True), (404, "", False, False)],
)
def test_fetch_fail(code, fs, out, byterange, ret):
    response = Mock()
    response.status_code = code
    response.content = bytes("foo", encoding="utf-8")
    headers = {"Range": "bytes=1-2"} if byterange else {}
    path = Path(fs.create_file("f").path)
    url = "https://some.url"
    with patch.object(net.requests, "get", return_value=response) as get:
        assert net.fetch(taskname="task", url=url, path=path, headers=headers) is ret
    get.assert_called_once_with(url, allow_redirects=True, timeout=3, headers=headers)
    assert path.read_text(encoding="utf-8") == out
