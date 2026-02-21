"""
Optimized Hole Detector - contour-based, entity-type agnostic
=============================================================

Algorithm
---------
1.  Convert every DXF entity's tessellated points to Shapely LineStrings.
    This handles ALL entity types: LINE, ARC, CIRCLE, LWPOLYLINE, POLYLINE,
    SPLINE, ELLIPSE - any entity the parser has already tessellated to points.

2.  Snap all coordinates to a fine grid (SNAP units) so that nearly-coincident
    endpoints (e.g. the tessellated endpoint of an ARC vs. the exact endpoint
    of an adjacent LINE) become exactly coincident and can be joined.

3.  Node all LineStrings together with unary_union() - splits edges at every
    shared endpoint and produces a clean planar graph.

4.  Run shapely.ops.polygonize() to reconstruct every closed ring in the
    planar graph.  polygonize returns one Polygon per closed loop regardless
    of which entity types contributed to it:
        * a single CIRCLE entity                  -> 1 polygon
        * a rectangle drawn as 4 LINE entities    -> 1 polygon
        * a slot drawn as 2 ARCs + 2 LINEs        -> 1 polygon
        * a hexagon drawn as 6 LINE entities      -> 1 polygon
        * any closed LWPOLYLINE / SPLINE          -> 1 polygon
        * any irregular mix of entities           -> 1 polygon

5.  Deduplicate polygons that share the same centroid and area.

6.  Identify the outer boundary: the largest polygon that is not a
    drawing-frame rectangle covering >= 95 % of the drawing bbox.

7.  Count holes: every closed ring whose centroid lies inside the outer
    boundary (with a small tolerance buffer for boundary-touching cases).
"""

import math
from typing import List, Dict, Any, Optional, Tuple

try:
    from shapely.geometry import Polygon, Point, LineString
    from shapely.validation import make_valid
    from shapely.ops import polygonize, unary_union
    SHAPELY_AVAILABLE = True
except ImportError:
    SHAPELY_AVAILABLE = False
    print("[HOLE_DETECTOR] Shapely not available - hole detection disabled")


# -- Tunables ------------------------------------------------------------------
SNAP        = 0.1    # coordinate grid snap (must be >= DXF FLATTEN_DISTANCE)
MIN_AREA    = 0.01   # discard polygons smaller than this (drawing units^2)
DEDUP_DIST  = 0.5    # centroid proximity threshold for duplicate suppression
MAX_SEGS    = 50000  # polygonize safety limit (prevents hang on huge files)


# ===============================================================================
# PUBLIC API
# ===============================================================================

def detect_holes_from_entities(
    entities: List[Dict[str, Any]],
    tolerance: float = SNAP,
    min_area:  float = MIN_AREA,
) -> Dict[str, Any]:
    """
    Detect all internal closed loops (holes) in a set of DXF entities.

    Parameters
    ----------
    entities  : list of geometry dicts produced by dxf_parser.py
                Each dict must have a "points" key with [[x,y],...] coordinates.
    tolerance : coordinate snap distance for endpoint merging (drawing units).
                Should be >= tessellation chord deviation (default 0.1).
    min_area  : minimum polygon area; smaller polygons are discarded.

    Returns
    -------
    dict with keys:
        total_holes, holes, hole_details, outer_boundary_area,
        outer_perimeter, external_perimeter, internal_perimeter,
        internal_cutouts_detected, hole_geometries
    """
    if not SHAPELY_AVAILABLE:
        return _empty_result()

    if not entities:
        return _empty_result()

    snap = max(tolerance, 1e-6)

    # -- 1. Convert entities -> snapped LineStrings -----------------------------
    lines: list = []
    all_xs: list = []
    all_ys: list = []

    for entity in entities:
        pts = entity.get("points", [])
        if len(pts) < 2:
            continue
        try:
            coords: list = []
            for p in pts:
                x = round(float(p[0]) / snap) * snap
                y = round(float(p[1]) / snap) * snap
                coords.append((x, y))
                all_xs.append(x)
                all_ys.append(y)

            # Remove consecutive duplicates
            deduped: list = [coords[0]]
            for c in coords[1:]:
                if abs(c[0] - deduped[-1][0]) > 1e-9 or abs(c[1] - deduped[-1][1]) > 1e-9:
                    deduped.append(c)

            if len(deduped) >= 2:
                lines.append(LineString(deduped))
        except Exception:
            continue

    if not lines:
        print("[HOLE_DETECTOR] No segments extracted from entities")
        return _empty_result()

    print(f"[HOLE_DETECTOR] {len(lines)} segments from {len(entities)} entities")

    if len(lines) > MAX_SEGS:
        print(f"[HOLE_DETECTOR] Segment count {len(lines)} > MAX_SEGS={MAX_SEGS} - aborting")
        return _empty_result()

    # Drawing bbox area (used for frame detection)
    bbox_area = 0.0
    if all_xs and all_ys:
        dx = max(all_xs) - min(all_xs)
        dy = max(all_ys) - min(all_ys)
        bbox_area = dx * dy

    # -- 2. Node segments and polygonize ---------------------------------------
    try:
        merged    = unary_union(lines)
        raw_polys = list(polygonize(merged))
        print(f"[HOLE_DETECTOR] polygonize -> {len(raw_polys)} candidate rings")
    except Exception as exc:
        print(f"[HOLE_DETECTOR] polygonize error: {exc}")
        return _empty_result()

    # -- 3. Validate and collect candidate polygons ----------------------------
    #
    # polygonize() can return polygons WITH interior holes (the "annular" face
    # between nested rings).  We deliberately extract only the exterior ring of
    # each returned polygon so that:
    #   - The outer rectangle is treated as a solid rectangle (full area)
    #     rather than as a rectangle-minus-hole-polygon (reduced area).
    #   - Each nested ring (circle, slot, etc.) is treated as its own solid
    #     polygon.
    # After deduplication the two representations collapse to one per shape.
    #
    candidates: list = []
    for p in raw_polys:
        if p.is_empty:
            continue
        if not p.is_valid:
            p = make_valid(p)

        polys_to_add: list = []
        if p.geom_type == "MultiPolygon":
            polys_to_add = list(p.geoms)
        elif p.geom_type == "Polygon":
            polys_to_add = [p]

        for sub in polys_to_add:
            if sub.is_empty:
                continue
            # Use only the exterior ring - discards interior holes so the
            # polygon represents the full enclosed area of each ring.
            try:
                ext = Polygon(sub.exterior.coords)
                if not ext.is_valid:
                    ext = make_valid(ext)
                if ext.geom_type == "Polygon" and not ext.is_empty and ext.area >= min_area:
                    candidates.append(ext)
            except Exception:
                pass

    if not candidates:
        print("[HOLE_DETECTOR] No valid polygons after area filter")
        return _empty_result()

    # Deduplicate, sort largest first
    candidates = _dedup(candidates)
    candidates.sort(key=lambda p: p.area, reverse=True)
    print(f"[HOLE_DETECTOR] {len(candidates)} unique candidate polygons")

    # -- 4. Identify outer boundary --------------------------------------------
    outer = _find_outer(candidates, bbox_area)
    if outer is None:
        print("[HOLE_DETECTOR] Could not identify outer boundary")
        return _empty_result()

    print(f"[HOLE_DETECTOR] Outer boundary  area={outer.area:.4f}  "
          f"perimeter={outer.exterior.length:.4f}")

    # -- 5. Identify holes -----------------------------------------------------
    bx0, by0, bx1, by1 = outer.bounds
    max_dim   = max(bx1 - bx0, by1 - by0, 1.0)
    outer_buf = outer.buffer(max_dim * 0.005)   # tolerance for boundary-hugging holes

    seen: list = []   # accepted (cx, cy) for deduplication
    holes: list = []

    for poly in candidates:
        if _same_shape(poly, outer):
            continue
        try:
            c      = poly.centroid
            cx, cy = c.x, c.y

            if not (outer.contains(c) or outer_buf.contains(c)):
                continue

            if any(math.hypot(cx - sx, cy - sy) < DEDUP_DIST for sx, sy in seen):
                continue

            seen.append((cx, cy))
            holes.append(poly)
        except Exception:
            continue

    print(f"[HOLE_DETECTOR] {len(holes)} holes detected")

    # -- 6. Build result -------------------------------------------------------
    hole_details    = [_describe_hole(h) for h in holes]
    hole_geometries = [_hole_geom(h, i)  for i, h in enumerate(holes)]

    # Compute internal perimeter: sum of all hole perimeters
    internal_perimeter = sum(h.exterior.length for h in holes)

    return {
        "total_holes":               len(holes),
        "holes":                     len(holes),
        "hole_details":              hole_details,
        "outer_boundary_area":       round(outer.area, 6),
        "outer_perimeter":           round(outer.exterior.length, 6),
        "external_perimeter":        round(outer.exterior.length, 6),  # EP
        "internal_perimeter":        round(internal_perimeter, 6),     # IP
        "internal_cutouts_detected": len(holes),
        "hole_geometries":           hole_geometries,
    }


# ===============================================================================
# HELPERS
# ===============================================================================

def _find_outer(candidates: list, bbox_area: float = 0.0) -> Optional["Polygon"]:
    """
    Return the outer boundary polygon.

    The largest polygon returned by polygonize is always the outer boundary
    of the part.  All smaller polygons whose centroids fall inside it are holes.
    """
    return candidates[0] if candidates else None


def _same_shape(a: "Polygon", b: "Polygon", tol: float = 0.05) -> bool:
    """True when a and b represent the same physical polygon."""
    if a.area <= 0 or b.area <= 0:
        return False
    if abs(a.area - b.area) / max(a.area, b.area) > tol:
        return False
    try:
        return a.intersection(b).area / min(a.area, b.area) > 0.90
    except Exception:
        return False


def _dedup(polygons: list) -> list:
    """
    Remove duplicate polygons.  Two polygons are duplicates when their
    centroids are within DEDUP_DIST of each other AND their areas agree
    within 5 %.
    """
    unique: list = []
    for p in polygons:
        try:
            c = p.centroid
            is_dup = any(
                c.distance(q.centroid) < DEDUP_DIST
                and max(p.area, q.area) > 0
                and abs(p.area - q.area) / max(p.area, q.area) < 0.05
                for q in unique
            )
            if not is_dup:
                unique.append(p)
        except Exception:
            unique.append(p)
    return unique


def _describe_hole(poly: "Polygon") -> dict:
    """Return a metadata dict classifying a hole polygon by shape."""
    try:
        area    = poly.area
        ext_len = poly.exterior.length
        iso     = (ext_len ** 2) / area if area > 0 else 0
        bounds  = poly.bounds
        w       = bounds[2] - bounds[0]
        h       = bounds[3] - bounds[1]
        aspect  = max(w, h) / max(min(w, h), 1e-9)
        c       = poly.centroid

        # Shape classification
        if iso < 14.5:
            shape = "circle"
        elif aspect > 2.5:
            shape = "slot"
        else:
            coords = list(poly.exterior.coords)
            unique = coords[:-1] if coords[0] == coords[-1] else coords
            n = len(unique)
            shape = {3: "triangle", 4: "rectangle", 6: "hexagon"}.get(n, "polygon")

        result: dict = {
            "type":      shape,
            "location":  "internal",
            "area":      round(area, 4),
            "perimeter": round(ext_len, 4),
            "center":    [round(c.x, 4), round(c.y, 4)],
            "bounds":    [round(b, 4) for b in bounds],
        }

        if shape == "circle":
            result["diameter"] = round(math.sqrt(area / math.pi) * 2, 4)
        elif shape in ("slot", "rectangle"):
            result["width"]  = round(min(w, h), 4)
            result["height"] = round(max(w, h), 4)

        return result

    except Exception:
        return {"type": "unknown", "location": "internal", "area": 0.0, "perimeter": 0.0}


def _hole_geom(poly: "Polygon", index: int) -> dict:
    """Return a geometry dict for a hole (for frontend rendering)."""
    try:
        coords = [[round(x, 4), round(y, 4)] for x, y in poly.exterior.coords[:-1]]
        c      = poly.centroid
        return {
            "id":          index + 1,
            "coordinates": coords,
            "center":      [round(c.x, 4), round(c.y, 4)],
            "area":        round(poly.area, 4),
            "perimeter":   round(poly.exterior.length, 4),
            "bounds":      [round(b, 4) for b in poly.bounds],
        }
    except Exception:
        return {"id": index + 1, "coordinates": [], "center": [0, 0]}


def _empty_result() -> dict:
    return {
        "total_holes":               0,
        "holes":                     0,
        "hole_details":              [],
        "outer_boundary_area":       0.0,
        "outer_perimeter":           0.0,
        "external_perimeter":        0.0,
        "internal_perimeter":        0.0,
        "internal_cutouts_detected": 0,
        "hole_geometries":           [],
    }


def count_holes_by_type(hole_details: list) -> dict:
    """Count holes grouped by their shape type."""
    counts: dict = {}
    for hole in hole_details:
        t = hole.get("type", "unknown")
        counts[t] = counts.get(t, 0) + 1
    return counts
