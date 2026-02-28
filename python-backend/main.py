from fastapi import FastAPI, UploadFile, File, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel
import tempfile
import os
import uuid
import time
import asyncio
import sqlite3
from pathlib import Path

from engine.dxf_parser import parse_dxf
from engine.geometry_analyzer_v4 import analyze_geometry
from engine.pdf_parser import parse_pdf
from engine.geometry_analyzer import build_edges_from_entities
from engine.nesting_engine import PolygonPart, StockSheet, NestingConfig, nest_parts


# -------------------------------------------------------------
# DATABASE  (SQLite — auto-created, no server required)
# -------------------------------------------------------------

DB_PATH  = Path(__file__).parent / "totalviewer.db"
LOGO_DIR = Path(__file__).parent / "logos"
LOGO_DIR.mkdir(exist_ok=True)


def _get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def _init_db() -> None:
    conn = _get_db()
    cur  = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS app_settings (
            id                     INTEGER PRIMARY KEY DEFAULT 1,
            company_name           TEXT    DEFAULT 'Your Company',
            address                TEXT    DEFAULT '',
            gst_number             TEXT    DEFAULT '',
            logo_filename          TEXT    DEFAULT NULL,
            price_per_kg           REAL    DEFAULT 0.0,
            price_per_hour         REAL    DEFAULT 0.0,
            cutting_cost_per_meter REAL    DEFAULT 0.0,
            minimum_charge         REAL    DEFAULT 0.0,
            tax_percent            REAL    DEFAULT 18.0,
            footer_text            TEXT    DEFAULT 'Thank you for your business.'
        )
    """)

    cur.execute("INSERT OR IGNORE INTO app_settings (id) VALUES (1)")
    conn.commit()
    conn.close()


# -------------------------------------------------------------
# IN-MEMORY STORES
# -------------------------------------------------------------

SESSIONS: dict = {}


# -------------------------------------------------------------
# REQUEST MODELS
# -------------------------------------------------------------

class AnalyzeRequest(BaseModel):
    session_id: str


class NestPartInput(BaseModel):
    id:       str
    outer:    list[list[float]]
    holes:    list[list[list[float]]] = []
    quantity: int   = 1
    area:     float = 0.0


class NestStockInput(BaseModel):
    width:     float
    height:    float
    thickness: float = 0.0


class NestRequest(BaseModel):
    parts:     list[NestPartInput]
    stock:     NestStockInput
    step_x:    float       = 1.0
    step_y:    float       = 1.0
    margin:    float       = 0.0
    rotations: list[float] = [0.0, 90.0]
    edge_gap:  float       = 0.0


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

_init_db()


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
# APP SETTINGS  (no authentication — open access)
# -------------------------------------------------------------

@app.get("/settings")
def get_settings():
    """Return current app settings (company info, pricing, footer)."""
    conn = _get_db()
    row  = conn.execute("SELECT * FROM app_settings WHERE id=1").fetchone()
    conn.close()
    if not row:
        return {}
    data = dict(row)
    data["logo_url"] = "/settings/logo" if data.get("logo_filename") else None
    data.pop("logo_filename", None)
    return data


@app.put("/settings")
async def update_settings(request: Request):
    """Update app settings."""
    body = await request.json()

    allowed = {
        "company_name", "address", "gst_number",
        "price_per_kg", "price_per_hour", "cutting_cost_per_meter",
        "minimum_charge", "tax_percent", "footer_text",
    }
    updates = {k: v for k, v in body.items() if k in allowed}
    if not updates:
        return {"ok": True}

    set_clause = ", ".join(f"{k}=?" for k in updates)
    conn = _get_db()
    conn.execute(
        f"UPDATE app_settings SET {set_clause} WHERE id=1",
        list(updates.values()),
    )
    conn.commit()
    conn.close()
    return {"ok": True}


@app.post("/settings/logo")
async def upload_logo(file: UploadFile = File(...)):
    """Upload company logo (PNG, JPG, SVG, WEBP)."""
    ext = Path(file.filename).suffix.lower()
    if ext not in {".jpg", ".jpeg", ".png", ".svg", ".webp"}:
        raise HTTPException(status_code=400, detail="Logo must be jpg/png/svg/webp")

    # Remove any previous logo
    for old in LOGO_DIR.glob("company_logo.*"):
        old.unlink(missing_ok=True)

    logo_path = LOGO_DIR / f"company_logo{ext}"
    logo_path.write_bytes(await file.read())

    conn = _get_db()
    conn.execute("UPDATE app_settings SET logo_filename=? WHERE id=1", (str(logo_path),))
    conn.commit()
    conn.close()

    return {"ok": True, "logo_url": "/settings/logo"}


@app.get("/settings/logo")
def get_logo():
    """Serve the company logo file."""
    conn = _get_db()
    row  = conn.execute("SELECT logo_filename FROM app_settings WHERE id=1").fetchone()
    conn.close()

    if not row or not row["logo_filename"]:
        raise HTTPException(status_code=404, detail="No logo uploaded")

    logo_path = Path(row["logo_filename"])
    if not logo_path.exists():
        raise HTTPException(status_code=404, detail="Logo file not found")

    media_types = {
        ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".png": "image/png",  ".svg": "image/svg+xml",
        ".webp": "image/webp",
    }
    media_type = media_types.get(logo_path.suffix.lower(), "image/png")
    return FileResponse(str(logo_path), media_type=media_type)


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

        parsed     = parse_dxf(tmp_path)
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
    """
    ext = Path(file.filename).suffix.lower()

    if ext not in {".dxf", ".pdf"}:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Accepted: .dxf, .pdf",
        )

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            tmp.write(await file.read())
            tmp_path = tmp.name

        if ext == ".dxf":
            parsed     = parse_dxf(tmp_path)
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
# ANALYZE DXF
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
    if not body.parts:
        raise HTTPException(status_code=400, detail="No parts provided.")
    if body.stock.width <= 0 or body.stock.height <= 0:
        raise HTTPException(status_code=400, detail="Stock sheet dimensions must be positive.")

    try:
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

        sheet  = StockSheet(width=body.stock.width, height=body.stock.height, thickness=body.stock.thickness)
        config = NestingConfig(
            step_x    = max(body.step_x, 0.01),
            step_y    = max(body.step_y, 0.01),
            margin    = max(body.margin, 0.0),
            rotations = body.rotations if body.rotations else [0.0],
            edge_gap  = max(body.edge_gap, 0.0),
        )

        result = await asyncio.wait_for(
            asyncio.to_thread(nest_parts, parts, sheet, config),
            timeout=120.0,
        )

        print(f"[NEST] {len(parts)} part type(s) -> "
              f"{result['total_sheets']} sheet(s), "
              f"utilization={result['utilization']}%, waste={result.get('waste', result.get('waste_percent', 0))}%")

        return result

    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Nesting timed out (120 s limit).")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# -------------------------------------------------------------
# DEBUG
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
