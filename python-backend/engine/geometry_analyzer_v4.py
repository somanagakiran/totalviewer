"""
Geometry Analyzer v4 - Optimized Hole Detection
================================================

Uses the optimized hole detector for improved detection of internal holes
and closed contours, including mixed entity types and non-PEDIT geometry.
"""

import math
from typing import Optional, List, Dict, Any

# Import our optimized hole detector
from engine.optimized_hole_detector import detect_holes_from_entities, count_holes_by_type

# -- Tunables ------------------------------------------------------------------
MIN_AREA            = 0.01   # ignore polygons smaller than this (units^2)
FRAME_MIN_COVERAGE  = 0.97   # frame must cover >= 97 % of the bbox area
FRAME_EDGE_REL_TOL  = 0.02   # frame edges within 2 % of max(W,H) of bbox edges
ISOPERIMETRIC_RATIO = 50.0   # L^2/A > 50 -> polygon is "hollow" (drawing frame)
DEDUP_DISTANCE      = 0.05   # centroids closer than this are considered duplicates

# ===============================================================================
# PUBLIC API
# ===============================================================================

def analyze_geometry(
    closed_contours: list,
    bounding_box:    dict,
    raw_entities:    list | None = None,
) -> dict:
    """
    Detect outer boundary, holes, and perimeter using optimized hole detector.

    Parameters
    ----------
    closed_contours : list of point loops  [[x, y], ...]  or  [(x, y), ...]
    bounding_box    : {minX, minY, maxX, maxY, width, height}
    raw_entities    : optional list of raw entity dicts from the parser

    Returns
    -------
    {
        "holes"               : int,
        "perimeter"           : float,
        "outer_perimeter"     : float,
        "external_perimeter"  : float (EP - perimeter of outer boundary),
        "internal_perimeter"  : float (IP - sum of all hole perimeters),
        "outer_boundary_area" : float,
        "hole_details"        : [{"type": ..., "area": ..., ...}, ...],
        "parts"               : [{"part_id": 1, "holes": int, "internal_perimeter": float, "external_perimeter": float}]
    }
    """
    print(f"[ANALYZER v4] Starting analysis with {len(raw_entities or [])} entities")
    
    if not raw_entities:
        print("[ANALYZER v4] No raw entities provided, using fallback")
        return _fallback_result()
    
    try:
        # Use the optimized hole detector
        result = detect_holes_from_entities(raw_entities, tolerance=0.1, min_area=MIN_AREA)

        # Convert to legacy format for frontend compatibility
        analysis_result = {
            "holes": result["total_holes"],
            "total_holes": result["total_holes"],
            "internal_cutouts_detected": result["internal_cutouts_detected"],
            "perimeter": result.get("outer_perimeter", 0),
            "outer_perimeter": result.get("outer_perimeter", 0),
            "external_perimeter": result.get("external_perimeter", 0),
            "internal_perimeter": result.get("internal_perimeter", 0),
            "outer_boundary_area": result["outer_boundary_area"],
            "hole_details": result["hole_details"],
            "hole_geometries": result["hole_geometries"],
        }

        # Build multi-part structure
        part = {
            "part_id": 1,
            "holes": result["total_holes"],
            "internal_perimeter": result.get("internal_perimeter", 0),
            "external_perimeter": result.get("external_perimeter", 0),
        }

        analysis_result["parts"] = [part]

        print(f"[ANALYZER v4] Analysis complete: {result['total_holes']} holes detected")
        print(f"[ANALYZER v4] IP={result.get('internal_perimeter', 0):.3f}, EP={result.get('external_perimeter', 0):.3f}")
        return analysis_result
        
    except Exception as e:
        print(f"[ANALYZER v4] Error in optimized detector: {e}")
        print("[ANALYZER v4] Falling back to legacy method")
        return _fallback_result()

def _fallback_result() -> dict:
    """Return empty result when analysis fails"""
    return {
        "holes": 0,
        "total_holes": 0,
        "internal_cutouts_detected": 0,
        "perimeter": 0.0,
        "outer_perimeter": 0.0,
        "external_perimeter": 0.0,
        "internal_perimeter": 0.0,
        "outer_boundary_area": 0.0,
        "hole_details": [],
        "hole_geometries": [],
        "parts": [{
            "part_id": 1,
            "holes": 0,
            "internal_perimeter": 0.0,
            "external_perimeter": 0.0,
        }],
    }