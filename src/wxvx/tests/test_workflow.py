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


@mark.parametrize(("fail", "stdname", "varname"), [(False, "gh", "HGT"), (True, "foo", "FOO")])
def test_workflow_forecast_variable(
    caplog, c_real, check_cf_metadata, da, fail, stdname, tc, varname
):
    var = variables.Var(name=stdname, levtype="isobaricInhPa", level=1000)
    fcstpath = Path(c_real.workdir, "raw.forecast.nc")
    c_real.forecast.path = fcstpath
    da.to_netcdf(path=fcstpath)
    val = workflow.forecast_variable(c=c_real, varname=varname, tc=tc, var=var)
    if fail:
        assert not ready(val)
        msg = f"Variable FOO valid at {tc.validtime.isoformat()} not found"
        assert msg in "\n".join(caplog.messages)
    else:
        assert ready(val)
        check_cf_metadata(ds=xr.open_dataset(refs(val), decode_timedelta=True), name="HGT")


def test_workflow_grib_message(c, idxdata, testvars, tc):
    var = variables.Var(name="t", levtype="isobaricInhPa", level=900)
    ready = Event()

    @external
    def mock(*_args, **_kwargs):
        yield "mock"
        yield asset(idxdata, ready.is_set)

    with patch.object(workflow, "grib_index_data", mock):
        val = workflow.grib_message(c=c, tc=tc, var=var, vxvars=testvars)
        path = refs(val)
        assert not path.exists()
        ready.set()
        with patch.object(workflow, "fetch") as fetch:
            fetch.side_effect = lambda taskname, url, path, headers: path.touch()  # noqa: ARG005
            path.parent.mkdir(parents=True, exist_ok=True)
            workflow.grib_message(c=c, tc=tc, var=var, vxvars=testvars)
        assert path.exists()


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

    with patch.object(workflow, "grib_index_local", mock):
        val = workflow.grib_index_data(c=c, vxvars=testvars, tc=tc, url=c.baseline.template)
    assert refs(val) == idxdata


def test_workflow_grib_index_local(c, tc):
    url = f"{c.baseline.template}.idx"
    with patch.object(workflow, "status", return_value=404):
        val = workflow.grib_index_local(c, tc, url)
    path: Path = refs(val)
    assert not path.exists()
    path.parent.mkdir(parents=True, exist_ok=True)
    with (
        patch.object(workflow, "status", return_value=200),
        patch.object(workflow, "fetch") as fetch,
    ):
        fetch.side_effect = lambda taskname, url, path: path.touch()  # noqa: ARG005
        workflow.grib_index_local(c, tc, url)
    fetch.assert_called_once_with(ANY, url, path)
    assert path.exists()


@mark.parametrize("code", [200, 404])
def test_workflow_grib_index_remote(c, code, utc):
    url = c.baseline.template
    tc = times.TimeCoords(cycle=utc(2025, 1, 30, 12))
    with patch.object(workflow, "status", return_value=code) as status:
        assert ready(workflow.grib_index_remote(url=url, tc=tc)) is (code == 200)
    status.assert_called_with(url)


def test_workflow_grid_stat_config(c, fakefs, fs):
    fs.add_real_file(util.resource_path("config.grid_stat"))
    var = variables.Var(name="2t", levtype="heightAboveGround", level=2)
    kwargs = dict(c=c, basepath=fakefs / "T2M.stat", varname="T2M", rundir=fakefs, var=var)
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
    taskname = f"Plotted stat data {path}"
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
    taskname = f"Reformatted stat data {path}"
    with (
        patch.object(workflow, "reformat_config", mock),
        patch.object(workflow, "statfiles", mock),
        patch.object(workflow, "mpexec", side_effect=lambda *_: path.touch()) as mpexec,
    ):
        rundir.mkdir(parents=True)
        val = workflow.reformat(c=c)
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
    val = workflow.runscript(taskname="foo", basepath=fakefs / "foo.png", content="commands")
    assert ready(val)
    assert refs(val) == expected
    assert expected.is_file()


def test_workflow_statfile(c, fakefs, tc, testvars):
    @external
    def mock(*_args, **_kwargs):
        yield "mock"
        yield asset(Path("/some/file"), lambda: True)

    rundir = fakefs / "run" / "19700101" / "00" / "000"
    taskname = "MET grid_stat results for 2t-heightAboveGround-0002 at 1970-01-01T00:00:00"
    var = variables.Var(name="2t", levtype="heightAboveGround", level=2)
    kwargs = dict(c=c, varname="T2M", tc=tc, var=var, vxvars=testvars)
    with (
        patch.object(workflow, "forecast_variable", mock),
        patch.object(workflow, "grib_message", mock),
        patch.object(workflow, "grid_stat_config", mock),
        patch.object(workflow, "mpexec") as mpexec,
    ):
        statfile = refs(workflow.statfile(**kwargs, dry_run=True))
        assert not statfile.is_file()
        mpexec.side_effect = lambda *_: statfile.touch()
        rundir.mkdir(parents=True)
        workflow.statfile(**kwargs)
    runscript = str((rundir / statfile.stem).with_suffix(".sh"))
    mpexec.assert_called_once_with(runscript, rundir, taskname)
    assert statfile.is_file()


def test_workflow_statfiles(c, fakefs):
    target = fakefs / "target" / "stats"
    link = c.workdir / "run" / "plot" / "stats"

    @external
    def mock(*_args, **_kwargs):
        yield "mock"
        yield asset(target, lambda: True)

    assert not link.exists()
    with patch.object(workflow, "statfile", mock):
        workflow.statfiles(c=c)
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
