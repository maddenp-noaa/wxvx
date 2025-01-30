"""
Tests for wxvx.workflow.
"""

# pylint: disable=protected-access,redefined-outer-name

from datetime import datetime, timedelta
from pathlib import Path
from textwrap import dedent
from unittest.mock import ANY, Mock, patch

import xarray as xr
from iotaa import asset, ready, refs, task
from pytest import fixture, mark

from wxvx import time, variables, workflow

# Tests


def test_workflow_existing(fakefs):
    path = fakefs / "forecast"
    assert not ready(workflow.existing(path=path))
    path.touch()
    assert ready(workflow.existing(path=path))


def test_workflow_forecast_dataset(da, fakefs):
    path = fakefs / "forecast"
    assert not ready(workflow.forecast_dataset(forecast=path))
    path.touch()
    with patch.object(workflow.xr, "open_dataset", return_value=da.to_dataset()):
        val = workflow.forecast_dataset(forecast=path)
    assert ready(val)
    assert refs(val).HGT == da


def test_workflow_forecast_var(check_cf_metadata, da, tmp_path, validtime):
    var = variables.Var(name="gh", levtype="isobaricInhPa", level="1000")
    forecast = tmp_path / "raw.forecast.nc"
    da.to_netcdf(path=forecast)
    val = workflow.forecast_var(var=var, validtime=validtime, forecast=forecast, rundir=tmp_path)
    assert ready(val)
    check_cf_metadata(xr.open_dataset(refs(val))["HGT"])


def test_workflow_grib_message(fakefs, idxdata, testvars, url, validtime):
    var = variables.Var(name="t", levtype="isobaricInhPa", level="900")
    with patch.object(workflow, "grib_index_data") as grib_index_data:
        grib_index_data().ready = False
        val = workflow.grib_message(
            var=var, variables=testvars, validtime=validtime, rundir=fakefs, url=url
        )
        path = refs(val)
        assert not path.exists()
        grib_index_data().ready = True
        grib_index_data()._assets = asset(idxdata, lambda: True)
        with patch.object(workflow, "fetch") as fetch:
            fetch.side_effect = lambda taskname, url, path, headers: path.touch()
            path.parent.mkdir(parents=True, exist_ok=True)
            workflow.grib_message(
                var=var, variables=testvars, validtime=validtime, rundir=fakefs, url=url
            )
        assert path.exists()


def test_workflow_grib_index_data(fakefs, idxdata, testvars, ts, url, validtime):
    gribidx = """
    1:0:d=2024040103:HGT:900 mb:anl:
    2:1:d=2024040103:FOO:900 mb:anl:
    3:2:d=2024040103:TMP:900 mb:anl:
    """
    idxfile = fakefs / "gfs.idx"
    idxfile.write_text(dedent(gribidx).strip())
    grib_index_local = Mock()
    grib_index_local()._assets = asset(idxfile, idxfile.exists)
    with patch.object(workflow, "grib_index_local", grib_index_local):
        val = workflow.grib_index_data(
            variables=testvars, validtime=validtime, rundir=fakefs, url=url, ts=ts
        )
    assert refs(val) == idxdata


def test_workflow_grib_index_local(fakefs, ts, url, validtime):
    url = f"{url}.idx"
    with patch.object(workflow, "status", return_value=404):
        val = workflow.grib_index_local(validtime=validtime, rundir=fakefs, url=url, ts=ts)
    path: Path = refs(val)
    assert not path.exists()
    path.parent.mkdir(parents=True, exist_ok=True)
    with patch.object(workflow, "status", return_value=200):
        with patch.object(workflow, "fetch") as fetch:
            fetch.side_effect = lambda taskname, url, path: path.touch()
            workflow.grib_index_local(validtime=validtime, rundir=fakefs, url=url, ts=ts)
        fetch.assert_called_once_with(taskname=ANY, url=url, path=path)
    assert path.exists()


@mark.parametrize("code", [200, 404])
def test_workflow_grib_index_remote(code, ts, url):
    with patch.object(workflow, "status", return_value=code) as status:
        assert ready(workflow.grib_index_remote(url=url, ts=ts)) is (code == 200)
    status.assert_called_with(url=url)


def test_workflow_verify_all(config):
    @task
    def test_verify_one(**kwargs):
        yield "test %s %s" % (str(kwargs["var"]), str(kwargs["validtime"]))
        yield asset(kwargs, lambda: True)
        yield None

    with patch.object(workflow, "verify_one", test_verify_one):
        val = workflow.verify_all(config=config)
    validtimes = time.validtimes(cycles=config["cycles"], leadtimes=config["leadtimes"])
    assert len(refs(val)) == len(validtimes) * len(config["variables"])
    assert set(x["validtime"] for x in refs(val)) == set(validtimes)


@mark.skip()
def test_workflow_verify_one():
    pass


# Fixtures


@fixture
def fakefs(fs):
    return Path(fs.create_dir("/test").path)


@fixture
def idxdata():
    return {
        "gh-isobaricInhPa-0900": variables.GFSVar(
            name="HGT", levstr="900 mb", firstbyte=0, lastbyte=0
        ),
        "t-isobaricInhPa-0900": variables.GFSVar(
            name="TMP", levstr="900 mb", firstbyte=2, lastbyte=2
        ),
    }


@fixture
def testvars():
    return {variables.Var(name=name, levtype="isobaricInhPa", level="900") for name in ("gh", "t")}


@fixture
def ts():
    return datetime.utcnow().isoformat()


@fixture
def url():
    return "https://some.url/path/to/a.grib2"


@fixture
def validtime(da):
    cycle = datetime.fromtimestamp(int(da.time.values[0]))
    leadtime = timedelta(hours=int(da.lead_time.values[0]))
    return time.TimeCoords(cycle=cycle, leadtime=leadtime)
