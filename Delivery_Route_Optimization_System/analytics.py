import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from geopy.distance import geodesic


def build_vehicle_summary(vehicle_routes: dict, distances: dict) -> pd.DataFrame:
    """Return a per-vehicle summary DataFrame."""
    rows = []
    for vid, route in vehicle_routes.items():
        total_weight = sum(o.get("weight", 0) for o in route)
        order_ids = [int(o.get("order_id", -1)) for o in route]
        rows.append({
            "Vehicle": f"Vehicle {vid + 1}",
            "Stops": len(route),
            "Total Weight (kg)": total_weight,
            "Distance (km)": round(distances.get(vid, 0), 2),
            "Orders": ", ".join(map(str, order_ids)),
        })
    return pd.DataFrame(rows)


def plot_distance_bar(summary_df: pd.DataFrame) -> go.Figure:
    fig = px.bar(
        summary_df,
        x="Vehicle", y="Distance (km)",
        color="Vehicle",
        title="Distance per Vehicle",
        text="Distance (km)",
        template="plotly_white"
    )
    fig.update_traces(textposition="outside")
    return fig


def plot_weight_pie(summary_df: pd.DataFrame) -> go.Figure:
    fig = px.pie(
        summary_df,
        names="Vehicle",
        values="Total Weight (kg)",
        title="Load Distribution",
        hole=0.4,
        template="plotly_white"
    )
    return fig


def plot_priority_breakdown(orders: pd.DataFrame) -> go.Figure:
    if "priority" not in orders.columns:
        return go.Figure()
    counts = orders["priority"].value_counts().reset_index()
    counts.columns = ["Priority", "Count"]
    color_map = {"high": "#e74c3c", "medium": "#f39c12", "low": "#2ecc71"}
    fig = px.bar(
        counts, x="Priority", y="Count",
        color="Priority",
        color_discrete_map=color_map,
        title="Orders by Priority",
        template="plotly_white"
    )
    return fig


def compute_route_coords(warehouse: tuple, route: list) -> list:
    """Return list of (lat, lon) for the full route including warehouse."""
    coords = [warehouse]
    for o in route:
        coords.append((o["latitude"], o["longitude"]))
    coords.append(warehouse)
    return coords


def compute_segment_distances(route_coords: list) -> list:
    """Return list of km distances for each leg."""
    dists = []
    for i in range(len(route_coords) - 1):
        dists.append(round(geodesic(route_coords[i], route_coords[i + 1]).km, 2))
    return dists