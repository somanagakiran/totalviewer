"""
Enhanced hole detection with proper loop finding
"""

import math
from typing import List, Dict, Any, Optional, Tuple
from collections import defaultdict

try:
    from shapely.geometry import Polygon, Point
    SHAPELY_AVAILABLE = True
except ImportError:
    SHAPELY_AVAILABLE = False
    print("[HOLE_DETECTOR] Shapely not available, using fallback methods")

class EnhancedHoleDetector:
    """Enhanced hole detector that properly finds separate closed loops"""
    
    def __init__(self, tolerance: float = 0.01, min_area: float = 0.1):
        self.tolerance = tolerance
        self.min_area = min_area
        self.edges = []
        self.closed_loops = []
        self.outer_boundary = None
        self.holes = []
    
    def detect_holes(self, entities: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Main detection method"""
        try:
            print(f"[HOLE_DETECTOR] Starting detection with {len(entities)} entities")
            
            # Convert entities to edges
            self.edges = self._convert_entities_to_edges(entities)
            print(f"[HOLE_DETECTOR] Converted to {len(self.edges)} edges")
            
            # Find closed loops
            self.closed_loops = self._find_closed_loops()
            print(f"[HOLE_DETECTOR] Found {len(self.closed_loops)} closed loops")
            
            if not self.closed_loops:
                return self._empty_result()
            
            # Find outer boundary (largest area)
            self.outer_boundary = self._find_outer_boundary()
            if not self.outer_boundary:
                return self._empty_result()
            
            print(f"[HOLE_DETECTOR] Outer boundary area: {self.outer_boundary.area:.2f}")
            
            # Identify internal holes
            self.holes = self._identify_internal_holes()
            print(f"[HOLE_DETECTOR] Found {len(self.holes)} internal holes")
            
            # Classify holes
            hole_details = self._classify_holes()
            
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
        """Convert all entities to line segment edges"""
        edges = []
        
        for entity in entities:
            entity_type = entity.get("type", "").upper()
            
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
        start = (entity["x1"], entity["y1"])
        end = (entity["x2"], entity["y2"])
        return [[start, end]]
    
    def _convert_arc(self, entity: Dict[str, Any]) -> List[List[Tuple[float, float]]]:
        """Convert ARC entity to edges by approximation"""
        center = (entity["center"][0], entity["center"][1])
        radius = entity["radius"]
        start_angle = math.radians(entity.get("start_angle", 0))
        end_angle = math.radians(entity.get("end_angle", 360))
        
        # Approximate arc with segments
        angle_range = end_angle - start_angle
        num_segments = max(8, int(abs(angle_range) * 32 / (2 * math.pi)))
        
        edges = []
        prev_point = None
        
        for i in range(num_segments + 1):
            angle = start_angle + (angle_range * i / num_segments)
            x = center[0] + radius * math.cos(angle)
            y = center[1] + radius * math.sin(angle)
            current_point = (x, y)
            
            if prev_point is not None:
                edges.append([prev_point, current_point])
            prev_point = current_point
        
        return edges
    
    def _convert_circle(self, entity: Dict[str, Any]) -> List[List[Tuple[float, float]]]:
        """Convert CIRCLE entity to edges"""
        center = (entity["center"][0], entity["center"][1])
        radius = entity["radius"]
        
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
        center = (entity["center"][0], entity["center"][1])
        major_axis = entity.get("major_axis", 1.0)
        minor_axis = entity.get("minor_axis", 1.0)
        rotation = math.radians(entity.get("rotation", 0))
        
        # Approximate ellipse with segments
        num_segments = 64
        edges = []
        prev_point = None
        
        for i in range(num_segments + 1):
            angle = 2 * math.pi * i / num_segments
            x = major_axis * math.cos(angle)
            y = minor_axis * math.sin(angle)
            
            # Apply rotation
            x_rot = x * math.cos(rotation) - y * math.sin(rotation)
            y_rot = x * math.sin(rotation) + y * math.cos(rotation)
            
            current_point = (center[0] + x_rot, center[1] + y_rot)
            
            if prev_point is not None:
                edges.append([prev_point, current_point])
            prev_point = current_point
        
        return edges
    
    def _find_closed_loops(self) -> List[Polygon]:
        """Find all closed loops in the edges"""
        if not self.edges:
            return []
        
        # Build connectivity graph
        connectivity = defaultdict(list)
        for i, (start, end) in enumerate(self.edges):
            # Normalize points to avoid floating point issues
            start_norm = self._normalize_point(start)
            end_norm = self._normalize_point(end)
            connectivity[start_norm].append((end_norm, i))
            connectivity[end_norm].append((start_norm, i))
        
        print(f"[HOLE_DETECTOR] Connectivity graph has {len(connectivity)} nodes")
        
        # Find closed loops
        visited_edges = set()
        closed_loops = []
        
        for start_node in connectivity:
            for end_node, edge_idx in connectivity[start_node]:
                if edge_idx in visited_edges:
                    continue
                
                # Try to trace a closed loop
                loop = self._trace_loop(start_node, edge_idx, connectivity, visited_edges)
                if loop:
                    # Convert to polygon
                    if SHAPELY_AVAILABLE:
                        try:
                            poly = Polygon(loop)
                            if poly.is_valid and poly.area >= self.min_area:
                                closed_loops.append(poly)
                                print(f"[HOLE_DETECTOR] Found closed loop with area: {poly.area:.2f}")
                        except:
                            pass
                    else:
                        # Fallback: just store the loop coordinates
                        if len(loop) >= 3:
                            closed_loops.append(loop)
        
        return closed_loops
    
    def _normalize_point(self, point: Tuple[float, float]) -> Tuple[float, float]:
        """Normalize point coordinates to handle floating point precision"""
        return (round(point[0], 6), round(point[1], 6))
    
    def _trace_loop(self, start_node: Tuple[float, float], start_edge_idx: int, 
                   connectivity: Dict, visited_edges: set) -> Optional[List[Tuple[float, float]]]:
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
            
            # Safety check to prevent infinite loops
            if len(path) > 200:
                break
        
        return None
    
    def _find_outer_boundary(self) -> Optional[Polygon]:
        """Find the outer boundary (largest area closed loop)"""
        if not self.closed_loops:
            return None
        
        # Find polygon with largest area
        largest_polygon = None
        largest_area = 0
        
        for polygon in self.closed_loops:
            if SHAPELY_AVAILABLE:
                area = polygon.area
            else:
                # Calculate area for coordinate list
                area = self._calculate_polygon_area(polygon)
            
            if area > largest_area:
                largest_area = area
                largest_polygon = polygon
        
        return largest_polygon
    
    def _calculate_polygon_area(self, coords: List[Tuple[float, float]]) -> float:
        """Calculate area of polygon given coordinates (Shoelace formula)"""
        if len(coords) < 3:
            return 0
        
        area = 0
        n = len(coords)
        for i in range(n):
            j = (i + 1) % n
            area += coords[i][0] * coords[j][1]
            area -= coords[j][0] * coords[i][1]
        
        return abs(area) / 2
    
    def _identify_internal_holes(self) -> List[Polygon]:
        """Identify internal holes (closed loops inside outer boundary)"""
        if not self.outer_boundary:
            return []
        
        holes = []
        outer = self.outer_boundary
        
        for polygon in self.closed_loops:
            # Skip the outer boundary itself
            if SHAPELY_AVAILABLE:
                if polygon.equals(outer):
                    continue
                
                # Check if this polygon is inside the outer boundary
                try:
                    centroid = polygon.centroid
                    if outer.contains(centroid):
                        holes.append(polygon)
                except:
                    pass
            else:
                # Fallback for non-Shapely case
                # Check if polygon area is significantly smaller
                if hasattr(polygon, 'area'):
                    if polygon.area < outer.area * 0.5:
                        holes.append(polygon)
                else:
                    # Compare coordinate lists
                    if len(polygon) < len(outer):
                        holes.append(polygon)
        
        return holes
    
    def _classify_holes(self) -> List[Dict[str, Any]]:
        """Classify holes by their geometric shape"""
        hole_details = []
        
        for i, hole in enumerate(self.holes):
            if SHAPELY_AVAILABLE:
                area = hole.area
                perimeter = hole.length
                coords = list(hole.exterior.coords)
            else:
                area = self._calculate_polygon_area(hole)
                perimeter = self._calculate_perimeter(hole)
                coords = hole
            
            shape_type = self._determine_shape_type(area, perimeter, coords)
            
            hole_info = {
                "id": i + 1,
                "type": shape_type,
                "area": round(area, 6),
                "perimeter": round(perimeter, 6),
                "vertices": len(coords) - 1,  # Exclude closing vertex
                "center": self._get_polygon_center(coords)
            }
            hole_details.append(hole_info)
        
        return hole_details
    
    def _calculate_perimeter(self, coords: List[Tuple[float, float]]) -> float:
        """Calculate perimeter of polygon given coordinates"""
        if len(coords) < 2:
            return 0
        
        perimeter = 0
        for i in range(len(coords) - 1):
            dx = coords[i+1][0] - coords[i][0]
            dy = coords[i+1][1] - coords[i][1]
            perimeter += math.sqrt(dx*dx + dy*dy)
        
        return perimeter
    
    def _get_polygon_center(self, coords: List[Tuple[float, float]]) -> Tuple[float, float]:
        """Get center point of polygon"""
        if not coords:
            return (0, 0)
        
        x_sum = sum(coord[0] for coord in coords)
        y_sum = sum(coord[1] for coord in coords)
        
        return (x_sum / len(coords), y_sum / len(coords))
    
    def _determine_shape_type(self, area: float, perimeter: float, coords: List[Tuple[float, float]]) -> str:
        """Determine the type of shape based on geometric properties"""
        if len(coords) < 3:
            return "invalid"
        
        # Calculate circularity (4pi * area / perimeter^2)
        if perimeter > 0:
            circularity = (4 * math.pi * area) / (perimeter * perimeter)
        else:
            circularity = 0
        
        num_vertices = len(coords) - 1  # Exclude closing vertex
        
        # Shape classification
        if circularity > 0.85:
            return "circle"
        elif num_vertices == 3:
            return "triangle"
        elif num_vertices == 4:
            # Check if it's a rectangle (opposite sides equal, angles ~90deg)
            if self._is_rectangle(coords):
                return "rectangle"
            else:
                return "quadrilateral"
        elif num_vertices <= 8:
            return f"polygon_{num_vertices}"
        else:
            return "irregular"
    
    def _is_rectangle(self, coords: List[Tuple[float, float]]) -> bool:
        """Check if coordinates form a rectangle"""
        if len(coords) != 5:  # 4 vertices + closing vertex
            return False
        
        # Simple check: opposite sides should be equal and angles ~90deg
        # This is a simplified check - for production you'd want more robust logic
        return True  # For now, assume all 4-vertex polygons are rectangles
    
    def _get_hole_geometries(self) -> List[Dict[str, Any]]:
        """Get detailed geometry information for each hole"""
        geometries = []
        
        for i, hole in enumerate(self.holes):
            if SHAPELY_AVAILABLE:
                coords = [[x, y] for x, y in hole.exterior.coords[:-1]]  # Exclude closing vertex
                center = [hole.centroid.x, hole.centroid.y]
            else:
                coords = [[x, y] for x, y in hole[:-1]]  # Exclude closing vertex
                center = self._get_polygon_center(hole)
            
            geometries.append({
                "id": i + 1,
                "coordinates": coords,
                "center": center
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
                              tolerance: float = 0.01,
                              min_area: float = 0.1) -> Dict[str, Any]:
    """Convenience function to detect holes from entities"""
    detector = EnhancedHoleDetector(tolerance=tolerance, min_area=min_area)
    return detector.detect_holes(entities)

def count_holes_by_type(hole_details: List[Dict[str, Any]]) -> Dict[str, int]:
    """Count holes by their shape type"""
    counts = {}
    for hole in hole_details:
        shape_type = hole["type"]
        counts[shape_type] = counts.get(shape_type, 0) + 1
    return counts