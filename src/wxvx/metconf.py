from typing import Any, Callable, NoReturn

# Generic:


def bare(v: str) -> str:
    return f"{v}"


def collect(f: Callable, d: dict, level: int) -> list[str]:
    lines = []
    for k, v in sorted(d.items()):
        lines.extend(f(k, v, level))
    return lines


def fail(k: str) -> NoReturn:
    msg = f"Unsupported key: {k}"
    raise ValueError(msg)


def indent(v: str, level: int) -> str:
    return "  " * level + v


def kvpair(k: str, v: str, level: int) -> list[str]:
    return [indent(f"{k} = {v};", level)]


def mapping(k: str, v: list[str], level: int) -> list[str]:
    return [indent("%s = {" % k, level), *v, indent("}", level)]


def quoted(v: str) -> str:
    return f'"{v}"'


def sequence(k: str, v: list, handler: Callable, level: int) -> list[str]:
    return [
        indent("%s = [" % k, level),
        *",\n".join([indent(handler(x), level + 1) for x in v]).split("\n"),
        indent("];", level),
    ]


# Item-specific:


def fcst_or_obs(k: str, v: list[dict], level: int) -> list[str]:
    match k:
        case "field":
            return field_sequence(k, v, level)
    fail(k)


def field_mapping(d: dict, level: int) -> str:
    lines = [indent("{", level), *collect(field_mapping_kvpairs, d, level + 1), indent("}", level)]
    return "\n".join(lines)


def field_mapping_kvpairs(k: str, v: Any, level: int) -> list[str]:
    match k:
        case "cat_thresh":
            return sequence(k, v, bare, level)
        case "level":
            return sequence(k, v, quoted, level)
        case "name":
            return kvpair(k, quoted(v), level)
    fail(k)


def field_sequence(k: str, v: list[dict], level: int) -> list[str]:
    mappings = ",\n".join([field_mapping(d, level + 1) for d in v]).split("\n")
    return [indent("%s = [" % k, level), *mappings, indent("];", level)]


def mask(k: str, v: list, level: int) -> list[str]:
    match k:
        case "poly":
            return sequence(k, v, quoted, level)
    fail(k)


def output_flag(k: str, v: str, level: int) -> list[str]:
    match k:
        case "cnt" | "cts":
            return kvpair(k, bare(v), level)
    fail(k)


def regrid(k: str, v: Any, level: int) -> list[str]:
    match k:
        case "to_grid":
            return kvpair(k, bare(v), level)
    fail(k)


# Top-level handler:


def render(config: dict) -> str:
    lines, level = [], 0
    for k, v in sorted(config.items()):
        match k:
            case "fcst" | "obs":
                lines.extend(mapping(k, collect(fcst_or_obs, v, level + 1), level))
            case "model" | "obtype" | "output_prefix" | "tmp_dir":
                lines.extend(kvpair(k, quoted(v), level))
            case "mask":
                lines.extend(mapping(k, collect(mask, v, level + 1), level))
            case "nc_pairs_flag":
                lines.extend(kvpair(k, bare(v), level))
            case "output_flag":
                lines.extend(mapping(k, collect(output_flag, v, level + 1), level))
            case "regrid":
                lines.extend(mapping(k, collect(regrid, v, level + 1), level))
            case _:
                fail(k)
    return "\n".join(lines)
