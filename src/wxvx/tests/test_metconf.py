from wxvx import metconf

config = {
    "fcst": {"field": [{"cat_thresh": [">0"], "level": ["(0,0,*,*)"], "name": "T2M"}]},
    "mask": {"poly": ["a.nc"]},
    "model": "GraphHRRR",
    "nc_pairs_flag": "FALSE",
    "obs": {"field": [{"cat_thresh": [">0"], "level": ["Z2"], "name": "TMP"}]},
    "obtype": "HRRR",
    "output_flag": {"cnt": "BOTH"},
    "output_prefix": "foo_bar",
    "regrid": {"to_grid": "FCST"},
    "tmp_dir": "/path/to/dir",
}

expected = """
fcst = {
  field = [
    {
      cat_thresh = [
        >0
      ];
      level = [
        "(0,0,*,*)"
      ];
      name = "T2M";
    }
  ];
}
mask = {
  poly = [
    "a.nc"
  ];
}
model = "GraphHRRR";
nc_pairs_flag = FALSE;
obs = {
  field = [
    {
      cat_thresh = [
        >0
      ];
      level = [
        "Z2"
      ];
      name = "TMP";
    }
  ];
}
obtype = "HRRR";
output_flag = {
  cnt = BOTH;
}
output_prefix = "foo_bar";
regrid = {
  to_grid = FCST;
}
tmp_dir = "/path/to/dir";
"""


def test_metconf_render():
    assert metconf.render(config=config).strip() == expected.strip()
