"""
Test the Flask API by creating a proper session and testing hole detection
"""

import requests
import json
import time
import tempfile
import os

def create_test_dxf_with_holes():
    """Create a test DXF file with proper format that should be parseable"""
    # Create a simple DXF with rectangle and circle hole
    dxf_content = """0
SECTION
2
HEADER
9
$ACADVER
1
AC1015
0
ENDSEC
0
SECTION
2
ENTITIES
0
LINE
8
0
10
0
20
0
11
10
21
0
0
LINE
8
0
10
10
20
0
11
10
21
10
0
LINE
8
0
10
10
20
10
11
0
21
10
0
LINE
8
0
10
0
20
10
11
0
21
0
0
CIRCLE
8
0
10
5
20
5
40
2
0
ENDSEC
0
EOF
"""
    
    # Create a temporary DXF file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.dxf', delete=False) as f:
        f.write(dxf_content)
        return f.name

def test_session_workflow():
    """Test the complete upload -> analyze workflow"""
    
    print("=== Testing Flask API Session Workflow ===")
    
    # Test the health endpoint first
    try:
        response = requests.get("http://127.0.0.1:8000/health")
        if response.status_code == 200:
            print(f" Health check: {response.json()}")
        else:
            print(f" Health check failed: {response.status_code}")
            return
    except:
        print(" Could not connect to health endpoint")
        return
    
    # Create a test DXF file
    dxf_path = create_test_dxf_with_holes()
    
    try:
        # Step 1: Upload the DXF file
        print("\n1. Uploading DXF file...")
        with open(dxf_path, 'rb') as f:
            files = {'file': f}
            response = requests.post("http://127.0.0.1:8000/upload", files=files)
        
        if response.status_code != 200:
            print(f" Upload failed: {response.status_code}")
            print(f"Response: {response.text}")
            return
        
        upload_result = response.json()
        session_id = upload_result['session_id']
        print(f" Upload successful, session_id: {session_id}")
        print(f"   Entities found: {upload_result.get('entities', 0)}")
        print(f"   Holes detected on upload: {upload_result.get('total_holes', 0)}")
        
        # Let's examine what was parsed
        print(f"   Geometry items: {len(upload_result.get('geometry', []))}")
        
        # Step 2: Analyze the uploaded file
        print("\n2. Analyzing uploaded file...")
        analyze_data = {"session_id": session_id}
        response = requests.post("http://127.0.0.1:8000/analyze", json=analyze_data)
        
        if response.status_code == 200:
            result = response.json()
            print(f" Analysis successful")
            print(f"   Total holes: {result.get('total_holes', 0)}")
            print(f"   Outer boundary area: {result.get('outer_boundary_area', 0)}")
            print(f"   Hole details: {len(result.get('hole_details', []))} holes")
            for i, hole in enumerate(result.get('hole_details', [])):
                print(f"     Hole {i+1}: {hole.get('type', 'unknown')} - area: {hole.get('area', 0):.2f}")
        else:
            print(f" Analysis failed: {response.status_code}")
            print(f"Response: {response.text}")
            
        # Step 3: Test debug endpoints
        print("\n3. Testing debug endpoints...")
        response = requests.get(f"http://127.0.0.1:8000/debug/edges?session_id={session_id}")
        if response.status_code == 200:
            debug_result = response.json()
            print(f" Debug edges: {debug_result.get('count', 0)} edges found")
            edges = debug_result.get('edges', [])
            print(f"   Sample edges (first 5):")
            for i, edge in enumerate(edges[:5]):
                print(f"     Edge {i+1}: {edge}")
        else:
            print(f" Debug edges failed: {response.status_code}")
            
    except requests.exceptions.ConnectionError:
        print(" Could not connect to Flask API. Make sure it's running on port 8000.")
        print("Run: python -m uvicorn main:app --reload --port 8000")
    except Exception as e:
        print(f" Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Clean up temp file
        if os.path.exists(dxf_path):
            os.unlink(dxf_path)

if __name__ == "__main__":
    print("Testing Flask API session workflow...")
    time.sleep(1)
    test_session_workflow()