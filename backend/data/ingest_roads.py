import osmnx as ox
import geopandas as gpd
import pandas as pd
import os

def load_road_graph():
    ox.settings.use_cache = True
    print("Downloading Bangalore drive network from OSM...")
    G = ox.graph_from_place("Bangalore, India", network_type="drive")
    
    # Convert to GeoDataFrame of edges (each edge = a road segment)
    nodes, edges = ox.graph_to_gdfs(G)
    
    # Keep only useful columns
    edges = edges[["geometry", "length", "highway", "name", "maxspeed", "oneway"]].copy()
    
    # Road type speed reference (fallback if maxspeed missing)
    speed_ref = {
        "motorway": 80, "trunk": 60, "primary": 50,
        "secondary": 40, "tertiary": 30, "residential": 20,
        "unclassified": 25, "service": 15
    }
    def parse_highway(h):
        if isinstance(h, list): h = h[0]
        return speed_ref.get(h, 25)
    
    def parse_speed(x):
        if isinstance(x, list): x = x[0]
        if pd.isna(x): return None
        try:
            return float(str(x).split()[0])
        except Exception:
            return None
            
    edges["speed_kmh"] = edges["maxspeed"].apply(parse_speed).fillna(edges["highway"].apply(parse_highway))
    
    edges["travel_time_s"] = (edges["length"] / 1000) / edges["speed_kmh"] * 3600
    
    edges = edges.reset_index()  # brings u, v, key as columns
    
    # Cast all object columns (like lists of highway names) to string to prevent Parquet crashes
    for col in edges.columns:
        if edges[col].dtype == object and col != "geometry":
            edges[col] = edges[col].astype(str)
            
    out_path = os.path.join(os.path.dirname(__file__), "roads_blr.parquet")
    edges.to_parquet(out_path, index=False)
    print(f"Saved {len(edges)} road segments to {out_path}")
    return edges

if __name__ == "__main__":
    load_road_graph()
