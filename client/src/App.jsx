import { useRef } from "react";
import * as THREE from "three";
import { DXFLoader } from "three-dxf";

function App() {
  const viewerRef = useRef();

  const handleFile = (e) => {
    const file = e.target.files[0];
    const reader = new FileReader();

    reader.onload = function (event) {
      const data = event.target.result;

      const scene = new THREE.Scene();
      const camera = new THREE.OrthographicCamera(
        -500,
        500,
        500,
        -500,
        1,
        1000
      );

      const renderer = new THREE.WebGLRenderer({ antialias: true });
      renderer.setSize(800, 500);
      viewerRef.current.innerHTML = "";
      viewerRef.current.appendChild(renderer.domElement);

      const loader = new DXFLoader();
      const dxf = loader.parse(data);

      scene.add(dxf);

      camera.position.z = 100;

      const animate = function () {
        requestAnimationFrame(animate);
        renderer.render(scene, camera);
      };

      animate();
    };

    reader.readAsText(file);
  };

  return (
    <div style={{ padding: 20 }}>
      <h1>Total Viewer</h1>

      <input type="file" accept=".dxf" onChange={handleFile} />

      <div
        ref={viewerRef}
        style={{
          marginTop: 20,
          border: "1px solid #ccc",
          width: 800,
          height: 500,
        }}
      ></div>
    </div>
  );
}

export default App;
