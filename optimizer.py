from geopy.distance import geodesic


def calculate_distance(a, b):
    """Calculate geodesic distance in km between two (lat, lon) tuples."""
    return geodesic(a, b).km


def nearest_neighbor(start, points):
    """
    Greedy nearest-neighbor TSP heuristic.
    Returns (ordered list of order dicts, total_distance_km).
    """
    unvisited = points.copy()
    route = []
    current = start
    total_distance = 0.0

    while len(unvisited) > 0:
        nearest = None
        best = float("inf")

        for index, row in unvisited.iterrows():
            loc = (row["latitude"], row["longitude"])
            dist = calculate_distance(current, loc)
            if dist < best:
                best = dist
                nearest = row

        route.append(nearest)
        total_distance += best
        current = (nearest["latitude"], nearest["longitude"])
        unvisited = unvisited.drop(nearest.name)

    # Add return-to-warehouse distance
    if route:
        last = (route[-1]["latitude"], route[-1]["longitude"])
        total_distance += calculate_distance(last, start)

    return route, total_distance


def two_opt_improve(start, route):
    """
    2-opt local search to improve a nearest-neighbor route.
    Swaps pairs of edges to reduce total distance.
    Returns (improved_route, improved_distance).
    """
    best_route = route[:]
    improved = True

    while improved:
        improved = False
        for i in range(len(best_route) - 1):
            for j in range(i + 2, len(best_route)):
                # Reverse the segment between i+1 and j
                new_route = best_route[:i + 1] + best_route[i + 1:j + 1][::-1] + best_route[j + 1:]
                if _route_distance(start, new_route) < _route_distance(start, best_route):
                    best_route = new_route
                    improved = True

    return best_route, _route_distance(start, best_route)


def _route_distance(start, route):
    """Calculate total round-trip distance for a route."""
    total = 0.0
    current = start
    for order in route:
        loc = (order["latitude"], order["longitude"])
        total += calculate_distance(current, loc)
        current = loc
    total += calculate_distance(current, start)
    return total


def priority_sort(route):
    """
    Sort route stops by priority within a vehicle's assignment.
    Priority order: high > medium > low (secondary to distance optimization).
    """
    priority_map = {"high": 0, "medium": 1, "low": 2}
    return sorted(route, key=lambda x: priority_map.get(str(x.get("priority", "low")), 2))