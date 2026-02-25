"""
nesting_engine.py  —  Bounding-Box Shelf Nesting
=================================================

Algorithm
---------

1.  Expand every part's quantity into individual pieces (flat list).
2.  Pack pieces sequentially into sheets row-by-row:

    cursor_x = 0,  cursor_y = 0,  current_row_height = 0
    sheet_index = 0,  current_sheet = { sheet_index, placements: [] }

    FOR each piece:

        part_width  = max_x - min_x
        part_height = max_y - min_y

        IF cursor_x + part_width > sheet_width:   # row full → next row
            cursor_x = 0
            cursor_y += current_row_height
            current_row_height = 0

        IF cursor_y + part_height > sheet_height: # sheet full → new sheet
            append current_sheet
            sheet_index += 1
            current_sheet = new sheet
            cursor_x = cursor_y = current_row_height = 0

        Place piece at (cursor_x, cursor_y)
        cursor_x += part_width
        current_row_height = max(current_row_height, part_height)

    Append final current_sheet

3.  Compute utilisation.

Public API (unchanged — main.py requires no modifications)
----------------------------------------------------------
    nest_parts(parts, sheet, config) -> dict
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


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
    step_x:        float       = 1.0
    step_y:        float       = 1.0
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


# ================================================================
# PUBLIC API
# ================================================================

def nest_parts(
    parts:  list[PolygonPart],
    sheet:  StockSheet,
    config: Optional[NestingConfig] = None,
) -> dict:
    """
    Bounding-box shelf nesting.

    Expands each part's quantity into individual pieces, then packs
    all pieces row-by-row into sheets.  A new sheet is started only
    when the current sheet has no more vertical space.

    Returns
    -------
    {
        "sheets":              [ { "sheet_index", "width", "height",
                                   "placements": [...] } ],
        "sheets_required":     int,
        "utilization_percent": float,
        "waste_percent":       float,
        "oversized_parts":     [str, ...],
        "total_sheets":        int,   # alias for main.py logging
        "utilization":         float, # alias for main.py logging
        "capacity_per_sheet":  int,   # 0 — not meaningful for shelf packing
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
            "oversized_parts":     [],
            "capacity_per_sheet":  0,
        }

    # ── Step 1: expand quantity into individual pieces ─────────────────────
    pieces:    list[dict] = []
    oversized: list[str]  = []

    for part in parts:
        if not part.outer or len(part.outer) < 2:
            continue

        min_x, min_y, max_x, max_y = _part_bbox(part.outer)
        part_width  = max_x - min_x
        part_height = max_y - min_y

        if part_width <= 0 or part_height <= 0:
            continue  # degenerate shape — skip

        if part_width > sheet_width or part_height > sheet_height:
            oversized.append(part.id)
            continue

        fname = part.file_name if part.file_name else part.id
        qty   = max(int(part.quantity), 1)

        for _ in range(qty):
            pieces.append({
                "file_name":   fname,
                "part_id":     part.id,
                "part_width":  part_width,
                "part_height": part_height,
            })

    # ── Step 2: sort by height descending (tallest parts first)
    #   Tallest parts placed first → rows share the same height → no wasted
    #   headroom above shorter parts → better sheet utilization.
    pieces.sort(key=lambda p: p["part_height"], reverse=True)

    # ── Step 3: pack sorted pieces into sheets ──────────────────────────────
    sheets_done:   list[dict] = []
    sheet_index:   int        = 0
    current_sheet: dict       = {"sheet_index": 0, "placements": []}

    cursor_x:          float = 0.0
    cursor_y:          float = 0.0
    current_row_height: float = 0.0

    for piece in pieces:
        pw = piece["part_width"]
        ph = piece["part_height"]

        # Width exceeded → move to next row
        if cursor_x + pw > sheet_width:
            cursor_x           = 0.0
            cursor_y          += current_row_height
            current_row_height = 0.0

        # Height exceeded → new sheet
        if cursor_y + ph > sheet_height:
            sheets_done.append(current_sheet)
            sheet_index       += 1
            current_sheet      = {"sheet_index": sheet_index, "placements": []}
            cursor_x           = 0.0
            cursor_y           = 0.0
            current_row_height = 0.0

        current_sheet["placements"].append({
            "file_name": piece["file_name"],
            "part_id":   piece["part_id"],
            "x":         cursor_x,
            "y":         cursor_y,
            "rotation":  0,
        })

        cursor_x           += pw
        current_row_height  = max(current_row_height, ph)

    # Append the last (possibly partial) sheet
    if current_sheet["placements"]:
        sheets_done.append(current_sheet)

    # ── Step 3: attach sheet dimensions ────────────────────────────────────
    sheets_list = [
        {
            "sheet_index": s["sheet_index"],
            "width":       sheet_width,
            "height":      sheet_height,
            "placements":  s["placements"],
        }
        for s in sheets_done
    ]

    # ── Step 4: utilisation ────────────────────────────────────────────────
    total_part_area  = sum(p["part_width"] * p["part_height"] for p in pieces)
    sheets_required  = len(sheets_list)
    total_sheet_area = sheets_required * sheet_width * sheet_height
    utilization_percent = (
        round(total_part_area / total_sheet_area * 100, 2)
        if total_sheet_area > 0 else 0.0
    )
    waste_percent = round(100.0 - utilization_percent, 2)

    return {
        "sheets":              sheets_list,
        "sheets_required":     sheets_required,
        "utilization_percent": utilization_percent,
        "waste_percent":       waste_percent,
        "oversized_parts":     oversized,
        # Backward-compat aliases for main.py logging
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
    """Stub — no collision detection in bounding-box nesting."""
    return False


def polygons_intersect(
    poly1:     Polygon,
    poly2:     Polygon,
    clearance: float = 0.0,
) -> bool:
    """Stub — no collision detection in bounding-box nesting."""
    return False
