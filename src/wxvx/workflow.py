from __future__ import annotations

import logging
from functools import cache
from itertools import pairwise, product
from pathlib import Path
from stat import S_IEXEC
from textwrap import dedent
from typing import TYPE_CHECKING
from urllib.parse import urlparse
from warnings import catch_warnings, simplefilter

import xarray as xr
import yaml
from iotaa import Node, asset, external, task, tasks

from wxvx.metconf import render
from wxvx.net import fetch, status
from wxvx.times import TimeCoords, tcinfo, validtimes
from wxvx.types import Source
from wxvx.util import mpexec
from wxvx.variables import HRRR, VARMETA, Var, da_construct, da_select, ds_construct, metlevel

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence

    from wxvx.types import Config, VarMeta

# Public tasks


@tasks
def grids(c: Config):
    taskname = "Grids for %s" % c.forecast.path
    yield taskname
    reqs: list[Node] = []
    for var, varname in _vxvars(c).items():
        for tc in validtimes(c.cycles, c.leadtimes):
            forecast_grid = _grid_nc(c, varname, tc, var)
            reqs.append(forecast_grid)
            baseline_grid = _grid_grib(c, TimeCoords(cycle=tc.validtime, leadtime=0), var)
            reqs.append(baseline_grid)
            if c.baseline.compare:
                comp_grid = _grid_grib(c, tc, var)
                reqs.append(comp_grid)
    yield reqs


@tasks
def plots(c: Config):
    taskname = "Plots for %s" % c.forecast.path
    yield taskname
    yield [_plot(c, varname, level) for varname, level in _varnames_and_levels(c)]


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
    yield _grib_index_remote(url)
    fetch(taskname, url, path)


@external
def _grib_index_remote(url: str):
    taskname = "GRIB index remote %s" % url
    yield taskname
    yield asset(url, lambda: status(url) == 200)


@task
def _grid_grib(c: Config, tc: TimeCoords, var: Var):
    yyyymmdd, hh, leadtime = tcinfo(tc)
    outdir = c.paths.grids / yyyymmdd / hh / leadtime
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
    fetch(taskname, url, path, headers)


@task
def _grid_nc(c: Config, varname: str, tc: TimeCoords, var: Var):
    yyyymmdd, hh, leadtime = tcinfo(tc)
    path = c.paths.grids / yyyymmdd / hh / leadtime / f"{var}.nc"
    taskname = "Forecast grid %s" % path
    yield taskname
    yield asset(path, path.is_file)
    fd = _forecast_dataset(c.forecast.path)
    yield fd
    src = da_select(fd.refs, c, varname, tc, var)
    da = da_construct(src)
    ds = ds_construct(c, da, taskname)
    path.parent.mkdir(parents=True, exist_ok=True)
    ds.to_netcdf(path, encoding={varname: {"zlib": True, "complevel": 9}})
    logging.info("%s: Wrote %s", taskname, path)


@task
def _grid_stat_config(
    c: Config, basepath: Path, varname: str, rundir: Path, var: Var, prefix: str, source: Source
):
    path = (basepath.parent / basepath.stem).with_suffix(".config")
    taskname = "Verification config %s" % path
    yield taskname
    yield asset(path, path.is_file)
    yield None
    level_obs = metlevel(var.level_type, var.level)
    attrs = {
        Source.BASELINE: (level_obs, HRRR.varname(var.name), c.baseline.name),
        Source.FORECAST: ("(0,0,*,*)", varname, c.forecast.name),
    }
    forecast_level, forecast_name, model = attrs[source]
    field_fcst = {"level": [forecast_level], "name": forecast_name, "set_attr_level": level_obs}
    field_obs = {"level": [level_obs], "name": HRRR.varname(var.name)}
    meta = _meta(c, varname)
    if meta.met_linetype == "cts":
        thresholds = ">=20, >=30, >=40"
        field_fcst["cat_thresh"] = [thresholds]
        field_obs["cat_thresh"] = [thresholds]
    config = render(
        {
            "fcst": {"field": [field_fcst]},
            "mask": {"grid": ["FULL"], "poly": []},
            "model": model,
            "nc_pairs_flag": "FALSE",
            "obs": {"field": [field_obs]},
            "obtype": c.baseline.name,
            "output_flag": {meta.met_linetype: "BOTH"},
            "output_prefix": f"{prefix}",
            "regrid": {"to_grid": "FCST"},
            "tmp_dir": rundir,
        }
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"{config}\n")


@task
def _plot(c: Config, varname: str, level: float | None):
    var = _var(c, varname, level)
    rundir = c.paths.run / "plot" / str(var)
    path = rundir / "plot.png"
    taskname = "Plot %s" % path
    yield taskname
    yield asset(path, path.is_file)
    reformatted = _reformat(c, varname, level, rundir)
    stat_fn = reformatted.refs.name
    cfgfile = _plot_config(c, rundir, varname, var, plot_fn=path.name, stat_fn=stat_fn)
    content = "line.py %s >%s 2>&1" % (cfgfile.refs.name, "plot.log")
    script = _runscript(basepath=path, content=content)
    yield [cfgfile, reformatted, script]
    mpexec(str(script.refs), rundir, taskname)


@task
def _plot_config(c: Config, rundir: Path, varname: str, var: Var, plot_fn: str, stat_fn: str):
    path = rundir / "plot.yaml"
    taskname = "Plot config %s" % path
    yield taskname
    yield asset(path, path.is_file)
    yield None
    meta = _meta(c, varname)
    stat = meta.met_stat
    vts = validtimes(c.cycles, c.leadtimes)
    x_axis_labels = [
        vt.validtime.strftime("%Y%m%d %HZ") if i % 10 == 0 else "" for i, vt in enumerate(vts)
    ]
    title = "%s %s vs %s" % (
        meta.description.format(level=var.level),
        stat,
        c.baseline.name,
    )
    config = dict(
        colors=["#CC6677"],
        con_series=[1],
        fcst_var_val_1={varname: [stat]},
        grid_col="#cccccc",
        indy_label=x_axis_labels,
        indy_vals=[vt.validtime.strftime("%Y-%m-%d %H:%M:%S") for vt in vts],
        indy_var="fcst_init_beg",
        legend_box="n",
        list_stat_1=[stat],
        log_level="DEBUG",
        met_linetype=meta.met_linetype,
        plot_caption="",
        plot_ci=["none"],
        plot_disp=[True],
        plot_filename=plot_fn,
        plot_height=10,
        plot_width=13,
        series_line_style=["-"],
        series_line_width=[1],
        series_order=[1],
        series_symbols=["."],
        series_type=["b"],
        series_val_1={"model": [c.forecast.name]},
        show_legend=[True],
        stat_input=stat_fn,
        title=title,
        xaxis="Cycle",
        xlab_offset=20,
        xtlab_orient=270,
        yaxis_1=stat,
        ylab_offset=10,
    )
    if c.baseline.compare:
        update = dict(
            fcst_var_val_2={HRRR.varname(var.name): [stat]},
            list_stat_2=[stat],
            series_val_2={"model": [c.baseline.name]},
        )
        config.update(update)
        for k, v in [
            ("colors", "#44AA99"),
            ("con_series", 1),
            ("plot_ci", "none"),
            ("plot_disp", True),
            ("series_line_style", "-"),
            ("series_line_width", 1),
            ("series_order", 2),
            ("series_symbols", "."),
            ("series_type", "b"),
            ("show_legend", True),
        ]:
            config[k].append(v)  # type: ignore[attr-defined]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        yaml.dump(config, f)


@task
def _reformat(c: Config, varname: str, level: float | None, rundir: Path):
    path = rundir / "reformat.data"
    taskname = "Reformatted stats %s" % path
    yield taskname
    yield asset(path, path.is_file)
    cfgfile = _reformat_config(c, varname, rundir)
    content = f"""
    export PYTHONWARNINGS=ignore::FutureWarning
    write_stat_ascii.py {cfgfile.refs.name} >reformat.log 2>&1
    """
    script = _runscript(basepath=path, content=content)
    yield [cfgfile, script, _stat_links(c, varname, level, rundir)]
    mpexec(str(script.refs), rundir, taskname)


@task
def _reformat_config(c: Config, varname: str, rundir: Path):
    path = rundir / "reformat.yaml"
    taskname = "Reformat config %s" % path
    yield taskname
    yield asset(path, path.is_file)
    yield None
    meta = _meta(c, varname)
    config = dict(
        input_data_dir=".",
        input_stats_aggregated=True,
        line_type=meta.met_linetype.upper(),
        log_directory=".",
        log_filename="/dev/stdout",
        log_level="debug",
        output_dir=".",
        output_filename="reformat.data",
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        yaml.dump(config, f)


@task
def _runscript(basepath: Path, content: str):
    path = (basepath.parent / basepath.stem).with_suffix(".sh")
    yield "Runscript %s" % path
    yield asset(path, path.is_file)
    yield None
    content = dedent(content).strip()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        print(f"#!/usr/bin/env bash\n\n{content}", file=f)
    path.chmod(path.stat().st_mode | S_IEXEC)


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
    cfgfile = _grid_stat_config(c, path, varname, rundir, var, prefix, source)
    log = f"{path.stem}.log"
    content = f"""
    export OMP_NUM_THREADS=1
    grid_stat -v 4 {toverify.refs} {baseline.refs} {cfgfile.refs.name} >{log} 2>&1
    """
    script = _runscript(basepath=path, content=content)
    reqs = [toverify, baseline, cfgfile, script]
    if source == Source.BASELINE:
        reqs.append(forecast)
    yield reqs
    mpexec(str(script.refs), rundir, taskname)


@task
def _stat_links(c: Config, varname: str, level: float | None, rundir: Path):
    taskname = "MET stats for %s " % _var(c, varname, level)
    yield taskname
    reqs = _statreqs(c, varname, level)
    files = [x.refs for x in reqs]
    links = [rundir / x.name for x in files]
    yield [asset(link, link.is_symlink) for link in links]
    yield reqs
    for target, link in zip(files, links):
        link.parent.mkdir(parents=True, exist_ok=True)
        logging.info("%s: Linking %s -> %s", taskname, link, target)
        if not link.exists():
            link.symlink_to(target)


# Support


def _meta(c: Config, varname: str) -> VarMeta:
    return VARMETA[c.variables[varname]["name"]]


def _statargs(c: Config, varname: str, level: float | None, source: Source) -> Iterator:
    name = (c.baseline if source == Source.BASELINE else c.forecast).name.lower()
    prefix = lambda var: "%s_%s" % (name, str(var).replace("-", "_"))
    args = [
        (c, vn, tc, var, prefix(var), source)
        for (var, vn), tc in product(_vxvars(c).items(), validtimes(c.cycles, c.leadtimes))
        if vn == varname and var.level == level
    ]
    return iter(sorted(args))


def _statreqs(c: Config, varname: str, level: float | None) -> Sequence[Node]:
    genreqs = lambda source: [_stat(*args) for args in _statargs(c, varname, level, source)]
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
