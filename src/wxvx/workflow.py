import logging
from itertools import pairwise
from pathlib import Path
from shutil import copyfile
from stat import S_IEXEC
from textwrap import dedent
from urllib.parse import urlparse
from warnings import catch_warnings, simplefilter

import numpy as np
import xarray as xr
import yaml
from iotaa import asset, external, refs, task, tasks
from uwtools.api.template import render

from wxvx.net import fetch, status
from wxvx.times import TimeCoords, tcinfo, validtimes
from wxvx.types import Config, VXVarsT
from wxvx.util import WXVXError, mpexec, resource_path
from wxvx.variables import HRRRVar, Var, cf_compliant_dataset, forecast_var_units


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
def grib_index_data(outdir: Path, vxvars: VXVarsT, tc: TimeCoords, url: str):
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
        if hrrrvar in vxvars.values():
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
def grid_grib(c: Config, tc: TimeCoords, var: Var, vxvars: VXVarsT):
    yyyymmdd, hh, leadtime = tcinfo(tc)
    outdir = c.workdir / "grids" / yyyymmdd / hh / leadtime
    path = outdir / f"{var}.grib2"
    taskname = "Baseline grid %s" % path
    url = c.baseline.template.format(yyyymmdd=yyyymmdd, hh=hh, ff="%02d" % int(leadtime))
    idxdata = grib_index_data(outdir, vxvars, tc, url=f"{url}.idx")
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
    try:
        da = (
            refs(fd)[varname]
            .sel(time=np.datetime64(str(tc.cycle.isoformat())))
            .sel(lead_time=np.timedelta64(int(tc.leadtime.total_seconds()), "s"))
        )
    except KeyError as e:
        msg = "Variable %s valid at %s not found in %s" % (varname, tc, c.forecast.path)
        raise WXVXError(msg) from e
    if var.level is not None and hasattr(da, "level"):
        da = da.sel(level=var.level)
    da = xr.DataArray(
        data=da.expand_dims(dim=["init_time", "valid_time"]),
        coords=dict(
            init_time=[da.time.values + np.timedelta64(0, "s")],
            valid_time=[da.time.values + da.lead_time.values],
            latitude=da.latitude,
            longitude=da.longitude,
        ),
        dims=("init_time", "valid_time", "latitude", "longitude"),
        name=varname,
    )
    ds = cf_compliant_dataset(da, taskname)
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
        "baseline_level": HRRRVar.metlevel(level_type=var.level_type, level=var.level),
        "baseline_name": HRRRVar.varname(name=var.name, level_type=var.level_type),
        "forecast_level": "(0,0,*,*)",
        "forecast_name": varname,
        # "forecast_level": HRRRVar.metlevel(level_type=var.level_type, level=var.level),  # TOGGLE
        # "forecast_name": HRRRVar.varname(name=var.name, level_type=var.level_type),  # TOGGLE
        "model": c.forecast.name,
        "obtype": c.baseline.name,
        "prefix": f"{prefix}",
        "tmpdir": rundir,
    }
    render(values_src=values, input_file=resource_path("config.grid_stat"), output_file=path)


@task
def plot(c: Config, varname: str):
    rundir = c.workdir / "run" / "plot"
    path = rundir / f"plot-{varname}.png"
    taskname = "Plot of stat data %s" % path
    reformatted = reformat(c, rundir)
    cfgfile = plot_config(c, rundir, varname, plotfn=path.name, statfn=refs(reformatted).name)
    content = "line.py %s >%s 2>&1" % (refs(cfgfile).name, f"plot-{varname}.log")
    script = runscript(basepath=path, content=content)
    yield taskname
    yield asset(path, path.is_file)
    yield [cfgfile, reformatted, script]
    mpexec(str(refs(script)), rundir, taskname)


@task
def plot_config(c: Config, rundir: Path, varname: str, plotfn: str, statfn: str):
    path = rundir / f"plot-{varname}.yaml"
    taskname = "Plot config %s" % path
    yield taskname
    yield asset(path, path.is_file)
    yield None
    stat = "RMSE"
    vts = validtimes(c.cycles, c.leadtimes)
    x_axis_labels = [
        vt.validtime.strftime("%Y%m%d %HZ") if i % 10 == 0 else "" for i, vt in enumerate(vts)
    ]
    config = {
        "colors": ["#32cd32"],
        "con_series": [1],
        "fcst_var_val_1": {varname: [stat]},
        # "fcst_var_val_1": {forecast_var_name_hrrr(varname): [stat]},  # TOGGLE
        "grid_col": "#cccccc",
        "indy_label": x_axis_labels,
        "indy_vals": [vt.validtime.strftime("%Y-%m-%d %H:%M:%S") for vt in vts],
        "indy_var": "fcst_init_beg",
        "legend_box": "n",
        "line_type": "cnt",
        "list_stat_1": [stat],
        "log_level": "DEBUG",
        "plot_caption": "",
        "plot_ci": ["none"],
        "plot_disp": [True],
        "plot_filename": plotfn,
        "plot_height": 10,
        "plot_width": 13,
        "series_line_style": ["-"],
        "series_line_width": [1],
        "series_order": [1],
        "series_symbols": ["."],
        "series_type": ["b"],
        "series_val_1": {"model": [c.forecast.name]},
        "show_legend": [True],
        "stat_input": statfn,
        "title": "%s (%s) 1-hour forecast %s" % (varname, forecast_var_units(varname), stat),
        "user_legend": ["%s vs %s" % (c.forecast.name, c.baseline.name)],
        "xaxis": "Cycle",
        "xlab_offset": 20,
        "xtlab_orient": 270,
        "yaxis_1": stat,
        "ylab_offset": 20,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        yaml.dump(config, f)


@task
def reformat(c: Config, rundir: Path):
    path = rundir / "reformat.data"
    taskname = "Reformatted grid_stat results %s" % path
    cfgfile = reformat_config(rundir)
    content = f"""
    export PYTHONWARNINGS=ignore::FutureWarning
    write_stat_ascii.py {refs(cfgfile).name} >reformat.log 2>&1
    """
    script = runscript(basepath=path, content=content)
    yield taskname
    yield asset(path, path.is_file)
    yield [cfgfile, script, stats(c)]
    mpexec(str(refs(script)), rundir, taskname)


@task
def reformat_config(rundir: Path):
    path = rundir / "reformat.yaml"
    taskname = "Reformat config %s" % path
    yield taskname
    yield asset(path, path.is_file)
    yield None
    path.parent.mkdir(parents=True, exist_ok=True)
    copyfile(resource_path("reformat.yaml"), path)


@task
def runscript(basepath: Path, content: str):
    path = (basepath.parent / basepath.stem).with_suffix(".sh")
    yield "Runscript %s" % path
    yield asset(path, path.is_file)
    yield None
    with path.open("w") as f:
        print(f"#!/usr/bin/env bash\n\n{content}", file=f)
    path.chmod(path.stat().st_mode | S_IEXEC)


@task
def stat(c: Config, varname: str, tc: TimeCoords, var: Var, vxvars: VXVarsT, prefix: str):
    yyyymmdd, hh, leadtime = tcinfo(tc)
    taskname = "MET grid_stat result %s at %s %sZ %s" % (var, yyyymmdd, hh, leadtime)
    rundir = c.workdir / "run" / "stat" / yyyymmdd / hh / leadtime
    yyyymmdd_valid, hh_valid, _ = tcinfo(TimeCoords(tc.validtime))
    fn = "grid_stat_%s_%02d0000L_%s_%s0000V.stat" % (
        prefix,
        0,  # int(leadtime),
        yyyymmdd_valid,
        hh_valid,
    )
    path = rundir / fn
    forecast = grid_nc(c, varname, tc, var)
    # forecast = grid_grib(c, tc, var, vxvars)  # TOGGLE
    baseline = grid_grib(c, TimeCoords(cycle=tc.validtime, leadtime=0), var, vxvars)
    cfgfile = grid_stat_config(c, path, varname, rundir, var, prefix)
    log = f"{path.stem}.log"
    content = f"""
    export OMP_NUM_THREADS=1
    grid_stat -v 4 {refs(forecast)} {refs(baseline)} {refs(cfgfile).name} >{log} 2>&1
    """
    script = runscript(basepath=path, content=dedent(content).strip())
    yield taskname
    yield asset(path, path.is_file)
    yield [forecast, baseline, cfgfile, script]
    mpexec(str(refs(script)), rundir, taskname)


@task
def stats(c: Config):
    taskname = "MET grid_stat results for %s" % c.forecast.path
    vxvars = {}
    for varname, attrs in c.variables.items():
        for level in attrs.get("levels", [None]):
            vxvars[varname] = Var(
                name=attrs["stdname"], level_type=attrs["level_type"], level=level
            )
    reqs = [
        stat(c, varname, tc, var, vxvars, "forecast_%s" % str(var).replace("-", "_"))
        for tc in validtimes(c.cycles, c.leadtimes)
        for varname, var in vxvars.items()
    ]
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
    reqs = [plot(c, varname) for varname in c.variables]
    yield taskname
    yield reqs
