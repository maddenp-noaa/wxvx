"""
Tests for wxvx.cli.
"""

# pylint: disable=protected-access

import logging
import re
from unittest.mock import ANY, DEFAULT, patch

from pytest import mark, raises

from wxvx import cli

PKGNAME = __name__.split(".", maxsplit=1)[0]


def test_main():
    with patch.multiple(cli, _parse_args=DEFAULT, _setup_logging=DEFAULT, sys=DEFAULT) as mocks:
        argv = [PKGNAME, "-c", "a.yaml"]
        mocks["sys"].argv = argv
        cli.main()
    mocks["_parse_args"].assert_called_once_with(argv)
    mocks["_setup_logging"].assert_called_once()  # _with(debug=False)


@mark.parametrize("c", ["-c", "--config"])
@mark.parametrize("d", ["-d", "--debug", None])
def test__parse_args(c, d):
    args = cli._parse_args([PKGNAME, c, "a.yaml"] + ([d] if d else []))
    assert args.config == "a.yaml"
    assert args.debug is bool(d)


@mark.parametrize("h", ["-h", "--help"])
def test__parse_args_help(capsys, h):
    with raises(SystemExit) as e:
        cli._parse_args([PKGNAME, h])
    assert e.value.code == 0
    assert capsys.readouterr().out.startswith("usage:")


@mark.parametrize("v", ["-v", "--version"])
def test__parse_args_version(capsys, v):
    with raises(SystemExit) as e:
        cli._parse_args([PKGNAME, v])
    assert e.value.code == 0
    assert re.match(r"^\w+ version \d+\.\d+\.\d+ build \d+$", capsys.readouterr().out.strip())


def test__parse_args_required_arg_missing():
    with raises(SystemExit) as e:
        cli._parse_args([PKGNAME])
    assert e.value.code == 2


@mark.parametrize("debug", [True, False])
def test__setup_logging(debug):
    with patch.object(logging, "basicConfig") as bc:
        cli._setup_logging(debug=debug)
        bc.assert_called_once_with(
            datefmt=ANY,
            format=ANY,
            level=logging.DEBUG if debug else logging.INFO,
            stream=cli.sys.stderr,
        )


def test__version():
    assert re.match(r"^version \d+\.\d+\.\d+ build \d+$", cli._version())
