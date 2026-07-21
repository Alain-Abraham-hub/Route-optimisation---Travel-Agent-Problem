"""Build an integer travel-time matrix for routing problems."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Sequence

from distance_matrix import (
    Coordinate,
    calculate_distance_matrix,
    load_solomon_coordinates,
)


def calculate_time_matrix_from_distances(
    distance_matrix: Sequence[Sequence[int]],
    speed: float = 1.0,
    time_scale: float = 1.0,
) -> list[list[int]]:
    """Convert an integer distance matrix into an integer travel-time matrix."""
    if speed <= 0:
        raise ValueError("speed must be greater than zero")
    if time_scale <= 0:
        raise ValueError("time_scale must be greater than zero")

    size = len(distance_matrix)
    if any(len(row) != size for row in distance_matrix):
        raise ValueError("distance_matrix must be square")

    return [
        [math.ceil((distance / speed) * time_scale) for distance in row]
        for row in distance_matrix
    ]


def calculate_time_matrix(
    coordinates: Sequence[Coordinate],
    speed: float = 1.0,
    time_scale: float = 1.0,
) -> list[list[int]]:
    """Derive a symmetric travel-time matrix from the distance matrix.

    Coordinates and ``speed`` must use compatible units. For example, if the
    coordinates represent kilometres and speed is kilometres per hour, set
    ``time_scale=60`` to return travel times in minutes.

    The Euclidean distance matrix is calculated first by ``distance_matrix.py``.
    Each stored distance is then divided by speed and converted to the requested
    time unit. Times are rounded up for use in OR-Tools dimensions.
    """
    distance_matrix = calculate_distance_matrix(coordinates)
    return calculate_time_matrix_from_distances(
        distance_matrix,
        speed=speed,
        time_scale=time_scale,
    )


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
