import pandas as pd


def allocate_by_capacity(orders, vehicle_capacity):
    """
    Greedy bin-packing: fill each vehicle up to capacity.
    High-priority orders are allocated first.
    Returns list of lists (each inner list = one vehicle's orders as dicts).
    """
    priority_map = {"high": 0, "medium": 1, "low": 2}

    # Sort by priority first
    sorted_orders = orders.copy()
    if "priority" in sorted_orders.columns:
        sorted_orders["_pri_num"] = sorted_orders["priority"].map(priority_map).fillna(2)
        sorted_orders = sorted_orders.sort_values("_pri_num").drop(columns=["_pri_num"])

    vehicles = []
    current_vehicle = []
    current_load = 0

    for _, order in sorted_orders.iterrows():
        w = order.get("weight", 1)
        if current_load + w <= vehicle_capacity:
            current_vehicle.append(order)
            current_load += w
        else:
            if current_vehicle:
                vehicles.append(current_vehicle)
            current_vehicle = [order]
            current_load = w

    if current_vehicle:
        vehicles.append(current_vehicle)

    return vehicles


def get_vehicle_stats(vehicles):
    """Return a summary DataFrame of each vehicle's load."""
    rows = []
    for i, v in enumerate(vehicles):
        total_weight = sum(o.get("weight", 0) for o in v)
        order_ids = [int(o.get("order_id", -1)) for o in v]
        rows.append({
            "Vehicle": f"Vehicle {i + 1}",
            "Orders": str(order_ids),
            "Total Weight": total_weight,
            "Stop Count": len(v),
        })
    return pd.DataFrame(rows)