import { useRef } from 'react';
import './TopBar.css';

export default function TopBar({
  fileName, onFileUpload, onFitScreen, isLoading,
  leftPanelOpen, onToggleLeft,
  sidebarOpen, onToggleSidebar,
  onOpenSettings,
  onOpenQuote,
}) {
  const fileInputRef = useRef(null);

  const handleUploadClick = () => fileInputRef.current?.click();

  const handleFileChange = (e) => {
    const files = Array.from(e.target.files ?? []);
    if (files.length > 0) { onFileUpload(files); e.target.value = ''; }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    const files = Array.from(e.dataTransfer.files ?? []);
    if (files.length > 0) onFileUpload(files);
  };

  return (
    <header className="topbar" onDragOver={e => e.preventDefault()} onDrop={handleDrop}>

      {/* Brand */}
      <div className="topbar-brand">
        <div className="brand-icon">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
            <path d="M3 3h8v8H3V3zm10 0h8v8h-8V3zM3 13h8v8H3v-8zm10 4h2v-2h2v2h2v2h-2v2h-2v-2h-2v-2z" fill="currentColor" opacity="0.9"/>
          </svg>
        </div>
        <span className="brand-name">Total Viewer</span>
        <span className="brand-tag">Drawing Viewer</span>
      </div>

      {/* Actions */}
      <div className="topbar-actions">

        {/* Sidebar toggle */}
        <button
          className={`btn-sidebar-toggle${sidebarOpen ? '' : ' active'}`}
          onClick={onToggleSidebar}
          title={sidebarOpen ? 'Hide sidebar' : 'Show sidebar'}
          aria-label="Toggle sidebar"
          aria-pressed={!sidebarOpen}
        >
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <rect x="3" y="3" width="18" height="18" rx="2"/>
            <line x1="9" y1="3" x2="9" y2="21"/>
          </svg>
        </button>

        <button
          className={`btn-panel-toggle${leftPanelOpen ? ' active' : ''}`}
          onClick={onToggleLeft}
          title="File Info Panel"
          aria-label="Toggle file info panel"
          aria-pressed={leftPanelOpen}
        >
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <line x1="3" y1="6"  x2="21" y2="6"/>
            <line x1="3" y1="12" x2="21" y2="12"/>
            <line x1="3" y1="18" x2="21" y2="18"/>
          </svg>
        </button>

        {/* Open File */}
        <button
          className="btn-upload"
          onClick={handleUploadClick}
          disabled={isLoading}
          title="Upload DXF / PDF / Image"
        >
          {isLoading ? (
            <><span className="spinner-sm" /><span className="btn-label">Processing…</span></>
          ) : (
            <>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M17 8l-5-5-5 5M12 3v12"/>
              </svg>
              <span className="btn-label">Open File</span>
            </>
          )}
        </button>

        {/* Add Quote */}
        <button
          className="btn-quote"
          onClick={onOpenQuote}
          title="Generate a quotation for loaded parts"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M20.59 13.41l-7.17 7.17a2 2 0 01-2.83 0L2 12V2h10l8.59 8.59a2 2 0 010 2.82z"/>
            <line x1="7" y1="7" x2="7.01" y2="7"/>
          </svg>
          <span className="btn-label">Add Quote</span>
        </button>

        {/* Settings ⚙ */}
        <button
          className="btn-settings"
          onClick={onOpenSettings}
          title="App Settings"
        >
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="12" cy="12" r="3"/>
            <path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-2 2 2 2 0 01-2-2v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83 0 2 2 0 010-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 01-2-2 2 2 0 012-2h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 010-2.83 2 2 0 012.83 0l.06.06A1.65 1.65 0 009 4.68a1.65 1.65 0 001-1.51V3a2 2 0 012-2 2 2 0 012 2v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 0 2 2 0 010 2.83l-.06.06A1.65 1.65 0 0019.4 9a1.65 1.65 0 001.51 1H21a2 2 0 012 2 2 2 0 01-2 2h-.09a1.65 1.65 0 00-1.51 1z"/>
          </svg>
          <span className="btn-label">Settings</span>
        </button>

        {fileName && (
          <button className="btn-icon" onClick={onFitScreen} title="Fit drawing to screen">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M8 3H5a2 2 0 00-2 2v3m18 0V5a2 2 0 00-2-2h-3m0 18h3a2 2 0 002-2v-3M3 16v3a2 2 0 002 2h3"/>
            </svg>
          </button>
        )}

        <div className="topbar-separator" />
        <span className="topbar-hint">Scroll / Pinch to zoom &nbsp;·&nbsp; Drag to pan</span>
      </div>

      {/* File name chip */}
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
        accept=".dxf,.pdf,.jpg,.jpeg,.png"
        multiple
        style={{ display: 'none' }}
        onChange={handleFileChange}
      />
    </header>
  );
}
