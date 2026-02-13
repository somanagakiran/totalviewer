from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import tempfile
import os

from engine.dxf_parser import parse_dxf
from engine.geometry_analyzer import analyze_geometry

app = FastAPI(title="Total Viewer — Python Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def home():
    return {"status": "Total Viewer Python Backend Running"}


@app.get("/health")
def health():
    return {"status": "ok"}


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

        analysis = analyze_geometry(
            parsed["closed_contours"],
            parsed["bounding_box"],
        )

        return {
            "fileName": file.filename,
            "entities": parsed["entity_count"],
            "holes": analysis["holes"],
            "perimeter": analysis["perimeter"],
            "outer_boundary_area": analysis["outer_boundary_area"],
            "geometry": parsed["geometry"],
            "bounding_box": parsed["bounding_box"],
            "units": parsed["units"],
            "layers": parsed["layers"],
        }

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)
