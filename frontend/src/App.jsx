import { useState, useCallback, useRef, useEffect } from 'react';
import TopBar from './components/TopBar';
import LeftPanel from './components/LeftPanel';
import DXFViewer from './components/DXFViewer';
import StatusBar from './components/StatusBar';
import SummaryTable from './components/SummaryTable';
import './App.css';

export default function App() {

  const [uploadedFile, setUploadedFile] = useState(null);
  const [analysisResult, setAnalysisResult] = useState(null);

  // Geometry for all uploaded parts — only grows, never replaced
  const [geometryParts, setGeometryParts] = useState([]);

  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [viewerStatus, setViewerStatus] = useState('Ready');

  const [leftPanelOpen, setLeftPanelOpen] = useState(false);

  // Layout toggles
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [partsOpen, setPartsOpen] = useState(true);

  // Multi-part summary table rows
  const [rows, setRows] = useState([]);
  const [selectedRowId, setSelectedRowId] = useState(null);
  const rowCounterRef = useRef(0);

  // Stores whichever backend URL (Render or localhost) responded successfully
  const apiBaseRef = useRef(null);

  // ─────────────────────────────────────────────
  // LOAD PERSISTED PARTS FROM DB ON MOUNT
  // ─────────────────────────────────────────────
  useEffect(() => {
    const API_BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';

    (async () => {
      try {
        const res = await fetch(`${API_BASE}/parts`);
        if (!res.ok) return;
        const parts = await res.json();
        if (!Array.isArray(parts) || parts.length === 0) return;

        const loaded = parts.map(p => ({
          id:             p.id,
          partName:       p.part_name,
          fileName:       p.file_name,
          fileSize:       0,
          material:       p.material || 'MS',
          holes:          p.holes ?? 0,
          ep:             p.external_perimeter ?? 0,
          ip:             p.internal_perimeter ?? 0,
          geometry:       null,
          analysisResult: { entityCount: 0, layers: [] },
        }));

        setRows(loaded);

        // Advance counter past existing DB ids so new uploads get unique local ids
        const maxId = Math.max(...parts.map(p => p.id));
        rowCounterRef.current = Math.max(rowCounterRef.current, maxId);
      } catch (err) {
        console.error('[Parts] Failed to load from DB:', err);
      }
    })();
  }, []);

  const closeAllPanels = useCallback(() => {
    setLeftPanelOpen(false);
  }, []);

  const handleToggleLeft = useCallback(() => {
    setLeftPanelOpen(v => !v);
  }, []);

  // ─────────────────────────────────────────────
  // FILE UPLOAD  (accepts a File or File[])
  // ─────────────────────────────────────────────
  const handleFileUpload = useCallback(async (filesInput) => {

    // Normalize to array
    const allFiles  = Array.isArray(filesInput) ? filesInput : [filesInput];
    const dxfFiles  = allFiles.filter(f => f?.name?.split('.').pop().toLowerCase() === 'dxf');

    if (dxfFiles.length === 0) {
      setError('Invalid file format. Only .DXF files are accepted.');
      return;
    }

    // Enforce 5-file limit per selection
    let toProcess = dxfFiles;
    if (dxfFiles.length > 5) {
      alert(`Maximum 5 files per upload. Only the first 5 will be processed.`);
      toProcess = dxfFiles.slice(0, 5);
    }

    setError(null);
    setIsLoading(true);
    setAnalysisResult(null);
    setUploadedFile(toProcess[0]);
    setViewerStatus('Connecting to Python engine…');
    setLeftPanelOpen(false);

    const PRIMARY  = import.meta.env.VITE_API_BASE_URL     ?? 'http://localhost:8000';
    const FALLBACK = import.meta.env.VITE_API_FALLBACK_URL ?? 'http://localhost:8000';

    // Single server ping for the whole batch
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

    let lastResult = null;
    let lastFile   = null;
    let processed  = 0;

    // Upload each file sequentially — append to scene, never replace
    for (const file of toProcess) {
      try {
        setViewerStatus(
          toProcess.length > 1
            ? `Uploading ${file.name} (${processed + 1}/${toProcess.length})…`
            : `Uploading to Python engine…`
        );
        setUploadedFile(file);

        const formData = new FormData();
        formData.append('file', file);

        const controller = new AbortController();
        const timer = setTimeout(() => controller.abort(), 20000);
        const response = await fetch(`${API_BASE}/upload`, {
          method: 'POST',
          body: formData,
          signal: controller.signal,
        });
        clearTimeout(timer);

        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || 'Upload failed');

        const result = {
          ...data,
          entityCount: data.entities,
          boundingBox: data.bounding_box,
        };

        // Extract EP and IP from the API response (no calculation, values as-is)
        const part = data.parts?.[0];
        const ep = part?.external_perimeter ?? data.external_perimeter ?? data.perimeter ?? 0;
        const ip = part?.internal_perimeter ?? data.internal_perimeter ?? 0;

        // Use counter as ID — guaranteed unique even within the same batch
        rowCounterRef.current += 1;
        const rowId = rowCounterRef.current;
        const newRow = {
          id:           rowId,
          partName:     `p${rowId}`,
          fileName:     file.name,
          fileSize:     file.size,
          material:     'MS',
          holes:        data.holes ?? 0,
          ep:           ep ?? 0,
          ip:           ip ?? 0,
          geometry:     data.geometry,
          analysisResult: result,
        };

        setRows(prev => [...prev, newRow]);
        setSelectedRowId(rowId);
        // Append geometry — all parts stay visible in the viewer
        setGeometryParts(prev => [...prev, { id: rowId, geometry: data.geometry }]);

        lastResult = result;
        lastFile   = file;
        processed++;

      } catch (err) {
        const msg = err?.name === 'AbortError'
          ? `Timed out: ${file.name}. Please try again.`
          : (err?.message || `Upload failed: ${file.name}`);
        setError(msg);
        setViewerStatus('Error loading file');
      }
    }

    if (lastResult) {
      setAnalysisResult(lastResult);
      setUploadedFile(lastFile);
      setViewerStatus(
        processed > 1
          ? `Loaded ${processed} files`
          : `Loaded · ${lastResult.entityCount} entities · ${lastResult.layers?.length ?? 0} layers`
      );
    }

    setIsLoading(false);

  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleUpdateRow = useCallback((id, field, value) => {
    setRows(prev => prev.map(row => row.id === id ? { ...row, [field]: value } : row));
  }, []);

  const handleRemovePart = useCallback((partId) => {
    setRows(prev => prev.filter(p => p.id !== partId));
    setGeometryParts(prev => prev.filter(p => p.id !== partId));
    setSelectedRowId(prev => (prev === partId ? null : prev));
  }, []);

  const handleSelectRow = useCallback(async (rowId) => {
    const row = rows.find(r => r.id === rowId);
    if (!row) return;

    setSelectedRowId(rowId);
    setAnalysisResult(row.analysisResult);
    setUploadedFile({ name: row.fileName, size: row.fileSize });

    if (row.geometry) {
      // Fresh-upload row — geometry already in memory, replace viewer immediately
      setGeometryParts([{ id: row.id, geometry: row.geometry }]);
      setViewerStatus(
        `Loaded · ${row.analysisResult.entityCount ?? '?'} entities · ${row.analysisResult.layers?.length ?? 0} layers`
      );
      return;
    }

    // DB-loaded row — fetch geometry from backend
    const API_BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';
    setViewerStatus('Loading geometry…');
    try {
      const res = await fetch(`${API_BASE}/parts/${rowId}/geometry`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const geometry = await res.json();
      setGeometryParts([{ id: row.id, geometry }]);
      setViewerStatus(`Loaded · ${row.fileName}`);
    } catch (err) {
      console.error('[Viewer] Failed to load geometry:', err);
      setViewerStatus('Geometry not available');
    }
  }, [rows]);

  const handleFitScreen = useCallback(() => {
    window.dispatchEvent(new CustomEvent('dxf-fit-screen'));
  }, []);

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
      />

      <StatusBar status={viewerStatus} fileName={uploadedFile?.name} />

    </div>
  );
}
