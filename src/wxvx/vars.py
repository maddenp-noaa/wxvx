import re
from typing import Optional

UNKNOWN = "unknown"


class Var:

    def __init__(self, name: str, levtype: str, level: Optional[str] = None):
        self.name = name
        self.levtype = levtype
        self.level = str(level) if level else None
        self._keys = ["name", "levtype", "level"] if self.level else ["name", "levtype"]

    def __eq__(self, other):
        return hash(self) == hash(other)

    def __hash__(self):
        return hash((self.name, self.level, self.levtype))

    def __repr__(self):
        vals = [f"{k}={v}" for k, v in zip(self._keys, [getattr(self, key) for key in self._keys])]
        return "%s(%s)" % (self.__class__.__name__, ", ".join(vals))

    def __str__(self):
        level = f"{int(self.level):04}" if self.level else None
        vals = filter(None, [self.name, self.levtype, level])
        return "-".join(vals)


class GFSVar(Var):

    def __init__(self, name: str, levstr: str, firstbyte: int, lastbyte: int):
        levtype, level = self._levinfo(levstr)
        super().__init__(name=name, levtype=levtype, level=level)
        self.firstbyte: int = firstbyte
        self.lastbyte: Optional[int] = lastbyte if lastbyte > 0 else None
        self._keys = (
            ["name", "levtype", "level", "firstbyte", "lastbyte"]
            if self.level
            else ["name", "levtype", "firstbyte", "lastbyte"]
        )

    @staticmethod
    def stdvar(name: str) -> str:
        return {
            "HGT": "gh",
            "REFC": "refc",
            "SPFH": "q",
            "T2M": "t",
            "TMP": "t",
            "UGRD": "u",
            "VGRD": "v",
            "VVEL": "w",
        }.get(name, UNKNOWN)

    @staticmethod
    def _level_pressure(levstr: str) -> Optional[str]:
        return m[1] if (m := re.match(r"^([0-9\.]+) mb$", levstr)) else None

    @staticmethod
    def _levinfo(levstr: str) -> tuple[str, Optional[str]]:
        if m := re.match(r"^entire atmosphere$", levstr):
            return ("atmosphere", None)
        if m := re.match(r"^(\d+(\.\d+)?) mb$", levstr):
            return ("isobaricInhPa", m[1])
        if m := re.match(r"^surface$", levstr):
            return ("surface", None)
        return (UNKNOWN, None)
