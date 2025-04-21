from __future__ import annotations

import logging
from datetime import datetime
from functools import cache
from itertools import pairwise, product
from pathlib import Path
from stat import S_IEXEC
from textwrap import dedent
from typing import TYPE_CHECKING
from urllib.parse import urlparse
from warnings import catch_warnings, simplefilter

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
import xarray as xr
from iotaa import Node, asset, external, refs, task, tasks

from wxvx.metconf import render
from wxvx.net import fetch
from wxvx.times import TimeCoords, _cycles, _leadtimes, tcinfo, validtimes
from wxvx.types import Cycles, Source
from wxvx.util import LINETYPE, atomic, mpexec
from wxvx.variables import HRRR, VARMETA, Var, da_construct, da_select, ds_construct, metlevel

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence

    from wxvx.types import Config, VarMeta

# Public tasks


@tasks
def grids(c: Config, baseline: bool = True, forecast: bool = True):
    taskname = "Grids for %s" % c.forecast.path
    yield taskname
    reqs: list[Node] = []
    for var, varname in _vxvars(c).items():
        for tc in validtimes(c.cycles, c.leadtimes):
            if forecast:
                forecast_grid = _grid_nc(c, varname, tc, var)
                reqs.append(forecast_grid)
            if baseline:
                baseline_grid = _grid_grib(c, TimeCoords(cycle=tc.validtime, leadtime=0), var)
                reqs.append(baseline_grid)
                if c.baseline.compare:
                    comp_grid = _grid_grib(c, tc, var)
                    reqs.append(comp_grid)
    yield reqs


@tasks
def grids_baseline(c: Config):
    taskname = "Baseline grids for %s" % c.forecast.path
    yield taskname
    yield grids(c, baseline=True, forecast=False)


@tasks
def grids_forecast(c: Config):
    taskname = "Forecast grids for %s" % c.forecast.path
    yield taskname
    yield grids(c, baseline=False, forecast=True)


@tasks
def plots(c: Config):
    taskname = "Plots for %s" % c.forecast.path
    yield taskname
    cycles = _cycles(start=c.cycles.start, step=c.cycles.step, stop=c.cycles.stop)
    yield [
        _plot(c, cycle, varname, level)
        for cycle in cycles
        for varname, level in _varnames_and_levels(c)
    ]


@tasks
def stats(c: Config):
    taskname = "Stats for %s" % c.forecast.path
    yield taskname
    reqs: list[Node] = []
    for varname, level in _varnames_and_levels(c):
        reqs.extend(_statreqs(c, varname, level))
    yield reqs


# Private tasks


@external
def _existing(path: Path):
    taskname = "Existing path %s" % path
    yield taskname
    yield asset(path, path.exists)


@task
def _forecast_dataset(path: Path):
    taskname = "Forecast dataset %s" % path
    yield taskname
    ds = xr.Dataset()
    yield asset(ds, lambda: bool(ds))
    yield _existing(path)
    logging.info("%s: Opening forecast %s", taskname, path)
    with catch_warnings():
        simplefilter("ignore")
        ds.update(xr.open_dataset(path, decode_timedelta=True))


@task
def _grib_index_data(c: Config, outdir: Path, tc: TimeCoords, url: str):
    yyyymmdd, hh, leadtime = tcinfo(tc)
    taskname = "GRIB index data %s %sZ %s" % (yyyymmdd, hh, leadtime)
    yield taskname
    idxdata: dict[str, HRRR] = {}
    yield asset(idxdata, lambda: bool(idxdata))
    idxfile = _grib_index_file(outdir, url)
    yield idxfile
    lines = idxfile.refs.read_text(encoding="utf-8").strip().split("\n")
    lines.append(":-1:::::")  # end marker
    vxvars = set(_vxvars(c).keys())
    for this_record, next_record in pairwise([line.split(":") for line in lines]):
        hrrrvar = HRRR(
            name=this_record[3],
            levstr=this_record[4],
            firstbyte=int(this_record[1]),
            lastbyte=int(next_record[1]) - 1,
        )
        if hrrrvar in vxvars:
            idxdata[str(hrrrvar)] = hrrrvar


@task
def _grib_index_file(outdir: Path, url: str):
    path = outdir / Path(urlparse(url).path).name
    taskname = "GRIB index file %s" % path
    yield taskname
    yield asset(path, path.is_file)
    yield None
    with atomic(path) as tmp:
        fetch(taskname, url, tmp)


@task
def _grid_grib(c: Config, tc: TimeCoords, var: Var):
    yyyymmdd, hh, leadtime = tcinfo(tc)
    outdir = c.paths.grids_baseline / yyyymmdd / hh / leadtime
    path = outdir / f"{var}.grib2"
    taskname = "Baseline grid %s" % path
    yield taskname
    yield asset(path, path.is_file)
    url = c.baseline.template.format(yyyymmdd=yyyymmdd, hh=hh, ff="%02d" % int(leadtime))
    idxdata = _grib_index_data(c, outdir, tc, url=f"{url}.idx")
    yield idxdata
    var_idxdata = idxdata.refs[str(var)]
    fb, lb = var_idxdata.firstbyte, var_idxdata.lastbyte
    headers = {"Range": "bytes=%s" % (f"{fb}-{lb}" if lb else fb)}
    with atomic(path) as tmp:
        fetch(taskname, url, tmp, headers)


@task
def _grid_nc(c: Config, varname: str, tc: TimeCoords, var: Var):
    yyyymmdd, hh, leadtime = tcinfo(tc)
    path = c.paths.grids_forecast / yyyymmdd / hh / leadtime / f"{var}.nc"
    taskname = "Forecast grid %s" % path
    yield taskname
    yield asset(path, path.is_file)
    fd = _forecast_dataset(c.forecast.path)
    yield fd
    src = da_select(fd.refs, c, varname, tc, var)
    da = da_construct(src)
    ds = ds_construct(c, da, taskname, var.level)
    with atomic(path) as tmp:
        ds.to_netcdf(tmp, encoding={varname: {"zlib": True, "complevel": 9}})
    logging.info("%s: Wrote %s", taskname, path)


@task
def _polyfile(path: Path, mask: tuple[tuple[float, float]]):
    yield "Poly file %s" % path
    yield asset(path, path.is_file)
    yield None
    content = "MASK\n%s\n" % "\n".join(f"{lat} {lon}" for lat, lon in mask)
    with atomic(path) as tmp:
        tmp.write_text(content)


@task
def _plot(c: Config, cycle: datetime, varname: str, level: float | None):
    taskname = "Plot %s %s %s" % (varname, level, cycle)
    yield taskname
    var = _var(c, varname, level)
    rundir = c.paths.run / "plot" / str(var) / cycle.strftime("%Y%m%d") / cycle.strftime("%H")
    plot_fn = rundir / "plot.png"
    yield asset(plot_fn, plot_fn.is_file)
    reqs = _statreqs(c, varname, level, cycle)
    yield reqs
    meta = _meta(c, varname)
    stat = "RMSE" if "RMSE" in meta.met_stats else "PODY"
    files = [str(refs(x)).replace(".stat", f"_{LINETYPE[stat]}.txt") for x in reqs]
    leadtimes = [
        "%03d" % (td.total_seconds() // 3600)
        for td in _leadtimes(start=c.leadtimes.start, step=c.leadtimes.step, stop=c.leadtimes.stop)
    ]
    plot_rows = [
        pd.read_csv(file, sep=r"\s+")[["MODEL", "FCST_LEAD", "FCST_THRESH", stat]] for file in files
    ]
    plot_data = pd.concat(plot_rows)
    plot_data["FCST_LEAD"] = plot_data["FCST_LEAD"] // 10000
    plt.figure(figsize=(10, 6))
    sns.set(style="darkgrid")
    if stat == "PODY":
        plot_data["LABEL"] = plot_data.apply(
            lambda row: f"{row['MODEL']} {row['FCST_THRESH']}", axis=1
        )
    sns.lineplot(
        data=plot_data,
        x="FCST_LEAD",
        y=stat,
        hue="MODEL" if stat == "RMSE" else "LABEL",
        marker="o",
    )
    plt.title(
        "%s %s %s vs %s at %s"
        % (
            meta.description.format(level=var.level),
            stat,
            c.forecast.name,
            c.baseline.name,
            cycle.strftime("%Y%m%d %HZ"),
        )
    )
    plt.xlabel("Leadtime")
    plt.ylabel(f"{stat} ({meta.units})")
    plt.xticks(ticks=[int(lt) for lt in leadtimes], labels=leadtimes, rotation=90)
    plt.legend(title="Model")
    plt.tight_layout()
    plot_fn.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(plot_fn)
    plt.close()


@task
def _stat(c: Config, varname: str, tc: TimeCoords, var: Var, prefix: str, source: Source):
    yyyymmdd, hh, leadtime = tcinfo(tc)
    source_name = {Source.BASELINE: "baseline", Source.FORECAST: "forecast"}[source]
    taskname = "MET stats for %s %s at %s %sZ %s" % (source_name, var, yyyymmdd, hh, leadtime)
    yield taskname
    rundir = c.paths.run / "stats" / yyyymmdd / hh / leadtime
    yyyymmdd_valid, hh_valid, _ = tcinfo(TimeCoords(tc.validtime))
    template = "grid_stat_%s_%02d0000L_%s_%s0000V.stat"
    path = rundir / (template % (prefix, int(leadtime), yyyymmdd_valid, hh_valid))
    yield asset(path, path.is_file)
    baseline = _grid_grib(c, TimeCoords(cycle=tc.validtime, leadtime=0), var)
    forecast = _grid_nc(c, varname, tc, var)
    toverify = _grid_grib(c, tc, var) if source == Source.BASELINE else forecast
    log = f"{path.stem}.log"
    reqs = [toverify, baseline]
    if source == Source.BASELINE:
        reqs.append(forecast)
    polyfile = None
    if mask := c.forecast.mask:
        polyfile = _polyfile(c.paths.run / "stats" / "mask.poly", mask)
        reqs.append(polyfile)
    yield reqs
    cfgfile = path.with_suffix(".config")
    _grid_stat_config(c, cfgfile, varname, rundir, var, prefix, source, polyfile)
    runscript = path.with_suffix(".sh")
    content = f"""
    export OMP_NUM_THREADS=1
    grid_stat -v 4 {toverify.refs} {baseline.refs} {cfgfile} >{log} 2>&1
    """
    with atomic(runscript) as tmp:
        tmp.write_text("#!/usr/bin/env bash\n\n%s\n" % dedent(content).strip())
    runscript.chmod(runscript.stat().st_mode | S_IEXEC)
    mpexec(str(runscript), rundir, taskname)


# Support


def _grid_stat_config(
    c: Config,
    path: Path,
    varname: str,
    rundir: Path,
    var: Var,
    prefix: str,
    source: Source,
    polyfile: Node | None,
):
    level_obs = metlevel(var.level_type, var.level)
    attrs = {
        Source.BASELINE: (level_obs, HRRR.varname(var.name), c.baseline.name),
        Source.FORECAST: ("(0,0,*,*)", varname, c.forecast.name),
    }
    level_fcst, name_fcst, model = attrs[source]
    field_fcst = {"level": [level_fcst], "name": name_fcst, "set_attr_level": level_obs}
    field_obs = {"level": [level_obs], "name": HRRR.varname(var.name)}
    meta = _meta(c, varname)
    if meta.cat_thresh:
        for x in field_fcst, field_obs:
            x["cat_thresh"] = meta.cat_thresh
    if meta.cnt_thresh:
        for x in field_fcst, field_obs:
            x["cnt_thresh"] = meta.cnt_thresh
    mask_grid = [] if polyfile else ["FULL"]
    mask_poly = [polyfile.refs] if polyfile else []
    config = {
        "fcst": {"field": [field_fcst]},
        "mask": {"grid": mask_grid, "poly": mask_poly},
        "model": model,
        "nc_pairs_flag": "FALSE",
        "obs": {"field": [field_obs]},
        "obtype": c.baseline.name,
        "output_flag": {x: "BOTH" for x in sorted({LINETYPE[x] for x in meta.met_stats})},
        "output_prefix": f"{prefix}",
        "regrid": {"to_grid": "FCST"},
        "tmp_dir": rundir,
    }
    if nbrhd := {k: v for k, v in [("shape", meta.nbrhd_shape), ("width", meta.nbrhd_width)] if v}:
        config["nbrhd"] = nbrhd
    with atomic(path) as tmp:
        tmp.write_text("%s\n" % render(config))


def _meta(c: Config, varname: str) -> VarMeta:
    return VARMETA[c.variables[varname]["name"]]


def _statargs(
    c: Config, varname: str, level: float | None, source: Source, cycle: datetime | None = None
) -> Iterator:
    if isinstance(cycle, datetime):
        ctc = Cycles(
            start=cycle.strftime("%Y-%m-%dT%H:%M:%S"),
            step="01:00:00",
            stop=cycle.strftime("%Y-%m-%dT%H:%M:%S"),
        )
    else:
        ctc = c.cycles
    name = (c.baseline if source == Source.BASELINE else c.forecast).name.lower()
    prefix = lambda var: "%s_%s" % (name, str(var).replace("-", "_"))
    args = [
        (c, vn, tc, var, prefix(var), source)
        for (var, vn), tc in product(_vxvars(c).items(), validtimes(ctc, c.leadtimes))
        if vn == varname and var.level == level
    ]
    return iter(sorted(args))


def _statreqs(
    c: Config, varname: str, level: float | None, cycle: datetime | None = None
) -> Sequence[Node]:
    genreqs = lambda source: [_stat(*args) for args in _statargs(c, varname, level, source, cycle)]
    reqs: Sequence[Node] = genreqs(Source.FORECAST)
    if c.baseline.compare:
        reqs = [*reqs, *genreqs(Source.BASELINE)]
    return reqs


def _var(c: Config, varname: str, level: float | None) -> Var:
    m = _meta(c, varname)
    return Var(m.name, m.level_type, level)


def _varnames_and_levels(c: Config) -> Iterator[tuple[str, float | None]]:
    return iter(
        (varname, level)
        for varname, attrs in c.variables.items()
        for level in attrs.get("levels", [None])
    )


@cache
def _vxvars(c: Config) -> dict[Var, str]:
    return {
        Var(attrs["name"], attrs["level_type"], level): varname
        for varname, attrs in c.variables.items()
        for level in attrs.get("levels", [None])
    }
