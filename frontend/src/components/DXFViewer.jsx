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
export default function DXFViewer({ parts, selectedRowId, isLoading, error, onStatusChange }) {
  const mountRef       = useRef(null);
  const threeRef       = useRef(null);
  const geoGroupRef    = useRef(null);
  const baseFrustumRef = useRef(200);
  const stateRef       = useRef({
    isPanning:   false,
    lastMouse:   { x: 0, y: 0 },
    frustumSize: 200,
  });
  // Touch state for pinch-to-zoom + single-finger pan
  const touchRef = useRef({ dist: 0 });

  // Smooth zoom animation state
  const smoothZoomRef = useRef({
    targetFs: 200,    // frustum we're animating toward
    ndcX:     0,      // cursor NDC when scroll fired
    ndcY:     0,
    worldX:   0,      // world-space anchor under cursor
    worldY:   0,
    rafId:    null,
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

  // ── 2. Render all parts whenever the parts array changes ──────────────────
  useEffect(() => {
    const three = threeRef.current;
    if (!three) return;
    const { scene } = three;

    // Clear previous scene geometry
    if (geoGroupRef.current) {
      scene.remove(geoGroupRef.current);
      disposeGroup(geoGroupRef.current);
      geoGroupRef.current = null;
      setHasGeo(false);
    }

    if (!parts?.length) return;

    const visibleParts = selectedRowId
      ? parts.filter(p => p.id === selectedRowId)
      : parts;

    if (!visibleParts.length) return;

    onStatusChange?.('Rendering geometry…');

    const tid = setTimeout(() => {
      try {
        // Parent group holds all per-part sub-groups
        const parentGroup = new THREE.Group();
        let currentOffsetX = 0;
        let totalEntities  = 0;

        for (const part of visibleParts) {
          if (!part.geometry?.length) continue;

          const subGroup = buildGroupFromGeometry(part.geometry);

          // Compute raw bounding box (before offset) to determine spacing
          subGroup.updateWorldMatrix(true, true);
          const box = new THREE.Box3().setFromObject(subGroup);

          if (!box.isEmpty()) {
            const size    = box.getSize(new THREE.Vector3());
            // Dynamic gap: 15% of this part's width, minimum 20 units; 0 if only one part
            const spacing = visibleParts.length > 1 ? Math.max(20, size.x * 0.15) : 0;
            // Shift sub-group so its left edge aligns to currentOffsetX
            subGroup.position.x = currentOffsetX - box.min.x;
            currentOffsetX += size.x + spacing;
          }

          parentGroup.add(subGroup);
          totalEntities += part.geometry.length;
        }

        scene.add(parentGroup);
        geoGroupRef.current = parentGroup;
        setHasGeo(true);
        fitToScreen(parentGroup);
        onStatusChange?.(
          `Rendered ${totalEntities} entities · ${visibleParts.length} part(s)`
        );
      } catch (err) {
        console.error('[DXF] Render error:', err);
        onStatusChange?.('Render error — ' + err.message);
      }
    }, 10);

    return () => clearTimeout(tid);
  }, [parts, selectedRowId]); // eslint-disable-line react-hooks/exhaustive-deps

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
      const W = mount.clientWidth, H = mount.clientHeight, asp = W / H;
      const currFs = stateRef.current.frustumSize;

      // Zoom limits: 0.2× (zoom out) – 10× (zoom in) relative to fit frustum
      const base    = baseFrustumRef.current || currFs;
      const MIN_FS  = base / 10;
      const MAX_FS  = base * 5;

      // Accumulate toward target so rapid scrolls don't reset the easing
      const prevTarget = smoothZoomRef.current.rafId
        ? smoothZoomRef.current.targetFs
        : currFs;
      const step      = e.deltaY < 0 ? 0.85 : 1 / 0.85;
      const newTarget = Math.max(MIN_FS, Math.min(MAX_FS, prevTarget * step));

      // Anchor: world point under cursor at this moment
      smoothZoomRef.current.targetFs = newTarget;
      smoothZoomRef.current.ndcX     = mx;
      smoothZoomRef.current.ndcY     = my;
      smoothZoomRef.current.worldX   = camera.position.x + mx * (currFs * asp) / 2;
      smoothZoomRef.current.worldY   = camera.position.y + my *  currFs        / 2;

      if (!smoothZoomRef.current.rafId) {
        const tick = () => {
          const t = threeRef.current, m = mountRef.current;
          if (!t || !m) { smoothZoomRef.current.rafId = null; return; }
          const { camera: cam } = t;

          const cur  = stateRef.current.frustumSize;
          const tgt  = smoothZoomRef.current.targetFs;
          const diff = tgt - cur;
          const done = Math.abs(diff) < Math.abs(tgt) * 0.0008;
          const next = done ? tgt : cur + diff * 0.22;

          stateRef.current.frustumSize = next;
          const a = m.clientWidth / m.clientHeight;
          cam.left   = (next * a) / -2;
          cam.right  = (next * a) /  2;
          cam.top    =  next      /  2;
          cam.bottom =  next      / -2;
          cam.updateProjectionMatrix();

          // Keep anchor world point fixed under cursor
          const { ndcX, ndcY, worldX, worldY } = smoothZoomRef.current;
          const cx = cam.position.x + ndcX * (next * a) / 2;
          const cy = cam.position.y + ndcY *  next      / 2;
          cam.position.x += worldX - cx;
          cam.position.y += worldY - cy;

          setZoomPct(Math.round((baseFrustumRef.current / next) * 100));

          if (done) {
            smoothZoomRef.current.rafId = null;
          } else {
            smoothZoomRef.current.rafId = requestAnimationFrame(tick);
          }
        };
        smoothZoomRef.current.rafId = requestAnimationFrame(tick);
      }
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

    // ── Touch: single-finger pan + two-finger pinch-zoom ──────────────────
    const onTouchStart = (e) => {
      if (e.touches.length === 1) {
        stateRef.current.isPanning = true;
        stateRef.current.lastMouse = { x: e.touches[0].clientX, y: e.touches[0].clientY };
      } else if (e.touches.length === 2) {
        stateRef.current.isPanning = false;
        const dx = e.touches[0].clientX - e.touches[1].clientX;
        const dy = e.touches[0].clientY - e.touches[1].clientY;
        touchRef.current.dist = Math.hypot(dx, dy);
      }
    };

    const onTouchMove = (e) => {
      e.preventDefault(); // block browser scroll / native pinch-zoom
      const three = threeRef.current;
      if (!three) return;
      const { camera } = three;

      if (e.touches.length === 1 && stateRef.current.isPanning) {
        const dx = e.touches[0].clientX - stateRef.current.lastMouse.x;
        const dy = e.touches[0].clientY - stateRef.current.lastMouse.y;
        stateRef.current.lastMouse = { x: e.touches[0].clientX, y: e.touches[0].clientY };
        const W   = mount.clientWidth, H = mount.clientHeight;
        const fs  = stateRef.current.frustumSize;
        const asp = W / H;
        camera.position.x -= dx * (fs * asp) / W;
        camera.position.y += dy * fs / H;
      } else if (e.touches.length === 2) {
        const dx   = e.touches[0].clientX - e.touches[1].clientX;
        const dy   = e.touches[0].clientY - e.touches[1].clientY;
        const dist = Math.hypot(dx, dy);
        // Clamp factor to avoid jumps when fingers first separate
        const factor = touchRef.current.dist > 0
          ? touchRef.current.dist / dist
          : 1;
        touchRef.current.dist = dist;
        const oldFs = stateRef.current.frustumSize;
        const newFs = Math.max(1e-4, Math.min(1e8, oldFs * factor));
        stateRef.current.frustumSize = newFs;
        const W   = mount.clientWidth, H = mount.clientHeight, asp = W / H;
        camera.left   = (newFs * asp) / -2;
        camera.right  = (newFs * asp) /  2;
        camera.top    =  newFs        /  2;
        camera.bottom =  newFs        / -2;
        camera.updateProjectionMatrix();
        setZoomPct(Math.round((baseFrustumRef.current / newFs) * 100));
      }
    };

    const onTouchEnd = (e) => {
      if (e.touches.length === 0) {
        stateRef.current.isPanning = false;
        touchRef.current.dist = 0;
      } else if (e.touches.length === 1) {
        // Dropped from 2-finger to 1-finger — restart pan tracking
        stateRef.current.isPanning = true;
        stateRef.current.lastMouse = { x: e.touches[0].clientX, y: e.touches[0].clientY };
      }
    };

    const onDblClick = () => {
      if (geoGroupRef.current) fitToScreen(geoGroupRef.current);
    };

    mount.addEventListener('wheel',      onWheel,      { passive: false });
    mount.addEventListener('mousedown',  onMouseDown);
    mount.addEventListener('dblclick',   onDblClick);
    mount.addEventListener('touchstart', onTouchStart, { passive: false });
    mount.addEventListener('touchmove',  onTouchMove,  { passive: false });
    mount.addEventListener('touchend',   onTouchEnd);
    window.addEventListener('mousemove', onMouseMove);
    window.addEventListener('mouseup',   onMouseUp);

    return () => {
      mount.removeEventListener('wheel',      onWheel);
      mount.removeEventListener('mousedown',  onMouseDown);
      mount.removeEventListener('dblclick',   onDblClick);
      mount.removeEventListener('touchstart', onTouchStart);
      mount.removeEventListener('touchmove',  onTouchMove);
      mount.removeEventListener('touchend',   onTouchEnd);
      window.removeEventListener('mousemove', onMouseMove);
      window.removeEventListener('mouseup',   onMouseUp);
      if (smoothZoomRef.current.rafId) {
        cancelAnimationFrame(smoothZoomRef.current.rafId);
        smoothZoomRef.current.rafId = null;
      }
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

    stateRef.current.frustumSize   = newFs;
    baseFrustumRef.current         = newFs;
    smoothZoomRef.current.targetFs = newFs;  // keep easing in sync

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
    const base  = baseFrustumRef.current || stateRef.current.frustumSize;
    const newFs = Math.max(base / 10, Math.min(base * 5, stateRef.current.frustumSize * factor));
    stateRef.current.frustumSize   = newFs;
    smoothZoomRef.current.targetFs = newFs;   // keep easing in sync
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
          Scroll to zoom &nbsp;·&nbsp; Drag to pan &nbsp;·&nbsp; Double-click to fit
        </div>
      )}
    </div>
  );
}
