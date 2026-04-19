"""
Outage Manager — Closed-Loop Network Assurance
===============================================
Maintains the in-memory state of active tower outages.
The router queries this at call-time to apply an infinite penalty
to road segments within the outage radius, forcing Dijkstra to
re-route around the dead zone automatically.
"""
import math
from typing import List, Dict, Optional

# ---------------------------------------------------------------------------
# In-memory outage registry — no DB required for hackathon demo
# ---------------------------------------------------------------------------
_outages: Dict[str, dict] = {}


def register_outage(outage_id: str, lat: float, lon: float, radius_m: float = 800) -> dict:
    """Mark a geographic area as degraded (tower down / KPI breach)."""
    outage = {
        "id": outage_id,
        "lat": lat,
        "lon": lon,
        "radius_m": radius_m,
    }
    _outages[outage_id] = outage
    print(f"[ALARM] Outage registered: {outage_id} @ ({lat:.4f}, {lon:.4f}) r={radius_m}m")
    return outage


def clear_outage(outage_id: str) -> bool:
    """Remove an outage — simulates the closed-loop recovery action completing."""
    if outage_id in _outages:
        del _outages[outage_id]
        print(f"[RECOVERY] Outage cleared: {outage_id}")
        return True
    return False


def clear_all_outages():
    _outages.clear()
    print("[RECOVERY] All outages cleared.")


def get_active_outages() -> List[dict]:
    return list(_outages.values())


def _haversine_m(lat1, lon1, lat2, lon2) -> float:
    """Returns distance in metres between two lat/lon points."""
    R = 6_371_000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def get_outage_penalty(seg_lat: float, seg_lon: float) -> float:
    """
    Returns a cost multiplier for a road segment midpoint.
    - 0.0  → not in any outage zone (no penalty)
    - 1.0  → fully inside outage zone (maximum penalty, avoidance-level)
    Uses a soft distance-based falloff so Dijkstra smoothly routes around edges
    rather than creating hard cliffs that cause graph-disconnect errors.
    """
    if not _outages:
        return 0.0

    max_penalty = 0.0
    for outage in _outages.values():
        dist = _haversine_m(seg_lat, seg_lon, outage["lat"], outage["lon"])
        if dist < outage["radius_m"]:
            # Soft falloff: penalty=1 at center, 0 at boundary
            penalty = 1.0 - (dist / outage["radius_m"])
            max_penalty = max(max_penalty, penalty)

    return max_penalty
