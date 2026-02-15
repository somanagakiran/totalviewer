import { useState, useCallback, useEffect } from 'react';
import TopBar from './components/TopBar';
import LeftPanel from './components/LeftPanel';
import RightPanel from './components/RightPanel';
import DXFViewer from './components/DXFViewer';
import StatusBar from './components/StatusBar';
import './App.css';

export default function App() {

  const [uploadedFile, setUploadedFile] = useState(null);
  const [analysisResult, setAnalysisResult] = useState(null);
  const [sessionId, setSessionId] = useState(null);   // ⭐ NEW
  const [geometry, setGeometry] = useState(null);

  const [isLoading, setIsLoading] = useState(false);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analysisComplete, setAnalysisComplete] = useState(false);

  const [error, setError] = useState(null);
  const [analyzeError, setAnalyzeError] = useState(null);
  const [viewerStatus, setViewerStatus] = useState('Ready');

  const [leftPanelOpen, setLeftPanelOpen] = useState(false);
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

  // ─────────────────────────────────────────────
  // RESTORE SESSION AFTER REFRESH
  // ─────────────────────────────────────────────
  useEffect(() => {
    const savedSession = localStorage.getItem('session_id');
    if (savedSession) {
      setSessionId(savedSession);
    }
  }, []);

  // ─────────────────────────────────────────────
  // FILE UPLOAD
  // ─────────────────────────────────────────────
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
    setAnalysisComplete(false);
    setAnalyzeError(null);
    setUploadedFile(file);
    setViewerStatus('Uploading to Python engine…');
    setLeftPanelOpen(false);   // close left panel only; keep/open right for results

    const API_BASE =
      import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';

    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await fetch(`${API_BASE}/upload`, {
        method: 'POST',
        body: formData,
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || 'Upload failed');
      }

      // ⭐ STORE SESSION ID SAFELY
      setSessionId(data.session_id);
      localStorage.setItem('session_id', data.session_id);

      const result = {
        ...data,
        entityCount: data.entities,
        boundingBox: data.bounding_box,
      };

      setAnalysisResult(result);
      setGeometry(data.geometry);
      setAnalysisComplete(true);   // analysis runs inline on upload — always complete
      setRightPanelOpen(true);     // auto-open right panel to show results

      setViewerStatus(
        `Loaded · ${data.entities} entities · ${data.layers?.length ?? 0} layers`
      );

    } catch (err) {
      setError(err.message);
      setViewerStatus('Error loading file');
    } finally {
      setIsLoading(false);
    }

  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ─────────────────────────────────────────────
  // ANALYZE
  // ─────────────────────────────────────────────
  const handleAnalyze = useCallback(async () => {

    if (isAnalyzing) return;

    if (!sessionId) {
      setAnalyzeError('Session not found. Please re-upload the DXF file.');
      return;
    }

    const API_BASE =
      import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';

    setIsAnalyzing(true);

    try {
      const response = await fetch(`${API_BASE}/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || 'Analysis failed');
      }

      setAnalysisResult(prev => ({ ...prev, ...data }));
      setAnalysisComplete(true);

    } catch (err) {
      setAnalyzeError(err.message);
    } finally {
      setIsAnalyzing(false);
    }

  }, [sessionId, isAnalyzing]);

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

      <div
        className={`panel-backdrop${anyPanelOpen ? ' visible' : ''}`}
        onClick={closeAllPanels}
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
          isAnalyzing={isAnalyzing}
          analysisComplete={analysisComplete}
          onAnalyze={handleAnalyze}
          analyzeError={analyzeError}
          isOpen={rightPanelOpen}
          onClose={() => setRightPanelOpen(false)}
        />

      </div>

      <StatusBar status={viewerStatus} fileName={uploadedFile?.name} />

    </div>
  );
}
