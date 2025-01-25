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

The content YAML configuration file supplied via `-c` / `--config` is described in the table below.

```
┌────────────────┬─────────────────────────────────────────────┐
│ Key            │ Description                                 │
├────────────────┼─────────────────────────────────────────────┤
│ baseline:      │ Template for baseline GRIB file URLs        │
│ cycles:        │ Cycles to verify                            │
│   start:       │ First cycle as ISO8601 timestamp            │
│   step:        │ Interval between cycles as hh[:mm[:ss]]     │
│   stop:        │ Last cycle as ISO8601 timestamp             │
│ forecast:      │ Path to netCDF or Zarr forecast             │
│ leadtimes:     │ Leadtimes to verify                         │
│   start:       │ First leadtime as hh[:mm[:ss]]              │
│   step:        │ Interval between leadtimes as hh[:mm[:ss]]  │
│   stop:        │ Last leadtime as hh[:mm[:ss]]               │
│ meta:          │ Optional free-form data section             │
│ rundir:        │ Run directory for temporary files           │
│ threads:       │ Number of concurrent threads to use         │
│ variables:     │ A sequence of variables to verify           │
│   - levels:    │ A sequence of level values                  │
│     levtype:   │ The level type                              │
│     name:      │ The variable name                           │
└────────────────┴─────────────────────────────────────────────┘
```

Use the `-s` / `--show` CLI switch to show a pro-forma config with realistic values for reference.

- The baseline URL template may include {yyyymmdd} (forecast date), {hh} (forecast hour), and {fh} (forecast leadtime) Jinja2 expressions, which will be replaced with appropriate values at run time.
- The last cycle/leadtime is included in verification. That is, the range upper bound is inclusive, not exclusive.
- The `meta:` block may contain, for example, values tagged with YAML anchors referenced elsewhere via aliases (see the _Aliases_ section [here](https://pyyaml.org/wiki/PyYAMLDocumentation)), or values referenced elsewhere in Jinja2 expressions as realized by `uwtools` (see examples in [here](https://uwtools.readthedocs.io/en/stable/sections/user_guide/cli/tools/config.html#realize)).
- The `variables:` block may be an arbitrarily long sequence of variable descriptions. Variable names and level types follow ECMWF conventions. See the [Parameter Database](https://codes.ecmwf.int/grib/param-db/) for details.
- Currently supported level types are: `atmosphere`, `isobaricInhPa`, `surface`.
- A `levels:` value should only be specified for variable supporting it, currently: `isobaricInhPa`.
