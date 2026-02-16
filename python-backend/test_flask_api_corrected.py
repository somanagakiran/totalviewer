"""
Test the Flask API with hole detection - corrected version
"""

import requests
import json
import time

def test_api():
    """Test the Flask API with a simple DXF-like geometry"""
    
    # First, we need to simulate the upload process
    # The analyze endpoint expects a session_id, so we need to create one
    
    print("=== Testing Flask API ===")
    
    # Test the health endpoint first
    try:
        response = requests.get("http://127.0.0.1:8000/health")
        if response.status_code == 200:
            print(f"✅ Health check: {response.json()}")
        else:
            print(f"❌ Health check failed: {response.status_code}")
            return
    except:
        print("❌ Could not connect to health endpoint")
        return
    
    # Now test the analyze endpoint with proper session data
    # We'll simulate what the upload endpoint would return
    
    # Create test data that simulates what the DXF parser would return
    test_data = {
        "closed_contours": [],
        "bounding_box": {
            "minX": 0, "minY": 0, "maxX": 10, "maxY": 10,
            "width": 10, "height": 10
        },
        "raw_entities": [
            # Outer rectangle
            {"type": "LINE", "x1": 0, "y1": 0, "x2": 10, "y2": 0},
            {"type": "LINE", "x1": 10, "y1": 0, "x2": 10, "y2": 10},
            {"type": "LINE", "x1": 10, "y1": 10, "x2": 0, "y2": 10},
            {"type": "LINE", "x1": 0, "y1": 10, "x2": 0, "y2": 0},
            # Circle hole
            {"type": "CIRCLE", "center": [5, 5], "radius": 2}
        ]
    }
    
    # Test the analyze endpoint directly
    try:
        response = requests.post("http://127.0.0.1:8000/analyze", json=test_data)
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ API Response successful")
            print(f"Total holes: {result.get('total_holes', 0)}")
            print(f"Outer boundary area: {result.get('outer_boundary_area', 0)}")
            print(f"Hole details: {result.get('hole_details', [])}")
        else:
            print(f"❌ API Error: {response.status_code}")
            print(f"Response: {response.text}")
            
    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to Flask API. Make sure it's running on port 8000.")
        print("Run: python -m uvicorn main:app --reload --port 8000")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    print("Testing Flask API...")
    time.sleep(1)
    test_api()