import { useRef, useEffect, useState } from 'react';
import './RightPanel.css';

function MetricCard({ icon, label, value, unit, color, description }) {
  return (
    <div className="metric-card" style={{ '--card-accent': color }}>
      <div className="metric-icon" style={{ color }}>
        {icon}
      </div>
      <div className="metric-body">
        <div className="metric-label">{label}</div>
        <div className="metric-value">
          {value != null ? (
            <>
              <span className="metric-num">{value.toLocaleString()}</span>
              {unit && <span className="metric-unit">{unit}</span>}
            </>
          ) : (
            <span className="metric-placeholder">--</span>
          )}
        </div>
        {description && <div className="metric-desc">{description}</div>}
      </div>
    </div>
  );
}

function SkeletonCard() {
  return (
    <div className="metric-card skeleton">
      <div className="sk-icon" />
      <div className="sk-body">
        <div className="sk-line short" />
        <div className="sk-line long" />
      </div>
    </div>
  );
}

export default function RightPanel({
  analysisResult,
  isLoading,
  isOpen,
  onClose,
  isAnalyzing,
  analysisComplete,
  onAnalyze,
  analyzeError,
  fileLoaded,
}) {
  const panelRef  = useRef(null);
  const hasFileData = !!analysisResult;
  const hasAnalysis = hasFileData && analysisComplete;

  // Auto-dismiss toast after 5 s whenever a new error arrives
  const [toastVisible, setToastVisible] = useState(false);
  useEffect(() => {
    if (!analyzeError) { setToastVisible(false); return; }
    setToastVisible(true);
    const t = setTimeout(() => setToastVisible(false), 5000);
    return () => clearTimeout(t);
  }, [analyzeError]);

  // Scroll panel to top when analysis completes so user sees the results
  useEffect(() => {
    if (analysisComplete && panelRef.current) {
      panelRef.current.scrollTo({ top: 0, behavior: 'smooth' });
    }
  }, [analysisComplete]);

  const btnDisabled = !fileLoaded || isAnalyzing || isLoading;

  return (
    <aside ref={panelRef} className={`right-panel${isOpen ? ' is-open' : ''}`}>
      <div className="panel-header">
        <span className="panel-title">Analysis</span>
        {hasAnalysis && !isAnalyzing && (
          <span className="status-badge success">
            <span className="badge-dot" />
            Complete
          </span>
        )}
        {(isLoading || isAnalyzing) && (
          <span className="status-badge loading">
            <span className="spinner-badge" />
            {isLoading ? 'Parsing' : 'Analyzing'}
          </span>
        )}
        {fileLoaded && !hasAnalysis && !isAnalyzing && !isLoading && (
          <span className="status-badge ready">
            <span className="badge-dot-ready" />
            Ready
          </span>
        )}
        {/* Close button — visible on tablet/mobile only via CSS */}
        <button className="panel-close-btn" onClick={onClose} title="Close panel" aria-label="Close panel">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
            <line x1="18" y1="6" x2="6"  y2="18"/>
            <line x1="6"  y1="6" x2="18" y2="18"/>
          </svg>
        </button>
      </div>

      <div className="metrics-container">
        {isLoading ? (
          <>
            <SkeletonCard />
            <SkeletonCard />
          </>
        ) : (
          <>
            <MetricCard
              icon={
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
                  <circle cx="12" cy="12" r="10"/>
                  <circle cx="12" cy="12" r="4"/>
                  <line x1="12" y1="2" x2="12" y2="6"/>
                  <line x1="12" y1="18" x2="12" y2="22"/>
                  <line x1="2" y1="12" x2="6" y2="12"/>
                  <line x1="18" y1="12" x2="22" y2="12"/>
                </svg>
              }
              label="Total Holes"
              value={hasAnalysis ? analysisResult.holes : null}
              color="#58a6ff"
              description="Internal cutouts detected"
            />

            <MetricCard
              icon={
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
                  <rect x="3" y="3" width="18" height="18" rx="2"/>
                  <path d="M3 9h18M3 15h18M9 3v18M15 3v18" strokeOpacity="0.4"/>
                </svg>
              }
              label="Outer Perimeter"
              value={hasAnalysis ? analysisResult.perimeter : null}
              unit={analysisResult?.units && analysisResult.units !== 'Unknown' ? analysisResult.units.slice(0, 2).toLowerCase() : 'u'}
              color="#3fb950"
              description="Outer boundary length"
            />
          </>
        )}
      </div>

      {/* ── Analyze DXF action section ────────────────────────────────── */}
      {!isLoading && (
        <div className="analyze-section">
          <button
            className={`btn-analyze-dxf${hasAnalysis ? ' btn-analyze-done' : ''}`}
            onClick={onAnalyze}
            disabled={btnDisabled}
            title={!hasFileData ? 'Upload a DXF file first' : hasAnalysis ? 'Run analysis again' : 'Click to analyze'}
          >
            {isAnalyzing ? (
              <>
                <span className="btn-spinner-inline" />
                Analyzing…
              </>
            ) : hasAnalysis ? (
              <>
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                  <polyline points="20 6 9 17 4 12"/>
                </svg>
                Re-analyze
              </>
            ) : (
              <>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
                </svg>
                Analyze DXF
              </>
            )}
          </button>

          {toastVisible && analyzeError && (
            <div className="analyze-error-toast">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" style={{ flexShrink: 0 }}>
                <circle cx="12" cy="12" r="10"/>
                <line x1="12" y1="8" x2="12" y2="12"/>
                <line x1="12" y1="16" x2="12.01" y2="16"/>
              </svg>
              <span>{analyzeError}</span>
              <button className="toast-dismiss" onClick={() => setToastVisible(false)} aria-label="Dismiss">
                <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                  <line x1="18" y1="6" x2="6" y2="18"/>
                  <line x1="6" y1="6" x2="18" y2="18"/>
                </svg>
              </button>
            </div>
          )}
        </div>
      )}

      {/* Summary section */}
      {hasFileData && !isLoading && (
        <div className="summary-section">
          <div className="summary-header">Summary</div>
          <div className="summary-body">
            <div className="summary-row">
              <span>File</span>
              <span className="summary-val" title={analysisResult.fileName}>
                {analysisResult.fileName}
              </span>
            </div>
            <div className="summary-row">
              <span>Entities</span>
              <span className="summary-val">{analysisResult.entityCount?.toLocaleString() ?? '--'}</span>
            </div>
            <div className="summary-row">
              <span>Layers</span>
              <span className="summary-val">{analysisResult.layers?.length ?? '--'}</span>
            </div>
            <div className="summary-row">
              <span>Units</span>
              <span className="summary-val">{analysisResult.units ?? '--'}</span>
            </div>
          </div>
        </div>
      )}

      {/* Empty state */}
      {!hasFileData && !isLoading && (
        <div className="right-empty-state">
          <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.2">
            <path d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"/>
          </svg>
          <p>Upload a DXF file to<br/>see analysis results</p>
        </div>
      )}

      {/* Future features placeholder */}
      <div className="future-section">
        <div className="future-header">Coming Soon</div>
        <div className="future-list">
          <div className="future-item">
            <span className="future-dot" />
            Area Calculation
          </div>
          <div className="future-item">
            <span className="future-dot" />
            Bend Line Detection
          </div>
          <div className="future-item">
            <span className="future-dot" />
            Material Nesting
          </div>
          <div className="future-item">
            <span className="future-dot" />
            Cost Estimation
          </div>
          <div className="future-item">
            <span className="future-dot" />
            3D Preview
          </div>
        </div>
      </div>
    </aside>
  );
}
