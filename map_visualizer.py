import folium
from folium.plugins import AntPath, MarkerCluster
from osrm_router import get_road_route

VEHICLE_COLORS = [
    "red", "blue", "purple", "orange",
    "darkred", "cadetblue", "darkgreen", "pink"
]


def create_map(warehouse: tuple, vehicle_routes: dict,
               delivered: dict = None, live_positions: dict = None) -> folium.Map:
    """
    Build and return a Folium map.

    Args:
        warehouse:      (lat, lon) of the depot/warehouse.
        vehicle_routes: {vehicle_id: [list of order dicts]}
        delivered:      {order_id: True/False} — marks delivered orders differently.
        live_positions: {vehicle_id: (lat, lon)} — current simulated vehicle positions.
    """
    delivered = delivered or {}
    live_positions = live_positions or {}

    m = folium.Map(location=warehouse, zoom_start=12, tiles="CartoDB positron")

    # ── Warehouse marker ──────────────────────────────────────────────────────
    folium.Marker(
        location=warehouse,
        popup=folium.Popup("<b>🏭 Warehouse / Depot</b>", max_width=200),
        tooltip="Warehouse",
        icon=folium.Icon(color="green", icon="home", prefix="fa")
    ).add_to(m)

    # ── Per-vehicle routes ────────────────────────────────────────────────────
    for vehicle_id, route in vehicle_routes.items():
        color = VEHICLE_COLORS[vehicle_id % len(VEHICLE_COLORS)]
        prev = warehouse

        # Feature group per vehicle so they can be toggled
        fg = folium.FeatureGroup(name=f"Vehicle {vehicle_id + 1}", show=True)

        for order in route:
            loc = (order["latitude"], order["longitude"])
            oid = int(order.get("order_id", 0))
            addr = order.get("address", "")
            priority = order.get("priority", "medium")
            weight = order.get("weight", "?")
            is_done = delivered.get(oid, False)

            # Marker icon
            icon_color = "lightgray" if is_done else color
            icon_symbol = "check" if is_done else "shopping-cart"

            popup_html = f"""
            <div style='font-family:Arial;min-width:160px'>
              <b>Order #{oid}</b><br>
              📍 {addr}<br>
              ⚖️ Weight: {weight} kg<br>
              🎯 Priority: {priority.upper()}<br>
              {'✅ Delivered' if is_done else '⏳ Pending'}
            </div>"""

            folium.Marker(
                location=loc,
                popup=folium.Popup(popup_html, max_width=220),
                tooltip=f"Order #{oid} ({priority})",
                icon=folium.Icon(color=icon_color, icon=icon_symbol, prefix="fa")
            ).add_to(fg)

            # Road route (OSRM) with straight-line fallback
            road = get_road_route(prev, loc)
            if not road:
                road = [prev, loc]

            AntPath(
                locations=road,
                color=color,
                weight=4,
                opacity=0.75,
                delay=800,
                tooltip=f"Vehicle {vehicle_id + 1} route"
            ).add_to(fg)

            prev = loc

        # Return to warehouse leg (dashed)
        return_road = get_road_route(prev, warehouse)
        if not return_road:
            return_road = [prev, warehouse]
        folium.PolyLine(
            locations=return_road,
            color=color,
            weight=2,
            dash_array="8 4",
            opacity=0.5,
            tooltip=f"Vehicle {vehicle_id + 1} return"
        ).add_to(fg)

        # ── Live vehicle position ─────────────────────────────────────────────
        if vehicle_id in live_positions:
            vloc = live_positions[vehicle_id]
            folium.Marker(
                location=vloc,
                popup=f"🚚 Vehicle {vehicle_id + 1} — Live",
                tooltip=f"Vehicle {vehicle_id + 1} (Live)",
                icon=folium.DivIcon(
                    html=f"""
                    <div style="
                        background:{color};
                        border:2px solid white;
                        border-radius:50%;
                        width:22px; height:22px;
                        display:flex; align-items:center;
                        justify-content:center;
                        font-size:12px; color:white;
                        box-shadow:0 2px 6px rgba(0,0,0,.4)">
                      🚚
                    </div>""",
                    icon_size=(22, 22),
                    icon_anchor=(11, 11)
                )
            ).add_to(fg)

        fg.add_to(m)

    folium.LayerControl(collapsed=False).add_to(m)
    return m


def create_heatmap_layer(m: folium.Map, orders) -> folium.Map:
    """Add a heatmap layer based on order weight/density."""
    from folium.plugins import HeatMap
    heat_data = [
        [row["latitude"], row["longitude"], row.get("weight", 1)]
        for _, row in orders.iterrows()
    ]
    HeatMap(heat_data, radius=25, blur=15, name="Delivery Density Heatmap").add_to(m)
    return m