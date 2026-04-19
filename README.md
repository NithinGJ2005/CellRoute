# CellRoute 🛜
### *Cellular-Aware Intelligent Routing for L4 Autonomous Vehicles*

> **MAHE-Harman AI in Mobility Challenge 2026**

---

## 🚗 What is CellRoute?

CellRoute is a **cellular-aware multi-objective routing engine** for L4 autonomous vehicles. It goes beyond traditional GPS navigation by incorporating **real-time 5G/4G network intelligence** directly into the route optimization heuristic.

Every route decision is evaluated across **16 connectivity features** — including cell tower density, signal quality, Ookla throughput scores, monsoon degradation, predictive handoff modeling, and 5G network slice compatibility — producing a trajectory that guarantees the vehicle stays connected even in dense urban environments like Bangalore.

---

## ✨ Key Features

| Feature | Description |
|---|---|
| **16-Feature Heuristic** | Multi-objective scoring (ETA vs. Signal Quality via lambda λ) |
| **5G Edge-Optimized Routing** | Routes via towers with Mobile Edge Computing (UPF) nodes |
| **Network Slice Awareness** | URSP-aware routing for eMBB (streaming) & URLLC (V2X) |
| **ISP-Specific Modes** | Jio/Airtel/BSNL network-aware path filtering |
| **Monsoon Penalty (F14)** | Signal degradation model for rain-impacted coverage |
| **Closed-Loop Assurance** | Self-healing demo: simulates outage → autonomous re-route |
| **Live Cell Tower Overlay** | Real tower data (NR/LTE) rendered on map |
| **Signal Heatmap** | Real-time explainability heatmap with eCall conformance |
| **L4 Cockpit Entry** | Cinematic dashboard entry via infotainment system |

---

## 🏗️ Architecture

```
cellroute/
├── backend/               # FastAPI Routing Engine
│   ├── main.py            # API server (routes, towers, heatmap, explain)
│   ├── router/            # Routing core (graph, scorer, heuristic)
│   │   ├── engine.py      # Main routing engine (NetworkX + OSMnx)
│   │   ├── scorer.py      # 16-feature scoring model
│   │   └── heuristic.py   # Multi-objective A* heuristic
│   ├── data/              # Data ingestion scripts
│   │   ├── ingest_towers.py
│   │   ├── ingest_ookla.py
│   │   ├── ingest_roads.py
│   │   └── congestion_nodes.json
│   └── requirements.txt
├── L4_FRONTEND/           # L4 Autonomy Intelligence Dashboard
│   ├── index.html         # Main dashboard UI
│   ├── map.js             # Route rendering & Leaflet logic
│   ├── assurance.js       # Closed-loop network assurance engine
│   ├── demo.js            # Guided pitch autopilot
│   ├── static/            # Assets (noise texture, cockpit image)
│   └── components/        # Reusable JS components (RouteCard, SignalBadge)
├── docs/                  # Technical brief & data source assumptions
└── HOW_TO_RUN.md          # Setup instructions
```

---

## 🚀 How to Run

See **[HOW_TO_RUN.md](HOW_TO_RUN.md)** for full setup.

**Quick Start:**
```bash
# 1. Install dependencies
pip install -r backend/requirements.txt

# 2. Ingest data (first time only)
python backend/data/ingest_towers.py
python backend/data/ingest_roads.py
python backend/data/ingest_ookla.py
python backend/data/ingest_traffic.py

# 3. Start backend + frontend
cd backend
uvicorn main:app --host 0.0.0.0 --port 8000
```

Then open: **http://localhost:8000/l4**

---

## 📡 API Reference

| Endpoint | Description |
|---|---|
| `GET /api/route` | Compute optimal routes |
| `GET /api/towers` | Live cell tower data |
| `GET /heatmap` | Signal quality heatmap |
| `GET /api/explain` | Feature-level connectivity rationale |
| `GET /api/health` | System health check |
| `GET /api/docs` | Swagger UI |

---

## 🗂️ Data Sources

- **TRAI Open Data** — Cell tower locations (BLR)
- **Ookla Speedtest** — Tile-level throughput scores
- **OpenStreetMap** — Road network (via OSMnx)
- **OpenTrafficData** — Congestion node penalties

---

## 👥 Team

Built for the **MAHE-Harman AI in Mobility Challenge 2026**
