"""
Delivery Route Optimization Dashboard
======================================
Run:  streamlit run app.py
"""

import os
import time
import pandas as pd
import streamlit as st
import folium
from streamlit_folium import st_folium
from datetime import datetime

from optimizer import nearest_neighbor, two_opt_improve
from map_visualizer import create_map, create_heatmap_layer
from vehicle_allocator import allocate_by_capacity, get_vehicle_stats
from traffic_model import predict_traffic_factor, get_traffic_label, estimate_eta
from analytics import (
    build_vehicle_summary, plot_distance_bar,
    plot_weight_pie, plot_priority_breakdown, compute_route_coords
)

# ─────────────────────────── Page Config ────────────────────────────────────
st.set_page_config(
    page_title="Delivery Route Optimizer",
    page_icon="🚚",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ─────────────────────────── Custom CSS ─────────────────────────────────────
st.markdown("""
<style>
  .metric-card {
      background: #f0f2f6; border-radius: 12px;
      padding: 16px 20px; text-align: center;
      box-shadow: 0 2px 8px rgba(0,0,0,.08);
  }
  .metric-card h2 { margin:0; font-size:2rem; color:#1f77b4; }
  .metric-card p  { margin:4px 0 0; color:#555; font-size:.9rem; }
  .status-delivered { color:#27ae60; font-weight:bold; }
  .status-pending   { color:#e67e22; font-weight:bold; }
  .banner {
      background:linear-gradient(135deg,#1f77b4,#2ecc71);
      color:white; border-radius:14px; padding:20px 28px;
      margin-bottom:20px;
  }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────── Constants ──────────────────────────────────────
WAREHOUSE = (13.0827, 80.2707)
DATASET_PATH = os.path.join(os.path.dirname(__file__), "dataset", "orders.csv")
OUTPUT_DIR   = os.path.join(os.path.dirname(__file__), "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ─────────────────────────── Session State ──────────────────────────────────
def _init_state():
    defaults = {
        "delivered":       {},
        "live_step":       {},
        "simulation_on":   False,
        "vehicle_routes":  {},
        "vehicle_dists":   {},
        "orders":          None,
        "optimized":       False,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

_init_state()

# ─────────────────────────── Sidebar ────────────────────────────────────────
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/delivery-truck.png", width=72)
    st.title("⚙️ Settings")

    st.markdown("### 📂 Data Source")
    upload = st.file_uploader("Upload your orders CSV", type=["csv"])
    if upload:
        orders = pd.read_csv(upload)
        st.session_state["orders"] = orders
        st.success(f"Loaded {len(orders)} orders from upload")
    else:
        orders = pd.read_csv(DATASET_PATH)
        st.session_state["orders"] = orders

    st.markdown("---")
    st.markdown("### 🚛 Vehicle Config")
    vehicle_capacity  = st.slider("Vehicle Capacity (kg)", 1, 20, 5)
    vehicle_speed     = st.slider("Avg Speed (km/h)", 10, 80, 40)
    use_two_opt       = st.checkbox("Enable 2-opt Improvement", value=True)
    use_priority_sort = st.checkbox("Priority-aware Routing", value=True)

    st.markdown("---")
    st.markdown("### 🕐 Traffic")
    manual_hour = st.slider("Simulate Hour of Day", 0, 23, datetime.now().hour)
    traffic_factor = predict_traffic_factor(manual_hour)
    st.info(f"{get_traffic_label(traffic_factor)}  (×{traffic_factor})")

    st.markdown("---")
    run_btn = st.button("🚀 Optimize Routes", use_container_width=True, type="primary")

orders = st.session_state["orders"]

# ─────────────────────────── Banner ─────────────────────────────────────────
st.markdown("""
<div class='banner'>
  <h2 style='margin:0'>🚚 Delivery Route Optimization System</h2>
  <p style='margin:4px 0 0;opacity:.85'>
    Intelligent multi-vehicle routing with live simulation, traffic modelling & analytics
  </p>
</div>
""", unsafe_allow_html=True)

# ─────────────────────────── Tabs ───────────────────────────────────────────
tab_orders, tab_map, tab_live, tab_analytics, tab_report = st.tabs([
    "📦 Orders", "🗺️ Route Map", "📡 Live Tracking", "📊 Analytics", "📋 Report"
])

# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — ORDERS
# ══════════════════════════════════════════════════════════════════════════════
with tab_orders:
    st.subheader("📦 Order Dataset")

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Orders",  len(orders))
    col2.metric("Total Weight",  f"{orders['weight'].sum()} kg")
    if "priority" in orders.columns:
        col3.metric("High Priority", int((orders["priority"] == "high").sum()))

    st.dataframe(orders, use_container_width=True, hide_index=True)

    st.markdown("#### ➕ Add a New Order")
    with st.expander("Add order manually"):
        c1, c2, c3, c4 = st.columns(4)
        new_lat  = c1.number_input("Latitude",  value=13.07, format="%.4f")
        new_lon  = c2.number_input("Longitude", value=80.25, format="%.4f")
        new_wt   = c3.number_input("Weight (kg)", value=1, min_value=1)
        new_pri  = c4.selectbox("Priority", ["high", "medium", "low"])
        new_addr = st.text_input("Address / Label", value="New Location")
        if st.button("Add Order"):
            new_row = {
                "order_id": int(orders["order_id"].max()) + 1,
                "latitude": new_lat, "longitude": new_lon,
                "weight": new_wt, "priority": new_pri,
                "address": new_addr,
                "time_window_start": "09:00", "time_window_end": "18:00"
            }
            st.session_state["orders"] = pd.concat(
                [orders, pd.DataFrame([new_row])], ignore_index=True
            )
            st.success("Order added! Re-run optimization.")
            st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# OPTIMIZATION TRIGGER
# ══════════════════════════════════════════════════════════════════════════════
if run_btn:
    with st.spinner("Optimizing routes…"):
        orders = st.session_state["orders"]
        vehicles = allocate_by_capacity(orders, vehicle_capacity)

        vehicle_routes = {}
        vehicle_dists  = {}

        for i, vehicle_orders in enumerate(vehicles):
            df = pd.DataFrame(vehicle_orders)
            route, dist = nearest_neighbor(WAREHOUSE, df)

            if use_two_opt and len(route) > 2:
                route, dist = two_opt_improve(WAREHOUSE, route)

            vehicle_routes[i] = route
            vehicle_dists[i]  = dist

        st.session_state["vehicle_routes"] = vehicle_routes
        st.session_state["vehicle_dists"]  = vehicle_dists
        st.session_state["delivered"]      = {}
        st.session_state["live_step"]      = {i: 0 for i in vehicle_routes}
        st.session_state["optimized"]      = True

    st.success(f"✅ Optimized {len(vehicle_routes)} vehicle route(s)!")

vehicle_routes = st.session_state["vehicle_routes"]
vehicle_dists  = st.session_state["vehicle_dists"]
delivered      = st.session_state["delivered"]

# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — ROUTE MAP
# ══════════════════════════════════════════════════════════════════════════════
with tab_map:
    st.subheader("🗺️ Optimized Route Map")

    if not vehicle_routes:
        st.info("👈 Configure settings and click **Optimize Routes** to generate the map.")
    else:
        total_dist = sum(vehicle_dists.values())
        total_eta  = estimate_eta(total_dist, vehicle_speed, traffic_factor)

        k1, k2, k3, k4 = st.columns(4)
        k1.metric("🚚 Vehicles",       len(vehicle_routes))
        k2.metric("📏 Total Distance", f"{round(total_dist, 2)} km")
        k3.metric("⏱️ Est. Time",      f"{round(total_eta, 2)} hrs")
        k4.metric("🚦 Traffic",        get_traffic_label(traffic_factor))

        show_heat = st.checkbox("Show Delivery Density Heatmap", value=False)

        orders_data = st.session_state["orders"]
        m = create_map(WAREHOUSE, vehicle_routes, delivered=delivered)
        if show_heat:
            m = create_heatmap_layer(m, orders_data)

        map_path = os.path.join(OUTPUT_DIR, "route_map.html")
        m.save(map_path)

        st_folium(m, width=None, height=580, returned_objects=[])

        with open(map_path, "rb") as f:
            st.download_button(
                "⬇️ Download Map HTML", f,
                file_name="route_map.html", mime="text/html"
            )

        st.markdown("#### 🛣️ Route Details")
        for vid, route in vehicle_routes.items():
            stops = " → ".join(
                [f"#{int(o.get('order_id', '?'))}" for o in route]
            )
            st.markdown(
                f"**Vehicle {vid+1}** ({round(vehicle_dists[vid], 2)} km): "
                f"Depot → {stops} → Depot"
            )

# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — LIVE TRACKING
# ══════════════════════════════════════════════════════════════════════════════
with tab_live:
    st.subheader("📡 Live Vehicle Tracking Simulation")

    if not vehicle_routes:
        st.info("Run optimization first to enable live tracking.")
    else:
        col_ctrl1, col_ctrl2 = st.columns([1, 3])

        with col_ctrl1:
            sim_speed = st.selectbox("Simulation Speed", [0.5, 1, 2, 4], index=1)

        with col_ctrl2:
            c1, c2, c3 = st.columns(3)
            start_sim  = c1.button("▶️ Start Simulation")
            pause_sim  = c2.button("⏸️ Pause")
            reset_sim  = c3.button("🔄 Reset")

        if reset_sim:
            st.session_state["live_step"]   = {i: 0 for i in vehicle_routes}
            st.session_state["delivered"]   = {}
            st.session_state["simulation_on"] = False

        if start_sim:
            st.session_state["simulation_on"] = True

        if pause_sim:
            st.session_state["simulation_on"] = False

        # Delivery status panel
        st.markdown("#### 📋 Delivery Status")
        all_orders = [o for route in vehicle_routes.values() for o in route]
        status_cols = st.columns(min(len(all_orders), 4))
        for idx, order in enumerate(all_orders):
            oid = int(order.get("order_id", idx))
            done = delivered.get(oid, False)
            
            status_html = '<span class="status-delivered">✅ Delivered</span>' if done else '<span class="status-pending">⏳ Pending</span>'
            
            status_cols[idx % len(status_cols)].markdown(
                f"**Order #{oid}**<br>{status_html}",
                unsafe_allow_html=True
            )

        # Live map placeholder
        live_map_placeholder = st.empty()
        progress_placeholder = st.empty()

        def render_live_map():
            live_positions = {}
            for vid, route in vehicle_routes.items():
                step = st.session_state["live_step"].get(vid, 0)
                if step < len(route):
                    o = route[step]
                    live_positions[vid] = (o["latitude"], o["longitude"])
                else:
                    live_positions[vid] = WAREHOUSE

            m_live = create_map(
                WAREHOUSE, vehicle_routes,
                delivered=st.session_state["delivered"],
                live_positions=live_positions
            )
            with live_map_placeholder:
                st_folium(m_live, width=None, height=500, returned_objects=[], key="live_map")

        render_live_map()

        # Advance simulation one step at a time
        if st.session_state["simulation_on"]:
            any_moving = False
            for vid, route in vehicle_routes.items():
                step = st.session_state["live_step"].get(vid, 0)
                if step < len(route):
                    # Mark current stop as delivered
                    oid = int(route[step].get("order_id", -1))
                    st.session_state["delivered"][oid] = True
                    st.session_state["live_step"][vid] = step + 1
                    any_moving = True

            time.sleep(max(0.3, 1.0 / sim_speed))

            if any_moving:
                st.rerun()
            else:
                st.session_state["simulation_on"] = False
                st.success("🎉 All deliveries completed!")

        # Progress bars
        st.markdown("#### 📊 Vehicle Progress")
        for vid, route in vehicle_routes.items():
            step = st.session_state["live_step"].get(vid, 0)
            pct  = step / len(route) if route else 1.0
            st.write(f"Vehicle {vid+1}")
            st.progress(min(pct, 1.0))

# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 — ANALYTICS
# ══════════════════════════════════════════════════════════════════════════════
with tab_analytics:
    st.subheader("📊 Route Analytics")

    if not vehicle_routes:
        st.info("Run optimization to see analytics.")
    else:
        summary_df = build_vehicle_summary(vehicle_routes, vehicle_dists)
        st.dataframe(summary_df, use_container_width=True, hide_index=True)

        col_a, col_b = st.columns(2)
        with col_a:
            st.plotly_chart(plot_distance_bar(summary_df), use_container_width=True)
        with col_b:
            st.plotly_chart(plot_weight_pie(summary_df), use_container_width=True)

        orders_data = st.session_state["orders"]
        if "priority" in orders_data.columns:
            st.plotly_chart(
                plot_priority_breakdown(orders_data), use_container_width=True
            )

        st.markdown("#### ⚡ KPI Summary")
        total_dist = sum(vehicle_dists.values())
        avg_dist   = total_dist / len(vehicle_routes) if vehicle_routes else 0
        total_eta  = estimate_eta(total_dist, vehicle_speed, traffic_factor)
        total_wt   = sum(
            o.get("weight", 0)
            for route in vehicle_routes.values()
            for o in route
        )

        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Total Distance",    f"{round(total_dist, 2)} km")
        k2.metric("Avg per Vehicle",   f"{round(avg_dist, 2)} km")
        k3.metric("Est. Total Time",   f"{round(total_eta, 2)} hrs")
        k4.metric("Total Weight Moved",f"{total_wt} kg")

# ══════════════════════════════════════════════════════════════════════════════
# TAB 5 — REPORT
# ══════════════════════════════════════════════════════════════════════════════
with tab_report:
    st.subheader("📋 Optimization Report")

    if not vehicle_routes:
        st.info("Run optimization to generate a report.")
    else:
        total_dist = sum(vehicle_dists.values())
        total_eta  = estimate_eta(total_dist, vehicle_speed, traffic_factor)
        now_str    = datetime.now().strftime("%Y-%m-%d %H:%M")

        report_md = f"""# Delivery Route Optimization Report
**Generated:** {now_str}

---

## Summary
| Metric | Value |
|--------|-------|
| Vehicles Used | {len(vehicle_routes)} |
| Total Distance | {round(total_dist, 2)} km |
| Traffic Factor | {traffic_factor} ({get_traffic_label(traffic_factor)}) |
| Estimated Time | {round(total_eta, 2)} hours |
| Avg Speed | {vehicle_speed} km/h |

---

## Vehicle Routes
"""
        for vid, route in vehicle_routes.items():
            stops = " → ".join([f"Order #{int(o.get('order_id','?'))}" for o in route])
            report_md += f"""
### Vehicle {vid + 1}
- **Distance:** {round(vehicle_dists[vid], 2)} km
- **Stops:** {len(route)}
- **Route:** Depot → {stops} → Depot
"""

        report_md += "\n---\n*Generated by Delivery Route Optimization System*"

        st.markdown(report_md)

        report_path = os.path.join(OUTPUT_DIR, "report.md")
        with open(report_path, "w") as f:
            f.write(report_md)

        st.download_button(
            "⬇️ Download Report",
            report_md,
            file_name="route_report.md",
            mime="text/markdown"
        )

        # CSV export
        summary_df = build_vehicle_summary(vehicle_routes, vehicle_dists)
        csv_data = summary_df.to_csv(index=False)
        st.download_button(
            "⬇️ Export Summary CSV",
            csv_data,
            file_name="route_summary.csv",
            mime="text/csv"
        )