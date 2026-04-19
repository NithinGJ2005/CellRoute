import osmnx as ox
import pandas as pd
import numpy as np
import os

def load_towers():
    print("Downloading REAL communication towers for Bangalore from OpenStreetMap...")
    ox.settings.use_cache = True
    tags = {
        'man_made': ['mast', 'tower', 'communications_tower'],
        'tower:type': 'communication'
    }
    
    # Using the features module to grab live geometries
    gdf = ox.features_from_place("Bangalore, India", tags)
    print(f"Found {len(gdf)} real physical tower features.")
    
    # Convert polygons to centroids for distance mapping
    if not gdf.empty:
        gdf["geometry"] = gdf["geometry"].centroid
        
    df = pd.DataFrame({
        "lat": gdf.geometry.y,
        "lon": gdf.geometry.x,
    })
    
    # Since actual 5G/4G bandwidth frequencies are rarely manually typed into OSM by volunteers,
    # we mathematically distribute modern radio network params over the real coordinates.
    num_towers = len(df)
    np.random.seed(42) # Deterministic assignments for presentation
    radios = np.random.choice(["NR", "LTE", "GSM", "UMTS"], size=num_towers, p=[0.5, 0.35, 0.1, 0.05])
    df["radio"] = radios
    df["range"] = np.random.randint(500, 3000, size=num_towers)
    df["confidence"] = np.random.uniform(0.7, 1.0, size=num_towers)
    df["has_edge_upf"] = False
    
    nr_indices = df[df["radio"] == "NR"].index
    if len(nr_indices) > 0:
        edge_indices = np.random.choice(nr_indices, size=int(len(nr_indices)*0.3), replace=False)
        df.loc[edge_indices, "has_edge_upf"] = True
        
    radio_weight = {"NR": 1.0, "LTE": 0.9, "UMTS": 0.65, "GSM": 0.3}
    df["radio_weight"] = df["radio"].map(radio_weight).fillna(0.3)
    
    out_path = os.path.join(os.path.dirname(__file__), "towers_blr.parquet")
    df.to_parquet(out_path, index=False)
    print(f"Successfully scraped and saved {num_towers} physical OSM towers to {out_path}!")
    return df

if __name__ == "__main__":
    load_towers()
