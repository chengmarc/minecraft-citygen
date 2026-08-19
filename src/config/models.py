"""Typed config and domain models shared across pipeline stages."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


def _coerce_xyz_point(values: Iterable[int]) -> tuple[int, int, int]:
    values = tuple(values)
    if len(values) != 3:
        raise ValueError(f"expected 3 values, got {len(values)}")
    return tuple(int(value) for value in values)


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
    def from_xyz_pair(
        cls,
        start: tuple[int, int, int] | list[int],
        end: tuple[int, int, int] | list[int],
    ) -> "BlockRegion":
        x0, y0, z0 = _coerce_xyz_point(start)
        x1, y1, z1 = _coerce_xyz_point(end)
        return cls(x0, x1, z0, z1, y0, y1)

    @classmethod
    def from_values(cls, values) -> "BlockRegion":
        values = tuple(values)
        if len(values) == 6:
            return cls(*(int(value) for value in values))
        if len(values) == 2:
            return cls.from_xyz_pair(values[0], values[1])
        raise ValueError(f"expected 6 flat values or 2 xyz points, got {len(values)}")

    def as_tuple(self) -> tuple[tuple[int, int, int], tuple[int, int, int]]:
        return self.as_xyz_pair()

    def as_flat_tuple(self) -> tuple[int, int, int, int, int, int]:
        return self.x0, self.x1, self.z0, self.z1, self.y0, self.y1

    def as_xyz_pair(self) -> tuple[tuple[int, int, int], tuple[int, int, int]]:
        return (self.x0, self.y0, self.z0), (self.x1, self.y1, self.z1)

    def to_env_value(self) -> str:
        start, end = self.as_xyz_pair()
        return f"({start}, {end})"


@dataclass(frozen=True, slots=True)
class BuildRegion:
    build_type: int
    bounds: BlockRegion

    @classmethod
    def from_values(cls, values) -> "BuildRegion":
        values = tuple(values)
        if len(values) == 7:
            build_type, *bounds = values
            return cls(int(build_type), BlockRegion.from_values(bounds))
        if len(values) == 3:
            build_type, start, end = values
            return cls(int(build_type), BlockRegion.from_xyz_pair(start, end))
        if len(values) == 2:
            build_type, bounds = values
            return cls(int(build_type), BlockRegion.from_values(bounds))
        raise ValueError(f"expected build type plus bounds, got {len(values)} values")

    def as_tuple(self) -> tuple[int, tuple[int, int, int], tuple[int, int, int]]:
        start, end = self.bounds.as_xyz_pair()
        return self.build_type, start, end

    def as_flat_tuple(self) -> tuple[int, int, int, int, int, int, int]:
        return (self.build_type, *self.bounds.as_flat_tuple())

    def to_env_value(self) -> str:
        return f"{self.build_type}, {self.bounds.to_env_value()}"
