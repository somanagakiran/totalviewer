import { useState, useCallback, useRef } from 'react';
import TopBar from './components/TopBar';
import LeftPanel from './components/LeftPanel';
import DXFViewer from './components/DXFViewer';
import StatusBar from './components/StatusBar';
import SummaryTable from './components/SummaryTable';
import './App.css';

// -------------------------------------------------------------
// POLYGON EXTRACTION
// Build the outer polygon from the full geometry bounding box.
//
// Why bbox instead of the largest closed polygon?
// DXF part outlines are often drawn with open LINE/ARC entities
// (not closed polylines), so "largest closed polygon" would
// pick a hole circle, giving a tiny pw/ph.  The nesting engine
// spaces copies pw apart, but the THREE.js renderer draws the
// full DXF (including the large open-path outline) for each copy.
// Result: copies overlap and appear nested inside one another.
//
// Using the full-geometry bbox as outer guarantees pw/ph equal
// the exact rendered width/height (Box3.setFromObject), so every
// placed copy is spaced correctly and appears side-by-side.
// -------------------------------------------------------------
function extractPolygons(geometry) {
  if (!Array.isArray(geometry)) return { outer: [], holes: [] };

  let minX = Infinity, maxX = -Infinity;
  let minY = Infinity, maxY = -Infinity;
  for (const e of geometry) {
    for (const pt of (Array.isArray(e.points) ? e.points : [])) {
      if (pt[0] < minX) minX = pt[0];
      if (pt[0] > maxX) maxX = pt[0];
      if (pt[1] < minY) minY = pt[1];
      if (pt[1] > maxY) maxY = pt[1];
    }
  }

  if (!isFinite(minX) || maxX <= minX || maxY <= minY) return { outer: [], holes: [] };

  return {
    outer: [[minX, minY], [maxX, minY], [maxX, maxY], [minX, maxY]],
    holes: [],
  };
}

// Supported file extensions
const IMAGE_EXTS    = new Set(['jpg', 'jpeg', 'png']);
const BACKEND_EXTS  = new Set(['dxf', 'pdf']);
const SUPPORTED_EXTS = new Set([...IMAGE_EXTS, ...BACKEND_EXTS]);

function fileExt(file) {
  return file?.name?.split('.').pop().toLowerCase() ?? '';
}

// -------------------------------------------------------------

export default function App() {

  const [uploadedFile, setUploadedFile]     = useState(null);
  const [analysisResult, setAnalysisResult] = useState(null);
  const [geometryParts, setGeometryParts]   = useState([]);
  const [isLoading, setIsLoading]           = useState(false);
  const [error, setError]                   = useState(null);
  const [viewerStatus, setViewerStatus]     = useState('Ready');
  const [leftPanelOpen, setLeftPanelOpen]   = useState(false);
  const [sidebarOpen, setSidebarOpen]       = useState(true);
  const [partsOpen, setPartsOpen]           = useState(true);
  const [rows, setRows]                     = useState([]);
  const [selectedRowId, setSelectedRowId]   = useState(null);
  const rowCounterRef                       = useRef(0);
  const apiBaseRef                          = useRef(null);

  // Nesting state
  const [stock, setStock]                 = useState({ width: 3000, height: 1500, thickness: 3, spacing: 0 });
  const [nestingResult, setNestingResult] = useState(null);
  const [isNesting, setIsNesting]         = useState(false);
  const [selectedParts, setSelectedParts] = useState([]);
  const [viewMode, setViewMode]           = useState('original');

  // Multi-format viewer state
  const [activeFileType, setActiveFileType] = useState('dxf');

  const closeAllPanels   = useCallback(() => setLeftPanelOpen(false), []);
  const handleToggleLeft = useCallback(() => setLeftPanelOpen(v => !v), []);

  // -------------------------------------------------------
  // FILE UPLOAD
  // -------------------------------------------------------
  const handleFileUpload = useCallback(async (filesInput) => {

    const allFiles = Array.isArray(filesInput) ? filesInput : [filesInput];
    const validFiles = allFiles.filter(f => SUPPORTED_EXTS.has(fileExt(f)));

    if (validFiles.length === 0) {
      setError('Invalid file format. Accepted: .DXF, .PDF, .JPG, .PNG');
      return;
    }

    let toProcess = validFiles;
    if (validFiles.length > 5) {
      alert('Maximum 5 files per upload. Only the first 5 will be processed.');
      toProcess = validFiles.slice(0, 5);
    }

    setError(null);
    setUploadedFile(toProcess[0]);
    setLeftPanelOpen(false);
    setViewMode('original');

    // ── Image files: handled entirely on the frontend ──────────────────────
    const imageFiles   = toProcess.filter(f => IMAGE_EXTS.has(fileExt(f)));
    const backendFiles = toProcess.filter(f => BACKEND_EXTS.has(fileExt(f)));

    for (const file of imageFiles) {
      const imageUrl = URL.createObjectURL(file);
      rowCounterRef.current += 1;
      const rowId = rowCounterRef.current;

      setRows(prev => [...prev, {
        id:             rowId,
        partName:       `p${rowId}`,
        fileName:       file.name,
        fileSize:       file.size,
        fileType:       'image',
        imageUrl,
        pdfData:        null,
        material:       'N/A',
        qty:            1,
        holes:          0,
        ep:             0,
        ip:             0,
        geometry:       null,
        analysisResult: null,
      }]);
      setSelectedRowId(rowId);
      setActiveFileType('image');
      setGeometryParts([]);
      setViewerStatus(`Loaded - ${file.name}`);
    }

    if (backendFiles.length === 0) return;

    // ── Backend files: DXF and PDF need the Python engine ─────────────────
    setIsLoading(true);
    setAnalysisResult(null);
    setViewerStatus('Connecting to Python engine...');

    const PRIMARY  = import.meta.env.VITE_API_BASE_URL     ?? 'http://localhost:8000';
    const FALLBACK = import.meta.env.VITE_API_FALLBACK_URL ?? 'http://localhost:8000';

    const tryPing = async (base) => {
      const hc = new AbortController();
      const t  = setTimeout(() => hc.abort(), 4000);
      try {
        const r = await fetch(`${base}/health`, { signal: hc.signal });
        return r.ok;
      } catch { return false; }
      finally  { clearTimeout(t); }
    };

    let API_BASE = null;
    if (await tryPing(PRIMARY))       API_BASE = PRIMARY;
    else if (await tryPing(FALLBACK)) API_BASE = FALLBACK;
    else {
      setError('Cannot reach backend. Ensure Python server is running.');
      setViewerStatus('Error loading file');
      setIsLoading(false);
      return;
    }
    apiBaseRef.current = API_BASE;

    let lastDxfResult = null;
    let lastFile      = null;
    let processed     = 0;

    for (const file of backendFiles) {
      const ext = fileExt(file);
      try {
        setViewerStatus(
          backendFiles.length > 1
            ? `Uploading ${file.name} (${processed + 1}/${backendFiles.length})...`
            : 'Uploading to Python engine...'
        );
        setUploadedFile(file);

        const controller = new AbortController();
        const timer = setTimeout(() => controller.abort(), 30000);
        const formData = new FormData();
        formData.append('file', file);

        const response = await fetch(`${API_BASE}/upload-drawing`, {
          method: 'POST',
          body:   formData,
          signal: controller.signal,
        });
        clearTimeout(timer);

        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || 'Upload failed');

        rowCounterRef.current += 1;
        const rowId = rowCounterRef.current;

        if (ext === 'dxf') {
          const result = {
            ...data,
            entityCount: data.entities,
            boundingBox: data.bounding_box,
          };
          const part = data.parts?.[0];
          const ep   = part?.external_perimeter ?? data.external_perimeter ?? data.perimeter ?? 0;
          const ip   = part?.internal_perimeter ?? data.internal_perimeter ?? 0;

          setRows(prev => [...prev, {
            id:             rowId,
            partName:       `p${rowId}`,
            fileName:       file.name,
            fileSize:       file.size,
            fileType:       'dxf',
            imageUrl:       null,
            pdfData:        null,
            material:       'MS',
            qty:            1,
            holes:          data.holes ?? 0,
            ep:             ep ?? 0,
            ip:             ip ?? 0,
            geometry:       data.geometry,
            analysisResult: result,
          }]);
          setSelectedRowId(rowId);
          setGeometryParts(prev => [...prev, { id: rowId, geometry: data.geometry }]);
          setActiveFileType('dxf');
          lastDxfResult = result;
          lastFile      = file;

        } else if (ext === 'pdf') {
          const pdfData = {
            page_image_b64:       data.page_image_b64,
            vector_lines:         data.vector_lines ?? [],
            extracted_dimensions: data.extracted_dimensions ?? [],
            width:                data.width,
            height:               data.height,
          };

          setRows(prev => [...prev, {
            id:             rowId,
            partName:       `p${rowId}`,
            fileName:       file.name,
            fileSize:       file.size,
            fileType:       'pdf',
            imageUrl:       null,
            pdfData,
            material:       'N/A',
            qty:            1,
            holes:          0,
            ep:             0,
            ip:             0,
            geometry:       null,
            analysisResult: null,
          }]);
          setSelectedRowId(rowId);
          setGeometryParts([]);
          setActiveFileType('pdf');
          setViewerStatus(
            `Loaded - ${file.name}` +
            (pdfData.extracted_dimensions.length > 0
              ? ` (${pdfData.extracted_dimensions.length} dimensions found)`
              : '')
          );
          lastFile = file;
        }

        processed++;

      } catch (err) {
        const msg = err?.name === 'AbortError'
          ? `Timed out: ${file.name}. Please try again.`
          : (err?.message || `Upload failed: ${file.name}`);
        setError(msg);
        setViewerStatus('Error loading file');
      }
    }

    if (lastDxfResult) {
      setAnalysisResult(lastDxfResult);
      setUploadedFile(lastFile);
      setViewerStatus(
        processed > 1
          ? `Loaded ${processed} files`
          : `Loaded - ${lastDxfResult.entityCount} entities - ${lastDxfResult.layers?.length ?? 0} layers`
      );
    }

    setIsLoading(false);

  }, []);

  // -------------------------------------------------------
  // ROW SELECTION
  // -------------------------------------------------------
  const handleSelectRow = useCallback((rowId) => {
    const row = rows.find(r => r.id === rowId);
    if (!row) return;

    setSelectedRowId(rowId);
    setAnalysisResult(row.analysisResult);
    setUploadedFile({ name: row.fileName, size: row.fileSize });
    setActiveFileType(row.fileType ?? 'dxf');

    if (row.fileType === 'dxf' && row.geometry) {
      setGeometryParts([{ id: row.id, geometry: row.geometry }]);
      setViewerStatus(
        `Loaded - ${row.analysisResult?.entityCount ?? '?'} entities - ${row.analysisResult?.layers?.length ?? 0} layers`
      );
    } else if (row.fileType === 'pdf') {
      setGeometryParts([]);
      const dimCount = row.pdfData?.extracted_dimensions?.length ?? 0;
      setViewerStatus(
        `Loaded - ${row.fileName}` + (dimCount > 0 ? ` (${dimCount} dimensions)` : '')
      );
    } else if (row.fileType === 'image') {
      setGeometryParts([]);
      setViewerStatus(`Loaded - ${row.fileName}`);
    }
  }, [rows]);

  const handleUpdateRow = useCallback((id, field, value) => {
    setRows(prev => prev.map(row => row.id === id ? { ...row, [field]: value } : row));
  }, []);

  const handleRemovePart = useCallback((partId) => {
    const row = rows.find(r => r.id === partId);
    if (row?.imageUrl) URL.revokeObjectURL(row.imageUrl);
    setRows(prev => prev.filter(p => p.id !== partId));
    setGeometryParts(prev => prev.filter(p => p.id !== partId));
    setSelectedRowId(prev => (prev === partId ? null : prev));
    setSelectedParts(prev => prev.filter(id => id !== partId));
  }, [rows]);

  const handleFitScreen = useCallback(() => {
    window.dispatchEvent(new CustomEvent('dxf-fit-screen'));
  }, []);

  // -------------------------------------------------------
  // PART SELECTION FOR NESTING
  // -------------------------------------------------------
  const handleTogglePart = useCallback((rowId) => {
    setSelectedParts(prev =>
      prev.includes(rowId) ? prev.filter(id => id !== rowId) : [...prev, rowId]
    );
  }, []);

  // -------------------------------------------------------
  // STOCK SETTINGS
  // -------------------------------------------------------
  const handleUpdateStock = useCallback((field, value) => {
    setStock(prev => ({ ...prev, [field]: parseFloat(value) || 0 }));
  }, []);

  // -------------------------------------------------------
  // RUN NESTING
  // -------------------------------------------------------
  const handleRunNesting = useCallback(async () => {
    if (rows.length === 0 || isNesting) return;

    const API_BASE = apiBaseRef.current ?? import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';

    setIsNesting(true);
    setNestingResult(null);

    try {
      // Only DXF rows contribute geometry for nesting; PDF/image rows are silently skipped
      const nestParts = rows
        .map(row => {
          const { outer, holes } = extractPolygons(row.geometry);
          if (outer.length < 3) return null;
          return {
            id:       String(row.id),
            outer,
            holes,
            quantity: Math.max(1, Math.floor(row.qty ?? 1)),
            area:     0,
          };
        })
        .filter(Boolean);

      if (nestParts.length === 0) {
        console.warn('[NESTING] No valid polygons found in uploaded parts.');
        setIsNesting(false);
        return;
      }

      const body = {
        parts:     nestParts,
        stock:     { width: stock.width, height: stock.height, thickness: stock.thickness },
        step_x:    5.0,
        step_y:    5.0,
        margin:    stock.spacing ?? 0,
        rotations: [0.0, 90.0],
      };

      const res = await fetch(`${API_BASE}/nest`, {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify(body),
      });

      const result = await res.json();
      if (!res.ok) throw new Error(result.detail || 'Nesting request failed');

      console.log('[NESTING] Placements:', result.placements);
      setNestingResult(result);
      setViewMode('nesting');

    } catch (err) {
      console.error('[NESTING] Failed:', err);
    } finally {
      setIsNesting(false);
    }
  }, [rows, stock, isNesting]);

  // -------------------------------------------------------
  // NEST SELECTED PARTS ONLY
  // -------------------------------------------------------
  const handleNestSelected = useCallback(async () => {
    if (selectedParts.length === 0 || isNesting) return;

    const targetRows = rows.filter(r => selectedParts.includes(r.id));
    if (targetRows.length === 0) return;

    const API_BASE = apiBaseRef.current ?? import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';

    setIsNesting(true);
    setNestingResult(null);

    try {
      const nestParts = targetRows
        .map(row => {
          const { outer, holes } = extractPolygons(row.geometry);
          if (outer.length < 3) return null;
          return {
            id:       String(row.id),
            outer,
            holes,
            quantity: Math.max(1, Math.floor(row.qty ?? 1)),
            area:     0,
          };
        })
        .filter(Boolean);

      if (nestParts.length === 0) {
        console.warn('[NESTING] No valid polygons found in selected parts.');
        setIsNesting(false);
        return;
      }

      const body = {
        parts:     nestParts,
        stock:     { width: stock.width, height: stock.height, thickness: stock.thickness },
        step_x:    5.0,
        step_y:    5.0,
        margin:    stock.spacing ?? 0,
        rotations: [0.0, 90.0, 180.0, 270.0],
      };

      const res = await fetch(`${API_BASE}/nest`, {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify(body),
      });

      const result = await res.json();
      if (!res.ok) throw new Error(result.detail || 'Nesting request failed');

      console.log('[NESTING] Selected placements:', result.placements);
      setNestingResult(result);
      setViewMode('nesting');

    } catch (err) {
      console.error('[NESTING] Failed:', err);
    } finally {
      setIsNesting(false);
    }
  }, [rows, selectedParts, stock, isNesting]);

  // -------------------------------------------------------

  const selectedRow = rows.find(r => r.id === selectedRowId);

  return (
    <div className="app-layout">

      <TopBar
        fileName={uploadedFile?.name}
        onFileUpload={handleFileUpload}
        onFitScreen={handleFitScreen}
        isLoading={isLoading}
        leftPanelOpen={leftPanelOpen}
        onToggleLeft={handleToggleLeft}
        sidebarOpen={sidebarOpen}
        onToggleSidebar={() => setSidebarOpen(v => !v)}
      />

      <div
        className={`panel-backdrop${leftPanelOpen ? ' visible' : ''}`}
        onClick={closeAllPanels}
      />

      <div className="app-body">

        <div className={`sidebar-wrap${sidebarOpen ? '' : ' sidebar-wrap--collapsed'}`}>
          <LeftPanel
            fileName={uploadedFile?.name}
            fileSize={uploadedFile?.size}
            layers={analysisResult?.layers || []}
            entityCount={analysisResult?.entityCount}
            units={analysisResult?.units}
            boundingBox={analysisResult?.boundingBox}
            isOpen={leftPanelOpen}
            onClose={() => setLeftPanelOpen(false)}
          />
        </div>

        <main className="viewer-container">
          <DXFViewer
            parts={geometryParts}
            selectedRowId={selectedRowId}
            isLoading={isLoading}
            error={error}
            onStatusChange={setViewerStatus}
            nestedSheets={nestingResult?.sheets ?? []}
            viewMode={viewMode}
            onSetViewMode={setViewMode}
            fileType={activeFileType}
            pdfData={selectedRow?.pdfData ?? null}
            imageUrl={selectedRow?.imageUrl ?? null}
          />
        </main>

      </div>

      <SummaryTable
        rows={rows}
        onUpdateRow={handleUpdateRow}
        selectedRowId={selectedRowId}
        onSelectRow={handleSelectRow}
        onRemoveRow={handleRemovePart}
        partsOpen={partsOpen}
        onToggleTable={() => setPartsOpen(v => !v)}
        stock={stock}
        onUpdateStock={handleUpdateStock}
        nestingResult={nestingResult}
        isNesting={isNesting}
        onRunNesting={handleRunNesting}
        selectedParts={selectedParts}
        onTogglePart={handleTogglePart}
        onNestSelected={handleNestSelected}
      />

      <StatusBar status={viewerStatus} fileName={uploadedFile?.name} />

    </div>
  );
}
