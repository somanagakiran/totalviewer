import { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import './DXFViewer.css';

// ═══════════════════════════════════════════════════════════════════════════════
// ACI COLOR TABLE — AutoCAD Color Index → hex
// Python backend sends entity.color as an ACI integer (0-256)
// ═══════════════════════════════════════════════════════════════════════════════
const ACI = [
  0xffffff,0xff0000,0xffff00,0x00ff00,0x00ffff,0x0000ff,0xff00ff,0xffffff,
  0x414141,0x808080,0xff0000,0xff7f7f,0xbf0000,0xbf5f5f,0x800000,0x804040,
  0xff3f00,0xff9f7f,0xbf2f00,0xbf775f,0x801f00,0x804f40,0xff7f00,0xffbf7f,
  0xbf5f00,0xbf8f5f,0x803f00,0x805f40,0xffbf00,0xffdf7f,0xbf8f00,0xbfaf5f,
  0x805f00,0x807040,0xffff00,0xffff7f,0xbfbf00,0xbfbf5f,0x808000,0x808040,
  0xbfff00,0xdfff7f,0x8fbf00,0xafbf5f,0x608000,0x708040,0x7fff00,0xbfff7f,
  0x5fbf00,0x8fbf5f,0x3f8000,0x608040,0x3fff00,0x9fff7f,0x2fbf00,0x77bf5f,
  0x1f8000,0x508040,0x00ff00,0x7fff7f,0x00bf00,0x5fbf5f,0x008000,0x408040,
  0x00ff3f,0x7fff9f,0x00bf2f,0x5fbf77,0x00801f,0x408050,0x00ff7f,0x7fffbf,
  0x00bf5f,0x5fbf8f,0x00803f,0x408060,0x00ffbf,0x7fffdf,0x00bf8f,0x5fbfaf,
  0x00805f,0x408070,0x00ffff,0x7fffff,0x00bfbf,0x5fbfbf,0x008080,0x408080,
  0x00bfff,0x7fdfff,0x008fbf,0x5fafbf,0x005f80,0x407080,0x007fff,0x7fbfff,
  0x005fbf,0x5f8fbf,0x003f80,0x406080,0x003fff,0x7f9fff,0x002fbf,0x5f77bf,
  0x001f80,0x405080,0x0000ff,0x7f7fff,0x0000bf,0x5f5fbf,0x000080,0x404080,
  0x3f00ff,0x9f7fff,0x2f00bf,0x775fbf,0x1f0080,0x504080,0x7f00ff,0xbf7fff,
  0x5f00bf,0x8f5fbf,0x3f0080,0x604080,0xbf00ff,0xdf7fff,0x8f00bf,0xaf5fbf,
  0x5f0080,0x704080,0xff00ff,0xff7fff,0xbf00bf,0xbf5fbf,0x800080,0x804080,
  0xff00bf,0xff7fdf,0xbf008f,0xbf5faf,0x800060,0x804070,0xff007f,0xff7fbf,
  0xbf005f,0xbf5f8f,0x800040,0x804060,0xff003f,0xff7f9f,0xbf002f,0xbf5f77,
  0x800020,0x804050,0xff0000,0xff7f7f,0xbf0000,0xbf5f5f,0x800000,0x804040,
  0x4c4c4c,0x5f5f5f,0x717171,0x838383,0x969696,0xa8a8a8,0xbababa,0xcccccc,
  0xdfdfdf,0xf1f1f1,0xffffff,0x000000,
];

function aciToHex(index) {
  // 0 = by block, 7 = white, 256 = by layer → all render as white/default
  if (index == null || index === 0 || index === 7)  return 0xffffff;
  if (index === 256) return 0x4fc3f7; // by-layer fallback → CAD cyan
  return ACI[index] ?? 0x4fc3f7;
}

// ═══════════════════════════════════════════════════════════════════════════════
// BUILD THREE.JS GROUP FROM PYTHON GEOMETRY ARRAY
//
// Python backend sends pre-tessellated geometry:
//   { type, points: [[x,y], ...], color: <aciIndex>, closed: bool, layer: str }
//
// All curves (arcs, circles, splines, ellipses, bulge arcs) are already
// sampled to point arrays by the Python engine — no client-side math needed.
// ═══════════════════════════════════════════════════════════════════════════════
function buildGroupFromGeometry(geometry) {
  const group = new THREE.Group();
  let rendered = 0;

  for (const item of geometry) {
    const pts = item.points;
    if (!pts || pts.length < 2) continue;

    const color = aciToHex(item.color);
    const pts3  = pts.map(p => new THREE.Vector3(p[0], p[1], 0));
    const geo   = new THREE.BufferGeometry().setFromPoints(pts3);
    const mat   = new THREE.LineBasicMaterial({ color });
    const line  = item.closed
      ? new THREE.LineLoop(geo, mat)
      : new THREE.Line(geo, mat);

    group.add(line);
    rendered++;
  }

  console.info(`[DXF] Rendered ${rendered} / ${geometry.length} geometry items`);
  return group;
}

// ═══════════════════════════════════════════════════════════════════════════════
// DISPOSE — free Three.js GPU memory
// ═══════════════════════════════════════════════════════════════════════════════
function disposeGroup(group) {
  group.traverse(child => {
    child.geometry?.dispose();
    if (child.material) {
      Array.isArray(child.material)
        ? child.material.forEach(m => m.dispose())
        : child.material.dispose();
    }
  });
}

// ═══════════════════════════════════════════════════════════════════════════════
// REACT COMPONENT
// Props:
//   geometry     — array of geometry items from Python backend (or null)
//   isLoading    — show loading spinner
//   error        — error string to display
//   onStatusChange — status bar callback
// ═══════════════════════════════════════════════════════════════════════════════
export default function DXFViewer({ geometry, isLoading, error, onStatusChange }) {
  const mountRef       = useRef(null);
  const threeRef       = useRef(null);
  const geoGroupRef    = useRef(null);
  const baseFrustumRef = useRef(200);
  const stateRef       = useRef({
    isPanning:   false,
    lastMouse:   { x: 0, y: 0 },
    frustumSize: 200,
  });

  const [zoomPct, setZoomPct] = useState(100);
  const [hasGeo,  setHasGeo]  = useState(false);

  // ── 1. Init Three.js renderer once ────────────────────────────────────────
  useEffect(() => {
    const mount = mountRef.current;
    if (!mount) return;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x141920);

    const W   = mount.clientWidth  || 800;
    const H   = mount.clientHeight || 600;
    const fs  = 200;
    const asp = W / H;

    const camera = new THREE.OrthographicCamera(
      (fs * asp) / -2, (fs * asp) / 2,
       fs        /  2,  fs        / -2,
      -1e5, 1e5
    );
    camera.position.set(0, 0, 10);

    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setSize(W, H);
    renderer.domElement.style.cssText =
      'position:absolute;top:0;left:0;width:100%;height:100%;display:block;';
    mount.appendChild(renderer.domElement);

    stateRef.current.frustumSize = fs;
    threeRef.current = { scene, camera, renderer };

    let animId;
    const animate = () => {
      animId = requestAnimationFrame(animate);
      renderer.render(scene, camera);
    };
    animate();

    const ro = new ResizeObserver(() => {
      const w = mount.clientWidth, h = mount.clientHeight;
      if (!w || !h) return;
      const a   = w / h;
      const fs2 = stateRef.current.frustumSize;
      camera.left   = (fs2 * a) / -2;
      camera.right  = (fs2 * a) /  2;
      camera.top    =  fs2      /  2;
      camera.bottom =  fs2      / -2;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
    });
    ro.observe(mount);

    return () => {
      cancelAnimationFrame(animId);
      ro.disconnect();
      renderer.dispose();
      if (mount.contains(renderer.domElement)) mount.removeChild(renderer.domElement);
      threeRef.current = null;
    };
  }, []);

  // ── 2. Render geometry when Python API response arrives ────────────────────
  useEffect(() => {
    const three = threeRef.current;
    if (!three) return;
    const { scene } = three;

    // Clear previous drawing
    if (geoGroupRef.current) {
      scene.remove(geoGroupRef.current);
      disposeGroup(geoGroupRef.current);
      geoGroupRef.current = null;
      setHasGeo(false);
    }

    if (!geometry?.length) return;

    onStatusChange?.('Rendering geometry…');

    const tid = setTimeout(() => {
      try {
        const group = buildGroupFromGeometry(geometry);
        scene.add(group);
        geoGroupRef.current = group;
        setHasGeo(true);
        fitToScreen(group);
        onStatusChange?.(`Rendered ${geometry.length} entities`);
      } catch (err) {
        console.error('[DXF] Render error:', err);
        onStatusChange?.('Render error — ' + err.message);
      }
    }, 10);

    return () => clearTimeout(tid);
  }, [geometry]); // eslint-disable-line react-hooks/exhaustive-deps

  // ── 3. Wheel zoom + drag pan ───────────────────────────────────────────────
  useEffect(() => {
    const mount = mountRef.current;
    if (!mount) return;

    const onWheel = (e) => {
      e.preventDefault();
      const three = threeRef.current;
      if (!three) return;
      const { camera } = three;

      const rect   = mount.getBoundingClientRect();
      const mx     = ((e.clientX - rect.left) / rect.width)  * 2 - 1;
      const my     = -(((e.clientY - rect.top) / rect.height) * 2 - 1);
      const factor = e.deltaY < 0 ? 0.85 : 1 / 0.85;
      const oldFs  = stateRef.current.frustumSize;
      const newFs  = Math.max(1e-4, Math.min(1e8, oldFs * factor));
      stateRef.current.frustumSize = newFs;

      const W = mount.clientWidth, H = mount.clientHeight, asp = W / H;

      // Keep the world point under the cursor stationary
      const wx1 = camera.position.x + mx * (oldFs * asp) / 2;
      const wy1 = camera.position.y + my *  oldFs        / 2;

      camera.left   = (newFs * asp) / -2;
      camera.right  = (newFs * asp) /  2;
      camera.top    =  newFs        /  2;
      camera.bottom =  newFs        / -2;
      camera.updateProjectionMatrix();

      const wx2 = camera.position.x + mx * (newFs * asp) / 2;
      const wy2 = camera.position.y + my *  newFs        / 2;

      camera.position.x += wx1 - wx2;
      camera.position.y += wy1 - wy2;

      setZoomPct(Math.round((baseFrustumRef.current / newFs) * 100));
    };

    const onMouseDown = (e) => {
      if (e.button === 0 || e.button === 1) {
        stateRef.current.isPanning = true;
        stateRef.current.lastMouse = { x: e.clientX, y: e.clientY };
        mount.style.cursor = 'grabbing';
      }
    };

    const onMouseMove = (e) => {
      if (!stateRef.current.isPanning || !threeRef.current) return;
      const { camera } = threeRef.current;
      const dx  = e.clientX - stateRef.current.lastMouse.x;
      const dy  = e.clientY - stateRef.current.lastMouse.y;
      stateRef.current.lastMouse = { x: e.clientX, y: e.clientY };

      const W   = mount.clientWidth, H = mount.clientHeight;
      const fs  = stateRef.current.frustumSize;
      const asp = W / H;
      camera.position.x -= dx * (fs * asp) / W;
      camera.position.y += dy *  fs        / H;
    };

    const onMouseUp = () => {
      stateRef.current.isPanning = false;
      mount.style.cursor = 'grab';
    };

    mount.addEventListener('wheel',      onWheel,     { passive: false });
    mount.addEventListener('mousedown',  onMouseDown);
    window.addEventListener('mousemove', onMouseMove);
    window.addEventListener('mouseup',   onMouseUp);

    return () => {
      mount.removeEventListener('wheel',      onWheel);
      mount.removeEventListener('mousedown',  onMouseDown);
      window.removeEventListener('mousemove', onMouseMove);
      window.removeEventListener('mouseup',   onMouseUp);
    };
  }, []);

  // ── 4. Fit-screen via custom event (TopBar button) ─────────────────────────
  useEffect(() => {
    const h = () => { if (geoGroupRef.current) fitToScreen(geoGroupRef.current); };
    window.addEventListener('dxf-fit-screen', h);
    return () => window.removeEventListener('dxf-fit-screen', h);
  }, []);

  // ── Fit to screen ──────────────────────────────────────────────────────────
  function fitToScreen(group) {
    const three = threeRef.current;
    const mount = mountRef.current;
    if (!three || !mount) return;
    const { camera } = three;

    group.updateWorldMatrix(true, true);
    const box = new THREE.Box3().setFromObject(group);
    if (box.isEmpty()) return;

    const size   = box.getSize(new THREE.Vector3());
    const center = box.getCenter(new THREE.Vector3());
    const W = mount.clientWidth, H = mount.clientHeight, asp = W / H;

    const M   = 1.12; // 12% margin
    let newFs = size.y * M;
    if ((size.x * M) / asp > newFs) newFs = (size.x * M) / asp;
    if (!isFinite(newFs) || newFs <= 0) newFs = 200;

    stateRef.current.frustumSize = newFs;
    baseFrustumRef.current       = newFs;

    camera.left   = (newFs * asp) / -2;
    camera.right  = (newFs * asp) /  2;
    camera.top    =  newFs        /  2;
    camera.bottom =  newFs        / -2;
    camera.position.set(center.x, center.y, 10);
    camera.updateProjectionMatrix();
    setZoomPct(100);
  }

  // ── Zoom step buttons ──────────────────────────────────────────────────────
  function applyZoom(factor) {
    const three = threeRef.current;
    const mount = mountRef.current;
    if (!three || !mount) return;
    const { camera } = three;
    const newFs = Math.max(1e-4, Math.min(1e8, stateRef.current.frustumSize * factor));
    stateRef.current.frustumSize = newFs;
    const asp = mount.clientWidth / mount.clientHeight;
    camera.left   = (newFs * asp) / -2;
    camera.right  = (newFs * asp) /  2;
    camera.top    =  newFs        /  2;
    camera.bottom =  newFs        / -2;
    camera.updateProjectionMatrix();
    setZoomPct(Math.round((baseFrustumRef.current / newFs) * 100));
  }

  // ── JSX ────────────────────────────────────────────────────────────────────
  return (
    <div className="dxf-viewer">
      <div ref={mountRef} className="dxf-mount" style={{ cursor: 'grab' }} />

      {/* Empty state */}
      {!hasGeo && !isLoading && !error && (
        <div className="viewer-overlay empty-overlay">
          <div className="empty-box">
            <svg width="56" height="56" viewBox="0 0 24 24" fill="none" stroke="#388bfd" strokeWidth="1">
              <rect x="3" y="3" width="18" height="18" rx="1"/>
              <line x1="3"  y1="9"  x2="21" y2="9"  strokeOpacity="0.4"/>
              <line x1="3"  y1="15" x2="21" y2="15" strokeOpacity="0.4"/>
              <line x1="9"  y1="3"  x2="9"  y2="21" strokeOpacity="0.4"/>
              <line x1="15" y1="3"  x2="15" y2="21" strokeOpacity="0.4"/>
            </svg>
            <div className="empty-title">No Drawing Loaded</div>
            <div className="empty-sub">
              Click <strong>Open DXF</strong> or drag &amp; drop a .DXF file
            </div>
          </div>
        </div>
      )}

      {/* Loading */}
      {isLoading && (
        <div className="viewer-overlay">
          <div className="loading-box">
            <div className="loader-ring" />
            <div className="loader-text">Processing DXF File</div>
            <div className="loader-sub">Python engine parsing geometry…</div>
          </div>
        </div>
      )}

      {/* Error */}
      {error && !isLoading && (
        <div className="viewer-overlay error-overlay">
          <div className="error-box">
            <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="#f85149" strokeWidth="1.5">
              <circle cx="12" cy="12" r="10"/>
              <line x1="12" y1="8"  x2="12" y2="13"/>
              <circle cx="12" cy="16.5" r="0.5" fill="#f85149"/>
            </svg>
            <div className="error-title">Error</div>
            <div className="error-msg">{error}</div>
          </div>
        </div>
      )}

      {/* Zoom / fit controls */}
      <div className="viewer-controls">
        <button className="ctrl-btn" onClick={() => applyZoom(0.75)} title="Zoom In">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
            <circle cx="11" cy="11" r="8"/>
            <line x1="21" y1="21" x2="16.65" y2="16.65"/>
            <line x1="11" y1="8"  x2="11"    y2="14"/>
            <line x1="8"  y1="11" x2="14"    y2="11"/>
          </svg>
        </button>
        <div className="ctrl-zoom">{zoomPct}%</div>
        <button className="ctrl-btn" onClick={() => applyZoom(1 / 0.75)} title="Zoom Out">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
            <circle cx="11" cy="11" r="8"/>
            <line x1="21" y1="21" x2="16.65" y2="16.65"/>
            <line x1="8"  y1="11" x2="14"    y2="11"/>
          </svg>
        </button>
        <div className="ctrl-divider" />
        <button
          className="ctrl-btn"
          onClick={() => geoGroupRef.current && fitToScreen(geoGroupRef.current)}
          title="Fit to Screen"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M8 3H5a2 2 0 00-2 2v3m18 0V5a2 2 0 00-2-2h-3m0 18h3a2 2 0 002-2v-3M3 16v3a2 2 0 002 2h3"/>
          </svg>
        </button>
      </div>

      {hasGeo && (
        <div className="viewer-hint">
          Scroll to zoom &nbsp;·&nbsp; Drag to pan
        </div>
      )}
    </div>
  );
}
