"""
Geometry Analyzer
Uses Shapely for polygon operations:
  - Outer cutting boundary detection
  - Title block exclusion
  - Hole counting
  - Perimeter calculation

Algorithm:
  1. Convert all closed contours → Shapely Polygons
  2. Sort by area descending
  3. Detect and exclude title block (large axis-aligned rectangle at drawing edge)
  4. Largest remaining polygon → outer boundary
  5. Polygons fully contained within outer boundary → holes
"""

import math
from typing import Optional

try:
    from shapely.geometry import Polygon, MultiPolygon, LinearRing
    from shapely.validation import make_valid
    SHAPELY_OK = True
except ImportError:
    SHAPELY_OK = False
    print("[WARNING] Shapely not installed — hole/perimeter analysis disabled.")


# ─── Minimum polygon area to consider (filters noise / tiny artifacts) ───────
MIN_AREA = 0.01


def analyze_geometry(
    closed_contours: list[list],
    bounding_box: dict,
) -> dict:
    """
    Main analysis entry point.

    Args:
        closed_contours: list of closed point loops  [[x,y], ...] or [(x,y), ...]
        bounding_box:    {"minX", "minY", "maxX", "maxY", "width", "height"}

    Returns:
        {
            "holes": int,
            "perimeter": float,
            "outer_boundary_area": float,
        }
    """
    if not SHAPELY_OK or not closed_contours:
        return _fallback_result()

    # ── 1. Convert contours → valid Shapely polygons ──────────────────────────
    polygons = _build_polygons(closed_contours)

    if not polygons:
        return _fallback_result()

    # ── 2. Sort by area (largest first) ──────────────────────────────────────
    polygons.sort(key=lambda p: p.area, reverse=True)

    # ── 3. Detect and exclude title block ────────────────────────────────────
    title_block_idx = _find_title_block(polygons, bounding_box)

    # ── 4. Find outer boundary (largest non-title-block polygon) ─────────────
    outer_poly: Optional[Polygon] = None
    outer_idx: Optional[int] = None

    for i, poly in enumerate(polygons):
        if i == title_block_idx:
            continue
        outer_poly = poly
        outer_idx = i
        break

    if outer_poly is None or outer_poly.is_empty:
        return _fallback_result()

    # ── 5. Count holes (polygons inside outer boundary) ──────────────────────
    hole_count = 0
    for i, poly in enumerate(polygons):
        if i == outer_idx or i == title_block_idx:
            continue
        if poly.area < MIN_AREA:
            continue
        try:
            # A hole must be entirely contained within the outer boundary
            if outer_poly.contains(poly):
                hole_count += 1
        except Exception:
            pass

    # ── 6. Perimeter = outer boundary exterior length ─────────────────────────
    try:
        perimeter = outer_poly.exterior.length
    except Exception:
        perimeter = _fallback_perimeter(bounding_box)

    return {
        "holes": hole_count,
        "perimeter": round(perimeter, 3),
        "outer_boundary_area": round(outer_poly.area, 3),
    }


# ═════════════════════════════════════════════════════════════════════════════
# POLYGON BUILDING
# ═════════════════════════════════════════════════════════════════════════════

def _build_polygons(contours: list[list]) -> list[Polygon]:
    """Convert raw point lists to valid Shapely Polygons."""
    result = []

    for contour in contours:
        if not contour or len(contour) < 3:
            continue

        # Normalise to list of (float, float) tuples
        try:
            pts = [(float(p[0]), float(p[1])) for p in contour]
        except (TypeError, IndexError):
            continue

        # Deduplicate consecutive identical points
        pts = _deduplicate(pts)
        if len(pts) < 3:
            continue

        # Ensure the contour is closed
        if pts[0] != pts[-1]:
            pts.append(pts[0])

        try:
            poly = Polygon(pts)

            # Attempt to fix invalid polygon (self-intersections, etc.)
            if not poly.is_valid:
                poly = make_valid(poly)

            # make_valid can return GeometryCollection — keep only Polygons
            if poly.geom_type == "GeometryCollection":
                for geom in poly.geoms:
                    if geom.geom_type == "Polygon" and geom.area >= MIN_AREA:
                        result.append(geom)
                continue
            elif poly.geom_type == "MultiPolygon":
                for geom in poly.geoms:
                    if geom.area >= MIN_AREA:
                        result.append(geom)
                continue

            if poly.is_valid and poly.area >= MIN_AREA:
                result.append(poly)

        except Exception:
            pass

    return result


def _deduplicate(pts: list[tuple]) -> list[tuple]:
    """Remove consecutive duplicate points."""
    if not pts:
        return pts
    out = [pts[0]]
    for p in pts[1:]:
        if abs(p[0] - out[-1][0]) > 1e-9 or abs(p[1] - out[-1][1]) > 1e-9:
            out.append(p)
    return out


# ═════════════════════════════════════════════════════════════════════════════
# TITLE BLOCK DETECTION
# ═════════════════════════════════════════════════════════════════════════════

def _find_title_block(polygons: list[Polygon], bbox: dict) -> Optional[int]:
    """
    Identify the title block polygon (if present) and return its index.

    Heuristic rules:
      1. Must be a simple axis-aligned rectangle (4 exterior coordinates).
      2. Must span ≥ 60% of the drawing bounding box in both dimensions.
      3. Must be one of the two largest polygons.

    Returns None if no title block is detected.
    """
    if not polygons:
        return None

    bb_width  = bbox.get("width", 0)
    bb_height = bbox.get("height", 0)
    bb_area   = bb_width * bb_height

    if bb_area < 1:
        return None

    # Only check the two largest polygons for title block
    for i, poly in enumerate(polygons[:2]):
        try:
            if not _is_axis_aligned_rect(poly):
                continue
            # Check coverage
            ratio = poly.area / bb_area
            if ratio >= 0.50:
                return i
        except Exception:
            pass

    return None


def _is_axis_aligned_rect(poly: Polygon) -> bool:
    """
    Return True if the polygon is (approximately) an axis-aligned rectangle.
    Allows a small angular tolerance for slightly rotated title blocks.
    """
    coords = list(poly.exterior.coords)
    # A rectangle has 5 coords (4 unique + closing repeat)
    if len(coords) not in (5, 4):
        return False

    unique = coords[:-1]  # drop the closing duplicate
    if len(unique) != 4:
        return False

    xs = [p[0] for p in unique]
    ys = [p[1] for p in unique]

    x_range = max(xs) - min(xs)
    y_range = max(ys) - min(ys)

    if x_range < 1 or y_range < 1:
        return False

    # Each point must be at a corner of the bounding box (with tolerance)
    TOL = max(x_range, y_range) * 0.02
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)

    for x, y in unique:
        on_x = abs(x - min_x) < TOL or abs(x - max_x) < TOL
        on_y = abs(y - min_y) < TOL or abs(y - max_y) < TOL
        if not (on_x and on_y):
            return False

    return True


# ═════════════════════════════════════════════════════════════════════════════
# FALLBACKS
# ═════════════════════════════════════════════════════════════════════════════

def _fallback_result() -> dict:
    return {"holes": 0, "perimeter": 0.0, "outer_boundary_area": 0.0}


def _fallback_perimeter(bbox: dict) -> float:
    """Estimate perimeter from bounding box if Shapely fails."""
    w = bbox.get("width", 0)
    h = bbox.get("height", 0)
    return round(2 * (w + h), 3)
