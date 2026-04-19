# CellRoute — Heuristics Reference Card (v2.0)

**Project:** Cellular Network-Aware Routing Engine  
**Challenge:** MAHE-Harman AI in Mobility 2026 — Problem Statement 1  
**Scoring Engine:** `backend/router/waypoint_scorer.py` — `WaypointScorer` class

---

## What Is a "Connectivity Score"?

A single GPS coordinate receives a score from **5 to 100** representing the quality of cellular connectivity a Harman TCU would experience at that location. The score aggregates **16 independent signal dimensions** into one actionable number that the routing engine uses to compare candidate route segments.

Route bands used by the frontend UI:

| Band | Score | Routing recommendation |
|---|---|---|
| Excellent | 85 – 100 | Unrestricted — all in-vehicle services safe |
| Good | 70 – 84 | Normal operation; OTA firmware transfers feasible |
| Moderate | 55 – 69 | Buffer-sensitive; schedule large transfers at waypoints |
| Poor | 40 – 54 | Avoid if alternatives exist; disable non-critical streaming |
| Dead Zone | < 40 | Pre-buffer before entry; alert driver via HMI |

---

## The 16 Weighted Features

### F1 — Tower Density (log-scaled)

```
F1 = log10(tower_count + 1) × 20.0
```

Counts all OSM towers within the search radius (default 2 km) and applies a **base-10 logarithm** before weighting.

**Why log-scale?** Bangalore's MG Road has thousands of towers in 2 km. A linear weight would collapse all urban cores to score=100 with no useful differentiation. The log scale maps the full range so every geography produces a meaningful, graded score.

**Physical basis:** Macro-cell spatial diversity gain — more towers in range means more base stations available for handover, reducing drop probability (Rappaport, *Wireless Communications*, 2002).

*Source: OpenStreetMap towers_blr.parquet*

---

### F2 — Signal Quality (RSRP Physics)

```
RSRP(dBm) = TX_POWER - PathLoss(dist_m)
F2 = clamp((RSRP + 140) / 60 × 15.0,  0, 15)
```

Uses the **ITU-R log-distance path loss model** to compute RSRP at each tower's measured distance from the waypoint, then normalises to a 0–15 point contribution.

- TX Power: 46 dBm (LTE eNB typical)
- Frequency: 1800 MHz (LTE Band 3 — dominant in India)
- Exponent: 3.5 (urban macro ITU-R)

*Source: OSM tower coordinates + physics model*

---

### F3 — Radio Generation Score

```
F3 = clamp(avg_radio_weight × 18.0,  0, 15)

radio_weight mapping:
  NR (5G)  → 1.00 → 18 pts
  LTE      → 0.83 → 15 pts
  UMTS/3G  → 0.38 →  7 pts
  GSM/2G   → 0.11 →  2 pts
```

**V2X relevance:** 3GPP TS 22.186 requires sub-100 ms end-to-end latency for cooperative collision avoidance. GSM cannot meet this; LTE consistently can. NR (5G) is future-proofed.

*Source: OSM radio_weight field in towers_blr.parquet*

---

### F4 — Operator Diversity

```
F4 = clamp(unique_confidence_bands × 3.0,  0, 12)
```

More operators in range = more roaming fallback paths for the TCU. Proxied via OSM confidence band diversity where explicit MNC data is unavailable.

Max contribution: 12 pts (4+ distinct coverage profiles in range).

*Source: OSM confidence field*

---

### F5 — Time-of-Day Factor *(multiplicative — F5 modifies all other features)*

```
score = raw_score × F5

F5 periods (IST, TRAI 2023 Bangalore network load data):
  08:00 – 10:30  →  0.72×   Morning rush; 80–95% PRB utilisation
  13:00 – 14:30  →  0.88×   Lunch congestion
  17:30 – 21:00  →  0.68×   Evening rush (worst congestion period)
  23:00 – 05:00  →  1.15×   Night; low-congestion bonus
  Other          →  1.00×   Off-peak; normal
```

**Why multiplicative?** Network congestion degrades *all* connectivity dimensions simultaneously — throughput falls, handover success rate drops, latency inflates. A single post-hoc multiplier on the combined raw score reflects this correlated effect.

**In-vehicle policy:** The TCU firmware can set F5 thresholds to trigger automatic routing re-evaluation when the effective score drops below a safety threshold.

*Source: TRAI Annual Report 2023*

---

### F6 — Data Reliability

```
F6 = 4.0 × avg_confidence
```

OSM tower confidence (0–1) reflects the accuracy of the tower's geoposition. High confidence = sub-50m positional accuracy. This bonus rewards regions where the underlying data is trustworthy.

*Source: OSM confidence field in towers_blr.parquet*

---

### F7 — Measured Throughput (Ookla)

```
F7 = clamp(avg_d_mbps / 100 × 10.0,  0, 10)
```

Real-world Ookla Speedtest download speed tiles for Bangalore. Maps 0–100 Mbps throughput to 0–10 pts.

*Source: Ookla Speedtest Open Data — ookla_blr.parquet*

---

### F8 — Traffic Congestion Inverse

```
jam_factor = distance_to_nearest_congestion_node / max_range   [0–1]
F8 = 8.0 × (1.0 − jam_factor)
```

High traffic congestion degrades network quality through increased user density and physical multipath. Proxied by proximity to congestion hotspots.

*Source: OpenTrafficData congestion_nodes.json*

---

### F9 — Handoff Stability *(route-level feature)*

```
handoffs = count(dominant_tower changes along route)
F9_bonus = 6.0 × (1 − handoffs / max_possible_handoffs)
```

Computed at route-level (not per-waypoint): tracks the dominant serving cell at each sampled waypoint. Fewer cell changes = smoother V2X/streaming experience.

**3GPP reference:** Each LTE X2 handover causes a 20–50ms connectivity interruption (3GPP TS 36.331). Minimising handoffs is critical for URLLC slice V2X applications.

---

### F10 — eCall Reliability *(EU Regulation 2015/758)*

```
F10 = 5.0   if RSRP ≥ −95 dBm   (reliable eCall)
F10 = 2.5   if RSRP ≥ −110 dBm  (marginal eCall)
F10 = 0.0   if RSRP  < −110 dBm (dead zone — eCall unavailable)
```

**Why this matters for Harman:** EU Regulation 2015/758 requires all new vehicles sold in Europe to have a working eCall system. The Harman TCU must maintain reliable GSM/LTE coverage for the crash-triggered emergency call. Routes that pass through signal dead zones risk eCall failure — legally and safety-critical.

---

### F11 — 5G Network Slicing (URSP — 3GPP TS 24.526)

```
eMBB slice (OTA firmware updates):
  F11 = clamp(ookla_speed / 50 Mbps × 5.0,  0, 5)

URLLC slice (V2X cooperative driving):
  F11 = LTE/NR bonus (0.5–2.0)
       + jam_free bonus (0–1.5)
       + RSRP signal bonus (0–1.5)

Default slice:
  F11 = 2.5 (neutral)
```

**3GPP URSP context:** The TCU uses URSP (UE Route Selection Policy) rules to bind different traffic types to appropriate 5G network slices. OTA firmware downloads → eMBB (high throughput), V2X safety messages → URLLC (ultra-low latency, <5ms). The routing engine optimises for the active slice type.

---

### F12 — Tower Load Simulation (Peak-Hour Penalty)

```
if time_factor ≤ 0.9 and tower_count ≥ 10:
    load_proxy = (0.9 − time_factor) / 0.9 × min(tower_count / 50, 1.0)
    F12 = −10 × load_proxy
else:
    F12 = 0
```

At peak hours in dense areas, towers are overloaded — PRB (Physical Resource Block) utilisation spikes to 95%, causing effective throughput to drop even without total signal loss. This penalty simulates that effect.

---

### F14 — Weather Connectivity (ITU-R P.838)

```
F14 = −8.0  if weather = "rain" / "monsoon"
F14 =  0.0  if weather = "clear"
```

Rain attenuation at LTE frequencies (1800 MHz) — ITU-R P.838 model. Bangalore's monsoon (June–September) causes measurable signal degradation, particularly in dense urban canyons where multipath combines with rain scattering.

Toggled via the **Monsoon Penalty** UI control.

---

### F15 — Predictive Forecasting (ETA-based)

```
future_dt = now + route_ETA_minutes
future_factor = get_time_of_day_factor(future_dt)
F15 = 10.0 × (future_factor − current_factor)
```

Predicts whether network conditions will be better or worse by the time the vehicle *arrives* at a waypoint, based on the TRAI time-of-day model. A positive F15 means conditions will improve en-route; negative means congestion is worsening.

**Example:** Leaving at 5:00 PM (F5=1.0) with a 45-min ETA → arrival at 5:45 PM (F5=0.68) → F15=−3.2 (congestion warning).

---

### F16 — Ultra-Low Latency / V2X Bonus (3GPP TS 22.186)

```
F16 = 5.0    if Ookla latency ≤ 25ms   (ideal V2X)
F16 = 0.0    if Ookla latency ≥ 60ms   (too slow for V2X)
F16 = linear interpolation between 25–60ms
```

3GPP TS 22.186 specifies <100ms end-to-end latency for cooperative collision avoidance (V2X). The practical Ookla target is <25ms to leave headroom for radio/transport overhead. Routes with low-latency Ookla tiles receive a bonus in URLLC slice mode.

---

### ISP_Bonus — User Service Provider Multiplier *(multiplicative — applies to final score)*

```
score = clamp(raw_score × F5 × ISP_Bonus,  5, 100)

ISP_Bonus mapping (Bangalore 2024 market study):
  Jio     → 1.15  (largest 5G NR footprint in India; ~40% towers in BLR)
  Airtel   → 1.05  (premium urban LTE+; strong on ORR and commercial corridors)
  Vi       → 1.00  (baseline; shrinking network, limited 5G deployment)
  BSNL     → 1.00  (legacy 4G rollout, minimal BLR urban NR presence)
  All / Default → 1.00 (operator-neutral)
```

**Why a multiplier?** When the vehicle's TCU SIM is bound to a specific carrier, only towers belonging to that carrier's MNO are relevant for connectivity scoring. A Jio SIM cannot benefit from an Airtel tower. The ISP_Bonus reflects the *effective density advantage* each carrier has in Bangalore, derived from their relative tower counts in the OpenCelliD dataset filtered by MNO prefix.

**Scalability:** The `ISP_BONUS` dictionary in `waypoint_scorer.py` is a single-line addition per new operator. To add BSNL 5G or MVNO support, simply extend the dict with the measured coverage bonus.

**Auto-detect path (future):** In a production Harman TCU, the SIM's IMSI prefix (MCC+MNC) can be read from the modem via AT commands, enabling zero-user-input ISP-awareness.

*Source: OpenCelliD MNO distribution | Bangalore market penetration reports*

---

```
raw_score = F1 + F2 + F3 + F4 + F6 + F7 + F8 + F10 + F11 + F12 + F14 + F15 + F16
score     = clamp(raw_score × F5 × ISP_Bonus,  5, 100)
```

**F5 is multiplicative** — applied on the combined raw total.  
**ISP_Bonus is multiplicative** — applied after F5, reflecting carrier-specific network advantage.  
**F9 is a route-level bonus** — added to the per-route aggregate, not per waypoint.  
The floor of 5 ensures no location returns zero — even dead zones retain a residual connectivity probability the router should represent (but penalise).

---

## Data Sources

| Source | Features | Volume |
|---|---|---|
| **OpenStreetMap Towers** (`towers_blr.parquet`) | F1, F2, F3, F4, F6, F9, F10 | ~12,000 cell sites, Bangalore |
| **OSM Road Network** (`scored_segments_blr.parquet`) | Dijkstra graph, pre-scored edges | ~20M road segments |
| **Ookla Speedtest Open Data** (`ookla_blr.parquet`) | F7, F11-eMBB, F16 | 35 Bangalore tile quadrants |
| **OpenTrafficData** (`congestion_nodes.json`) | F8, F11-URLLC | 34 Bangalore intersections |

All 4 sources are **real open datasets** — no synthetic data used in routing.

---

## Why This Heuristic Is Unique

1. **First open-source router** to treat 4G/5G connectivity as a primary route constraint alongside ETA.
2. **Physically motivated weights** — log-scale density (Rappaport 2002), ITU-R M.2370 ISD for search radius, 3GPP TS 22.186 for latency targets.
3. **eCall compliance modelling** — uniquely relevant to Harman's automotive TCU product roadmap (EU Reg 2015/758).
4. **URSP-aware slice scoring** — differentiates eMBB (throughput) vs URLLC (latency) route optimisation matching real 5G SA deployment behaviour.
5. **ISP-aware personalisation** — TCU SIM carrier selection (Jio/Airtel/Vi/BSNL) dynamically adjusts scoring, matching reality where a Jio SIM cannot benefit from Airtel towers.
6. **18-line arithmetic kernel** — no ML inference, no I/O at query time — portable directly to **C++ for Harman TCU SoC (Qualcomm SA8155)** embedded deployment (as noted in HarmanLink architecture doc).
7. **Real-time closed-loop assurance** — tower KPI breach → automatic network alarm → Dijkstra re-routes around dead zone (unique to CellRoute).

---

## Live Demo Endpoints (for judges)

```bash
# Full heuristic explanation for a GPS point (URLLC slice)
GET /api/explain?lat=12.9716&lon=77.5946&slice=urllc

# Connectivity heatmap for Bangalore (visualised on map)
GET /heatmap?step=0.02&slice=default

# Route with ISP-aware routing (Jio SIM + URLLC slice)
GET /api/route?start_lat=12.9550&start_lon=77.7144&end_lat=12.9978&end_lon=77.5698&alpha=0.5&slice=urllc&isp=jio

# Health + data source status
GET /api/health
GET /api/sources
```

---

*CellRoute Team | MAHE-Harman AI in Mobility Challenge 2026*
