import { useState, useCallback } from 'react';
import './SummaryTable.css';

export default function SummaryTable({
  rows,
  onUpdateRow,
  selectedRowId,
  onSelectRow,
  onRemoveRow,
  partsOpen,
  onToggleTable,
  stock,
  onUpdateStock,
  nestingResult,
  nestingError,
  isNesting,
  onRunNesting,
  selectedParts = [],
  onTogglePart,
  onNestSelected,
}) {
  const [nestWarn, setNestWarn] = useState(false);

  const handleNestSelected = useCallback(() => {
    if (selectedParts.length === 0) {
      setNestWarn(true);
      setTimeout(() => setNestWarn(false), 3000);
      return;
    }
    onNestSelected?.();
  }, [selectedParts, onNestSelected]);

  if (rows.length === 0) return null;

  const selCount = selectedParts.length;

  return (
    <div className="summary-table-wrap">

      {/* -- Collapse/expand header bar ------------------------------------ */}
      <div className="st-header-bar">
        <span className="st-header-title">
          Parts List
          <span className="st-header-count">{rows.length}</span>
        </span>
        <button
          className="st-toggle-btn"
          onClick={onToggleTable}
          title={partsOpen ? 'Collapse parts list' : 'Expand parts list'}
          aria-label="Toggle parts list"
        >
          <svg
            width="13" height="13" viewBox="0 0 24 24"
            fill="none" stroke="currentColor" strokeWidth="2.5"
            style={{ transform: partsOpen ? 'rotate(0deg)' : 'rotate(-90deg)', transition: 'transform 0.2s' }}
          >
            <polyline points="6 9 12 15 18 9"/>
          </svg>
        </button>
      </div>

      {/* -- Collapsible table body ---------------------------------------- */}
      <div className={`st-table-collapse${partsOpen ? ' st-table-collapse--open' : ''}`}>
        <table className="summary-table">
          <colgroup>
            <col className="col-partname" />
            <col className="col-filename" />
            <col className="col-material" />
            <col className="col-qty" />
            <col className="col-num" />
            <col className="col-num" />
            <col className="col-num" />
            <col className="col-num" />
            <col className="col-remove" />
          </colgroup>
          <thead>
            <tr>
              <th>Part Name</th>
              <th>File Name</th>
              <th>Material</th>
              <th className="st-num">Qty</th>
              <th className="st-num">Holes</th>
              <th className="st-num">EP</th>
              <th className="st-num">IP</th>
              <th className="st-num">Total</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {rows.map(row => {
              const isNestSel = selectedParts.includes(row.id);
              return (
                <tr
                  key={row.id}
                  className={[
                    'st-row',
                    row.id === selectedRowId ? 'st-row-selected' : '',
                    isNestSel ? 'st-row-nest-sel' : '',
                  ].filter(Boolean).join(' ')}
                  onClick={() => onSelectRow(row.id)}
                >
                  <td onClick={e => e.stopPropagation()}>
                    <div className="st-part-cell">
                      <button
                        className={`st-part-sel${isNestSel ? ' st-part-sel--on' : ''}`}
                        title={isNestSel ? 'Deselect for nesting' : 'Select for nesting'}
                        onClick={() => onTogglePart?.(row.id)}
                        tabIndex={-1}
                      />
                      <input
                        className="st-input"
                        value={row.partName}
                        onChange={e => onUpdateRow(row.id, 'partName', e.target.value)}
                      />
                    </div>
                  </td>
                  <td className="st-filename" title={row.fileName}>{row.fileName}</td>
                  <td onClick={e => e.stopPropagation()}>
                    <select
                      className="st-select"
                      value={row.material}
                      onChange={e => onUpdateRow(row.id, 'material', e.target.value)}
                    >
                      <option value="MS">MS</option>
                      <option value="SS">SS</option>
                    </select>
                  </td>
                  <td className="st-num" onClick={e => e.stopPropagation()}>
                    <input
                      className="st-qty-input"
                      type="number"
                      min="1"
                      max="999"
                      value={row.qty ?? 1}
                      onChange={e => onUpdateRow(row.id, 'qty', Math.max(1, parseInt(e.target.value, 10) || 1))}
                    />
                  </td>
                  <td className="st-num">{row.holes}</td>
                  <td className="st-num">{row.ep.toFixed(2)}</td>
                  <td className="st-num">{row.ip.toFixed(2)}</td>
                  <td className="st-num st-total">{(row.ep + row.ip).toFixed(2)}</td>
                  <td className="st-remove-cell" onClick={e => e.stopPropagation()}>
                    <button
                      className="st-remove-btn"
                      title="Remove part"
                      onClick={() => onRemoveRow(row.id)}
                    >
                      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                        <line x1="18" y1="6" x2="6" y2="18"/>
                        <line x1="6" y1="6" x2="18" y2="18"/>
                      </svg>
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* -- Nesting bar (always visible) ---------------------------------- */}
      <div className="st-nesting-bar">

        <span className="st-nesting-label">Stock Sheet</span>

        <div className="st-nesting-field">
          <label className="st-nesting-field-label">W</label>
          <input
            className="st-nesting-input"
            type="number"
            min="1"
            value={stock.width}
            onChange={e => onUpdateStock('width', e.target.value)}
            title="Sheet Width (mm)"
          />
        </div>

        <div className="st-nesting-field">
          <label className="st-nesting-field-label">H</label>
          <input
            className="st-nesting-input"
            type="number"
            min="1"
            value={stock.height}
            onChange={e => onUpdateStock('height', e.target.value)}
            title="Sheet Height (mm)"
          />
        </div>

        <div className="st-nesting-field">
          <label className="st-nesting-field-label">T</label>
          <input
            className="st-nesting-input"
            type="number"
            min="0"
            value={stock.thickness}
            onChange={e => onUpdateStock('thickness', e.target.value)}
            title="Sheet Thickness (mm)"
          />
        </div>

        <div className="st-nesting-field">
          <label className="st-nesting-field-label">Gap</label>
          <input
            className="st-nesting-input"
            type="number"
            min="0"
            step="0.5"
            value={stock.spacing}
            onChange={e => onUpdateStock('spacing', e.target.value)}
            title="Part-to-part spacing (mm)"
          />
          <span className="st-nesting-unit">mm</span>
        </div>

        <div className="st-nesting-field">
          <label className="st-nesting-field-label">Edge Gap</label>
          <input
            className="st-nesting-input"
            type="number"
            min="0"
            step="0.5"
            value={stock.edge_gap ?? 0}
            onChange={e => onUpdateStock('edge_gap', e.target.value)}
            title="Minimum distance from sheet boundary (mm)"
          />
          <span className="st-nesting-unit">mm</span>
        </div>

        <div className="st-nesting-actions">
          <button
            className={`st-nesting-run${isNesting ? ' st-nesting-run--busy' : ''}`}
            onClick={onRunNesting}
            disabled={isNesting}
            title="Nest all parts"
          >
            {isNesting ? (
              <>
                <svg className="st-spin" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                  <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"/>
                </svg>
                Nesting...
              </>
            ) : (
              <>
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                  <rect x="3" y="3" width="8" height="8" rx="1"/>
                  <rect x="13" y="3" width="8" height="5" rx="1"/>
                  <rect x="13" y="12" width="8" height="9" rx="1"/>
                  <rect x="3" y="15" width="8" height="6" rx="1"/>
                </svg>
                Nest All
              </>
            )}
          </button>

          <button
            className={`st-nesting-run st-nesting-run--selected${isNesting ? ' st-nesting-run--busy' : ''}`}
            onClick={handleNestSelected}
            disabled={isNesting}
            title={selCount > 0 ? `Nest ${selCount} selected part${selCount > 1 ? 's' : ''}` : 'Select parts using the dot on each row'}
          >
            {isNesting ? (
              <>
                <svg className="st-spin" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                  <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"/>
                </svg>
                Nesting...
              </>
            ) : (
              <>
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                  <polyline points="9 11 12 14 22 4"/>
                  <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/>
                </svg>
                Nest Selected
                {selCount > 0 && (
                  <span className="st-sel-badge">{selCount}</span>
                )}
              </>
            )}
          </button>
        </div>

        {nestWarn && (
          <span className="st-nest-warning">Select at least one part first</span>
        )}

        {nestingError && (
          <span className="st-nest-error">{nestingError}</span>
        )}

        {nestingResult && (
          <div className="st-nesting-results">
            <span className="st-nest-stat">
              <span className="st-nest-stat-label">Sheets</span>
              <span className="st-nest-stat-value">{nestingResult.total_sheets}</span>
            </span>
            <span className="st-nest-stat">
              <span className="st-nest-stat-label">Utilization</span>
              <span className="st-nest-stat-value st-nest-util">{nestingResult.utilization}%</span>
            </span>
            <span className="st-nest-stat">
              <span className="st-nest-stat-label">Waste</span>
              <span className="st-nest-stat-value st-nest-waste">{nestingResult.waste}%</span>
            </span>
          </div>
        )}

      </div>

    </div>
  );
}
