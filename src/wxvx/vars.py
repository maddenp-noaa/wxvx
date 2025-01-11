import re
from typing import Optional

from wxvx.strings import STR


class Var:

    def __init__(self, name: str, level: Optional[int], levtype: str):
        self.name = name
        self.level = level
        self.levtype = levtype

    def __eq__(self, other):
        return (
            self.name == other.name and self.level == other.level and self.levtype == other.levtype
        )


class GFSVar(Var):

    def __init__(self, name: str, first_byte: int, last_byte: int, levstr: str):
        super().__init__(name=name, level=GFSVar._level(levstr), levtype=GFSVar._levtype(levstr))
        self.first_byte = first_byte
        self.last_byte = last_byte if last_byte > 0 else None

    @staticmethod
    def canonical(name: str) -> Optional[str]:
        return {
            "HGT": "gh",
            "REFC": "refc",
            "SPFH": "q",
            "T2M": "t",
            "TMP": "t",
            "UGRD": "u",
            "VGRD": "v",
            "VVEL": "w",
        }.get(name)

    @staticmethod
    def _pressure_level(levstr: str) -> Optional[int]:
        return int(m[1]) if (m := re.match(r"^(\d+) mb$", levstr)) else None

    @staticmethod
    def _level(levstr: str) -> Optional[int]:
        if levstr == STR.surface:
            return None
        if level := GFSVar._pressure_level(levstr):
            return level
        raise NotImplementedError("Unhandled level: %s" % levstr)

    @staticmethod
    def _levtype(levstr: str) -> str:
        if levstr == STR.surface:
            return STR.surface
        if GFSVar._pressure_level(levstr):
            return STR.pressure
        raise NotImplementedError("Unhandled level: %s" % levstr)
