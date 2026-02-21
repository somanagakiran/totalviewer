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

from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, JSON, ForeignKey, text
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

from engine.dxf_parser import parse_dxf
from engine.geometry_analyzer_v4 import analyze_geometry
from engine.geometry_analyzer import build_edges_from_entities


# ─────────────────────────────────────────────────────────────
# DATABASE
# ─────────────────────────────────────────────────────────────

_raw_db_url = os.getenv("DATABASE_URL", "")

DATABASE_URL = (
    _raw_db_url.replace("postgres://", "postgresql://", 1)
    if _raw_db_url.startswith("postgres://")
    else _raw_db_url
)

Base = declarative_base()


class Project(Base):
    __tablename__ = "projects"

    id         = Column(Integer, primary_key=True, index=True)
    name       = Column(String, nullable=False, unique=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    parts      = relationship("Part", back_populates="project", cascade="all, delete-orphan")


class Part(Base):
    __tablename__ = "parts"

    id                 = Column(Integer, primary_key=True, index=True)
    project_id         = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=True)
    file_name          = Column(String, nullable=False)
    part_name          = Column(String, nullable=False)
    material           = Column(String, nullable=False, default="MS")
    holes              = Column(Integer, nullable=False)
    external_perimeter = Column(Float, nullable=False)
    internal_perimeter = Column(Float, nullable=False)
    total_perimeter    = Column(Float, nullable=False)
    geometry_json      = Column(JSON, nullable=True)
    created_at         = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    project            = relationship("Project", back_populates="parts")


# ─────────────────────────────────────────────────────────────
# PYDANTIC RESPONSE MODELS
# ─────────────────────────────────────────────────────────────

class ProjectResponse(BaseModel):
    id:         int
    name:       str
    created_at: datetime
    model_config = {"from_attributes": True}


class PartResponse(BaseModel):
    id:                 int
    project_id:         Optional[int]
    file_name:          str
    part_name:          str
    material:           str
    holes:              int
    external_perimeter: float
    internal_perimeter: float
    total_perimeter:    float
    created_at:         datetime
    model_config = {"from_attributes": True}


class CreateProjectRequest(BaseModel):
    name: str


# ─────────────────────────────────────────────────────────────
# DB ENGINE SETUP
# ─────────────────────────────────────────────────────────────

_engine       = None
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

        # Idempotent migrations for DBs that predate these columns
        try:
            with _engine.connect() as _mc:
                _mc.execute(text(
                    "ALTER TABLE parts ADD COLUMN IF NOT EXISTS geometry_json JSON"
                ))
                _mc.execute(text(
                    "ALTER TABLE parts ADD COLUMN IF NOT EXISTS "
                    "project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE"
                ))
                _mc.commit()
        except Exception as _me:
            print(f"[DB] Migration note: {_me}")

        print("[DB] Connected to PostgreSQL — tables ready")
    except Exception as _db_exc:
        print(f"[DB] Connection failed: {_db_exc!r}")
else:
    print("[DB] DATABASE_URL not set — database features disabled")


def _get_db():
    if _SessionLocal is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    return _SessionLocal()


# ─────────────────────────────────────────────────────────────
# SHARED ANALYSIS HELPER
# ─────────────────────────────────────────────────────────────

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
        print("[ANALYSIS] Timed out after 20s — using fallback")
        return _FALLBACK_ANALYSIS
    except Exception as exc:
        print(f"[ANALYSIS] Error: {exc}")
        return _FALLBACK_ANALYSIS


def _analysis_response(parsed: dict, analysis: dict, filename: str, session_id: str) -> dict:
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


# ─────────────────────────────────────────────────────────────
# SESSION STORE
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
# HEALTH
# ─────────────────────────────────────────────────────────────

@app.get("/")
def home():
    return {"status": "Total Viewer Python Backend Running"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/sessions")
def list_sessions():
    return {"active_sessions": list(SESSIONS.keys()), "count": len(SESSIONS)}


# ─────────────────────────────────────────────────────────────
# PROJECTS
# ─────────────────────────────────────────────────────────────

@app.get("/projects", response_model=list[ProjectResponse])
def get_projects():
    db = _get_db()
    try:
        return db.query(Project).order_by(Project.created_at.desc()).all()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        db.close()


@app.post("/projects", response_model=ProjectResponse)
def create_project(body: CreateProjectRequest):
    db = _get_db()
    try:
        project = Project(name=body.name.strip())
        db.add(project)
        db.commit()
        db.refresh(project)
        return project
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))
    finally:
        db.close()


@app.delete("/projects/{project_id}")
def delete_project(project_id: int):
    db = _get_db()
    try:
        project = db.query(Project).filter(Project.id == project_id).first()
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")
        db.delete(project)
        db.commit()
        return {"deleted": project_id}
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────
# PARTS WITHIN A PROJECT
# ─────────────────────────────────────────────────────────────

@app.get("/projects/{project_id}/parts", response_model=list[PartResponse])
def get_project_parts(project_id: int):
    db = _get_db()
    try:
        project = db.query(Project).filter(Project.id == project_id).first()
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")
        return (
            db.query(Part)
            .filter(Part.project_id == project_id)
            .order_by(Part.created_at.asc())
            .all()
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        db.close()


@app.post("/projects/{project_id}/parts")
async def upload_part_to_project(project_id: int, file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".dxf"):
        raise HTTPException(status_code=400, detail="Only .dxf files are accepted.")

    # Validate project exists
    db = _get_db()
    try:
        if db.query(Project).filter(Project.id == project_id).first() is None:
            raise HTTPException(status_code=404, detail="Project not found")
    finally:
        db.close()

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

        analysis = await _run_analysis(parsed)

        # Persist part under the project
        db_part_id = None
        db = _get_db()
        try:
            part = Part(
                project_id         = project_id,
                file_name          = file.filename,
                part_name          = os.path.splitext(file.filename)[0],
                material           = "MS",
                holes              = analysis["holes"],
                external_perimeter = analysis.get("external_perimeter", 0.0),
                internal_perimeter = analysis.get("internal_perimeter", 0.0),
                total_perimeter    = analysis["perimeter"],
                geometry_json      = parsed["geometry"],
            )
            db.add(part)
            db.commit()
            db.refresh(part)
            db_part_id = part.id
        except Exception as exc:
            db.rollback()
            print(f"[DB] Failed to store part: {exc}")
        finally:
            db.close()

        response = _analysis_response(parsed, analysis, file.filename, session_id)
        response["db_part_id"] = db_part_id
        return response

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


# ─────────────────────────────────────────────────────────────
# PART GEOMETRY (used when clicking a DB-loaded part)
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
        return part.geometry_json
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────
# UPLOAD DXF  (no project — session only, not persisted)
# ─────────────────────────────────────────────────────────────

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

        print(f"\n[UPLOAD] {file.filename} → session {session_id}")

        analysis = await _run_analysis(parsed)
        return _analysis_response(parsed, analysis, file.filename, session_id)

    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


# ─────────────────────────────────────────────────────────────
# DEBUG: snapped edges
# ─────────────────────────────────────────────────────────────

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


# ─────────────────────────────────────────────────────────────
# ANALYZE DXF (re-analyze from session)
# ─────────────────────────────────────────────────────────────

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
