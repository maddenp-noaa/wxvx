# wxvx

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

- The baseline URL template may include {yyyymmdd} (forecast date) and {hh} (forecast hour) Jinja2 expressions, which will be replaced with appropriate values at run time.
- The last cycle/leadtime is included in verification. That is, the range upper bound is inclusive, not exclusive.
- The `meta:` block may contain, for example, values tagged with YAML anchors referenced elsewhere via aliases (see the _Aliases_ section [here](https://pyyaml.org/wiki/PyYAMLDocumentation)), or values referenced elsewhere in Jinja2 expressions as realized by `uwtools` (see examples in [here](https://uwtools.readthedocs.io/en/stable/sections/user_guide/cli/tools/config.html#realize)).
- The `variables:` block may be an arbitrarily long sequence of variable descriptions. Generic variable names and level types follow ECMWF conventions. See the [Parameter Database](https://codes.ecmwf.int/grib/param-db/) for details.
- Currently supported level types are: `atmosphere`, `heightAboveGround`, `isobaricInhPa`, `surface`.
- A `levels:` value should only be specified for variable supporting it, currently: `heightAboveGround`, `isobaricInhPa`.

## TODO

- Generalize for more baseline dataset types.
- Support loading Zarr forecast data remotely.
