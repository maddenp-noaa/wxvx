"""
Tests for wxvx.cli.
"""

# pylint: disable=protected-access,redefined-outer-name

import re
from pathlib import Path
from unittest.mock import DEFAULT as D
from unittest.mock import Mock, patch

import yaml
from pytest import mark, raises

from wxvx import cli
from wxvx.tests.test_schema import config  # pylint: disable=unused-import
from wxvx.util import pkgname, resource_path

# Tests


def test_cli_main(config, fs):
    fs.add_real_file(resource_path("info.json"))
    fs.add_real_file(resource_path("config.jsonschema"))
    with patch.multiple(cli, workflow=D, sys=D, use_uwtools_logger=D) as mocks:
        cf = fs.create_file("/path/to/config.yaml", contents=yaml.safe_dump(config))
        argv = [pkgname, "-c", cf.path]
        mocks["sys"].argv = argv
        with patch.object(cli, "_parse_args", wraps=cli._parse_args) as _parse_args:
            cli.main()
        _parse_args.assert_called_once_with(argv)
    mocks["use_uwtools_logger"].assert_called_once_with(verbose=False)
    mocks["workflow"].go.assert_called_once_with(config)


def test_cli_main_bad_config(fs):
    resources_dir = resource_path("")
    config_file = Path(fs.create_file(resources_dir / "test.yaml", contents="{}").path)
    fs.add_real_file(resources_dir / "config.jsonschema")
    with patch.multiple(cli, _parse_args=D, use_uwtools_logger=D) as mocks:
        mocks["_parse_args"].return_value = Mock(debug=False, config=config_file)
        with raises(SystemExit) as e:
            cli.main()
    assert e.value.code == 1


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


def test_cli__version():
    assert re.match(r"^version \d+\.\d+\.\d+ build \d+$", cli._version())
