from fastapi import FastAPI, UploadFile, File, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import tempfile
import os
import uuid
import time
import asyncio

from engine.dxf_parser import parse_dxf
from engine.geometry_analyzer_v4 import analyze_geometry
from engine.geometry_analyzer import build_edges_from_entities


# ─────────────────────────────────────────────────────────────
# SESSION STORE
# ─────────────────────────────────────────────────────────────
# Stores parsed DXF data between /upload → /analyze
# Cleared only when server restarts
# ─────────────────────────────────────────────────────────────

SESSIONS: dict = {}


# ─────────────────────────────────────────────────────────────
# REQUEST MODELS
# ─────────────────────────────────────────────────────────────

class AnalyzeRequest(BaseModel):
    session_id: str


# ─────────────────────────────────────────────────────────────
# FASTAPI INIT
# ─────────────────────────────────────────────────────────────

app = FastAPI(title="Total Viewer — Python Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─────────────────────────────────────────────────────────────
# HEALTH ROUTES
# ─────────────────────────────────────────────────────────────

@app.get("/")
def home():
    return {"status": "Total Viewer Python Backend Running"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/sessions")
def list_sessions():
    """Debug route — shows active sessions"""
    return {
        "active_sessions": list(SESSIONS.keys()),
        "count": len(SESSIONS)
    }


# ─────────────────────────────────────────────────────────────
# UPLOAD DXF
# ─────────────────────────────────────────────────────────────

@app.post("/upload")
async def upload_dxf(file: UploadFile = File(...)):

    if not file.filename.lower().endswith(".dxf"):
        raise HTTPException(
            status_code=400,
            detail="Only .dxf files are accepted."
        )

    tmp_path = None

    try:
        # Save temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".dxf") as tmp:
            tmp.write(await file.read())
            tmp_path = tmp.name

        # Parse DXF
        parsed = parse_dxf(tmp_path)

        # Create session
        session_id = str(uuid.uuid4())

        SESSIONS[session_id] = {
            "closed_contours": parsed["closed_contours"],
            "bounding_box": parsed["bounding_box"],
            "raw_entities": parsed.get("geometry"),
            "created_at": time.time(),
        }

        # Debug logs
        print("\n[UPLOAD] DXF Uploaded")
        print("Session created:", session_id)
        print("Active sessions:", list(SESSIONS.keys()), "\n")

        # Run analysis in a thread so it doesn't block the event loop.
        # 20-second timeout prevents hanging on complex DXF files.
        _fallback_analysis = {
            "holes": 0, "total_holes": 0, "internal_cutouts_detected": 0,
            "perimeter": 0.0, "outer_perimeter": 0.0, "external_perimeter": 0.0,
            "internal_perimeter": 0.0, "outer_boundary_area": 0.0,
            "hole_details": [],
            "hole_geometries": [],
            "parts": [{"part_id": 1, "holes": 0, "internal_perimeter": 0.0, "external_perimeter": 0.0}],
        }
        try:
            analysis = await asyncio.wait_for(
                asyncio.to_thread(
                    analyze_geometry,
                    parsed["closed_contours"],
                    parsed["bounding_box"],
                    parsed.get("geometry"),
                ),
                timeout=20.0,
            )
        except asyncio.TimeoutError:
            print("[UPLOAD] Analysis timed out after 20s — using fallback")
            analysis = _fallback_analysis
        except Exception as exc:
            print(f"[UPLOAD] Inline analysis error: {exc}")
            analysis = _fallback_analysis

        return {
            "session_id": session_id,
            "fileName": file.filename,
            "entities": parsed["entity_count"],
            "geometry": parsed["geometry"],
            "bounding_box": parsed["bounding_box"],
            "units": parsed["units"],
            "layers": parsed["layers"],
            # Analysis results — returned immediately on upload
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

    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        # Clean up temp file
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


# ─────────────────────────────────────────────────────────────
# DEBUG: Return snapped edges used for polygonization
# ─────────────────────────────────────────────────────────────
@app.get("/debug/edges")
async def debug_edges(session_id: str = Query(..., description="Session id from /upload"),
                      include_closed: bool = Query(True, description="Include edges from closed contours")):
    session = SESSIONS.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    raw_entities = session.get("raw_entities", [])
    edges = build_edges_from_entities(raw_entities, include_closed=include_closed)
    return {"count": len(edges), "edges": edges}


# ─────────────────────────────────────────────────────────────
# ANALYZE DXF
# ─────────────────────────────────────────────────────────────

@app.post("/analyze")
async def analyze_dxf(body: AnalyzeRequest):

    session_id = body.session_id

    print("\n🔍 Analyze request received")
    print("Requested session:", session_id)
    print("Available sessions:", list(SESSIONS.keys()))

    session = SESSIONS.get(session_id)

    if session is None:
        raise HTTPException(
            status_code=404,
            detail="Session not found. Please re-upload the DXF file."
        )

    try:
        analysis = analyze_geometry(
            session["closed_contours"],
            session["bounding_box"],
            raw_entities=session["raw_entities"],
        )

        return {
            "holes": analysis["holes"],
            "total_holes": analysis["total_holes"],
            "internal_cutouts_detected": analysis["internal_cutouts_detected"],
            "hole_details": analysis.get("hole_details", []),
            "hole_geometries": analysis.get("hole_geometries", []),
            "perimeter": analysis["perimeter"],
            "outer_perimeter": analysis["outer_perimeter"],
            "external_perimeter": analysis.get("external_perimeter", 0.0),
            "internal_perimeter": analysis.get("internal_perimeter", 0.0),
            "outer_boundary_area": analysis["outer_boundary_area"],
            "parts": analysis.get("parts", []),
        }

    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
