def calculate_alpha_score(alpha: float, route_duration: float, min_duration: float, max_duration: float, connectivity: float):
    """
    Combines routing ETA and connectivity connectivity index using alpha.
    
    alpha = 0.0 -> 100% ETA Optimization
    alpha = 1.0 -> 100% Connectivity Optimization
    """
    
    # Normalize duration (efficiency). 1.0 is max efficiency (fastest route).
    # If all routes have same duration, efficiency is 1.0
    if max_duration > min_duration:
        # Smaller duration means higher efficiency ( closer to 1.0 )
        efficiency = 1.0 - ((route_duration - min_duration) / (max_duration - min_duration))
    else:
        efficiency = 1.0
        
    composite_score = (alpha * connectivity) + ((1.0 - alpha) * efficiency)
    return composite_score

def rank_routes(routes, alpha: float):
    """
    Processes routes returned by OSRM, calculates composite score, and sorts them.
    """
    if not list(routes):
        return []
        
    # Extract durations
    durations = [r.get("duration", 0) for r in routes]
    min_d = min(durations) if durations else 0
    max_d = max(durations) if durations else 1 # avoid divide by zero if 0
    
    for route in routes:
        connectivity = route.get("connectivity_score", 0.0)
        route_duration = route.get("duration", 0)
        route["composite_score"] = calculate_alpha_score(alpha, route_duration, min_d, max_d, connectivity)
        
    # Sort by descending composite_score
    return sorted(routes, key=lambda x: x.get("composite_score", 0.0), reverse=True)
