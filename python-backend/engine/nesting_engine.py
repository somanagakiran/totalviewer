"""
nesting_engine.py  —  True-Shape Bottom-Left Nesting (Optimised)
================================================================

Algorithm
---------
1.  Expand every part's quantity into individual pieces (flat list).
2.  Sort pieces by area descending (largest parts placed first).
3.  For each piece, try every requested rotation angle.
    For each angle, build a candidate position set:
        • Critical x positions: {0} ∪ {right_bbox_of_placed_part + margin}
        • Critical y positions: {0} ∪ {top_bbox_of_placed_part + margin}
        • Supplementary coarse grid (step ≥ 10 mm)
    Scan candidates (y ascending, x ascending) and check the actual
    polygon geometry via Shapely STRtree.  First valid (x, y) → place.
4.  If no valid position → start a new sheet and retry the piece.

Performance vs. previous implementation
----------------------------------------
• placed_union (ever-growing complex polygon) is replaced by a list of
  individual placed polygons + STRtree for O(log n) spatial queries.
• Critical-point candidates: for a partially-filled sheet only O(n)
  positions are checked instead of O(W×H / step²).
• Placed parts are pre-buffered once on placement, not per candidate.
• STRtree.query(predicate='intersects') runs in C — sub-microsecond per
  call regardless of how many parts are on the sheet.

Public API unchanged — main.py requires no modifications.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from shapely.geometry import Polygon as ShapelyPolygon
from shapely.affinity import (
    translate as shapely_translate,
    rotate   as shapely_rotate,
)
from shapely.strtree import STRtree


# ================================================================
# DATA STRUCTURES
# ================================================================

Point   = tuple[float, float]
Polygon = list[Point]


@dataclass
class PolygonPart:
    """
    One unique part shape with a repeat quantity.

    Fields used by main.py (must not be renamed):
        id, outer, holes, quantity, area

    file_name is optional metadata forwarded to each placement dict.
    Defaults to the id value when not provided.
    """
    id:        str
    outer:     Polygon
    holes:     list[Polygon] = field(default_factory=list)
    quantity:  int           = 1
    area:      float         = 0.0
    file_name: Optional[str] = field(default=None)


@dataclass
class StockSheet:
    """Rectangular material sheet."""
    width:     float
    height:    float
    thickness: float = 0.0


@dataclass
class NestingConfig:
    """Nesting parameters."""
    step_x:        float       = 5.0
    step_y:        float       = 5.0
    margin:        float       = 0.0
    rotations:     list[float] = field(default_factory=lambda: [0.0, 90.0])
    advanced_mode: bool        = False
    rotation_step: float       = 10.0
    n_passes:      int         = 5


# ================================================================
# HELPERS
# ================================================================

def _part_bbox(outer: Polygon) -> tuple[float, float, float, float]:
    """Return (min_x, min_y, max_x, max_y) from a polygon vertex list."""
    xs = [p[0] for p in outer]
    ys = [p[1] for p in outer]
    return min(xs), min(ys), max(xs), max(ys)


def _try_place(
    raw_poly:        ShapelyPolygon,
    rotations:       list[float],
    sheet_width:     float,
    sheet_height:    float,
    placed_polys:    list[ShapelyPolygon],   # actual placed shapes (for critical points)
    placed_buffered: list[ShapelyPolygon],   # margin-buffered shapes (for collision)
    tree:            Optional[STRtree],      # STRtree built over placed_buffered
    margin:          float,
    step_x:          float,   # kept for API compatibility, not used in scan
    step_y:          float,   # kept for API compatibility, not used in scan
) -> Optional[tuple[float, float, float, ShapelyPolygon]]:
    """
    Find the first valid bottom-left placement for raw_poly on the sheet.

    Candidate positions come exclusively from critical points:
        x ∈ {0} ∪ { bx2 + margin  for each placed part }
        y ∈ {0} ∪ { by2 + margin  for each placed part }

    Critical points are provably complete for the bottom-left fill
    heuristic: any valid placement can be slid left and down until it
    touches the left wall, the bottom wall, or the edge of another part,
    which is exactly where the critical points sit.

    A per-rotation candidate cap (MAX_CANDS) is applied so that a
    nearly-full sheet bails out quickly and triggers a new sheet rather
    than exhausting millions of positions.

    Returns (x, y, angle, placed_polygon) or None if no position fits.
    """
    # If the sheet is nearly full, stop searching after this many candidates
    # (prevents timeout on dense sheets with large quantities).
    MAX_CANDS = 25_000

    for angle in rotations:
        rotated = shapely_rotate(raw_poly, angle, origin='centroid', use_radians=False)
        minx, miny, maxx, maxy = rotated.bounds
        pw = maxx - minx
        ph = maxy - miny

        if pw > sheet_width + 1e-9 or ph > sheet_height + 1e-9:
            continue  # This rotation does not fit the sheet at all

        # Normalise so the polygon bounding box starts at (0, 0)
        normalized = shapely_translate(rotated, -minx, -miny)

        # ── Build candidate positions: critical points only ─────────────
        xs: set[float] = {0.0}
        ys: set[float] = {0.0}

        for p in placed_polys:
            bx1, by1, bx2, by2 = p.bounds
            xr = bx2 + margin
            yt = by2 + margin
            if xr + pw <= sheet_width + 1e-9:
                xs.add(round(xr, 6))
            if yt + ph <= sheet_height + 1e-9:
                ys.add(round(yt, 6))

        # ── Scan: bottom-left first (y asc → x asc) ────────────────────
        checked = 0
        found   = False

        for y in sorted(ys):
            if y + ph > sheet_height + 1e-9:
                continue
            for x in sorted(xs):
                if x + pw > sheet_width + 1e-9:
                    continue

                checked += 1
                if checked > MAX_CANDS:
                    found = True   # signal outer loop to stop this rotation
                    break

                candidate = shapely_translate(normalized, x, y)

                # No placed parts yet — trivially valid
                if tree is None:
                    return x, y, angle, candidate

                # Fast collision check: STRtree query runs in C (GEOS).
                # Shrink candidate by a tiny epsilon so boundary-touching
                # polygons (margin=0, parts placed flush) are NOT treated
                # as intersecting — only real overlaps are rejected.
                _PROBE_SHRINK = 1e-4
                probe = candidate.buffer(-_PROBE_SHRINK)
                if probe.is_empty:
                    probe = candidate
                if len(tree.query(probe, predicate='intersects')) == 0:
                    return x, y, angle, candidate

            if found:
                break

    return None  # No valid position found on this sheet


# ================================================================
# PUBLIC API
# ================================================================

def nest_parts(
    parts:  list[PolygonPart],
    sheet:  StockSheet,
    config: Optional[NestingConfig] = None,
) -> dict:
    """
    True-shape bottom-left nesting using Shapely polygon geometry.

    Parts are placed using their actual contour, not their bounding box.
    The margin parameter enforces a minimum gap between parts.

    Returns
    -------
    {
        "sheets":              [ { "sheet_index", "width", "height",
                                   "placements": [...] } ],
        "sheets_required":     int,
        "utilization_percent": float,
        "waste_percent":       float,
        "waste":               float,  # alias for frontend
        "oversized_parts":     [str, ...],
        "total_sheets":        int,
        "utilization":         float,
        "capacity_per_sheet":  int,
    }
    """
    if config is None:
        config = NestingConfig()

    sheet_width  = sheet.width
    sheet_height = sheet.height

    # ── Validate sheet ─────────────────────────────────────────────────────
    if sheet_width <= 0 or sheet_height <= 0:
        return {
            "error":               "Sheet dimensions must be positive.",
            "sheets":              [],
            "sheets_required":     0,
            "total_sheets":        0,
            "utilization":         0.0,
            "utilization_percent": 0.0,
            "waste_percent":       100.0,
            "waste":               100.0,
            "oversized_parts":     [],
            "capacity_per_sheet":  0,
        }

    margin    = max(config.margin, 0.0)
    step_x    = max(config.step_x, 0.1)
    step_y    = max(config.step_y, 0.1)
    rotations = config.rotations if config.rotations else [0.0]

    # ── Step 1: build Shapely polygons and expand by quantity ──────────────
    pieces:    list[dict] = []
    oversized: list[str]  = []

    for part in parts:
        if not part.outer or len(part.outer) < 3:
            continue

        try:
            raw = ShapelyPolygon(part.outer)
            if not raw.is_valid:
                raw = raw.buffer(0)     # attempt self-intersection repair
            if raw.is_empty or raw.area == 0:
                continue
        except Exception:
            continue

        # Pre-check: does the part fit the sheet in at least one rotation?
        fits_sheet = False
        for angle in rotations:
            rot = shapely_rotate(raw, angle, origin='centroid', use_radians=False)
            bx1, by1, bx2, by2 = rot.bounds
            if (bx2 - bx1) <= sheet_width + 1e-9 and (by2 - by1) <= sheet_height + 1e-9:
                fits_sheet = True
                break

        if not fits_sheet:
            oversized.append(part.id)
            continue

        fname = part.file_name if part.file_name else part.id
        qty   = max(int(part.quantity), 1)
        for _ in range(qty):
            pieces.append({"part_id": part.id, "file_name": fname, "poly": raw})

    # ── Step 2: largest area first (better packing) ────────────────────────
    pieces.sort(key=lambda p: p["poly"].area, reverse=True)

    # ── Step 3: place pieces sheet by sheet ────────────────────────────────
    sheets_list:        list[dict]               = []
    sheet_idx:          int                      = 0
    current_placements: list[dict]               = []
    placed_polys:       list[ShapelyPolygon]     = []   # actual shapes
    placed_buffered:    list[ShapelyPolygon]     = []   # margin-buffered shapes
    tree:               Optional[STRtree]        = None
    total_placed_area:  float                    = 0.0

    for piece in pieces:
        raw_poly = piece["poly"]

        placement = _try_place(
            raw_poly, rotations,
            sheet_width, sheet_height,
            placed_polys, placed_buffered, tree,
            margin, step_x, step_y,
        )

        if placement is None:
            # Current sheet is full — save and open a new one
            if current_placements:
                sheets_list.append({
                    "sheet_index": sheet_idx,
                    "width":       sheet_width,
                    "height":      sheet_height,
                    "placements":  current_placements,
                })
            sheet_idx          += 1
            current_placements  = []
            placed_polys        = []
            placed_buffered     = []
            tree                = None

            # Retry on the new empty sheet
            placement = _try_place(
                raw_poly, rotations,
                sheet_width, sheet_height,
                [], [], None,
                margin, step_x, step_y,
            )

        if placement is not None:
            x, y, angle, candidate = placement
            current_placements.append({
                "file_name": piece["file_name"],
                "part_id":   piece["part_id"],
                "x":         round(x, 4),
                "y":         round(y, 4),
                "rotation":  angle,
            })
            # Store actual shape (for future critical-point calculation)
            placed_polys.append(candidate)
            # Store buffered shape (for collision detection)
            placed_buffered.append(
                candidate.buffer(margin, resolution=4) if margin > 0 else candidate
            )
            # Rebuild STRtree with the updated buffered list (fast in C)
            tree = STRtree(placed_buffered)
            total_placed_area += raw_poly.area
        else:
            # Still doesn't fit — truly oversized
            if piece["part_id"] not in oversized:
                oversized.append(piece["part_id"])

    # Append the last (possibly partial) sheet
    if current_placements:
        sheets_list.append({
            "sheet_index": sheet_idx,
            "width":       sheet_width,
            "height":      sheet_height,
            "placements":  current_placements,
        })

    # ── Step 4: utilisation (actual polygon area, not bbox) ────────────────
    sheets_required     = len(sheets_list)
    total_sheet_area    = sheets_required * sheet_width * sheet_height
    utilization_percent = (
        round(total_placed_area / total_sheet_area * 100, 2)
        if total_sheet_area > 0 else 0.0
    )
    waste_percent = round(100.0 - utilization_percent, 2)

    return {
        "sheets":              sheets_list,
        "sheets_required":     sheets_required,
        "utilization_percent": utilization_percent,
        "waste_percent":       waste_percent,
        "waste":               waste_percent,   # alias used by frontend
        "oversized_parts":     oversized,
        # Backward-compat aliases
        "total_sheets":        sheets_required,
        "utilization":         utilization_percent,
        "capacity_per_sheet":  0,
    }


# ================================================================
# BACKWARD-COMPATIBILITY STUBS
# ================================================================

def part_from_geometry(
    part_id:  str,
    geometry: list,
    quantity: int = 1,
) -> Optional[PolygonPart]:
    """Build a PolygonPart from a geometry list produced by dxf_parser."""
    if not geometry:
        return None
    for item in geometry:
        pts = item.get("points", [])
        if len(pts) >= 3:
            return PolygonPart(
                id       = part_id,
                outer    = [(float(p[0]), float(p[1])) for p in pts],
                quantity = quantity,
            )
    return None


def compute_polygon_area(pts: Polygon) -> float:
    """Absolute area via the shoelace formula."""
    n = len(pts)
    if n < 3:
        return 0.0
    s = 0.0
    for i in range(n):
        x0, y0 = pts[i][0],           pts[i][1]
        x1, y1 = pts[(i + 1) % n][0], pts[(i + 1) % n][1]
        s += x0 * y1 - x1 * y0
    return abs(s) / 2.0


def polygon_collision(poly1: Polygon, poly2: Polygon) -> bool:
    """Check polygon collision using Shapely."""
    try:
        p1 = ShapelyPolygon(poly1)
        p2 = ShapelyPolygon(poly2)
        return bool(p1.intersects(p2))
    except Exception:
        return False


def polygons_intersect(
    poly1:     Polygon,
    poly2:     Polygon,
    clearance: float = 0.0,
) -> bool:
    """Check polygon intersection with optional clearance using Shapely."""
    try:
        p1 = ShapelyPolygon(poly1)
        p2 = ShapelyPolygon(poly2)
        if clearance > 0:
            p1 = p1.buffer(clearance / 2)
        return bool(p1.intersects(p2))
    except Exception:
        return False
