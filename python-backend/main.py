from fastapi import FastAPI, UploadFile, File, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import tempfile
import os
import uuid
import time
import asyncio
from pathlib import Path

from engine.dxf_parser import parse_dxf
from engine.geometry_analyzer_v4 import analyze_geometry
from engine.pdf_parser import parse_pdf
from engine.geometry_analyzer import build_edges_from_entities
from engine.nesting_engine import PolygonPart, StockSheet, NestingConfig, nest_parts


# -------------------------------------------------------------
# IN-MEMORY STORES  (no database required)
# -------------------------------------------------------------

parts_memory:    list = []   # placeholder for future feature work
projects_memory: list = []   # placeholder for future feature work


# -------------------------------------------------------------
# SESSION STORE  (parsed DXF data between /upload -> /analyze)
# -------------------------------------------------------------

SESSIONS: dict = {}


# -------------------------------------------------------------
# REQUEST MODELS
# -------------------------------------------------------------

class AnalyzeRequest(BaseModel):
    session_id: str


class NestPartInput(BaseModel):
    id:       str
    outer:    list[list[float]]   # [[x, y], ...]
    holes:    list[list[list[float]]] = []
    quantity: int   = 1
    area:     float = 0.0


class NestStockInput(BaseModel):
    width:     float
    height:    float
    thickness: float = 0.0


class NestRequest(BaseModel):
    parts: list[NestPartInput]
    stock: NestStockInput
    step_x:    float       = 1.0
    step_y:    float       = 1.0
    margin:    float       = 0.0
    rotations: list[float] = [0.0, 90.0]


# -------------------------------------------------------------
# ANALYSIS HELPERS
# -------------------------------------------------------------

_FALLBACK_ANALYSIS = {
    "holes": 0, "total_holes": 0, "internal_cutouts_detected": 0,
    "perimeter": 0.0, "outer_perimeter": 0.0,
    "external_perimeter": 0.0, "internal_perimeter": 0.0,
    "outer_boundary_area": 0.0,
    "hole_details": [], "hole_geometries": [],
    "parts": [{"part_id": 1, "holes": 0, "internal_perimeter": 0.0, "external_perimeter": 0.0}],
}


async def _run_analysis(parsed: dict) -> dict:
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(
                analyze_geometry,
                parsed["closed_contours"],
                parsed["bounding_box"],
                parsed.get("geometry"),
            ),
            timeout=20.0,
        )
    except asyncio.TimeoutError:
        print("[ANALYSIS] Timed out after 20s - using fallback")
        return _FALLBACK_ANALYSIS
    except Exception as exc:
        print(f"[ANALYSIS] Error: {exc}")
        return _FALLBACK_ANALYSIS


def _build_response(parsed: dict, analysis: dict, filename: str, session_id: str) -> dict:
    return {
        "session_id":                 session_id,
        "fileName":                   filename,
        "entities":                   parsed["entity_count"],
        "geometry":                   parsed["geometry"],
        "bounding_box":               parsed["bounding_box"],
        "units":                      parsed["units"],
        "layers":                     parsed["layers"],
        "holes":                      analysis["holes"],
        "total_holes":                analysis["total_holes"],
        "internal_cutouts_detected":  analysis["internal_cutouts_detected"],
        "perimeter":                  analysis["perimeter"],
        "outer_perimeter":            analysis["outer_perimeter"],
        "external_perimeter":         analysis.get("external_perimeter", 0.0),
        "internal_perimeter":         analysis.get("internal_perimeter", 0.0),
        "outer_boundary_area":        analysis["outer_boundary_area"],
        "hole_details":               analysis.get("hole_details", []),
        "hole_geometries":            analysis.get("hole_geometries", []),
        "parts":                      analysis.get("parts", []),
    }


# -------------------------------------------------------------
# FASTAPI INIT
# -------------------------------------------------------------

app = FastAPI(title="Total Viewer - Python Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -------------------------------------------------------------
# HEALTH
# -------------------------------------------------------------

@app.get("/")
def home():
    return {"status": "Total Viewer Python Backend Running"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/sessions")
def list_sessions():
    return {"active_sessions": list(SESSIONS.keys()), "count": len(SESSIONS)}


# -------------------------------------------------------------
# UPLOAD DXF
# -------------------------------------------------------------

@app.post("/upload")
async def upload_dxf(file: UploadFile = File(...)):

    if not file.filename.lower().endswith(".dxf"):
        raise HTTPException(status_code=400, detail="Only .dxf files are accepted.")

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".dxf") as tmp:
            tmp.write(await file.read())
            tmp_path = tmp.name

        parsed = parse_dxf(tmp_path)
        session_id = str(uuid.uuid4())

        SESSIONS[session_id] = {
            "closed_contours": parsed["closed_contours"],
            "bounding_box":    parsed["bounding_box"],
            "raw_entities":    parsed.get("geometry"),
            "created_at":      time.time(),
        }

        print(f"\n[UPLOAD] {file.filename} -> session {session_id}")

        analysis = await _run_analysis(parsed)
        return _build_response(parsed, analysis, file.filename, session_id)

    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


# -------------------------------------------------------------
# UNIFIED UPLOAD  (DXF + PDF)
# -------------------------------------------------------------

@app.post("/upload-drawing")
async def upload_drawing(file: UploadFile = File(...)):
    """
    Unified upload endpoint supporting .dxf and .pdf files.

    - .dxf  : identical behavior to /upload (parse + analyze geometry)
    - .pdf  : rasterize page to PNG, extract dimensions and vector lines
    """
    ext = Path(file.filename).suffix.lower()

    if ext not in {".dxf", ".pdf"}:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Accepted: .dxf, .pdf",
        )

    tmp_path = None
    try:
        suffix = ext  # keep original extension so parsers detect format correctly
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(await file.read())
            tmp_path = tmp.name

        # ── DXF branch ────────────────────────────────────────────────────
        if ext == ".dxf":
            parsed = parse_dxf(tmp_path)
            session_id = str(uuid.uuid4())

            SESSIONS[session_id] = {
                "closed_contours": parsed["closed_contours"],
                "bounding_box":    parsed["bounding_box"],
                "raw_entities":    parsed.get("geometry"),
                "created_at":      time.time(),
            }

            print(f"\n[UPLOAD-DRAWING] DXF {file.filename} -> session {session_id}")

            analysis = await _run_analysis(parsed)
            response = _build_response(parsed, analysis, file.filename, session_id)
            response["file_type"] = "dxf"
            return JSONResponse(response)

        # ── PDF branch ────────────────────────────────────────────────────
        else:
            print(f"\n[UPLOAD-DRAWING] PDF {file.filename}")
            result = await asyncio.wait_for(
                asyncio.to_thread(parse_pdf, tmp_path),
                timeout=30.0,
            )
            result["fileName"] = file.filename
            return JSONResponse(result)

    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Processing timed out.")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


# -------------------------------------------------------------
# ANALYZE DXF  (re-analyze from an existing session)
# -------------------------------------------------------------

@app.post("/analyze")
async def analyze_dxf(body: AnalyzeRequest):
    session = SESSIONS.get(body.session_id)
    if session is None:
        raise HTTPException(
            status_code=404,
            detail="Session not found. Please re-upload the DXF file.",
        )
    try:
        analysis = analyze_geometry(
            session["closed_contours"],
            session["bounding_box"],
            raw_entities=session["raw_entities"],
        )
        return {
            "holes":                      analysis["holes"],
            "total_holes":                analysis["total_holes"],
            "internal_cutouts_detected":  analysis["internal_cutouts_detected"],
            "hole_details":               analysis.get("hole_details", []),
            "hole_geometries":            analysis.get("hole_geometries", []),
            "perimeter":                  analysis["perimeter"],
            "outer_perimeter":            analysis["outer_perimeter"],
            "external_perimeter":         analysis.get("external_perimeter", 0.0),
            "internal_perimeter":         analysis.get("internal_perimeter", 0.0),
            "outer_boundary_area":        analysis["outer_boundary_area"],
            "parts":                      analysis.get("parts", []),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# -------------------------------------------------------------
# NESTING
# -------------------------------------------------------------

@app.post("/nest")
async def run_nesting(body: NestRequest):
    """
    True-shape nesting using the Bottom-Left placement algorithm.

    Accepts a list of polygon parts with quantities and a stock sheet size.
    Returns placement coordinates, sheet count, utilization, and waste.
    """
    if not body.parts:
        raise HTTPException(status_code=400, detail="No parts provided.")

    if body.stock.width <= 0 or body.stock.height <= 0:
        raise HTTPException(status_code=400, detail="Stock sheet dimensions must be positive.")

    try:
        # Convert request models -> nesting engine objects
        parts = []
        for p in body.parts:
            if len(p.outer) < 3:
                raise HTTPException(
                    status_code=400,
                    detail=f"Part '{p.id}' outer polygon must have at least 3 points."
                )
            if p.quantity < 1:
                raise HTTPException(
                    status_code=400,
                    detail=f"Part '{p.id}' quantity must be >= 1."
                )
            parts.append(PolygonPart(
                id       = p.id,
                outer    = [(pt[0], pt[1]) for pt in p.outer],
                holes    = [[(pt[0], pt[1]) for pt in ring] for ring in p.holes],
                quantity = p.quantity,
                area     = p.area,
            ))

        sheet  = StockSheet(
            width     = body.stock.width,
            height    = body.stock.height,
            thickness = body.stock.thickness,
        )
        config = NestingConfig(
            step_x    = max(body.step_x, 0.01),
            step_y    = max(body.step_y, 0.01),
            margin    = max(body.margin, 0.0),
            rotations = body.rotations if body.rotations else [0.0],
        )

        # Run in a thread - nesting is CPU-bound
        result = await asyncio.wait_for(
            asyncio.to_thread(nest_parts, parts, sheet, config),
            timeout=60.0,
        )

        print(f"[NEST] {len(parts)} part type(s) -> "
              f"{result['total_sheets']} sheet(s), "
              f"utilization={result['utilization']}%")

        return result

    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Nesting timed out (60 s limit).")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# -------------------------------------------------------------
# DEBUG: snapped edges used for polygonization
# -------------------------------------------------------------

@app.get("/debug/edges")
async def debug_edges(
    session_id:     str  = Query(...),
    include_closed: bool = Query(True),
):
    session = SESSIONS.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    edges = build_edges_from_entities(
        session.get("raw_entities", []),
        include_closed=include_closed,
    )
    return {"count": len(edges), "edges": edges}
