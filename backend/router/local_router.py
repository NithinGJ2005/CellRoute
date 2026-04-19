import networkx as nx
import geopandas as gpd
import numpy as np
from scipy.spatial import cKDTree
import os
import polyline
from router.outage_manager import get_outage_penalty
from router.waypoint_scorer import ISP_BONUS

G = None
node_coords = None
kdtree = None
node_list = []

def init_graph():
    global G, node_coords, kdtree, node_list
    parquet_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "scored_segments_blr.parquet")
    if not os.path.exists(parquet_path):
        return
        
    print("Loading static KD-Tree network graph into memory...")
    df = gpd.read_parquet(parquet_path)
    
    G = nx.from_pandas_edgelist(
        df, 'u', 'v', 
        edge_attr=['length_m', 'travel_time_s', 'conn_score', 'edge_score', 'geometry', 'name'], 
        create_using=nx.MultiDiGraph()
    )
    
    # Harvest node locations from geometries to allow lon/lat snapping
    coords_dict = {}
    for i, row in df.iterrows():
        geom = row['geometry']
        if geom:
            coords_dict[row['u']] = geom.coords[0]
            coords_dict[row['v']] = geom.coords[-1]
            
    node_list = list(coords_dict.keys())
    pts = [coords_dict[n] for n in node_list]
    kdtree = cKDTree(pts)
    node_coords = coords_dict
    print("NetworkX graph successfully booted and ready for routing!")

def get_nearest_node(lon, lat):
    if kdtree is None:
        init_graph()
        if kdtree is None: return None
    
    pt = np.array([lon, lat])
    # Search for top 3 nodes to ensure we don't snap to an island
    dists, idxs = kdtree.query(pt, k=5)
    return node_list[idxs[0]]

def get_local_route(start_lon, start_lat, end_lon, end_lat, alpha, edge_weight=0.0, isp="all"):
    start_node = get_nearest_node(start_lon, start_lat)
    end_node = get_nearest_node(end_lon, end_lat)
    
    if start_node is None or end_node is None:
        return {"error": "Snap failed: Coordinates are too far from the road network."}

    # Our custom heuristic: Trade off connectivity penalty with ETA
    def travel_weight(u, v, d):
        attr = list(d.values())[0]  # multigraph
        eta = attr.get('travel_time_s', 15)
        conn = attr.get('conn_score', 0.5)
        
        # Apply ISP Bonus
        isp_factor = ISP_BONUS.get(isp.lower(), ISP_BONUS["default"])
        conn = min(conn * isp_factor, 1.0)
        
        edge_score = attr.get('edge_score', 0.0)
        # alpha=0 -> strictly ETA. alpha=1 -> strictly connectivity penalty
        norm_eta = min(eta / 30.0, 1.0)
        penalty = 1.0 - conn
        base_cost = (alpha * penalty) + ((1.0 - alpha) * norm_eta)

        if edge_weight > 0:
            base_cost = (1 - edge_weight) * base_cost + (edge_weight * (1 - edge_score))

        # ── Closed-Loop Assurance: avoid outage zones ──────────────────────
        # Extract the midpoint of this edge from the geometry for outage check
        geom = attr.get('geometry')
        if geom:
            mid = geom.interpolate(0.5, normalized=True)
            outage_penalty = get_outage_penalty(mid.y, mid.x)
            if outage_penalty > 0:
                # Apply exponential cost explosion so Dijkstra strongly avoids the zone
                # penalty=1.0 (center) → cost multiplier ×50; penalty=0.5 → ×6
                base_cost = base_cost * (1 + 49 * (outage_penalty ** 2))
        # ──────────────────────────────────────────────────────────────────

        return base_cost
        
    try:
        path = nx.shortest_path(G, source=start_node, target=end_node, weight=travel_weight)
    except nx.NetworkXNoPath:
        return {"error": "Graph Disconnected: No drivable path found between these points."}
    except Exception as e:
        return {"error": f"Routing Engine Error: {str(e)}"}
        
    # Reconstruct the geometry
    raw_coords = []
    total_time = 0
    total_dist = 0
    segment_scores = []
    deadzone_count = 0
    conn_sum = 0
    road_names_dist = {} # name -> total distance
    
    for i in range(len(path)-1):
        u = path[i]
        v = path[i+1]
        edges_dict = G.get_edge_data(u, v)
        attr = list(edges_dict.values())[0]
        
        geom = attr['geometry']
        raw_coords.extend(list(geom.coords))
        
        total_time += attr['travel_time_s']
        total_dist += attr['length_m']
        
        c_score = attr['conn_score']
        segment_scores.append(round(c_score, 3))
        conn_sum += c_score
        
        # Track road names for primary labeling
        r_name = attr.get('name')
        if r_name and isinstance(r_name, str) and r_name != "Unknown Road":
            dist = attr['length_m']
            road_names_dist[r_name] = road_names_dist.get(r_name, 0) + dist
            
        if c_score < 0.2:
            deadzone_count += 1
            
    # Flip coords for OSRM format (lat, lon)
    flipped = [(lat, lon) for lon, lat in raw_coords]
    poly = polyline.encode(flipped)
    
    num_segs = max(len(segment_scores), 1)
    avg_conn = round((conn_sum / num_segs) * 100)
    
    # Determine primary road (most distance on named roads)
    if road_names_dist:
        # Filter out 'nan' or generic names if others exist
        named_roads = {k: v for k, v in road_names_dist.items() if k and str(k).lower() != 'nan'}
        if named_roads:
            primary_road = max(named_roads, key=named_roads.get)
        else:
            primary_road = "Optimized Urban Path"
    else:
        primary_road = "Optimized Urban Path"

    # Return matched API signature
    return {
        "geometry": poly,
        "duration": total_time,
        "distance": total_dist,
        "connectivity_score": avg_conn,
        "deadzone_count": deadzone_count,
        "segment_scores": segment_scores,
        "primary_road": primary_road
    }

init_graph()
