"""
Tests for wxvx.workflow.
"""

import logging
from pathlib import Path
from textwrap import dedent
from threading import Event
from unittest.mock import ANY, patch

import xarray as xr
import yaml
from iotaa import asset, external, ready, refs
from pytest import fixture, mark

from wxvx import util, variables, workflow
from wxvx.types import Source

logging.getLogger().setLevel(logging.DEBUG)

# Tests


def test_workflow_existing(fakefs):
    path = fakefs / "forecast"
    assert not ready(workflow.existing(path=path))
    path.touch()
    assert ready(workflow.existing(path=path))


def test_workflow_forecast_dataset(da, fakefs):
    path = fakefs / "forecast"
    assert not ready(workflow.forecast_dataset(path=path))
    path.touch()
    with patch.object(workflow.xr, "open_dataset", return_value=da.to_dataset()):
        val = workflow.forecast_dataset(path=path)
    assert ready(val)
    assert (da == refs(val).HGT).all()


def test_workflow_grib_index_data(c, tc):
    gribidx = """
    1:0:d=2024040103:HGT:900 mb:anl:
    2:1:d=2024040103:FOO:900 mb:anl:
    3:2:d=2024040103:TMP:900 mb:anl:
    """
    idxfile = c.workdir / "hrrr.idx"
    idxfile.write_text(dedent(gribidx).strip())

    @external
    def mock(*_args, **_kwargs):
        yield "mock"
        yield asset(idxfile, idxfile.exists)

    with patch.object(workflow, "grib_index_file", mock):
        val = workflow.grib_index_data(c=c, outdir=c.workdir, tc=tc, url=c.baseline.template)
    assert refs(val) == {
        "gh-isobaricInhPa-0900": variables.HRRRVar(
            name="HGT", levstr="900 mb", firstbyte=0, lastbyte=0
        )
    }


def test_workflow_grib_index_file(c):
    url = f"{c.baseline.template}.idx"
    with patch.object(workflow, "grib_index_remote"):
        val = workflow.grib_index_file(outdir=c.workdir, url=url)
        path: Path = refs(val)
        assert not path.exists()
        path.parent.mkdir(parents=True, exist_ok=True)
        with patch.object(workflow, "fetch") as fetch:
            fetch.side_effect = lambda taskname, url, path: path.touch()  # noqa: ARG005
            workflow.grib_index_file(outdir=c.workdir, url=url)
        fetch.assert_called_once_with(ANY, url, path)
    assert path.exists()


@mark.parametrize("code", [200, 404])
def test_workflow_grib_index_remote(c, code):
    url = c.baseline.template
    with patch.object(workflow, "status", return_value=code) as status:
        assert ready(workflow.grib_index_remote(url=url)) is (code == 200)
    status.assert_called_with(url)


def test_workflow_grid_grib(c, tc):
    idxdata = {
        "gh-isobaricInhPa-0900": variables.HRRRVar(
            name="HGT", levstr="900 mb", firstbyte=0, lastbyte=0
        ),
        "t-isobaricInhPa-0900": variables.HRRRVar(
            name="TMP", levstr="900 mb", firstbyte=2, lastbyte=2
        ),
    }
    ready = Event()

    @external
    def mock(*_args, **_kwargs):
        yield "mock"
        yield asset(idxdata, ready.is_set)

    var = variables.Var(name="t", level_type="isobaricInhPa", level=900)
    with patch.object(workflow, "grib_index_data", mock):
        val = workflow.grid_grib(c=c, tc=tc, var=var)
        path = refs(val)
        assert not path.exists()
        ready.set()
        with patch.object(workflow, "fetch") as fetch:
            fetch.side_effect = lambda taskname, url, path, headers: path.touch()  # noqa: ARG005
            path.parent.mkdir(parents=True, exist_ok=True)
            workflow.grid_grib(c=c, tc=tc, var=var)
        assert path.exists()


def test_workflow_grid_nc(c_real, check_cf_metadata, da, tc):
    var = variables.Var(name="gh", level_type="isobaricInhPa", level=900)
    path = Path(c_real.workdir, "a.nc")
    da.to_netcdf(path)
    c_real.forecast.path = path
    val = workflow.grid_nc(c=c_real, varname="HGT", tc=tc, var=var)
    assert ready(val)
    assert check_cf_metadata(ds=xr.open_dataset(refs(val), decode_timedelta=True), name="HGT")


def test_workflow_grid_stat_config(c, fakefs, fs):
    fs.add_real_file(util.resource_path("config.grid_stat"))
    var = variables.Var(name="2t", level_type="heightAboveGround", level=2)
    basepath = fakefs / "T2M.stat"
    kwargs = dict(
        c=c,
        poly_path="/path/to/forecast.nc",
        basepath=basepath,
        varname="T2M",
        rundir=fakefs,
        var=var,
        prefix="foo",
        source=Source.FORECAST,
    )
    assert not ready(val := workflow.grid_stat_config(**kwargs, dry_run=True))
    assert not refs(val).is_file()
    assert ready(val := workflow.grid_stat_config(**kwargs))
    assert refs(val).is_file()


def test_workflow_plot(c, fakefs):
    @external
    def mock(*_args, **_kwargs):
        yield "mock"
        yield asset(Path("/some/file"), lambda: True)

    varname, level = "T2M", 2
    var = variables.Var(name="2t", level_type="heightAboveGround", level=level)
    rundir = fakefs / "run" / "plot" / str(var)
    path = rundir / "plot.png"
    taskname = f"Plot {path}"
    with (
        patch.object(workflow, "reformat", mock),
        patch.object(workflow, "plot_config", mock),
        patch.object(workflow, "mpexec", side_effect=lambda *_: path.touch()) as mpexec,
    ):
        rundir.mkdir(parents=True)
        val = workflow.plot(c=c, varname=varname, level=level)
    runscript = str((rundir / refs(val).stem).with_suffix(".sh"))
    mpexec.assert_called_once_with(runscript, rundir, taskname)
    assert ready(val)
    assert path.is_file()


def test_workflow_plot_config(c, fakefs):
    var = variables.Var(name="2t", level_type="heightAboveGround", level=2)
    varname, plot_fn, stat_fn = "T2M", f"plot-{var}.png", f"{var}.stat"
    kwargs = dict(c=c, rundir=fakefs, varname=varname, var=var, plot_fn=plot_fn, stat_fn=stat_fn)
    assert not ready(val := workflow.plot_config(**kwargs, dry_run=True))
    assert not refs(val).is_file()
    val = workflow.plot_config(**kwargs)
    assert ready(val)
    config_data = yaml.safe_load(refs(val).read_text())
    assert config_data["fcst_var_val_1"] == {varname: ["RMSE"]}
    assert config_data["plot_filename"] == plot_fn
    assert config_data["stat_input"] == stat_fn


def test_workflow_reformat(c, fakefs, testvars):
    @external
    def mock(*_args, **_kwargs):
        yield "mock"
        yield asset(Path("/some/file"), lambda: True)

    varname = "HGT"
    var = testvars[varname]
    rundir = fakefs / "run" / "plot" / str(var)
    path = rundir / "reformat.data"
    taskname = f"Reformatted stats {path}"
    with (
        patch.object(workflow, "reformat_config", mock),
        patch.object(workflow, "stats", mock),
        patch.object(workflow, "mpexec", side_effect=lambda *_: path.touch()) as mpexec,
    ):
        rundir.mkdir(parents=True)
        val = workflow.reformat(c=c, varname=varname, rundir=rundir)
    runscript = str((rundir / refs(val).stem).with_suffix(".sh"))
    mpexec.assert_called_once_with(runscript, rundir, taskname)
    assert ready(val)
    assert path.is_file()


def test_workflow_reformat_config(fakefs):
    val = workflow.reformat_config(rundir=fakefs, dry_run=True)
    assert not ready(val)
    assert not refs(val).is_file()
    val = workflow.reformat_config(rundir=fakefs)
    assert ready(val)
    assert refs(val).is_file()


def test_workflow_runscript(fakefs):
    expected = fakefs / "foo.sh"
    assert not expected.is_file()
    val = workflow.runscript(basepath=fakefs / "foo.png", content="commands")
    assert ready(val)
    assert refs(val) == expected
    assert expected.is_file()


def test_workflow_stat(c, fakefs, tc):
    @external
    def mock(*_args, **_kwargs):
        yield "mock"
        yield asset(Path("/some/file"), lambda: True)

    rundir = fakefs / "run" / "stat" / "19700101" / "00" / "000"
    taskname = "MET stats for baseline 2t-heightAboveGround-0002 at 19700101 00Z 000"
    var = variables.Var(name="2t", level_type="heightAboveGround", level=2)
    kwargs = dict(c=c, varname="T2M", tc=tc, var=var, prefix="foo", source=Source.BASELINE)
    with (
        patch.object(workflow, "grid_grib", mock),
        patch.object(workflow, "grid_nc", mock),
        patch.object(workflow, "grid_stat_config", mock),
        patch.object(workflow, "mpexec") as mpexec,
    ):
        stat = refs(workflow.stat(**kwargs, dry_run=True))
        assert not stat.is_file()
        mpexec.side_effect = lambda *_: stat.touch()
        rundir.mkdir(parents=True)
        workflow.stat(**kwargs)
    runscript = str((rundir / stat.stem).with_suffix(".sh"))
    mpexec.assert_called_once_with(runscript, rundir, taskname)
    assert stat.is_file()


def test_workflow_stats(c, fakefs):
    target = fakefs / "target" / "a.stats"
    rundir = c.workdir / "run" / "plot"
    link = rundir / "a.stats"

    @external
    def mock(*_args, **_kwargs):
        yield "mock"
        yield asset(target, lambda: True)

    assert not link.exists()
    with patch.object(workflow, "stat", mock):
        workflow.stats(c=c, varname="T2M", rundir=rundir)
    assert link.is_symlink()
    assert link.resolve() == target


def test_workflow_verification(c):
    @external
    def mock(*_args, **_kwargs):
        yield "mock"
        yield asset(Path("/some/file"), lambda: False)

    with patch.object(workflow, "plot", mock):
        val = workflow.verification(c=c)
    assert len(refs(val)) == len(c.variables)


# Fixtures


@fixture
def testvars():
    return {
        name: variables.Var(name=standard_name, level_type="isobaricInhPa", level=900)
        for name, standard_name in [("HGT", "gh"), ("TMP", "t")]
    }
