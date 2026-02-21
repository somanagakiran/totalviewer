"""
Geometry Analyzer v3  -  Industrial DXF Hole Detection
=======================================================
Uses Shapely 2.x for all polygon operations.

Two-track polygon reconstruction
----------------------------------
Track A - Closed contours (circles, closed polylines, ellipses):
  Entities already flagged as closed by the DXF parser are converted
  directly to Shapely Polygons via _build_polygons().

Track B - Open-edge polygonize (lines, arcs, open segments):
  All open edge segments (LINE, ARC, open LWPOLYLINE ...) are converted to
  Shapely LineString objects, nodded together with unary_union(), then fed
  to shapely.ops.polygonize() which reconstructs any closed rings formed
  by connected edges.  This handles drawings where the cutting profile is
  composed of many individual LINE/ARC entities.

Both tracks feed into the same outer-boundary + hole-detection logic.

Hole detection
--------------
1. Merge Track-A and Track-B polygons; sort by area (largest first).
2. Identify drawing frames conservatively (isoperimetric ratio L^2/A > 50,
   covers >= 97 % of bbox, hugs all four bbox edges).
3. Outer boundary = largest non-frame polygon.
4. Holes = polygons whose centroid lies strictly inside the outer boundary
           AND whose overlap with the outer boundary is >= 80 % of their area.
5. Per-hole metadata: circle (diameter), slot (width/length), rectangle, polygon.
"""

import math
from typing import Optional

try:
    from shapely.geometry import Polygon, MultiPolygon, LineString, Point
    from shapely.validation import make_valid
    from shapely.ops import polygonize, unary_union
    SHAPELY_OK = True
except ImportError:
    SHAPELY_OK = False
    print("[WARNING] Shapely not installed - hole/perimeter analysis disabled.")

# -- Tunables ------------------------------------------------------------------
MIN_AREA            = 0.01   # ignore polygons smaller than this (units^2)
FRAME_MIN_COVERAGE  = 0.97   # frame must cover >= 97 % of the bbox area
FRAME_EDGE_REL_TOL  = 0.02   # frame edges within 2 % of max(W,H) of bbox edges
ISOPERIMETRIC_RATIO = 50.0   # L^2/A > 50 -> polygon is "hollow" (drawing frame)
DEDUP_DISTANCE      = 1.0    # centroids closer than this are considered duplicates
SNAP_PRECISION      = 1e-3   # coordinate grid for polygonize endpoint snapping
MAX_POLYGONIZE_SEGS = 300    # skip Track B polygonize above this - prevents hang


# ===============================================================================
# PUBLIC API
# ===============================================================================

def analyze_geometry(
    closed_contours: list,
    bounding_box:    dict,
    raw_entities:    list | None = None,
) -> dict:
    """
    Detect outer boundary, holes, and perimeter from closed contours.

    Parameters
    ----------
    closed_contours : list of point loops  [[x, y], ...]  or  [(x, y), ...]
    bounding_box    : {minX, minY, maxX, maxY, width, height}
    raw_entities    : optional list of raw entity dicts from the parser
                      (currently reserved for future per-entity metadata)

    Returns
    -------
    {
        "holes"               : int,
        "perimeter"           : float,
        "outer_boundary_area" : float,
        "hole_details"        : [{"type": ..., "area": ..., ...}, ...]
    }
    """
    if not SHAPELY_OK:
        return _fallback_result()

    # -- 0. Pipeline-entry diagnostics ----------------------------------------
    print(f"[ANALYZER] -- Pipeline start --------------------------------------")
    print(f"[ANALYZER] closed_contours received : {len(closed_contours)}")
    if raw_entities:
        from collections import Counter
        type_counts = Counter(e.get("type", "?") for e in raw_entities)
        print(f"[ANALYZER] raw_entities total       : {len(raw_entities)}")
        for etype, cnt in sorted(type_counts.items()):
            print(f"[ANALYZER]   {etype:<12}: {cnt}")
    else:
        print(f"[ANALYZER] raw_entities             : None (circles will NOT be detected)")

    # -- 1. Build candidate polygons - POLYGON TRACK ---------------------------

    # Track A: already-closed contours (closed LWPOLYLINE, closed SPLINE, ...)
    #          Note: CIRCLE tessellations come in here too, but we bypass them
    #          in favour of the analytical Track C below for better accuracy.
    polygons = _build_polygons(closed_contours)
    print(f"[ANALYZER] Track A polygons (closed contours): {len(polygons)}")

    # Track B: polygonize open edge segments (LINE, ARC, open segments)
    if raw_entities:
        poly_b = _polygonize_open_edges(raw_entities)
        if poly_b:
            print(f"[ANALYZER] Track B polygons (polygonize)     : {len(poly_b)}")
            polygons.extend(poly_b)
        else:
            print(f"[ANALYZER] Track B polygons (polygonize)     : 0")

    # -- 2. Build candidate polygons - CIRCLE TRACK ---------------------------
    #
    #   polygonize() never reconstructs a CIRCLE because a circle has no open
    #   endpoints - it is a single closed entity, not a chain of edges.
    #   We therefore detect circles directly from the raw entity list using
    #   Point(cx, cy).buffer(r), which creates a proper analytical circle
    #   polygon that works reliably with Shapely's containment checks.
    #
    circle_polys: list = []
    if raw_entities:
        circle_polys = _extract_circle_polygons(raw_entities)
        print(f"[ANALYZER] Track C polygons (circles)        : {len(circle_polys)}")
    else:
        print(f"[ANALYZER] Track C polygons (circles)        : 0 (no raw_entities)")

    if not polygons and not circle_polys:
        print(f"[ANALYZER] No polygons at all - returning fallback (0 holes)")
        return _fallback_result()

    print(f"[ANALYZER] Total polygon candidates          : {len(polygons)} (+ {len(circle_polys)} circles)")

    # -- 3. Find outer boundary from the polygon track ------------------------
    #
    #   Sort by area; skip drawing-frame rectangles; pick the largest.
    #   Circles are never the outer boundary of a sheet-metal part.
    #
    polygons.sort(key=lambda p: p.area, reverse=True)
    frame_indices = _find_frame_indices(polygons, bounding_box)

    outer_poly: Optional[Polygon] = None
    outer_idx:  Optional[int]     = None

    for i, poly in enumerate(polygons):
        if i in frame_indices:
            continue
        outer_poly = poly
        outer_idx  = i
        break

    if outer_poly is None or outer_poly.is_empty:
        if polygons:
            outer_poly = polygons[0]
            outer_idx  = 0
            print("[ANALYZER] Warning: no non-frame polygon found; using largest polygon as outer boundary.")
        elif circle_polys:
            # No closed-contour polygon at all, but analytical circles exist.
            # Synthesise outer boundary from the bounding box so holes can still
            # be classified correctly.
            outer_poly = _synthesize_bbox_polygon(bounding_box)
            outer_idx  = -1
            print("[ANALYZER] No polygon track results - synthesising outer boundary from bounding box.")
        else:
            return _fallback_result()

    print(f"[ANALYZER] Outer boundary area: {outer_poly.area:.3f}")
    print(f"[ANALYZER] Outer boundary perimeter: {outer_poly.exterior.length:.3f}")
    print(f"[ANALYZER] Frame indices filtered out: {frame_indices}")

    # -- 3b. Validate outer boundary actually contains holes -------------------
    #
    #   A polygon is a valid outer boundary only if it contains circle holes
    #   that are NOT the same circle as itself.  If the true outer boundary
    #   was never reconstructed (all polygons are hole circles), the "largest"
    #   polygon is a hole circle - it doesn't contain the others.  We then
    #   search all candidates for a better container, falling back to the
    #   drawing bounding box if none works.
    #
    valid_circles = [c for c in circle_polys if c.area >= MIN_AREA]
    if valid_circles:
        contained = _count_contained_circles(outer_poly, valid_circles)
        print(f"[ANALYZER] Outer boundary contains {contained} hole circle(s)")

        if contained == 0:
            # outer_poly holds no circles other than itself - likely wrong.
            best_outer, best_idx, best_count = _find_best_container(
                polygons, valid_circles, frame_indices
            )
            if best_count > 0:
                print(f"[ANALYZER] Switched outer boundary to polygon #{best_idx} "
                      f"(contains {best_count} circles)")
                outer_poly = best_outer
                outer_idx  = best_idx
            else:
                outer_poly = _synthesize_bbox_polygon(bounding_box)
                outer_idx  = -1
                print("[ANALYZER] No container polygon found - using bounding box as outer boundary")

    # -- 4. Unified contour-based hole detection -------------------------------
    #
    # Holes are identified by TOPOLOGY, not entity type:
    #   Any closed loop whose centroid lies inside the outer boundary = hole.
    #
    # Sources checked in order (deduplication prevents double-counting):
    #   a) Track A + B polygons - entity-type agnostic; covers circles, closed
    #      polylines, ellipses, splines, AND combinations of LINE/ARC that form
    #      closed loops (rectangles, triangles, slots, irregular polygons).
    #   b) CIRCLE entities - direct center-point fallback in case Track A
    #      tessellation missed a circle due to boundary precision.
    #   c) Other closed raw entities - fallback for any closed entity not
    #      captured by Track A.

    max_dim = max(bounding_box.get("width", 1) or 1, bounding_box.get("height", 1) or 1)
    _outer_buf = None
    try:
        _outer_buf = outer_poly.buffer(max_dim * 0.005)
    except Exception:
        pass

    def _pt_inside(px: float, py: float) -> bool:
        pt = Point(px, py)
        if outer_poly.contains(pt):
            return True
        if _outer_buf is not None and _outer_buf.contains(pt):
            return True
        return False

    seen_positions: list = []

    def _is_duplicate(px: float, py: float) -> bool:
        return any(math.hypot(px - sx, py - sy) < DEDUP_DISTANCE for sx, sy in seen_positions)

    hole_details: list = []

    # 4a. Track A + B polygons - primary path, handles ALL closed loop types.
    deduped_polys = _dedup_by_centroid(polygons)
    for poly in deduped_polys:
        if poly.is_empty or poly.area < MIN_AREA:
            continue
        # Skip outer boundary (same area + high overlap)
        if outer_poly.area > 0:
            rel_diff = abs(poly.area - outer_poly.area) / outer_poly.area
            if rel_diff < 0.05:
                try:
                    if outer_poly.intersection(poly).area / poly.area > 0.90:
                        continue
                except Exception:
                    pass
        c = poly.centroid
        cx, cy = c.x, c.y
        if _is_duplicate(cx, cy):
            continue
        if not _pt_inside(cx, cy):
            continue
        seen_positions.append((cx, cy))
        hole_details.append(_describe_hole(poly, outer_poly))

    print(f"[ANALYZER] Track A+B holes: {len(hole_details)}")

    # 4b. CIRCLE entities - direct center-point fallback.
    for item in (raw_entities or []):
        if item.get("type") != "CIRCLE":
            continue
        center = item.get("center")
        radius = item.get("radius")
        if not center or radius is None:
            continue
        try:
            cx = float(center[0])
            cy = float(center[1])
            r  = float(radius)
            area = math.pi * r * r
            if area < MIN_AREA:
                continue
            if _is_duplicate(cx, cy):
                print(f"[ANALYZER] CIRCLE ({cx:.2f},{cy:.2f}) r={r:.3f} - duplicate, skip")
                continue
            if not _pt_inside(cx, cy):
                print(f"[ANALYZER] CIRCLE ({cx:.2f},{cy:.2f}) r={r:.3f} - outside boundary, skip")
                continue
            seen_positions.append((cx, cy))
            print(f"[ANALYZER] CIRCLE ({cx:.2f},{cy:.2f}) r={r:.3f} - HOLE #{len(hole_details)+1}")
            hole_details.append({
                "type":      "circle",
                "location":  "internal",
                "diameter":  round(r * 2, 4),
                "area":      round(area, 4),
                "perimeter": round(2 * math.pi * r, 4),
            })
        except Exception as exc:
            print(f"[ANALYZER] CIRCLE scan error: {exc}")

    print(f"[ANALYZER] Circle holes (direct): {len([h for h in hole_details if h.get('type') == 'circle'])}")

    # 4c. Other closed raw entities - fallback for any closed shape not
    #     captured by Track A (LWPOLYLINE, POLYLINE, ELLIPSE, SPLINE).
    for item in (raw_entities or []):
        etype = item.get("type", "")
        if etype == "CIRCLE":
            continue
        if not item.get("closed"):
            continue
        pts = item.get("points", [])
        if len(pts) < 3:
            continue
        try:
            poly = Polygon([(float(p[0]), float(p[1])) for p in pts])
            if not poly.is_valid:
                poly = make_valid(poly)
            if poly.geom_type != "Polygon":
                continue
            if poly.is_empty or poly.area < MIN_AREA:
                continue
            if outer_poly.area > 0:
                rel_diff = abs(poly.area - outer_poly.area) / outer_poly.area
                if rel_diff < 0.05:
                    try:
                        if outer_poly.intersection(poly).area / poly.area > 0.90:
                            print(f"[ANALYZER] {etype} skipped (outer boundary shape)")
                            continue
                    except Exception:
                        pass
            cx, cy = poly.centroid.x, poly.centroid.y
            if _is_duplicate(cx, cy):
                continue
            if not _pt_inside(cx, cy):
                continue
            seen_positions.append((cx, cy))
            detail = _describe_hole(poly, outer_poly)
            print(f"[ANALYZER] {etype} ({cx:.2f},{cy:.2f}) area={poly.area:.3f} - HOLE #{len(hole_details)+1} ({detail['type']})")
            hole_details.append(detail)
        except Exception as exc:
            print(f"[ANALYZER] {etype} scan error: {exc}")

    print(f"[ANALYZER] Total holes detected: {len(hole_details)}")

    # -- 5. Outer perimeter ----------------------------------------------------
    try:
        perimeter = outer_poly.exterior.length
    except Exception:
        perimeter = _fallback_perimeter(bounding_box)

    return {
        "holes":               len(hole_details),
        "perimeter":           round(perimeter, 3),
        "outer_boundary_area": round(outer_poly.area, 3),
        "hole_details":        hole_details,
        "total_holes":                len(hole_details),
        "internal_cutouts_detected":  len(hole_details),
        "outer_perimeter":            round(perimeter, 3),
    }


# ===============================================================================
# POLYGON BUILDING
# ===============================================================================

def _build_polygons(contours: list) -> list:
    """Convert raw point lists to valid Shapely Polygons, filtering rubbish."""
    result: list[Polygon] = []

    for contour in contours:
        if not contour or len(contour) < 3:
            continue

        # Normalise to list of (float, float) tuples
        try:
            pts = [(float(p[0]), float(p[1])) for p in contour]
        except (TypeError, IndexError):
            continue

        # Remove consecutive duplicates
        pts = _deduplicate(pts)
        if len(pts) < 3:
            continue

        # Ensure closed (first == last)
        if pts[0] != pts[-1]:
            pts.append(pts[0])

        try:
            poly = Polygon(pts)

            if not poly.is_valid:
                poly = make_valid(poly)

            # make_valid can return GeometryCollection or MultiPolygon
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

            if poly.is_valid and not poly.is_empty and poly.area >= MIN_AREA:
                result.append(poly)

        except Exception as exc:
            print(f"[ANALYZER] Polygon build error: {exc}")
            continue

    return result


def _polygonize_open_edges(raw_entities: list) -> list:
    """
    Convert all *open* entity segments to Shapely LineStrings, node them
    together, then reconstruct closed polygons via shapely.ops.polygonize().

    This recovers closed loops built from many separate LINE / ARC entities -
    a common pattern in sheet-metal DXF files where the cutting profile is
    drawn as individual edges rather than a single closed polyline.

    Parameters
    ----------
    raw_entities : list of geometry dicts from the DXF parser

    Returns
    -------
    List of valid Shapely Polygon objects with area >= MIN_AREA.
    """
    lines: list = []

    for item in raw_entities:
        if item.get("closed"):
            continue  # already handled via Track A (closed contours)
        raw_pts = item.get("points", [])
        if len(raw_pts) < 2:
            continue
        try:
            # Snap coordinates to a fine grid so that nearly-coincident
            # endpoints (common when different CAD tools write the same DXF)
            # are treated as exactly coincident by unary_union / polygonize.
            coords = [
                (
                    round(float(p[0]) / SNAP_PRECISION) * SNAP_PRECISION,
                    round(float(p[1]) / SNAP_PRECISION) * SNAP_PRECISION,
                )
                for p in raw_pts
            ]
            # Remove consecutive duplicates
            deduped = [coords[0]]
            for c in coords[1:]:
                if abs(c[0] - deduped[-1][0]) > 1e-9 or abs(c[1] - deduped[-1][1]) > 1e-9:
                    deduped.append(c)
            if len(deduped) >= 2:
                lines.append(LineString(deduped))
        except Exception as exc:
            print(f"[ANALYZER] LineString build error: {exc}")
            continue

    if not lines:
        return []

    if len(lines) > MAX_POLYGONIZE_SEGS:
        print(f"[ANALYZER] Track B skipped - {len(lines)} segments > MAX ({MAX_POLYGONIZE_SEGS})")
        return []

    try:
        # Node all lines at their intersections/shared endpoints
        merged = unary_union(lines)
        # Reconstruct closed rings from the planar graph
        result = list(polygonize(merged))
        valid: list = []
        for p in result:
            if p.is_empty:
                continue
            if not p.is_valid:
                p = make_valid(p)
            if p.geom_type == "MultiPolygon":
                for sub in p.geoms:
                    if sub.area >= MIN_AREA:
                        valid.append(sub)
            elif p.geom_type == "Polygon" and p.area >= MIN_AREA:
                valid.append(p)
        return valid
    except Exception as exc:
        print(f"[ANALYZER] polygonize error: {exc}")
        return []


def _extract_circle_polygons(raw_entities: list) -> list:
    """
    Extract CIRCLE entities from the raw geometry list and convert each one
    to an analytical Shapely Polygon using Point(cx, cy).buffer(radius).

    Why not rely on tessellated circles from Track A?
    -------------------------------------------------
    The DXF parser already tessellates circles into point lists (Track A), but
    a tessellated polygon has its boundary points *exactly on* the outer polygon
    boundary when the hole is a snug fit.  Shapely's `contains()` treats any
    shared boundary point as "not inside", so the containment test fails even
    with the 0.01 buffer.

    Point.buffer(r) generates a proper circular polygon whose interior is
    correctly handled by all Shapely predicates regardless of boundary contact.

    Parameters
    ----------
    raw_entities : list of geometry dicts (from dxf_parser.py)

    Returns
    -------
    List of valid Shapely Polygon objects, one per CIRCLE entity.
    """
    result: list = []
    seen_types: set = set()

    for item in raw_entities:
        etype = item.get("type", "?")

        # Log every unique entity type we encounter in this pass
        if etype not in seen_types:
            seen_types.add(etype)
            print(f"[ANALYZER][CircleTrack] entity type seen: {etype}")

        if etype != "CIRCLE":
            continue

        center = item.get("center")
        radius = item.get("radius")

        if center is None or radius is None:
            print(f"[ANALYZER][CircleTrack] CIRCLE missing center/radius - skipped")
            continue

        try:
            r  = float(radius)
            cx = float(center[0])
            cy = float(center[1])

            if r < 1e-6:
                print(f"[ANALYZER][CircleTrack] CIRCLE at ({cx:.3f},{cy:.3f}) r={r:.6f} - too small, skipped")
                continue

            poly     = Point(cx, cy).buffer(r)
            computed_area = poly.area

            if not poly.is_valid or poly.is_empty:
                print(f"[ANALYZER][CircleTrack] CIRCLE at ({cx:.3f},{cy:.3f}) r={r:.3f} - invalid polygon, skipped")
                continue

            if computed_area < MIN_AREA:
                print(f"[ANALYZER][CircleTrack] CIRCLE at ({cx:.3f},{cy:.3f}) r={r:.3f}"
                      f" area={computed_area:.4f} < MIN_AREA={MIN_AREA} - filtered")
                continue

            print(f"[ANALYZER][CircleTrack] CIRCLE at ({cx:.3f},{cy:.3f}) r={r:.3f}"
                  f" area={computed_area:.4f} - accepted")
            result.append(poly)

        except Exception as exc:
            print(f"[ANALYZER][CircleTrack] Circle extraction error: {exc}")

    print(f"[ANALYZER][CircleTrack] Total circles accepted: {len(result)}")
    return result


def _deduplicate_holes(holes: list) -> list:
    """
    Remove duplicate hole polygons that share the same spatial location.

    A CIRCLE entity can appear in both Track A (tessellated closed contour)
    and Track C (analytical Point.buffer).  We keep whichever polygon was
    added first (circle track runs first, so the accurate version wins).

    Two holes are considered duplicates when their centroids are within
    DEDUP_DISTANCE of each other.

    Parameters
    ----------
    holes : list of Shapely Polygon objects (may contain duplicates)

    Returns
    -------
    De-duplicated list preserving insertion order.
    """
    unique: list = []

    for poly in holes:
        try:
            c = poly.centroid
            is_dup = any(
                c.distance(accepted.centroid) < DEDUP_DISTANCE
                for accepted in unique
            )
            if not is_dup:
                unique.append(poly)
        except Exception:
            unique.append(poly)  # keep on error

    return unique


def _deduplicate(pts: list) -> list:
    """Remove consecutive duplicate coordinate pairs."""
    if not pts:
        return pts
    out = [pts[0]]
    for p in pts[1:]:
        if abs(p[0] - out[-1][0]) > 1e-9 or abs(p[1] - out[-1][1]) > 1e-9:
            out.append(p)
    return out


def _dedup_by_centroid(polygons: list) -> list:
    """
    Remove polygon duplicates that arise from multi-track reconstruction.

    Two polygons are considered the same shape when:
      - Their centroids are within DEDUP_DISTANCE of each other, AND
      - Their areas agree within 5 %.

    This eliminates duplicates such as:
      - CIRCLE appearing in Track A (tessellated) and Track C (analytical buffer)
      - LINE-based loops reconstructed by both _chain_segments_to_loops (Track A)
        and _polygonize_open_edges (Track B)

    The first occurrence is kept; later duplicates are dropped.
    """
    unique: list = []
    for p in polygons:
        try:
            c = p.centroid
            is_dup = False
            for q in unique:
                try:
                    if c.distance(q.centroid) < DEDUP_DISTANCE:
                        if q.area > 0 and abs(p.area - q.area) / q.area < 0.05:
                            is_dup = True
                            break
                except Exception:
                    pass
            if not is_dup:
                unique.append(p)
        except Exception:
            unique.append(p)
    return unique


def _synthesize_bbox_polygon(bounding_box: dict) -> "Polygon":
    """
    Build a rectangular Polygon that tightly wraps the drawing bounding box.

    Used as a last-resort outer boundary when the true outer boundary cannot be
    reconstructed from the DXF entities (e.g. LINE segments with non-matching
    endpoints, or a drawing that consists solely of CIRCLE holes).

    A 0.1 % margin is added on all sides so that holes that touch the bbox
    edge still register a containment ratio of 1.0.
    """
    w      = bounding_box.get("width",  1) or 1
    h      = bounding_box.get("height", 1) or 1
    margin = max(w, h) * 0.001
    x0 = bounding_box.get("minX", 0) - margin
    y0 = bounding_box.get("minY", 0) - margin
    x1 = bounding_box.get("maxX", 1) + margin
    y1 = bounding_box.get("maxY", 1) + margin
    return Polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])


def _count_contained_circles(outer: "Polygon", circles: list) -> int:
    """
    Count how many circles from *circles* are genuinely inside *outer*.

    A circle that is essentially the same polygon as *outer* (matching area
    and centroid) is excluded - this prevents a hole-circle that was
    accidentally promoted to outer boundary from validating itself.

    Parameters
    ----------
    outer   : candidate outer-boundary Polygon
    circles : list of analytical circle Polygons (from _extract_circle_polygons)

    Returns
    -------
    Number of circles (other than outer itself) with containment ratio >= HOLE_OVERLAP_RATIO.
    """
    count = 0
    for c in circles:
        try:
            # Skip circles that are essentially the same shape as outer
            if outer.area > 0:
                rel_area_diff = abs(c.area - outer.area) / outer.area
                if rel_area_diff < 0.05:
                    if outer.intersection(c).area / c.area > 0.95:
                        continue  # same circle - not a genuine hole

            ratio = outer.intersection(c).area / c.area if c.area > 0 else 0
            if ratio >= 0.50:
                count += 1
        except Exception:
            pass
    return count


def _find_best_container(
    polygons: list,
    circles:  list,
    frame_indices: set,
) -> tuple:
    """
    Search the top-10 largest polygons for whichever contains the most circles.

    Used when the initially selected outer boundary fails the containment
    sanity check.  Returns (best_polygon, best_index, circle_count).
    If no polygon contains any circles, returns (None, -1, 0).
    """
    best_poly  = None
    best_idx   = -1
    best_count = 0

    for j, candidate in enumerate(polygons[:10]):
        if j in frame_indices:
            continue
        cnt = _count_contained_circles(candidate, circles)
        if cnt > best_count:
            best_count = cnt
            best_poly  = candidate
            best_idx   = j

    return best_poly, best_idx, best_count


# ===============================================================================
# DRAWING FRAME / TITLE BLOCK DETECTION
# ===============================================================================

def _find_frame_indices(polygons: list, bounding_box: dict) -> set:
    """
    Return the set of polygon indices that look like drawing frames/borders.

    A drawing frame must satisfy ALL four conditions:

    1. It is a simple axis-aligned rectangle (<= 6 exterior coordinates).
    2. Its area covers >= 97 % of the overall drawing bounding box.
    3. All four of its sides are within 2 % of max(W, H) of the matching
       bounding-box edge - i.e. it hugs the bbox closely on every side.
    4. Its isoperimetric ratio  L^2 / A  exceeds ISOPERIMETRIC_RATIO,
       indicating a thin-walled "frame" shape rather than a solid part.
       (For a solid square, L^2/A = 16; a very thin rectangle -> inf.)

    Condition 4 is the key discriminator: a solid rectangular sheet-metal
    part has L^2/A ~= 16, while a drawing border (thin walls) has L^2/A >> 16.

    NOTE: Conditions 1-3 alone are NOT sufficient because a rectangular
    sheet-metal part also satisfies them (its bbox IS itself).
    """
    frame_indices: set = set()

    bb_w    = bounding_box.get("width",  0)
    bb_h    = bounding_box.get("height", 0)
    bb_area = bb_w * bb_h

    if bb_area < 1.0:
        return frame_indices  # drawing too small to have a meaningful frame

    bb_min_x = bounding_box.get("minX", 0.0)
    bb_min_y = bounding_box.get("minY", 0.0)
    bb_max_x = bounding_box.get("maxX", 0.0)
    bb_max_y = bounding_box.get("maxY", 0.0)
    edge_tol = max(bb_w, bb_h) * FRAME_EDGE_REL_TOL

    for i, poly in enumerate(polygons):
        try:
            # 1. Simple rectangle
            if not _is_simple_rectangle(poly):
                continue

            # 2. Coverage
            if poly.area / bb_area < FRAME_MIN_COVERAGE:
                continue

            # 3. Hugs all four bbox edges
            bx0, by0, bx1, by1 = poly.bounds
            if not (
                abs(bx0 - bb_min_x) < edge_tol and
                abs(by0 - bb_min_y) < edge_tol and
                abs(bx1 - bb_max_x) < edge_tol and
                abs(by1 - bb_max_y) < edge_tol
            ):
                continue

            # 4. Isoperimetric ratio - thin frame vs. solid part
            ext_len = poly.exterior.length
            iso_ratio = (ext_len ** 2) / poly.area if poly.area > 0 else 0
            if iso_ratio <= ISOPERIMETRIC_RATIO:
                # L^2/A <= 50 -> solid-ish rectangle (sheet metal part outline)
                # do NOT exclude it
                continue

            frame_indices.add(i)
            print(f"[ANALYZER] Drawing frame detected: polygon #{i}  L^2/A={iso_ratio:.1f}")

        except Exception:
            pass

    return frame_indices


def _is_simple_rectangle(poly: "Polygon") -> bool:
    """Return True if the polygon is an axis-aligned rectangle (4 unique vertices)."""
    try:
        coords = list(poly.exterior.coords)
        # 5 coords = 4 unique points + closing repeat
        unique = coords[:-1] if coords[0] == coords[-1] else coords
        if len(unique) != 4:
            return False

        xs = [c[0] for c in unique]
        ys = [c[1] for c in unique]
        x_range = max(xs) - min(xs)
        y_range = max(ys) - min(ys)
        if x_range < 1 or y_range < 1:
            return False

        # Every corner must be at an intersection of min/max x and y
        tol = max(x_range, y_range) * 0.02
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)

        for x, y in unique:
            on_x = abs(x - min_x) < tol or abs(x - max_x) < tol
            on_y = abs(y - min_y) < tol or abs(y - max_y) < tol
            if not (on_x and on_y):
                return False

        return True
    except Exception:
        return False


# ===============================================================================
# HOLE METADATA
# ===============================================================================

def _describe_hole(poly: "Polygon", outer_poly: "Polygon | None" = None) -> dict:
    """
    Return a metadata dict describing a detected hole / cutout polygon.

    Shape classification (type field)
    ----------------------------------
    - "circle"    : iso-perimetric ratio near 4pi ~= 12.57  -> reports diameter
    - "slot"      : bounding-box aspect ratio > 2.5       -> reports width/length
    - "rectangle" : exactly 4 unique vertices             -> reports width/height
    - "polygon"   : everything else

    Spatial classification (location field)
    ----------------------------------------
    - "internal"    : hole is fully (>= 95 %) inside the outer boundary
    - "edge_cutout" : hole crosses the outer boundary edge (side notch, partial cutout)

    The location field reflects sheet-metal manufacturing semantics: both
    types are genuine material-removal features.
    """
    try:
        ext_len = poly.exterior.length
        area    = poly.area
        iso     = (ext_len ** 2) / area if area > 0 else 0

        # -- Spatial location relative to outer boundary --------------------
        location = "internal"
        if outer_poly is not None and not outer_poly.is_empty:
            try:
                overlap = outer_poly.intersection(poly).area
                ratio   = overlap / area if area > 0 else 1.0
                location = "internal" if ratio >= 0.95 else "edge_cutout"
            except Exception:
                pass

        # -- Shape classification -------------------------------------------

        # Circle: isoperimetric ratio ~= 4pi ~= 12.57
        if iso < 14.5:
            radius   = math.sqrt(area / math.pi)
            diameter = round(radius * 2, 4)
            return {
                "type":      "circle",
                "location":  location,
                "diameter":  diameter,
                "area":      round(area, 4),
                "perimeter": round(ext_len, 4),
            }

        # Slot: long narrow shape
        bounds = poly.bounds
        w      = bounds[2] - bounds[0]
        h      = bounds[3] - bounds[1]
        aspect = max(w, h) / max(min(w, h), 1e-9)
        if aspect > 2.5:
            return {
                "type":      "slot",
                "location":  location,
                "area":      round(area, 4),
                "perimeter": round(ext_len, 4),
                "width":     round(min(w, h), 4),
                "length":    round(max(w, h), 4),
            }

        # Rectangular cutout: exactly 4 unique vertices
        coords = list(poly.exterior.coords)
        unique = coords[:-1] if coords[0] == coords[-1] else coords
        if len(unique) == 4:
            return {
                "type":      "rectangle",
                "location":  location,
                "area":      round(area, 4),
                "perimeter": round(ext_len, 4),
                "width":     round(min(w, h), 4),
                "height":    round(max(w, h), 4),
            }

        # Generic polygon cutout
        return {
            "type":      "polygon",
            "location":  location,
            "area":      round(area, 4),
            "perimeter": round(ext_len, 4),
        }

    except Exception:
        return {"type": "unknown", "location": "internal", "area": 0.0, "perimeter": 0.0}


# ===============================================================================
# FALLBACKS
# ===============================================================================

def count_circle_holes(raw_entities: list) -> int:
    """
    Count all CIRCLE entities with a positive radius.

    Used as a last-resort fallback when the Shapely polygon containment
    pipeline returns zero holes (e.g. the outer boundary could not be
    reconstructed for a given drawing).  Every circle with radius > 0 is
    assumed to be a cutting hole - no containment check is performed.

    Parameters
    ----------
    raw_entities : list of geometry dicts from the DXF parser

    Returns
    -------
    int - number of circles found
    """
    count = 0
    for entity in raw_entities:
        if entity.get("type") == "CIRCLE":
            radius = entity.get("radius", 0)
            if radius and float(radius) > 0:
                count += 1
    return count


def _fallback_result() -> dict:
    return {
        "holes":               0,
        "perimeter":           0.0,
        "outer_boundary_area": 0.0,
        "hole_details":        [],
        "total_holes":                0,
        "internal_cutouts_detected":  0,
        "outer_perimeter":            0.0,
    }


def _fallback_perimeter(bbox: dict) -> float:
    w = bbox.get("width",  0)
    h = bbox.get("height", 0)
    return round(2 * (w + h), 3)


# ===============================================================================
# EDGE DEBUG HELPERS  (imported by main.py)
# ===============================================================================

def build_edges_from_entities(raw_entities: list, include_closed: bool = True) -> list:
    """
    Return a list of snapped line segments built from raw entity point lists.
    Each segment is [[x1, y1], [x2, y2]].
    """
    edges: list = []
    if not raw_entities:
        return edges

    def _snap(pt) -> tuple:
        return (
            round(float(pt[0]) / SNAP_PRECISION) * SNAP_PRECISION,
            round(float(pt[1]) / SNAP_PRECISION) * SNAP_PRECISION,
        )

    for item in raw_entities:
        if not include_closed and item.get("closed"):
            continue
        pts = item.get("points", [])
        if len(pts) < 2:
            continue
        try:
            coords = [_snap(p) for p in pts]
            deduped = [coords[0]]
            for c in coords[1:]:
                if abs(c[0] - deduped[-1][0]) > 1e-9 or abs(c[1] - deduped[-1][1]) > 1e-9:
                    deduped.append(c)
            for i in range(len(deduped) - 1):
                a = deduped[i]
                b = deduped[i + 1]
                if abs(a[0] - b[0]) < 1e-12 and abs(a[1] - b[1]) < 1e-12:
                    continue
                edges.append([[round(a[0], 6), round(a[1], 6)], [round(b[0], 6), round(b[1], 6)]])
        except Exception:
            continue

    return edges
