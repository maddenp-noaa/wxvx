"""
Tests for wxvx.workflow.
"""

from pathlib import Path
from textwrap import dedent
from threading import Event
from types import SimpleNamespace as ns
from unittest.mock import ANY, patch

import xarray as xr
import yaml
from iotaa import asset, external, ready, refs
from pytest import fixture, mark

from wxvx import util, variables, workflow
from wxvx.times import TimeCoords, validtimes
from wxvx.types import Source
from wxvx.variables import Var

# Task Tests


def test_workflow_grids(c, noop):
    with patch.object(workflow, "_grid_grib", noop), patch.object(workflow, "_grid_nc", noop):
        val = workflow.grids(c=c)
    n_validtimes = len(validtimes(c.cycles, c.leadtimes))
    n_var_level_pairs = len(list(workflow._varnames_and_levels(c)))
    n_grids_per_pair = 3  # forecast grid, baseline grid, comparision grid
    assert len(refs(val)) == n_var_level_pairs * n_validtimes * n_grids_per_pair


def test_workflow_plots(c, noop):
    with patch.object(workflow, "_plot", noop):
        val = workflow.plots(c=c)
    assert len(refs(val)) == len(c.variables) + 1  # for 2x SPFH levels


def test_workflow_stats(c, noop):
    with patch.object(workflow, "_statreqs", return_value=[noop()]) as _statreqs:
        val = workflow.stats(c=c)
    assert len(refs(val)) == len(c.variables) + 1  # for 2x SPFH levels


def test_workflow__existing(fakefs):
    path = fakefs / "forecast"
    assert not ready(workflow._existing(path=path))
    path.touch()
    assert ready(workflow._existing(path=path))


def test_workflow__forecast_dataset(da, fakefs):
    path = fakefs / "forecast"
    assert not ready(workflow._forecast_dataset(path=path))
    path.touch()
    with patch.object(workflow.xr, "open_dataset", return_value=da.to_dataset()):
        val = workflow._forecast_dataset(path=path)
    assert ready(val)
    assert (da == refs(val).HGT).all()


def test_workflow__grib_index_data(c, tc):
    gribidx = """
    1:0:d=2024040103:HGT:900 mb:anl:
    2:1:d=2024040103:FOO:900 mb:anl:
    3:2:d=2024040103:TMP:900 mb:anl:
    """
    idxfile = c.paths.grids / "hrrr.idx"
    idxfile.write_text(dedent(gribidx).strip())

    @external
    def mock(*_args, **_kwargs):
        yield "mock"
        yield asset(idxfile, idxfile.exists)

    with patch.object(workflow, "_grib_index_file", mock):
        val = workflow._grib_index_data(c=c, outdir=c.paths.grids, tc=tc, url=c.baseline.template)
    assert refs(val) == {
        "gh-isobaricInhPa-0900": variables.HRRR(
            name="HGT", levstr="900 mb", firstbyte=0, lastbyte=0
        )
    }


def test_workflow__grib_index_file(c):
    url = f"{c.baseline.template}.idx"
    with patch.object(workflow, "_grib_index_remote"):
        val = workflow._grib_index_file(outdir=c.paths.grids, url=url)
        path: Path = refs(val)
        assert not path.exists()
        path.parent.mkdir(parents=True, exist_ok=True)
        with patch.object(workflow, "fetch") as fetch:
            fetch.side_effect = lambda taskname, url, path: path.touch()  # noqa: ARG005
            workflow._grib_index_file(outdir=c.paths.grids, url=url)
        fetch.assert_called_once_with(ANY, url, path)
    assert path.exists()


@mark.parametrize("code", [200, 404])
def test_workflow__grib_index_remote(c, code):
    url = c.baseline.template
    with patch.object(workflow, "status", return_value=code) as status:
        assert ready(workflow._grib_index_remote(url=url)) is (code == 200)
    status.assert_called_with(url)


def test_workflow__grid_grib(c, tc):
    idxdata = {
        "gh-isobaricInhPa-0900": variables.HRRR(
            name="HGT", levstr="900 mb", firstbyte=0, lastbyte=0
        ),
        "t-isobaricInhPa-0900": variables.HRRR(
            name="TMP", levstr="900 mb", firstbyte=2, lastbyte=2
        ),
    }
    ready = Event()

    @external
    def mock(*_args, **_kwargs):
        yield "mock"
        yield asset(idxdata, ready.is_set)

    var = variables.Var(name="t", level_type="isobaricInhPa", level=900)
    with patch.object(workflow, "_grib_index_data", mock):
        val = workflow._grid_grib(c=c, tc=tc, var=var)
        path = refs(val)
        assert not path.exists()
        ready.set()
        with patch.object(workflow, "fetch") as fetch:
            fetch.side_effect = lambda taskname, url, path, headers: path.touch()  # noqa: ARG005
            path.parent.mkdir(parents=True, exist_ok=True)
            workflow._grid_grib(c=c, tc=tc, var=var)
        assert path.exists()


def test_workflow__grid_nc(c_real_fs, check_cf_metadata, da, tc):
    var = variables.Var(name="gh", level_type="isobaricInhPa", level=900)
    path = Path(c_real_fs.paths.grids, "a.nc")
    da.to_netcdf(path)
    object.__setattr__(c_real_fs.forecast, "path", path)
    val = workflow._grid_nc(c=c_real_fs, varname="HGT", tc=tc, var=var)
    assert ready(val)
    assert check_cf_metadata(ds=xr.open_dataset(refs(val), decode_timedelta=True), name="HGT")


def test_workflow__grid_stat_config(c, fakefs, fs):
    fs.add_real_file(util.resource_path("config.grid_stat"))
    var = variables.Var(name="refc", level_type="atmosphere")
    basepath = fakefs / "refc.stat"
    kwargs = dict(
        c=c,
        poly_path="/path/to/forecast.nc",
        basepath=basepath,
        varname="REFC",
        rundir=fakefs,
        var=var,
        prefix="foo",
        source=Source.FORECAST,
    )
    assert not ready(val := workflow._grid_stat_config(**kwargs, dry_run=True))
    assert not refs(val).is_file()
    assert ready(val := workflow._grid_stat_config(**kwargs))
    assert refs(val).is_file()


def test_workflow__plot(c, fakefs):
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
        patch.object(workflow, "_reformat", mock),
        patch.object(workflow, "_plot_config", mock),
        patch.object(workflow, "mpexec", side_effect=lambda *_: path.touch()) as mpexec,
    ):
        rundir.mkdir(parents=True)
        val = workflow._plot(c=c, varname=varname, level=level)
    runscript = str((rundir / refs(val).stem).with_suffix(".sh"))
    mpexec.assert_called_once_with(runscript, rundir, taskname)
    assert ready(val)
    assert path.is_file()


def test_workflow__plot_config(c, fakefs):
    var = variables.Var(name="2t", level_type="heightAboveGround", level=2)
    varname, plot_fn, stat_fn = "T2M", f"plot-{var}.png", f"{var}.stat"
    kwargs = dict(c=c, rundir=fakefs, varname=varname, var=var, plot_fn=plot_fn, stat_fn=stat_fn)
    assert not ready(val := workflow._plot_config(**kwargs, dry_run=True))
    assert not refs(val).is_file()
    val = workflow._plot_config(**kwargs)
    assert ready(val)
    config_data = yaml.safe_load(refs(val).read_text())
    assert config_data["fcst_var_val_1"] == {varname: ["RMSE"]}
    assert config_data["plot_filename"] == plot_fn
    assert config_data["stat_input"] == stat_fn


def test_workflow__reformat(c, fakefs, testvars):
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
        patch.object(workflow, "_reformat_config", mock),
        patch.object(workflow, "_stat_links", mock),
        patch.object(workflow, "mpexec", side_effect=lambda *_: path.touch()) as mpexec,
    ):
        rundir.mkdir(parents=True)
        val = workflow._reformat(c=c, varname=varname, level=900, rundir=rundir)
    runscript = str((rundir / refs(val).stem).with_suffix(".sh"))
    mpexec.assert_called_once_with(runscript, rundir, taskname)
    assert ready(val)
    assert path.is_file()


def test_workflow__reformat_config(c, fakefs):
    val = workflow._reformat_config(c=c, varname="HGT", rundir=fakefs, dry_run=True)
    assert not ready(val)
    assert not refs(val).is_file()
    val = workflow._reformat_config(c, varname="HGT", rundir=fakefs)
    assert ready(val)
    assert refs(val).is_file()


def test_workflow__runscript(fakefs):
    expected = fakefs / "foo.sh"
    assert not expected.is_file()
    val = workflow._runscript(basepath=fakefs / "foo.png", content="commands")
    assert ready(val)
    assert refs(val) == expected
    assert expected.is_file()


def test_workflow__stat(c, fakefs, tc):
    @external
    def mock(*_args, **_kwargs):
        yield "mock"
        yield asset(Path("/some/file"), lambda: True)

    rundir = fakefs / "run" / "stats" / "19700101" / "00" / "000"
    taskname = "MET stats for baseline 2t-heightAboveGround-0002 at 19700101 00Z 000"
    var = variables.Var(name="2t", level_type="heightAboveGround", level=2)
    kwargs = dict(c=c, varname="T2M", tc=tc, var=var, prefix="foo", source=Source.BASELINE)
    with (
        patch.object(workflow, "_grid_grib", mock),
        patch.object(workflow, "_grid_nc", mock),
        patch.object(workflow, "_grid_stat_config", mock),
        patch.object(workflow, "mpexec") as mpexec,
    ):
        stat = refs(workflow._stat(**kwargs, dry_run=True))
        assert not stat.is_file()
        mpexec.side_effect = lambda *_: stat.touch()
        rundir.mkdir(parents=True)
        workflow._stat(**kwargs)
    runscript = str((rundir / stat.stem).with_suffix(".sh"))
    mpexec.assert_called_once_with(runscript, rundir, taskname)
    assert stat.is_file()


def test_workflow__stat_links(c, fakefs):
    target = fakefs / "target" / "a.stats"

    @external
    def mock(*_args, **_kwargs):
        yield "mock"
        yield asset(target, lambda: True)

    rundir = c.paths.run / "plot"
    link = rundir / "a.stats"
    assert not link.exists()
    with patch.object(workflow, "_stat", mock):
        workflow._stat_links(c=c, varname="T2M", level=2, rundir=rundir)
    assert link.is_symlink()
    assert link.resolve() == target


# Support Tests


def test__meta(c):
    meta = workflow._meta(c=c, varname="HGT")
    assert meta.cf_standard_name == "geopotential_height"
    assert meta.level_type == "isobaricInhPa"


def test__statargs(c, statkit):
    with (
        patch.object(workflow, "_vxvars", return_value={statkit.var: statkit.varname}),
        patch.object(workflow, "validtimes", return_value=[statkit.tc]),
    ):
        statargs = workflow._statargs(
            c=c, varname=statkit.varname, level=statkit.level, source=statkit.source
        )
    assert list(statargs) == [
        (c, statkit.varname, statkit.tc, statkit.var, statkit.prefix, statkit.source)
    ]


def test__statreqs(c, statkit):
    with (
        patch.object(workflow, "_stat") as _stat,
        patch.object(workflow, "_vxvars", return_value={statkit.var: statkit.varname}),
        patch.object(workflow, "validtimes", return_value=[statkit.tc]),
    ):
        reqs = workflow._statreqs(c=c, varname=statkit.varname, level=statkit.level)
    assert len(reqs) == 2
    assert _stat.call_count == 2
    args = (c, statkit.varname, statkit.tc, statkit.var)
    assert _stat.call_args_list[0].args == (
        *args,
        f"forecast_gh_{statkit.level_type}_{statkit.level:04d}",
        Source.FORECAST,
    )
    assert _stat.call_args_list[1].args == (
        *args,
        f"baseline_gh_{statkit.level_type}_{statkit.level:04d}",
        Source.BASELINE,
    )


def test__var(c):
    assert workflow._var(c=c, varname="HGT", level=900) == Var("gh", "isobaricInhPa", 900)


def test__varnames_and_levels(c):
    assert list(workflow._varnames_and_levels(c=c)) == [
        ("HGT", 900),
        ("REFC", None),
        ("SPFH", 900),
        ("SPFH", 1000),
        ("T2M", 2),
    ]


def test__vxvars(c):
    assert workflow._vxvars(c=c) == {
        Var("2t", "heightAboveGround", 2): "T2M",
        Var("gh", "isobaricInhPa", 900): "HGT",
        Var("q", "isobaricInhPa", 1000): "SPFH",
        Var("q", "isobaricInhPa", 900): "SPFH",
        Var("refc", "atmosphere"): "REFC",
    }


# Fixtures


@fixture
def noop():
    @external
    def noop(*_args, **_kwargs):
        yield "mock"
        yield asset(None, lambda: False)

    return noop


@fixture
def statkit(utc):
    level = 900
    level_type = "isobaricInhPa"
    return ns(
        level=level,
        level_type=level_type,
        prefix=f"forecast_gh_{level_type}_{level:04d}",
        source=Source.FORECAST,
        tc=TimeCoords(utc(2025, 3, 2, 12)),
        var=Var("gh", level_type, level),
        varname="HGT",
    )


@fixture
def testvars():
    return {
        varname: variables.Var(name=name, level_type="isobaricInhPa", level=900)
        for varname, name in [("HGT", "gh"), ("TMP", "t")]
    }
