"""
Advanced Hole Detection Engine for DXF Files

This module implements a comprehensive hole detection system that can identify
ANY internal closed contour inside the outer boundary, regardless of how it was
created (LINE, ARC, CIRCLE, LWPOLYLINE, POLYLINE, SPLINE, ELLIPSE, or mixed entities).

Key Features:
- Converts all DXF entities to line segments
- Builds geometry graph and traces closed loops
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
        self.nodes = defaultdict(list)
        self.closed_loops = []
        self.outer_boundary = None
        self.holes = []
        
    def detect_holes(self, entities: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Main entry point for hole detection.
        
        Args:
            entities: List of DXF entities from parser
            
        Returns:
            Dictionary with hole detection results
        """
        print(f"[HOLE_DETECTOR] Starting detection with {len(entities)} entities")
        
        # Step 1: Convert all entities to edges
        self.edges = self._convert_entities_to_edges(entities)
        print(f"[HOLE_DETECTOR] Converted to {len(self.edges)} edges")
        
        # Step 2: Build geometry graph
        self._build_geometry_graph()
        
        # Step 3: Detect closed loops
        self.closed_loops = self._detect_closed_loops()
        print(f"[HOLE_DETECTOR] Found {len(self.closed_loops)} closed loops")
        
        # Step 4: Find outer boundary (largest area)
        self.outer_boundary = self._find_outer_boundary()
        
        if not self.outer_boundary:
            print("[HOLE_DETECTOR] No outer boundary found")
            return self._empty_result()
            
        print(f"[HOLE_DETECTOR] Outer boundary area: {self.outer_boundary.area:.3f}")
        
        # Step 5: Identify internal holes
        self.holes = self._identify_internal_holes()
        print(f"[HOLE_DETECTOR] Found {len(self.holes)} internal holes")
        
        # Step 6: Classify holes by shape
        hole_details = self._classify_holes()
        
        return {
            "total_holes": len(self.holes),
            "holes": len(self.holes),  # Legacy compatibility
            "hole_details": hole_details,
            "outer_boundary_area": self.outer_boundary.area if self.outer_boundary else 0,
            "outer_perimeter": self.outer_boundary.length if self.outer_boundary else 0,
            "internal_cutouts_detected": len(self.holes),
            "hole_geometries": self._get_hole_geometries()
        }
    
    def _convert_entities_to_edges(self, entities: List[Dict[str, Any]]) -> List[List[Tuple[float, float]]]:
        """Convert all DXF entities to line segments (edges)"""
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
    
    def _build_geometry_graph(self):
        """Build graph where nodes are endpoints and edges connect them"""
        self.nodes = defaultdict(list)
        
        for edge_idx, (start, end) in enumerate(self.edges):
            # Snap endpoints to handle floating point errors
            start_snapped = self._snap_point(start)
            end_snapped = self._snap_point(end)
            
            # Skip zero-length edges
            if start_snapped == end_snapped:
                continue
                
            # Add to graph (bidirectional)
            self.nodes[start_snapped].append((end_snapped, edge_idx))
            self.nodes[end_snapped].append((start_snapped, edge_idx))
    
    def _detect_closed_loops(self) -> List[List[Tuple[float, float]]]:
        """Detect all closed loops in the geometry graph"""
        visited_edges = set()
        closed_loops = []
        
        # Keep trying until all edges are visited
        while len(visited_edges) < len(self.edges):
            # Find an unvisited edge to start from
            start_edge_idx = None
            for i in range(len(self.edges)):
                if i not in visited_edges:
                    start_edge_idx = i
                    break
            
            if start_edge_idx is None:
                break
                
            # Get the start node for this edge
            start_edge = self.edges[start_edge_idx]
            start_node = self._snap_point(start_edge[0])
            
            # Trace loop starting from this edge
            loop = self._trace_loop(start_node, start_edge_idx, visited_edges)
            if loop and len(loop) >= 3:  # Minimum triangle
                closed_loops.append(loop)
        
        return closed_loops
    
    def _trace_loop(self, start_node: Tuple[float, float], start_edge_idx: int, 
                   visited_edges: set) -> Optional[List[Tuple[float, float]]]:
        """Trace a closed loop starting from a given edge"""
        current_node = start_node
        path = [start_node]
        local_visited = set([start_edge_idx])
        
        while True:
            # Find next unvisited edge from current node
            next_edge = None
            next_node = None
            
            # Get all edges from current node
            if current_node not in self.nodes:
                return None
                
            for neighbor_node, edge_idx in self.nodes[current_node]:
                if edge_idx not in local_visited and edge_idx not in visited_edges:
                    next_edge = edge_idx
                    next_node = neighbor_node
                    break
            
            if next_edge is None:
                # No unvisited edges from current node
                # Check if we can close the loop with existing path
                if current_node == start_node and len(path) > 2:
                    # We have a closed loop!
                    visited_edges.update(local_visited)
                    return path
                else:
                    # Dead end
                    return None
                
            # Add to path
            path.append(next_node)
            local_visited.add(next_edge)
            current_node = next_node
            
            # Check if we closed the loop
            if current_node == start_node and len(path) > 2:
                # Mark all edges in this loop as visited
                visited_edges.update(local_visited)
                return path
                
            # Safety check - prevent infinite loops
            if len(path) > 200:  # Reduced from 1000 to prevent infinite loops
                return None
    
    def _find_outer_boundary(self) -> Optional[Polygon]:
        """Find the outer boundary (largest area closed loop)"""
        if not self.closed_loops:
            return None
            
        # Convert loops to polygons and find largest
        largest_area = 0
        largest_polygon = None
        
        for loop in self.closed_loops:
            try:
                polygon = Polygon(loop)
                if polygon.is_valid and polygon.area > largest_area:
                    largest_area = polygon.area
                    largest_polygon = polygon
            except:
                continue
                
        return largest_polygon
    
    def _identify_internal_holes(self) -> List[Polygon]:
        """Identify internal holes (closed loops inside outer boundary)"""
        if not self.outer_boundary:
            return []
            
        holes = []
        outer_boundary = self.outer_boundary
        
        for loop in self.closed_loops:
            try:
                loop_polygon = Polygon(loop)
                
                # Skip invalid or too small polygons
                if not loop_polygon.is_valid or loop_polygon.area < self.min_area:
                    continue
                    
                # Skip if it's the outer boundary itself
                if loop_polygon.equals(outer_boundary):
                    continue
                    
                # Check if loop is inside outer boundary
                loop_centroid = loop_polygon.centroid
                if outer_boundary.contains(loop_centroid) or outer_boundary.touches(loop_centroid):
                    # Additional check: ensure it's actually inside, not just touching
                    if outer_boundary.intersection(loop_polygon).area > 0:
                        holes.append(loop_polygon)
                        
            except Exception as e:
                print(f"[HOLE_DETECTOR] Error processing loop: {e}")
                continue
                
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
            diameter = width if abs(width - height) < self.tolerance else (width + height) / 2
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
            
        # Check if opposite sides are parallel and equal length
        coords = list(hole.exterior.coords)
        
        # Calculate side lengths
        side_lengths = []
        for i in range(4):
            p1 = coords[i]
            p2 = coords[i + 1]
            length = math.sqrt((p2[0] - p1[0])**2 + (p2[1] - p1[1])**2)
            side_lengths.append(length)
        
        # Check if opposite sides are equal (within tolerance)
        return (abs(side_lengths[0] - side_lengths[2]) < self.tolerance and 
                abs(side_lengths[1] - side_lengths[3]) < self.tolerance)
    
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
    
    def _snap_point(self, point: Tuple[float, float]) -> Tuple[float, float]:
        """Snap point to grid to handle floating point errors"""
        x, y = point
        snapped_x = round(x / self.tolerance) * self.tolerance
        snapped_y = round(y / self.tolerance) * self.tolerance
        return (snapped_x, snapped_y)
    
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