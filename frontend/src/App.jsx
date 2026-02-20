import { useState, useCallback, useRef } from 'react';
import TopBar from './components/TopBar';
import LeftPanel from './components/LeftPanel';
import RightPanel from './components/RightPanel';
import DXFViewer from './components/DXFViewer';
import StatusBar from './components/StatusBar';
import './App.css';

export default function App() {

  const [uploadedFile, setUploadedFile] = useState(null);
  const [analysisResult, setAnalysisResult] = useState(null);
  const [geometry, setGeometry] = useState(null);

  const [isLoading, setIsLoading] = useState(false);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analysisComplete, setAnalysisComplete] = useState(false);

  const [error, setError] = useState(null);
  const [analyzeError, setAnalyzeError] = useState(null);
  const [viewerStatus, setViewerStatus] = useState('Ready');

  const [leftPanelOpen, setLeftPanelOpen] = useState(false);
  const [rightPanelOpen, setRightPanelOpen] = useState(false);

  // Stores whichever backend URL (Render or localhost) responded successfully
  const apiBaseRef = useRef(null);

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

    const PRIMARY  = import.meta.env.VITE_API_BASE_URL     ?? 'http://localhost:8000';
    const FALLBACK = import.meta.env.VITE_API_FALLBACK_URL ?? 'http://localhost:8000';

    // Try primary (Render), silently fall back to localhost if unreachable
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
    if (await tryPing(PRIMARY))  API_BASE = PRIMARY;
    else if (await tryPing(FALLBACK)) API_BASE = FALLBACK;
    else {
      setError('Cannot reach backend. Ensure Python server is running.');
      setViewerStatus('Error loading file');
      setIsLoading(false);
      return;
    }
    apiBaseRef.current = API_BASE;

    const formData = new FormData();
    formData.append('file', file);

    try {
      // Upload with timeout (20s) to avoid getting stuck on network issues
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), 20000);
      const response = await fetch(`${API_BASE}/upload`, {
        method: 'POST',
        body: formData,
        signal: controller.signal,
      });
      clearTimeout(timer);

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || 'Upload failed');
      }

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
      const msg = err?.name === 'AbortError'
        ? 'Upload timed out. Please try again.'
        : (err?.message || 'Upload failed');
      setError(msg);
      setViewerStatus('Error loading file');
    } finally {
      setIsLoading(false);
    }

  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ─────────────────────────────────────────────
  // ANALYZE
  // Prefer calling /analyze with existing session_id.
  // Falls back to re-upload if session is missing.
  // ─────────────────────────────────────────────
  const handleAnalyze = useCallback(async () => {
    if (isLoading || isAnalyzing) return;
    if (!uploadedFile) {
      setAnalyzeError('No file loaded. Please upload a DXF file first.');
      return;
    }

    const API_BASE =
      apiBaseRef.current ?? import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';

    // If we have a session, call /analyze for a fast re-run
    const sid = analysisResult?.session_id;
    if (sid) {
      try {
        setAnalyzeError(null);
        setIsAnalyzing(true);
        setViewerStatus('Re-running analysis…');

        const resp = await fetch(`${API_BASE}/analyze`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ session_id: sid }),
        });

        const data = await resp.json();
        if (!resp.ok) {
          throw new Error(data.detail || 'Analyze failed');
        }

        const updated = {
          ...analysisResult,
          ...data,
        };
        setAnalysisResult(updated);
        setAnalysisComplete(true);
        setRightPanelOpen(true);
        setViewerStatus('Analysis complete');
      } catch (err) {
        // Fall back to re-upload on error
        setAnalyzeError(err.message);
        await handleFileUpload(uploadedFile);
      } finally {
        setIsAnalyzing(false);
      }
      return;
    }

    // No session_id — re-upload the file to regenerate a session + results
    await handleFileUpload(uploadedFile);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [uploadedFile, isLoading, isAnalyzing, analysisResult]);

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
          fileLoaded={!!uploadedFile}
          isOpen={rightPanelOpen}
          onClose={() => setRightPanelOpen(false)}
        />

      </div>

      <StatusBar status={viewerStatus} fileName={uploadedFile?.name} />

    </div>
  );
}
