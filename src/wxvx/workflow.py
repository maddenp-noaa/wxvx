from __future__ import annotations

import logging
from itertools import pairwise, product
from pathlib import Path
from stat import S_IEXEC
from textwrap import dedent
from typing import TYPE_CHECKING
from urllib.parse import urlparse
from warnings import catch_warnings, simplefilter

import xarray as xr
import yaml
from iotaa import asset, external, refs, task, tasks
from uwtools.api.template import render

from wxvx.net import fetch, status
from wxvx.times import TimeCoords, tcinfo, validtimes
from wxvx.util import mpexec, resource_path
from wxvx.variables import VARMETA, HRRRVar, Var, da_construct, da_select, ds_from_da, metlevel

if TYPE_CHECKING:
    from collections.abc import Iterator  # pragma: no cover
    from types import SimpleNamespace as ns  # pragma: no cover

    from wxvx.types import Config  # pragma: no cover


@external
def existing(path: Path):
    yield path
    yield asset(path, path.exists)


@task
def forecast_dataset(path: Path):
    taskname = "Forecast dataset from %s" % path
    ds = xr.Dataset()
    yield taskname
    yield asset(ds, lambda: bool(ds))
    yield existing(path)
    logging.info("%s: Opening forecast %s", taskname, path)
    with catch_warnings():
        simplefilter("ignore")
        ds.update(xr.open_dataset(path, decode_timedelta=True))


@task
def grib_index_data(c: Config, outdir: Path, tc: TimeCoords, url: str):
    yyyymmdd, hh, leadtime = tcinfo(tc)
    taskname = "GRIB index data %s %sZ %s" % (yyyymmdd, hh, leadtime)
    idxdata: dict[str, HRRRVar] = {}
    idxfile = grib_index_file(outdir, url)
    yield taskname
    yield asset(idxdata, lambda: bool(idxdata))
    yield idxfile
    lines = refs(idxfile).read_text(encoding="utf-8").strip().split("\n")
    lines.append(":-1:::::")  # end marker
    for this_record, next_record in pairwise([line.split(":") for line in lines]):
        hrrrvar = HRRRVar(
            name=this_record[3],
            levstr=this_record[4],
            firstbyte=int(this_record[1]),
            lastbyte=int(next_record[1]) - 1,
        )
        if hrrrvar in _vxvars(c).values():
            idxdata[str(hrrrvar)] = hrrrvar


@task
def grib_index_file(outdir: Path, url: str):
    path = outdir / Path(urlparse(url).path).name
    taskname = "GRIB index file %s" % path
    yield taskname
    yield asset(path, path.is_file)
    yield grib_index_remote(url)
    fetch(taskname, url, path)


@external
def grib_index_remote(url: str):
    yield url
    yield asset(url, lambda: status(url) == 200)


@task
def grid_grib(c: Config, tc: TimeCoords, var: Var):
    yyyymmdd, hh, leadtime = tcinfo(tc)
    outdir = c.workdir / "grids" / yyyymmdd / hh / leadtime
    path = outdir / f"{var}.grib2"
    taskname = "Baseline grid %s" % path
    url = c.baseline.template.format(yyyymmdd=yyyymmdd, hh=hh, ff="%02d" % int(leadtime))
    idxdata = grib_index_data(c, outdir, tc, url=f"{url}.idx")
    yield taskname
    yield asset(path, path.is_file)
    yield idxdata
    var_idxdata = refs(idxdata)[str(var)]
    fb, lb = var_idxdata.firstbyte, var_idxdata.lastbyte
    headers = {"Range": "bytes=%s" % (f"{fb}-{lb}" if lb else fb)}
    fetch(taskname, url, path, headers)


@task
def grid_nc(c: Config, varname: str, tc: TimeCoords, var: Var):
    yyyymmdd, hh, leadtime = tcinfo(tc)
    path = c.workdir / "grids" / yyyymmdd / hh / leadtime / f"{var}.nc"
    taskname = "Forecast grid %s" % path
    fd = forecast_dataset(c.forecast.path)
    yield taskname
    yield asset(path, path.is_file)
    yield fd
    src = da_select(refs(fd), c, varname, tc, var)
    da = da_construct(src)
    ds = ds_from_da(c, da, taskname)
    path.parent.mkdir(parents=True, exist_ok=True)
    ds.to_netcdf(path)
    logging.info("%s: Wrote %s", taskname, path)


@task
def grid_stat_config(c: Config, basepath: Path, varname: str, rundir: Path, var: Var, prefix: str):
    path = (basepath.parent / basepath.stem).with_suffix(".config")
    taskname = "Verification config %s" % path
    yield taskname
    yield asset(path, path.is_file)
    yield None
    values = {
        "baseline_level": metlevel(level_type=var.level_type, level=var.level),
        "baseline_name": HRRRVar.varname(name=var.name, level_type=var.level_type),
        "forecast_level": "(0,0,*,*)",
        "forecast_name": varname,
        # "forecast_level": metlevel(level_type=var.level_type, level=var.level),  # TOGGLE
        # "forecast_name": HRRRVar.varname(name=var.name, level_type=var.level_type),  # TOGGLE
        "model": c.forecast.name,
        "obtype": c.baseline.name,
        "prefix": f"{prefix}",
        "tmpdir": rundir,
    }
    render(values_src=values, input_file=resource_path("config.grid_stat"), output_file=path)


@task
def plot(c: Config, varname: str, level: float | None):
    rundir = c.workdir / "run" / "plot"
    var = _var(c, varname, level)
    path = rundir / f"{var}-plot.png"
    taskname = "Plot of stat data %s" % path
    reformatted = reformat(c, varname, level, rundir)
    stat_fn = refs(reformatted).name
    cfgfile = plot_config(c, rundir, varname, var, plot_fn=path.name, stat_fn=stat_fn)
    content = "line.py %s >%s 2>&1" % (refs(cfgfile).name, f"{var}-plot.log")
    script = runscript(basepath=path, content=content)
    yield taskname
    yield asset(path, path.is_file)
    yield [cfgfile, reformatted, script]
    mpexec(str(refs(script)), rundir, taskname)


@task
def plot_config(c: Config, rundir: Path, varname: str, var: Var, plot_fn: str, stat_fn: str):
    path = rundir / f"{var}-plot.yaml"
    taskname = "Plot config %s" % path
    yield taskname
    yield asset(path, path.is_file)
    yield None
    stat = "RMSE"
    vts = validtimes(c.cycles, c.leadtimes)
    x_axis_labels = [
        vt.validtime.strftime("%Y%m%d %HZ") if i % 10 == 0 else "" for i, vt in enumerate(vts)
    ]
    config = dict(
        colors=["#00ff00"],
        con_series=[1],
        fcst_var_val_1={varname: [stat]},
        grid_col="#cccccc",
        indy_label=x_axis_labels,
        indy_vals=[vt.validtime.strftime("%Y-%m-%d %H:%M:%S") for vt in vts],
        indy_var="fcst_init_beg",
        legend_box="n",
        line_type="cnt",
        list_stat_1=[stat],
        log_level="DEBUG",
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
        title="%s (%s) 1-hour forecast %s" % (varname, _meta(c, varname).units, stat),
        user_legend=["%s vs %s" % (c.forecast.name, c.baseline.name)],
        xaxis="Cycle",
        xlab_offset=20,
        xtlab_orient=270,
        yaxis_1=stat,
        ylab_offset=20,
    )
    if c.plot.baseline:
        update = dict(
            fcst_var_val_2={HRRRVar.varname(var.name, var.level_type): [stat]},
            list_stat_2=[stat],
            series_val_2={"model": [c.baseline.name]},
        )
        config.update(update)
        for k, v in [
            ("colors", "#0000ff"),
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
def reformat(c: Config, varname: str, level: int, rundir: Path):
    var = _var(c, varname, level)
    path = rundir / f"{var}-reformat.data"
    taskname = "Reformatted grid_stat results %s" % path
    cfgfile = reformat_config(rundir, var)
    content = f"""
    export PYTHONWARNINGS=ignore::FutureWarning
    write_stat_ascii.py {refs(cfgfile).name} >{var}-reformat.log 2>&1
    """
    script = runscript(basepath=path, content=content)
    yield taskname
    yield asset(path, path.is_file)
    yield [cfgfile, script, stats(c)]
    mpexec(str(refs(script)), rundir, taskname)


@task
def reformat_config(rundir: Path, var: Var):
    path = rundir / f"{var}-reformat.yaml"
    taskname = "Reformat config %s" % path
    yield taskname
    yield asset(path, path.is_file)
    yield None
    config = dict(
        input_data_dir=".",
        input_stats_aggregated=True,
        line_type="CNT",
        log_directory=".",
        log_filename="/dev/stdout",
        log_level="debug",
        output_dir=".",
        output_filename=f"{var}-reformat.data",
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        yaml.dump(config, f)


@task
def runscript(basepath: Path, content: str):
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
def stat(c: Config, varname: str, tc: TimeCoords, var: Var, prefix: str):
    yyyymmdd, hh, leadtime = tcinfo(tc)
    taskname = "MET grid_stat result %s at %s %sZ %s" % (var, yyyymmdd, hh, leadtime)
    rundir = c.workdir / "run" / "stat" / yyyymmdd / hh / leadtime
    yyyymmdd_valid, hh_valid, _ = tcinfo(TimeCoords(tc.validtime))
    fn = "grid_stat_%s_%02d0000L_%s_%s0000V.stat" % (
        prefix,
        int(leadtime),
        yyyymmdd_valid,
        hh_valid,
    )
    path = rundir / fn
    forecast = grid_nc(c, varname, tc, var)
    # forecast = grid_grib(c, tc, var)  # TOGGLE
    baseline = grid_grib(c, TimeCoords(cycle=tc.validtime, leadtime=0), var)
    cfgfile = grid_stat_config(c, path, varname, rundir, var, prefix)
    log = f"{path.stem}.log"
    content = f"""
    export OMP_NUM_THREADS=1
    grid_stat -v 4 {refs(forecast)} {refs(baseline)} {refs(cfgfile).name} >{log} 2>&1
    """
    script = runscript(basepath=path, content=content)
    yield taskname
    yield asset(path, path.is_file)
    yield [forecast, baseline, cfgfile, script]
    mpexec(str(refs(script)), rundir, taskname)


@task
def stats(c: Config):
    taskname = "MET grid_stat results for %s" % c.forecast.path
    reqs = [stat(*args) for args in _statargs(c)]
    files = [refs(x) for x in reqs]
    links = [c.workdir / "run" / "plot" / x.name for x in files]
    yield taskname
    yield [asset(path, path.is_symlink) for path in links]
    yield reqs
    for target, link in zip(files, links):
        link.parent.mkdir(parents=True, exist_ok=True)
        logging.info("%s: Linking %s -> %s", taskname, link, target)
        if not link.exists():
            link.symlink_to(target)


@tasks
def verification(c: Config):
    taskname = "Verification of %s" % c.forecast.path
    reqs = [
        plot(c, varname, level)
        for varname, attrs in c.variables.items()
        for level in attrs.get("levels", [None])
    ]
    yield taskname
    yield reqs


# Support


def _meta(c: Config, varname: str) -> ns:
    return VARMETA[tuple(c.variables[varname][x] for x in ["standard_name", "level_type"])]


def _statargs(c: Config) -> Iterator:
    args = [
        (c, varname, tc, var, prefix)
        for (varname, var), tc in product(_vxvars(c).items(), validtimes(c.cycles, c.leadtimes))
        for prefix in ["%s_%s" % (c.forecast.name.lower(), str(var).replace("-", "_"))]
    ]
    return iter(args)


def _var(c: Config, varname: str, level: float | None) -> Var:
    m = _meta(c, varname)
    return Var(m.name, m.level_type, level)


def _vxvars(c: Config) -> dict[str, Var]:
    vxvars = {}
    for varname, attrs in c.variables.items():
        for level in attrs.get("levels", [None]):
            vxvars[varname] = Var(
                name=attrs["standard_name"], level_type=attrs["level_type"], level=level
            )
    return vxvars
