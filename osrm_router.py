import requests
import time


OSRM_BASE = "http://router.project-osrm.org/route/v1/driving"


def get_road_route(start: tuple, end: tuple, retries: int = 2) -> list:
    """
    Fetch a road-following polyline from OSRM between two (lat, lon) points.
    Returns list of (lat, lon) tuples, or [] on failure (caller should use straight line).
    """
    url = (
        f"{OSRM_BASE}/{start[1]},{start[0]};{end[1]},{end[0]}"
        f"?overview=full&geometries=geojson"
    )

    for attempt in range(retries):
        try:
            resp = requests.get(url, timeout=5)
            if resp.status_code != 200:
                break
            data = resp.json()
            if "routes" not in data or not data["routes"]:
                break
            coords = data["routes"][0]["geometry"]["coordinates"]
            return [(lat, lon) for lon, lat in coords]
        except requests.exceptions.Timeout:
            time.sleep(0.5)
        except Exception as e:
            print(f"OSRM error: {e}")
            break

    return []  # Fallback to caller