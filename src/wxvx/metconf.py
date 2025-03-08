from typing import NoReturn

d = {
    # "fcst": {
    #     "field": [
    #         {
    #             "cat_thresh": [ ">0" ],
    #             "name": "TMP",
    #             "level": [ "Z2" ],
    #         }
    #     ]
    # },
    "mask": {
        "poly": [ "a.nc" ],
    },
    "model": "GraphHRRRR",
    "nc_pairs_flag": "FALSE",
    # "obs": {
    #     "field": [
    #         {
    #             "cat_thresh": [ ">0" ],
    #             "name": "TMP",
    #             "level": [ "Z2" ],
    #         }
    #     ]
    # },
    "obtype": "HRRR",
    "output_flag": {
        "cnt": "BOTH"
    },
    "output_prefix": "foo_bar",
    "regrid": {
        "to_grid": "FCST"
    },
    "tmp_dir": "/path/to"
}

def bare(s: str) -> str:
    return f'{s};'

def fail(k: str) -> NoReturn:
    raise ValueError(f"Unsupported key: {k}")

def indent(s: str, level: int) -> str:
    return "  " * level + s

def pair(k: str, v: str, level: int) -> str:
    return indent(f"{k} = {v}", level)

def quoted(s: str) -> str:
    return f'"{s}";'

def mapping(k: str, v: list[str], level: int) -> list[str]:
    return [indent("%s = {" % k, level), *v, indent("}", level)]

def mask(d: dict, level: int) -> list[str]:
    lines = []
    for k, v in sorted(d.items()):
        match k:
            case "poly":
                lines.extend(sequence(k, v, level + 1))
            case _:
                fail(k)
    return lines

def output_flag(d: dict, level: int) -> list[str]:
    lines = []
    for k, v in sorted(d.items()):
        match k:
            case "cnt" | "cts":
                lines.append(pair(k, bare(v), level))
            case _:
                fail(k)
    return lines

def regrid(d: dict, level: int) -> list[str]:
    lines = []
    for k, v in sorted(d.items()):
        match k:
            case "to_grid":
                lines.append(pair(k, bare(v), level))
            case _:
                fail(k)
    return lines

def sequence(k: str, v: list, level: int) -> list[str]:
    return [indent("%s = [" % k, level), *[indent(str(f"{x},"), level+1) for x in v], indent("]", level)]

def top(config: dict) -> str:
    lines, level = [], 0
    for k, v in sorted(d.items()):
        match k:
            case "model" | "obtype" | "output_prefix" | "tmp_dir":
                lines.append(pair(k, quoted(v), level))
            case "mask":
                lines.extend(mapping(k, mask(v, level + 1), level))
            case "nc_pairs_flag":
                lines.append(pair(k, bare(v), level))
            case "output_flag":
                lines.extend(mapping(k, output_flag(v, level + 1), level))
            case "regrid":
                lines.extend(mapping(k, regrid(v, level + 1), level))
    return "\n".join(lines)

print(top(d))

#model = "WRF";
#desc = "NA";
#obtype = "ANALYS";
#regrid = {
#   method = NEAREST;
#   shape = SQUARE;
#   to_grid = NONE;
#   vld_thresh = 0.5;
#   width = 1;
#}
#censor_thresh = [];
#censor_val = [];
#mpr_column = [];
#mpr_thresh = [];
#cat_thresh = [];
#cnt_thresh = [ NA ];
#cnt_logic = UNION;
#wind_thresh = [ NA ];
#wind_logic = UNION;
#eclv_points = 0.05;
#nc_pairs_var_name = "";
#nc_pairs_var_suffix = "";
#hss_ec_value = NA;
#rank_corr_flag = FALSE;
#fcst = {
#   field = [
#      {
#        name = "APCP";
#        level = [ "A03" ];
#        cat_thresh = [ >0.0, >=5.0 ];
#      }
#   ];
#}
#obs = fcst;
#climo_mean = {
#   file_name = [];
#   field = [];
#   regrid = {
#      method = NEAREST;
#      width = 1;
#      vld_thresh = 0.5;
#      shape = SQUARE;
#   }
#   time_interp_method = DW_MEAN;
#   day_interval = 31;
#   hour_interval = 6;
#}
#climo_stdev = climo_mean;
#climo_stdev = {
#   file_name = [];
#}
#climo_cdf = {
#   cdf_bins = 1;
#   center_bins = FALSE;
#   write_bins = TRUE;
#   direct_prob = FALSE;
#}
#mask = {
#   grid = [ "FULL" ];
#   poly = [];
#}
#ci_alpha = [ 0.05 ];
#boot = {
#   interval = PCTILE;
#   rep_prop = 1.0;
#   n_rep = 0;
#   rng = "mt19937";
#   seed = "";
#}
#interp = {
#   field = BOTH;
#   vld_thresh = 1.0;
#   shape = SQUARE;
#   type = [
#      {
#         method = NEAREST;
#         width = 1;
#      }
#   ];
#}
#nbrhd = {
#   field = BOTH;
#   vld_thresh = 1.0;
#   shape = SQUARE;
#   width = [ 1 ];
#   cov_thresh = [ >=0.5 ];
#}
#fourier = {
#   wave_1d_beg = [];
#   wave_1d_end = [];
#}
#gradient = {
#   dx = [ 1 ];
#   dy = [ 1 ];
#}
#distance_map = {
#   baddeley_p = 2;
#   baddeley_max_dist = NA;
#   fom_alpha = 0.1;
#   zhu_weight = 0.5;
#   beta_value(n) = n * n / 2.0;
#}
#output_flag = {
#   fho = NONE;
#   ctc = NONE;
#   cts = NONE;
#   mctc = NONE;
#   mcts = NONE;
#   cnt = NONE;
#   sl1l2 = NONE;
#   sal1l2 = NONE;
#   vl1l2 = NONE;
#   val1l2 = NONE;
#   vcnt = NONE;
#   pct = NONE;
#   pstd = NONE;
#   pjc = NONE;
#   prc = NONE;
#   eclv = NONE;
#   nbrctc = NONE;
#   nbrcts = NONE;
#   nbrcnt = NONE;
#   grad = NONE;
#   dmap = NONE;
#   seeps = NONE;
#}
#nc_pairs_flag = {
#   latlon = TRUE;
#   raw = TRUE;
#   diff = TRUE;
#   climo = TRUE;
#   climo_cdp = FALSE;
#   seeps = FALSE;
#   weight = FALSE;
#   nbrhd = FALSE;
#   fourier = FALSE;
#   gradient = FALSE;
#   distance_map = FALSE;
#   apply_mask = TRUE;
#}
#seeps_p1_thresh = NA;
#grid_weight_flag = NONE;
#tmp_dir = "/tmp";
#output_prefix = "";
#version = "V11.0.0";
#
