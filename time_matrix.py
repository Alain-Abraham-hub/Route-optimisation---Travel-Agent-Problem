"""Build an integer travel-time matrix for routing problems."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Sequence

from distance_matrix import Coordinate, load_solomon_coordinates


def calculate_time_matrix(
    coordinates: Sequence[Coordinate],
    speed: float = 1.0,
    time_scale: float = 1.0,
) -> list[list[int]]:
    """Return a symmetric travel-time matrix.

    Coordinates and ``speed`` must use compatible units. For example, if the
    coordinates represent kilometres and speed is kilometres per hour, set
    ``time_scale=60`` to return travel times in minutes.

    Times are rounded up so a non-zero journey never becomes zero after integer
    conversion, which is important for OR-Tools dimensions.
    """
    if speed <= 0:
        raise ValueError("speed must be greater than zero")
    if time_scale <= 0:
        raise ValueError("time_scale must be greater than zero")

    points = [(float(x), float(y)) for x, y in coordinates]
    size = len(points)
    matrix = [[0] * size for _ in range(size)]

    for start in range(size):
        for end in range(start + 1, size):
            distance = math.dist(points[start], points[end])
            travel_time = math.ceil((distance / speed) * time_scale)
            matrix[start][end] = travel_time
            matrix[end][start] = travel_time

    return matrix


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Calculate a travel-time matrix from a Solomon CSV file."
    )
    parser.add_argument("csv_path", type=Path, help="Path to the input CSV file")
    parser.add_argument(
        "--speed",
        type=float,
        default=1.0,
        help="Travel speed in coordinate units per base time unit (default: 1)",
    )
    parser.add_argument(
        "--time-scale",
        type=float,
        default=1.0,
        help="Multiplier for output time units; use 60 for minutes (default: 1)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional JSON output path; otherwise prints to standard output",
    )
    args = parser.parse_args()

    coordinates = load_solomon_coordinates(args.csv_path)
    time_matrix = calculate_time_matrix(
        coordinates,
        speed=args.speed,
        time_scale=args.time_scale,
    )
    serialized = json.dumps(time_matrix, indent=2)

    if args.output:
        args.output.write_text(serialized + "\n", encoding="utf-8")
    else:
        print(serialized)


if __name__ == "__main__":
    main()
