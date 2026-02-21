"""
Debug the hole detection issue
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.hole_detector_v2 import HoleDetector

def debug_hole_detection():
    """Debug the hole detection step by step"""
    
    print("=== Debugging Hole Detection ===")
    
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
    detector.edges = edges
    
    # Step 2: Build polygons
    print("\n2. Building polygons from edges...")
    try:
        from shapely.geometry import Polygon, Point
        from shapely.ops import polygonize
        
        # Create line strings from edges
        line_strings = []
        for start, end in edges:
            from shapely.geometry import LineString
            line_strings.append(LineString([start, end]))
        
        print(f"   Created {len(line_strings)} line strings")
        
        # Use polygonize to find closed loops
        polygons = list(polygonize(line_strings))
        print(f"   Polygonize found {len(polygons)} polygons")
        
        # Filter valid polygons by area
        valid_polygons = []
        for i, poly in enumerate(polygons):
            print(f"   Polygon {i+1}: area={poly.area:.2f}, valid={poly.is_valid}")
            if poly.is_valid and poly.area >= detector.min_area:
                valid_polygons.append(poly)
        
        print(f"   Valid polygons: {len(valid_polygons)}")
        detector.closed_loops = valid_polygons
        
    except Exception as e:
        print(f"   Error: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Step 3: Find outer boundary
    print("\n3. Finding outer boundary...")
    outer = detector._find_outer_boundary()
    if outer:
        print(f"   Outer boundary area: {outer.area:.2f}")
        detector.outer_boundary = outer
    else:
        print("   No outer boundary found!")
        return
    
    # Step 4: Check each polygon
    print("\n4. Checking internal holes...")
    print(f"   Total polygons: {len(detector.closed_loops)}")
    
    for i, polygon in enumerate(detector.closed_loops):
        print(f"\n   Polygon {i+1}:")
        print(f"     Area: {polygon.area:.2f}")
        print(f"     Centroid: ({polygon.centroid.x:.2f}, {polygon.centroid.y:.2f})")
        
        # Check if it's the outer boundary
        if polygon.equals(outer):
            print(f"     -> This is the outer boundary")
            continue
        
        # Check containment
        try:
            centroid = polygon.centroid
            if outer.contains(centroid):
                print(f"     -> Centroid is INSIDE outer boundary -> HOLE")
                detector.holes.append(polygon)
            else:
                print(f"     -> Centroid is OUTSIDE outer boundary")
                
                # Additional check: see if any point is inside
                print(f"     -> Checking individual points...")
                for j, coord in enumerate(polygon.exterior.coords):
                    point = Point(coord)
                    if outer.contains(point):
                        print(f"       Point {j}: ({coord[0]:.2f}, {coord[1]:.2f}) is INSIDE -> HOLE")
                        detector.holes.append(polygon)
                        break
                    else:
                        print(f"       Point {j}: ({coord[0]:.2f}, {coord[1]:.2f}) is outside")
                        
        except Exception as e:
            print(f"     Error checking containment: {e}")
    
    print(f"\n5. Final result: {len(detector.holes)} holes found")
    
    return detector.holes

if __name__ == "__main__":
    debug_hole_detection()