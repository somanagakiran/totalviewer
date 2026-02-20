from fastapi import FastAPI, UploadFile, File, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import tempfile
import os
import uuid
import time
import asyncio
from datetime import datetime, timezone
from typing import Optional

import json
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Text, text
from sqlalchemy.orm import declarative_base, sessionmaker

from engine.dxf_parser import parse_dxf
from engine.geometry_analyzer_v4 import analyze_geometry
from engine.geometry_analyzer import build_edges_from_entities


# ─────────────────────────────────────────────────────────────
# DATABASE
# ─────────────────────────────────────────────────────────────

_raw_db_url = os.getenv("DATABASE_URL", "")

# Supabase/Heroku use "postgres://" — SQLAlchemy requires "postgresql://"
DATABASE_URL = (
    _raw_db_url.replace("postgres://", "postgresql://", 1)
    if _raw_db_url.startswith("postgres://")
    else _raw_db_url
)

Base = declarative_base()


class Part(Base):
    __tablename__ = "parts"

    id                 = Column(Integer, primary_key=True, index=True)
    file_name          = Column(String, nullable=False)
    part_name          = Column(String, nullable=False)
    material           = Column(String, nullable=False)
    holes              = Column(Integer, nullable=False)
    external_perimeter = Column(Float, nullable=False)
    internal_perimeter = Column(Float, nullable=False)
    total_perimeter    = Column(Float, nullable=False)
    geometry_json      = Column(Text, nullable=True)
    created_at         = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class PartResponse(BaseModel):
    id:                 int
    file_name:          str
    part_name:          str
    material:           str
    holes:              int
    external_perimeter: float
    internal_perimeter: float
    total_perimeter:    float
    created_at:         datetime

    model_config = {"from_attributes": True}


_engine = None
_SessionLocal = None

if DATABASE_URL:
    try:
        _engine = create_engine(
            DATABASE_URL,
            pool_pre_ping=True,
            connect_args={"sslmode": "require"},
        )
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)
        Base.metadata.create_all(bind=_engine)
        # Idempotent migration — adds geometry_json if the column is missing
        # (create_all never alters existing tables)
        with _engine.connect() as _conn:
            _conn.execute(text(
                "ALTER TABLE parts ADD COLUMN IF NOT EXISTS geometry_json TEXT"
            ))
            _conn.commit()
        print("[DB] Connected to Supabase PostgreSQL — tables ready")
    except Exception as _db_exc:
        print(f"[DB] Connection failed: {_db_exc!r}")
else:
    print("[DB] DATABASE_URL not set — database features disabled")


def _get_db():
    """Return a new DB session, or raise 503 if DB is not configured."""
    if _SessionLocal is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    return _SessionLocal()


def store_part(
    file_name: str,
    part_name: str,
    material: str,
    holes: int,
    external_perimeter: float,
    internal_perimeter: float,
    total_perimeter: float,
    geometry_json: Optional[str] = None,
) -> Optional[Part]:
    """Upsert one Part row (delete existing by file_name, then insert).
    Returns the saved object, or None on failure / DB unavailable."""
    if _SessionLocal is None:
        return None
    db = _SessionLocal()
    try:
        # Remove any previous record for the same file to avoid duplicates.
        # A re-upload is intentional, so overwrite is the correct behaviour.
        db.query(Part).filter(Part.file_name == file_name).delete()
        db.flush()
        part = Part(
            file_name=file_name,
            part_name=part_name,
            material=material,
            holes=holes,
            external_perimeter=external_perimeter,
            internal_perimeter=internal_perimeter,
            total_perimeter=total_perimeter,
            geometry_json=geometry_json,
        )
        db.add(part)
        db.commit()
        db.refresh(part)
        return part
    except Exception as exc:
        db.rollback()
        print(f"[DB] store_part error: {exc}")
        return None
    finally:
        db.close()


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

        # Persist to DB — runs after analysis, never blocks the response
        store_part(
            file_name=file.filename,
            part_name=os.path.splitext(file.filename)[0],
            material="",
            holes=analysis["holes"],
            external_perimeter=analysis.get("external_perimeter", 0.0),
            internal_perimeter=analysis.get("internal_perimeter", 0.0),
            total_perimeter=analysis["perimeter"],
            geometry_json=json.dumps(parsed["geometry"]),
        )

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


# ─────────────────────────────────────────────────────────────
# PARTS ENDPOINTS
# ─────────────────────────────────────────────────────────────

@app.get("/parts/{part_id}/geometry")
def get_part_geometry(part_id: int):
    db = _get_db()
    try:
        part = db.query(Part).filter(Part.id == part_id).first()
        if part is None:
            raise HTTPException(status_code=404, detail="Part not found")
        if not part.geometry_json:
            raise HTTPException(status_code=404, detail="Geometry not stored for this part")
        return json.loads(part.geometry_json)
    finally:
        db.close()


@app.get("/parts", response_model=list[PartResponse])
def get_parts():
    db = _get_db()
    try:
        return db.query(Part).order_by(Part.created_at.desc()).all()
    except Exception as exc:
        print(f"[DB] GET /parts error: {exc!r}")
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        db.close()


@app.delete("/parts/{part_id}")
def delete_part(part_id: int):
    db = _get_db()
    try:
        part = db.query(Part).filter(Part.id == part_id).first()
        if part is None:
            raise HTTPException(status_code=404, detail="Part not found")
        db.delete(part)
        db.commit()
        return {"deleted": part_id}
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        db.close()
