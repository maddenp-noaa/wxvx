"""
Tests for wxvx.workflow.
"""

# pylint: disable=redefined-outer-name

from datetime import datetime
from pathlib import Path
from unittest.mock import ANY, patch

import xarray as xr
from iotaa import ready, refs
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


def test_workflow_grib_message():
    pass


def test_workflow_grib_index_data():
    pass


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


def test_workflow_verify_all():
    pass


def test_workflow_verify_one():
    pass


# Fixtures


@fixture
def fakefs(fs):
    return Path(fs.create_dir("/test").path)


@fixture
def ts():
    return datetime.utcnow().isoformat()


@fixture
def url():
    return "https://some.url/path/to/a.grib2"


@fixture
def validtime(da):
    return time.TimeCoords(dt=datetime.utcfromtimestamp(da.time.values[0]))
