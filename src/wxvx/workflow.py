import logging
import stat
from itertools import pairwise
from pathlib import Path
from shutil import copyfile
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
    taskname = "Existing path %s" % path
    yield taskname
    yield asset(path, path.exists)


@task
def forecast_dataset(fcstpath: Path):
    taskname = "Forecast %s" % fcstpath
    ds = xr.Dataset()
    yield taskname
    yield asset(ds, lambda: bool(ds))
    yield existing(path=fcstpath)
    logging.info("%s: Opening forecast %s", taskname, fcstpath)
    with catch_warnings():
        simplefilter("ignore")
        ds.update(xr.open_dataset(fcstpath, decode_timedelta=True))


@task
def forecast_variable(c: Config, varname: str, tc: TimeCoords, var: Var):
    taskname = "%s forecast variable %s" % (tc, var)
    yyyymmdd, hh, leadtime = tcinfo(tc)
    path = c.workdir / "forecast" / yyyymmdd / hh / leadtime / f"{var}.nc"
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
    da["time"] = da.time + da.lead_time
    da = da.drop_vars("lead_time")
    ds = cf_compliant_dataset(da, taskname)
    path.parent.mkdir(parents=True, exist_ok=True)
    ds.to_netcdf(path)
    logging.info("%s: Wrote %s", taskname, path)


@task
def grib_index_data(c: Config, vxvars: VXVarsT, tc: TimeCoords, url: str):
    taskname = "%s GRIB index data" % tc
    idxdata: dict[str, HRRRVar] = {}
    idxfile = grib_index_local(c, tc, url)
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
def grib_index_local(c: Config, tc: TimeCoords, url: str):
    taskname = "%s GRIB index local" % tc
    leadtime = "%03d" % (tc.leadtime.total_seconds() // 3600)
    fn = Path(urlparse(url).path).name
    path = c.workdir / "baseline" / tc.yyyymmdd / tc.hh / leadtime / fn
    yield taskname
    yield asset(path, path.is_file)
    yield grib_index_remote(url, tc)
    fetch(taskname, url, path)


@external
def grib_index_remote(url: str, tc: TimeCoords):
    taskname = "%s GRIB index remote %s" % (tc, url)
    yield taskname
    yield asset(url, lambda: status(url) == 200)


@task
def grib_message(c: Config, tc: TimeCoords, var: Var, vxvars: VXVarsT):
    taskname = "%s GRIB message at %s" % (var, tc)
    leadtime = "%03d" % (tc.leadtime.total_seconds() // 3600)
    fn = "%s.grib2" % var
    path = c.workdir / "baseline" / tc.yyyymmdd / tc.hh / leadtime / fn
    yyyymmdd, hh, _ = tcinfo(TimeCoords(cycle=tc.validtime))
    url = c.baseline.template.format(yyyymmdd=yyyymmdd, hh=hh)
    idxdata = grib_index_data(c, vxvars, tc, url=f"{url}.idx")
    yield taskname
    yield asset(path, path.is_file)
    yield idxdata
    var_idxdata = refs(idxdata)[str(var)]
    fb, lb = var_idxdata.firstbyte, var_idxdata.lastbyte
    headers = {"Range": "bytes=%s" % (f"{fb}-{lb}" if lb else fb)}
    fetch(taskname, url, path, headers)


@task
def grid_stat_config(c: Config, basepath: Path, varname: str, rundir: Path, var: Var):
    path = (basepath.parent / basepath.stem).with_suffix(".config")
    taskname = "Verification config %s" % path
    yield taskname
    yield asset(path, path.is_file)
    yield None
    values = {
        "baseline_level": HRRRVar.metlevel(levtype=var.levtype, level=var.level),
        "baseline_name": HRRRVar.varname(name=var.name, levtype=var.levtype),
        "forecast_level": "(*,*)",
        "forecast_name": varname,
        "model": c.forecast.name,
        "obtype": c.baseline.name,
        "tmpdir": rundir,
    }
    render(values_src=values, input_file=resource_path("config.grid_stat"), output_file=path)


@task
def plot(c: Config, varname: str):
    rundir = c.workdir / "run" / "plot"
    path = rundir / f"plot-{varname}.png"
    taskname = "Plotted stat data %s" % path
    reformatted = reformat(c)
    pc = plot_config(c, rundir, varname, plotfn=path.name, statfn=refs(reformatted).name)
    cmd = "line.py %s >%s 2>&1" % (refs(pc).name, f"plot-{varname}.log")
    rs = runscript(taskname, basepath=path, content=cmd)
    yield taskname
    yield asset(path, path.is_file)
    yield [pc, reformatted, rs]
    mpexec(str(refs(rs)), rundir, taskname)


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
def reformat(c: Config):
    rundir = c.workdir / "run" / "plot"
    path = rundir / "reformat.data"
    taskname = "Reformatted stat data %s" % path
    rc = reformat_config(rundir)
    stats = statfiles(c)
    cmd = "write_stat_ascii.py %s >reformat.log 2>&1" % refs(rc).name
    rs = runscript(taskname, basepath=path, content=cmd)
    yield taskname
    yield asset(path, path.is_file)
    yield [rc, rs, stats]
    mpexec(str(refs(rs)), rundir, taskname)


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
def runscript(taskname: str, basepath: Path, content: str):
    path = (basepath.parent / basepath.stem).with_suffix(".sh")
    yield "%s: Runscript %s" % (taskname, path)
    yield asset(path, path.is_file)
    yield None
    with path.open("w") as f:
        print(f"#!/usr/bin/env bash\n\n{content}", file=f)
    path.chmod(path.stat().st_mode | stat.S_IEXEC)


@task
def statfile(c: Config, varname: str, tc: TimeCoords, var: Var, vxvars: VXVarsT):
    taskname = "MET grid_stat results for %s at %s" % (var, tc)
    yyyymmdd, hh, leadtime = tcinfo(tc)
    rundir = c.workdir / "run" / yyyymmdd / hh / leadtime
    yyyymmdd_valid, hh_valid, _ = tcinfo(TimeCoords(tc.validtime))
    fn = "grid_stat_000000L_%s_%s0000V.stat" % (yyyymmdd_valid, hh_valid)
    path = rundir / fn
    fv = forecast_variable(c, varname, tc, var)
    tcvalid = TimeCoords(cycle=tc.validtime)
    gm = grib_message(c, tcvalid, var, vxvars)
    gsc = grid_stat_config(c, path, varname, rundir, var)
    log = f"{path.stem}.log"
    content = f"""
    export OMP_NUM_THREADS=1
    grid_stat -v 3 {refs(fv)} {refs(gm)} {refs(gsc).name} >{log} 2>&1
    """
    rs = runscript(taskname, basepath=path, content=dedent(content).strip())
    yield taskname
    yield asset(path, path.is_file)
    yield [fv, gm, gsc, rs]
    mpexec(str(refs(rs)), rundir, taskname)


@task
def statfiles(c: Config):
    taskname = "MET grid_stat results for %s" % c.forecast.path
    vxvars = {}
    for varname, attrs in c.variables.items():
        for level in attrs.get("levels", [None]):
            vxvars[varname] = Var(name=attrs["stdname"], levtype=attrs["levtype"], level=level)
    reqs = [
        statfile(c, varname, tc, var, vxvars)
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
