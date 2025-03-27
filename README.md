# wxvx

A workflow tool for weather-model verification, leveraging [`uwtools`](https://github.com/ufs-community/uwtools) to drive [MET](https://github.com/dtcenter/MET) and [METplus](https://github.com/dtcenter/METplus).

## Installation

1. Download, install, and activate [Miniforge](https://github.com/conda-forge/miniforge), the [conda-forge](https://conda-forge.org/) project's implementation of [Miniconda](https://docs.anaconda.com/miniconda/). This step can be skipped if you already have a conda installation you want to use. Linux `aarch64` and `x86_64` systems are currently supported. The example shown below is for a Linux `aarch64` system, so if your system is Intel/AMD, download the `x86_64` installer.

``` bash
wget https://github.com/conda-forge/miniforge/releases/download/24.11.3-0/Miniforge3-Linux-aarch64.sh
bash Miniforge3-Linux-aarch64.sh -bfp conda
rm Miniforge3-Linux-aarch64.sh
. conda/etc/profile.d/conda.sh
conda activate
```

2. Create and activate a conda virtual environment providing the latest `wxvx`. Add the flags `-c conda-forge --override-channels` to the `conda create` command if you are using a non-conda-forge conda installation.

``` bash
conda create -y -n wxvx -c ufs-community -c maddenp wxvx
conda activate wxvx
wxvx --version
```

The activated virtual environment includes the [`metkit`](https://github.com/maddenp-noaa/metkit) package, which provides [MET](https://github.com/dtcenter/MET) and select [METplus](https://github.com/dtcenter/METplus) executables and data files. See the `metkit` [docs](https://github.com/maddenp-noaa/metkit/blob/main/README.md) for more information.

## Configuration

The content of the YAML configuration file supplied via `-c` / `--config` is described in the table below.

```
┌────────────────────┬──────────────────────────────────────────────┐
│ Key                │ Description                                  │
├────────────────────┼──────────────────────────────────────────────┤
│ baseline:          │ Description of the baseline dataset          │
│   name:            │   Dataset descriptive name                   │
│   plot:            │   Plot baseline forecast?                    │
│   url:             │   Template for baseline GRIB file URLs       │
│ cycles:            │ Cycles to verify                             │
│   start:           │   First cycle as ISO8601 timestamp           │
│   step:            │   Interval between cycles as hh[:mm[:ss]]    │
│   stop:            │   Last cycle as ISO8601 timestamp            │
│ forecast:          │ Description of the forecast dataset          │
│   name:            │   Dataset descriptive name                   │
│   path:            │   Filesystem path to Zarr/netCDF dataset     │
│   projection:      │   Projection name and attributes (see below) │
│ leadtimes:         │ Leadtimes to verify                          │
│   start:           │   First leadtime as hh[:mm[:ss]]             │
│   step:            │   Interval between leadtimes as hh[:mm[:ss]] │
│   stop:            │   Last leadtime as hh[:mm[:ss]]              │
│ meta:              │ Optional free-form data section              │
│ paths:             │ Paths                                        │
│   grids:           │   Where to store netCDF/GRIB grids           │
│   run:             │   Where to store run data                    │
│ variables:         │ Mapping describing variables to verify       │
│   VAR:             │   Forecast-dataset variable name             │
│     level_type:    │     Generic level type                       │
│     levels:        │     Sequence of level values                 │
│     name:          │     Canonical variable name                  │
└────────────────────┴──────────────────────────────────────────────┘
```

Use the `-s` / `--show` CLI switch to show a pro-forma config with realistic values for reference.

- The `baseline` URL template may include `{yyyymmdd}` (forecast date) and `{hh}` (forecast hour) Jinja2 expressions, which will be replaced with appropriate values at run time.
- The last cycle/leadtime is included in verification. That is, the ranges are inclusive of their upper bounds.
- The `meta:` block may contain, for example, values tagged with YAML anchors referenced elsewhere via aliases (see the _Aliases_ section [here](https://pyyaml.org/wiki/PyYAMLDocumentation)), or values referenced elsewhere in Jinja2 expressions to be rendered by `uwtools` (see examples in [here](https://uwtools.readthedocs.io/en/stable/sections/user_guide/cli/tools/config.html#realize)).
- The `variables:` block is an arbitrarily long mapping from forecast-dataset variable names to generic descriptions of the named variables. Generic-description attributes (names and level types) follow ECMWF conventions: See the [Parameter Database](https://codes.ecmwf.int/grib/param-db/) for names, and [this list](https://codes.ecmwf.int/grib/format/edition-independent/3/) or the output of [`grib_ls`](https://confluence.ecmwf.int/display/ECC/grib_ls) run on a GRIB file containing the variable in question, for level types.
- Currently supported level types are: `atmosphere`, `heightAboveGround`, `isobaricInhPa`, `surface`.
- A `levels:` value should only be specified if a level type supports it. Currently, these are: `heightAboveGround`, `isobaricInhPa`.
- [CF Metadata](https://cfconventions.org/) are added to the copies made of forecast variables that are provided to MET, which requires them. See [this database](https://cfconventions.org/Data/cf-standard-names/current/build/cf-standard-name-table.html) for CF standard names and units.
- The `forecast.projection` value should be a mapping with at least a `proj` key identifying the ID of the [projection](https://proj.org/en/stable/operations/projections/index.html), and potentially additional projection attributes depending on the `proj` value:
  - When `proj` is [`latlon`](https://proj.org/en/stable/operations/conversions/latlon.html), specify no additional attributes.
  - When `proj` is [`lcc`](https://proj.org/en/stable/operations/projections/lcc.html), specify attributes `a`, `b`, `lat_0`, `lat_1`, `lat_2`, and `lon_0`.

## Use

```
$ wxvx --help
usage: wxvx -c FILE [-t [TASK]] [-d] [-h] [-k] [-n N] [-s] [-v]

wxvx

Required arguments:
  -c FILE, --config FILE
      Configuration file
  -t [TASK], --task [TASK]
      Execute task (no argument => list available tasks)

Optional arguments:
  -d, --debug
      Log all messages
  -h, --help
      Show help and exit
  -k, --check
      Check config and exit
  -n N, --threads N
      Threads
  -s, --show
      Show a pro-forma config and exit
  -v, --version
      Show version and exit
```

### Example

Consider a `config.yaml`

``` yaml
baseline:
  name: HRRR
  plot: true
  template: https://noaa-hrrr-bdp-pds.s3.amazonaws.com/hrrr.{yyyymmdd}/conus/hrrr.t{hh}z.wrfprsf{ff}.grib2
cycles:
  start: "2025-03-01T00:00:00"
  step: "01:00:00"
  stop: "2025-03-01T23:00:00"
forecast:
  name: ML
  path: /path/to/forecast.zarr
  projection:
    proj: latlon
leadtimes:
  start: "03:00:00"
  step: "03:00:00"
  stop: "09:00:00"
meta:
  levels: &levels [800, 1000]
  workdir: /path/to/workdir
paths:
  grids: "{{ meta.workdir }}/grids"
  run: "{{ meta.workdir }}/run"
variables:
  HGT:
    level_type: isobaricInhPa
    levels: *levels
    name: gh
  REFC:
    level_type: atmosphere
    name: refc
  T2M:
    level_type: heightAboveGround
    levels: [2]
    name: 2t
```

This config directs `wxvx` to find forecast data, in Zarr format and on a regular lat/lon grid, under `/path/to/forecast.zarr`. The forecast will be called `ML` in MET `.stat` files and in plots. It will be verified against `HRRR` analysis, which can be found in GRIB files in an AWS bucket at URLs given as the `baseline.template` value, where `yyyymmdd`, `hh`, and `ff` will be filled in by `wxvx`. 24 hourly cycles starting at 2025-03-01 00Z, each with forecast leadtimes 3, 6, and 9, will be verified. Variable grids extracted from forecast and baseline datasets will be written to `/path/to/workdir/grids`, and run output will be created in `/path/to/workdir/run`: The [Jinja2](https://jinja.palletsprojects.com/en/stable/) expressions inside `{{ }}` markers will be processed by [`uwtools`](https://uwtools.readthedocs.io/en/stable/) and may use any features it supports. Three variables -- geopotential height, composite reflectivity, and 2-meter temperature, will be verified. The keys under `variables` map the names of the variables as they appear in the forecast dataset to a canonical description of the variable using ECMWF variable names and level-type descriptions (see the notes in the _Configuration_ section for links). Note that some variables do not support a "level" concept. So, the full verification task-graph will comprise: cycles x leadtimes x variables x levels.

Invoking `wxvx -c config.yaml -t grids` would stage the forecast and baseline grids on disk, only; `-t stats` would produce statistics via MET tools, but also stage grids if they are not already available; and `-t plots` would plot statistics, but also _produce_ statistics (and stage grids) if they are not already available.

## Development

1. In the `base` environment of a [Miniforge](https://github.com/conda-forge/miniforge) installation, install the [`condev`](https://github.com/maddenp/condev) package. Add the flags `-c conda-forge --override-channels` to the `conda create` command if using a non-conda-forge conda installation.

``` bash
conda install -y -c maddenp condev
```

2. In the root directory of a `wxvx` git clone:

``` bash
make devshell
```

This will create and activate a conda virtual environment named `DEV-wxvx`, where all build, run, and test requirement packages are available, and the code under `src/wxvx/` is live-linked into the environment, such that code changes are immediately live and testable. Several `make` targets are available: `make format` formats Python code and JSON documents, and `make test` runs all code-quality checks (equivalent to `make lint && make typecheck && make unittest`, targets which can also be run independently). A common development idiom is to periodically run `make format && make test`.

When you are finished, type `exit` to return to your previous shell. The `DEV-wxvx` environment will still exist, and a future `make devshell` command will more-or-less instantly activate it again.

## Extract Grid Projection from GRIB

``` python
conda install -y pygrib
python -c "import pygrib; print(pygrib.open('a.grib2').message(1).projparams)"
```
