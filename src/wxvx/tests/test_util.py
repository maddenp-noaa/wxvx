"""
Tests for wxvx.util.
"""

import logging
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from pytest import mark, raises

from wxvx import util

# Tests


def test_atomic(fakefs):
    greeting, recipient = [fakefs / f"out.{x}" for x in ("greeting", "recipient")]
    assert not greeting.is_file()
    assert not recipient.is_file()
    s1, s2 = "hello", "world"
    with util.atomic(greeting) as tmp1:
        with util.atomic(recipient) as tmp2:
            assert tmp2 != tmp1
            tmp1.write_text(s1)
            tmp2.write_text(s2)
            assert tmp1.is_file()
            assert tmp2.is_file()
        assert not tmp2.is_file()
    assert not tmp1.is_file()
    assert greeting.read_text() == s1
    assert recipient.read_text() == s2


def test_times_expand_basic(utc):
    start = utc(2024, 12, 19, 12, 0)
    step = timedelta(hours=6)
    stop = utc(2024, 12, 20, 6, 0)
    assert util.expand(start=start, stop=stop, step=step) == [
        utc(2024, 12, 19, 12, 0),
        utc(2024, 12, 19, 18, 0),
        utc(2024, 12, 20, 0, 0),
        utc(2024, 12, 20, 6, 0),
    ]


def test_times_expand_degenerate_one(utc):
    start = utc(2024, 12, 19, 12, 0)
    step = timedelta(hours=6)
    stop = utc(2024, 12, 19, 12, 0)
    assert util.expand(start=start, step=step, stop=stop) == [utc(2024, 12, 19, 12, 0)]


def test_times_expand_stop_precedes_start(utc):
    start = utc(2024, 12, 19, 12, 0)
    step = timedelta(hours=6)
    stop = utc(2024, 12, 19, 6, 0)
    with raises(util.WXVXError) as e:
        util.expand(start=start, step=step, stop=stop)
    assert str(e.value) == "Stop time 2024-12-19 06:00:00 precedes start time 2024-12-19 12:00:00"


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


@mark.parametrize(
    ("step", "expected"),
    [
        ("01:02:03", timedelta(hours=1, minutes=2, seconds=3)),
        ("168:00:00", timedelta(days=7)),
    ],
)
def test_util_to_timedelta(step, expected):
    assert util.to_timedelta(value=step) == expected
