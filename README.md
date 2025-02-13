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

## Use

```
$ wxvx --help
usage: wxvx -c FILE [-d] [-h] [-s] [-v]

wxvx

Required arguments:
  -c FILE, --config FILE
      Configuration file

Optional arguments:
  -d, --debug
      Log all messages
  -h, --help
      Show help and exit
  -s, --show
      Show a pro-forma config and exit
  -v, --version
      Show version and exit
```

## Configuration

The content of the YAML configuration file supplied via `-c` / `--config` is described in the table below.

```
┌────────────────┬──────────────────────────────────────────────┐
│ Key            │ Description                                  │
├────────────────┼──────────────────────────────────────────────┤
│ baseline:      │ Description of the baseline dataset          │
│   name:        │   Dataset descriptive name                   │
│   url:         │   Template for baseline GRIB file URLs       │
│ cycles:        │ Cycles to verify                             │
│   start:       │   First cycle as ISO8601 timestamp           │
│   step:        │   Interval between cycles as hh[:mm[:ss]]    │
│   stop:        │   Last cycle as ISO8601 timestamp            │
│ forecast:      │ Description of the forecast dataset          │
│   name:        │   Dataset descriptive name                   │
│   path:        │   Filesystem path to Zarr/netCDF dataset     │
│ leadtimes:     │ Leadtimes to verify                          │
│   start:       │   First leadtime as hh[:mm[:ss]]             │
│   step:        │   Interval between leadtimes as hh[:mm[:ss]] │
│   stop:        │   Last leadtime as hh[:mm[:ss]]              │
│ meta:          │ Optional free-form data section              │
│ threads:       │ Number of concurrent threads to use          │
│ variables:     │ Mapping describing variables to verify       │
│   VAR:         │   Forecast-dataset variable name             │
│     levels:    │     Sequence of level values                 │
│     levtype:   │     Generic level type                       │
│     name:      │     Generic variable name                    │
│ workdir:       │ Base directory for temporary files           │
└────────────────┴──────────────────────────────────────────────┘
```

Use the `-s` / `--show` CLI switch to show a pro-forma config with realistic values for reference.

- The `baseline` URL template may include `{yyyymmdd}` (forecast date) and `{hh}` (forecast hour) Jinja2 expressions, which will be replaced with appropriate values at run time.
- The last cycle/leadtime is included in verification. That is, the ranges are inclusive of their upper bounds.
- The `meta:` block may contain, for example, values tagged with YAML anchors referenced elsewhere via aliases (see the _Aliases_ section [here](https://pyyaml.org/wiki/PyYAMLDocumentation)), or values referenced elsewhere in Jinja2 expressions to be rendered by `uwtools` (see examples in [here](https://uwtools.readthedocs.io/en/stable/sections/user_guide/cli/tools/config.html#realize)).
- The `variables:` block is an arbitrarily long mapping from forecast-dataset variable names to generic descriptions of the named variables. Generic-description attributes (names and level types) follow ECMWF conventions: See the [Parameter Database](https://codes.ecmwf.int/grib/param-db/) for names, and [this list](https://codes.ecmwf.int/grib/format/edition-independent/3/) or the output of [`grib_ls`](https://confluence.ecmwf.int/display/ECC/grib_ls) run on a GRIB file containing the variable in question, for level types.
- Currently supported level types are: `atmosphere`, `heightAboveGround`, `isobaricInhPa`, `surface`.
- A `levels:` value should only be specified if a level type supports it. Currently, these are: `heightAboveGround`, `isobaricInhPa`.
- [CF Metadata](https://cfconventions.org/) are added to the copies made of forecast variables that are provided to MET, which requires them. See [this database](https://cfconventions.org/Data/cf-standard-names/current/build/cf-standard-name-table.html) for CF standard names and units.

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

## TODO

- Generalize for more baseline dataset types.
- Support loading Zarr forecast data remotely.
