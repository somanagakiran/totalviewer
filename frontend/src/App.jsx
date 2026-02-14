import { useState, useCallback } from 'react';
import TopBar from './components/TopBar';
import LeftPanel from './components/LeftPanel';
import RightPanel from './components/RightPanel';
import DXFViewer from './components/DXFViewer';
import StatusBar from './components/StatusBar';
import './App.css';

export default function App() {
  const [uploadedFile,   setUploadedFile]   = useState(null);
  const [analysisResult, setAnalysisResult] = useState(null);
  const [isLoading,      setIsLoading]      = useState(false);
  const [error,          setError]          = useState(null);
  const [geometry,       setGeometry]       = useState(null);
  const [viewerStatus,   setViewerStatus]   = useState('Ready');

  // ── Responsive panel drawer state (tablet / mobile) ───────────────────────
  const [leftPanelOpen,  setLeftPanelOpen]  = useState(false);
  const [rightPanelOpen, setRightPanelOpen] = useState(false);

  const closeAllPanels = useCallback(() => {
    setLeftPanelOpen(false);
    setRightPanelOpen(false);
  }, []);

  const handleToggleLeft = useCallback(() => {
    setLeftPanelOpen(v => !v);
    setRightPanelOpen(false);
  }, []);

  const handleToggleRight = useCallback(() => {
    setRightPanelOpen(v => !v);
    setLeftPanelOpen(false);
  }, []);

  const handleFileUpload = useCallback(async (file) => {
    if (!file) return;

    const ext = file.name.split('.').pop().toLowerCase();
    if (ext !== 'dxf') {
      setError('Invalid file format. Only .DXF files are accepted.');
      return;
    }

    setError(null);
    setIsLoading(true);
    setAnalysisResult(null);
    setGeometry(null);
    setUploadedFile(file);
    setViewerStatus('Uploading to Python engine…');
    closeAllPanels(); // show viewer during load on mobile

    // POST to Python FastAPI backend.
    // In dev: VITE_API_BASE_URL=http://localhost:8000 (set in .env)
    // In production: VITE_API_BASE_URL=https://your-backend.onrender.com
    const API_BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';
    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await fetch(`${API_BASE}/upload`, {
        method: 'POST',
        body: formData,
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || data.error || 'Upload failed');
      }

      // Normalise field names expected by LeftPanel / RightPanel
      const result = {
        ...data,
        entityCount: data.entities,
        boundingBox: data.bounding_box,
      };

      setAnalysisResult(result);
      setGeometry(data.geometry);
      setViewerStatus(
        `Loaded · ${data.entities} entities · ${data.layers?.length ?? 0} layers`
      );
    } catch (err) {
      setError(
        err.message ||
        `Failed to process file. Is the Python backend running at ${import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'}?`
      );
      setViewerStatus('Error loading file');
    } finally {
      setIsLoading(false);
    }
  }, [closeAllPanels]);

  const handleFitScreen = useCallback(() => {
    window.dispatchEvent(new CustomEvent('dxf-fit-screen'));
  }, []);

  const anyPanelOpen = leftPanelOpen || rightPanelOpen;

  return (
    <div className="app-layout">
      <TopBar
        fileName={uploadedFile?.name}
        onFileUpload={handleFileUpload}
        onFitScreen={handleFitScreen}
        isLoading={isLoading}
        leftPanelOpen={leftPanelOpen}
        rightPanelOpen={rightPanelOpen}
        onToggleLeft={handleToggleLeft}
        onToggleRight={handleToggleRight}
      />

      {/* Backdrop: tapping outside an open drawer closes it (tablet/mobile) */}
      <div
        className={`panel-backdrop${anyPanelOpen ? ' visible' : ''}`}
        onClick={closeAllPanels}
        aria-hidden="true"
      />

      <div className="app-body">
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

        <main className="viewer-container">
          <DXFViewer
            geometry={geometry}
            isLoading={isLoading}
            error={error}
            onStatusChange={setViewerStatus}
          />
        </main>

        <RightPanel
          analysisResult={analysisResult}
          isLoading={isLoading}
          isOpen={rightPanelOpen}
          onClose={() => setRightPanelOpen(false)}
        />
      </div>

      <StatusBar status={viewerStatus} fileName={uploadedFile?.name} />
    </div>
  );
}
