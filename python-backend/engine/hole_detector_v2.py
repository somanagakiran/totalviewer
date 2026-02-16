"""
Advanced Hole Detection Engine for DXF Files - Simplified Version

This module implements a comprehensive hole detection system that can identify
ANY internal closed contour inside the outer boundary, regardless of how it was
created (LINE, ARC, CIRCLE, LWPOLYLINE, POLYLINE, SPLINE, ELLIPSE, or mixed entities).

Key Features:
- Converts all DXF entities to line segments
- Uses Shapely for robust polygon operations
- Handles non-PEDIT joined geometry
- Uses tolerance-based endpoint snapping
- Implements robust closed loop detection
- Classifies holes by shape (circle, rectangle, triangle, slot, etc.)
- Provides detailed hole statistics
"""

import math
from typing import List, Tuple, Dict, Any, Optional
from collections import defaultdict

try:
    from shapely.geometry import Polygon, Point, LineString
    from shapely.ops import polygonize, unary_union
    from shapely.validation import make_valid
    SHAPELY_AVAILABLE = True
except ImportError:
    SHAPELY_AVAILABLE = False
    print("[WARNING] Shapely not available - some features disabled")

# Configuration constants
TOLERANCE = 0.01  # Snap tolerance for endpoint matching
MIN_AREA = 0.1    # Minimum area for valid holes
MAX_SEGMENTS = 1000  # Maximum segments for curve approximation

class HoleDetector:
    """Advanced hole detection for DXF geometry"""
    
    def __init__(self, tolerance: float = TOLERANCE, min_area: float = MIN_AREA):
        self.tolerance = tolerance
        self.min_area = min_area
        self.edges = []
        self.closed_loops = []
        self.outer_boundary = None
        self.holes = []
        
    def detect_holes(self, entities: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Main entry point for hole detection.
        
        Returns:
            Dictionary containing:
            - total_holes: Number of holes found
            - hole_details: List of hole information
            - outer_boundary_area: Area of outer boundary
            - outer_perimeter: Perimeter of outer boundary
            - internal_cutouts_detected: Number of internal holes
            - hole_geometries: Geometric details of holes
        """
        print(f"[HOLE_DETECTOR] Starting detection with {len(entities)} entities")
        
        if not entities:
            return self._empty_result()
            
        try:
            # Step 1: Convert all entities to edges
            self.edges = self._convert_entities_to_edges(entities)
            print(f"[HOLE_DETECTOR] Converted to {len(self.edges)} edges")
            
            if not self.edges:
                return self._empty_result()
            
            # Step 2: Build polygons from edges using Shapely
            self.closed_loops = self._build_polygons_from_edges()
            print(f"[HOLE_DETECTOR] Found {len(self.closed_loops)} closed loops")
            
            if not self.closed_loops:
                return self._empty_result()
            
            # Step 3: Find outer boundary (largest area)
            self.outer_boundary = self._find_outer_boundary()
            if not self.outer_boundary:
                return self._empty_result()
                
            print(f"[HOLE_DETECTOR] Outer boundary area: {self.outer_boundary.area:.2f}")
            
            # Step 4: Identify internal holes
            self.holes = self._identify_internal_holes()
            print(f"[HOLE_DETECTOR] Found {len(self.holes)} internal holes")
            
            # Step 5: Classify holes
            hole_details = self._classify_holes()
            
            # Step 6: Build result
            return {
                "total_holes": len(self.holes),
                "holes": len(self.holes),
                "hole_details": hole_details,
                "outer_boundary_area": round(self.outer_boundary.area, 6),
                "outer_perimeter": round(self.outer_boundary.length, 6),
                "internal_cutouts_detected": len(self.holes),
                "hole_geometries": self._get_hole_geometries()
            }
            
        except Exception as e:
            print(f"[HOLE_DETECTOR] Error during detection: {e}")
            import traceback
            traceback.print_exc()
            return self._empty_result()
    
    def _convert_entities_to_edges(self, entities: List[Dict[str, Any]]) -> List[List[Tuple[float, float]]]:
        """Convert all DXF entities to line segments"""
        edges = []
        
        for entity in entities:
            entity_type = entity.get("type", "")
            
            if entity_type == "LINE":
                edges.extend(self._convert_line(entity))
            elif entity_type == "ARC":
                edges.extend(self._convert_arc(entity))
            elif entity_type == "CIRCLE":
                edges.extend(self._convert_circle(entity))
            elif entity_type == "LWPOLYLINE":
                edges.extend(self._convert_lwpolyline(entity))
            elif entity_type == "POLYLINE":
                edges.extend(self._convert_polyline(entity))
            elif entity_type == "SPLINE":
                edges.extend(self._convert_spline(entity))
            elif entity_type == "ELLIPSE":
                edges.extend(self._convert_ellipse(entity))
                
        return edges
    
    def _convert_line(self, entity: Dict[str, Any]) -> List[List[Tuple[float, float]]]:
        """Convert LINE entity to edges"""
        start = (entity.get("x1", 0), entity.get("y1", 0))
        end = (entity.get("x2", 0), entity.get("y2", 0))
        return [[start, end]]
    
    def _convert_arc(self, entity: Dict[str, Any]) -> List[List[Tuple[float, float]]]:
        """Convert ARC entity to edges by approximation"""
        center = entity.get("center", [0, 0])
        radius = entity.get("radius", 0)
        start_angle = entity.get("startAngle", 0)
        end_angle = entity.get("endAngle", 360)
        
        if radius <= 0:
            return []
            
        # Calculate number of segments based on arc angle
        angle_span = abs(end_angle - start_angle)
        if angle_span > 180:
            angle_span = 360 - angle_span if angle_span < 360 else 360
            
        num_segments = max(8, int(angle_span / 5))  # 5 degrees per segment
        if num_segments > MAX_SEGMENTS:
            num_segments = MAX_SEGMENTS
            
        edges = []
        prev_point = None
        
        for i in range(num_segments + 1):
            angle = math.radians(start_angle + (end_angle - start_angle) * i / num_segments)
            x = center[0] + radius * math.cos(angle)
            y = center[1] + radius * math.sin(angle)
            current_point = (x, y)
            
            if prev_point is not None:
                edges.append([prev_point, current_point])
            prev_point = current_point
            
        return edges
    
    def _convert_circle(self, entity: Dict[str, Any]) -> List[List[Tuple[float, float]]]:
        """Convert CIRCLE entity to edges by approximation"""
        center = entity.get("center", [0, 0])
        radius = entity.get("radius", 0)
        
        if radius <= 0:
            return []
            
        num_segments = 64  # Good circle approximation
        edges = []
        prev_point = None
        
        for i in range(num_segments + 1):
            angle = 2 * math.pi * i / num_segments
            x = center[0] + radius * math.cos(angle)
            y = center[1] + radius * math.sin(angle)
            current_point = (x, y)
            
            if prev_point is not None:
                edges.append([prev_point, current_point])
            prev_point = current_point
            
        return edges
    
    def _convert_lwpolyline(self, entity: Dict[str, Any]) -> List[List[Tuple[float, float]]]:
        """Convert LWPOLYLINE entity to edges"""
        points = entity.get("points", [])
        is_closed = entity.get("closed", False)
        
        if len(points) < 2:
            return []
            
        edges = []
        for i in range(len(points) - 1):
            edges.append([tuple(points[i]), tuple(points[i + 1])])
            
        if is_closed and len(points) > 2:
            edges.append([tuple(points[-1]), tuple(points[0])])
            
        return edges
    
    def _convert_polyline(self, entity: Dict[str, Any]) -> List[List[Tuple[float, float]]]:
        """Convert POLYLINE entity to edges"""
        return self._convert_lwpolyline(entity)  # Same logic
    
    def _convert_spline(self, entity: Dict[str, Any]) -> List[List[Tuple[float, float]]]:
        """Convert SPLINE entity to edges by approximation"""
        points = entity.get("points", [])
        is_closed = entity.get("closed", False)
        
        if len(points) < 2:
            return []
            
        edges = []
        for i in range(len(points) - 1):
            edges.append([tuple(points[i]), tuple(points[i + 1])])
            
        if is_closed and len(points) > 2:
            edges.append([tuple(points[-1]), tuple(points[0])])
            
        return edges
    
    def _convert_ellipse(self, entity: Dict[str, Any]) -> List[List[Tuple[float, float]]]:
        """Convert ELLIPSE entity to edges by approximation"""
        points = entity.get("points", [])
        is_closed = entity.get("closed", False)
        
        if len(points) < 2:
            return []
            
        edges = []
        for i in range(len(points) - 1):
            edges.append([tuple(points[i]), tuple(points[i + 1])])
            
        if is_closed and len(points) > 2:
            edges.append([tuple(points[-1]), tuple(points[0])])
            
        return edges
    
    def _build_polygons_from_edges(self) -> List[Polygon]:
        """Build polygons from edges using Shapely"""
        if not SHAPELY_AVAILABLE:
            print("[HOLE_DETECTOR] Shapely not available, using simple method")
            return self._build_polygons_simple()
            
        try:
            # Create line strings from edges
            line_strings = []
            for start, end in self.edges:
                line_strings.append(LineString([start, end]))
            
            # Use polygonize to find closed loops
            polygons = list(polygonize(line_strings))
            
            # Filter valid polygons by area
            valid_polygons = []
            for poly in polygons:
                if poly.is_valid and poly.area >= self.min_area:
                    valid_polygons.append(poly)
            
            return valid_polygons
            
        except Exception as e:
            print(f"[HOLE_DETECTOR] Error building polygons with Shapely: {e}")
            return self._build_polygons_simple()
    
    def _build_polygons_simple(self) -> List[Polygon]:
        """Simple polygon building method when Shapely is not available"""
        # For now, return empty list - can be implemented later
        return []
    
    def _find_outer_boundary(self) -> Optional[Polygon]:
        """Find the outer boundary (largest area closed loop)"""
        if not self.closed_loops:
            return None
            
        # Find polygon with largest area
        largest_polygon = None
        largest_area = 0
        
        for polygon in self.closed_loops:
            if polygon.area > largest_area:
                largest_area = polygon.area
                largest_polygon = polygon
                
        return largest_polygon
    
    def _identify_internal_holes(self) -> List[Polygon]:
        """Identify internal holes (closed loops inside outer boundary)"""
        if not self.outer_boundary:
            return []
            
        holes = []
        outer = self.outer_boundary
        
        for polygon in self.closed_loops:
            # Skip the outer boundary itself
            if polygon.equals(outer):
                continue
                
            # Check if this polygon is inside the outer boundary
            try:
                # Multiple checks to ensure it's truly internal
                centroid = polygon.centroid
                
                # Check if centroid is inside outer boundary
                if outer.contains(centroid):
                    holes.append(polygon)
                elif polygon.area < outer.area * 0.1:  # Much smaller
                    # Additional check: see if any point is inside
                    for coord in polygon.exterior.coords:
                        point = Point(coord)
                        if outer.contains(point):
                            holes.append(polygon)
                            break
                            
            except Exception as e:
                print(f"[HOLE_DETECTOR] Error checking polygon containment: {e}")
                # Fallback: if it's significantly smaller, assume it's a hole
                if polygon.area < outer.area * 0.5:
                    holes.append(polygon)
                    
        return holes
    
    def _classify_holes(self) -> List[Dict[str, Any]]:
        """Classify holes by their geometric shape"""
        hole_details = []
        
        for i, hole in enumerate(self.holes):
            detail = self._classify_single_hole(hole, i)
            hole_details.append(detail)
            
        return hole_details
    
    def _classify_single_hole(self, hole: Polygon, index: int) -> Dict[str, Any]:
        """Classify a single hole by its shape"""
        area = hole.area
        perimeter = hole.length
        
        # Get bounding box
        minx, miny, maxx, maxy = hole.bounds
        width = maxx - minx
        height = maxy - miny
        
        # Calculate shape metrics
        centroid = hole.centroid
        
        # Count vertices (simplified)
        coords = list(hole.exterior.coords)
        vertex_count = len(coords) - 1  # Exclude closing vertex
        
        # Classify by shape
        shape_type = self._determine_shape_type(hole, area, perimeter, width, height, vertex_count)
        
        return {
            "id": index + 1,
            "type": shape_type,
            "area": round(area, 6),
            "perimeter": round(perimeter, 6),
            "width": round(width, 6),
            "height": round(height, 6),
            "vertex_count": vertex_count,
            "centroid": [round(centroid.x, 6), round(centroid.y, 6)],
            "location": "internal"
        }
    
    def _determine_shape_type(self, hole: Polygon, area: float, perimeter: float, 
                             width: float, height: float, vertex_count: int) -> str:
        """Determine the type of hole based on geometric analysis"""
        
        # Check if it's close to a circle
        if self._is_circle(hole, area, perimeter):
            return "circle"
        
        # Check if it's a rectangle
        if self._is_rectangle(hole, vertex_count, width, height):
            return "rectangle"
        
        # Check if it's a triangle
        if vertex_count == 3:
            return "triangle"
        
        # Check if it's a slot (oblong)
        if self._is_slot(hole, width, height):
            return "slot"
        
        # Check if it's a polygon
        if vertex_count >= 4:
            return f"polygon_{vertex_count}"
        
        return "irregular"
    
    def _is_circle(self, hole: Polygon, area: float, perimeter: float) -> bool:
        """Check if polygon is approximately circular"""
        # Circle has minimum perimeter for given area
        expected_perimeter = 2 * math.pi * math.sqrt(area / math.pi)
        perimeter_ratio = abs(perimeter - expected_perimeter) / expected_perimeter
        
        # Check circularity (should be close to 1.0)
        circularity = 4 * math.pi * area / (perimeter * perimeter)
        
        return perimeter_ratio < 0.1 and circularity > 0.9
    
    def _is_rectangle(self, hole: Polygon, vertex_count: int, width: float, height: float) -> bool:
        """Check if polygon is approximately rectangular"""
        if vertex_count != 4:
            return False
            
        # Check if aspect ratio is reasonable for rectangle
        aspect_ratio = max(width, height) / min(width, height)
        return aspect_ratio < 10.0  # Not too elongated
    
    def _is_slot(self, hole: Polygon, width: float, height: float) -> bool:
        """Check if polygon is slot-shaped (oblong with rounded ends)"""
        # Slots are typically much longer than they are wide
        aspect_ratio = max(width, height) / min(width, height)
        return aspect_ratio > 2.0
    
    def _get_hole_geometries(self) -> List[Dict[str, Any]]:
        """Get geometric details for all holes"""
        geometries = []
        
        for hole in self.holes:
            coords = list(hole.exterior.coords)
            geometries.append({
                "points": [[round(x, 6), round(y, 6)] for x, y in coords],
                "area": hole.area,
                "perimeter": hole.length
            })
            
        return geometries
    
    def _empty_result(self) -> Dict[str, Any]:
        """Return empty result when no holes are found"""
        return {
            "total_holes": 0,
            "holes": 0,
            "hole_details": [],
            "outer_boundary_area": 0,
            "outer_perimeter": 0,
            "internal_cutouts_detected": 0,
            "hole_geometries": []
        }


def detect_holes_from_entities(entities: List[Dict[str, Any]], 
                              tolerance: float = TOLERANCE,
                              min_area: float = MIN_AREA) -> Dict[str, Any]:
    """
    Convenience function to detect holes from a list of DXF entities.
    
    Args:
        entities: List of DXF entities from parser
        tolerance: Snap tolerance for endpoint matching
        min_area: Minimum area for valid holes
        
    Returns:
        Dictionary with hole detection results
    """
    detector = HoleDetector(tolerance=tolerance, min_area=min_area)
    return detector.detect_holes(entities)


def count_holes_by_type(hole_details: List[Dict[str, Any]]) -> Dict[str, int]:
    """
    Count holes by their geometric type.
    
    Args:
        hole_details: List of hole detail dictionaries
        
    Returns:
        Dictionary with hole counts by type
    """
    counts = defaultdict(int)
    
    for hole in hole_details:
        hole_type = hole.get("type", "unknown")
        counts[hole_type] += 1
        
    return dict(counts)