"""
Example usage of the Advanced Hole Detection System

This script demonstrates how to use the hole detection system with real DXF files
and shows the expected output format.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.hole_detector import HoleDetector, detect_holes_from_entities, count_holes_by_type
from engine.dxf_parser import parse_dxf

def demonstrate_hole_detection():
    """Demonstrate the hole detection system capabilities"""
    
    print("=" * 60)
    print("ADVANCED DXF HOLE DETECTION SYSTEM")
    print("=" * 60)
    
    print("\nThis system can detect ANY internal closed contour:")
    print("• Circles")
    print("• Rectangles") 
    print("• Triangles")
    print("• Polygons (any number of sides)")
    print("• Slots/Oblongs")
    print("• Irregular closed shapes")
    print("• Mixed entity contours (LINE + ARC combinations)")
    
    print("\nSupported DXF entities:")
    print("• LINE")
    print("• ARC") 
    print("• CIRCLE")
    print("• LWPOLYLINE")
    print("• POLYLINE")
    print("• SPLINE")
    print("• ELLIPSE")
    
    print("\nKey features:")
    print("• Handles non-PEDIT joined geometry")
    print("• Tolerance-based endpoint snapping")
    print("• Automatic closed loop detection")
    print("• Shape classification")
    print("• Robust edge case handling")
    
    # Example: Create a complex part with multiple hole types
    print("\n" + "=" * 60)
    print("EXAMPLE: Complex Part with Multiple Hole Types")
    print("=" * 60)
    
    # Create example entities
    entities = create_complex_part_example()
    
    # Detect holes
    result = detect_holes_from_entities(entities, tolerance=0.01, min_area=0.1)
    
    # Display results
    display_results(result)
    
    return result

def create_complex_part_example():
    """Create a complex part example with various hole types"""
    entities = []
    
    # Outer boundary (200x150 rectangle)
    entities.extend([
        {"type": "LINE", "x1": 0, "y1": 0, "x2": 200, "y2": 0},
        {"type": "LINE", "x1": 200, "y1": 0, "x2": 200, "y2": 150},
        {"type": "LINE", "x1": 200, "y1": 150, "x2": 0, "y2": 150},
        {"type": "LINE", "x1": 0, "y1": 150, "x2": 0, "y2": 0}
    ])
    
    # 1. Circle holes (mounting holes)
    entities.append({"type": "CIRCLE", "center": [30, 30], "radius": 8})
    entities.append({"type": "CIRCLE", "center": [170, 30], "radius": 8})
    entities.append({"type": "CIRCLE", "center": [30, 120], "radius": 8})
    entities.append({"type": "CIRCLE", "center": [170, 120], "radius": 8})
    
    # 2. Large center hole (circle)
    entities.append({"type": "CIRCLE", "center": [100, 75], "radius": 25})
    
    # 3. Rectangular cutout (switch opening)
    entities.extend([
        {"type": "LINE", "x1": 60, "y1": 50, "x2": 140, "y2": 50},
        {"type": "LINE", "x1": 140, "y1": 50, "x2": 140, "y2": 100},
        {"type": "LINE", "x1": 140, "y1": 100, "x2": 60, "y2": 100},
        {"type": "LINE", "x1": 60, "y1": 100, "x2": 60, "y2": 50}
    ])
    
    # 4. Triangular holes (ventilation)
    # Triangle 1
    entities.extend([
        {"type": "LINE", "x1": 15, "y1": 60, "x2": 25, "y2": 60},
        {"type": "LINE", "x1": 25, "y1": 60, "x2": 20, "y2": 70},
        {"type": "LINE", "x1": 20, "y1": 70, "x2": 15, "y2": 60}
    ])
    
    # Triangle 2
    entities.extend([
        {"type": "LINE", "x1": 175, "y1": 60, "x2": 185, "y2": 60},
        {"type": "LINE", "x1": 185, "y1": 60, "x2": 180, "y2": 70},
        {"type": "LINE", "x1": 180, "y1": 70, "x2": 175, "y2": 60}
    ])
    
    # 5. Slot holes (connector openings)
    # Slot 1: Horizontal slot
    entities.extend([
        {"type": "ARC", "center": [50, 25], "radius": 5, "startAngle": 90, "endAngle": 270},
        {"type": "LINE", "x1": 50, "y1": 20, "x2": 70, "y2": 20},
        {"type": "ARC", "center": [70, 25], "radius": 5, "startAngle": 270, "endAngle": 90},
        {"type": "LINE", "x1": 70, "y1": 30, "x2": 50, "y2": 30}
    ])
    
    # Slot 2: Vertical slot
    entities.extend([
        {"type": "ARC", "center": [130, 25], "radius": 4, "startAngle": 180, "endAngle": 0},
        {"type": "LINE", "x1": 126, "y1": 25, "x2": 126, "y2": 40},
        {"type": "ARC", "center": [130, 40], "radius": 4, "startAngle": 0, "endAngle": 180},
        {"type": "LINE", "x1": 134, "y1": 40, "x2": 134, "y2": 25}
    ])
    
    # 6. Hexagonal hole (special feature)
    hex_center = [150, 75]
    hex_radius = 12
    hex_points = []
    for i in range(6):
        angle = 2 * math.pi * i / 6
        x = hex_center[0] + hex_radius * math.cos(angle)
        y = hex_center[1] + hex_radius * math.sin(angle)
        hex_points.append([x, y])
    
    for i in range(6):
        p1 = hex_points[i]
        p2 = hex_points[(i + 1) % 6]
        entities.append({
            "type": "LINE",
            "x1": p1[0], "y1": p1[1],
            "x2": p2[0], "y2": p2[1]
        })
    
    # 7. Octagonal hole (another special feature)
    oct_center = [50, 115]
    oct_radius = 8
    oct_points = []
    for i in range(8):
        angle = 2 * math.pi * i / 8
        x = oct_center[0] + oct_radius * math.cos(angle)
        y = oct_center[1] + oct_radius * math.sin(angle)
        oct_points.append([x, y])
    
    for i in range(8):
        p1 = oct_points[i]
        p2 = oct_points[(i + 1) % 8]
        entities.append({
            "type": "LINE",
            "x1": p1[0], "y1": p1[1],
            "x2": p2[0], "y2": p2[1]
        })
    
    # 8. Irregular polygon (complex shape)
    irregular_points = [[120, 110], [135, 105], [140, 115], [135, 125], [125, 130], [115, 125]]
    for i in range(len(irregular_points)):
        p1 = irregular_points[i]
        p2 = irregular_points[(i + 1) % len(irregular_points)]
        entities.append({
            "type": "LINE",
            "x1": p1[0], "y1": p1[1],
            "x2": p2[0], "y2": p2[1]
        })
    
    return entities

def display_results(result):
    """Display hole detection results in a formatted way"""
    
    print(f"\n📊 HOLE DETECTION RESULTS")
    print(f"{'='*50}")
    print(f"Total Holes Found: {result['total_holes']}")
    print(f"Outer Boundary Area: {result['outer_boundary_area']:.2f} square units")
    print(f"Outer Perimeter: {result['outer_perimeter']:.2f} units")
    
    # Count by type
    hole_counts = count_holes_by_type(result['hole_details'])
    
    print(f"\n📋 HOLE BREAKDOWN BY TYPE:")
    print(f"{'='*30}")
    
    for hole_type, count in sorted(hole_counts.items()):
        if count > 0:
            print(f"• {hole_type.replace('_', ' ').title()}: {count}")
    
    # Detailed hole information
    print(f"\n🔍 DETAILED HOLE INFORMATION:")
    print(f"{'='*40}")
    
    for i, hole in enumerate(result['hole_details'], 1):
        print(f"\nHole #{hole['id']} - {hole['type'].replace('_', ' ').title()}")
        print(f"  Area: {hole['area']:.2f} square units")
        print(f"  Perimeter: {hole['perimeter']:.2f} units")
        print(f"  Width: {hole['width']:.2f} units")
        print(f"  Height: {hole['height']:.2f} units")
        print(f"  Vertices: {hole['vertex_count']}")
        print(f"  Centroid: ({hole['centroid'][0]:.1f}, {hole['centroid'][1]:.1f})")
    
    # Summary statistics
    print(f"\n📈 SUMMARY STATISTICS:")
    print(f"{'='*25}")
    
    total_area = sum(hole['area'] for hole in result['hole_details'])
    total_perimeter = sum(hole['perimeter'] for hole in result['hole_details'])
    
    print(f"Total Hole Area: {total_area:.2f} square units")
    print(f"Total Hole Perimeter: {total_perimeter:.2f} units")
    print(f"Hole Area Ratio: {(total_area / result['outer_boundary_area'] * 100):.1f}%")
    
    # Shape-specific insights
    hole_counts = count_holes_by_type(result['hole_details'])
    
    print(f"\n💡 INSIGHTS:")
    print(f"{'='*15}")
    
    if hole_counts.get('circle', 0) > 0:
        print(f"• Found {hole_counts['circle']} circular holes (likely mounting holes)")
    
    if hole_counts.get('rectangle', 0) > 0:
        print(f"• Found {hole_counts['rectangle']} rectangular cutouts")
    
    if hole_counts.get('slot', 0) > 0:
        print(f"• Found {hole_counts['slot']} slot holes (connector openings)")
    
    if hole_counts.get('triangle', 0) > 0:
        print(f"• Found {hole_counts['triangle']} triangular holes (ventilation)")
    
    polygon_holes = sum(count for hole_type, count in hole_counts.items() 
                       if hole_type.startswith('polygon_') and count > 0)
    if polygon_holes > 0:
        print(f"• Found {polygon_holes} polygonal holes (special features)")

def test_with_real_dxf():
    """Test with a real DXF file if available"""
    
    # Look for DXF files in common locations
    test_files = [
        "test_part.dxf",
        "sample.dxf", 
        "example.dxf",
        "part.dxf"
    ]
    
    for filename in test_files:
        if os.path.exists(filename):
            print(f"\n🎯 TESTING WITH REAL DXF FILE: {filename}")
            print(f"{'='*50}")
            
            try:
                # Parse the DXF file
                parsed_data = parse_dxf(filename)
                
                # Detect holes
                result = detect_holes_from_entities(
                    parsed_data.get("geometry", []),
                    tolerance=0.01,
                    min_area=0.1
                )
                
                # Display results
                display_results(result)
                
                return result
                
            except Exception as e:
                print(f"Error processing {filename}: {e}")
                continue
    
    print("\nℹ️  No test DXF files found. Using synthetic example instead.")
    return None

if __name__ == "__main__":
    print("Advanced Hole Detection System - Example Usage")
    print("This demonstrates the comprehensive hole detection capabilities.")
    
    # Run the demonstration
    result = demonstrate_hole_detection()
    
    # Try to test with real DXF if available
    real_result = test_with_real_dxf()
    
    print(f"\n✅ Demonstration complete!")
    print(f"The system successfully detected {result['total_holes']} holes in the example part.")
    print(f"Ready for integration with your DXF processing workflow!")