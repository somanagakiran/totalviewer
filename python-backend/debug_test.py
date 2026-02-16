"""
Simple debug test for hole detection
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.hole_detector import HoleDetector

def simple_test():
    """Simple test with just a rectangle and a circle"""
    
    print("=== Simple Debug Test ===")
    
    # Create simple entities
    entities = [
        # Outer rectangle
        {"type": "LINE", "x1": 0, "y1": 0, "x2": 10, "y2": 0},
        {"type": "LINE", "x1": 10, "y1": 0, "x2": 10, "y2": 10},
        {"type": "LINE", "x1": 10, "y1": 10, "x2": 0, "y2": 10},
        {"type": "LINE", "x1": 0, "y1": 10, "x2": 0, "y2": 0},
        # Circle hole
        {"type": "CIRCLE", "center": [5, 5], "radius": 2}
    ]
    
    print(f"Testing with {len(entities)} entities...")
    
    # Create detector
    detector = HoleDetector(tolerance=0.1, min_area=0.1)
    
    # Convert entities to edges
    print("Converting entities to edges...")
    edges = detector._convert_entities_to_edges(entities)
    print(f"Converted to {len(edges)} edges")
    
    # Build graph
    print("Building geometry graph...")
    detector.edges = edges
    detector._build_geometry_graph()
    print(f"Graph has {len(detector.nodes)} nodes")
    
    # Detect loops
    print("Detecting closed loops...")
    import time
    start_time = time.time()
    
    try:
        loops = detector._detect_closed_loops()
        elapsed = time.time() - start_time
        print(f"Found {len(loops)} closed loops in {elapsed:.2f} seconds")
        
        for i, loop in enumerate(loops):
            print(f"Loop {i+1}: {len(loop)} vertices")
            print(f"  First few points: {loop[:5]}...")
            
    except Exception as e:
        print(f"Error during loop detection: {e}")
        import traceback
        traceback.print_exc()
    
    # Find outer boundary
    print("Finding outer boundary...")
    detector.closed_loops = loops
    outer = detector._find_outer_boundary()
    if outer:
        print(f"Outer boundary area: {outer.area:.2f}")
    else:
        print("No outer boundary found")
    
    # Find holes
    print("Identifying internal holes...")
    holes = detector._identify_internal_holes()
    print(f"Found {len(holes)} internal holes")
    
    return loops, holes

if __name__ == "__main__":
    simple_test()