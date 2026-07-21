"""Solve Solomon datasets as capacitated VRPs with delivery time windows."""

from __future__ import annotations

import argparse
import csv
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from ortools.constraint_solver import pywrapcp, routing_enums_pb2

from distance_matrix import calculate_distance_matrix
from time_matrix import calculate_time_matrix_from_distances


@dataclass(frozen=True)
class ProblemData:
    customer_ids: list[int]
    coordinates: list[tuple[float, float]]
    demands: list[int]
    time_windows: list[tuple[int, int]]
    service_times: list[int]


def load_problem(csv_path: str | Path) -> ProblemData:
    """Load and validate one Solomon-format CSV instance."""
    required = {
        "CUST NO.", "XCOORD.", "YCOORD.", "DEMAND",
        "READY TIME", "DUE DATE", "SERVICE TIME",
    }
    rows: list[dict[str, float]] = []

    with Path(csv_path).open(newline="", encoding="utf-8-sig") as csv_file:
        reader = csv.DictReader(csv_file)
        if reader.fieldnames is None or not required.issubset(reader.fieldnames):
            raise ValueError(f"CSV must contain: {', '.join(sorted(required))}")

        for row_number, row in enumerate(reader, start=2):
            try:
                rows.append({column: float(row[column]) for column in required})
            except (TypeError, ValueError) as error:
                raise ValueError(
                    f"Invalid numeric value in {csv_path} at row {row_number}: {row}"
                ) from error

    if len(rows) < 2:
        raise ValueError("The dataset must contain a depot and at least one customer")

    time_windows = [
        (round(row["READY TIME"]), round(row["DUE DATE"])) for row in rows
    ]
    for index, (ready, due) in enumerate(time_windows):
        if ready > due:
            raise ValueError(f"Ready time exceeds due date at dataset row {index + 1}")

    return ProblemData(
        customer_ids=[round(row["CUST NO."]) for row in rows],
        coordinates=[(row["XCOORD."], row["YCOORD."]) for row in rows],
        demands=[round(row["DEMAND"]) for row in rows],
        time_windows=time_windows,
        service_times=[round(row["SERVICE TIME"]) for row in rows],
    )


def infer_vehicle_capacity(csv_path: str | Path) -> int:
    """Return the standard capacity for a Solomon benchmark family."""
    name = Path(csv_path).stem.upper()
    if name.startswith("C1") or name.startswith("R1") or name.startswith("RC1"):
        return 200
    if name.startswith("C2"):
        return 700
    if name.startswith("R2") or name.startswith("RC2"):
        return 1000
    raise ValueError("Could not infer capacity; provide --vehicle-capacity")


def check_fleet_capacity(
    demands: Sequence[int], number_of_vehicles: int, vehicle_capacity: int
) -> tuple[int, int]:
    """Check whether total fleet capacity can carry all customer demand.

    The first demand belongs to the depot and is excluded. This is a necessary
    feasibility check; routing and time-window constraints may still make an
    instance infeasible even when total fleet capacity is sufficient.
    """
    if number_of_vehicles <= 0:
        raise ValueError("number_of_vehicles must be greater than zero")
    if vehicle_capacity <= 0:
        raise ValueError("vehicle_capacity must be greater than zero")
    if not demands:
        raise ValueError("demands must include at least the depot")
    if any(demand < 0 for demand in demands):
        raise ValueError("demands cannot be negative")

    total_customer_demand = sum(demands[1:])
    total_fleet_capacity = number_of_vehicles * vehicle_capacity
    if total_customer_demand > total_fleet_capacity:
        shortfall = total_customer_demand - total_fleet_capacity
        minimum_vehicles = math.ceil(total_customer_demand / vehicle_capacity)
        raise ValueError(
            "Insufficient fleet capacity: "
            f"customer demand={total_customer_demand}, "
            f"fleet capacity={total_fleet_capacity}, shortfall={shortfall}. "
            f"At least {minimum_vehicles} vehicles are required by capacity alone."
        )

    return total_customer_demand, total_fleet_capacity


def solve(
    data: ProblemData,
    number_of_vehicles: int,
    vehicle_capacity: int,
    time_limit_seconds: int = 30,
    fleet_penalty: int | None = None,
) -> dict[str, object] | None:
    """Solve a CVRPTW, minimizing used vehicles first and distance second."""
    if number_of_vehicles <= 0 or vehicle_capacity <= 0:
        raise ValueError("Vehicle count and capacity must be greater than zero")

    check_fleet_capacity(data.demands, number_of_vehicles, vehicle_capacity)
    distance_matrix = calculate_distance_matrix(data.coordinates)
    time_matrix = calculate_time_matrix_from_distances(distance_matrix)
    manager = pywrapcp.RoutingIndexManager(len(data.coordinates), number_of_vehicles, 0)
    routing = pywrapcp.RoutingModel(manager)

    def distance_callback(from_index: int, to_index: int) -> int:
        return distance_matrix[manager.IndexToNode(from_index)][manager.IndexToNode(to_index)]

    distance_callback_index = routing.RegisterTransitCallback(distance_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(distance_callback_index)

    def demand_callback(from_index: int) -> int:
        return data.demands[manager.IndexToNode(from_index)]

    demand_callback_index = routing.RegisterUnaryTransitCallback(demand_callback)
    routing.AddDimensionWithVehicleCapacity(
        demand_callback_index,
        0,
        [vehicle_capacity] * number_of_vehicles,
        True,
        "Capacity",
    )

    def time_callback(from_index: int, to_index: int) -> int:
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        return data.service_times[from_node] + time_matrix[from_node][to_node]

    time_callback_index = routing.RegisterTransitCallback(time_callback)
    depot_ready, depot_due = data.time_windows[0]
    max_waiting_time = max(due - ready for ready, due in data.time_windows)
    routing.AddDimension(
        time_callback_index,
        max_waiting_time,
        depot_due,
        False,
        "Time",
    )
    time_dimension = routing.GetDimensionOrDie("Time")

    for node, (ready, due) in enumerate(data.time_windows[1:], start=1):
        index = manager.NodeToIndex(node)
        time_dimension.CumulVar(index).SetRange(ready, due)

    for vehicle in range(number_of_vehicles):
        start = routing.Start(vehicle)
        end = routing.End(vehicle)
        time_dimension.CumulVar(start).SetRange(depot_ready, depot_due)
        time_dimension.CumulVar(end).SetRange(depot_ready, depot_due)
        routing.AddVariableMinimizedByFinalizer(time_dimension.CumulVar(start))
        routing.AddVariableMinimizedByFinalizer(time_dimension.CumulVar(end))

    if fleet_penalty is None:
        maximum_arc = max(max(row) for row in distance_matrix)
        fleet_penalty = maximum_arc * (len(data.coordinates) + number_of_vehicles + 1) + 1
    routing.SetFixedCostOfAllVehicles(fleet_penalty)

    search = pywrapcp.DefaultRoutingSearchParameters()
    search.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PARALLEL_CHEAPEST_INSERTION
    search.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    search.time_limit.FromSeconds(time_limit_seconds)
    search.log_search = False

    solution = routing.SolveWithParameters(search)
    if solution is None:
        return None

    routes: list[dict[str, object]] = []
    total_distance = 0
    total_load = 0

    for vehicle in range(number_of_vehicles):
        index = routing.Start(vehicle)
        if routing.IsEnd(solution.Value(routing.NextVar(index))):
            continue

        stops: list[dict[str, int]] = []
        route_distance = 0
        route_load = 0

        while not routing.IsEnd(index):
            node = manager.IndexToNode(index)
            arrival = solution.Value(time_dimension.CumulVar(index))
            route_load += data.demands[node]
            stops.append(
                {
                    "customer_id": data.customer_ids[node],
                    "arrival_time": arrival,
                    "load_after_stop": route_load,
                }
            )
            next_index = solution.Value(routing.NextVar(index))
            next_node = manager.IndexToNode(next_index)
            route_distance += distance_matrix[node][next_node]
            index = next_index

        stops.append(
            {
                "customer_id": data.customer_ids[0],
                "arrival_time": solution.Value(time_dimension.CumulVar(index)),
                "load_after_stop": route_load,
            }
        )
        total_distance += route_distance
        total_load += route_load
        routes.append(
            {
                "vehicle": vehicle + 1,
                "distance": route_distance,
                "load": route_load,
                "stops": stops,
            }
        )

    return {
        "vehicles_used": len(routes),
        "total_distance": total_distance,
        "total_demand_served": total_load,
        "vehicle_capacity": vehicle_capacity,
        "fleet_penalty": fleet_penalty,
        "objective_value": solution.ObjectiveValue(),
        "routes": routes,
    }


def print_solution(result: dict[str, object]) -> None:
    """Print a concise human-readable route plan."""
    print(f"Vehicles used: {result['vehicles_used']}")
    print(f"Total distance: {result['total_distance']}")
    print(f"Total demand served: {result['total_demand_served']}")
    for route in result["routes"]:  # type: ignore[union-attr]
        stop_text = " -> ".join(
            f"{stop['customer_id']}@{stop['arrival_time']}"
            for stop in route["stops"]
        )
        print(
            f"Vehicle {route['vehicle']}: {stop_text} | "
            f"distance={route['distance']}, load={route['load']}"
        )


def main() -> None:
    project_directory = Path(__file__).resolve().parent
    default_csv = project_directory / "solomon_dataset" / "R1" / "R101.csv"
    parser = argparse.ArgumentParser(description="Solve a Solomon CVRPTW with OR-Tools")
    parser.add_argument("csv_path", nargs="?", type=Path, default=default_csv)
    parser.add_argument("--vehicles", type=int, default=25)
    parser.add_argument("--vehicle-capacity", type=int)
    parser.add_argument("--time-limit", type=int, default=30)
    parser.add_argument(
        "--fleet-penalty",
        type=int,
        help="Cost per used vehicle; default makes fleet size the primary objective",
    )
    parser.add_argument("--output", type=Path, help="Optional solution JSON path")
    args = parser.parse_args()

    capacity = args.vehicle_capacity or infer_vehicle_capacity(args.csv_path)
    problem = load_problem(args.csv_path)
    try:
        total_demand, fleet_capacity = check_fleet_capacity(
            problem.demands, args.vehicles, capacity
        )
    except ValueError as error:
        raise SystemExit(f"Capacity check failed: {error}") from error
    print(
        f"Capacity check passed: customer demand={total_demand}, "
        f"fleet capacity={fleet_capacity}"
    )
    result = solve(
        problem,
        number_of_vehicles=args.vehicles,
        vehicle_capacity=capacity,
        time_limit_seconds=args.time_limit,
        fleet_penalty=args.fleet_penalty,
    )
    if result is None:
        raise SystemExit("No feasible solution found. Check fleet, capacity, and time windows.")

    print_solution(result)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print(f"Solution saved to: {args.output}")


if __name__ == "__main__":
    main()
