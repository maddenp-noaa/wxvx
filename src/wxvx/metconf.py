from typing import Callable, NoReturn

# Generic:


def bare(v: str) -> str:
    return f"{v}"


def fail(k: str) -> NoReturn:
    msg = f"Unsupported key: {k}"
    raise ValueError(msg)


def indent(v: str, level: int) -> str:
    return "  " * level + v


def kvpair(k: str, v: str, level: int) -> str:
    return indent(f"{k} = {v};", level)


def quoted(v: str) -> str:
    return f'"{v}"'


def mapping(k: str, v: list[str], level: int) -> list[str]:
    return [indent("%s = {" % k, level), *v, indent("}", level)]


def sequence(k: str, v: list, handler: Callable, level: int) -> list[str]:
    return [
        indent("%s = [" % k, level),
        *",\n".join([indent(handler(x), level + 1) for x in v]).split("\n"),
        indent("];", level),
    ]


# Item-specific:


def fcst_or_obs(d: dict, level: int) -> list[str]:
    lines = []
    for k, v in sorted(d.items()):
        match k:
            case "field":
                lines.extend(field_sequence(k, v, level))
            case _:
                fail(k)
    return lines


def field_mapping(d: dict, level: int) -> str:
    lines = [indent("{", level), *field_mapping_kvpairs(d, level + 1), indent("}", level)]
    return "\n".join(lines)


def field_mapping_kvpairs(d: dict, level: int) -> list[str]:
    lines = []
    for k, v in sorted(d.items()):
        match k:
            case "cat_thresh":
                lines.extend(sequence(k, v, bare, level))
            case "level":
                lines.extend(sequence(k, v, quoted, level))
            case "name":
                lines.append(kvpair(k, quoted(v), level))
            case _:
                fail(k)
    return lines


def field_sequence(k: str, v: list[dict], level: int) -> list[str]:
    return [
        indent("%s = [" % k, level),
        *",\n".join([field_mapping(d, level + 1) for d in v]).split("\n"),
        indent("];", level),
    ]


def mask(d: dict, level: int) -> list[str]:
    lines = []
    for k, v in sorted(d.items()):
        match k:
            case "poly":
                lines.extend(sequence(k, v, quoted, level))
            case _:
                fail(k)
    return lines


def output_flag(d: dict, level: int) -> list[str]:
    lines = []
    for k, v in sorted(d.items()):
        match k:
            case "cnt" | "cts":
                lines.append(kvpair(k, bare(v), level))
            case _:
                fail(k)
    return lines


def regrid(d: dict, level: int) -> list[str]:
    lines = []
    for k, v in sorted(d.items()):
        match k:
            case "to_grid":
                lines.append(kvpair(k, bare(v), level))
            case _:
                fail(k)
    return lines


# Top-level handler:


def render(config: dict) -> str:
    lines, level = [], 0
    for k, v in sorted(config.items()):
        match k:
            case "fcst" | "obs":
                lines.extend(mapping(k, fcst_or_obs(v, level + 1), level))
            case "model" | "obtype" | "output_prefix" | "tmp_dir":
                lines.append(kvpair(k, quoted(v), level))
            case "mask":
                lines.extend(mapping(k, mask(v, level + 1), level))
            case "nc_pairs_flag":
                lines.append(kvpair(k, bare(v), level))
            case "output_flag":
                lines.extend(mapping(k, output_flag(v, level + 1), level))
            case "regrid":
                lines.extend(mapping(k, regrid(v, level + 1), level))
            case _:
                fail(k)
    return "\n".join(lines)
