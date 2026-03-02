import { useState, useCallback, useRef, useMemo } from 'react';
import TopBar       from './components/TopBar';
import LeftPanel    from './components/LeftPanel';
import DXFViewer    from './components/DXFViewer';
import StatusBar    from './components/StatusBar';
import SummaryTable from './components/SummaryTable';
import AppSettings    from './components/AppSettings';
import QuotationView  from './components/QuotationView';
import './App.css';

// -------------------------------------------------------------
// POLYGON EXTRACTION
// Build the outer polygon from the full geometry bounding box.
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
const IMAGE_EXTS     = new Set(['jpg', 'jpeg', 'png']);
const BACKEND_EXTS   = new Set(['dxf', 'pdf']);
const SUPPORTED_EXTS = new Set([...IMAGE_EXTS, ...BACKEND_EXTS]);

function fileExt(file) {
  return file?.name?.split('.').pop().toLowerCase() ?? '';
}

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';

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

  const nestingParts = useMemo(
    () => rows.filter(r => r.fileType === 'dxf' && r.geometry)
              .map(r => ({ id: r.id, geometry: r.geometry })),
    [rows],
  );

  const [stock, setStock]                 = useState({ width: 3000, height: 1500, thickness: 3, spacing: 0, edge_gap: 0 });
  const [nestingResult, setNestingResult] = useState(null);
  const [nestingError, setNestingError]   = useState(null);
  const [isNesting, setIsNesting]         = useState(false);
  const [selectedParts, setSelectedParts] = useState([]);
  const [viewMode, setViewMode]           = useState('original');
  const [activeFileType, setActiveFileType] = useState('dxf');

  // Modal / view state
  const [showSettings, setShowSettings] = useState(false);
  const [quoteMode, setQuoteMode]       = useState(false);

  const closeAllPanels   = useCallback(() => setLeftPanelOpen(false), []);
  const handleToggleLeft = useCallback(() => setLeftPanelOpen(v => !v), []);

  // -------------------------------------------------------
  // FILE UPLOAD
  // -------------------------------------------------------
  const handleFileUpload = useCallback(async (filesInput) => {

    const allFiles   = Array.isArray(filesInput) ? filesInput : [filesInput];
    const validFiles = allFiles.filter(f => SUPPORTED_EXTS.has(fileExt(f)));

    if (validFiles.length === 0) {
      setError('Invalid file format. Accepted: .DXF, .PDF, .JPG, .PNG');
      return;
    }

    const remaining = Math.max(0, 5 - rows.length);
    if (remaining === 0) {
      setError('Maximum 5 parts loaded. Remove parts before importing more.');
      return;
    }
    let toProcess = validFiles.slice(0, remaining);
    if (validFiles.length > remaining) {
      alert(`Maximum 5 parts total. Only ${remaining} more can be added — extra files skipped.`);
    }

    setError(null);
    setUploadedFile(toProcess[0]);
    setLeftPanelOpen(false);
    setViewMode('original');

    const imageFiles   = toProcess.filter(f => IMAGE_EXTS.has(fileExt(f)));
    const backendFiles = toProcess.filter(f => BACKEND_EXTS.has(fileExt(f)));

    for (const file of imageFiles) {
      const imageUrl = URL.createObjectURL(file);
      rowCounterRef.current += 1;
      const rowId = rowCounterRef.current;
      setRows(prev => [...prev, {
        id: rowId, partName: `p${prev.length + 1}`, fileName: file.name, fileSize: file.size,
        fileType: 'image', imageUrl, pdfData: null,
        material: 'N/A', qty: 1, holes: 0, ep: 0, ip: 0,
        geometry: null, analysisResult: null,
      }]);
      setSelectedRowId(rowId);
      setActiveFileType('image');
      setGeometryParts([]);
      setViewerStatus(`Loaded - ${file.name}`);
    }

    if (backendFiles.length === 0) return;

    setIsLoading(true);
    setAnalysisResult(null);
    setViewerStatus('Connecting to Python engine…');

    const tryPing = async (base) => {
      const hc = new AbortController();
      const t  = setTimeout(() => hc.abort(), 4000);
      try   { const r = await fetch(`${base}/health`, { signal: hc.signal }); return r.ok; }
      catch { return false; }
      finally { clearTimeout(t); }
    };

    let resolvedBase = null;
    if      (await tryPing(API_BASE))                              resolvedBase = API_BASE;
    else if (await tryPing(import.meta.env.VITE_API_FALLBACK_URL ?? 'http://localhost:8000'))
                                                                   resolvedBase = import.meta.env.VITE_API_FALLBACK_URL ?? 'http://localhost:8000';
    else {
      setError('Cannot reach backend. Ensure Python server is running.');
      setViewerStatus('Error loading file');
      setIsLoading(false);
      return;
    }
    apiBaseRef.current = resolvedBase;

    let lastDxfResult = null, lastFile = null, processed = 0;

    for (const file of backendFiles) {
      const ext = fileExt(file);
      try {
        setViewerStatus(
          backendFiles.length > 1
            ? `Uploading ${file.name} (${processed + 1}/${backendFiles.length})…`
            : 'Uploading to Python engine…'
        );
        setUploadedFile(file);

        const ctrl = new AbortController();
        const timer = setTimeout(() => ctrl.abort(), 30000);
        const fd    = new FormData();
        fd.append('file', file);

        const res  = await fetch(`${resolvedBase}/upload-drawing`, { method: 'POST', body: fd, signal: ctrl.signal });
        clearTimeout(timer);
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Upload failed');

        rowCounterRef.current += 1;
        const rowId = rowCounterRef.current;

        if (ext === 'dxf') {
          const result = { ...data, entityCount: data.entities, boundingBox: data.bounding_box };
          const part   = data.parts?.[0];
          const ep     = part?.external_perimeter ?? data.external_perimeter ?? data.perimeter ?? 0;
          const ip     = part?.internal_perimeter ?? data.internal_perimeter ?? 0;

          setRows(prev => [...prev, {
            id: rowId, partName: `p${prev.length + 1}`, fileName: file.name, fileSize: file.size,
            fileType: 'dxf', imageUrl: null, pdfData: null,
            material: 'MS', qty: 1, holes: data.holes ?? 0,
            ep, ip, geometry: data.geometry, analysisResult: result,
          }]);
          setSelectedRowId(rowId);
          setGeometryParts(prev => [...prev, { id: rowId, geometry: data.geometry }]);
          setActiveFileType('dxf');
          lastDxfResult = result;
          lastFile      = file;

        } else if (ext === 'pdf') {
          const pdfData = {
            page_image_b64: data.page_image_b64,
            vector_lines:   data.vector_lines ?? [],
            extracted_dimensions: data.extracted_dimensions ?? [],
            width: data.width, height: data.height,
          };
          setRows(prev => [...prev, {
            id: rowId, partName: `p${prev.length + 1}`, fileName: file.name, fileSize: file.size,
            fileType: 'pdf', imageUrl: null, pdfData,
            material: 'N/A', qty: 1, holes: 0, ep: 0, ip: 0,
            geometry: null, analysisResult: null,
          }]);
          setSelectedRowId(rowId);
          setGeometryParts([]);
          setActiveFileType('pdf');
          setViewerStatus(
            `Loaded - ${file.name}` +
            (pdfData.extracted_dimensions.length > 0 ? ` (${pdfData.extracted_dimensions.length} dimensions found)` : '')
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

  }, [rows]);

  // -------------------------------------------------------
  // ROW MANAGEMENT
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
      setViewerStatus(`Loaded - ${row.analysisResult?.entityCount ?? '?'} entities - ${row.analysisResult?.layers?.length ?? 0} layers`);
    } else if (row.fileType === 'pdf') {
      setGeometryParts([]);
      const dc = row.pdfData?.extracted_dimensions?.length ?? 0;
      setViewerStatus(`Loaded - ${row.fileName}` + (dc > 0 ? ` (${dc} dimensions)` : ''));
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

  const handleClearAll = useCallback(() => {
    rows.forEach(row => { if (row?.imageUrl) URL.revokeObjectURL(row.imageUrl); });
    setRows([]);
    setGeometryParts([]);
    setSelectedRowId(null);
    setSelectedParts([]);
    setNestingResult(null);
    setNestingError(null);
    setAnalysisResult(null);
    setUploadedFile(null);
    setViewerStatus('Ready');
    setViewMode('original');
  }, [rows]);

  const handleFitScreen = useCallback(() => {
    window.dispatchEvent(new CustomEvent('dxf-fit-screen'));
  }, []);

  const handleTogglePart = useCallback((rowId) => {
    setSelectedParts(prev => prev.includes(rowId) ? prev.filter(id => id !== rowId) : [...prev, rowId]);
  }, []);

  const handleUpdateStock = useCallback((field, value) => {
    setStock(prev => ({ ...prev, [field]: parseFloat(value) || 0 }));
  }, []);

  // -------------------------------------------------------
  // NESTING
  // -------------------------------------------------------
  const _nestParts = (targetRows) =>
    targetRows
      .map(row => {
        const { outer, holes } = extractPolygons(row.geometry);
        if (outer.length < 3) return null;
        return { id: String(row.id), outer, holes, quantity: Math.max(1, Math.floor(row.qty ?? 1)), area: 0 };
      })
      .filter(Boolean);

  const _runNest = useCallback(async (nestParts, rotations = [0.0, 90.0, 180.0, 270.0]) => {
    const base = apiBaseRef.current ?? API_BASE;
    const body = {
      parts: nestParts,
      stock: { width: stock.width, height: stock.height, thickness: stock.thickness },
      step_x: 5.0, step_y: 5.0,
      margin:    stock.spacing ?? 0,
      rotations,
      edge_gap:  stock.edge_gap ?? 0,
    };
    const res    = await fetch(`${base}/nest`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    const result = await res.json();
    if (!res.ok) throw new Error(result.detail || 'Nesting request failed');
    return result;
  }, [stock]);

  const handleRunNesting = useCallback(async () => {
    if (rows.length === 0 || isNesting) return;
    setIsNesting(true); setNestingResult(null); setNestingError(null);
    try {
      const nestParts = _nestParts(rows);
      if (!nestParts.length) return;
      const result = await _runNest(nestParts);
      setNestingResult(result); setNestingError(null); setViewMode('nesting');
    } catch (err) {
      setNestingError(err.message || 'Nesting failed.');
    } finally { setIsNesting(false); }
  }, [rows, _runNest, isNesting]);

  const handleNestSelected = useCallback(async () => {
    if (selectedParts.length === 0 || isNesting) return;
    const targetRows = rows.filter(r => selectedParts.includes(r.id));
    if (!targetRows.length) return;
    setIsNesting(true); setNestingResult(null); setNestingError(null);
    try {
      const nestParts = _nestParts(targetRows);
      if (!nestParts.length) return;
      const result = await _runNest(nestParts, [0.0, 90.0, 180.0, 270.0]);
      setNestingResult(result); setNestingError(null); setViewMode('nesting');
    } catch (err) {
      setNestingError(err.message || 'Nesting failed.');
    } finally { setIsNesting(false); }
  }, [rows, selectedParts, _runNest, isNesting]);

  // -------------------------------------------------------

  const selectedRow = rows.find(r => r.id === selectedRowId);

  // ── Quote mode: full-screen quotation replaces the entire workspace ──
  if (quoteMode) {
    return (
      <QuotationView
        rows={rows}
        apiBase={API_BASE}
        stock={stock}
        onBack={() => setQuoteMode(false)}
      />
    );
  }

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
        onOpenSettings={() => setShowSettings(true)}
        onOpenQuote={() => setQuoteMode(true)}
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
            nestingParts={nestingParts}
            selectedRowId={selectedRowId}
            isLoading={isLoading}
            error={error}
            onStatusChange={setViewerStatus}
            nestedSheets={nestingResult?.sheets ?? []}
            nestEdgeGap={stock.edge_gap ?? 0}
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
        onClearAll={handleClearAll}
        partsOpen={partsOpen}
        onToggleTable={() => setPartsOpen(v => !v)}
        stock={stock}
        onUpdateStock={handleUpdateStock}
        nestingResult={nestingResult}
        nestingError={nestingError}
        isNesting={isNesting}
        onRunNesting={handleRunNesting}
        selectedParts={selectedParts}
        onTogglePart={handleTogglePart}
        onNestSelected={handleNestSelected}
      />

      <StatusBar status={viewerStatus} fileName={uploadedFile?.name} />

      {/* ── Modals ── */}
      {showSettings && (
        <AppSettings
          apiBase={API_BASE}
          onClose={() => setShowSettings(false)}
        />
      )}


    </div>
  );
}
