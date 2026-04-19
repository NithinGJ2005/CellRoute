import requests, geopandas as gpd
from shapely.geometry import LineString
import json
import os

def fetch_overpass_traffic():
    """Fetch known slow roads: traffic signals, bus routes, junctions"""
    bbox_str = "12.834,77.460,13.139,77.752"
    query = f"""
    [out:json][timeout:60];
    (
      way["highway"]["traffic_calming"]({bbox_str});
      way["highway"]["junction"="roundabout"]({bbox_str});
      node["highway"="traffic_signals"]({bbox_str});
    );
    out body geom;
    """
    print("Calling Overpass API...")
    r = requests.post("https://overpass-api.de/api/interpreter", data={"data": query})
    data = r.json()
    
    congestion_nodes = set()
    for el in data["elements"]:
        if el["type"] == "node":
            congestion_nodes.add((round(el["lat"],5), round(el["lon"],5)))
    
    print(f"Found {len(congestion_nodes)} congestion points (signals, calming, roundabouts)")
    
    out_path = os.path.join(os.path.dirname(__file__), "congestion_nodes.json")
    with open(out_path, "w") as f:
        json.dump(list(congestion_nodes), f)
    return congestion_nodes

if __name__ == "__main__":
    fetch_overpass_traffic()
