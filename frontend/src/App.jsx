import { useState, useCallback, useRef, useEffect } from 'react';
import TopBar from './components/TopBar';
import LeftPanel from './components/LeftPanel';
import DXFViewer from './components/DXFViewer';
import StatusBar from './components/StatusBar';
import SummaryTable from './components/SummaryTable';
import ProjectBar from './components/ProjectBar';
import {
  fetchProjects,
  createProject,
  deleteProject,
  fetchProjectParts,
  uploadPartToProject,
  fetchPartGeometry,
  uploadDxf,
} from './api';
import './App.css';

export default function App() {

  const [uploadedFile, setUploadedFile]     = useState(null);
  const [analysisResult, setAnalysisResult] = useState(null);

  // Geometry for all visible parts
  const [geometryParts, setGeometryParts]   = useState([]);

  const [isLoading, setIsLoading]           = useState(false);
  const [error, setError]                   = useState(null);
  const [viewerStatus, setViewerStatus]     = useState('Ready');

  const [leftPanelOpen, setLeftPanelOpen]   = useState(false);
  const [sidebarOpen, setSidebarOpen]       = useState(true);
  const [partsOpen, setPartsOpen]           = useState(true);

  // Summary table rows
  const [rows, setRows]                     = useState([]);
  const [selectedRowId, setSelectedRowId]   = useState(null);
  const rowCounterRef                       = useRef(0);

  // Projects
  const [projects, setProjects]             = useState([]);
  const [selectedProjectId, setSelectedProjectId] = useState(null);

  const apiBaseRef = useRef(null);

  // ─────────────────────────────────────────────
  // LOAD PROJECTS ON MOUNT
  // ─────────────────────────────────────────────
  useEffect(() => {
    fetchProjects()
      .then(setProjects)
      .catch(err => console.error('[Projects] Failed to load:', err));
  }, []);

  // ─────────────────────────────────────────────
  // PROJECT HANDLERS
  // ─────────────────────────────────────────────
  const handleCreateProject = useCallback(async (name) => {
    try {
      await createProject(name);
      const updated = await fetchProjects();
      setProjects(updated);
    } catch (err) {
      console.error('[Projects] Create failed:', err);
    }
  }, []);

  const handleDeleteProject = useCallback(async (id) => {
    try {
      await deleteProject(id);
      const updated = await fetchProjects();
      setProjects(updated);
      // Clear parts list if the deleted project was selected
      if (id === selectedProjectId) {
        setSelectedProjectId(null);
        setRows([]);
        setGeometryParts([]);
        setAnalysisResult(null);
        setUploadedFile(null);
        setViewerStatus('Ready');
      }
    } catch (err) {
      console.error('[Projects] Delete failed:', err);
    }
  }, [selectedProjectId]);

  const handleSelectProject = useCallback(async (projectId) => {
    setSelectedProjectId(projectId);
    setRows([]);
    setGeometryParts([]);
    setAnalysisResult(null);
    setSelectedRowId(null);

    if (!projectId) {
      setViewerStatus('Ready');
      return;
    }

    setViewerStatus('Loading project…');
    try {
      const parts = await fetchProjectParts(projectId);
      if (!Array.isArray(parts) || parts.length === 0) {
        setViewerStatus('Project is empty — upload a DXF to begin');
        return;
      }

      const loaded = parts.map(p => ({
        id:             p.id,         // DB id doubles as local row id
        dbPartId:       p.id,         // used for geometry fetch
        partName:       p.part_name,
        fileName:       p.file_name,
        fileSize:       0,
        material:       p.material || 'MS',
        holes:          p.holes ?? 0,
        ep:             p.external_perimeter ?? 0,
        ip:             p.internal_perimeter ?? 0,
        geometry:       null,         // fetched on demand when row is clicked
        analysisResult: { entityCount: 0, layers: [] },
      }));

      const maxId = Math.max(...loaded.map(r => r.id));
      rowCounterRef.current = Math.max(rowCounterRef.current, maxId);
      setRows(loaded);
      setViewerStatus(`Project loaded — ${loaded.length} part(s)`);
    } catch (err) {
      console.error('[Projects] Load parts failed:', err);
      setViewerStatus('Failed to load project parts');
    }
  }, []);

  // ─────────────────────────────────────────────
  // PANEL HANDLERS
  // ─────────────────────────────────────────────
  const closeAllPanels  = useCallback(() => setLeftPanelOpen(false), []);
  const handleToggleLeft = useCallback(() => setLeftPanelOpen(v => !v), []);

  // ─────────────────────────────────────────────
  // FILE UPLOAD
  // ─────────────────────────────────────────────
  const handleFileUpload = useCallback(async (filesInput) => {

    const allFiles = Array.isArray(filesInput) ? filesInput : [filesInput];
    const dxfFiles = allFiles.filter(f => f?.name?.split('.').pop().toLowerCase() === 'dxf');

    if (dxfFiles.length === 0) {
      setError('Invalid file format. Only .DXF files are accepted.');
      return;
    }

    let toProcess = dxfFiles;
    if (dxfFiles.length > 5) {
      alert('Maximum 5 files per upload. Only the first 5 will be processed.');
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

    for (const file of toProcess) {
      try {
        setViewerStatus(
          toProcess.length > 1
            ? `Uploading ${file.name} (${processed + 1}/${toProcess.length})…`
            : 'Uploading to Python engine…'
        );
        setUploadedFile(file);

        const controller = new AbortController();
        const timer = setTimeout(() => controller.abort(), 20000);

        let data;
        if (selectedProjectId) {
          // Upload into the selected project — persists to DB
          data = await uploadPartToProject(selectedProjectId, file, controller.signal);
        } else {
          // Session-only upload — no DB persistence
          data = await uploadDxf(file, controller.signal);
        }
        clearTimeout(timer);

        const result = {
          ...data,
          entityCount: data.entities,
          boundingBox: data.bounding_box,
        };

        const part = data.parts?.[0];
        const ep   = part?.external_perimeter ?? data.external_perimeter ?? data.perimeter ?? 0;
        const ip   = part?.internal_perimeter ?? data.internal_perimeter ?? 0;

        rowCounterRef.current += 1;
        const rowId = rowCounterRef.current;

        const newRow = {
          id:             rowId,
          dbPartId:       data.db_part_id ?? null,  // set only on project uploads
          partName:       `p${rowId}`,
          fileName:       file.name,
          fileSize:       file.size,
          material:       'MS',
          holes:          data.holes ?? 0,
          ep:             ep ?? 0,
          ip:             ip ?? 0,
          geometry:       data.geometry,
          analysisResult: result,
        };

        setRows(prev => [...prev, newRow]);
        setSelectedRowId(rowId);
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
  }, [selectedProjectId]);

  // ─────────────────────────────────────────────
  // ROW SELECTION — loads geometry on demand
  // ─────────────────────────────────────────────
  const handleSelectRow = useCallback(async (rowId) => {
    const row = rows.find(r => r.id === rowId);
    if (!row) return;

    setSelectedRowId(rowId);
    setAnalysisResult(row.analysisResult);
    setUploadedFile({ name: row.fileName, size: row.fileSize });

    if (row.geometry) {
      // Already in memory (fresh upload)
      setGeometryParts([{ id: row.id, geometry: row.geometry }]);
      setViewerStatus(
        `Loaded · ${row.analysisResult?.entityCount ?? '?'} entities · ${row.analysisResult?.layers?.length ?? 0} layers`
      );
      return;
    }

    if (row.dbPartId) {
      // DB-loaded row — fetch geometry from backend
      setViewerStatus('Loading geometry…');
      try {
        const geometry = await fetchPartGeometry(row.dbPartId);
        // Cache it in the row so next click is instant
        setRows(prev => prev.map(r => r.id === rowId ? { ...r, geometry } : r));
        setGeometryParts([{ id: row.id, geometry }]);
        setViewerStatus(`Loaded · ${row.fileName}`);
      } catch (err) {
        console.error('[Viewer] Failed to load geometry:', err);
        setViewerStatus('Geometry not available');
      }
    }
  }, [rows]);

  const handleUpdateRow = useCallback((id, field, value) => {
    setRows(prev => prev.map(row => row.id === id ? { ...row, [field]: value } : row));
  }, []);

  const handleRemovePart = useCallback((partId) => {
    setRows(prev => prev.filter(p => p.id !== partId));
    setGeometryParts(prev => prev.filter(p => p.id !== partId));
    setSelectedRowId(prev => (prev === partId ? null : prev));
  }, []);

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

      <ProjectBar
        projects={projects}
        selectedProjectId={selectedProjectId}
        onSelectProject={handleSelectProject}
        onCreateProject={handleCreateProject}
        onDeleteProject={handleDeleteProject}
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
