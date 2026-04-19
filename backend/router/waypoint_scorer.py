"""
backend/router/waypoint_scorer.py  —  CellRoute Waypoint Scorer v2.0
=====================================================================
Real-time per-waypoint connectivity scoring using 16 features.

This module handles ONLINE query-time scoring. The offline precomputed
scored_segments_blr.parquet (from scorer.py) provides the F1+F2 base.
This module layers F5–F16 on top at request time.

16 Features
-----------
  F1  Tower Density          — KD-Tree count in radius (OSM towers)
  F2  Signal Quality         — RSRP physics ITU-R path loss model
  F3  Radio Generation       — NR/LTE/UMTS/GSM radio_weight scale
  F4  Operator Diversity     — Multi-MNO redundancy (confidence proxy)
  F5  Time-of-Day            — TRAI Bangalore IST peak/off-peak  [multiplicative]
  F6  Data Reliability       — OSM tower confidence score
  F7  Measured Throughput    — Ookla download speed tile
  F8  Traffic Congestion     — Congestion node proximity penalty
  F9  Handoff Stability      — Route-level: fewest dominant-cell changes (3GPP TS 36.331)
  F10 eCall Reliability      — EU Reg 2015/758 RSRP threshold tier (Harman TCU critical)
  F11 5G Network Slicing     — URSP: embb/urllc/default (3GPP TS 24.526)
  F12 Tower Load Simulation  — Peak-hour density penalty
  F14 Weather Connectivity   — Monsoon attenuation −8 pts (ITU-R P.838)
  F15 Predictive Forecasting — Lookahead t+ETA load prediction
  F16 Ultra-Low Latency      — V2X safety <25ms Ookla latency bonus (3GPP TS 22.186)

Public API
----------
  WaypointScorer.score_waypoint(lat, lon, slice_type, weather, eta_min) → dict
  WaypointScorer.score_route(waypoints, slice_type, weather, eta_min)   → dict
  WaypointScorer.explain(lat, lon, slice_type, weather)                 → dict
  WaypointScorer.heatmap_grid(lat_min, lat_max, lon_min, lon_max, step, slice_type) → list

Author: CellRoute Team | MAHE-Harman AI in Mobility 2026
"""

import os
import math
import json
import logging
import datetime
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree
from typing import Optional

log = logging.getLogger("CellRoute.WaypointScorer")


# =============================================================================
# SECTION 1: DATA PATHS
# =============================================================================

def _data(filename: str) -> str:
    """Resolve path relative to backend/data/."""
    return os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", filename)


# =============================================================================
# SECTION 2: RSRP PHYSICS CONSTANTS  (same as scorer.py — consistent)
# =============================================================================

TX_POWER_DBM    = 46      # Typical eNB transmit power (dBm)
FREQ_MHZ        = 1800    # LTE Band 3 — dominant in India
PL_EXPONENT     = 3.5     # Urban macro path loss exponent (ITU-R)
EARTH_RADIUS_KM = 6371.0
DEFAULT_RADIUS_KM = 2.0   # ITU-R M.2370 typical urban macro ISD


# =============================================================================
# SECTION 3: FEATURE CONSTANTS
# =============================================================================

# ── F5: Time-of-Day (TRAI Bangalore IST 2023) ────────────────────────────────
IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30))

PEAK_PERIODS = [
    ( 8.0, 10.5, 0.72, "Morning rush 8–10:30 AM IST"),
    (13.0, 14.5, 0.88, "Lunch congestion 1–2:30 PM IST"),
    (17.5, 21.0, 0.68, "Evening rush 5:30–9 PM IST (worst)"),
    (23.0,  5.0, 1.15, "Night 11 PM–5 AM IST — low-congestion bonus"),
]

# ── F10: eCall (EU Regulation 2015/758) ──────────────────────────────────────
# RSRP thresholds (dBm) — LTE minimum for eCall emergency channel
ECALL_RSRP_FULL    = -95.0    # Reliable eCall: strong signal
ECALL_RSRP_PARTIAL = -110.0   # Marginal eCall: weak signal
ECALL_FULL    = 5.0
ECALL_PARTIAL = 2.5
ECALL_DEAD    = 0.0

# ── F11: 5G URSP Network Slicing (3GPP TS 24.526) ────────────────────────────
SLICE_EMBB_REF_MBPS = 50.0    # eMBB reference download speed
F11_MAX     = 5.0
F11_DEFAULT = 2.5

# ── F12: Tower Load Simulation ────────────────────────────────────────────────
F12_LOAD_PENALTY_MAX = -10.0

# ── F14: Weather Connectivity (ITU-R P.838 — rain attenuation) ───────────────
F14_WEATHER_PENALTY_RAIN = -8.0

# ── F15: Predictive Forecasting ───────────────────────────────────────────────
F15_PREDICTIVE_SCALE = 10.0

# ── F16: Ultra-Low Latency / V2X (3GPP TS 22.186) ────────────────────────────
F16_LATENCY_IDEAL_MS    = 25.0
F16_LATENCY_TERRIBLE_MS = 60.0
F16_MAX = 5.0

# ── Score bounds ──────────────────────────────────────────────────────────────
SCORE_MIN = 5.0
SCORE_MAX = 100.0

# ── User ISP Multipliers ──────────────────────────────────────────────────────
ISP_BONUS = {
    "jio": 1.15,
    "airtel": 1.05,
    "default": 1.0
}

# ── Score color bands (same as frontend) ─────────────────────────────────────
SCORE_COLOR_BANDS = [
    (85, "#00D4AA"),   # Excellent — teal
    (70, "#4CAF50"),   # Good      — green
    (55, "#FFC107"),   # Moderate  — amber
    (40, "#FF9800"),   # Poor      — orange
    (0,  "#F44336"),   # Dead Zone — red
]


# =============================================================================
# SECTION 4: UTILITY FUNCTIONS
# =============================================================================

def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance (km) — Haversine formula."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return EARTH_RADIUS_KM * 2 * math.asin(math.sqrt(a))


def _rsrp_dbm(dist_m: float) -> float:
    """Compute RSRP (dBm) at a given distance from a tower using ITU-R log-distance path loss."""
    if dist_m < 1:
        dist_m = 1.0
    pl = 20 * np.log10(dist_m) + 32.4 + 20 * np.log10(FREQ_MHZ)
    return TX_POWER_DBM - pl * (PL_EXPONENT / 2)


def get_time_of_day_factor(dt: Optional[datetime.datetime] = None) -> tuple:
    """Return (multiplier, label) for the given datetime (defaults to now IST)."""
    if dt is None:
        dt = datetime.datetime.now(tz=IST)
    ist_dt = dt.astimezone(IST)
    h = ist_dt.hour + ist_dt.minute / 60.0
    for start, end, mult, label in PEAK_PERIODS:
        if start < end:
            if start <= h < end:
                return mult, label
        else:
            if h >= start or h < end:
                return mult, label
    return 1.0, "Off-peak — normal network load"


def score_to_color(s: float) -> str:
    for threshold, color in SCORE_COLOR_BANDS:
        if s >= threshold:
            return color
    return "#F44336"


def score_to_label(s: float) -> str:
    if s >= 85: return "Excellent"
    if s >= 70: return "Good"
    if s >= 55: return "Moderate"
    if s >= 40: return "Poor"
    return "Dead Zone"


# =============================================================================
# SECTION 5: WAYPOINT SCORER CLASS
# =============================================================================

class WaypointScorer:
    """
    Online query-time scoring of GPS waypoints using 16 connectivity features.

    Loads towers_blr.parquet + ookla_blr.parquet + congestion_nodes.json
    once at startup (same files used by the precompute scorer.py).

    Used by the API endpoints:
      GET /api/explain   → full per-point feature breakdown
      GET /heatmap       → grid over Bangalore bbox
      GET /api/route     → enriched route response (eCall, slice, handoff)
    """

    def __init__(self):
        self.towers_df      = None
        self.tower_kdtree   = None

        self.ookla_df       = None
        self.ookla_kdtree   = None
        self._ookla_centroids = None

        self.traffic_kdtree = None

        self._load_towers()
        self._load_ookla()
        self._load_traffic()

        t_count = len(self.towers_df) if self.towers_df is not None else 0
        o_count = len(self.ookla_df)  if self.ookla_df  is not None else 0
        log.info("[WaypointScorer] Ready — %d towers | %d ookla tiles", t_count, o_count)

    # ── 5a. Data loaders ──────────────────────────────────────────────────────

    def _load_towers(self) -> None:
        p = _data("towers_blr.parquet")
        if not os.path.exists(p):
            log.warning("[WaypointScorer] towers_blr.parquet not found — F1-F4/F6/F9/F10 degraded")
            return
        self.towers_df = pd.read_parquet(p)
        coords = np.column_stack([self.towers_df["lon"].values, self.towers_df["lat"].values])
        self.tower_kdtree = cKDTree(coords)
        log.info("[WaypointScorer] %d towers from towers_blr.parquet", len(self.towers_df))

    def _load_ookla(self) -> None:
        p = _data("ookla_blr.parquet")
        if not os.path.exists(p):
            log.warning("[WaypointScorer] ookla_blr.parquet not found — F7/F16 will use defaults")
            return
        try:
            import geopandas as gpd
            gdf = gpd.read_parquet(p)
            self.ookla_df = gdf
            # Reproject to metric CRS for accurate centroids, then get WGS84 coords
            gdf_m = gdf.to_crs("EPSG:32643")  # UTM Zone 43N — covers Bangalore
            centroids_m = gdf_m.geometry.centroid
            centroids_wgs = centroids_m.to_crs("EPSG:4326")
            self._ookla_centroids = np.column_stack([centroids_wgs.x.values, centroids_wgs.y.values])
            self.ookla_kdtree = cKDTree(self._ookla_centroids)
            log.info("[WaypointScorer] %d Ookla tiles from ookla_blr.parquet", len(gdf))
        except Exception as e:
            log.warning("[WaypointScorer] Could not load ookla parquet: %s", e)


    def _load_traffic(self) -> None:
        p = _data("congestion_nodes.json")
        if not os.path.exists(p):
            log.warning("[WaypointScorer] congestion_nodes.json not found — F8 will use default")
            return
        try:
            with open(p) as f:
                data = json.load(f)
            if data:
                # data is [[lat, lon], ...] — store as [lon, lat] for cKDTree
                coords = np.array([[pt[1], pt[0]] for pt in data])
                self.traffic_kdtree = cKDTree(coords)
                log.info("[WaypointScorer] %d congestion nodes loaded", len(data))
        except Exception as e:
            log.warning("[WaypointScorer] Could not load congestion nodes: %s", e)

    # ── 5b. Spatial lookups ───────────────────────────────────────────────────

    def _nearby_towers(self, lat: float, lon: float, radius_km: float = DEFAULT_RADIUS_KM):
        """Return (DataFrame rows, list of distances_m) for towers within radius_km."""
        if self.tower_kdtree is None:
            return None, []
        radius_deg = radius_km / 111.0
        idxs = self.tower_kdtree.query_ball_point([lon, lat], radius_deg)
        if not idxs:
            return None, []
        rows = self.towers_df.iloc[idxs]
        dists_m = [_haversine_km(lat, lon, float(r["lat"]), float(r["lon"])) * 1000
                   for _, r in rows.iterrows()]
        return rows, dists_m

    def _ookla_stats(self, lat: float, lon: float, radius_km: float = 3.0):
        """Return (avg_d_mbps, avg_latency_ms) from nearest Ookla tile."""
        DEFAULT_SPEED   = 30.0   # Bangalore urban median
        DEFAULT_LATENCY = 45.0
        if self.ookla_kdtree is None:
            return DEFAULT_SPEED, DEFAULT_LATENCY
        radius_deg = radius_km / 111.0
        dists, idxs = self.ookla_kdtree.query([lon, lat], k=3, distance_upper_bound=radius_deg)
        valid = [(d, i) for d, i in zip(dists, idxs)
                 if d != np.inf and i < len(self.ookla_df)]
        if not valid:
            return DEFAULT_SPEED, DEFAULT_LATENCY
        row = self.ookla_df.iloc[valid[0][1]]
        speed   = float(row["avg_d_mbps"])   if pd.notna(row.get("avg_d_mbps"))   else DEFAULT_SPEED
        latency = float(row["avg_latency_ms"]) if pd.notna(row.get("avg_latency_ms")) else DEFAULT_LATENCY
        return round(speed, 1), round(latency, 1)

    def _jam_factor(self, lat: float, lon: float, radius_m: float = 600.0) -> float:
        """Return jam factor 0–1 based on congestion node proximity."""
        if self.traffic_kdtree is None:
            return 0.35  # Bangalore baseline
        radius_deg = radius_m / 111_000.0
        dist, _ = self.traffic_kdtree.query([lon, lat], k=1, distance_upper_bound=radius_deg * 6)
        if dist == np.inf:
            return 0.25
        jam = max(0.0, 1.0 - dist / (radius_deg * 6))
        return round(jam, 3)

    # ── 5c. Core scoring function ─────────────────────────────────────────────

    def score_waypoint(
        self,
        lat:        float,
        lon:        float,
        radius_km:  float = DEFAULT_RADIUS_KM,
        slice_type: str   = "default",
        weather:    str   = "clear",
        isp:        str   = "all",
        eta_min:    float = 0.0,
        dt:         Optional[datetime.datetime] = None,
    ) -> dict:
        """
        Compute 16-feature connectivity score for a single GPS waypoint.

        Returns a rich dict with score, all feature values, eCall status,
        dominant tower index (for F9 handoff tracking), and reason string.
        """
        if dt is None:
            dt = datetime.datetime.now(tz=IST)

        # ── F5: Time-of-Day ──────────────────────────────────────────────────
        time_factor, time_label = get_time_of_day_factor(dt)

        # ── F14: Weather penalty ──────────────────────────────────────────────
        f14 = F14_WEATHER_PENALTY_RAIN if weather in ("rain", "monsoon") else 0.0

        # ── F15: Predictive Forecasting ───────────────────────────────────────
        future_dt = dt + datetime.timedelta(minutes=eta_min)
        future_tf, _ = get_time_of_day_factor(future_dt)
        f15 = round(F15_PREDICTIVE_SCALE * (future_tf - time_factor), 2)

        # ── F7 + F16: Ookla throughput & latency ─────────────────────────────
        ookla_speed, ookla_latency = self._ookla_stats(lat, lon)
        f7 = round(min(10.0, (ookla_speed / 100.0) * 10.0), 2)
        if ookla_latency <= F16_LATENCY_IDEAL_MS:
            f16 = F16_MAX
        elif ookla_latency >= F16_LATENCY_TERRIBLE_MS:
            f16 = 0.0
        else:
            ratio = (ookla_latency - F16_LATENCY_IDEAL_MS) / (
                F16_LATENCY_TERRIBLE_MS - F16_LATENCY_IDEAL_MS)
            f16 = round(F16_MAX * (1.0 - ratio), 2)

        # ── F8: Traffic congestion ────────────────────────────────────────────
        jam = self._jam_factor(lat, lon)
        f8 = round(8.0 * (1.0 - jam), 2)

        # ── Tower-based features ──────────────────────────────────────────────
        tower_rows, dists_m = self._nearby_towers(lat, lon, radius_km)
        no_towers = tower_rows is None or len(tower_rows) == 0

        isp_factor = ISP_BONUS.get(isp.lower(), ISP_BONUS["default"])

        if no_towers:
            raw   = f7 + f8 + f14 + f15 + f16
            score = round(min(SCORE_MAX, max(SCORE_MIN, raw * time_factor * isp_factor)), 1)
            return {
                "score": score,
                "towers": 0, "has_lte": False,
                "avg_rsrp_dbm": None,
                "dominant_tower_idx": -1,
                "time_factor": round(time_factor, 3), "time_label": time_label,
                "ookla_speed_mbps": ookla_speed, "ookla_latency_ms": ookla_latency,
                "jam_factor": jam, "slice_type": slice_type,
                "ecall_status": "dead zone",
                "feature_breakdown": {
                    "F1_tower_density": 0.0, "F2_signal_quality": 0.0,
                    "F3_radio_generation": 0.0, "F4_operator_diversity": 0.0,
                    "F5_time_of_day": f"×{round(time_factor, 3)}", "F6_data_reliability": 0.0,
                    "F7_ookla_throughput": f7, "F8_traffic_congestion": f8,
                    "F10_ecall_reliability": ECALL_DEAD, "F11_5g_slice": F11_DEFAULT,
                    "F12_tower_load": 0.0, "F14_weather": f14,
                    "F15_predictive": f15, "F16_v2x_latency": f16,
                    "raw_before_F5": round(raw, 2),
                    "isp_bonus": isp_factor,
                },
                "reason": f"No towers within {radius_km} km (dead zone) | Ookla {ookla_speed} Mbps | jam {jam} | ISP: {isp}",
                "score_color": score_to_color(score),
                "score_label": score_to_label(score),
            }

        tower_count = len(tower_rows)

        # ── F1: Tower Density ─────────────────────────────────────────────────
        f1 = round(math.log10(tower_count + 1) * 20.0, 2)

        # ── F2: Signal Quality — RSRP physics ────────────────────────────────
        rsrp_vals = [_rsrp_dbm(max(d, 1.0)) for d in dists_m]
        avg_rsrp  = round(float(np.mean(rsrp_vals)), 1)
        # Map RSRP from [-140 dead → -80 excellent] to 0–15 pts
        f2 = round(min(15.0, max(0.0, (avg_rsrp + 140) / 60 * 15.0)), 2)

        # ── F3: Radio Generation — radio_weight proxy ─────────────────────────
        # radio_weight in OSM parquet: NR≈1.0, LTE≈0.83, UMTS≈0.38, GSM≈0.11
        avg_radio_weight = float(tower_rows["radio_weight"].mean()) if "radio_weight" in tower_rows else 0.83
        # Scale: NR(1.0)→18 pts, LTE(0.83)→15 pts, UMTS(0.38)→7 pts, GSM(0.11)→2 pts
        f3 = round(min(15.0, avg_radio_weight * 18.0), 2)
        has_lte = avg_radio_weight >= 0.75   # LTE or NR threshold

        # ── F4: Operator Diversity — confidence variance proxy ────────────────
        if "confidence" in tower_rows.columns:
            n_unique_conf_bands = max(1, int(tower_rows["confidence"].nunique()))
            f4 = round(min(12.0, n_unique_conf_bands * 3.0), 2)
        else:
            f4 = 6.0  # reasonable urban default

        # ── F6: Data Reliability — OSM confidence score ───────────────────────
        if "confidence" in tower_rows.columns:
            avg_conf = float(tower_rows["confidence"].mean())
            f6 = round(4.0 * avg_conf, 2)
        else:
            f6 = 2.0

        # ── F10: eCall Reliability (EU Reg 2015/758) ──────────────────────────
        if avg_rsrp >= ECALL_RSRP_FULL:
            f10, ecall_status = ECALL_FULL,    "reliable"
        elif avg_rsrp >= ECALL_RSRP_PARTIAL:
            f10, ecall_status = ECALL_PARTIAL, "marginal"
        else:
            f10, ecall_status = ECALL_DEAD,    "dead zone"

        # ── F11: 5G Network Slicing (URSP — 3GPP TS 24.526) ──────────────────
        if slice_type == "embb":
            f11 = round(min(F11_MAX, (ookla_speed / SLICE_EMBB_REF_MBPS) * F11_MAX), 2)
        elif slice_type == "urllc":
            lte_bonus = 2.0 if has_lte else 0.5
            jam_bonus = round((1.0 - jam) * 1.5, 2)
            sig_bonus = round(min(1.5, (avg_rsrp + 95) / 40.0), 2) if avg_rsrp > -95 else 0.0
            f11 = round(min(F11_MAX, lte_bonus + jam_bonus + sig_bonus), 2)
        else:
            f11 = F11_DEFAULT

        # ── F12: Tower Load Simulation ────────────────────────────────────────
        if time_factor <= 0.9 and tower_count >= 10:
            load_proxy = ((0.9 - time_factor) / 0.9) * min(tower_count / 50.0, 1.0)
            f12 = round(F12_LOAD_PENALTY_MAX * load_proxy, 2)
        else:
            f12 = 0.0

        # ── Dominant tower (for F9 handoff tracking at route level) ───────────
        dominant_tower_idx = int(tower_rows.index[int(np.argmin(dists_m))])

        # ── Composite: additive raw → multipliers ───────────────────────────
        raw   = f1 + f2 + f3 + f4 + f6 + f7 + f8 + f10 + f11 + f12 + f14 + f15 + f16
        score = round(min(SCORE_MAX, max(SCORE_MIN, raw * time_factor * isp_factor)), 1)

        return {
            "score":               score,
            "towers":              tower_count,
            "has_lte":             has_lte,
            "avg_rsrp_dbm":        avg_rsrp,
            "dominant_tower_idx":  dominant_tower_idx,
            "time_factor":         round(time_factor, 3),
            "time_label":          time_label,
            "ookla_speed_mbps":    ookla_speed,
            "ookla_latency_ms":    ookla_latency,
            "jam_factor":          jam,
            "slice_type":          slice_type,
            "ecall_status":        ecall_status,
            "feature_breakdown": {
                "F1_tower_density":      f1,
                "F2_signal_quality":     f2,
                "F3_radio_generation":   f3,
                "F4_operator_diversity": f4,
                "F5_time_of_day":        f"×{round(time_factor, 3)}",
                "F6_data_reliability":   f6,
                "F7_ookla_throughput":   f7,
                "F8_traffic_congestion": f8,
                "F10_ecall_reliability": f10,
                "F11_5g_slice":          f11,
                "F12_tower_load":        f12,
                "F14_weather":           f14,
                "F15_predictive":        f15,
                "F16_v2x_latency":       f16,
                "raw_before_F5":         round(raw, 2),
                "isp_bonus":             isp_factor,
            },
            "reason": (
                f"{tower_count} towers | RSRP={avg_rsrp} dBm | "
                f"{'LTE/NR' if has_lte else 'sub-LTE'} | "
                f"Ookla={ookla_speed} Mbps | jam={jam} | "
                f"eCall={ecall_status} | slice={slice_type} | ISP={isp}"
            ),
            "score_color": score_to_color(score),
            "score_label": score_to_label(score),
        }

    # ── 5d. Route-level scoring (F9 handoff) ──────────────────────────────────

    def score_route(
        self,
        waypoints:  list,
        slice_type: str   = "default",
        weather:    str   = "clear",
        isp:        str   = "all",
        eta_min:    float = 0.0,
        dt:         Optional[datetime.datetime] = None,
    ) -> dict:
        """
        Score a list of waypoints and aggregate to route level.
        Computes F9 Handoff Stability at route level.
        """
        if not waypoints:
            return {}

        if dt is None:
            dt = datetime.datetime.now(tz=IST)
        points = [
            {
                "lat": float(wp[0]) if isinstance(wp, (list, tuple)) else float(wp["lat"]),
                "lon": float(wp[1]) if isinstance(wp, (list, tuple)) else float(wp["lon"]),
                **self.score_waypoint(
                    float(wp[0]) if isinstance(wp, (list, tuple)) else float(wp["lat"]),
                    float(wp[1]) if isinstance(wp, (list, tuple)) else float(wp["lon"]),
                    slice_type=slice_type, weather=weather, isp=isp, eta_min=eta_min, dt=dt,
                )
            }
            for wp in waypoints
        ]

        scores         = [p["score"] for p in points]
        ecall_statuses = [p["ecall_status"] for p in points]

        # ── F9: Handoff Stability (route-level) ────────────────────────────
        dom = [p["dominant_tower_idx"] for p in points]
        handoffs = sum(
            1 for i in range(1, len(dom))
            if dom[i] != dom[i - 1] and dom[i] != -1 and dom[i - 1] != -1
        )
        max_h     = max(len(points) - 1, 1)
        f9_bonus  = round(6.0 * (1.0 - handoffs / max_h), 2)

        route_score = round(
            min(SCORE_MAX, max(SCORE_MIN, float(np.mean(scores)) + f9_bonus)), 1
        )

        return {
            "route_score":             route_score,
            "min_score":               round(min(scores), 1),
            "max_score":               round(max(scores), 1),
            "std_score":               round(float(np.std(scores)), 1),
            "handoff_count":           handoffs,
            "f9_handoff_bonus":        f9_bonus,
            "ecall_statuses":          ecall_statuses,
            "ecall_failed_waypoints":  [i + 1 for i, s in enumerate(ecall_statuses) if s == "dead zone"],
            "ecall_partial_waypoints": [i + 1 for i, s in enumerate(ecall_statuses) if s == "marginal"],
            "ecall_reliable_fraction": round(
                sum(1 for s in ecall_statuses if s == "reliable") / len(ecall_statuses), 2
            ),
            "avg_ookla_speed_mbps":    round(float(np.mean([p["ookla_speed_mbps"] for p in points])), 1),
            "avg_jam_factor":          round(float(np.mean([p["jam_factor"] for p in points])), 3),
            "time_label":              points[0]["time_label"] if points else "unknown",
            "slice_type":              slice_type,
            "points":                  points,
        }

    # ── 5e. Explain endpoint ──────────────────────────────────────────────────

    def explain(
        self,
        lat:        float,
        lon:        float,
        slice_type: str = "default",
        weather:    str = "clear",
        isp:        str = "all",
        dt:         Optional[datetime.datetime] = None,
    ) -> dict:
        """Returns full scoring rationale for the /api/explain endpoint."""
        if dt is None:
            dt = datetime.datetime.now(tz=IST)
        result = self.score_waypoint(lat, lon, slice_type=slice_type, weather=weather, isp=isp, dt=dt)
        tod_factor, tod_label = get_time_of_day_factor(dt)

        return {
            "location":          {"lat": lat, "lon": lon},
            "score":             result["score"],
            "score_color":       result["score_color"],
            "score_label":       result["score_label"],
            "feature_breakdown": result["feature_breakdown"],
            "reason":            result["reason"],
            "slice_type":        slice_type,
            "time_of_day":       {"factor": round(tod_factor, 3), "label": tod_label},
            "formula":           "score = clamp((F1+F2++...+F16) × F5 × ISP_Bonus,  5, 100)",
            "features_explained": {
                "F1":  "Tower Density — log10(count+1)×20 | Source: OpenStreetMap towers_blr.parquet",
                "F2":  "Signal Quality — RSRP physics ITU-R path loss | Source: tower distance",
                "F3":  "Radio Generation — NR/LTE/UMTS/GSM radio_weight | Source: OSM radio field",
                "F4":  "Operator Diversity — multi-MNO proxy via confidence variance | Source: OSM",
                "F5":  "Time-of-Day — TRAI IST peak/off-peak multiplier 0.68×–1.15× | Source: TRAI 2023",
                "F6":  "Data Reliability — OSM tower confidence 0–1 | Source: OSM confidence field",
                "F7":  "Measured Throughput — Ookla download speed tile (Mbps) | Source: Ookla Open Data",
                "F8":  "Traffic Congestion — congestion node proximity jam factor inverse | Source: OpenTrafficData",
                "F9":  "Handoff Stability — fewest dominant-cell changes per route | 3GPP TS 36.331",
                "F10": "eCall Reliability — EU Regulation 2015/758 RSRP threshold tier | Harman TCU critical",
                "F11": "5G Network Slicing — URSP eMBB/URLLC/default policy | 3GPP TS 24.526",
                "F12": "Tower Load Simulation — peak-hour density penalty | Source: time × density proxy",
                "F14": "Weather Connectivity — monsoon rain attenuation −8 pts | ITU-R P.838",
                "F15": "Predictive Forecasting — lookahead congestion at t+ETA | TRAI time model",
                "F16": "Ultra-Low Latency — V2X safety <25ms Ookla latency bonus | 3GPP TS 22.186",
            },
            "harman_use_cases": {
                "F10": "eCall emergency call compliance — EU Reg 2015/758 requires reliable voice at crash site",
                "F11": "TCU 5G URSP policy — OTA firmware (eMBB needs throughput) vs V2X (URLLC needs <100ms)",
                "F9":  "Handover smoothness — each LTE X2 handover causes 20–50ms connectivity gap (3GPP TS 36.331)",
                "F16": "Cooperative collision avoidance — V2X BSM needs <100ms E2E latency (3GPP TS 22.186)",
            },
            "scalability_note": (
                "Scoring kernel is pure Python arithmetic, portable to C++ for "
                "Harman TCU SoC (Qualcomm SA8155) deployment."
            ),
        }

    # ── 5f. Heatmap grid ─────────────────────────────────────────────────────

    def heatmap_grid(
        self,
        lat_min:    float = 12.85,
        lat_max:    float = 13.05,
        lon_min:    float = 77.55,
        lon_max:    float = 77.75,
        step:       float = 0.02,
        slice_type: str   = "default",
        isp:        str   = "all",
        dt:         Optional[datetime.datetime] = None,
    ) -> list:
        """
        Generate a grid of connectivity_index values for the heatmap overlay.
        step=0.02° ≈ 2.2 km at Bangalore latitude → ~50 cells (fast).
        step=0.01° ≈ 1.1 km → ~200 cells (slower, richer).
        """
        step = max(float(step), 0.005)  # Cap density for performance
        cells = []
        lat = lat_min
        while lat <= lat_max + 1e-9:
            lon = lon_min
            while lon <= lon_max + 1e-9:
                result = self.score_waypoint(lat, lon, slice_type=slice_type, isp=isp, dt=dt)
                cells.append({
                    "lat":   round(lat, 5),
                    "lon":   round(lon, 5),
                    "score": result["score"],
                    "color": result["score_color"],
                    "label": result["score_label"],
                    "ecall": result["ecall_status"],
                    "step":  step,
                })
                lon = round(lon + step, 6)
            lat = round(lat + step, 6)
        log.info("[WaypointScorer] Heatmap grid: %d cells (step=%.4f°, slice=%s)",
                 len(cells), step, slice_type)
        return cells


# =============================================================================
# SELF-TEST
# =============================================================================

if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(name)s: %(message)s")

    print("\n── CellRoute WaypointScorer v2.0 Self-Test ──")
    scorer = WaypointScorer()

    test_points = [
        (12.9716, 77.5946, "MG Road"),
        (12.9591, 77.6974, "Marathahalli"),
        (12.8399, 77.6770, "Electronic City"),
    ]

    for lat, lon, name in test_points:
        for sl in ["default", "embb", "urllc"]:
            r = scorer.score_waypoint(lat, lon, slice_type=sl)
            fb = r["feature_breakdown"]
            print(
                f"  {name:18} slice={sl:7} → score={r['score']:5.1f}  "
                f"eCall={r['ecall_status']:8}  "
                f"F10={fb['F10_ecall_reliability']}  F11={fb['F11_5g_slice']}  "
                f"F16={fb['F16_v2x_latency']}"
            )

    print("\n── Explain output (MG Road, URLLC slice) ──")
    exp = scorer.explain(12.9716, 77.5946, slice_type="urllc")
    for k, v in exp["feature_breakdown"].items():
        print(f"  {k:28} = {v}")

    print("\n── Heatmap grid sample (5×5) ──")
    h = scorer.heatmap_grid(12.96, 12.98, 77.58, 77.60, step=0.01)
    print(f"  Generated {len(h)} cells")
    for c in h[:3]:
        print(f"  {c['lat']}, {c['lon']} → {c['score']} ({c['label']}) eCall={c['ecall']}")

    print("\n[OK] waypoint_scorer.py v2.0 self-test complete")
