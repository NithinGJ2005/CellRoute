# CellRoute v2.0 — Project Status & Architecture Summary

## 📅 Project Status: SUBMISSION-READY (v2.0 — Feature-Complete)

**CellRoute** is a fully operational, 16-feature cellular-aware routing engine for the MAHE-Harman AI in Mobility 2026 hackathon. All four data sources are integrated, the 16-feature scoring engine is live, and the frontend includes 5G slice control, a connectivity heatmap, and closed-loop self-healing network assurance.

**Last major update:** 2026-04-18 — Feature Merge (HarmanLink best-of analysis)

---

## 🏗️ Technical Architecture (v2.0)

### Module 1 — Data Ingestion Layer (`backend/data/`)

| Script | Purpose | Output |
|---|---|---|
| `ingest_roads.py` | OSM road network (Bangalore bbox) | `scored_segments_blr.parquet` |
| `ingest_towers.py` | OSM cell tower positions, radio type, confidence | `towers_blr.parquet` |
| `ingest_ookla.py` | Ookla Speedtest Open Data tiles | `ookla_blr.parquet` |
| `ingest_traffic.py` | OpenTrafficData congestion intersections | `congestion_nodes.json` |

- All data stored in **Parquet / JSON** binary format for sub-millisecond I/O.
- All 4 sources are **real open datasets** — no synthetic data used in routing.

### Module 2 — Scoring Engine (`backend/router/`)

#### `scorer.py` — Offline Precompute (runs once)
- Uses **SciPy cKDTree** for spatial nearest-neighbour analysis.
- Assigns a base `conn_score` (RSRP physics + Ookla) to every road segment edge.
- Output is directly embedded in the NetworkX graph as edge attributes.

#### `waypoint_scorer.py` — Online Query-Time (NEW — v2.0)
16-feature real-time scorer for individual GPS waypoints:

| Feature | Description | Source |
|---|---|---|
| **F1** Tower Density | `log10(count+1) × 20` | OSM towers |
| **F2** Signal Quality | RSRP physics, ITU-R path loss model | tower distance |
| **F3** Radio Generation | NR/LTE/UMTS/GSM weight (18→2) | OSM radio field |
| **F4** Operator Diversity | Multi-MNO coverage proxy | OSM confidence |
| **F5** Time-of-Day *(×)* | TRAI IST peak/off-peak 0.68×–1.15× | TRAI 2023 |
| **F6** Data Reliability | OSM tower confidence 0–1 | OSM confidence |
| **F7** Measured Throughput | Ookla download speed tile (Mbps) | Ookla Open Data |
| **F8** Traffic Congestion | Congestion node proximity inverse | OpenTrafficData |
| **F9** Handoff Stability | Fewest dominant-cell changes per route | 3GPP TS 36.331 |
| **F10** eCall Reliability | EU Reg 2015/758 RSRP threshold tier | Critical for Harman TCU |
| **F11** 5G Network Slicing | URSP eMBB/URLLC/default policy | 3GPP TS 24.526 |
| **F12** Tower Load Sim | Peak-hour density penalty | time × density proxy |
| **F14** Weather / Monsoon | Rain attenuation −8 pts toggle | ITU-R P.838 |
| **F15** Predictive Forecast | Lookahead congestion at t+ETA | TRAI time model |
| **F16** Ultra-Low Latency | V2X safety <25ms Ookla latency bonus | 3GPP TS 22.186 |

**Formula:**
```
raw  = F1+F2+F3+F4+F6+F7+F8+F10+F11+F12+F14+F15+F16
score = clamp(raw × F5, 5, 100)
```
F9 is a route-level bonus applied on top of the per-waypoint aggregate.

#### `local_router.py` — Dijkstra Routing Engine
- **NetworkX MultiDiGraph** over the full Bangalore OSM road network.
- **Multi-objective cost function:**
  ```
  Cost = α × SignalPenalty + (1−α) × NormalisedETA
  ```
- **Closed-loop assurance integration:** `OutageManager` injects exponential cost penalties (`base × (1 + 49 × penalty²)`) onto road segments inside outage zones, causing Dijkstra to naturally avoid dead zones.
- Returns 3 distinct routes (primary + fastest + max-connectivity).
- Response time: **~40ms** across full Bangalore graph.

#### `outage_manager.py` — Closed-Loop Network Assurance
- In-memory outage registry (`_outages` dict).
- `register_outage(id, lat, lon, radius_m)` — marks a geographic area as KPI-breached.
- `get_outage_penalty(lat, lon)` — called by router per edge; returns 0–1 penalty with soft distance falloff.
- `clear_all_outages()` — recovery action.

### Module 3 — API & Serving (`backend/main.py`)

#### Endpoints (v2.0)

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Glassmorphic frontend map UI |
| `GET` | `/api/route` | Dijkstra 3-route set + 16-feature route enrichment |
| `GET` | `/api/explain` | Full F1–F16 breakdown for a GPS point (judge demo) |
| `GET` | `/heatmap` | Connectivity score grid over any Bangalore bbox |
| `GET` | `/api/health` | Server status + 4 source counts + live time-of-day factor |
| `GET` | `/api/sources` | Quick data source verification for judges |
| `GET` | `/api/towers` | OSM tower coordinates for map overlay |
| `POST` | `/api/outage` | Simulate tower KPI breach (closed-loop assurance) |
| `GET` | `/api/outages` | List active outages |
| `POST` | `/api/outage/clear-all` | Recovery — remove all outages |

**New query params on `/api/route`:**
- `slice=embb|urllc|default` — 5G URSP network slice selection
- `weather=clear|rain` — monsoon penalty (F14) toggle

### Module 4 — Premium Frontend (`frontend/`)

**Map:** CartoDB Dark Matter tile layer on Leaflet.js  
**Layout:** Glassmorphic HUD panel (fixed viewport height, internal scroll — v2.0 fixed)

#### Controls
| Control | Feature |
|---|---|
| **Alpha Slider** | ETA ↔ Connectivity trade-off (re-routes on change) |
| **5G Edge Optimized** | Prioritises towers with edge UPF nodes |
| **5G Network Slice** | Three-button selector: Default / eMBB / URLLC (V2X) |
| **📡 Signal Heatmap** | Toggle colored grid overlay (score per 2.2 km cell) |
| **🌧 Monsoon Penalty** | Toggles F14 rain attenuation on all routes |
| **⚡ Simulate Outage** | Closes the assurance loop — places dead zone, re-routes |
| **✓ Recover** | Clears outage, re-routes back to optimal path |

#### Route Cards (v2.0 enriched)
Each route card shows:
- Duration, distance, signal %
- **eCall badge** (✓ reliable / ⚠ marginal / ✕ dead zone)
- **Handoff count** (F9)
- **Slice badge** (eMBB / URLLC when selected)
- **Segment strip** — per-segment color road visualization

#### Special Visualizations
- **Per-segment polyline coloring** — each road segment colored by its `conn_score` (green/amber/red)
- **Last-mile handoff** — dotted walking line from road end to destination pin
- **Outage dead zone** — pulsing red ripple circle with ⚠ marker
- **Heatmap grid** — colored `L.rectangle` tiles, right-click any cell for `/api/explain` popup
- **Live Device Feed** — Network Information API showing real device `effectiveType` + downlink

---

## 🚀 Launch Instructions

```powershell
# 1. Install dependencies
pip install -r backend/requirements.txt

# 2. Start backend (serves frontend too)
cd backend
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# 3. Open browser
# http://localhost:8000
```

### Demo Flow (for judges)
1. Click **Load Blr Demo** → Marathahalli → Malleswaram routes appear
2. Switch slice to **URLLC (V2X)** → route scores update, eCall badges appear
3. Enable **📡 Signal Heatmap** → colored coverage grid overlaid
4. Enable **🌧 Monsoon Penalty** → scores drop, routing adjusts
5. Click **⚡ Simulate Outage** → alarm fires, vehicle re-routes around dead zone
6. Click **✓ Recover** → network healed, optimal route restored
7. Hit `/api/explain?lat=12.9716&lon=77.5946&slice=urllc` in browser → full 16-feature rationale

---

## ✅ Feature Checklist

### Routing Engine
- [x] NetworkX Dijkstra on real OSM road graph
- [x] 3 route alternatives per request
- [x] Click-anywhere origin/destination
- [x] Alpha trade-off slider (ETA ↔ Connectivity)
- [x] 5G Edge UPF preference toggle

### 16-Feature Scoring
- [x] F1 — Tower Density (log-scaled)
- [x] F2 — Signal Quality (RSRP physics, ITU-R)
- [x] F3 — Radio Generation (NR/LTE/UMTS/GSM)
- [x] F4 — Operator Diversity
- [x] F5 — Time-of-Day multiplicative (TRAI IST)
- [x] F6 — Data Reliability (OSM confidence)
- [x] F7 — Measured Throughput (Ookla)
- [x] F8 — Traffic Congestion (OpenTrafficData)
- [x] F9 — Handoff Stability (route-level, 3GPP TS 36.331)
- [x] F10 — eCall Reliability (EU Reg 2015/758)
- [x] F11 — 5G Network Slicing (URSP, 3GPP TS 24.526)
- [x] F12 — Tower Load Simulation
- [x] F14 — Weather / Monsoon Penalty (ITU-R P.838)
- [x] F15 — Predictive Forecasting
- [x] F16 — Ultra-Low Latency / V2X Bonus (3GPP TS 22.186)

### Network Assurance
- [x] Tower outage simulation (POST /api/outage)
- [x] Exponential Dijkstra cost penalty for dead zones
- [x] Automatic re-routing on outage trigger
- [x] Pulsing dead zone visualization
- [x] One-click recovery (clear-all + re-route)
- [x] Nokia Assurance Center alarm banner

### Frontend
- [x] Glassmorphic HUD panel (fixed height, internal scroll — fixed v2.0)
- [x] Per-segment polyline coloring
- [x] Connectivity heatmap grid overlay
- [x] Right-click cell → /api/explain popup
- [x] 5G slice selector (Default / eMBB / URLLC)
- [x] Monsoon weather toggle
- [x] eCall badge on route cards
- [x] Handoff count on route cards
- [x] Last-mile handoff dotted line
- [x] Live device network feed (Network Information API)

### Judges / Documentation
- [x] `GET /api/explain` — full heuristic rationale per GPS point
- [x] `GET /api/health` — live status, source counts, time-of-day factor
- [x] `GET /api/sources` — data source verification
- [x] `docs/heuristics.md` — 16-feature technical reference with 3GPP/ITU-R citations
- [x] `docs/JUDGES_PITCH_GUIDE.md` — presentation strategy
- [x] `docs/assumptions.md` — data assumptions

---

## 📚 Documentation Index

| Document | Purpose |
|---|---|
| `docs/PROJECT_STATUS.md` | This file — architecture & checklist |
| `docs/heuristics.md` | 16-feature scoring reference with 3GPP/ITU-R citations |
| `docs/JUDGES_PITCH_GUIDE.md` | Judging criteria mapping and pitch strategy |
| `docs/assumptions.md` | Data source assumptions and limitations |

---

*CellRoute Team | MAHE-Harman AI in Mobility Challenge 2026*
