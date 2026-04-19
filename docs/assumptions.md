# CellRoute: Heuristic & Modeling Assumptions

This document outlines the core mathematical models and heuristic assumptions driving the CellRoute engine. Understanding these design choices is crucial for evaluating the connectivity scoring algorithm.

## 1. Signal Propagation & Decay Model

We utilize a simplified Log-Distance Path Loss model to estimate Received Signal Received Power (RSRP) at any given coordinate, based on the distance to the nearest cell tower.

The standard formula is:
`RSRP = P_tx - 20 * log10(d) - 32.4 - 20 * log10(f)`

Where:
*   `P_tx`: Transmitter power (assumed average values based on tower tier).
*   `d`: Distance from the user equipment to the tower (in km).
*   `f`: Frequency of the band (in MHz).

**Simplification for Prototype:**
Given the processing constraints of real-time route evaluation, we approximate the path loss with an exponential decay function clamped between `[0, 1]` for normalization:

`Signal_Quality = max(0, 1 - (d / D_max)^2)`

*   `d`: Euclidean distance (calculated via Haversine) to nearest tower.
*   `D_max`: Maximum effective range of a cell (e.g., 2km for urban LTE).

## 2. Tower Weighting by Radio Type

Not all towers provide the same bandwidth or reliability. We tier towers found in the OpenCelliD dataset and apply a multiplier to the base signal quality.

| Radio Mode | Weight Modifier | Justification |
| :--- | :--- | :--- |
| **5G/NR** | `1.5` | Highest throughput, ultra-low latency. |
| **LTE (4G)** | `1.0` | Baseline standard for reliable mobility data. |
| **UMTS (3G)**| `0.4` | Sufficient for telemetry, poor for high-bandwidth apps. |
| **GSM (2G)** | `0.1` | Emergency fallback only (dead zone equivalent for modern data). |

## 3. OOKLA Speed Index Normalization

To incorporate historical bandwidth, OOKLA Quadbin tiles (600m² resolution) are normalized into a `[0, 1]` index.

`Speed_Index = log_clip(Median_Download_Speed) / Max_Expected_Speed`

*   `log_clip`: A squashing function since download speeds have a heavy-tailed distribution, preventing one extremely fast tile from skewing the entire route score.

## 4. The Composite Objective Function (Alpha Ranker)

The core differentiator of CellRoute is allowing the user to seamlessly trade off travel time (ETA) against connection stability.

For a Candidate Route $R$, the final score is:

`Score(R) = \alpha * Normalized_Connectivity(R) + (1 - \alpha) * Normalized_Efficiency(R)`

*   $\alpha \in [0, 1]$: The user-controlled slider value.
    *   $\alpha = 0$: Standard shortest-time routing (OSRM default).
    *   $\alpha = 1$: Maximum connectivity routing, regardless of time taken.
*   `Normalized_Connectivity(R)`: The average segment quality across the route, **heavily penalized by an exponential decay factor for any segments dropping below the minimum acceptable threshold** (e.g., -110 dBm equivalent). This ensures a route with consistent average coverage will heavily outrank a route with excellent coverage but severe dead zones, as dropped packets are catastrophic to autonomous telemetry.
*   `Normalized_Efficiency(R)`: `Min_ETA_all_routes / ETA(R)`

## 5. Segment Discretization & Density

Routes evaluated by the Dijkstra algorithm are composed of edges from the OSM road network graph. Each segment is evaluated independently by cross-referencing cell tower density within a 2km bounding area. 

This approach powers the unique "Segment Strip" visualization (Green/Orange/Red), providing granular visibility into precisely *where* the signal drops, and serves as our basis for applying isolated severe penalties without discarding an entire route indiscriminately.

## 6. Scalability & System Architecture Constraints

The system design effortlessly scales to any global city by modifying the geographic `BBOX` constant and `graph_from_place` tag.

*   **Offline Graph Compilation:** By pivoting to a local precomputed GeoPandas parquet graph rather than real-time PostGIS parsing, read-time latency is practically eliminated.
*   **Vectorized Scoring:** `scorer.py` utilizes SciPy's `cKDTree`. Fast O(log n) nearest neighbor search allows it to process the entire global OpenCelliD dataset (~40M towers) without any code modifications.
*   **Parquet Persistence:** OOKLA tiles are naturally distributed globally via quadkeys and natively loaded using fast, compressed parquet reads.
*   **Parallel Execution:** The current segment scoring bottleneck in Python can be trivially parallelized using `multiprocessing.Pool` if mapping thousands of square miles simultaneously.
