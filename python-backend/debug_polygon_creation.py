"""
Debug the polygon creation issue
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.hole_detector_v2 import HoleDetector

def debug_polygon_creation():
    """Debug why polygonize isn't finding separate loops"""
    
    print("=== Debugging Polygon Creation ===")
    
    # Create simple test case
    entities = [
        # Outer rectangle (10x10)
        {"type": "LINE", "x1": 0, "y1": 0, "x2": 10, "y2": 0},
        {"type": "LINE", "x1": 10, "y1": 0, "x2": 10, "y2": 10},
        {"type": "LINE", "x1": 10, "y1": 10, "x2": 0, "y2": 10},
        {"type": "LINE", "x1": 0, "y1": 10, "x2": 0, "y2": 0},
        # Circle hole (radius 2, center at 5,5)
        {"type": "CIRCLE", "center": [5, 5], "radius": 2}
    ]
    
    print(f"Testing with {len(entities)} entities...")
    
    # Create detector
    detector = HoleDetector(tolerance=0.1, min_area=0.1)
    
    # Step 1: Convert entities to edges
    print("\n1. Converting entities to edges...")
    edges = detector._convert_entities_to_edges(entities)
    print(f"   Converted to {len(edges)} edges")
    
    # Let's look at what edges we have
    print("\n2. Edge breakdown:")
    for i, (start, end) in enumerate(edges):
        print(f"   Edge {i+1}: ({start[0]:.2f}, {start[1]:.2f}) -> ({end[0]:.2f}, {end[1]:.2f})")
    
    # Step 3: Try different approaches
    print("\n3. Trying different polygon creation approaches...")
    
    try:
        from shapely.geometry import Polygon, Point, LineString
        from shapely.ops import polygonize
        
        # Approach 1: Use polygonize as before
        print("\n   Approach 1: polygonize all edges")
        line_strings = []
        for start, end in edges:
            line_strings.append(LineString([start, end]))
        
        polygons = list(polygonize(line_strings))
        print(f"   Found {len(polygons)} polygons")
        
        # Approach 2: Try to find separate loops manually
        print("\n   Approach 2: Manual loop detection")
        
        # Group edges by connectivity
        from collections import defaultdict
        
        # Build connectivity graph
        connectivity = defaultdict(list)
        for i, (start, end) in enumerate(edges):
            # Normalize points to avoid floating point issues
            start_norm = (round(start[0], 6), round(start[1], 6))
            end_norm = (round(end[0], 6), round(end[1], 6))
            connectivity[start_norm].append((end_norm, i))
            connectivity[end_norm].append((start_norm, i))
        
        print(f"   Connectivity graph has {len(connectivity)} nodes")
        
        # Find closed loops
        visited_edges = set()
        loops = []
        
        for start_node in connectivity:
            for end_node, edge_idx in connectivity[start_node]:
                if edge_idx in visited_edges:
                    continue
                    
                # Try to trace a loop
                loop = trace_loop(start_node, edge_idx, connectivity, visited_edges, edges)
                if loop:
                    loops.append(loop)
        
        print(f"   Found {len(loops)} loops manually")
        
        # Convert loops to polygons
        loop_polygons = []
        for loop in loops:
            if len(loop) >= 3:  # Need at least 3 points for a polygon
                try:
                    poly = Polygon(loop)
                    if poly.is_valid and poly.area >= detector.min_area:
                        loop_polygons.append(poly)
                        print(f"   Loop polygon: area={poly.area:.2f}")
                except:
                    pass
        
        print(f"   Valid loop polygons: {len(loop_polygons)}")
        
    except Exception as e:
        print(f"   Error: {e}")
        import traceback
        traceback.print_exc()

def trace_loop(start_node, start_edge_idx, connectivity, visited_edges, all_edges):
    """Trace a closed loop starting from a node and edge"""
    
    current_node = start_node
    path = [start_node]
    local_visited = {start_edge_idx}
    
    while True:
        # Find next unvisited edge from current node
        next_found = False
        for next_node, edge_idx in connectivity[current_node]:
            if edge_idx not in local_visited and edge_idx not in visited_edges:
                path.append(next_node)
                local_visited.add(edge_idx)
                current_node = next_node
                next_found = True
                break
        
        if not next_found:
            break
            
        # Check if we returned to start
        if current_node == start_node and len(path) > 2:
            # Found a closed loop
            visited_edges.update(local_visited)
            return path
            
        # Safety check
        if len(path) > 100:
            break
    
    return None

if __name__ == "__main__":
    debug_polygon_creation()