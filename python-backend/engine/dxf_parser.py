"""
DXF Parsing Engine
Extracts geometry from DXF files using ezdxf with full entity support.

Supported entities:
  LINE, ARC, CIRCLE, ELLIPSE, LWPOLYLINE, POLYLINE, SPLINE, INSERT (blocks)

Strategy:
  - Use ezdxf path module (make_path + flattening) for universal tessellation
  - Retain raw entity metadata (center, radius, angles) for high-quality rendering
  - Explode INSERT blocks recursively with correct transform application
  - Collect closed contours separately for the geometry analyser
"""

import math
from typing import Any

import ezdxf
from ezdxf.math import Matrix44, Vec3, BSpline
from ezdxf import path as ezpath

# ─── Constants ────────────────────────────────────────────────────────────────
FLATTEN_DISTANCE = 0.1          # max chord deviation for curve tessellation (mm)
ARC_SEGMENTS_PER_DEG = 0.5      # segments per degree for arcs
MIN_CIRCLE_SEGMENTS = 64
SPLINE_SEGMENTS = 100
TOLERANCE = 1e-4                # coordinate snap tolerance

SUPPORTED_TYPES = frozenset({
    "LINE", "ARC", "CIRCLE", "ELLIPSE",
    "LWPOLYLINE", "POLYLINE", "SPLINE", "INSERT",
})

# ─── Unit name map ────────────────────────────────────────────────────────────
UNIT_MAP = {
    0: "Unitless", 1: "Inches", 2: "Feet", 3: "Miles",
    4: "Millimeters", 5: "Centimeters", 6: "Meters", 7: "Kilometers",
    8: "Microinches", 9: "Mils", 10: "Yards", 14: "Decimeters",
}


# ═════════════════════════════════════════════════════════════════════════════
# PUBLIC API
# ═════════════════════════════════════════════════════════════════════════════

def parse_dxf(filepath: str) -> dict:
    """
    Parse a DXF file and return:
      - geometry     : list of geometry items for the frontend renderer
      - closed_contours : list of closed point loops for the analyser
      - bounding_box : {minX, minY, maxX, maxY, width, height}
      - units        : unit string
      - layers       : list of layer names
      - entity_count : total number of extracted entities
    """
    doc = ezdxf.readfile(filepath)
    msp = doc.modelspace()

    units = _get_units(doc)
    layers = _get_layers(doc)

    geometry: list[dict] = []
    closed_contours: list[list[tuple]] = []

    # Walk the model space, exploding INSERT blocks
    _walk_entities(msp, doc, Matrix44(), geometry, closed_contours)

    # Also chain disconnected line segments into closed loops
    line_loops = _chain_segments_to_loops(geometry)
    closed_contours.extend(line_loops)

    bbox = _bounding_box(geometry)

    return {
        "geometry": geometry,
        "closed_contours": closed_contours,
        "bounding_box": bbox,
        "units": units,
        "layers": layers,
        "entity_count": len(geometry),
    }


# ═════════════════════════════════════════════════════════════════════════════
# ENTITY WALKER
# ═════════════════════════════════════════════════════════════════════════════

def _walk_entities(
    entity_collection,
    doc: ezdxf.document.Drawing,
    transform: Matrix44,
    geometry: list,
    closed_contours: list,
    depth: int = 0,
) -> None:
    """Recursively walk entities, exploding INSERT blocks."""
    if depth > 10:
        return  # prevent infinite recursion from circular block references

    for entity in entity_collection:
        dxftype = entity.dxftype()

        if dxftype not in SUPPORTED_TYPES:
            continue

        try:
            if dxftype == "INSERT":
                _handle_insert(entity, doc, transform, geometry, closed_contours, depth)
            else:
                item = _extract_entity(entity, transform)
                if item:
                    geometry.append(item)
                    if item.get("closed") and len(item["points"]) >= 3:
                        closed_contours.append(item["points"])
        except Exception as exc:
            # Never crash on a single bad entity
            print(f"[DXF] Skip {dxftype}: {exc}")


def _handle_insert(entity, doc, parent_transform: Matrix44, geometry, closed_contours, depth):
    """Explode an INSERT entity into its constituent geometry."""
    block_name = entity.dxf.name
    block = doc.blocks.get(block_name)
    if block is None:
        return

    # INSERT transformation: translate, rotate, scale
    insert_mat = entity.matrix44()
    combined = parent_transform @ insert_mat

    _walk_entities(block, doc, combined, geometry, closed_contours, depth + 1)


# ═════════════════════════════════════════════════════════════════════════════
# ENTITY EXTRACTION
# ═════════════════════════════════════════════════════════════════════════════

def _extract_entity(entity, transform: Matrix44) -> dict | None:
    """Convert a DXF entity to a serialisable geometry item."""
    dxftype = entity.dxftype()

    if dxftype == "LINE":
        return _extract_line(entity, transform)
    if dxftype == "CIRCLE":
        return _extract_circle(entity, transform)
    if dxftype == "ARC":
        return _extract_arc(entity, transform)
    if dxftype == "ELLIPSE":
        return _extract_ellipse(entity, transform)
    if dxftype == "LWPOLYLINE":
        return _extract_lwpolyline(entity, transform)
    if dxftype == "POLYLINE":
        return _extract_polyline(entity, transform)
    if dxftype == "SPLINE":
        return _extract_spline(entity, transform)
    return None


# ─── LINE ────────────────────────────────────────────────────────────────────
def _extract_line(entity, transform: Matrix44) -> dict | None:
    s = _xform(entity.dxf.start, transform)
    e = _xform(entity.dxf.end, transform)
    if _dist(s, e) < TOLERANCE:
        return None
    return {
        "type": "LINE",
        "layer": entity.dxf.get("layer", "0"),
        "color": _color(entity),
        "closed": False,
        "start": list(s),
        "end": list(e),
        "points": [list(s), list(e)],
    }


# ─── CIRCLE ──────────────────────────────────────────────────────────────────
def _extract_circle(entity, transform: Matrix44) -> dict | None:
    cx, cy = _xform(entity.dxf.center, transform)
    r = entity.dxf.radius
    if r <= TOLERANCE:
        return None

    segs = max(MIN_CIRCLE_SEGMENTS, int(360 * ARC_SEGMENTS_PER_DEG))
    pts = _sample_arc(cx, cy, r, 0.0, 360.0, segs, close=True)

    return {
        "type": "CIRCLE",
        "layer": entity.dxf.get("layer", "0"),
        "color": _color(entity),
        "closed": True,
        "center": [cx, cy],
        "radius": r,
        "points": pts,
    }


# ─── ARC ─────────────────────────────────────────────────────────────────────
def _extract_arc(entity, transform: Matrix44) -> dict | None:
    cx, cy = _xform(entity.dxf.center, transform)
    r = entity.dxf.radius
    if r <= TOLERANCE:
        return None

    sa = entity.dxf.start_angle  # degrees
    ea = entity.dxf.end_angle    # degrees
    # DXF arcs are always counterclockwise
    if ea < sa:
        ea += 360.0
    span = ea - sa
    segs = max(8, int(span * ARC_SEGMENTS_PER_DEG))

    pts = _sample_arc(cx, cy, r, sa, ea, segs, close=False)

    return {
        "type": "ARC",
        "layer": entity.dxf.get("layer", "0"),
        "color": _color(entity),
        "closed": False,
        "center": [cx, cy],
        "radius": r,
        "startAngle": sa,
        "endAngle": ea,
        "points": pts,
    }


# ─── ELLIPSE ─────────────────────────────────────────────────────────────────
def _extract_ellipse(entity, transform: Matrix44) -> dict | None:
    try:
        # Use ezdxf construction tool for accurate tessellation
        ell = entity.construction_tool()
        raw_pts = list(ell.vertices(count=max(64, int(360 * ARC_SEGMENTS_PER_DEG))))
        pts = [list(_xform(Vec3(p.x, p.y, 0), transform)) for p in raw_pts]
    except Exception:
        return None

    sa = entity.dxf.start_param  # radians 0..2π
    ea = entity.dxf.end_param
    is_full = abs((ea - sa) % (2 * math.pi)) < 1e-4 or abs(ea - sa) < 1e-4

    if is_full and len(pts) > 0:
        pts.append(pts[0])  # close the loop

    return {
        "type": "ELLIPSE",
        "layer": entity.dxf.get("layer", "0"),
        "color": _color(entity),
        "closed": is_full,
        "points": pts,
    }


# ─── LWPOLYLINE ──────────────────────────────────────────────────────────────
def _extract_lwpolyline(entity, transform: Matrix44) -> dict | None:
    """
    Extract LWPOLYLINE with full bulge-arc support.
    Each vertex can carry a bulge value encoding a circular arc.
    """
    raw_verts = list(entity.lwpoints)  # (x, y, start_width, end_width, bulge)
    if len(raw_verts) < 2:
        return None

    closed = bool(entity.closed)
    pts: list[list[float]] = []

    n = len(raw_verts)
    for i in range(n):
        x, y, _sw, _ew, bulge = raw_verts[i]
        p1 = (x, y)
        pts.append(list(_xform(Vec3(x, y, 0), transform)))

        # Determine next vertex (wraps for closed polyline)
        has_next = (i < n - 1) or closed
        if not has_next:
            continue

        nx, ny = raw_verts[(i + 1) % n][:2]
        p2 = (nx, ny)

        if abs(bulge) > TOLERANCE:
            arc_pts = _bulge_to_arc_points(p1, p2, bulge, segments=48)
            for ap in arc_pts:
                pts.append(list(_xform(Vec3(ap[0], ap[1], 0), transform)))

    if closed and len(pts) >= 2:
        pts.append(pts[0])  # explicit closing vertex

    return {
        "type": "LWPOLYLINE",
        "layer": entity.dxf.get("layer", "0"),
        "color": _color(entity),
        "closed": closed,
        "points": pts,
    }


# ─── POLYLINE (2D / 3D) ──────────────────────────────────────────────────────
def _extract_polyline(entity, transform: Matrix44) -> dict | None:
    verts = list(entity.vertices)
    if len(verts) < 2:
        return None

    closed = bool(entity.is_closed)
    pts: list[list[float]] = []

    for i, v in enumerate(verts):
        p1 = (v.dxf.location.x, v.dxf.location.y)
        pts.append(list(_xform(Vec3(p1[0], p1[1], 0), transform)))

        bulge = v.dxf.get("bulge", 0.0)
        has_next = i < len(verts) - 1 or closed
        if abs(bulge) > TOLERANCE and has_next:
            nv = verts[(i + 1) % len(verts)]
            p2 = (nv.dxf.location.x, nv.dxf.location.y)
            arc_pts = _bulge_to_arc_points(p1, p2, bulge, segments=48)
            for ap in arc_pts:
                pts.append(list(_xform(Vec3(ap[0], ap[1], 0), transform)))

    if closed and len(pts) >= 2:
        pts.append(pts[0])

    return {
        "type": "POLYLINE",
        "layer": entity.dxf.get("layer", "0"),
        "color": _color(entity),
        "closed": closed,
        "points": pts,
    }


# ─── SPLINE ──────────────────────────────────────────────────────────────────
def _extract_spline(entity, transform: Matrix44) -> dict | None:
    """
    Tessellate SPLINE using ezdxf's built-in B-spline evaluator.
    Falls back to fit points if control points / knots are unavailable.
    """
    try:
        spline = entity.construction_tool()  # returns BSpline

        # Adaptive segment count based on control point count
        cp_count = len(entity.control_points)
        segs = max(SPLINE_SEGMENTS, cp_count * 20)
        raw_pts = list(spline.approximate(segments=segs))

    except Exception:
        # Fallback: use fit points if available
        fp = list(entity.fit_points)
        if len(fp) < 2:
            return None
        raw_pts = fp

    pts = [list(_xform(Vec3(p.x, p.y, 0), transform)) for p in raw_pts]
    closed = entity.closed or (
        len(pts) >= 2 and _dist(pts[0], pts[-1]) < TOLERANCE
    )
    if closed and len(pts) >= 2:
        pts.append(pts[0])

    return {
        "type": "SPLINE",
        "layer": entity.dxf.get("layer", "0"),
        "color": _color(entity),
        "closed": closed,
        "points": pts,
    }


# ═════════════════════════════════════════════════════════════════════════════
# BULGE → ARC CONVERSION
# ═════════════════════════════════════════════════════════════════════════════

def _bulge_to_arc_points(
    p1: tuple, p2: tuple, bulge: float, segments: int = 48
) -> list[tuple]:
    """
    Convert a DXF polyline bulge segment to a list of arc sample points.

    DXF bulge definition:
      bulge = tan(θ / 4)  where θ = included arc angle
      positive bulge = counterclockwise arc
      negative bulge = clockwise arc
    """
    x1, y1 = p1
    x2, y2 = p2
    dx, dy = x2 - x1, y2 - y1
    d = math.hypot(dx, dy)
    if d < 1e-12:
        return []

    # Included angle
    theta = 4.0 * math.atan(abs(bulge))
    # Radius
    r = d / (2.0 * math.sin(theta / 2.0))
    # Distance from chord midpoint to arc center
    d_to_center = r * math.cos(theta / 2.0)

    # Perpendicular unit vector (rotated 90° CCW from chord)
    perp_x, perp_y = -dy / d, dx / d
    mid_x, mid_y = (x1 + x2) / 2.0, (y1 + y2) / 2.0

    sign = 1.0 if bulge > 0 else -1.0
    cx = mid_x + perp_x * d_to_center * sign
    cy = mid_y + perp_y * d_to_center * sign

    # Start and end angles
    a1 = math.atan2(y1 - cy, x1 - cx)
    a2 = math.atan2(y2 - cy, x2 - cx)

    ccw = bulge > 0
    if ccw and a2 < a1:
        a2 += 2 * math.pi
    elif not ccw and a2 > a1:
        a2 -= 2 * math.pi

    pts = []
    for i in range(1, segments + 1):
        t = i / segments
        a = a1 + (a2 - a1) * t
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))

    return pts


# ═════════════════════════════════════════════════════════════════════════════
# LINE-SEGMENT CHAINING → closed loops
# ═════════════════════════════════════════════════════════════════════════════

def _chain_segments_to_loops(geometry: list[dict]) -> list[list[tuple]]:
    """
    Build a graph of all open line-segment endpoints and find closed loops.
    Each loop is returned as an ordered list of (x, y) tuples.

    This handles drawings where the cutting profile is defined as many
    individual LINE / open-ARC entities that together form closed contours.
    """
    SNAP = 0.5  # endpoint snap tolerance (units)

    # Collect all segment endpoint pairs from open geometries
    segments: list[tuple[tuple, tuple]] = []
    for item in geometry:
        if item.get("closed"):
            continue  # already a closed contour
        pts = item.get("points", [])
        if len(pts) < 2:
            continue
        p0 = (pts[0][0], pts[0][1])
        p1 = (pts[-1][0], pts[-1][1])
        if _dist(list(p0), list(p1)) < SNAP:
            continue  # already self-closing, tiny segment
        segments.append((p0, p1))

    if not segments:
        return []

    # Build adjacency map: snap endpoints together
    def snap_key(p: tuple) -> tuple:
        return (round(p[0] / SNAP) * SNAP, round(p[1] / SNAP) * SNAP)

    # adjacency: node → list of (neighbour_node, segment_index, direction)
    from collections import defaultdict
    adj: dict[tuple, list] = defaultdict(list)

    for idx, (p0, p1) in enumerate(segments):
        k0, k1 = snap_key(p0), snap_key(p1)
        adj[k0].append((k1, idx, "fwd"))
        adj[k1].append((k0, idx, "rev"))

    # DFS to find closed loops
    loops: list[list[tuple]] = []
    used: set[int] = set()

    def dfs_loop(start: tuple, current: tuple, path: list, path_pts: list[list]):
        for (nxt, seg_idx, _direction) in adj[current]:
            if seg_idx in used:
                continue
            # Check if we've closed a loop
            if nxt == start and len(path) > 2:
                loops.append([_snap_round(p) for p in path_pts])
                used.update(path)
                return True
            if nxt in [snap_key(p) for p in path_pts]:
                continue  # avoid revisiting
            used.add(seg_idx)
            path.append(seg_idx)
            # Add points from this segment
            seg_p0, seg_p1 = segments[seg_idx]
            path_pts.append(seg_p1)  # direction matters but approximate
            if dfs_loop(start, nxt, path, path_pts):
                return True
            path.pop()
            path_pts.pop()
            used.discard(seg_idx)
        return False

    for node in list(adj.keys()):
        dfs_loop(node, node, [], [adj[node][0][0]])

    return loops


def _snap_round(p) -> tuple:
    if isinstance(p, tuple):
        return (round(p[0], 4), round(p[1], 4))
    return (round(p[0], 4), round(p[1], 4))


# ═════════════════════════════════════════════════════════════════════════════
# HELPERS
# ═════════════════════════════════════════════════════════════════════════════

def _xform(point: Vec3, transform: Matrix44) -> tuple[float, float]:
    """Apply a 4×4 transform to a 3D point and return (x, y)."""
    if transform == Matrix44():  # identity — skip computation
        return (point.x, point.y)
    transformed = transform.transform(point)
    return (transformed.x, transformed.y)


def _dist(a: list | tuple, b: list | tuple) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _color(entity) -> int:
    """Return ACI color index (fallback 7 = white)."""
    return entity.dxf.get("color", 7)


def _sample_arc(
    cx: float, cy: float, r: float,
    start_deg: float, end_deg: float,
    segments: int,
    close: bool,
) -> list[list[float]]:
    """Sample a circular arc into (x, y) points."""
    sa = math.radians(start_deg)
    ea = math.radians(end_deg)
    pts = []
    for i in range(segments + 1):
        t = i / segments
        a = sa + (ea - sa) * t
        pts.append([cx + r * math.cos(a), cy + r * math.sin(a)])
    if close and pts:
        pts.append(pts[0])
    return pts


def _get_units(doc) -> str:
    try:
        code = doc.header.get("$INSUNITS", 0)
        return UNIT_MAP.get(code, "Unitless")
    except Exception:
        return "Unitless"


def _get_layers(doc) -> list[str]:
    try:
        return [layer.dxf.name for layer in doc.layers]
    except Exception:
        return []


def _bounding_box(geometry: list[dict]) -> dict:
    """Compute axis-aligned bounding box from all geometry points."""
    min_x = min_y = float("inf")
    max_x = max_y = float("-inf")

    for item in geometry:
        for pt in item.get("points", []):
            if pt[0] < min_x:
                min_x = pt[0]
            if pt[1] < min_y:
                min_y = pt[1]
            if pt[0] > max_x:
                max_x = pt[0]
            if pt[1] > max_y:
                max_y = pt[1]

    if not math.isfinite(min_x):
        return {"minX": 0, "minY": 0, "maxX": 0, "maxY": 0, "width": 0, "height": 0}

    return {
        "minX": round(min_x, 4),
        "minY": round(min_y, 4),
        "maxX": round(max_x, 4),
        "maxY": round(max_y, 4),
        "width": round(max_x - min_x, 4),
        "height": round(max_y - min_y, 4),
    }
