import React from 'react';
import './StatusBar.css';

export default function StatusBar({ status, fileName }) {
  return (
    <div className="status-bar">
      <div className="status-left">
        <span className="status-indicator" />
        <span className="status-text">{status || 'Ready'}</span>
      </div>
      <div className="status-center">
        {fileName && (
          <span className="status-file">{fileName}</span>
        )}
      </div>
      <div className="status-right">
        <span className="status-item">Total Viewer v1.0</span>
        <span className="status-sep">|</span>
        <span className="status-item">DXF Analysis Tool</span>
      </div>
    </div>
  );
}
