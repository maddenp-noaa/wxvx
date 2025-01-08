import logging
import os
from pathlib import Path
from typing import Optional

import requests


def fetch(url: str, path: Path, headers: Optional[dict[str, str]] = None) -> None:
    logging.info("Fetching %s", url)
    response = requests.get(url, allow_redirects=True, timeout=3, headers=headers or {})
    expected = 206 if headers and "Range" in headers.keys() else 200
    if response.status_code == expected:
        os.makedirs(path.parent, exist_ok=True)
        with open(path, "wb") as f:
            f.write(response.content)
            logging.info("Wrote %s", path)


# from urllib.parse import urlparse
# import xarray as xr

# config = {
#     "d": 20241201,
#     "h": 0,
#     "leadtimes": [3, 6],
#     "rundir": "/tmp/demo",
#     "url": "https://noaa-hrrr-bdp-pds.s3.amazonaws.com/hrrr."
# "{d}/conus/hrrr.t{h:02}z.wrfprsf{f:02}.grib2",
#     "varlevel": "2 m above ground",
#     "varname": "TMP",
# }

# @task
# def report():
#     info = {key: config[key] for key in ("d", "h", "leadtimes")}
#     yield "GRIB files {d} {h} {leadtimes}".format(**info)
#     yield asset(None, lambda: False)  # i.e. this task ALWAYS executes
#     specs_tasks = {f: _gribspecs(config["url"].format(**info, f=f)) for f in info["leadtimes"]}
#     yield specs_tasks
#     for leadtime, spec_task in specs_tasks.items():
#         spec = refs(spec_task)
#         print(
#             "Field '%s' at level '%s' in %s %s %s has dimensions (%s, %s)"
#             % (
#                 config["varname"],
#                 config["varlevel"],
#                 info["d"],
#                 info["h"],
#                 leadtime,
#                 spec[1],
#                 spec[2],
#             )
#         )

# @task
# def _gribspecs(url: str):
#     taskname = "GRIB data for %s" % Path(urlparse(url).path).name
#     yield taskname
#     gribfile = _gribfile(url)
#     path = refs(gribfile)
#     ds = xr.open_dataset(path, engine="cfgrib")
#     yield asset((path, ds.sizes["x"], ds.sizes["y"]), path.is_file)
#     yield gribfile
#     pass

# @task
# def _gribfile(url: str):
#     path = Path(config["rundir"], Path(urlparse(url).path).name)  # type: ignore
#     taskname = "GRIB file %s" % path
#     yield taskname
#     yield asset(path, path.is_file)
#     yield (indexfile_task := _indexfile(url))
#     headers = range_header(Path(refs(indexfile_task)))
#     fetch(taskname, url, path, headers)

# @task
# def _indexfile(url: str):
#     url += ".idx"
#     path = Path(config["rundir"], Path(urlparse(url).path).name)  # type: ignore
#     taskname = "Index file %s" % path
#     yield taskname
#     yield asset(path, path.is_file)
#     yield None
#     fetch(taskname, url, path)

# def range_header(indexfile: Path) -> dict[str, str]:
#     with open(indexfile, "r", encoding="utf-8") as f:
#         lines = filter(None, f.read().split("\n"))
#     records = [x.split(":") for x in lines]
#     record = [x for x in records if x[3] == config["varname"] and x[4] == config["varlevel"]][0]
#     start = record[1]
#     end = None if int(record[0]) == len(records) else records[int(record[0])][1]
#     return {"Range": "bytes=%s" % (f"{start}-{end}" if end else start)}
