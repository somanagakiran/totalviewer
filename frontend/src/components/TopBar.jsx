import React, { useRef } from 'react';
import './TopBar.css';

export default function TopBar({ fileName, onFileUpload, onFitScreen, isLoading }) {
  const fileInputRef = useRef(null);

  const handleUploadClick = () => {
    fileInputRef.current?.click();
  };

  const handleFileChange = (e) => {
    const file = e.target.files?.[0];
    if (file) {
      onFileUpload(file);
      e.target.value = ''; // reset input
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    const file = e.dataTransfer.files?.[0];
    if (file) onFileUpload(file);
  };

  // ── Quote handler (Phase 1 placeholder) ──────────────────────────────────
  // Phase 2: replace body with openQuoteModal({ geometry, analysisResult })
  const handleAddQuote = () => {
    // Future hook: pass geometry + analysis data to costing engine
    // openQuoteModal({ geometry, analysisResult, fileName });
    alert('Quote workflow will be implemented in next phase');
  };

  return (
    <header className="topbar" onDragOver={(e) => e.preventDefault()} onDrop={handleDrop}>
      {/* Logo / App Name */}
      <div className="topbar-brand">
        <div className="brand-icon">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
            <path d="M3 3h8v8H3V3zm10 0h8v8h-8V3zM3 13h8v8H3v-8zm10 4h2v-2h2v2h2v2h-2v2h-2v-2h-2v-2z" fill="currentColor" opacity="0.9"/>
          </svg>
        </div>
        <span className="brand-name">Total Viewer</span>
        <span className="brand-tag">DXF Analysis</span>
      </div>

      {/* Toolbar Actions */}
      <div className="topbar-actions">
        <button
          className="btn-upload"
          onClick={handleUploadClick}
          disabled={isLoading}
          title="Upload DXF File (or drag and drop)"
        >
          {isLoading ? (
            <>
              <span className="spinner-sm" />
              Processing...
            </>
          ) : (
            <>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M17 8l-5-5-5 5M12 3v12"/>
              </svg>
              Open DXF
            </>
          )}
        </button>

        <button
          className="btn-quote"
          onClick={handleAddQuote}
          title="Add Quote for this DXF part"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M20.59 13.41l-7.17 7.17a2 2 0 01-2.83 0L2 12V2h10l8.59 8.59a2 2 0 010 2.82z"/>
            <line x1="7" y1="7" x2="7.01" y2="7"/>
          </svg>
          Add Quote
        </button>

        {fileName && (
          <button
            className="btn-icon"
            onClick={onFitScreen}
            title="Fit drawing to screen"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M8 3H5a2 2 0 00-2 2v3m18 0V5a2 2 0 00-2-2h-3m0 18h3a2 2 0 002-2v-3M3 16v3a2 2 0 002 2h3"/>
            </svg>
          </button>
        )}

        <div className="topbar-separator" />

        {/* Zoom Controls placeholder */}
        <span className="topbar-hint">Scroll to zoom • Drag to pan</span>
      </div>

      {/* File Name Display */}
      {fileName && (
        <div className="topbar-filename">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/>
            <polyline points="14 2 14 8 20 8"/>
          </svg>
          <span title={fileName}>{fileName}</span>
        </div>
      )}

      <input
        ref={fileInputRef}
        type="file"
        accept=".dxf"
        style={{ display: 'none' }}
        onChange={handleFileChange}
      />
    </header>
  );
}
