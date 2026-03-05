import random
from datetime import datetime


def predict_traffic_factor(hour: int = None) -> float:
    """
    Returns a traffic multiplier based on hour of day.
    If hour is None, uses current system time.
    """
    if hour is None:
        hour = datetime.now().hour

    if 7 <= hour <= 9 or 17 <= hour <= 19:
        return 1.6   # peak rush hour
    elif 10 <= hour <= 16:
        return 1.2   # moderate daytime traffic
    elif 20 <= hour <= 22:
        return 1.1   # evening
    else:
        return 1.0   # off-peak / night


def get_traffic_label(factor: float) -> str:
    if factor >= 1.5:
        return "🔴 Heavy Traffic"
    elif factor >= 1.2:
        return "🟡 Moderate Traffic"
    else:
        return "🟢 Light Traffic"


def simulate_live_position(route, progress_fraction: float):
    """
    Given a route (list of order dicts) and a progress fraction [0,1],
    returns the (lat, lon) of the simulated vehicle position.
    progress_fraction=0 → warehouse start, =1 → last stop.
    """
    if not route or progress_fraction <= 0:
        return None

    idx = min(int(progress_fraction * len(route)), len(route) - 1)
    order = route[idx]
    return (order["latitude"], order["longitude"])


def estimate_eta(distance_km: float, speed_kmh: float, traffic_factor: float) -> float:
    """Returns estimated time in hours."""
    if speed_kmh <= 0:
        return float("inf")
    return (distance_km / speed_kmh) * traffic_factor