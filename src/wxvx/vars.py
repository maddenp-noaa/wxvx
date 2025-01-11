import re
from typing import Optional

from wxvx.strings import STR


class Var:

    def __init__(self, name: Optional[str], level: Optional[int], levtype: Optional[str]):
        self.name = name
        self.level = level
        self.levtype = levtype

    def __eq__(self, other):
        return hash(self) == hash(other)

    def __hash__(self):
        return hash((self.name, self.level, self.levtype))

    def __repr__(self):
        return "%s(name='%s', level=%s, levtype='%s')" % (
            self.__class__.__name__,
            self.name,
            self.level,
            self.levtype,
        )


class GFSVar(Var):

    def __init__(self, name: Optional[str], first_byte: int, last_byte: int, levstr: str):
        super().__init__(name=name, level=GFSVar._level(levstr), levtype=GFSVar._levtype(levstr))
        self.first_byte = first_byte
        self.last_byte = last_byte if last_byte > 0 else None

    def __repr__(self):
        return "%s(name='%s', level=%s, levtype='%s', first_byte=%s, last_byte=%s)" % (
            self.__class__.__name__,
            self.name,
            self.level,
            self.levtype,
            self.first_byte,
            self.last_byte,
        )

    @staticmethod
    def stdvar(name: str) -> Optional[str]:
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
        return None

    @staticmethod
    def _levtype(levstr: str) -> Optional[str]:
        if levstr == STR.surface:
            return STR.surface
        if GFSVar._pressure_level(levstr):
            return STR.pressure
        return None
