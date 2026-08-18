"""Typed config and domain models shared across pipeline stages."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class VerticalRange:
    start: int
    end: int

    def __post_init__(self) -> None:
        lo, hi = sorted((int(self.start), int(self.end)))
        object.__setattr__(self, "start", lo)
        object.__setattr__(self, "end", hi)

    def as_tuple(self) -> tuple[int, int]:
        return self.start, self.end


@dataclass(frozen=True, slots=True)
class BlockRegion:
    x0: int
    x1: int
    z0: int
    z1: int
    y0: int
    y1: int

    def __post_init__(self) -> None:
        x0, x1 = sorted((int(self.x0), int(self.x1)))
        z0, z1 = sorted((int(self.z0), int(self.z1)))
        y0, y1 = sorted((int(self.y0), int(self.y1)))
        object.__setattr__(self, "x0", x0)
        object.__setattr__(self, "x1", x1)
        object.__setattr__(self, "z0", z0)
        object.__setattr__(self, "z1", z1)
        object.__setattr__(self, "y0", y0)
        object.__setattr__(self, "y1", y1)

    @classmethod
    def from_values(cls, values: tuple[int, int, int, int, int, int] | list[int]) -> "BlockRegion":
        if len(values) != 6:
            raise ValueError(f"expected 6 values, got {len(values)}")
        return cls(*values)

    def as_tuple(self) -> tuple[int, int, int, int, int, int]:
        return self.x0, self.x1, self.z0, self.z1, self.y0, self.y1

    def as_xyz_pair(self) -> tuple[tuple[int, int, int], tuple[int, int, int]]:
        return (self.x0, self.y0, self.z0), (self.x1, self.y1, self.z1)

    def to_env_value(self) -> str:
        return f"{self.x0},{self.x1},{self.z0},{self.z1},{self.y0},{self.y1}"


@dataclass(frozen=True, slots=True)
class BuildRegion:
    build_type: int
    bounds: BlockRegion

    @classmethod
    def from_values(cls, values: tuple[int, int, int, int, int, int, int] | list[int]) -> "BuildRegion":
        if len(values) != 7:
            raise ValueError(f"expected 7 values, got {len(values)}")
        build_type, *bounds = values
        return cls(int(build_type), BlockRegion.from_values(bounds))

    def as_tuple(self) -> tuple[int, int, int, int, int, int, int]:
        return (self.build_type, *self.bounds.as_tuple())

    def to_env_value(self) -> str:
        return f"{self.build_type},{self.bounds.to_env_value()}"
