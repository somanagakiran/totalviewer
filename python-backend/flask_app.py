"""
Flask API for Advanced Hole Detection

This module provides Flask endpoints for the enhanced hole detection system.
It integrates with the existing FastAPI backend while providing additional
capabilities for comprehensive hole detection.
"""

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os
import tempfile
import uuid
from typing import Dict, Any, List

# Import the hole detector
from engine.hole_detector import detect_holes_from_entities, count_holes_by_type
from engine.dxf_parser import parse_dxf

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Session storage for parsed DXF data
SESSIONS: Dict[str, Dict[str, Any]] = {}

@app.route('/')
def home():
    """Health check endpoint"""
    return jsonify({
        "status": "Advanced Hole Detection API Running",
        "version": "1.0.0",
        "features": [
            "Comprehensive hole detection",
            "Shape classification (circle, rectangle, triangle, slot, polygon)",
            "Mixed entity support (LINE, ARC, CIRCLE, LWPOLYLINE, POLYLINE, SPLINE, ELLIPSE)",
            "Non-PEDIT joined geometry handling",
            "Tolerance-based endpoint snapping"
        ]
    })

@app.route('/health')
def health():
    """Detailed health check"""
    return jsonify({
        "status": "healthy",
        "sessions_active": len(SESSIONS),
        "api_version": "1.0.0"
    })

@app.route('/upload-dxf', methods=['POST'])
def upload_dxf():
    """
    Upload and parse DXF file with advanced hole detection
    
    Request:
        - Form data with 'file' field containing DXF file
        
    Response:
        - session_id: Unique session identifier
        - hole_detection: Comprehensive hole analysis results
        - geometry: Parsed geometry data
        - file_info: File metadata
    """
    if 'file' not in request.files:
        return jsonify({"error": "No file provided"}), 400
    
    file = request.files['file']
    if not file.filename.lower().endswith('.dxf'):
        return jsonify({"error": "Only DXF files are supported"}), 400
    
    # Save temporary file
    with tempfile.NamedTemporaryFile(delete=False, suffix='.dxf') as tmp_file:
        file.save(tmp_file.name)
        tmp_path = tmp_file.name
    
    try:
        # Parse DXF file
        parsed_data = parse_dxf(tmp_path)
        
        # Create session
        session_id = str(uuid.uuid4())
        
        # Store session data
        SESSIONS[session_id] = {
            "parsed_data": parsed_data,
            "created_at": uuid.uuid4().time,
            "filename": file.filename
        }
        
        # Perform advanced hole detection
        hole_results = detect_holes_from_entities(
            parsed_data.get("geometry", []),
            tolerance=0.01,
            min_area=0.1
        )
        
        # Count holes by type
        hole_type_counts = count_holes_by_type(hole_results.get("hole_details", []))
        
        return jsonify({
            "session_id": session_id,
            "file_info": {
                "filename": file.filename,
                "entities": parsed_data.get("entity_count", 0),
                "units": parsed_data.get("units", "unknown"),
                "layers": parsed_data.get("layers", [])
            },
            "hole_detection": {
                **hole_results,
                "hole_type_counts": hole_type_counts,
                "summary": {
                    "total_holes": hole_results.get("total_holes", 0),
                    "by_type": hole_type_counts
                }
            },
            "geometry": parsed_data.get("geometry", []),
            "bounding_box": parsed_data.get("bounding_box", {})
        })
        
    except Exception as e:
        return jsonify({"error": f"Failed to process DXF file: {str(e)}"}), 500
    
    finally:
        # Clean up temporary file
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)

@app.route('/analyze-holes/<session_id>', methods=['POST'])
def analyze_holes(session_id):
    """
    Analyze holes for an existing session with custom parameters
    
    Request Body (JSON):
        - tolerance: Snap tolerance for endpoint matching (default: 0.01)
        - min_area: Minimum area for valid holes (default: 0.1)
        
    Response:
        - Enhanced hole detection results
    """
    if session_id not in SESSIONS:
        return jsonify({"error": "Session not found"}), 404
    
    # Get custom parameters
    data = request.get_json() or {}
    tolerance = float(data.get('tolerance', 0.01))
    min_area = float(data.get('min_area', 0.1))
    
    session_data = SESSIONS[session_id]
    geometry = session_data["parsed_data"].get("geometry", [])
    
    try:
        # Perform advanced hole detection with custom parameters
        hole_results = detect_holes_from_entities(
            geometry,
            tolerance=tolerance,
            min_area=min_area
        )
        
        # Count holes by type
        hole_type_counts = count_holes_by_type(hole_results.get("hole_details", []))
        
        return jsonify({
            "session_id": session_id,
            "parameters": {
                "tolerance": tolerance,
                "min_area": min_area
            },
            "hole_detection": {
                **hole_results,
                "hole_type_counts": hole_type_counts,
                "summary": {
                    "total_holes": hole_results.get("total_holes", 0),
                    "by_type": hole_type_counts
                }
            }
        })
        
    except Exception as e:
        return jsonify({"error": f"Analysis failed: {str(e)}"}), 500

@app.route('/sessions', methods=['GET'])
def list_sessions():
    """List active sessions"""
    return jsonify({
        "active_sessions": list(SESSIONS.keys()),
        "count": len(SESSIONS)
    })

@app.route('/sessions/<session_id>', methods=['DELETE'])
def delete_session(session_id):
    """Delete a session"""
    if session_id in SESSIONS:
        del SESSIONS[session_id]
        return jsonify({"message": "Session deleted successfully"})
    else:
        return jsonify({"error": "Session not found"}), 404

@app.route('/hole-types', methods=['GET'])
def get_hole_types():
    """Get information about supported hole types"""
    return jsonify({
        "supported_types": [
            "circle",
            "rectangle", 
            "triangle",
            "slot",
            "polygon_4", "polygon_5", "polygon_6", "polygon_7", "polygon_8",
            "irregular"
        ],
        "classification_method": "Geometric analysis using area, perimeter, vertex count, and aspect ratio"
    })

@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Endpoint not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({"error": "Internal server error"}), 500

if __name__ == '__main__':
    # Run the Flask app
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('DEBUG', 'False').lower() == 'true'
    
    print(f"Starting Advanced Hole Detection API on port {port}")
    print(f"Debug mode: {debug}")
    print("Available endpoints:")
    print("  GET  / - Health check")
    print("  GET  /health - Detailed health check")
    print("  POST /upload-dxf - Upload and analyze DXF file")
    print("  POST /analyze-holes/<session_id> - Analyze holes with custom parameters")
    print("  GET  /sessions - List active sessions")
    print("  DELETE /sessions/<session_id> - Delete session")
    print("  GET  /hole-types - Get supported hole types")
    
    app.run(host='0.0.0.0', port=port, debug=debug)