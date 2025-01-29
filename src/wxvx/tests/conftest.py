import numpy as np
import xarray as xr
from pytest import fixture


@fixture
def da():
    return xr.DataArray(
        name="HGT",
        data=np.zeros((1, 1, 1, 1, 1)),
        dims=["latitude", "longitude", "level", "time", "lead_time"],
        coords=dict(
            latitude=(["latitude", "longitude"], np.zeros((1, 1))),
            longitude=(["latitude", "longitude"], np.zeros((1, 1))),
            level=(["level"], np.zeros((1,))),
            time=np.zeros((1,)),
            lead_time=np.zeros((1,)),
        ),
    )
