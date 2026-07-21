"""Generate an EDA dashboard for a Solomon routing dataset."""

from __future__ import annotations

import argparse
import csv
import statistics
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


REQUIRED_COLUMNS = (
    "CUST NO.",
    "XCOORD.",
    "YCOORD.",
    "DEMAND",
    "READY TIME",
    "DUE DATE",
    "SERVICE TIME",
)


def load_dataset(csv_path: Path) -> list[dict[str, float]]:
    """Load and validate a Solomon-format CSV file."""
    records: list[dict[str, float]] = []

    with csv_path.open(newline="", encoding="utf-8-sig") as csv_file:
        reader = csv.DictReader(csv_file)
        if reader.fieldnames is None or not set(REQUIRED_COLUMNS).issubset(
            reader.fieldnames
        ):
            raise ValueError(
                f"CSV must contain these columns: {', '.join(REQUIRED_COLUMNS)}"
            )

        for row_number, row in enumerate(reader, start=2):
            try:
                records.append(
                    {column: float(row[column]) for column in REQUIRED_COLUMNS}
                )
            except (TypeError, ValueError) as error:
                raise ValueError(
                    f"Invalid numeric value at CSV row {row_number}: {row}"
                ) from error

    if len(records) < 2:
        raise ValueError("The dataset must contain a depot and at least one customer")
    return records


def generate_dashboard(
    records: list[dict[str, float]], dataset_name: str, output_path: Path
) -> None:
    """Create four EDA plots and a customer-demand statistics panel."""
    depot = records[0]
    customers = records[1:]

    x_coordinates = [row["XCOORD."] for row in customers]
    y_coordinates = [row["YCOORD."] for row in customers]
    demands = [row["DEMAND"] for row in customers]
    time_windows = [
        row["DUE DATE"] - row["READY TIME"] for row in customers
    ]
    service_times = [row["SERVICE TIME"] for row in customers]

    total_demand = sum(demands)
    average_demand = statistics.mean(demands)
    maximum_demand = max(demands)

    print("Customer demand statistics")
    print(f"Total demand:   {total_demand:.0f}")
    print(f"Average demand: {average_demand:.2f}")
    print(f"Maximum demand: {maximum_demand:.0f}")

    figure, axes = plt.subplots(2, 3, figsize=(17, 10), constrained_layout=True)
    figure.suptitle(
        f"Route and Delivery Dataset EDA — {dataset_name}",
        fontsize=17,
        fontweight="bold",
    )

    location_plot = axes[0, 0].scatter(
        x_coordinates,
        y_coordinates,
        c=demands,
        s=[30 + demand * 2 for demand in demands],
        cmap="viridis",
        alpha=0.8,
        edgecolors="white",
        linewidths=0.4,
    )
    axes[0, 0].scatter(
        depot["XCOORD."],
        depot["YCOORD."],
        marker="*",
        s=280,
        color="red",
        edgecolors="black",
        label="Depot",
        zorder=3,
    )
    axes[0, 0].set(
        title="Customer distribution",
        xlabel="X coordinate",
        ylabel="Y coordinate",
    )
    axes[0, 0].legend()
    figure.colorbar(location_plot, ax=axes[0, 0], label="Demand")

    axes[0, 1].hist(demands, bins=12, color="#3b82f6", edgecolor="white")
    axes[0, 1].axvline(
        average_demand, color="red", linestyle="--", label="Average"
    )
    axes[0, 1].set(
        title="Demand histogram", xlabel="Customer demand", ylabel="Customers"
    )
    axes[0, 1].legend()

    axes[0, 2].hist(
        time_windows, bins=12, color="#10b981", edgecolor="white"
    )
    axes[0, 2].set(
        title="Time-window histogram",
        xlabel="Due date − ready time",
        ylabel="Customers",
    )

    service_bins = min(12, max(1, len(set(service_times))))
    axes[1, 0].hist(
        service_times,
        bins=service_bins,
        color="#f59e0b",
        edgecolor="white",
    )
    axes[1, 0].set(
        title="Service-time distribution",
        xlabel="Service time",
        ylabel="Customers",
    )

    axes[1, 1].axis("off")
    axes[1, 1].set_title("Customer demand statistics", pad=18)
    statistics_text = (
        f"Total demand\n{total_demand:,.0f}\n\n"
        f"Average demand\n{average_demand:,.2f}\n\n"
        f"Maximum demand\n{maximum_demand:,.0f}"
    )
    axes[1, 1].text(
        0.5,
        0.5,
        statistics_text,
        ha="center",
        va="center",
        fontsize=16,
        bbox={"boxstyle": "round,pad=1", "facecolor": "#eff6ff", "edgecolor": "#3b82f6"},
    )

    axes[1, 2].axis("off")
    axes[1, 2].text(
        0.5,
        0.5,
        f"Customers\n{len(customers)}\n\nDepot\n1",
        ha="center",
        va="center",
        fontsize=16,
        bbox={"boxstyle": "round,pad=1", "facecolor": "#f0fdf4", "edgecolor": "#10b981"},
    )

    for axis in (axes[0, 0], axes[0, 1], axes[0, 2], axes[1, 0]):
        axis.grid(alpha=0.2)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output_path, dpi=180, bbox_inches="tight")
    plt.close(figure)
    print(f"EDA dashboard saved to: {output_path}")


def main() -> None:
    project_directory = Path(__file__).resolve().parent
    default_csv_path = project_directory / "solomon_dataset" / "R1" / "R101.csv"

    parser = argparse.ArgumentParser(
        description="Generate plots and demand statistics for a Solomon CSV dataset."
    )
    parser.add_argument(
        "csv_path",
        type=Path,
        nargs="?",
        default=default_csv_path,
        help="Path to a Solomon CSV file (default: solomon_dataset/R1/R101.csv)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="PNG output path (default: <CSV name>_eda.png)",
    )
    args = parser.parse_args()

    records = load_dataset(args.csv_path)
    output_path = args.output or Path(f"{args.csv_path.stem}_eda.png")
    generate_dashboard(records, args.csv_path.stem, output_path)


if __name__ == "__main__":
    main()
