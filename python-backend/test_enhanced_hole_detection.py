"""
Test the enhanced hole detection
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.enhanced_hole_detector import detect_holes_from_entities, count_holes_by_type

def simple_test():
    """Simple test with just a rectangle and a circle"""
    
    print("=== Testing Enhanced Hole Detection ===")
    
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
    
    # Test hole detection
    result = detect_holes_from_entities(entities, tolerance=0.1, min_area=0.1)
    
    print(f"Total holes: {result['total_holes']}")
    print(f"Outer boundary area: {result['outer_boundary_area']}")
    
    # Count by type
    hole_counts = count_holes_by_type(result['hole_details'])
    print(f"Hole counts by type: {hole_counts}")
    
    # Show hole details
    for hole in result['hole_details']:
        print(f"Hole {hole['id']}: {hole['type']} - Area: {hole['area']}")
    
    return result

def comprehensive_test():
    """Test with multiple hole types"""
    
    print("\n=== Comprehensive Test ===")
    
    entities = [
        # Outer boundary (rectangle 100x80)
        {"type": "LINE", "x1": 0, "y1": 0, "x2": 100, "y2": 0},
        {"type": "LINE", "x1": 100, "y1": 0, "x2": 100, "y2": 80},
        {"type": "LINE", "x1": 100, "y1": 80, "x2": 0, "y2": 80},
        {"type": "LINE", "x1": 0, "y1": 80, "x2": 0, "y2": 0},
        
        # Circle hole
        {"type": "CIRCLE", "center": [20, 20], "radius": 5},
        
        # Rectangle hole
        {"type": "LINE", "x1": 40, "y1": 12.5, "x2": 60, "y2": 12.5},
        {"type": "LINE", "x1": 60, "y1": 12.5, "x2": 60, "y2": 27.5},
        {"type": "LINE", "x1": 60, "y1": 27.5, "x2": 40, "y2": 27.5},
        {"type": "LINE", "x1": 40, "y1": 27.5, "x2": 40, "y2": 12.5},
        
        # Triangle hole
        {"type": "LINE", "x1": 75, "y1": 15, "x2": 85, "y2": 15},
        {"type": "LINE", "x1": 85, "y1": 15, "x2": 80, "y2": 25},
        {"type": "LINE", "x1": 80, "y1": 25, "x2": 75, "y2": 15},
    ]
    
    result = detect_holes_from_entities(entities, tolerance=0.1, min_area=0.1)
    
    print(f"Total holes: {result['total_holes']}")
    print(f"Outer boundary area: {result['outer_boundary_area']}")
    
    hole_counts = count_holes_by_type(result['hole_details'])
    print(f"Hole counts by type: {hole_counts}")
    
    return result

if __name__ == "__main__":
    simple_test()
    comprehensive_test()
    print("\n Tests completed!")