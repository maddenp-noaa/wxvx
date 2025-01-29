"""
Tests for wxvx.workflow.
"""

# pylint: disable=redefined-outer-name

from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import xarray as xr
from iotaa import ready, refs
from pytest import fixture

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


def test_workflow_forecast_var(check_cf_metadata, da, tmp_path):
    var = variables.Var(name="gh", levtype="isobaricInhPa", level="1000")
    validtime = time.TimeCoords(dt=datetime.utcfromtimestamp(da.time.values[0]))
    forecast = tmp_path / "raw.forecast.nc"
    da.to_netcdf(path=forecast)
    val = workflow.forecast_var(var=var, validtime=validtime, forecast=forecast, rundir=tmp_path)
    assert ready(val)
    da = xr.open_dataset(refs(val))["HGT"]
    check_cf_metadata(da)


# Fixtures


@fixture
def fakefs(fs):
    return Path(fs.create_dir("/test").path)
