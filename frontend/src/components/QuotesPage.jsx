import { useState } from 'react';
import './QuotesPage.css';

const STATUSES = ['All', 'Quoted', 'Order Received', 'Under Production', 'Dispatched', 'Lost', 'Dropped'];

const STATUS_CLASS = {
  'Quoted':           'qs-quoted',
  'Order Received':   'qs-order',
  'Under Production': 'qs-production',
  'Dispatched':       'qs-dispatched',
  'Lost':             'qs-lost',
  'Dropped':          'qs-dropped',
};

function fmt(n) {
  return Number(n || 0).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function fmtDate(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  return isNaN(d) ? iso : d.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' });
}

export default function QuotesPage({ quotes, onUpdateStatus, onNewQuote }) {
  const [filter, setFilter] = useState('All');
  const [search, setSearch]  = useState('');

  const filtered = quotes.filter(q => {
    if (filter !== 'All' && q.status !== filter) return false;
    if (search) {
      const s = search.toLowerCase();
      if (!q.company.toLowerCase().includes(s) && !q.quoteNo.toLowerCase().includes(s)) return false;
    }
    return true;
  });

  const totalAmount = filtered.reduce((s, q) => s + (q.amount || 0), 0);

  return (
    <div className="qp-root">

      {/* ── Page header ── */}
      <div className="qp-header">
        <div className="qp-title-row">
          <div className="qp-page-icon">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M20.59 13.41l-7.17 7.17a2 2 0 01-2.83 0L2 12V2h10l8.59 8.59a2 2 0 010 2.82z"/>
              <line x1="7" y1="7" x2="7.01" y2="7"/>
            </svg>
          </div>
          <h1 className="qp-page-title">Quotes</h1>
          <span className="qp-count-badge">{quotes.length}</span>
        </div>
        <button className="qp-btn-new" onClick={onNewQuote}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
            <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
          </svg>
          New Quote
        </button>
      </div>

      {/* ── Summary strip ── */}
      {quotes.length > 0 && (
        <div className="qp-summary-strip">
          <div className="qp-summary-card">
            <span className="qp-summary-label">Total Quotes</span>
            <span className="qp-summary-value">{quotes.length}</span>
          </div>
          <div className="qp-summary-card">
            <span className="qp-summary-label">Showing</span>
            <span className="qp-summary-value">{filtered.length}</span>
          </div>
          <div className="qp-summary-card">
            <span className="qp-summary-label">Value (filtered)</span>
            <span className="qp-summary-value qp-rupee">₹ {fmt(totalAmount)}</span>
          </div>
        </div>
      )}

      {/* ── Toolbar: filters + search ── */}
      <div className="qp-toolbar">
        <div className="qp-filter-tabs">
          {STATUSES.map(s => (
            <button
              key={s}
              className={`qp-filter-tab${filter === s ? ' active' : ''}`}
              onClick={() => setFilter(s)}
            >
              {s}
            </button>
          ))}
        </div>
        <div className="qp-search-wrap">
          <svg className="qp-search-icon" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
          </svg>
          <input
            className="qp-search"
            placeholder="Search company or quote no…"
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
          {search && (
            <button className="qp-search-clear" onClick={() => setSearch('')} title="Clear">✕</button>
          )}
        </div>
      </div>

      {/* ── Table ── */}
      <div className="qp-table-wrap">
        {filtered.length === 0 ? (
          <div className="qp-empty-state">
            <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
              <path d="M20.59 13.41l-7.17 7.17a2 2 0 01-2.83 0L2 12V2h10l8.59 8.59a2 2 0 010 2.82z"/>
              <line x1="7" y1="7" x2="7.01" y2="7"/>
            </svg>
            <p>{quotes.length === 0 ? 'No quotes yet. Save a quote from the workspace.' : 'No quotes match the current filter.'}</p>
          </div>
        ) : (
          <table className="qp-table">
            <thead>
              <tr>
                <th>Company</th>
                <th>Quote No</th>
                <th>Date</th>
                <th className="qp-th-right">Amount (₹)</th>
                <th className="qp-th-center">Parts</th>
                <th className="qp-th-center">Weight (kg)</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map(q => (
                <tr key={q.id} className="qp-row">
                  <td className="qp-td-company">{q.company}</td>
                  <td className="qp-td-mono">{q.quoteNo}</td>
                  <td className="qp-td-date">{fmtDate(q.date)}</td>
                  <td className="qp-td-right qp-td-amount">₹ {fmt(q.amount)}</td>
                  <td className="qp-td-center">{q.parts || '—'}</td>
                  <td className="qp-td-center">{q.totalWeight ? Number(q.totalWeight).toFixed(2) : '—'}</td>
                  <td>
                    <select
                      className={`qp-status-select ${STATUS_CLASS[q.status] || ''}`}
                      value={q.status}
                      onChange={e => onUpdateStatus(q.id, e.target.value)}
                    >
                      {STATUSES.slice(1).map(s => (
                        <option key={s} value={s}>{s}</option>
                      ))}
                    </select>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

    </div>
  );
}
