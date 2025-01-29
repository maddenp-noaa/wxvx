"""
Tests for wxvx.workflow.
"""

# pylint: disable=redefined-outer-name

from pathlib import Path
from unittest.mock import patch

from iotaa import ready, refs
from pytest import fixture

from wxvx import workflow

# Fixtures


@fixture
def fakefs(fs):
    return Path(fs.create_dir("/test").path)


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
