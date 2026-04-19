import httpx
import logging

logger = logging.getLogger(__name__)

OSRM_BASE_URL = "http://router.project-osrm.org/route/v1/driving"

async def get_routes(start_lon: float, start_lat: float, end_lon: float, end_lat: float, alternatives: int = 3):
    """
    Fetches driving routes from the public OSRM demonstration server.
    IMPORTANT: Public server usage should be limited. For production, host OSRM locally.
    """
    url = f"{OSRM_BASE_URL}/{start_lon},{start_lat};{end_lon},{end_lat}"
    
    params = {
        "alternatives": str(alternatives) if alternatives > 1 else "false",
        "steps": "true",
        "geometries": "polyline",
        "overview": "full",
        "annotations": "true"
    }
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            if data.get("code") != "Ok":
                logger.error(f"OSRM Error: {data.get('code')}")
                return None
                
            return data.get("routes", [])
            
        except httpx.RequestError as e:
            logger.error(f"Error connecting to OSRM: {e}")
            return None
