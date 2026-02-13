import React, { useState } from 'react';
import './LeftPanel.css';

function formatFileSize(bytes) {
  if (!bytes) return '--';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

function formatNumber(n) {
  if (n == null) return '--';
  return n.toLocaleString();
}

export default function LeftPanel({ fileName, fileSize, layers, entityCount, units, boundingBox }) {
  const [layersExpanded, setLayersExpanded] = useState(true);

  const hasFile = !!fileName;

  return (
    <aside className="left-panel">
      <div className="panel-header">
        <span className="panel-title">File Info</span>
      </div>

      {/* File Details */}
      <div className="panel-section">
        <div className="section-label">Document</div>
        <div className="info-grid">
          <div className="info-row">
            <span className="info-key">Name</span>
            <span className="info-val" title={fileName}>{fileName || '--'}</span>
          </div>
          <div className="info-row">
            <span className="info-key">Size</span>
            <span className="info-val">{formatFileSize(fileSize)}</span>
          </div>
          <div className="info-row">
            <span className="info-key">Units</span>
            <span className="info-val">{units || '--'}</span>
          </div>
          <div className="info-row">
            <span className="info-key">Entities</span>
            <span className="info-val">{formatNumber(entityCount)}</span>
          </div>
        </div>
      </div>

      {/* Bounding Box */}
      {boundingBox && boundingBox.width > 0 && (
        <div className="panel-section">
          <div className="section-label">Bounding Box</div>
          <div className="info-grid">
            <div className="info-row">
              <span className="info-key">Width</span>
              <span className="info-val mono">{boundingBox.width.toFixed(2)}</span>
            </div>
            <div className="info-row">
              <span className="info-key">Height</span>
              <span className="info-val mono">{boundingBox.height.toFixed(2)}</span>
            </div>
            <div className="info-row">
              <span className="info-key">Min X</span>
              <span className="info-val mono">{boundingBox.minX.toFixed(2)}</span>
            </div>
            <div className="info-row">
              <span className="info-key">Min Y</span>
              <span className="info-val mono">{boundingBox.minY.toFixed(2)}</span>
            </div>
          </div>
        </div>
      )}

      {/* Layers */}
      <div className="panel-section">
        <button
          className="section-toggle"
          onClick={() => setLayersExpanded(v => !v)}
        >
          <span className="section-label">Layers</span>
          <span className="layer-count">{layers.length}</span>
          <svg
            className={`toggle-arrow ${layersExpanded ? 'expanded' : ''}`}
            width="12" height="12" viewBox="0 0 24 24"
            fill="none" stroke="currentColor" strokeWidth="2.5"
          >
            <polyline points="6 9 12 15 18 9"/>
          </svg>
        </button>

        {layersExpanded && (
          <div className="layer-list">
            {layers.length === 0 && !hasFile && (
              <div className="empty-msg">No file loaded</div>
            )}
            {layers.length === 0 && hasFile && (
              <div className="empty-msg">No layers found</div>
            )}
            {layers.map((layer, i) => (
              <div key={i} className="layer-item">
                <span className="layer-dot" style={{ background: getLayerColor(i) }} />
                <span className="layer-name">{layer || '0'}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Empty state */}
      {!hasFile && (
        <div className="panel-empty-state">
          <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
            <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/>
            <polyline points="14 2 14 8 20 8"/>
            <line x1="12" y1="18" x2="12" y2="12"/>
            <line x1="9" y1="15" x2="15" y2="15"/>
          </svg>
          <span>Open a DXF file<br/>to view details</span>
        </div>
      )}
    </aside>
  );
}

const LAYER_COLORS = [
  '#58a6ff', '#3fb950', '#f0883e', '#a371f7',
  '#d29922', '#79c0ff', '#56d364', '#ff7b72'
];

function getLayerColor(index) {
  return LAYER_COLORS[index % LAYER_COLORS.length];
}
