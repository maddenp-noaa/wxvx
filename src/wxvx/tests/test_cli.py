"""
Tests for wxvx.cli.
"""

# pylint: disable=protected-access

import logging
import re
from pathlib import Path
from unittest.mock import ANY
from unittest.mock import DEFAULT as D
from unittest.mock import patch, Mock

from pytest import mark, raises

from wxvx import cli
from wxvx.support import pkgname, resource_path


def test_cli_main():
    with patch.multiple(cli, _parse_args=D, _setup_logging=D, sys=D) as mocks:
        argv = [pkgname, "-c", "a.yaml"]
        mocks["sys"].argv = argv
        cli.main()
    _parse_args = mocks["_parse_args"]
    _parse_args.assert_called_once_with(argv)
    mocks["_setup_logging"].assert_called_once_with(debug=_parse_args().debug)


def test_cli_main_bad_config(fs):
    with resource_path("") as resources_dir:
        path = fs.create_file(Path(resources_dir, "test.yaml"), contents="{}").path
    breakpoint()
    with patch.multiple(cli, _parse_args=D, _setup_logging=D) as mocks:
        mocks["_parse_args"].return_value = Mock(debug=False, config=path)
        with raises(SystemExit) as e:
            cli.main()


@mark.parametrize("c", ["-c", "--config"])
@mark.parametrize("d", ["-d", "--debug", None])
def test_cli__parse_args(c, d):
    fn = "a.yaml"
    args = cli._parse_args([pkgname, c, fn] + ([d] if d else []))
    assert isinstance(args.config, Path)
    assert str(args.config) == fn
    assert args.debug is bool(d)


@mark.parametrize("h", ["-h", "--help"])
def test_cli__parse_args_help(capsys, h):
    with raises(SystemExit) as e:
        cli._parse_args([pkgname, h])
    assert e.value.code == 0
    assert capsys.readouterr().out.startswith("usage:")


@mark.parametrize("v", ["-v", "--version"])
def test_cli__parse_args_version(capsys, v):
    with raises(SystemExit) as e:
        cli._parse_args([pkgname, v])
    assert e.value.code == 0
    assert re.match(r"^\w+ version \d+\.\d+\.\d+ build \d+$", capsys.readouterr().out.strip())


def test_cli__parse_args_required_arg_missing():
    with raises(SystemExit) as e:
        cli._parse_args([pkgname])
    assert e.value.code == 2


@mark.parametrize("debug", [True, False])
def test_cli__setup_logging(debug):
    with patch.object(logging, "basicConfig") as bc:
        cli._setup_logging(debug=debug)
        bc.assert_called_once_with(
            datefmt=ANY,
            format=ANY,
            level=logging.DEBUG if debug else logging.INFO,
            stream=cli.sys.stderr,
        )


def test_cli__version():
    assert re.match(r"^version \d+\.\d+\.\d+ build \d+$", cli._version())
