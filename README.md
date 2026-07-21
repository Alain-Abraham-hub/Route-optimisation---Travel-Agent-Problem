# Route and Delivery Optimisation with Google OR-Tools

This project solves a real-world-style delivery routing problem using
[Google OR-Tools](https://developers.google.com/optimization). It determines
which customers each vehicle should visit, the order in which they should be
visited, and the expected arrival time at every stop.

The current model is a **Capacitated Vehicle Routing Problem with Time Windows
(CVRPTW)**. Every customer must be visited exactly once while respecting:

- vehicle capacity;
- customer delivery time windows;
- travel time between locations;
- service time at each customer;
- vehicle departure from and return to the depot.

The optimization objective prioritizes using fewer vehicles and then reducing
the total route distance.

> OR-Tools uses heuristic and metaheuristic search for this problem. A longer
> search can improve a solution, but the returned solution is not necessarily a
> mathematically proven global optimum.

## Dataset

The project uses the **Solomon Vehicle Routing Problem with Time Windows
(VRPTW) benchmark dataset**. These are synthetic benchmark instances designed
for comparing route-optimization algorithms.

The repository contains 56 CSV files and six dataset families:

| Family | Customer distribution | Scheduling horizon | Standard vehicle capacity |
|---|---|---|---:|
| `C1` | Clustered | Shorter, tighter windows | 200 |
| `C2` | Clustered | Longer, wider windows | 700 |
| `R1` | Random | Shorter, tighter windows | 200 |
| `R2` | Random | Longer, wider windows | 1,000 |
| `RC1` | Mixed clustered and random | Shorter, tighter windows | 200 |
| `RC2` | Mixed clustered and random | Longer, wider windows | 1,000 |

Clustered customers are concentrated in geographic groups. Random customers
are scattered throughout the service area. RC instances combine both patterns.

### Selected instance: R101

The default model and EDA use:

```text
solomon_dataset/R1/R101.csv
```

`R101` was selected as the initial case because it provides a challenging
random customer distribution with tight delivery windows. It contains:

- 1 depot;
- 100 customers;
- total customer demand of 1,458 units;
- vehicle capacity of 200 units per vehicle;
- a default maximum fleet of 25 vehicles.

The first CSV row is treated as the depot. In `R101`, it has zero demand and
zero service time.

### CSV columns

| Column | Meaning |
|---|---|
| `CUST NO.` | Location identifier |
| `XCOORD.` | Synthetic X coordinate |
| `YCOORD.` | Synthetic Y coordinate |
| `DEMAND` | Quantity to deliver to the customer |
| `READY TIME` | Earliest permitted service-arrival time |
| `DUE DATE` | Latest permitted service-arrival time |
| `SERVICE TIME` | Time spent serving the location |

The coordinates are synthetic Cartesian coordinates, not latitude and
longitude. Consequently, the project uses Euclidean distance rather than a
road-network routing API.

Vehicle capacity is not stored in the CSV files. `model.py` infers the standard
capacity from the dataset family, or it can be supplied with
`--vehicle-capacity`.

> Data-quality note: `solomon_dataset/C1/C104.csv` contains a malformed numeric
> value at CSV row 38 (`READY TIME = "0.00    1"`). Correct or replace that value
> from the authoritative source before solving that instance.

## Project structure

```text
.
├── README.md
├── requirements.txt
├── distance_matrix.py
├── time_matrix.py
├── visualize.py
├── model.py
└── solomon_dataset/
    ├── C1/
    ├── C2/
    ├── R1/
    ├── R2/
    ├── RC1/
    └── RC2/
```

### `distance_matrix.py`

Loads the X and Y coordinates and calculates the Euclidean distance between
every pair of locations:

```text
distance(i, j) = √((xj − xi)² + (yj − yi)²)
```

OR-Tools requires integer costs, so distances are rounded to integers. The
result is a symmetric `N × N` matrix with zeros on the diagonal.

### `time_matrix.py`

Derives travel time from the already-calculated distance matrix:

```text
travel time = distance ÷ speed × time scale
```

For example, with a distance of 20 units, a speed of 40 units per hour, and a
time scale of 60 minutes per hour:

```text
travel time = 20 ÷ 40 × 60 = 30 minutes
```

Travel times are rounded upward to integer values for the OR-Tools time
dimension. The current Solomon model uses the benchmark convention of one
distance unit per time unit.

### `visualize.py`

Performs exploratory data analysis and generates a PNG dashboard containing:

- customer distribution plot;
- demand histogram;
- time-window-width histogram;
- service-time distribution;
- customer demand statistics;
- total demand;
- average demand;
- maximum demand.

The depot is shown as a red star. Customer point color and size represent
demand.

### `model.py`

Loads and validates the dataset, builds the OR-Tools CVRPTW model, runs the
solver, prints the routes, and optionally exports the solution as JSON.

## Mathematical model

Let:

- `V` be the set of the depot and customers;
- `K` be the available vehicles;
- `d(i,j)` be the distance from location `i` to location `j`;
- `q(i)` be customer demand;
- `Q` be capacity per vehicle;
- `[a(i), b(i)]` be the delivery time window;
- `s(i)` be service time;
- `t(i,j)` be travel time.

The routing decision determines whether a vehicle travels from `i` to `j`.
The model aims to minimize:

```text
fleet penalty × vehicles used + total route distance
```

subject to:

1. Every customer is visited exactly once.
2. Every used vehicle starts and ends at the depot.
3. The demand assigned to a vehicle does not exceed `Q`.
4. Arrival at customer `i` lies within `[a(i), b(i)]`.
5. Consecutive arrival times include service and travel time:

   ```text
   arrival(j) ≥ arrival(i) + service(i) + travel(i,j)
   ```

6. A vehicle may wait if it reaches a customer before the ready time.

The automatically calculated fleet penalty is larger than a conservative
upper bound on route distance. This makes reducing the number of used vehicles
the primary objective and distance the secondary objective.

## Pre-solve capacity validation

Before OR-Tools starts, the model checks:

```text
total customer demand ≤ number of vehicles × capacity per vehicle
```

The depot demand is excluded. For the default `R101` configuration:

```text
Customer demand = 1,458
Fleet capacity  = 25 × 200 = 5,000
```

This is a necessary but not sufficient feasibility check. Time windows and
customer combinations may require more vehicles than the capacity-only minimum.

## Installation

### 1. Open the project

```bash
cd "/Users/hebron/Documents/Route-optimisation---Travel-Agent-Problem"
```

### 2. Create the virtual environment

The environment used by this project is named `.routeoptimisation`:

```bash
python3 -m venv .routeoptimisation
```

### 3. Activate it

On macOS or Linux:

```bash
source .routeoptimisation/bin/activate
```

### 4. Install dependencies

```bash
python -m pip install -r requirements.txt
```

The direct dependencies are:

- `ortools` for optimization;
- `matplotlib` for EDA visualization.

### 5. Confirm the interpreter

```bash
which python
```

It should point to:

```text
.../Route-optimisation---Travel-Agent-Problem/.routeoptimisation/bin/python
```

## Usage

### Generate the EDA dashboard

The default command analyzes `R101.csv`:

```bash
python visualize.py
```

It creates:

```text
R101_eda.png
```

Analyze another instance:

```bash
python visualize.py solomon_dataset/C1/C101.csv
```

Choose an output path:

```bash
python visualize.py solomon_dataset/R1/R101.csv --output outputs/R101_eda.png
```

### Generate a distance matrix

Print the matrix:

```bash
python distance_matrix.py solomon_dataset/R1/R101.csv
```

Save it as JSON:

```bash
python distance_matrix.py solomon_dataset/R1/R101.csv \
  --output outputs/R101_distance_matrix.json
```

Use a scale of 100 to preserve two implied decimal places:

```bash
python distance_matrix.py solomon_dataset/R1/R101.csv \
  --scale 100 \
  --output outputs/R101_distance_matrix.json
```

### Generate a time matrix

With the default Solomon convention of one distance unit per time unit:

```bash
python time_matrix.py solomon_dataset/R1/R101.csv \
  --output outputs/R101_time_matrix.json
```

For 40 distance units per hour with output in minutes:

```bash
python time_matrix.py solomon_dataset/R1/R101.csv \
  --speed 40 \
  --time-scale 60 \
  --output outputs/R101_time_matrix.json
```

### Solve the default routing problem

```bash
python model.py
```

Defaults:

- dataset: `R101.csv`;
- available vehicles: 25;
- capacity per vehicle: 200;
- solver time limit: 30 seconds.

### Allow a longer optimization search

```bash
python model.py --time-limit 120
```

A longer search often finds a better route plan.

### Save the solution as JSON

```bash
python model.py --time-limit 120 --output outputs/R101_solution.json
```

### Solve another dataset

```bash
python model.py solomon_dataset/RC2/RC201.csv --time-limit 120
```

### Override fleet settings

```bash
python model.py solomon_dataset/R1/R101.csv \
  --vehicles 20 \
  --vehicle-capacity 200 \
  --time-limit 120
```

If the fleet is too small by total capacity, the model stops before starting
the solver and reports the demand, capacity, shortfall, and capacity-only
minimum number of vehicles.

## Solution output

Each stop is printed as:

```text
customer_id@arrival_time
```

Example route format:

```text
Vehicle 1: 1@0 -> 54@95 -> 1@110 | distance=8, load=14
```

This means the vehicle:

1. departs depot `1` at time `0`;
2. arrives at customer `54` at time `95`;
3. returns to depot `1` at time `110`;
4. travels 8 integer distance units;
5. carries 14 demand units.

The JSON output contains:

- number of vehicles used;
- total distance;
- total demand served;
- vehicle capacity;
- fleet penalty;
- OR-Tools objective value;
- individual vehicle routes;
- arrival time and cumulative load at every stop.

## Current assumptions

- The first row is the depot.
- Every vehicle starts and ends at the same depot.
- Every vehicle has the same capacity.
- Every customer must be served exactly once.
- Demand is delivered rather than picked up.
- Distance is symmetric Euclidean distance.
- Travel time is derived from distance.
- Traffic and travel speeds do not change during the day.
- Customer time windows constrain arrival/start-of-service time.
- Waiting before a time window opens is permitted.
- Vehicle breaks, driver shifts, road restrictions, and multiple depots are not
  currently modelled.

## Current limitations and possible extensions

The Solomon data is excellent for algorithm benchmarking but does not represent
real roads. A production delivery system could add:

- latitude and longitude input;
- road-network distance and duration matrices;
- live or historical traffic;
- heterogeneous vehicles and capacities;
- multiple depots;
- driver working hours and mandatory breaks;
- pickup-and-delivery pairs;
- vehicle operating and overtime costs;
- priority or optional customers;
- route-map visualization;
- a web API and operational dashboard;
- automated comparison of solutions across all 56 instances.

## Deactivate the environment

When finished:

```bash
deactivate
```
