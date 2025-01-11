from dataclasses import dataclass


@dataclass(frozen=True)
class STR:
    pressure: str = "pressure"
    surface: str = "surface"
