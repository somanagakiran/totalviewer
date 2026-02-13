import React from 'react';
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

export default function RightPanel({ analysisResult, isLoading }) {
  const hasResult = !!analysisResult;

  return (
    <aside className="right-panel">
      <div className="panel-header">
        <span className="panel-title">Analysis</span>
        {hasResult && (
          <span className="status-badge success">
            <span className="badge-dot" />
            Complete
          </span>
        )}
        {isLoading && (
          <span className="status-badge loading">
            <span className="spinner-badge" />
            Processing
          </span>
        )}
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
              value={hasResult ? analysisResult.holes : null}
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
              value={hasResult ? analysisResult.perimeter : null}
              unit={analysisResult?.units && analysisResult.units !== 'Unknown' ? analysisResult.units.slice(0, 2).toLowerCase() : 'u'}
              color="#3fb950"
              description="Outer boundary length"
            />
          </>
        )}
      </div>

      {/* Summary section */}
      {hasResult && !isLoading && (
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
      {!hasResult && !isLoading && (
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
