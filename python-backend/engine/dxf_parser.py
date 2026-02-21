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

# --- Constants ----------------------------------------------------------------
FLATTEN_DISTANCE = 0.1          # max chord deviation for curve tessellation (mm)
ARC_SEGMENTS_PER_DEG = 0.5      # segments per degree for arcs
MIN_CIRCLE_SEGMENTS = 64
SPLINE_SEGMENTS = 100
TOLERANCE = 1e-4                # coordinate snap tolerance

SUPPORTED_TYPES = frozenset({
    "LINE", "ARC", "CIRCLE", "ELLIPSE",
    "LWPOLYLINE", "POLYLINE", "SPLINE", "INSERT",
})

# --- Unit name map ------------------------------------------------------------
UNIT_MAP = {
    0: "Unitless", 1: "Inches", 2: "Feet", 3: "Miles",
    4: "Millimeters", 5: "Centimeters", 6: "Meters", 7: "Kilometers",
    8: "Microinches", 9: "Mils", 10: "Yards", 14: "Decimeters",
}


# =============================================================================
# PUBLIC API
# =============================================================================

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


# =============================================================================
# ENTITY WALKER
# =============================================================================

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


# =============================================================================
# ENTITY EXTRACTION
# =============================================================================

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


# --- LINE --------------------------------------------------------------------
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


# --- CIRCLE ------------------------------------------------------------------
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


# --- ARC ---------------------------------------------------------------------
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


# --- ELLIPSE -----------------------------------------------------------------
def _extract_ellipse(entity, transform: Matrix44) -> dict | None:
    try:
        # Use ezdxf construction tool for accurate tessellation
        ell = entity.construction_tool()
        raw_pts = list(ell.vertices(count=max(64, int(360 * ARC_SEGMENTS_PER_DEG))))
        pts = [list(_xform(Vec3(p.x, p.y, 0), transform)) for p in raw_pts]
    except Exception:
        return None

    sa = entity.dxf.start_param  # radians 0..2pi
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


# --- LWPOLYLINE --------------------------------------------------------------
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


# --- POLYLINE (2D / 3D) ------------------------------------------------------
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


# --- SPLINE ------------------------------------------------------------------
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


# =============================================================================
# BULGE -> ARC CONVERSION
# =============================================================================

def _bulge_to_arc_points(
    p1: tuple, p2: tuple, bulge: float, segments: int = 48
) -> list[tuple]:
    """
    Convert a DXF polyline bulge segment to a list of arc sample points.

    DXF bulge definition:
      bulge = tan(theta / 4)  where theta = included arc angle
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

    # Perpendicular unit vector (rotated 90deg CCW from chord)
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


# =============================================================================
# LINE-SEGMENT CHAINING -> closed loops
# =============================================================================

def _chain_segments_to_loops(geometry: list[dict]) -> list[list[tuple]]:
    """
    Chain disconnected open line / arc segments into closed loops.

    Handles drawings where the cutting profile is composed of many individual
    LINE or open-ARC entities that together form closed contours (e.g. a
    rectangular outline drawn as 4 separate LINE entities).

    Algorithm
    ---------
    1.  Collect every open segment as (start_key, end_key, interpolated_pts).
    2.  Build an adjacency graph keyed on snapped endpoints.
    3.  For each unvisited node, greedily follow the single outgoing unused
        edge until we either return to the start (-> closed loop) or get stuck.
    4.  Accept a loop only if it has >= 3 segments and >= 3 unique points.

    The greedy walk works well for typical sheet-metal DXF profiles where
    each endpoint connects to exactly one other segment (degree-2 graph).
    For branching topologies the first valid branch is always taken.
    """
    from collections import defaultdict

    SNAP = 0.5  # endpoint snap tolerance (drawing units)

    def snap_key(px: float, py: float) -> tuple:
        return (round(px / SNAP) * SNAP, round(py / SNAP) * SNAP)

    # -- Collect open segments -------------------------------------------------
    segs: list[dict] = []          # {k0, k1, pts_fwd}
    for item in geometry:
        if item.get("closed"):
            continue
        raw = item.get("points", [])
        if len(raw) < 2:
            continue
        p0 = raw[0]
        p1 = raw[-1]
        k0 = snap_key(p0[0], p0[1])
        k1 = snap_key(p1[0], p1[1])
        if k0 == k1:
            continue  # self-closing -> treat as already closed
        pts = [(float(pt[0]), float(pt[1])) for pt in raw]
        segs.append({"k0": k0, "k1": k1, "pts": pts})

    if not segs:
        return []

    # -- Build adjacency -------------------------------------------------------
    # adj[node] = list of (neighbour_node, seg_idx, forward:bool)
    adj: dict[tuple, list] = defaultdict(list)
    for idx, seg in enumerate(segs):
        adj[seg["k0"]].append((seg["k1"], idx, True))
        adj[seg["k1"]].append((seg["k0"], idx, False))

    # -- Greedy chain-following ------------------------------------------------
    loops:     list[list[tuple]] = []
    used_segs: set[int]          = set()

    for start_node in list(adj.keys()):
        # Skip if all edges from this node are already consumed
        if all(sidx in used_segs for (_, sidx, _) in adj[start_node]):
            continue

        current     = start_node
        local_used: list[int] = []
        chain_pts:  list[tuple] = []
        found_loop  = False

        while True:
            # Pick the first unused edge from `current`
            step = None
            for (nxt, sidx, fwd) in adj[current]:
                if sidx not in used_segs:
                    step = (nxt, sidx, fwd)
                    break
            if step is None:
                break  # dead end - no more unused edges

            nxt, sidx, fwd = step
            used_segs.add(sidx)
            local_used.append(sidx)

            seg = segs[sidx]
            pts = seg["pts"] if fwd else list(reversed(seg["pts"]))

            if not chain_pts:
                # First segment: include all points
                chain_pts.extend(pts)
            else:
                # Subsequent: skip the first point (already in chain_pts)
                chain_pts.extend(pts[1:])

            if nxt == start_node:
                # Closed loop found
                if len(local_used) >= 3 and len(chain_pts) >= 3:
                    loops.append([(p[0], p[1]) for p in chain_pts])
                found_loop = True
                break

            current = nxt

        if not found_loop:
            # Walk did not close - release edges so other starts can try
            for sidx in local_used:
                used_segs.discard(sidx)

    return loops


# =============================================================================
# HELPERS
# =============================================================================

def _xform(point: Vec3, transform: Matrix44) -> tuple[float, float]:
    """Apply a 4x4 transform to a 3D point and return (x, y)."""
    if transform == Matrix44():  # identity - skip computation
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
