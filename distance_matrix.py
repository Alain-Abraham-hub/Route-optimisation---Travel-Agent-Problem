"""Build an integer Euclidean distance matrix for routing problems."""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Sequence


Coordinate = tuple[float, float]


def calculate_distance_matrix(
    coordinates: Sequence[Coordinate], scale: float = 1.0
) -> list[list[int]]:
    """Return a symmetric Euclidean distance matrix for OR-Tools."""
    if scale <= 0:
        raise ValueError("scale must be greater than zero")

    points = [(float(x), float(y)) for x, y in coordinates]
    size = len(points)
    matrix = [[0] * size for _ in range(size)]

    for start in range(size):
        for end in range(start + 1, size):
            distance = round(math.dist(points[start], points[end]) * scale)
            matrix[start][end] = distance
            matrix[end][start] = distance

    return matrix


def load_solomon_coordinates(csv_path: str | Path) -> list[Coordinate]:
    """Load X/Y coordinates from a Solomon-format CSV file."""
    coordinates: list[Coordinate] = []

    with Path(csv_path).open(newline="", encoding="utf-8-sig") as csv_file:
        reader = csv.DictReader(csv_file)
        required_columns = {"XCOORD.", "YCOORD."}
        if reader.fieldnames is None or not required_columns.issubset(reader.fieldnames):
            raise ValueError("CSV must contain 'XCOORD.' and 'YCOORD.' columns")

        for row_number, row in enumerate(reader, start=2):
            try:
                coordinates.append((float(row["XCOORD."]), float(row["YCOORD."])))
            except (TypeError, ValueError) as error:
                raise ValueError(
                    f"Invalid coordinate in {csv_path} at row {row_number}"
                ) from error

    if not coordinates:
        raise ValueError(f"No coordinates found in {csv_path}")

    return coordinates


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Calculate a Euclidean distance matrix from a Solomon CSV file."
    )
    parser.add_argument("csv_path", type=Path, help="Path to the input CSV file")
    parser.add_argument(
        "--scale", type=float, default=1.0,
        help="Multiplier applied before rounding distances (default: 1)",
    )
    parser.add_argument(
        "--output", type=Path,
        help="Optional JSON output path; otherwise prints to standard output",
    )
    args = parser.parse_args()

    coordinates = load_solomon_coordinates(args.csv_path)
    distance_matrix = calculate_distance_matrix(coordinates, args.scale)
    serialized = json.dumps(distance_matrix, indent=2)

    if args.output:
        args.output.write_text(serialized + "\n", encoding="utf-8")
    else:
        print(serialized)


if __name__ == "__main__":
    main()
