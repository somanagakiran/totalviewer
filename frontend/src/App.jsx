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
      />

      <div className="app-body">
        <LeftPanel
          fileName={uploadedFile?.name}
          fileSize={uploadedFile?.size}
          layers={analysisResult?.layers || []}
          entityCount={analysisResult?.entityCount}
          units={analysisResult?.units}
          boundingBox={analysisResult?.boundingBox}
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
        />
      </div>

      <StatusBar status={viewerStatus} fileName={uploadedFile?.name} />
    </div>
  );
}
