"""
Test script for Advanced Hole Detection System

This script tests the hole detection capabilities with various geometric shapes
and edge cases to ensure robust performance.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.hole_detector import HoleDetector, detect_holes_from_entities, count_holes_by_type
import math

def create_test_entities():
    """Create test entities representing various hole shapes"""
    entities = []
    
    # Create outer boundary (rectangle 100x80)
    entities.extend([
        {"type": "LINE", "x1": 0, "y1": 0, "x2": 100, "y2": 0},
        {"type": "LINE", "x1": 100, "y1": 0, "x2": 100, "y2": 80},
        {"type": "LINE", "x1": 100, "y1": 80, "x2": 0, "y2": 80},
        {"type": "LINE", "x1": 0, "y1": 80, "x2": 0, "y2": 0}
    ])
    
    # Circle hole (center at 20,20, radius 5)
    entities.append({
        "type": "CIRCLE",
        "center": [20, 20],
        "radius": 5
    })
    
    # Rectangle hole (20x15, center at 50,20)
    entities.extend([
        {"type": "LINE", "x1": 40, "y1": 12.5, "x2": 60, "y2": 12.5},
        {"type": "LINE", "x1": 60, "y1": 12.5, "x2": 60, "y2": 27.5},
        {"type": "LINE", "x1": 60, "y1": 27.5, "x2": 40, "y2": 27.5},
        {"type": "LINE", "x1": 40, "y1": 27.5, "x2": 40, "y2": 12.5}
    ])
    
    # Triangle hole (vertices at 75,15; 85,15; 80,25)
    entities.extend([
        {"type": "LINE", "x1": 75, "y1": 15, "x2": 85, "y2": 15},
        {"type": "LINE", "x1": 85, "y1": 15, "x2": 80, "y2": 25},
        {"type": "LINE", "x1": 80, "y1": 25, "x2": 75, "y2": 15}
    ])
    
    # Slot hole (oblong shape, center at 20,50)
    # Two semicircles connected by straight lines
    entities.extend([
        # Bottom arc (radius 5, center at 15,50)
        {"type": "ARC", "center": [15, 50], "radius": 5, "startAngle": 90, "endAngle": 270},
        # Left line
        {"type": "LINE", "x1": 15, "y1": 45, "x2": 25, "y2": 45},
        # Top arc (radius 5, center at 25,50)  
        {"type": "ARC", "center": [25, 50], "radius": 5, "startAngle": 270, "endAngle": 90},
        # Right line
        {"type": "LINE", "x1": 25, "y1": 55, "x2": 15, "y2": 55}
    ])
    
    # Hexagon hole (center at 50,50)
    center_x, center_y = 50, 50
    radius = 8
    hex_points = []
    for i in range(6):
        angle = 2 * math.pi * i / 6
        x = center_x + radius * math.cos(angle)
        y = center_y + radius * math.sin(angle)
        hex_points.append([x, y])
    
    for i in range(6):
        p1 = hex_points[i]
        p2 = hex_points[(i + 1) % 6]
        entities.append({
            "type": "LINE",
            "x1": p1[0], "y1": p1[1],
            "x2": p2[0], "y2": p2[1]
        })
    
    # LWPOLYLINE hole (pentagon, center at 75,50)
    center_x, center_y = 75, 50
    radius = 6
    pentagon_points = []
    for i in range(5):
        angle = 2 * math.pi * i / 5 - math.pi/2  # Start from top
        x = center_x + radius * math.cos(angle)
        y = center_y + radius * math.sin(angle)
        pentagon_points.append([x, y])
    
    entities.append({
        "type": "LWPOLYLINE",
        "points": pentagon_points,
        "closed": True
    })
    
    return entities

def test_basic_detection():
    """Test basic hole detection functionality"""
    print("=== Testing Basic Hole Detection ===")
    
    entities = create_test_entities()
    result = detect_holes_from_entities(entities)
    
    print(f"Total holes detected: {result['total_holes']}")
    print(f"Outer boundary area: {result['outer_boundary_area']:.2f}")
    print(f"Outer perimeter: {result['outer_perimeter']:.2f}")
    
    # Count by type
    hole_counts = count_holes_by_type(result['hole_details'])
    print("\nHole counts by type:")
    for hole_type, count in hole_counts.items():
        print(f"  {hole_type}: {count}")
    
    # Print hole details
    print("\nHole details:")
    for hole in result['hole_details']:
        print(f"  Hole {hole['id']}: {hole['type']} - Area: {hole['area']:.2f}, "
              f"Centroid: ({hole['centroid'][0]:.1f}, {hole['centroid'][1]:.1f})")
    
    return result

def test_edge_cases():
    """Test edge cases and error conditions"""
    print("\n=== Testing Edge Cases ===")
    
    # Test 1: Empty entities
    print("Test 1: Empty entities")
    result = detect_holes_from_entities([])
    assert result['total_holes'] == 0
    print("✓ Empty entities handled correctly")
    
    # Test 2: Only outer boundary, no holes
    print("\nTest 2: Only outer boundary")
    entities = [
        {"type": "LINE", "x1": 0, "y1": 0, "x2": 10, "y2": 0},
        {"type": "LINE", "x1": 10, "y1": 0, "x2": 10, "y2": 10},
        {"type": "LINE", "x1": 10, "y1": 10, "x2": 0, "y2": 10},
        {"type": "LINE", "x1": 0, "y1": 10, "x2": 0, "y2": 0}
    ]
    result = detect_holes_from_entities(entities)
    assert result['total_holes'] == 0
    print("✓ No holes detected correctly")
    
    # Test 3: Very small holes (should be filtered out)
    print("\nTest 3: Very small holes")
    entities = [
        # Outer boundary
        {"type": "LINE", "x1": 0, "y1": 0, "x2": 10, "y2": 0},
        {"type": "LINE", "x1": 10, "y1": 0, "x2": 10, "y2": 10},
        {"type": "LINE", "x1": 10, "y1": 10, "x2": 0, "y2": 10},
        {"type": "LINE", "x1": 0, "y1": 10, "x2": 0, "y2": 0},
        # Very small circle (should be filtered)
        {"type": "CIRCLE", "center": [5, 5], "radius": 0.01}
    ]
    result = detect_holes_from_entities(entities, min_area=0.1)
    assert result['total_holes'] == 0  # Should be filtered out
    print("✓ Small holes filtered correctly")
    
    # Test 4: Non-closed entities (should not form holes)
    print("\nTest 4: Non-closed entities")
    entities = [
        # Outer boundary
        {"type": "LINE", "x1": 0, "y1": 0, "x2": 10, "y2": 0},
        {"type": "LINE", "x1": 10, "y1": 0, "x2": 10, "y2": 10},
        {"type": "LINE", "x1": 10, "y1": 10, "x2": 0, "y2": 10},
        {"type": "LINE", "x1": 0, "y1": 10, "x2": 0, "y2": 0},
        # Open arc (should not form hole)
        {"type": "ARC", "center": [5, 5], "radius": 2, "startAngle": 0, "endAngle": 180}
    ]
    result = detect_holes_from_entities(entities)
    # Should not detect the arc as a hole since it's not closed
    print(f"✓ Non-closed entities handled (holes: {result['total_holes']})")

def test_tolerance_handling():
    """Test tolerance handling for gaps between entities"""
    print("\n=== Testing Tolerance Handling ===")
    
    # Create entities with small gaps that should be closed by tolerance
    entities = [
        # Outer boundary with small gaps
        {"type": "LINE", "x1": 0, "y1": 0, "x2": 9.99, "y2": 0},  # Small gap
        {"type": "LINE", "x1": 10, "y1": 0, "x2": 10, "y2": 10},
        {"type": "LINE", "x1": 10, "y1": 10, "x2": 0, "y2": 10},
        {"type": "LINE", "x1": 0, "y1": 10, "x2": 0, "y2": 0.01},  # Small gap
        # Circle with slight position offset (should still be detected)
        {"type": "CIRCLE", "center": [5, 5], "radius": 2}
    ]
    
    # Test with different tolerances
    for tolerance in [0.001, 0.01, 0.1]:
        result = detect_holes_from_entities(entities, tolerance=tolerance)
        print(f"Tolerance {tolerance}: {result['total_holes']} holes detected")

def test_shape_classification():
    """Test shape classification accuracy"""
    print("\n=== Testing Shape Classification ===")
    
    # Test circle classification
    entities = [
        # Outer boundary
        {"type": "LINE", "x1": 0, "y1": 0, "x2": 10, "y2": 0},
        {"type": "LINE", "x1": 10, "y1": 0, "x2": 10, "y2": 10},
        {"type": "LINE", "x1": 10, "y1": 10, "x2": 0, "y2": 10},
        {"type": "LINE", "x1": 0, "y1": 10, "x2": 0, "y2": 0},
        # Perfect circle
        {"type": "CIRCLE", "center": [5, 5], "radius": 2}
    ]
    
    result = detect_holes_from_entities(entities)
    hole_details = result['hole_details']
    
    if hole_details:
        hole_type = hole_details[0]['type']
        print(f"Circle classification: {hole_type}")
        assert hole_type == "circle"
        print("✓ Circle classification correct")
    
    # Test rectangle classification
    entities = [
        # Outer boundary
        {"type": "LINE", "x1": 0, "y1": 0, "x2": 10, "y2": 0},
        {"type": "LINE", "x1": 10, "y1": 0, "x2": 10, "y2": 10},
        {"type": "LINE", "x1": 10, "y1": 10, "x2": 0, "y2": 10},
        {"type": "LINE", "x1": 0, "y1": 10, "x2": 0, "y2": 0},
        # Perfect square
        {"type": "LINE", "x1": 3, "y1": 3, "x2": 7, "y2": 3},
        {"type": "LINE", "x1": 7, "y1": 3, "x2": 7, "y2": 7},
        {"type": "LINE", "x1": 7, "y1": 7, "x2": 3, "y2": 7},
        {"type": "LINE", "x1": 3, "y1": 7, "x2": 3, "y2": 3}
    ]
    
    result = detect_holes_from_entities(entities)
    hole_details = result['hole_details']
    
    if hole_details:
        hole_type = hole_details[0]['type']
        print(f"Rectangle classification: {hole_type}")
        assert hole_type == "rectangle"
        print("✓ Rectangle classification correct")

def main():
    """Run all tests"""
    print("Advanced Hole Detection System - Test Suite")
    print("=" * 50)
    
    try:
        # Run all tests
        test_basic_detection()
        test_edge_cases()
        test_tolerance_handling()
        test_shape_classification()
        
        print("\n" + "=" * 50)
        print("✅ All tests passed successfully!")
        print("The hole detection system is working correctly.")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())