"""
Tests for wxvx.workflow.
"""

from datetime import datetime, timedelta, timezone
from pathlib import Path
from textwrap import dedent
from threading import Event
from unittest.mock import ANY, patch

import xarray as xr
import yaml
from iotaa import asset, external, ready, refs
from pytest import fixture, mark

from wxvx import times, util, variables, workflow

# Tests


def test_workflow_existing(fakefs):
    path = fakefs / "forecast"
    assert not ready(workflow.existing(path=path))
    path.touch()
    assert ready(workflow.existing(path=path))


def test_workflow_forecast_dataset(da, fakefs):
    path = fakefs / "forecast"
    assert not ready(workflow.forecast_dataset(fcstpath=path))
    path.touch()
    with patch.object(workflow.xr, "open_dataset", return_value=da.to_dataset()):
        val = workflow.forecast_dataset(fcstpath=path)
    assert ready(val)
    assert (da == refs(val).HGT).all()


def test_workflow_grib_index_data(c, idxdata, testvars, tc):
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
        val = workflow.grib_index_data(
            outdir=c.workdir, vxvars=testvars, tc=tc, url=c.baseline.template
        )
    assert refs(val) == idxdata


def test_workflow_grib_index_file(c):
    url = f"{c.baseline.template}.idx"
    with patch.object(workflow, "status", return_value=404):
        val = workflow.grib_index_file(outdir=c.workdir, url=url)
    path: Path = refs(val)
    assert not path.exists()
    path.parent.mkdir(parents=True, exist_ok=True)
    with (
        patch.object(workflow, "status", return_value=200),
        patch.object(workflow, "fetch") as fetch,
    ):
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


def test_workflow_grid_grib(c, idxdata, testvars, tc):
    var = variables.Var(name="t", levtype="isobaricInhPa", level=900)
    ready = Event()

    @external
    def mock(*_args, **_kwargs):
        yield "mock"
        yield asset(idxdata, ready.is_set)

    with patch.object(workflow, "grib_index_data", mock):
        val = workflow.grid_grib(c=c, tc=tc, var=var, vxvars=testvars)
        path = refs(val)
        assert not path.exists()
        ready.set()
        with patch.object(workflow, "fetch") as fetch:
            fetch.side_effect = lambda taskname, url, path, headers: path.touch()  # noqa: ARG005
            path.parent.mkdir(parents=True, exist_ok=True)
            workflow.grid_grib(c=c, tc=tc, var=var, vxvars=testvars)
        assert path.exists()


@mark.parametrize(("fail", "stdname", "varname"), [(False, "gh", "HGT"), (True, "foo", "FOO")])
def test_workflow_grid_nc(caplog, c_real, check_cf_metadata, da, fail, stdname, tc, varname):
    var = variables.Var(name=stdname, levtype="isobaricInhPa", level=1000)
    fcstpath = Path(c_real.workdir, "raw.forecast.nc")
    c_real.forecast.path = fcstpath
    da.to_netcdf(path=fcstpath)
    val = workflow.grid_nc(c=c_real, varname=varname, tc=tc, var=var)
    if fail:
        assert not ready(val)
        msg = f"Variable FOO valid at {tc.validtime.isoformat()} not found"
        assert msg in "\n".join(caplog.messages)
    else:
        assert ready(val)
        check_cf_metadata(ds=xr.open_dataset(refs(val), decode_timedelta=True), name="HGT")


def test_workflow_grid_stat_config(c, fakefs, fs):
    fs.add_real_file(util.resource_path("config.grid_stat"))
    var = variables.Var(name="2t", levtype="heightAboveGround", level=2)
    basepath = fakefs / "T2M.stat"
    kwargs = dict(c=c, basepath=basepath, varname="T2M", rundir=fakefs, var=var, prefix="foo")
    assert not ready(val := workflow.grid_stat_config(**kwargs, dry_run=True))
    assert not refs(val).is_file()
    assert ready(val := workflow.grid_stat_config(**kwargs))
    assert refs(val).is_file()


def test_workflow_plot(c, fakefs):
    @external
    def mock(*_args, **_kwargs):
        yield "mock"
        yield asset(Path("/some/file"), lambda: True)

    rundir = fakefs / "run" / "plot"
    path = rundir / "plot-T2M.png"
    taskname = f"Plot of stat data {path}"
    with (
        patch.object(workflow, "reformat", mock),
        patch.object(workflow, "plot_config", mock),
        patch.object(workflow, "mpexec", side_effect=lambda *_: path.touch()) as mpexec,
    ):
        rundir.mkdir(parents=True)
        val = workflow.plot(c=c, varname="T2M")
    runscript = str((rundir / refs(val).stem).with_suffix(".sh"))
    mpexec.assert_called_once_with(runscript, rundir, taskname)
    assert ready(val)
    assert path.is_file()


def test_workflow_plot_config(c, fakefs):
    varname, plotfn, statfn = "T2M", "plot-T2M.png", "T2M.stat"
    kwargs = dict(c=c, rundir=fakefs, varname=varname, plotfn=plotfn, statfn=statfn)
    assert not ready(val := workflow.plot_config(**kwargs, dry_run=True))
    assert not refs(val).is_file()
    val = workflow.plot_config(**kwargs)
    assert ready(val)
    config_data = yaml.safe_load(refs(val).read_text())
    assert config_data["fcst_var_val_1"] == {varname: ["RMSE"]}
    assert config_data["plot_filename"] == plotfn
    assert config_data["stat_input"] == statfn


def test_workflow_reformat(c, fakefs):
    @external
    def mock(*_args, **_kwargs):
        yield "mock"
        yield asset(Path("/some/file"), lambda: True)

    rundir = fakefs / "run" / "plot"
    path = rundir / "reformat.data"
    taskname = f"Reformatted grid_stat results {path}"
    with (
        patch.object(workflow, "reformat_config", mock),
        patch.object(workflow, "stats", mock),
        patch.object(workflow, "mpexec", side_effect=lambda *_: path.touch()) as mpexec,
    ):
        rundir.mkdir(parents=True)
        val = workflow.reformat(c=c, rundir=rundir)
    runscript = str((rundir / refs(val).stem).with_suffix(".sh"))
    mpexec.assert_called_once_with(runscript, rundir, taskname)
    assert ready(val)
    assert path.is_file()


def test_workflow_reformat_config(fakefs, fs):
    fs.add_real_file(util.resource_path("reformat.yaml"))
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


def test_workflow_stat(c, fakefs, tc, testvars):
    @external
    def mock(*_args, **_kwargs):
        yield "mock"
        yield asset(Path("/some/file"), lambda: True)

    rundir = fakefs / "run" / "stat" / "19700101" / "00" / "000"
    taskname = "MET grid_stat result 2t-heightAboveGround-0002 at 19700101 00Z 000"
    var = variables.Var(name="2t", levtype="heightAboveGround", level=2)
    kwargs = dict(c=c, varname="T2M", tc=tc, var=var, vxvars=testvars, prefix="foo")
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
    target = fakefs / "target" / "stats"
    link = c.workdir / "run" / "plot" / "stats"

    @external
    def mock(*_args, **_kwargs):
        yield "mock"
        yield asset(target, lambda: True)

    assert not link.exists()
    with patch.object(workflow, "stat", mock):
        workflow.stats(c=c)
    assert link.is_symlink()
    assert link.resolve() == target


def test_workflow_verification(c):
    @external
    def mock(*_args, **_kwargs):
        yield "mock"
        yield asset(Path("/some/file"), lambda: True)

    with patch.object(workflow, "plot", mock):
        val = workflow.verification(c=c)
    assert len(refs(val)) == len(c.variables)


# Fixtures


@fixture
def idxdata():
    return {
        "gh-isobaricInhPa-0900": variables.HRRRVar(
            name="HGT", levstr="900 mb", firstbyte=0, lastbyte=0
        ),
        "t-isobaricInhPa-0900": variables.HRRRVar(
            name="TMP", levstr="900 mb", firstbyte=2, lastbyte=2
        ),
    }


@fixture
def tc(da):
    cycle = datetime.fromtimestamp(int(da.time.values[0]), tz=timezone.utc)
    leadtime = timedelta(hours=int(da.lead_time.values[0]))
    return times.TimeCoords(cycle=cycle, leadtime=leadtime)


@fixture
def testvars():
    return {
        name: variables.Var(name=stdname, levtype="isobaricInhPa", level=900)
        for name, stdname in [("HGT", "gh"), ("TMP", "t")]
    }
