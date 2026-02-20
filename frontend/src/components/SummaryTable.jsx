import './SummaryTable.css';

export default function SummaryTable({ rows, onUpdateRow, selectedRowId, onSelectRow, partsOpen, onToggleTable }) {
  if (rows.length === 0) return null;

  return (
    <div className="summary-table-wrap">

      {/* ── Collapse/expand header bar ─────────────────────────────── */}
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

      {/* ── Collapsible table body ──────────────────────────────────── */}
      <div className={`st-table-collapse${partsOpen ? ' st-table-collapse--open' : ''}`}>
        <table className="summary-table">
          <colgroup>
            <col className="col-partname" />
            <col className="col-filename" />
            <col className="col-material" />
            <col className="col-num" />
            <col className="col-num" />
            <col className="col-num" />
            <col className="col-num" />
          </colgroup>
          <thead>
            <tr>
              <th>Part Name</th>
              <th>File Name</th>
              <th>Material</th>
              <th className="st-num">Holes</th>
              <th className="st-num">EP</th>
              <th className="st-num">IP</th>
              <th className="st-num">Total</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(row => (
              <tr
                key={row.id}
                className={`st-row${row.id === selectedRowId ? ' st-row-selected' : ''}`}
                onClick={() => onSelectRow(row.id)}
              >
                <td onClick={e => e.stopPropagation()}>
                  <input
                    className="st-input"
                    value={row.partName}
                    onChange={e => onUpdateRow(row.id, 'partName', e.target.value)}
                  />
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
                <td className="st-num">{row.holes}</td>
                <td className="st-num">{row.ep.toFixed(2)}</td>
                <td className="st-num">{row.ip.toFixed(2)}</td>
                <td className="st-num st-total">{(row.ep + row.ip).toFixed(2)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

    </div>
  );
}
