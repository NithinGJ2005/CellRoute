import geopandas as gpd
import pandas as pd
import numpy as np
from shapely.geometry import Point
from scipy.spatial import cKDTree
import os
import json

# ── Signal propagation constants (log-distance path loss model)
# RSRP(dBm) = P_tx - 20*log10(d_m) - 32.4 - 20*log10(f_MHz)
# For LTE ~1800MHz: path_loss_exponent ≈ 3.5 in urban
TX_POWER_DBM = 46      # typical eNB transmit power
FREQ_MHZ     = 1800    # LTE Band 3 (dominant in India)
PL_EXPONENT  = 3.5     # urban path loss exponent

def get_data_path(filename):
    return os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", filename)

def rsrp_at_distance(dist_m: float, radio_weight: float) -> float:
    """Returns normalized signal quality 0-1 at a given distance from tower."""
    if dist_m < 1: dist_m = 1
    pl = 20 * np.log10(dist_m) + 32.4 + 20 * np.log10(FREQ_MHZ)
    rsrp = TX_POWER_DBM - pl * (PL_EXPONENT / 2)  # simplified
    # Typical usable range: -140 dBm (dead) to -80 dBm (excellent)
    normalized = np.clip((rsrp + 140) / 60, 0, 1)
    return float(normalized * radio_weight)

def score_segments(
    roads_path=None,
    towers_path=None,
    ookla_path=None,
    alpha_tower=0.5,   # weight for tower-based score
    alpha_ookla=0.5,   # weight for OOKLA speed score
):
    if roads_path is None: roads_path = get_data_path("roads_blr.parquet")
    if towers_path is None: towers_path = get_data_path("towers_blr.parquet")
    if ookla_path is None: ookla_path = get_data_path("ookla_blr.parquet")

    print("Loading data sets...")
    try:
        roads  = gpd.read_parquet(roads_path)
        if hasattr(roads, 'set_crs') and roads.crs is None: roads = roads.set_crs("EPSG:4326")
        
        towers = pd.read_parquet(towers_path)
        
        ookla  = gpd.read_parquet(ookla_path)
        if hasattr(ookla, 'set_crs') and ookla.crs is None: ookla = ookla.set_crs("EPSG:4326")
    except Exception as e:
        print(f"Error loading parquets. Ensure you ran the ingestion scripts first: {e}")
        return None

    # Build KD-tree on towers for fast nearest-neighbor lookup
    tower_coords = np.column_stack([towers["lon"].values, towers["lat"].values])
    tree = cKDTree(tower_coords)

    # Load and build KD-Tree for Traffic Congestion nodes
    traffic_path = get_data_path("congestion_nodes.json")
    traffic_tree = None
    if os.path.exists(traffic_path):
        with open(traffic_path, "r") as f:
            traffic_data = json.load(f)
            if traffic_data:
                # traffic_data is [[lat, lon], ...] -> turn to [lon, lat] for queries
                traffic_coords = np.array([[pt[1], pt[0]] for pt in traffic_data])
                traffic_tree = cKDTree(traffic_coords)

    print("Scoring road segments...")
    scores = []
    
    # Precompute ookla boundaries for faster spatial join
    # SJoin can be slow, so instead we'll sjoin all midpoints at once safely.
    # To keep it memory efficient, we can batch it or just follow the user logic.
    midpoints = roads.geometry.interpolate(0.5, normalized=True)
    mid_gdf = gpd.GeoDataFrame(geometry=midpoints, crs="EPSG:4326")
    
    # Fast vectorized OOKLA join
    joined = gpd.sjoin(mid_gdf, ookla[["geometry","ookla_score"]], how="left")
    # A single road might clip multiple tiles. Take the first.
    joined = joined[~joined.index.duplicated(keep='first')]

    print("Executing Vectorized Connectivity Scoring (Nearest 5)...")
    
    # 1. Coordinate array from all midpoints
    coords = np.column_stack([midpoints.x.values, midpoints.y.values])
    
    # 2. Vectorized KD-Tree query for N-5 neighbors (approx 3km bound)
    # This replaces the i-loop call to tree.query()
    dists_deg, idxs = tree.query(coords, k=5, distance_upper_bound=0.027)
    
    # 3. Handle masked indices (where dist > distance_upper_bound)
    # tree.query returns len(towers) as index for invalid points
    valid_mask = idxs < len(towers)
    
    # 4. Extract tower features for all neighbors
    radio_weights = np.zeros_like(idxs, dtype=float)
    confidences   = np.zeros_like(idxs, dtype=float)
    has_edge      = np.zeros_like(idxs, dtype=bool)
    
    # Fill only valid indices
    flat_idxs = idxs[valid_mask]
    radio_weights[valid_mask] = towers["radio_weight"].values[flat_idxs]
    confidences[valid_mask]   = towers["confidence"].values[flat_idxs]
    if "has_edge_upf" in towers.columns:
        has_edge[valid_mask] = towers["has_edge_upf"].values[flat_idxs]
        
    # 5. Vectorized RSRP physics calculation
    dists_m = dists_deg * 111_000
    dists_m = np.maximum(dists_m, 1.0)
    
    # RSRP(dBm) = TX_POWER_DBM - (20*log10(d) + 32.4 + 20*log10(f)) * (exponent/2)
    # We use path_loss(d) = 20*log10(d) + 32.4 + 20*log10(FREQ_MHZ)
    log_dist = np.log10(dists_m)
    path_loss = 20 * log_dist + 32.4 + 20 * np.log10(FREQ_MHZ)
    rsrp = TX_POWER_DBM - path_loss * (PL_EXPONENT / 2)
    
    # Normalized 0-1 (from -140 dead to -80 excellent)
    normalized = np.clip((rsrp + 140) / 60, 0, 1)
    signals = normalized * radio_weights * confidences
    
    # Zero out invalid neighbors
    signals[~valid_mask] = 0
    
    # 6. Mean scoring across the 5 neighbors
    count_valid = valid_mask.sum(axis=1)
    tower_scores = np.divide(signals.sum(axis=1), np.maximum(count_valid, 1))
    tower_scores = np.minimum(tower_scores, 1.0)
    
    # 7. Edge UPF Score (Max signal among neighbors with Edge UPF)
    edge_signals = signals.copy()
    edge_signals[~has_edge] = 0
    edge_scores = edge_signals.max(axis=1)

    # 8. OOKLA Component
    o_scores = joined["ookla_score"].values
    ookla_scores = np.where(pd.notna(o_scores), o_scores, tower_scores)
    
    # 9. Traffic Penalties
    travel_times = roads["travel_time_s"].values.astype(float)
    if traffic_tree is not None:
        traffic_dists, _ = traffic_tree.query(coords, k=1, distance_upper_bound=0.00045)
        jam_mask = traffic_dists != np.inf
        travel_times[jam_mask] *= 2.5

    # 10. Composite Connectivity
    conn_scores = alpha_tower * tower_scores + alpha_ookla * ookla_scores

    # Build final list
    final_output = pd.DataFrame({
        "u": roads["u"].values,
        "v": roads["v"].values,
        "name": roads["name"].values if "name" in roads.columns else "Unknown Road",
        "length_m": roads["length"].values,
        "travel_time_s": np.round(travel_times, 2),
        "tower_score": np.round(tower_scores, 4),
        "ookla_score": np.round(ookla_scores, 4),
        "conn_score": np.round(conn_scores, 4),
        "edge_score": np.round(edge_scores, 4),
        "geometry": roads.geometry.values
    })

    result = gpd.GeoDataFrame(final_output, crs="EPSG:4326")
    out_path = get_data_path("scored_segments_blr.parquet")
    result.to_parquet(out_path, index=False)

    print(f"Scored {len(result)} segments to {out_path}. Mean conn_score: {result['conn_score'].mean():.3f}")
    return result

if __name__ == "__main__":
    score_segments()
