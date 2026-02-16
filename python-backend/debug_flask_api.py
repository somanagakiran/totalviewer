"""
Debug the Flask API analysis process
"""

import requests
import json
import time
import tempfile
import os

def create_simple_test_dxf():
    """Create a very simple test DXF file"""
    # Create a simple DXF with just a rectangle and circle
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

def debug_analysis():
    """Debug the analysis process step by step"""
    
    print("=== Debugging Flask API Analysis ===")
    
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
    
    # Create a test DXF file
    dxf_path = create_simple_test_dxf()
    
    try:
        # Step 1: Upload the DXF file
        print("\n1. Uploading DXF file...")
        with open(dxf_path, 'rb') as f:
            files = {'file': f}
            response = requests.post("http://127.0.0.1:8000/upload", files=files)
        
        if response.status_code != 200:
            print(f"❌ Upload failed: {response.status_code}")
            print(f"Response: {response.text}")
            return
        
        upload_result = response.json()
        session_id = upload_result['session_id']
        print(f"✅ Upload successful, session_id: {session_id}")
        
        # Let's examine the parsed data in detail
        print(f"\n2. Parsed data details:")
        print(f"   Entities: {upload_result.get('entities', 0)}")
        print(f"   Geometry items: {len(upload_result.get('geometry', []))}")
        print(f"   Bounding box: {upload_result.get('bounding_box', {})}")
        print(f"   Units: {upload_result.get('units', 'unknown')}")
        print(f"   Layers: {upload_result.get('layers', [])}")
        
        # Show first few geometry items
        geometry = upload_result.get('geometry', [])
        print(f"   First 3 geometry items:")
        for i, item in enumerate(geometry[:3]):
            print(f"     Item {i+1}: {item}")
        
        # Step 3: Test debug endpoints
        print(f"\n3. Testing debug endpoints...")
        response = requests.get(f"http://127.0.0.1:8000/debug/edges?session_id={session_id}")
        if response.status_code == 200:
            debug_result = response.json()
            print(f"✅ Debug edges: {debug_result.get('count', 0)} edges found")
            edges = debug_result.get('edges', [])
            print(f"   First 5 edges:")
            for i, edge in enumerate(edges[:5]):
                print(f"     Edge {i+1}: {edge}")
        else:
            print(f"❌ Debug edges failed: {response.status_code}")
        
        # Step 4: Analyze the uploaded file
        print(f"\n4. Analyzing uploaded file...")
        analyze_data = {"session_id": session_id}
        response = requests.post("http://127.0.0.1:8000/analyze", json=analyze_data)
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Analysis successful")
            print(f"   Total holes: {result.get('total_holes', 0)}")
            print(f"   Outer boundary area: {result.get('outer_boundary_area', 0)}")
            print(f"   Hole details: {len(result.get('hole_details', []))} holes")
            for i, hole in enumerate(result.get('hole_details', [])):
                print(f"     Hole {i+1}: {hole.get('type', 'unknown')} - area: {hole.get('area', 0):.2f}")
        else:
            print(f"❌ Analysis failed: {response.status_code}")
            print(f"Response: {response.text}")
            
    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to Flask API. Make sure it's running on port 8000.")
        print("Run: python -m uvicorn main:app --reload --port 8000")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Clean up temp file
        if os.path.exists(dxf_path):
            os.unlink(dxf_path)

if __name__ == "__main__":
    print("Debugging Flask API analysis process...")
    time.sleep(1)
    debug_analysis()